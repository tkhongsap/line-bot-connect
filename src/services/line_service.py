import json
import hashlib
import hmac
import base64
import logging
import time
import requests.adapters
from urllib3.util.retry import Retry
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError, LineBotApiError
from linebot.models import (
    MessageEvent, TextMessage, ImageMessage, FileMessage, TextSendMessage,
    PostbackEvent, FlexSendMessage
)
from src.utils.connection_pool import OptimizedLineBotApi, connection_pool_manager
from src.exceptions import (
    LineAPIException, ValidationException, AuthenticationException,
    NetworkException, TimeoutException, DataProcessingException,
    BaseBotException, create_correlation_id, wrap_api_exception,
    log_exception
)
from src.utils.error_handler import StructuredLogger, error_handler, retry_with_backoff

logger = StructuredLogger(__name__)

class LineService:
    """LINE Bot service for handling messages and webhook verification"""
    
    def __init__(self, settings, openai_service, conversation_service, rich_message_service=None):
        self.settings = settings
        self.openai_service = openai_service
        self.conversation_service = conversation_service
        self.rich_message_service = rich_message_service
        
        # Initialize connection pools for LINE API
        self._setup_line_connection_pools()
        
        # Initialize LINE Bot API with enhanced connection pooling
        self.line_bot_api = self._create_optimized_line_bot_api(settings.LINE_CHANNEL_ACCESS_TOKEN)
        self.handler = WebhookHandler(settings.LINE_CHANNEL_SECRET)
        
        # Initialize connection metrics
        self.connection_metrics = {
            'webhook_requests': 0,
            'api_calls': 0,
            'successful_calls': 0,
            'failed_calls': 0,
            'avg_response_time': 0.0
        }
        
        # Register message handlers
        @self.handler.add(MessageEvent, message=TextMessage)
        def handle_text_message(event):
            self._handle_text_message(event)

        @self.handler.add(MessageEvent, message=ImageMessage)
        def handle_image_message(event):
            self._handle_image_message(event)

        @self.handler.add(MessageEvent, message=FileMessage)
        def handle_file_message(event):
            self._handle_file_message(event)
            
        # Register postback handler for Rich Message interactions
        @self.handler.add(PostbackEvent)
        def handle_postback(event):
            self._handle_postback_event(event)
    
    def _setup_line_connection_pools(self):
        """Set up connection pools for LINE API operations."""
        # Create dedicated session for LINE Bot API
        self.line_api_session = connection_pool_manager.create_session_with_pooling(
            name="line_bot_api",
            base_url="https://api.line.me",
            pool_maxsize=15,  # Medium pool size for LINE API
            max_retries=3,
            enable_keep_alive=True
        )
        
        # Create session for LINE content API (image downloads)
        self.line_content_session = connection_pool_manager.create_session_with_pooling(
            name="line_content_api",
            base_url="https://api-data.line.me",
            pool_maxsize=10,  # Smaller pool for content downloads
            max_retries=2,
            enable_keep_alive=True
        )
        
        logger.info("Set up connection pools for LINE API service")
    
    def _create_optimized_line_bot_api(self, channel_access_token: str) -> OptimizedLineBotApi:
        """Create optimized LINE Bot API client with enhanced connection pooling."""
        # Use connection pool manager to create LINE Bot API
        line_bot_api = connection_pool_manager.create_line_bot_api(
            channel_access_token=channel_access_token,
            timeout=10,
            pool_maxsize=15,
            max_retries=3
        )
        
        logger.info("Created optimized LINE Bot API client with connection pooling")
        return line_bot_api
    
    def get_connection_metrics(self) -> dict:
        """Get LINE service connection metrics."""
        pool_metrics = connection_pool_manager.get_metrics()
        
        # Filter for LINE-related pools
        line_pools = {k: v for k, v in pool_metrics.get('pools', {}).items() if 'line' in k}
        
        return {
            'service_metrics': self.connection_metrics,
            'line_connection_pools': line_pools,
            'total_line_pools': len(line_pools),
            'pool_health': {k: v for k, v in pool_metrics.get('health', {}).items() if 'line' in k}
        }
    
    @error_handler(reraise=False, default_return={'success': False, 'error': 'Webhook processing failed'})
    def handle_webhook(self, signature, body):
        """Handle incoming webhook from LINE with comprehensive error handling and connection pooling."""
        correlation_id = create_correlation_id()
        start_time = time.time()
        
        with logger.context(correlation_id=correlation_id, operation='webhook_processing'):
            logger.info("Processing LINE webhook request with connection pooling")
            
            try:
                # Track webhook request
                self.connection_metrics['webhook_requests'] += 1
                # Validate input parameters
                if not signature:
                    raise ValidationException(
                        message="Missing webhook signature",
                        field="signature",
                        correlation_id=correlation_id,
                        user_message="Invalid request signature"
                    )
                
                if not body:
                    raise ValidationException(
                        message="Missing webhook body",
                        field="body", 
                        correlation_id=correlation_id,
                        user_message="Invalid request body"
                    )
                
                # Verify webhook signature
                if not self._verify_signature(signature, body):
                    raise AuthenticationException(
                        message="Webhook signature verification failed",
                        service="LINE_WEBHOOK",
                        correlation_id=correlation_id,
                        context={'signature_provided': bool(signature)}
                    )
                
                # Handle the webhook event with timeout protection and connection pooling
                try:
                    # Use connection pool manager for webhook handling
                    def process_webhook():
                        self.handler.handle(body, signature)
                        return {'success': True, 'correlation_id': correlation_id}
                    
                    result = connection_pool_manager.execute_with_retry(
                        "line_bot_api",
                        process_webhook,
                        max_attempts=2
                    )
                    
                    # Update success metrics
                    response_time = time.time() - start_time
                    self.connection_metrics['successful_calls'] += 1
                    self.connection_metrics['avg_response_time'] = (
                        (self.connection_metrics['avg_response_time'] * (self.connection_metrics['successful_calls'] - 1) + response_time) /
                        self.connection_metrics['successful_calls']
                    )
                    
                    logger.info(
                        "Webhook processed successfully with connection pooling", 
                        correlation_id=correlation_id,
                        extra_context={'response_time': response_time}
                    )
                    return result
                    
                except Exception as handler_error:
                    # Update failure metrics
                    self.connection_metrics['failed_calls'] += 1
                    
                    # Wrap handler errors as processing exceptions
                    raise DataProcessingException(
                        message=f"Webhook event processing failed: {str(handler_error)}",
                        operation="event_handling",
                        data_type="webhook_event",
                        correlation_id=correlation_id,
                        original_exception=handler_error
                    )
            
            except InvalidSignatureError as e:
                # Update failure metrics
                self.connection_metrics['failed_calls'] += 1
                
                raise AuthenticationException(
                    message="LINE Bot SDK signature validation failed",
                    service="LINE_WEBHOOK",
                    correlation_id=correlation_id,
                    original_exception=e
                )
            
            except BaseBotException:
                # Update failure metrics for custom exceptions
                self.connection_metrics['failed_calls'] += 1
                # Re-raise our custom exceptions
                raise
            
            except Exception as e:
                # Wrap unexpected errors
                logger.exception(
                    "Unexpected error in webhook processing",
                    exception=e,
                    correlation_id=correlation_id
                )
                raise DataProcessingException(
                    message=f"Unexpected webhook processing error: {str(e)}",
                    operation="webhook_processing",
                    data_type="webhook_request",
                    correlation_id=correlation_id,
                    original_exception=e
                )
    
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
            
            # Use context manager for automatic cleanup
            with ImageProcessor() as image_processor:
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
                
        except Exception as e:
            logger.error(f"Error handling image message: {str(e)}")
            try:
                error_msg = "圖像處理時發生錯誤，請稍後再試。\nError processing image, please try again later."
                self._send_message(event.reply_token, error_msg)
            except:
                pass

    def _handle_file_message(self, event):
        """Handle incoming file message"""
        try:
            user_id = event.source.user_id
            message_id = event.message.id
            file_name = getattr(event.message, "file_name", "uploaded_file")

            logger.info(f"Received file from user {user_id[:8]}...: {file_name}")

            from src.utils.file_utils import FileProcessor
            processor = FileProcessor()
            download = processor.download_file_from_line(self.line_bot_api, message_id)

            if not download or not download.get("success", False):
                error_code = download.get("error_code", "UNKNOWN") if download else "UNKNOWN"
                
                if error_code == "FILE_TOO_LARGE":
                    error_msg = (
                        "ไฟล์ขนาดใหญ่เกินไป (สูงสุด 20MB)\n"
                        "File too large (maximum 20MB)"
                    )
                elif error_code == "DOWNLOAD_TIMEOUT":
                    error_msg = (
                        "การดาวน์โหลดไฟล์หมดเวลา กรุณาลองใหม่\n"
                        "File download timed out, please try again"
                    )
                else:
                    error_msg = (
                        "ไม่สามารถดาวน์โหลดไฟล์ได้ กรุณาลองใหม่\n"
                        "Cannot download file, please try again"
                    )
                
                self._send_message(event.reply_token, error_msg)
                return

            file_data = download["file_data"]
            
            # Validate file type before processing
            file_validation = processor.validate_file_type(file_name, file_data)
            if not file_validation.get("success", False):
                error_info = file_validation.get("detected_type", {})
                detected_ext = error_info.get("extension", "unknown")
                
                error_msg = (
                    f"ไฟล์ประเภท {detected_ext} ไม่รองรับ กรุณาส่งไฟล์ประเภทที่รองรับ\n"
                    f"File type {detected_ext} not supported. Please send a supported file type.\n\n"
                    f"รองรับ / Supported: PDF, DOC, DOCX, TXT, XLS, XLSX, CSV, PPT, PPTX, "
                    f"PY, JS, HTML, CSS, JSON, XML, SQL, MD, YAML"
                )
                self._send_message(event.reply_token, error_msg)
                return

            # Send processing status message via push (since we can only reply once)
            processing_msg = (
                f"กำลังวิเคราะห์ไฟล์ {file_name} โปรดรอสักครู่...\n"
                f"Analyzing file {file_name}, please wait..."
            )
            try:
                from linebot.models import TextSendMessage
                self.line_bot_api.push_message(user_id, TextSendMessage(text=processing_msg))
            except Exception as push_error:
                logger.warning(f"Could not send processing status: {push_error}")

            ai_response = self.openai_service.get_response(
                user_id,
                f"Please analyze the attached file: {file_name}",
                use_streaming=False,
                file_data=file_data,
                file_name=file_name,
            )

            if ai_response["success"]:
                self._send_message(event.reply_token, ai_response["message"])
                tokens_used = ai_response.get("tokens_used", 0)
                logger.info(
                    f"Sent file analysis response to user {user_id[:8]}... [{tokens_used} tokens, {download.get('size', 0)} bytes]"
                )
            else:
                error_msg = "檔案分析失敗，請稍後再試。\nFile analysis failed, please try again later."
                self._send_message(event.reply_token, error_msg)
                logger.error(f"AI file analysis failed: {ai_response['error']}")

        except Exception as e:
            logger.error(f"Error handling file message: {str(e)}")
            try:
                error_msg = "處理檔案時發生錯誤，請稍後再試。\nError processing file, please try again later."
                self._send_message(event.reply_token, error_msg)
            except Exception:
                pass



    @retry_with_backoff(
        max_attempts=3,
        handle_types=(LineBotApiError, NetworkException, TimeoutException)
    )
    def _send_message(self, reply_token, message_text):
        """Send message back to LINE user with retry logic and error handling."""
        correlation_id = create_correlation_id()
        
        with logger.context(correlation_id=correlation_id, operation='send_message'):
            try:
                # Validate inputs
                if not reply_token:
                    raise ValidationException(
                        message="Reply token is required",
                        field="reply_token",
                        correlation_id=correlation_id
                    )
                
                if not message_text:
                    raise ValidationException(
                        message="Message text cannot be empty",
                        field="message_text",
                        correlation_id=correlation_id
                    )
                
                # LINE message limit is 5000 characters
                original_length = len(message_text)
                if original_length > 5000:
                    message_text = message_text[:4900] + "\n\n[訊息過長已截斷 / Message truncated]"
                    logger.warning(
                        f"Message truncated from {original_length} to {len(message_text)} characters",
                        correlation_id=correlation_id
                    )
                
                # Create and send message
                message = TextSendMessage(text=message_text)
                self.line_bot_api.reply_message(reply_token, message)
                
                logger.info(
                    f"Message sent successfully ({len(message_text)} chars)",
                    correlation_id=correlation_id
                )
                
            except LineBotApiError as e:
                # Wrap LINE API errors with our exception system
                status_code = getattr(e, 'status_code', None)
                error_msg = getattr(e.error, 'message', str(e)) if hasattr(e, 'error') and e.error else str(e)
                
                raise LineAPIException(
                    message=f"Failed to send reply message: {error_msg}",
                    status_code=status_code,
                    correlation_id=correlation_id,
                    original_exception=e,
                    context={
                        'reply_token': reply_token[:10] + "..." if reply_token else None,
                        'message_length': len(message_text)
                    }
                )
            
            except ValidationException:
                # Re-raise validation errors
                raise
            
            except Exception as e:
                # Wrap unexpected errors
                raise wrap_api_exception(
                    original_exception=e,
                    api_name="LINE",
                    operation="send_reply_message",
                    correlation_id=correlation_id
                )
    
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
    
    def _handle_postback_event(self, event):
        """Handle postback events from Rich Messages"""
        try:
            user_id = event.source.user_id
            postback_data = event.postback.data
            
            logger.info(f"Received postback from user {user_id[:8]}...: {postback_data}")
            
            # Debug logging for postback parsing
            logger.debug(f"Parsing postback data: {postback_data}")
            
            # Try to parse as JSON first (new format), then fall back to old format
            try:
                interaction_data = json.loads(postback_data)
            except json.JSONDecodeError:
                # Parse postback data (format: action=value&param=value) - legacy format
                params = {}
                for param in postback_data.split('&'):
                    if '=' in param:
                        key, value = param.split('=', 1)
                        params[key] = value
                interaction_data = params
            
            # Handle different postback actions
            action = interaction_data.get('action', '')
            logger.debug(f"Processing postback action: '{action}' with data: {interaction_data}")
            
            if action == 'interaction':
                # New Rich Message interaction system
                self._handle_rich_message_interaction(event, interaction_data)
            elif action == 'conversation_trigger':
                # Handle conversation trigger buttons (Tell me more, What's real here?, etc.)
                self._handle_conversation_trigger_action(event, interaction_data)
            elif action == 'show_reactions':
                self._handle_show_reactions_action(event, interaction_data)
            elif action == 'share_platform':
                self._handle_share_platform_action(event, interaction_data)
            elif action == 'view_content':
                # Legacy action
                self._handle_view_content_action(event, interaction_data)
            elif action in ['share', 'save', 'like']:
                # Legacy actions - convert to new format
                self._handle_legacy_action(event, action, interaction_data)
            else:
                logger.warning(f"Unknown postback action: {action} - Data: {postback_data}")
                
        except Exception as e:
            logger.error(f"Error handling postback event: {str(e)}")
            # Send error response to user
            try:
                error_msg = "⚠️ เกิดข้อผิดพลาดในการประมวลผล กรุณาลองใหม่อีกครั้ง\nError processing your request. Please try again."
                self._send_message(event.reply_token, error_msg)
            except:
                pass
    
    def _handle_conversation_trigger_action(self, event, interaction_data):
        """Handle conversation trigger actions (Tell me more, What's real here?, etc.)"""
        try:
            from src.utils.interaction_handler import get_interaction_handler
            
            user_id = event.source.user_id
            trigger_type = interaction_data.get('trigger_type', 'unknown')
            content_id = interaction_data.get('content_id', 'unknown')
            
            logger.info(f"Processing conversation trigger '{trigger_type}' from user {user_id[:8]}... for content {content_id}")
            
            # Get interaction handler with OpenAI service for AI responses
            interaction_handler = get_interaction_handler(self.openai_service)
            
            # Process the conversation trigger
            result = interaction_handler.handle_user_interaction(user_id, interaction_data, self.rich_message_service)
            
            if result['success']:
                message = result.get('message', 'Thanks for your interest!')
                
                # Log successful response generation
                if result.get('ai_generated'):
                    logger.info(f"Generated AI conversation response for trigger '{trigger_type}' for user {user_id[:8]}...")
                else:
                    logger.info(f"Used fallback response for trigger '{trigger_type}' for user {user_id[:8]}...")
                
                # Send the response
                self._send_message(event.reply_token, message)
                
            else:
                error_msg = "Sorry, I couldn't process that right now. Please try again."
                self._send_message(event.reply_token, error_msg)
                logger.warning(f"Conversation trigger handling failed for user {user_id[:8]}...: {result.get('error')}")
                
        except Exception as e:
            logger.error(f"Error handling conversation trigger: {str(e)}")
            error_msg = "There was an issue processing your request. Please try again."
            self._send_message(event.reply_token, error_msg)

    def _handle_rich_message_interaction(self, event, interaction_data):
        """Handle Rich Message interaction using the interaction handler system"""
        try:
            from src.utils.interaction_handler import get_interaction_handler
            
            user_id = event.source.user_id
            interaction_handler = get_interaction_handler(self.openai_service)
            
            # Process the interaction
            result = interaction_handler.handle_user_interaction(user_id, interaction_data)
            
            if result['success']:
                response_type = result.get('response_type', 'message')
                
                if response_type == 'message':
                    # Send text response
                    message = result.get('message', '✅ Action completed')
                    self._send_message(event.reply_token, message)
                    
                elif response_type == 'quick_reply':
                    # Send message with quick reply
                    from linebot.models import TextSendMessage
                    message = result.get('message', 'Please choose an option:')
                    quick_reply = result.get('quick_reply')
                    
                    text_message = TextSendMessage(text=message, quick_reply=quick_reply)
                    self.line_bot_api.reply_message(event.reply_token, text_message)
                    
                elif response_type == 'flex_message':
                    # Send flex message
                    flex_message = result.get('flex_message')
                    if flex_message:
                        self.line_bot_api.reply_message(event.reply_token, flex_message)
                    else:
                        self._send_message(event.reply_token, "✅ Action completed")
                        
                logger.info(f"Successfully handled interaction for user {user_id[:8]}...")
                
            else:
                error_msg = result.get('message', '❌ ไม่สามารถดำเนินการได้ กรุณาลองใหม่\nCould not complete action. Please try again.')
                self._send_message(event.reply_token, error_msg)
                logger.warning(f"Interaction handling failed for user {user_id[:8]}...: {result.get('error')}")
                
        except Exception as e:
            logger.error(f"Error handling Rich Message interaction: {str(e)}")
            error_msg = "⚠️ เกิดข้อผิดพลาดในการประมวลผล\nError processing your interaction."
            self._send_message(event.reply_token, error_msg)
    
    def _handle_show_reactions_action(self, event, interaction_data):
        """Handle show reactions action"""
        try:
            from src.utils.interaction_handler import get_interaction_handler
            
            user_id = event.source.user_id
            interaction_handler = get_interaction_handler(self.openai_service)
            content_id = interaction_data.get('content_id')
            
            if not content_id:
                self._send_message(event.reply_token, "❌ ข้อมูลไม่ครบถ้วน\nIncomplete data")
                return
            
            # Get quick reply for reactions
            quick_reply = interaction_handler.create_reaction_quick_reply(content_id)
            
            from linebot.models import TextSendMessage
            message = "😊 คุณรู้สึกอย่างไรกับเนื้อหานี้?\nHow did this content make you feel?"
            text_message = TextSendMessage(text=message, quick_reply=quick_reply)
            
            self.line_bot_api.reply_message(event.reply_token, text_message)
            logger.info(f"Sent reaction options to user {user_id[:8]}...")
            
        except Exception as e:
            logger.error(f"Error showing reactions: {str(e)}")
            self._send_message(event.reply_token, "❌ ไม่สามารถแสดงตัวเลือกได้\nCannot show options")
    
    def _handle_share_platform_action(self, event, interaction_data):
        """Handle platform-specific sharing action"""
        try:
            from src.utils.interaction_handler import get_interaction_handler
            
            user_id = event.source.user_id
            interaction_handler = get_interaction_handler(self.openai_service)
            
            # Process the share action
            result = interaction_handler.handle_user_interaction(user_id, interaction_data)
            
            if result['success']:
                message = result.get('message', '📤 แชร์เรียบร้อยแล้ว!\nShared successfully!')
                self._send_message(event.reply_token, message)
            else:
                error_msg = "❌ ไม่สามารถแชร์ได้ กรุณาลองใหม่\nCannot share. Please try again."
                self._send_message(event.reply_token, error_msg)
                
        except Exception as e:
            logger.error(f"Error handling share action: {str(e)}")
            error_msg = "⚠️ เกิดข้อผิดพลาดในการแชร์\nError sharing content."
            self._send_message(event.reply_token, error_msg)
    
    def _handle_legacy_action(self, event, action, interaction_data):
        """Handle legacy postback actions by converting to new format"""
        try:
            # Convert legacy action to new interaction format
            legacy_mapping = {
                'like': 'like',
                'share': 'share',
                'save': 'save'
            }
            
            new_interaction_data = {
                'action': 'interaction',
                'type': legacy_mapping.get(action, action),
                'content_id': interaction_data.get('content_id', 'legacy_content'),
                'legacy': True
            }
            
            # Handle using new system
            self._handle_rich_message_interaction(event, new_interaction_data)
            
        except Exception as e:
            logger.error(f"Error handling legacy action: {str(e)}")
            self._send_message(event.reply_token, "✅ ดำเนินการเรียบร้อย\nAction completed")
    
    def _handle_view_content_action(self, event, params):
        """Handle view content action from Rich Message"""
        try:
            menu_type = params.get('menu', 'default')
            response_msg = f"您正在查看 {menu_type} 內容。\nYou are viewing {menu_type} content."
            self._send_message(event.reply_token, response_msg)
        except Exception as e:
            logger.error(f"Error handling view content action: {str(e)}")
    
    def _handle_share_action(self, event, params):
        """Handle share action from Rich Message"""
        try:
            content_id = params.get('content_id', 'unknown')
            response_msg = "感謝您的分享！內容已準備好分享。\nThank you for sharing! Content is ready to share."
            self._send_message(event.reply_token, response_msg)
            logger.info(f"User shared content: {content_id}")
        except Exception as e:
            logger.error(f"Error handling share action: {str(e)}")
    
    def _handle_save_action(self, event, params):
        """Handle save action from Rich Message"""
        try:
            content_id = params.get('content_id', 'unknown')
            response_msg = "內容已保存！您可以隨時在收藏中查看。\nContent saved! You can view it in your favorites anytime."
            self._send_message(event.reply_token, response_msg)
            logger.info(f"User saved content: {content_id}")
        except Exception as e:
            logger.error(f"Error handling save action: {str(e)}")
    
    def _handle_like_action(self, event, params):
        """Handle like/react action from Rich Message"""
        try:
            content_id = params.get('content_id', 'unknown')
            reaction = params.get('reaction', 'like')
            response_msg = "感謝您的反饋！我們會繼續為您提供優質內容。\nThank you for your feedback! We'll keep providing quality content."
            self._send_message(event.reply_token, response_msg)
            logger.info(f"User reacted to content {content_id} with {reaction}")
        except Exception as e:
            logger.error(f"Error handling like action: {str(e)}")
    
    def send_rich_message(self, user_id, flex_message):
        """Send a Rich Message (Flex Message) to a specific user"""
        try:
            if not isinstance(flex_message, FlexSendMessage):
                logger.error("Invalid message type: expected FlexSendMessage")
                return {'success': False, 'error': 'Invalid message type'}
            
            self.line_bot_api.push_message(user_id, flex_message)
            logger.info(f"Sent Rich Message to user {user_id[:8]}...")
            
            return {'success': True}
            
        except LineBotApiError as e:
            error_msg = getattr(e.error, 'message', str(e)) if hasattr(e, 'error') and e.error else str(e)
            logger.error(f"Failed to send Rich Message: {e.status_code} - {error_msg}")
            return {'success': False, 'error': f"LINE API error: {error_msg}"}
        except Exception as e:
            logger.error(f"Error sending Rich Message: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def broadcast_rich_message(self, flex_message, audience_id=None):
        """Broadcast a Rich Message to all users or specific audience"""
        try:
            if not self.rich_message_service:
                logger.error("RichMessageService not initialized")
                return {'success': False, 'error': 'RichMessageService not available'}
            
            result = self.rich_message_service.broadcast_rich_message(
                flex_message,
                target_audience=audience_id
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error broadcasting Rich Message: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def create_and_set_rich_menu(self, menu_type='default', image_path=None):
        """Create and set a Rich Menu as default"""
        try:
            if not self.rich_message_service:
                logger.error("RichMessageService not initialized")
                return {'success': False, 'error': 'RichMessageService not available'}
            
            # Create Rich Menu
            rich_menu_id = self.rich_message_service.create_rich_menu(
                menu_type=menu_type,
                custom_image_path=image_path
            )
            
            if not rich_menu_id:
                return {'success': False, 'error': 'Failed to create Rich Menu'}
            
            # Set as default
            success = self.rich_message_service.set_default_rich_menu(rich_menu_id)
            
            if success:
                logger.info(f"Successfully created and set Rich Menu: {rich_menu_id}")
                return {'success': True, 'rich_menu_id': rich_menu_id}
            else:
                return {'success': False, 'error': 'Failed to set Rich Menu as default'}
                
        except Exception as e:
            logger.error(f"Error creating Rich Menu: {str(e)}")
            return {'success': False, 'error': str(e)}
