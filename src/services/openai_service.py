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

    def get_response(self, user_id, user_message):
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
            
            logger.debug(f"Sending {len(messages)} messages to OpenAI for user {user_id}")
            
            # Call Azure OpenAI
            from typing import cast
            from openai.types.chat import ChatCompletionMessageParam
            
            formatted_messages = cast(list[ChatCompletionMessageParam], messages)
            response = self.client.chat.completions.create(
                model=self.settings.AZURE_OPENAI_DEPLOYMENT_NAME,
                messages=formatted_messages,
                max_tokens=800,  # Reasonable limit for LINE responses
                temperature=0.7,
                top_p=0.9,
                frequency_penalty=0.1,
                presence_penalty=0.1
            )
            
            # Extract response content
            ai_message = response.choices[0].message.content
            if ai_message:
                ai_message = ai_message.strip()
            else:
                ai_message = "I apologize, but I couldn't generate a response. Please try again."
            
            # Add AI response to conversation history
            self.conversation_service.add_message(user_id, "assistant", ai_message)
            
            logger.info(f"Generated response for user {user_id} (length: {len(ai_message)})")
            
            return {
                'success': True,
                'message': ai_message,
                'tokens_used': response.usage.total_tokens if response.usage else 0
            }
            
        except Exception as e:
            logger.error(f"OpenAI API error for user {user_id}: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'message': None
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
