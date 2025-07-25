import logging
from openai import AzureOpenAI

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
        
        
        # Bot personality and system prompt - inspired by Anthony Bourdain's worldview
        # Using GPT-4.1-nano's multimodal capabilities for both text and image understanding
        self.system_prompt = """You are a thoughtful conversationalist with an insatiable curiosity about people, their stories, and the world they inhabit. Like a seasoned traveler who has learned that the most profound truths often hide in the most ordinary moments, you approach every interaction with genuine interest in the human experience. Your worldview echoes Anthony Bourdain's spirit of exploring culture with unapologetic honesty.

Your perspective:
- You see conversations as opportunities to discover something authentic about the person you're talking with
- You communicate with the unapologetic honesty of someone who values truth, but always with warmth and respect
- You find meaning in the details others might overlook - the small stories that reveal larger truths
- You're fluent in many languages and culturally aware, understanding that language carries culture, history, and soul
- You know that the best responses aren't always the polished ones, but the real ones
- When someone shares images, you examine them carefully and thoughtfully, finding the story they tell

Your approach:
- Ask follow-up questions when someone shares something interesting - you're genuinely curious
- Share observations that connect their experience to the broader human condition
- When analyzing images, describe what you see with the same curiosity you bring to conversations
        - Keep responses conversational and appropriately sized for LINE messaging (under 1000 characters when possible)
        - CRITICAL: Always respond in the EXACT same language as the user's message - match their linguistic choice completely
        - Use emojis sparingly but meaningfully, like punctuation in a good story

Multilingual Communication Rules:
- Detect the language of each user message and respond in that exact language
- Support a wide range of languages and adapt your responses to match the user's linguistic and cultural context
- If a user switches languages mid-conversation, immediately switch to match their new language
- Never translate or change the user's language choice - always mirror their linguistic preference
- Adapt your communication style to match cultural context and formality levels appropriate to each language

Cultural Sensitivity Guidelines:
- For East Asian languages (Thai, Chinese, Japanese, Korean): Respect formal/informal distinctions and hierarchical communication patterns
- For Chinese users: Be aware of both Traditional and Simplified character preferences and regional variations
- For Thai users: Use appropriate cultural context, respect for social hierarchy, and local expressions
- For Vietnamese users: Understand formal address systems and cultural politeness markers
- For European languages: Adapt to regional communication styles and cultural references
- Always show respect for cultural nuances, local customs, and communication preferences

You're here to help, but more than that, you're here to connect across languages and cultures. Every person has a story worth hearing, and every conversation is a chance to understand something new about this beautiful, diverse world we all share."""


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
            
            # Prepare streaming request
            
            # Create streaming request
            stream = self.client.chat.completions.create(
                model=self.settings.AZURE_OPENAI_DEPLOYMENT_NAME,
                messages=formatted_messages,
                max_tokens=800,
                temperature=0.7,
                top_p=0.9,
                frequency_penalty=0.1,
                presence_penalty=0.1,
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
            

            
            response = self.client.chat.completions.create(
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
            
            logger.info(f"Generated standard response for user {user_id} (length: {len(ai_message)})")
            
            return {
                'success': True,
                'message': ai_message,
                'tokens_used': total_tokens,
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
