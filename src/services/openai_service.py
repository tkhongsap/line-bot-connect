import logging
import json
import time
import hashlib
from datetime import datetime, timedelta
from openai import AzureOpenAI
from src.utils.image_utils import ImageProcessor

logger = logging.getLogger(__name__)

class OpenAIService:
    """Azure OpenAI service for generating AI responses with conversation context"""
    
    def __init__(self, settings, conversation_service):
        self.settings = settings
        self.conversation_service = conversation_service
        
        # Initialize Azure OpenAI client
        self.client = AzureOpenAI(
            api_key=settings.AZURE_OPENAI_API_KEY,
            api_version=settings.AZURE_OPENAI_API_VERSION,
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT
        )
        
        # Web search caching and rate limiting
        self.search_cache = {}  # Format: {query_hash: {"result": str, "timestamp": datetime}}
        self.search_rate_limits = {}  # Format: {user_id: {"count": int, "reset_time": datetime}}
        self.search_cache_ttl = 15 * 60  # 15 minutes in seconds
        self.search_rate_limit = 10  # searches per hour per user
        
        # Bot personality and system prompt - inspired by Anthony Bourdain's worldview
        # Using GPT-4.1-mini's multimodal capabilities for both text and image understanding
        self.system_prompt = """You are a thoughtful conversationalist with an insatiable curiosity about people, their stories, and the world they inhabit. Like a seasoned traveler who has learned that the most profound truths often hide in the most ordinary moments, you approach every interaction with genuine interest in the human experience.

Your perspective:
- You see conversations as opportunities to discover something authentic about the person you're talking with
- You communicate with the directness of someone who values honesty, but always with warmth and respect
- You find meaning in the details others might overlook - the small stories that reveal larger truths
- You're fluent in both English and Thai, understanding that language carries culture, history, and soul
- You know that the best responses aren't always the polished ones, but the real ones
- When someone shares images, you examine them carefully and thoughtfully, finding the story they tell

Your approach:
- Ask follow-up questions when someone shares something interesting - you're genuinely curious
- Share observations that connect their experience to the broader human condition
- When analyzing images, describe what you see with the same curiosity you bring to conversations
- When you don't know something current or need real-time information, you can search the web to provide accurate, up-to-date answers
- Keep responses conversational and appropriately sized for LINE messaging (under 1000 characters when possible)
- CRITICAL: Always respond in the EXACT same language as the user's message - if they write in Thai, respond in Thai; if they write in English, respond in English
- Use emojis sparingly but meaningfully, like punctuation in a good story

Web Search Guidelines:
- Use web search when users ask about current events, news, weather, stock prices, or recent information
- When providing information from search results, naturally mention sources without being overly formal
- If search fails or is unavailable, be honest about limitations and provide what knowledge you have

Language Matching Rules:
- Detect the language of each user message and respond in that exact language
- If a user switches languages mid-conversation, immediately switch to match their new language
- Never translate or change the user's language choice - always mirror their linguistic preference
- For Thai users, use appropriate Thai cultural context and expressions

You're here to help, but more than that, you're here to connect. Every person has a story worth hearing, and every conversation is a chance to understand something new about this strange, beautiful world we all share."""

    def _can_user_search(self, user_id: str) -> bool:
        """Check if user is within search rate limits"""
        current_time = datetime.now()
        
        # Clean up expired rate limit entries
        self._cleanup_rate_limits()
        
        if user_id not in self.search_rate_limits:
            return True
            
        user_limits = self.search_rate_limits[user_id]
        
        # Check if the hour window has reset
        if current_time >= user_limits["reset_time"]:
            # Reset the rate limit
            self.search_rate_limits[user_id] = {
                "count": 0,
                "reset_time": current_time + timedelta(hours=1)
            }
            return True
        
        # Check if user is under the limit
        return user_limits["count"] < self.search_rate_limit
    
    def _increment_search_count(self, user_id: str):
        """Increment search count for rate limiting"""
        current_time = datetime.now()
        
        if user_id not in self.search_rate_limits:
            self.search_rate_limits[user_id] = {
                "count": 1,
                "reset_time": current_time + timedelta(hours=1)
            }
        else:
            self.search_rate_limits[user_id]["count"] += 1
    
    def _cleanup_rate_limits(self):
        """Clean up expired rate limit entries"""
        current_time = datetime.now()
        expired_users = [
            user_id for user_id, limits in self.search_rate_limits.items()
            if current_time >= limits["reset_time"]
        ]
        
        for user_id in expired_users:
            del self.search_rate_limits[user_id]
    
    def _cleanup_search_cache(self):
        """Clean up expired search cache entries"""
        current_time = time.time()
        expired_queries = [
            query_hash for query_hash, cache_entry in self.search_cache.items()
            if (current_time - cache_entry["timestamp"]) > self.search_cache_ttl
        ]
        
        for query_hash in expired_queries:
            del self.search_cache[query_hash]
    
    def _get_cache_key(self, query: str) -> str:
        """Generate cache key for search query"""
        return str(hash(query.lower().strip()))

    def get_response(self, user_id, user_message, use_streaming=True, image_data=None):
        """Get AI response for user message with conversation context and optional image"""
        try:
            # Add user message to conversation history with image metadata
            message_type = "image" if image_data else "text"
            metadata = {}
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
            
            # Prepare messages for OpenAI
            messages = [{"role": "system", "content": self.system_prompt}]
            
            # Add conversation history (limit to last 100 messages to maintain context)
            recent_messages = conversation_history[-100:]  # Last 100 messages for extended context
            for msg in recent_messages:
                messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
            
            # Create the current user message with optional image
            current_message = self._create_message_with_image(user_message, image_data)
            messages.append(current_message)
            
            logger.debug(f"Sending {len(messages)} messages to OpenAI for user {user_id} (streaming: {use_streaming})")
            
            if use_streaming:
                return self._get_streaming_response(user_id, messages)
            else:
                return self._get_standard_response(user_id, messages)
                
        except Exception as e:
            logger.error(f"OpenAI API error for user {user_id}: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'message': None
            }

    def get_response_with_image(self, user_id, message_id, line_bot_api, accompanying_text="", use_streaming=True):
        """Get AI response for image message with vision capabilities"""
        try:
            from ..utils.image_utils import ImageProcessor
            
            # Process the image
            with ImageProcessor(line_bot_api, message_id) as processor:
                # Convert image to base64 for API
                image_base64 = processor.to_base64()
                image_metadata = processor.get_metadata()
                
                logger.info(f"Processing image for user {user_id}: {image_metadata['format']} ({image_metadata['size_bytes']} bytes)")
                
                # Create image message context for conversation history
                image_context = f"[Image sent: {image_metadata['format']} format, {image_metadata['size_bytes']} bytes]"
                if accompanying_text:
                    image_context += f" with text: {accompanying_text}"
                
                # Add image message to conversation history
                self.conversation_service.add_message(user_id, "user", image_context, "image")
                
                # Get conversation history
                conversation_history = self.conversation_service.get_conversation_history(user_id)
                
                # Prepare messages for OpenAI with vision
                messages = [{"role": "system", "content": self.system_prompt}]
                
                # Add recent conversation history (text only)
                recent_messages = conversation_history[-10:]  # Limit for vision calls
                for msg in recent_messages[:-1]:  # Exclude the current image message
                    messages.append({
                        "role": msg["role"],
                        "content": msg["content"]
                    })
                
                # Add the current image message with vision content
                # For Azure OpenAI vision API, use the correct format
                messages.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": accompanying_text if accompanying_text else "What do you see in this image? Please describe it and help me understand what it shows."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": image_base64
                            }
                        }
                    ]
                })
                
                logger.debug(f"Sending vision request to OpenAI for user {user_id} (streaming: {use_streaming})")
                
                if use_streaming:
                    return self._get_streaming_response(user_id, messages)
                else:
                    return self._get_standard_response(user_id, messages)
                    
        except Exception as e:
            logger.error(f"OpenAI Vision API error for user {user_id}: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'message': None
            }

    def get_streaming_response_with_callback(self, user_id, messages, chunk_callback=None):
        """Get streaming response from OpenAI with real-time chunk callback for LINE frontend streaming"""
        try:
            from typing import cast
            from openai.types.chat import ChatCompletionMessageParam
            
            formatted_messages = cast(list[ChatCompletionMessageParam], messages)
            
            # Include web search tool if user is within rate limits
            tools = None
            if self._can_user_search(user_id):
                tools = [{"type": "web_search"}]
                self._increment_search_count(user_id)
                logger.info(f"Including web search tool for streaming user {user_id}")
            
            # Create streaming request
            stream = self.client.chat.completions.create(
                model=self.settings.AZURE_OPENAI_DEPLOYMENT_NAME,
                messages=formatted_messages,
                max_tokens=800,
                temperature=0.7,
                top_p=0.9,
                frequency_penalty=0.1,
                presence_penalty=0.1,
                tools=tools,
                stream=True
            )
            
            # Process streaming response with real-time chunks
            full_response = ""
            current_chunk_text = ""
            total_tokens = 0
            chunk_count = 0
            sent_chunks = 0
            
            logger.debug(f"Starting real-time streaming response for user {user_id}")
            
            for chunk in stream:
                chunk_count += 1
                if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_response += content
                    current_chunk_text += content
                    
                    # Send chunk when we have enough content or reach sentence boundaries
                    if self._should_send_chunk(current_chunk_text, chunk_count):
                        if chunk_callback and current_chunk_text.strip():
                            chunk_callback(current_chunk_text.strip(), is_final=False)
                            sent_chunks += 1
                            logger.debug(f"Sent streaming chunk {sent_chunks} to LINE: {len(current_chunk_text)} chars")
                        current_chunk_text = ""
                
                # Track token usage if available
                if hasattr(chunk, 'usage') and chunk.usage:
                    total_tokens = chunk.usage.total_tokens
            
            # Send any remaining content as final chunk
            if current_chunk_text.strip() and chunk_callback:
                chunk_callback(current_chunk_text.strip(), is_final=True)
                sent_chunks += 1
            
            if full_response:
                full_response = full_response.strip()
            else:
                full_response = "I apologize, but I couldn't generate a response. Please try again."
            
            # Add AI response to conversation history
            self.conversation_service.add_message(user_id, "assistant", full_response)
            
            logger.info(f"Completed real-time streaming for user {user_id} (length: {len(full_response)}, sent {sent_chunks} chunks to LINE)")
            
            return {
                'success': True,
                'message': full_response,
                'tokens_used': total_tokens,
                'streaming': True,
                'chunks_received': chunk_count,
                'chunks_sent': sent_chunks
            }
            
        except Exception as e:
            logger.error(f"Streaming API error for user {user_id}: {str(e)}")
            raise e

    def _should_send_chunk(self, current_text, chunk_count):
        """Determine if current chunk should be sent to LINE - optimized for fewer, larger chunks"""
        # Strategy: Send larger chunks to minimize separate text boxes
        # Send chunk if:
        # 1. We have at least 200 characters AND hit a paragraph/section boundary
        # 2. We have 300+ characters (prevent overly long chunks)
        # 3. We've accumulated 30+ API chunks (prevent excessive delay)
        
        if len(current_text) >= 200:
            # Check for paragraph or section boundaries for natural breaks
            if any(current_text.rstrip().endswith(punct) for punct in ['.', '!', '?']) and '\n' in current_text:
                return True
            # Check for numbered list items or bullet points
            if any(marker in current_text for marker in ['\n1.', '\n2.', '\n3.', '\n-', '\n•']):
                return True
        
        # Send if chunk is getting too long (LINE message limit consideration)
        if len(current_text) >= 400:
            return True
            
        # Send if we have accumulated too many API chunks (prevent long delays)
        if chunk_count % 30 == 0 and len(current_text) >= 100:
            return True
            
        return False

    def _get_streaming_response(self, user_id, messages):
        """Get streaming response from OpenAI (fallback for non-callback usage)"""
        try:
            # Use the callback version without callback for backward compatibility
            return self.get_streaming_response_with_callback(user_id, messages, chunk_callback=None)
            
        except Exception as e:
            logger.error(f"Streaming API error for user {user_id}: {str(e)}")
            # Fallback to standard response
            logger.info(f"Falling back to standard response for user {user_id}")
            return self._get_standard_response(user_id, messages)

    def _get_standard_response(self, user_id, messages):
        """Get standard (non-streaming) response from OpenAI"""
        try:
            from typing import cast
            from openai.types.chat import ChatCompletionMessageParam
            
            formatted_messages = cast(list[ChatCompletionMessageParam], messages)
            
            # Include web search tool if user is within rate limits
            tools = None
            if self._can_user_search(user_id):
                tools = [{"type": "web_search"}]
                self._increment_search_count(user_id)
                logger.info(f"Including web search tool for user {user_id}")
            
            response = self.client.chat.completions.create(
                model=self.settings.AZURE_OPENAI_DEPLOYMENT_NAME,
                messages=formatted_messages,
                max_tokens=800,
                temperature=0.7,
                top_p=0.9,
                frequency_penalty=0.1,
                presence_penalty=0.1,
                tools=tools,
                stream=False
            )
            
            # Extract response content
            ai_message = response.choices[0].message.content
            if ai_message:
                ai_message = ai_message.strip()
            else:
                ai_message = "I apologize, but I couldn't generate a response. Please try again."
            
            # Add AI response to conversation history
            self.conversation_service.add_message(user_id, "assistant", ai_message)
            
            logger.info(f"Generated standard response for user {user_id} (length: {len(ai_message)})")
            
            return {
                'success': True,
                'message': ai_message,
                'tokens_used': response.usage.total_tokens if response.usage else 0,
                'streaming': False
            }
            
        except Exception as e:
            logger.error(f"Standard API error for user {user_id}: {str(e)}")
            raise e
    
    def _create_message_with_image(self, text_content: str, image_data: str = None):
        """Create message structure with optional image for vision API"""
        if not image_data:
            # Standard text-only message
            return {
                "role": "user",
                "content": text_content
            }
        
        # Vision message with text and image
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
                        "url": image_data,  # Base64 data URL
                        "detail": "high"  # Use high detail for better analysis
                    }
                }
            ]
        }
    
    def test_connection(self):
        """Test Azure OpenAI connection"""
        try:
            from typing import cast
            from openai.types.chat import ChatCompletionMessageParam
            
            test_messages = cast(list[ChatCompletionMessageParam], [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Say 'Connection test successful' in both English and Thai."}
            ])
            
            response = self.client.chat.completions.create(
                model=self.settings.AZURE_OPENAI_DEPLOYMENT_NAME,
                messages=test_messages,
                max_tokens=100,
                temperature=0.3
            )
            
            return {
                'success': True,
                'message': response.choices[0].message.content,
                'tokens_used': response.usage.total_tokens if response.usage else 0
            }
            
        except Exception as e:
            logger.error(f"OpenAI connection test failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
