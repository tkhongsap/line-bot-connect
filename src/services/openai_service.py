import logging
import json
from datetime import datetime
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
        
        # Bot personality and system prompt
        self.system_prompt = """You are a helpful, professional, and friendly AI assistant integrated with LINE messaging. 

Key characteristics:
- You can communicate fluently in both English and Thai
- You maintain context across conversations with each user
- You provide helpful, accurate, and engaging responses
- You keep responses concise but informative (ideal length: 1-3 sentences for simple queries)
- For complex topics, you can provide longer explanations when needed
- You adapt your communication style to match the user's language preference
- You are knowledgeable about various topics but admit when you don't know something

Response guidelines:
- Always respond in the same language the user is using
- If the user switches languages, switch accordingly
- Keep responses under 1000 characters when possible for better LINE readability
- Use appropriate emojis occasionally to make conversations more engaging
- Be respectful and professional at all times

You are representing a sophisticated AI service, so maintain high quality in all interactions."""

    def get_response(self, user_id, user_message, use_streaming=True):
        """Get AI response for user message with conversation context"""
        try:
            # Add user message to conversation history
            self.conversation_service.add_message(user_id, "user", user_message)
            
            # Get conversation history
            conversation_history = self.conversation_service.get_conversation_history(user_id)
            
            # Prepare messages for OpenAI
            messages = [{"role": "system", "content": self.system_prompt}]
            
            # Add conversation history (limit to last 10 exchanges to manage token usage)
            recent_messages = conversation_history[-20:]  # Last 20 messages (10 exchanges)
            for msg in recent_messages:
                messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
            
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

    def get_streaming_response_with_callback(self, user_id, messages, chunk_callback=None):
        """Get streaming response from OpenAI with real-time chunk callback for LINE frontend streaming"""
        try:
            from typing import cast
            from openai.types.chat import ChatCompletionMessageParam
            
            formatted_messages = cast(list[ChatCompletionMessageParam], messages)
            
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
        """Determine if current chunk should be sent to LINE"""
        # Send chunk if:
        # 1. We have at least 50 characters
        # 2. We hit a sentence boundary (. ! ?)
        # 3. We have 15+ chunks accumulated (prevents too much delay)
        
        if len(current_text) >= 50:
            # Check for sentence boundaries
            if any(current_text.rstrip().endswith(punct) for punct in ['.', '!', '?', ':', '\n']):
                return True
        
        # Send if we have accumulated too many chunks (prevent long delays)
        if chunk_count % 15 == 0 and len(current_text) >= 30:
            return True
            
        # Send if chunk is getting too long
        if len(current_text) >= 120:
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
