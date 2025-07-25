import json
import hashlib
import hmac
import base64
import logging
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError, LineBotApiError
from linebot.models import MessageEvent, TextMessage, ImageMessage, TextSendMessage

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
        
        # Register message handlers
        @self.handler.add(MessageEvent, message=TextMessage)
        def handle_text_message(event):
            self._handle_text_message(event)

        @self.handler.add(MessageEvent, message=ImageMessage)
        def handle_image_message(event):
            self._handle_image_message(event)
    
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
        """Handle incoming text message from LINE user - single complete response"""
        try:
            user_id = event.source.user_id
            user_message = event.message.text
            
            logger.info(f"Received message from user {user_id}: {user_message}")
            
            # Get AI response (single complete message, no streaming)
            ai_response = self.openai_service.get_response(user_id, user_message, use_streaming=False)
            
            if ai_response['success']:
                # Send single complete response
                self._send_message(event.reply_token, ai_response['message'])
                
                # Log response details
                tokens_used = ai_response.get('tokens_used', 0)
                logger.info(f"Sent complete response to user {user_id}: {len(ai_response['message'])} chars [{tokens_used} tokens]")
                
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

    def _handle_image_message(self, event):
        """Handle incoming image message from LINE user"""
        try:
            user_id = event.source.user_id
            message_id = event.message.id
            
            logger.info(f"Received image message from user {user_id[:8]}... (message_id: {message_id})")
            
            # Send processing status message (using push since we'll need reply token later)
            processing_msg = "กำลังประมวลผลรูปภาพของคุณ กรุณารอสักครู่... 🖼️\nProcessing your image, please wait... 🖼️"
            push_result = self.send_push_message(user_id, processing_msg)
            if not push_result['success']:
                logger.warning(f"Failed to send processing status to user {user_id[:8]}...")
            
            # Import image utilities
            from src.utils.image_utils import ImageProcessor
            
            # Initialize image processor
            image_processor = ImageProcessor()
            
            try:
                # Download and process the image
                download_result = image_processor.download_image_from_line(self.line_bot_api, message_id)
                
                if not download_result or not download_result.get('success', False):
                    # Handle download/validation errors
                    error_code = download_result.get('error_code', 'UNKNOWN') if download_result else 'DOWNLOAD_FAILED'
                    error_details = download_result.get('error', 'Unknown error') if download_result else 'Failed to download image'
                    
                    logger.error(f"Image download failed for user {user_id[:8]}...: {error_code} - {error_details}")
                    
                    if error_code == 'FILE_TOO_LARGE':
                        error_msg = "ไฟล์รูปภาพใหญ่เกินไป (สูงสุด 10MB)\nImage file too large (max 10MB)"
                    elif error_code == 'UNSUPPORTED_FORMAT':
                        error_msg = "รูปแบบไฟล์ไม่รองรับ กรุณาส่งรูป JPG, PNG หรือ GIF\nUnsupported format. Please send JPG, PNG or GIF"
                    elif error_code == 'DOWNLOAD_TIMEOUT':
                        error_msg = "ดาวน์โหลดรูปภาพใช้เวลานานเกินไป กรุณาลองใหม่\nImage download timed out. Please try again"
                    else:
                        error_msg = f"ประมวลผลรูปภาพไม่สำเร็จ\nImage processing failed"
                    
                    self._send_message(event.reply_token, error_msg)
                    return
                
                # Preprocess image if needed
                image_data = download_result.get('image_data', b'')
                image_format = download_result.get('format', 'JPEG')
                logger.info(f"Processing {image_format} image ({len(image_data)} bytes) for user {user_id[:8]}...")
                
                processed_image_data = image_processor.preprocess_image_if_needed(image_data)
                
                # Convert to base64 for OpenAI API
                base64_image = image_processor.image_to_base64(processed_image_data, image_format)
                logger.debug(f"Converted image to base64 format for OpenAI API")
                
                # Get accompanying text or default prompt
                user_text = "What can you tell me about this image?"
                if hasattr(event.message, 'text') and event.message.text:
                    user_text = event.message.text
                    logger.info(f"Image from user {user_id[:8]}... has accompanying text")
                
                # Get AI response with image
                ai_response = self.openai_service.get_response(
                    user_id, 
                    user_text, 
                    use_streaming=False,
                    image_data=base64_image
                )
                
                if ai_response['success']:
                    # Send AI response
                    self._send_message(event.reply_token, ai_response['message'])
                    
                    # Log success
                    tokens_used = ai_response.get('tokens_used', 0)
                    logger.info(f"Sent image analysis response to user {user_id[:8]}... "
                               f"[{tokens_used} tokens, {download_result.get('size', 0)} bytes, "
                               f"{download_result.get('dimensions', (0, 0))[0]}x{download_result.get('dimensions', (0, 0))[1]}]")
                else:
                    # AI processing failed, send error
                    error_msg = "圖像分析失敗，請稍後再試。\nImage analysis failed, please try again later."
                    self._send_message(event.reply_token, error_msg)
                    logger.error(f"AI image analysis failed: {ai_response['error']}")
                
            finally:
                # Always cleanup temporary files
                image_processor.cleanup_temp_files()
                
        except Exception as e:
            logger.error(f"Error handling image message: {str(e)}")
            try:
                error_msg = "圖像處理時發生錯誤，請稍後再試。\nError processing image, please try again later."
                self._send_message(event.reply_token, error_msg)
            except:
                pass



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
