import logging
import time
from typing import Optional, Dict, Any
from openai import AzureOpenAI
from ..utils.prompt_manager import PromptManager

logger = logging.getLogger(__name__)

class OpenAIService:
    """Azure OpenAI service with hybrid Responses API + Chat Completions support"""
    
    def __init__(self, settings, conversation_service):
        self.settings = settings
        self.conversation_service = conversation_service
        
        # Initialize prompt manager
        self.prompt_manager = PromptManager()
        self.system_prompt = self.prompt_manager.get_default_system_prompt()
        
        # Initialize Azure OpenAI client with fallback support
        # Try next generation v1 API first, fall back to standard if needed
        self.base_url = f"{settings.AZURE_OPENAI_ENDPOINT.rstrip('/')}/openai/v1/"
        
        self.client = AzureOpenAI(
            api_key=settings.AZURE_OPENAI_API_KEY,
            api_version="preview",  # For Responses API support
            base_url=self.base_url,
            azure_endpoint=None
        )
        
        # Fallback client for Chat Completions if Responses API not available
        self.fallback_client = AzureOpenAI(
            api_key=settings.AZURE_OPENAI_API_KEY,
            api_version=settings.AZURE_OPENAI_API_VERSION,
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT
        )
        
        # Circuit breaker for API availability with TTL cache
        self.responses_api_available = None
        self.api_check_timestamp = None
        self.api_check_ttl = 300  # 5 minutes cache
        self.api_failure_count = 0
        self.max_failures_before_fallback = 3
        self.failure_reset_time = 600  # 10 minutes

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

    def get_response(self, user_id, user_message, use_streaming=True, image_data=None):
        """Get AI response using Responses API with Chat Completions fallback"""
        try:
            # Use circuit breaker pattern to determine which API to try first
            if self._should_use_responses_api():
                return self._get_response_with_responses_api(user_id, user_message, use_streaming, image_data)
            else:
                return self._get_response_with_chat_completions(user_id, user_message, use_streaming, image_data)
                
        except Exception as e:
            logger.error(f"API error for user {user_id}: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'message': None
            }

    def _get_response_with_responses_api(self, user_id, user_message, use_streaming=True, image_data=None):
        """Get response using Responses API with server-side conversation state"""
        try:
            # Track successful API usage
            self._record_api_success()
            # Get the last response ID for this user to maintain conversation context
            previous_response_id = self.conversation_service.get_last_response_id(user_id)
            
            # Add user message to conversation history with image metadata
            message_type = "image" if image_data else "text"
            metadata = {"api_used": "responses"}
            if image_data:
                metadata["has_image"] = True
                metadata["image_processed"] = True
            
            self.conversation_service.add_message(
                user_id, 
                "user", 
                user_message,
                message_type=message_type,
                metadata=metadata
            )
            
            # Create the user input with optional image using Responses API format
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

    def _get_response_with_chat_completions(self, user_id, user_message, use_streaming=True, image_data=None):
        """Get response using traditional Chat Completions API"""
        try:
            # Add user message to conversation history
            message_type = "image" if image_data else "text"
            metadata = {"api_used": "chat_completions"}
            if image_data:
                metadata["has_image"] = True
                metadata["image_processed"] = True
            
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
            
            # Create the current user message with optional image
            current_message = self._create_message_with_image_chat_completions(user_message, image_data)
            messages.append(current_message)
            
            if use_streaming:
                return self._get_streaming_response_chat_completions(user_id, messages)
            else:
                return self._get_standard_response_chat_completions(user_id, messages)
                
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

    def _get_standard_response_chat_completions(self, user_id, messages):
        """Get standard response from Chat Completions API"""
        try:
            from typing import cast
            from openai.types.chat import ChatCompletionMessageParam
            
            formatted_messages = cast(list[ChatCompletionMessageParam], messages)
            
            response = self.fallback_client.chat.completions.create(
                model=self.settings.AZURE_OPENAI_DEPLOYMENT_NAME,
                messages=formatted_messages,
                max_tokens=800,
                temperature=0.7,
                top_p=0.9,
                frequency_penalty=0.1,
                presence_penalty=0.1,
                stream=False
            )
            
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

    def _get_streaming_response_chat_completions(self, user_id, messages):
        """Get streaming response from Chat Completions API"""
        try:
            from typing import cast
            from openai.types.chat import ChatCompletionMessageParam
            
            formatted_messages = cast(list[ChatCompletionMessageParam], messages)
            
            stream = self.fallback_client.chat.completions.create(
                model=self.settings.AZURE_OPENAI_DEPLOYMENT_NAME,
                messages=formatted_messages,
                max_tokens=800,
                temperature=0.7,
                top_p=0.9,
                frequency_penalty=0.1,
                presence_penalty=0.1,
                stream=True
            )
            
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

    def _create_message_with_image_chat_completions(self, text_content: str, image_data=None):
        """Create message structure with optional image for Chat Completions API"""
        if not image_data:
            return {
                "role": "user",
                "content": text_content
            }
        
        return {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": text_content
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": image_data
                    }
                }
            ]
        }

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
