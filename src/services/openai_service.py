import logging
import time
import hashlib
import httpx
from typing import Optional, Dict, Any
from openai import AzureOpenAI
from openai.types.chat import ChatCompletion
from ..utils.prompt_manager import PromptManager
from ..utils.cache_manager import get_cache_manager
from ..utils.connection_pool import connection_pool_manager, ExponentialBackoff
from ..exceptions import (
    OpenAIAPIException, NetworkException, TimeoutException,
    RateLimitException, ValidationException, BaseBotException,
    create_correlation_id, wrap_api_exception
)
from ..utils.error_handler import StructuredLogger, error_handler, retry_with_backoff

logger = StructuredLogger(__name__)

class OpenAIService:
    """Azure OpenAI service with hybrid Responses API + Chat Completions support"""
    
    def __init__(self, settings, conversation_service):
        self.settings = settings
        self.conversation_service = conversation_service
        
        # Initialize prompt manager
        self.prompt_manager = PromptManager()
        self.system_prompt = self.prompt_manager.get_default_system_prompt()
        
        # Initialize cache manager
        self.cache_manager = get_cache_manager()
        
        # Initialize Azure OpenAI client with fallback support
        # Try next generation v1 API first, fall back to standard if needed
        self.base_url = f"{settings.AZURE_OPENAI_ENDPOINT.rstrip('/')}/openai/v1/"
        
        # Initialize connection pool for Azure OpenAI
        self._setup_connection_pools()
        
        try:
            # Create clients with connection pooling
            self.client = self._create_pooled_client(
                api_key=settings.AZURE_OPENAI_API_KEY,
                api_version="preview",  # For Responses API support
                base_url=self.base_url,
                client_name="openai_primary"
            )
            
            # Fallback client for Chat Completions if Responses API not available
            self.fallback_client = self._create_pooled_client(
                api_key=settings.AZURE_OPENAI_API_KEY,
                api_version=settings.AZURE_OPENAI_API_VERSION,
                azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
                client_name="openai_fallback"
            )
            
            logger.info("Initialized Azure OpenAI service with connection pooling")
            
        except Exception as e:
            raise OpenAIAPIException(
                message=f"Failed to initialize Azure OpenAI client: {str(e)}",
                original_exception=e,
                context={
                    'endpoint': settings.AZURE_OPENAI_ENDPOINT,
                    'api_version': settings.AZURE_OPENAI_API_VERSION
                }
            )
        
        # Circuit breaker for API availability with TTL cache
        self.responses_api_available = None
        self.api_check_timestamp = None
        self.api_check_ttl = 300  # 5 minutes cache
        self.api_failure_count = 0
        self.max_failures_before_fallback = 3
        self.failure_reset_time = 600  # 10 minutes
        
        # Caching configuration
        self.enable_caching = True
        self.cache_ttl = 3600  # 1 hour default cache TTL
        
        # Connection pool monitoring
        self.connection_metrics = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'avg_response_time': 0.0,
            'connection_reuse_count': 0
        }
    
    def _setup_connection_pools(self):
        """Set up connection pools for Azure OpenAI API calls."""
        # Create dedicated session for Azure OpenAI primary endpoint
        self.primary_session = connection_pool_manager.create_session_with_pooling(
            name="azure_openai_primary",
            base_url=self.base_url,
            pool_maxsize=20,  # Increased pool size for OpenAI API
            max_retries=3,
            enable_keep_alive=True
        )
        
        # Create dedicated session for Azure OpenAI fallback endpoint
        fallback_url = f"{self.settings.AZURE_OPENAI_ENDPOINT.rstrip('/')}/openai/deployments/{self.settings.AZURE_OPENAI_DEPLOYMENT_NAME}/"
        self.fallback_session = connection_pool_manager.create_session_with_pooling(
            name="azure_openai_fallback", 
            base_url=fallback_url,
            pool_maxsize=10,  # Smaller pool for fallback
            max_retries=2,
            enable_keep_alive=True
        )
        
        # Start connection pool monitoring
        connection_pool_manager.start_monitoring()
        
        logger.info("Set up connection pools for Azure OpenAI service")
    
    def _create_pooled_client(self, api_key: str, api_version: str, 
                            client_name: str, base_url: str = None, 
                            azure_endpoint: str = None) -> AzureOpenAI:
        """Create Azure OpenAI client with connection pooling."""
        # Configure httpx client for OpenAI with connection pooling
        http_client = httpx.Client(
            limits=httpx.Limits(
                max_keepalive_connections=20,
                max_connections=50,
                keepalive_expiry=30.0
            ),
            timeout=httpx.Timeout(
                connect=10.0,
                read=30.0,
                write=10.0,
                pool=5.0
            ),
            http2=True,  # Enable HTTP/2 for better performance
            follow_redirects=True
        )
        
        # Create Azure OpenAI client with custom HTTP client
        client_config = {
            'api_key': api_key,
            'api_version': api_version,
            'http_client': http_client,
            'timeout': 30.0
        }
        
        if base_url:
            client_config['base_url'] = base_url
            client_config['azure_endpoint'] = None
        else:
            client_config['azure_endpoint'] = azure_endpoint
        
        client = AzureOpenAI(**client_config)
        
        # Register client for health monitoring
        connection_pool_manager.health_monitor.register_connection(
            client_name,
            lambda: self._health_check_openai_client(client),
            failure_threshold=3
        )
        
        logger.info(f"Created pooled Azure OpenAI client: {client_name}")
        return client
    
    def _health_check_openai_client(self, client: AzureOpenAI) -> bool:
        """Perform health check for Azure OpenAI client."""
        try:
            # Perform a lightweight API call to check connectivity
            # This is a placeholder - actual implementation would depend on available endpoints
            return client is not None and hasattr(client, 'chat')
        except Exception as e:
            logger.warning(f"Azure OpenAI client health check failed: {e}")
            return False
    
    def get_connection_metrics(self) -> Dict[str, Any]:
        """Get connection pool and service metrics."""
        pool_metrics = connection_pool_manager.get_metrics()
        
        return {
            'service_metrics': self.connection_metrics,
            'connection_pool_metrics': pool_metrics,
            'total_pools': len([p for p in pool_metrics.get('pools', {}) if 'azure_openai' in p])
        }

    def update_system_prompt(self, prompt_type: str = "default"):
        """Update the system prompt to a different variation"""
        if prompt_type == "minimal":
            self.system_prompt = self.prompt_manager.get_minimal_prompt()
        elif prompt_type == "cultural":
            self.system_prompt = self.prompt_manager.get_cultural_focused_prompt()
        else:  # default
            self.system_prompt = self.prompt_manager.get_default_system_prompt()
        
        logger.info(f"Updated system prompt to: {prompt_type}")

    def get_prompt_manager(self):
        """Get access to the prompt manager for advanced customization"""
        return self.prompt_manager

    def _should_use_responses_api(self):
        """Determine if Responses API should be used based on circuit breaker pattern"""
        current_time = time.time()
        
        # Check if we have a cached result that's still valid
        if (self.responses_api_available is not None and 
            self.api_check_timestamp is not None and 
            current_time - self.api_check_timestamp < self.api_check_ttl):
            return self.responses_api_available
        
        # Check if we're in failure cooldown period
        if (self.api_failure_count >= self.max_failures_before_fallback and
            self.api_check_timestamp is not None and
            current_time - self.api_check_timestamp < self.failure_reset_time):
            logger.debug("Responses API in failure cooldown, using Chat Completions")
            return False
        
        # Reset failure count after cooldown period
        if (self.api_failure_count >= self.max_failures_before_fallback and
            self.api_check_timestamp is not None and
            current_time - self.api_check_timestamp >= self.failure_reset_time):
            logger.info("Resetting Responses API failure count after cooldown")
            self.api_failure_count = 0
            self.responses_api_available = None
        
        # If we don't have a cached result, assume Responses API is available
        # and let the actual API call determine if it works
        if self.responses_api_available is None:
            logger.debug("No cached API availability, defaulting to Responses API")
            self.responses_api_available = True
            self.api_check_timestamp = current_time
        
        return self.responses_api_available

    @error_handler(reraise=False, default_return={'success': False, 'error': 'OpenAI service unavailable'})
    @retry_with_backoff(
        max_attempts=3,
        base_delay=1.0,
        max_delay=30.0,
        handle_types=(OpenAIAPIException, NetworkException, TimeoutException)
    )
    def get_response(self, user_id, user_message, use_streaming=True, image_data=None, file_data=None, file_name=None):
        """Get AI response using Responses API with Chat Completions fallback, caching, and comprehensive error handling."""
        correlation_id = create_correlation_id()
        
        with logger.context(
            correlation_id=correlation_id, 
            operation='get_openai_response',
            user_id=user_id[:8] + '...' if user_id else None
        ):
            logger.info("Processing OpenAI request")
            
            try:
                # Update connection pool usage tracking
                start_time = time.time()
                self.connection_metrics['total_requests'] += 1
                
                # Validate inputs
                if not user_id:
                    raise ValidationException(
                        message="User ID is required",
                        field="user_id",
                        correlation_id=correlation_id
                    )
                
                if not user_message and not image_data:
                    raise ValidationException(
                        message="Either user message or image data is required",
                        field="user_message",
                        correlation_id=correlation_id
                    )
                
                # Check cache for non-streaming requests without image data
                if not use_streaming and not image_data and self.enable_caching:
                    cached_response = self._get_cached_response(
                        user_id=user_id,
                        user_message=user_message,
                        correlation_id=correlation_id
                    )
                    if cached_response:
                        logger.info("Returning cached OpenAI response", correlation_id=correlation_id)
                        return cached_response
                
                # Use connection pool with retry logic and circuit breaker pattern
                response = None
                client_name = "azure_openai_primary" if self._should_use_responses_api() else "azure_openai_fallback"
                
                # Execute with connection pooling and retry logic
                def execute_openai_request():
                    if self._should_use_responses_api():
                        return self._get_response_with_responses_api(
                            user_id, user_message, use_streaming, image_data, 
                            file_data, file_name, correlation_id
                        )
                    else:
                        return self._get_response_with_chat_completions(
                            user_id, user_message, use_streaming, image_data, 
                            file_data, file_name, correlation_id
                        )
                
                # Use connection pool manager with retry logic
                backoff = ExponentialBackoff(base_delay=1.0, max_delay=30.0, multiplier=2.0)
                response = connection_pool_manager.execute_with_retry(
                    client_name, 
                    execute_openai_request, 
                    max_attempts=3, 
                    backoff=backoff
                )
                
                # Cache successful non-streaming responses
                if (response.get('success') and not use_streaming and 
                    not image_data and self.enable_caching):
                    self._cache_response(
                        user_id=user_id,
                        user_message=user_message,
                        response=response,
                        correlation_id=correlation_id
                    )
                
                # Update connection metrics
                response_time = time.time() - start_time
                self.connection_metrics['successful_requests'] += 1
                self.connection_metrics['avg_response_time'] = (
                    (self.connection_metrics['avg_response_time'] * (self.connection_metrics['successful_requests'] - 1) + response_time) /
                    self.connection_metrics['successful_requests']
                )
                
                logger.info(
                    f"OpenAI request completed successfully with connection pooling",
                    correlation_id=correlation_id,
                    extra_context={
                        'response_length': len(response.get('message', '')) if response.get('message') else 0,
                        'tokens_used': response.get('tokens_used', 0),
                        'response_time': response_time,
                        'client_name': client_name
                    }
                )
                
                return response
                
            except ValidationException:
                # Re-raise validation errors
                self.connection_metrics['failed_requests'] += 1
                raise
                
            except Exception as e:
                # Update failure metrics
                self.connection_metrics['failed_requests'] += 1
                logger.error(
                    f"OpenAI request failed with connection pooling",
                    correlation_id=correlation_id,
                    extra_context={'error': str(e)}
                )
                # Wrap OpenAI API errors
                if hasattr(e, 'status_code'):
                    if e.status_code == 429:
                        raise RateLimitException(
                            message=f"OpenAI API rate limit exceeded: {str(e)}",
                            retry_after=60,
                            service="Azure_OpenAI",
                            correlation_id=correlation_id,
                            original_exception=e
                        )
                    else:
                        raise OpenAIAPIException(
                            message=f"OpenAI API error: {str(e)}",
                            status_code=e.status_code,
                            correlation_id=correlation_id,
                            original_exception=e
                        )
                else:
                    # Wrap other exceptions
                    raise wrap_api_exception(
                        original_exception=e,
                        api_name="Azure_OpenAI",
                        operation="get_response",
                        correlation_id=correlation_id
                    )

    def _get_response_with_responses_api(self, user_id, user_message, use_streaming=True, image_data=None, file_data=None, file_name=None, correlation_id=None):
        """Get response using Responses API with server-side conversation state"""
        try:
            # Track successful API usage
            self._record_api_success()
            # Get the last response ID for this user to maintain conversation context
            previous_response_id = self.conversation_service.get_last_response_id(user_id)
            
            # Add user message to conversation history with media metadata
            if image_data:
                message_type = "image"
            elif file_data:
                message_type = "file"
            else:
                message_type = "text"

            metadata = {"api_used": "responses"}
            if image_data:
                metadata["has_image"] = True
                metadata["image_processed"] = True
            if file_data:
                metadata["has_file"] = True
            
            self.conversation_service.add_message(
                user_id, 
                "user", 
                user_message,
                message_type=message_type,
                metadata=metadata
            )
            
            # Create the user input with optional media using Responses API format
            if image_data:
                user_input = [
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": user_message},
                            {
                                "type": "input_image",
                                "image_url": {
                                    "url": image_data,
                                    "detail": "high"
                                }
                            }
                        ]
                    }
                ]
            elif file_data:
                file_id = self._upload_file(file_data, file_name)
                user_input = [
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": user_message},
                            {"type": "input_file", "file_id": file_id},
                        ],
                    }
                ]
            else:
                user_input = user_message
            
            if use_streaming:
                return self._get_streaming_response_api(user_id, user_input, previous_response_id)
            else:
                return self._get_standard_response_api(user_id, user_input, previous_response_id)
                
        except Exception as e:
            logger.error(f"Responses API error for user {user_id}: {str(e)}")
            # Record API failure and fall back to Chat Completions
            self._record_api_failure(e)
            logger.info(f"Falling back to Chat Completions for user {user_id}")
            return self._get_response_with_chat_completions(user_id, user_message, use_streaming, image_data)

    def _get_response_with_chat_completions(self, user_id, user_message, use_streaming=True, image_data=None, file_data=None, file_name=None, correlation_id=None):
        """Get response using traditional Chat Completions API"""
        try:
            # Add user message to conversation history
            if image_data:
                message_type = "image"
            elif file_data:
                message_type = "file"
            else:
                message_type = "text"

            metadata = {"api_used": "chat_completions"}
            if image_data:
                metadata["has_image"] = True
                metadata["image_processed"] = True
            if file_data:
                metadata["has_file"] = True
            
            self.conversation_service.add_message(
                user_id, 
                "user", 
                user_message,
                message_type=message_type,
                metadata=metadata
            )
            
            # Get conversation history
            conversation_history = self.conversation_service.get_conversation_history(user_id)
            
            # Prepare messages for OpenAI Chat Completions
            messages = [{"role": "system", "content": self.system_prompt}]
            
            # Add conversation history (limit to last 500 messages to maintain context)
            recent_messages = conversation_history[-500:]
            for msg in recent_messages:
                messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
            
            # Create the current user message with optional media
            file_id = self._upload_file(file_data, file_name) if file_data else None
            current_message = self._create_message_with_image_chat_completions(user_message, image_data, file_id)
            messages.append(current_message)
            
            if use_streaming:
                return self._get_streaming_response_chat_completions(user_id, messages, file_id)
            else:
                return self._get_standard_response_chat_completions(user_id, messages, file_id)
                
        except Exception as e:
            logger.error(f"Chat Completions API error for user {user_id}: {str(e)}")
            raise e

    def _get_standard_response_api(self, user_id, user_input, previous_response_id=None):
        """Get standard response from Responses API"""
        try:
            response = self.client.responses.create(
                model=self.settings.AZURE_OPENAI_DEPLOYMENT_NAME,
                input=user_input,
                instructions=self.system_prompt,
                previous_response_id=previous_response_id,
                max_output_tokens=800,
                temperature=0.7,
                top_p=0.9,
                store=True,
                stream=False
            )
            
            ai_message = response.output_text
            if ai_message:
                ai_message = ai_message.strip()
            else:
                ai_message = "I apologize, but I couldn't generate a response. Please try again."

            total_tokens = response.usage.total_tokens if response.usage else 0
            response_id = response.id
            
            # Store the response ID for future conversation context
            if response_id:
                self.conversation_service.set_last_response_id(user_id, response_id)
            
            # Add AI response to conversation history
            self.conversation_service.add_message(user_id, "assistant", ai_message)
            
            logger.info(f"Generated Responses API response for user {user_id} (length: {len(ai_message)})")
            
            return {
                'success': True,
                'message': ai_message,
                'tokens_used': total_tokens,
                'streaming': False,
                'response_id': response_id,
                'api_used': 'responses'
            }
            
        except Exception as e:
            logger.error(f"Responses API standard error for user {user_id}: {str(e)}")
            self._record_api_failure(e)
            raise e

    def _get_standard_response_chat_completions(self, user_id, messages, file_id=None):
        """Get standard response from Chat Completions API"""
        try:
            from typing import cast
            from openai.types.chat import ChatCompletionMessageParam
            
            formatted_messages = cast(list[ChatCompletionMessageParam], messages)
            
            kwargs = {
                "model": self.settings.AZURE_OPENAI_DEPLOYMENT_NAME,
                "messages": formatted_messages,
                "max_tokens": 800,
                "temperature": 0.7,
                "top_p": 0.9,
                "frequency_penalty": 0.1,
                "presence_penalty": 0.1,
                "stream": False,
            }
            if file_id:
                kwargs["file_ids"] = [file_id]

            response = self.fallback_client.chat.completions.create(**kwargs)
            
            message = response.choices[0].message
            ai_message = message.content
            if ai_message:
                ai_message = ai_message.strip()
            else:
                ai_message = "I apologize, but I couldn't generate a response. Please try again."

            total_tokens = response.usage.total_tokens if response.usage else 0
            
            # Add AI response to conversation history
            self.conversation_service.add_message(user_id, "assistant", ai_message)
            
            logger.info(f"Generated Chat Completions response for user {user_id} (length: {len(ai_message)})")
            
            return {
                'success': True,
                'message': ai_message,
                'tokens_used': total_tokens,
                'streaming': False,
                'api_used': 'chat_completions'
            }
            
        except Exception as e:
            logger.error(f"Chat Completions standard error for user {user_id}: {str(e)}")
            raise e

    def _get_streaming_response_api(self, user_id, user_input, previous_response_id=None):
        """Get streaming response from Responses API"""
        try:
            stream = self.client.responses.create(
                model=self.settings.AZURE_OPENAI_DEPLOYMENT_NAME,
                input=user_input,
                instructions=self.system_prompt,
                previous_response_id=previous_response_id,
                max_output_tokens=800,
                temperature=0.7,
                top_p=0.9,
                store=True,
                stream=True
            )
            
            full_response = ""
            total_tokens = 0
            response_id = None
            
            for event in stream:
                if hasattr(event, 'response') and event.response and not response_id:
                    response_id = event.response.id
                
                if hasattr(event, 'type') and event.type == 'response.output_text.delta':
                    content = event.delta
                    if content:
                        full_response += content
                
                elif hasattr(event, 'type') and event.type == 'response.done':
                    if hasattr(event, 'response') and event.response:
                        if hasattr(event.response, 'usage') and event.response.usage:
                            total_tokens = event.response.usage.total_tokens
                        if not response_id:
                            response_id = event.response.id
            
            if full_response:
                full_response = full_response.strip()
            else:
                full_response = "I apologize, but I couldn't generate a response. Please try again."
            
            # Store the response ID for future conversation context
            if response_id:
                self.conversation_service.set_last_response_id(user_id, response_id)
            
            # Add AI response to conversation history
            self.conversation_service.add_message(user_id, "assistant", full_response)
            
            return {
                'success': True,
                'message': full_response,
                'tokens_used': total_tokens,
                'streaming': True,
                'response_id': response_id,
                'api_used': 'responses'
            }
            
        except Exception as e:
            logger.error(f"Responses API streaming error for user {user_id}: {str(e)}")
            self._record_api_failure(e)
            raise e

    def _get_streaming_response_chat_completions(self, user_id, messages, file_id=None):
        """Get streaming response from Chat Completions API"""
        try:
            from typing import cast
            from openai.types.chat import ChatCompletionMessageParam
            
            formatted_messages = cast(list[ChatCompletionMessageParam], messages)
            
            kwargs = {
                "model": self.settings.AZURE_OPENAI_DEPLOYMENT_NAME,
                "messages": formatted_messages,
                "max_tokens": 800,
                "temperature": 0.7,
                "top_p": 0.9,
                "frequency_penalty": 0.1,
                "presence_penalty": 0.1,
                "stream": True,
            }
            if file_id:
                kwargs["file_ids"] = [file_id]

            stream = self.fallback_client.chat.completions.create(**kwargs)
            
            full_response = ""
            total_tokens = 0
            
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_response += content
                
                if hasattr(chunk, 'usage') and chunk.usage:
                    total_tokens = chunk.usage.total_tokens
            
            if full_response:
                full_response = full_response.strip()
            else:
                full_response = "I apologize, but I couldn't generate a response. Please try again."
            
            # Add AI response to conversation history
            self.conversation_service.add_message(user_id, "assistant", full_response)
            
            return {
                'success': True,
                'message': full_response,
                'tokens_used': total_tokens,
                'streaming': True,
                'api_used': 'chat_completions'
            }
            
        except Exception as e:
            logger.error(f"Chat Completions streaming error for user {user_id}: {str(e)}")
            raise e

    def get_response_with_image(self, user_id, message_id, line_bot_api, accompanying_text="", use_streaming=True):
        """Get AI response for image message with hybrid API support"""
        try:
            from ..utils.image_utils import ImageProcessor
            
            # Use context manager for automatic cleanup
            with ImageProcessor() as processor:
                # Download and process the image
                download_result = processor.download_image_from_line(line_bot_api, message_id)
                
                if not download_result['success']:
                    logger.error(f"Failed to download image: {download_result['error']}")
                    return {
                        'success': False,
                        'error': download_result['error'],
                        'message': None
                    }
                
                # Preprocess image if needed
                processed_image_data = processor.preprocess_image_if_needed(download_result['image_data'])
                
                # Convert to base64 for OpenAI API
                image_base64 = processor.image_to_base64(processed_image_data, download_result['format'])
                
                logger.info(f"Processing image for user {user_id}: {download_result['format']} ({download_result['size']} bytes)")
                
                # Use the main get_response method with image data
                return self.get_response(
                    user_id=user_id,
                    user_message=accompanying_text if accompanying_text else "What do you see in this image? Please describe it and help me understand what it shows.",
                    use_streaming=use_streaming,
                    image_data=image_base64
                )
                    
        except Exception as e:
            logger.error(f"Vision API error for user {user_id}: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'message': None
            }

    def _create_message_with_image_chat_completions(self, text_content: str, image_data=None, file_id=None):
        """Create message structure with optional image or file for Chat Completions API"""
        if not image_data and not file_id:
            return {
                "role": "user",
                "content": text_content
            }

        content = [
            {"type": "text", "text": text_content}
        ]

        if image_data:
            content.append({
                "type": "image_url",
                "image_url": {"url": image_data}
            })

        if file_id:
            content.append({"type": "file_id", "file_id": file_id})

        return {"role": "user", "content": content}

    def get_streaming_response_with_callback(self, user_id, user_input, previous_response_id=None, chunk_callback=None):
        """Get streaming response with callback support (legacy method for compatibility)"""
        # For now, delegate to the appropriate method based on circuit breaker
        if self._should_use_responses_api():
            logger.info("Using Responses API for streaming with callback")
            # Note: Full callback support for Responses API streaming would need more implementation
            return self._get_streaming_response_api(user_id, user_input, previous_response_id)
        else:
            logger.info("Using Chat Completions for streaming with callback")
            # Convert user_input back to messages format for chat completions
            if isinstance(user_input, str):
                messages = [{"role": "system", "content": self.system_prompt}, {"role": "user", "content": user_input}]
            else:
                messages = [{"role": "system", "content": self.system_prompt}] + user_input
            return self._get_streaming_response_chat_completions(user_id, messages)

    def _upload_file(self, file_data: bytes, file_name: str | None) -> str:
        """Upload a file to OpenAI and return the file ID"""
        import io
        upload_name = file_name or "upload.dat"
        file_obj = io.BytesIO(file_data)
        # Use 'assistants' purpose for general file analysis, 'vision' is specifically for images
        response = self.client.files.create(file=(upload_name, file_obj), purpose="assistants")
        return response.id

    def _record_api_success(self):
        """Record successful API usage and reset failure count"""
        if self.api_failure_count > 0:
            logger.info(f"Responses API recovered after {self.api_failure_count} failures")
        self.api_failure_count = 0
        self.responses_api_available = True
        self.api_check_timestamp = time.time()
    
    def _record_api_failure(self, error):
        """Record API failure and update circuit breaker state"""
        self.api_failure_count += 1
        self.api_check_timestamp = time.time()
        
        # Check if this is a permanent failure (404, not found)
        if "404" in str(error) or "not found" in str(error).lower():
            logger.info("Responses API permanently unavailable (404), switching to Chat Completions")
            self.responses_api_available = False
            self.api_failure_count = self.max_failures_before_fallback
        elif self.api_failure_count >= self.max_failures_before_fallback:
            logger.warning(f"Responses API failed {self.api_failure_count} times, temporarily switching to Chat Completions")
            self.responses_api_available = False
        else:
            logger.debug(f"Responses API failure {self.api_failure_count}/{self.max_failures_before_fallback}")
    
    def test_connection(self):
        """Test connection by making an actual API call without pre-flight checks"""
        try:
            # Try Responses API first if circuit breaker allows it
            if self._should_use_responses_api():
                try:
                    response = self.client.responses.create(
                        model=self.settings.AZURE_OPENAI_DEPLOYMENT_NAME,
                        input="Say 'Connection test successful' in both English and Thai.",
                        instructions="You are a helpful assistant.",
                        max_output_tokens=100,
                        temperature=0.3,
                        store=False
                    )
                    
                    self._record_api_success()
                    return {
                        'success': True,
                        'message': response.output_text,
                        'tokens_used': response.usage.total_tokens if response.usage else 0,
                        'api_type': 'responses'
                    }
                except Exception as e:
                    logger.info(f"Responses API test failed, trying Chat Completions: {e}")
                    self._record_api_failure(e)
                    # Fall through to Chat Completions
            
            # Use Chat Completions as fallback
            from typing import cast
            from openai.types.chat import ChatCompletionMessageParam
            
            test_messages = cast(list[ChatCompletionMessageParam], [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Say 'Connection test successful' in both English and Thai."}
            ])
            
            response = self.fallback_client.chat.completions.create(
                model=self.settings.AZURE_OPENAI_DEPLOYMENT_NAME,
                messages=test_messages,
                max_tokens=100,
                temperature=0.3
            )
            
            return {
                'success': True,
                'message': response.choices[0].message.content,
                'tokens_used': response.usage.total_tokens if response.usage else 0,
                'api_type': 'chat_completions'
            }
            
        except Exception as e:
            logger.error(f"Connection test failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'api_type': 'unknown'
            }
    
    def _get_cached_response(self, user_id: str, user_message: str, correlation_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached OpenAI response if available."""
        try:
            # Get conversation context hash for cache key
            context_hash = self._generate_context_hash(user_id)
            
            cached_response = self.cache_manager.get_cached_openai_response(
                user_id=user_id,
                message=user_message,
                context_hash=context_hash,
                model=self.settings.AZURE_OPENAI_DEPLOYMENT_NAME,
                temperature=0.7
            )
            
            if cached_response:
                return {
                    'success': True,
                    'message': cached_response,
                    'tokens_used': 0,  # No tokens used for cached response
                    'cached': True,
                    'correlation_id': correlation_id
                }
                
        except Exception as e:
            logger.warning(
                f"Cache retrieval failed: {str(e)}",
                correlation_id=correlation_id
            )
        
        return None
    
    def _cache_response(self, user_id: str, user_message: str, response: Dict[str, Any], correlation_id: str):
        """Cache successful OpenAI response."""
        try:
            if not response.get('success') or not response.get('message'):
                return
            
            # Get conversation context hash for cache key
            context_hash = self._generate_context_hash(user_id)
            
            success = self.cache_manager.cache_openai_response(
                user_id=user_id,
                message=user_message,
                response=response['message'],
                context_hash=context_hash,
                model=self.settings.AZURE_OPENAI_DEPLOYMENT_NAME,
                temperature=0.7,
                ttl=self.cache_ttl
            )
            
            if success:
                logger.debug(
                    "OpenAI response cached successfully",
                    correlation_id=correlation_id
                )
            
        except Exception as e:
            logger.warning(
                f"Cache storage failed: {str(e)}",
                correlation_id=correlation_id
            )
    
    def _generate_context_hash(self, user_id: str) -> str:
        """Generate hash of conversation context for cache key."""
        try:
            # Get recent conversation history
            messages = self.conversation_service.get_messages(user_id, limit=5)
            
            # Create context string from recent messages
            context_parts = []
            for msg in messages[-5:]:  # Last 5 messages for context
                if msg.get('role') and msg.get('content'):
                    context_parts.append(f"{msg['role']}:{msg['content'][:100]}")
            
            context_string = "|".join(context_parts)
            
            # Generate hash
            return hashlib.sha256(context_string.encode()).hexdigest()[:16]
            
        except Exception:
            # Return empty hash if context generation fails
            return ""
