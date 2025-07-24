import json
import hashlib
import hmac
import base64
import logging
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError, LineBotApiError
from linebot.models import MessageEvent, TextMessage, TextSendMessage

logger = logging.getLogger(__name__)

class LineService:
    """LINE Bot service for handling messages and webhook verification"""
    
    def __init__(self, settings, openai_service, conversation_service):
        self.settings = settings
        self.openai_service = openai_service
        self.conversation_service = conversation_service
        
        # Initialize LINE Bot API
        self.line_bot_api = LineBotApi(settings.LINE_CHANNEL_ACCESS_TOKEN)
        self.handler = WebhookHandler(settings.LINE_CHANNEL_SECRET)
        
        # Register message handler
        @self.handler.add(MessageEvent, message=TextMessage)
        def handle_text_message(event):
            self._handle_text_message(event)
    
    def handle_webhook(self, signature, body):
        """Handle incoming webhook from LINE"""
        try:
            # Verify webhook signature
            if not self._verify_signature(signature, body):
                logger.error("Invalid webhook signature")
                return {'success': False, 'error': 'Invalid signature'}
            
            # Handle the webhook event
            self.handler.handle(body, signature)
            
            return {'success': True}
            
        except InvalidSignatureError:
            logger.error("Invalid signature error")
            return {'success': False, 'error': 'Invalid signature'}
        except Exception as e:
            logger.error(f"Error handling webhook: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _verify_signature(self, signature, body):
        """Verify LINE webhook signature"""
        if not signature:
            return False
        
        try:
            # Create signature hash
            hash_digest = hmac.new(
                self.settings.LINE_CHANNEL_SECRET.encode('utf-8'),
                body.encode('utf-8'),
                hashlib.sha256
            ).digest()
            
            # Encode to base64
            expected_signature = base64.b64encode(hash_digest).decode('utf-8')
            
            # Compare signatures
            return hmac.compare_digest(signature, expected_signature)
            
        except Exception as e:
            logger.error(f"Signature verification error: {str(e)}")
            return False
    
    def _handle_text_message(self, event):
        """Handle incoming text message from LINE user with streaming support"""
        try:
            user_id = event.source.user_id
            user_message = event.message.text
            
            logger.info(f"Received message from user {user_id}: {user_message}")
            
            # Show typing indicator while processing (optional)
            try:
                self._show_typing_indicator(user_id)
            except Exception as e:
                logger.debug(f"Could not show typing indicator: {e}")
            
            # Get AI response with streaming
            ai_response = self.openai_service.get_response(user_id, user_message, use_streaming=True)
            
            if ai_response['success']:
                # Handle response (potentially break into chunks for long responses)
                response_message = ai_response['message']
                
                # Check if response is too long and should be chunked
                if len(response_message) > 1000:  # 1000 chars threshold
                    self._send_chunked_response(event.reply_token, response_message)
                else:
                    self._send_message(event.reply_token, response_message)
                
                # Log response details
                streaming_info = " (streamed)" if ai_response.get('streaming') else ""
                tokens_used = ai_response.get('tokens_used', 0)
                logger.info(f"Sent response to user {user_id}: {response_message[:100]}...{streaming_info} [{tokens_used} tokens]")
                
            else:
                # Send error message
                error_msg = "抱歉，我現在無法回應您的訊息。請稍後再試。\nSorry, I'm unable to respond to your message right now. Please try again later."
                self._send_message(event.reply_token, error_msg)
                logger.error(f"Failed to get AI response: {ai_response['error']}")
                
        except Exception as e:
            logger.error(f"Error handling text message: {str(e)}")
            # Send generic error message
            try:
                error_msg = "系統發生錯誤，請稍後再試。\nSystem error occurred, please try again later."
                self._send_message(event.reply_token, error_msg)
            except:
                pass  # If we can't even send error message, just log and continue

    def _show_typing_indicator(self, user_id):
        """Show typing indicator (LINE doesn't have native typing indicators, but we can simulate)"""
        # Note: LINE doesn't have typing indicators like other platforms
        # This is a placeholder for future enhancement or push messages
        pass

    def _send_chunked_response(self, reply_token, message_text):
        """Send long responses in chunks for better readability"""
        try:
            # Split message into chunks at sentence boundaries
            chunks = self._split_message_intelligently(message_text)
            
            if len(chunks) <= 1:
                # If only one chunk, send normally
                self._send_message(reply_token, message_text)
                return
            
            # Send first chunk as reply, others as push messages would require user_id
            # For now, send as single message with better formatting
            formatted_message = self._format_long_message(message_text)
            self._send_message(reply_token, formatted_message)
            
        except Exception as e:
            logger.error(f"Error sending chunked response: {e}")
            # Fallback to regular message
            self._send_message(reply_token, message_text)

    def _split_message_intelligently(self, text, max_chunk_size=800):
        """Split message at sentence boundaries for better readability"""
        if len(text) <= max_chunk_size:
            return [text]
        
        chunks = []
        current_chunk = ""
        
        # Split by sentences (look for . ! ? followed by space or end)
        import re
        sentences = re.split(r'([.!?]\s+)', text)
        
        for i in range(0, len(sentences), 2):
            sentence = sentences[i]
            if i + 1 < len(sentences):
                sentence += sentences[i + 1]  # Add the punctuation back
            
            if len(current_chunk + sentence) <= max_chunk_size:
                current_chunk += sentence
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks

    def _format_long_message(self, text):
        """Format long messages for better readability"""
        # Add line breaks for better readability
        formatted = text.replace('. ', '.\n\n')
        formatted = formatted.replace('? ', '?\n\n')
        formatted = formatted.replace('! ', '!\n\n')
        
        # Remove excessive line breaks
        import re
        formatted = re.sub(r'\n{3,}', '\n\n', formatted)
        
        return formatted.strip()
    
    def _send_message(self, reply_token, message_text):
        """Send message back to LINE user"""
        try:
            # LINE message limit is 5000 characters
            if len(message_text) > 5000:
                message_text = message_text[:4900] + "\n\n[訊息過長已截斷 / Message truncated]"
            
            message = TextSendMessage(text=message_text)
            self.line_bot_api.reply_message(reply_token, message)
            
        except LineBotApiError as e:
            error_msg = getattr(e.error, 'message', str(e)) if hasattr(e, 'error') and e.error else str(e)
            logger.error(f"LINE Bot API error: {e.status_code} - {error_msg}")
            raise
        except Exception as e:
            logger.error(f"Error sending message: {str(e)}")
            raise
    
    def send_push_message(self, user_id, message_text):
        """Send push message to specific user (for testing)"""
        try:
            if len(message_text) > 5000:
                message_text = message_text[:4900] + "\n\n[訊息過長已截斷 / Message truncated]"
            
            message = TextSendMessage(text=message_text)
            self.line_bot_api.push_message(user_id, message)
            
            return {'success': True}
            
        except LineBotApiError as e:
            error_msg = getattr(e.error, 'message', str(e)) if hasattr(e, 'error') and e.error else str(e)
            logger.error(f"LINE Bot API error: {e.status_code} - {error_msg}")
            return {'success': False, 'error': f"LINE API error: {error_msg}"}
        except Exception as e:
            logger.error(f"Error sending push message: {str(e)}")
            return {'success': False, 'error': str(e)}
