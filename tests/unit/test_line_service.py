"""
Unit tests for LINE service
"""
import pytest
import json
import hmac
import hashlib
import base64
from unittest.mock import Mock, patch, call
from linebot.exceptions import InvalidSignatureError, LineBotApiError
from linebot.models import FlexSendMessage, PostbackEvent
from src.services.line_service import LineService


@pytest.mark.unit
@pytest.mark.line_api
class TestLineService:
    """Test LINE service functionality"""
    
    def test_init(self, mock_settings, openai_service, conversation_service):
        """Test LINE service initialization"""
        with patch('src.services.line_service.LineBotApi') as mock_api, \
             patch('src.services.line_service.WebhookHandler') as mock_handler:
            
            service = LineService(mock_settings, openai_service, conversation_service)
            
            assert service.settings == mock_settings
            assert service.openai_service == openai_service
            assert service.conversation_service == conversation_service
            
            # Verify LINE Bot API initialization
            mock_api.assert_called_once_with(mock_settings.LINE_CHANNEL_ACCESS_TOKEN)
            mock_handler.assert_called_once_with(mock_settings.LINE_CHANNEL_SECRET)
    
    def test_verify_signature_valid(self, line_service):
        """Test valid webhook signature verification"""
        body = "test_body"
        secret = "test_channel_secret"
        
        # Create expected signature
        hash_digest = hmac.new(
            secret.encode('utf-8'),
            body.encode('utf-8'),
            hashlib.sha256
        ).digest()
        expected_signature = base64.b64encode(hash_digest).decode('utf-8')
        
        # Mock the settings secret
        line_service.settings.LINE_CHANNEL_SECRET = secret
        
        assert line_service._verify_signature(expected_signature, body) is True
    
    def test_verify_signature_invalid(self, line_service):
        """Test invalid webhook signature verification"""
        body = "test_body"
        invalid_signature = "invalid_signature"
        
        assert line_service._verify_signature(invalid_signature, body) is False
    
    def test_verify_signature_empty(self, line_service):
        """Test empty signature verification"""
        body = "test_body"
        empty_signature = ""
        
        assert line_service._verify_signature(empty_signature, body) is False
    
    def test_handle_webhook_success(self, line_service):
        """Test successful webhook handling"""
        signature = "valid_signature"
        body = "webhook_body"
        
        # Mock signature verification and handler
        line_service._verify_signature = Mock(return_value=True)
        line_service.handler.handle = Mock()
        
        result = line_service.handle_webhook(signature, body)
        
        assert result['success'] is True
        line_service._verify_signature.assert_called_once_with(signature, body)
        line_service.handler.handle.assert_called_once_with(body, signature)
    
    def test_handle_webhook_invalid_signature(self, line_service):
        """Test webhook handling with invalid signature"""
        signature = "invalid_signature"
        body = "webhook_body"
        
        # Mock signature verification to fail
        line_service._verify_signature = Mock(return_value=False)
        
        result = line_service.handle_webhook(signature, body)
        
        assert result['success'] is False
        assert result['error'] == 'Invalid signature'
        line_service._verify_signature.assert_called_once_with(signature, body)
    
    def test_handle_webhook_exception(self, line_service):
        """Test webhook handling with exception"""
        signature = "valid_signature"
        body = "webhook_body"
        
        # Mock signature verification to pass but handler to raise exception
        line_service._verify_signature = Mock(return_value=True)
        line_service.handler.handle = Mock(side_effect=Exception("Handler error"))
        
        result = line_service.handle_webhook(signature, body)
        
        assert result['success'] is False
        assert result['error'] == "Handler error"
    
    def test_handle_text_message_success(self, line_service, sample_line_message_event):
        """Test successful text message handling"""
        # Mock OpenAI service response
        mock_ai_response = {
            'success': True,
            'message': 'Hello! How can I help you?',
            'tokens_used': 25
        }
        line_service.openai_service.get_response = Mock(return_value=mock_ai_response)
        line_service._send_message = Mock()
        
        # Call the text message handler
        line_service._handle_text_message(sample_line_message_event)
        
        # Verify OpenAI service was called
        line_service.openai_service.get_response.assert_called_once_with(
            sample_line_message_event.source.user_id,
            sample_line_message_event.message.text,
            use_streaming=False
        )
        
        # Verify message was sent
        line_service._send_message.assert_called_once_with(
            sample_line_message_event.reply_token,
            mock_ai_response['message']
        )
    
    def test_handle_text_message_ai_failure(self, line_service, sample_line_message_event):
        """Test text message handling when AI service fails"""
        # Mock OpenAI service failure
        mock_ai_response = {
            'success': False,
            'message': None,
            'error': 'API timeout'
        }
        line_service.openai_service.get_response = Mock(return_value=mock_ai_response)
        line_service._send_message = Mock()
        
        # Call the text message handler
        line_service._handle_text_message(sample_line_message_event)
        
        # Verify error message was sent
        expected_error_msg = "抱歉，我現在無法回應您的訊息。請稍後再試。\nSorry, I'm unable to respond to your message right now. Please try again later."
        line_service._send_message.assert_called_once_with(
            sample_line_message_event.reply_token,
            expected_error_msg
        )
    
    def test_handle_text_message_exception(self, line_service, sample_line_message_event):
        """Test text message handling with exception"""
        # Mock OpenAI service to raise exception
        line_service.openai_service.get_response = Mock(side_effect=Exception("Service error"))
        line_service._send_message = Mock()
        
        # Call the text message handler
        line_service._handle_text_message(sample_line_message_event)
        
        # Verify error message was sent
        expected_error_msg = "系統發生錯誤，請稍後再試。\nSystem error occurred, please try again later."
        line_service._send_message.assert_called_once_with(
            sample_line_message_event.reply_token,
            expected_error_msg
        )
    
    def test_send_message_success(self, line_service):
        """Test successful message sending"""
        reply_token = "reply_token_123"
        message_text = "Test message"
        
        # Mock LINE Bot API
        line_service.line_bot_api.reply_message = Mock()
        
        line_service._send_message(reply_token, message_text)
        
        # Verify API call
        line_service.line_bot_api.reply_message.assert_called_once()
        call_args = line_service.line_bot_api.reply_message.call_args
        assert call_args[0][0] == reply_token
        assert call_args[0][1].text == message_text
    
    def test_send_message_truncation(self, line_service):
        """Test message truncation for long messages"""
        reply_token = "reply_token_123"
        long_message = "x" * 6000  # Exceeds 5000 character limit
        
        line_service.line_bot_api.reply_message = Mock()
        
        line_service._send_message(reply_token, long_message)
        
        # Verify message was truncated
        call_args = line_service.line_bot_api.reply_message.call_args
        sent_message = call_args[0][1].text
        assert len(sent_message) <= 5000
        assert "[訊息過長已截斷 / Message truncated]" in sent_message
    
    def test_send_message_api_error(self, line_service):
        """Test message sending with LINE Bot API error"""
        reply_token = "reply_token_123"
        message_text = "Test message"
        
        # Mock LINE Bot API to raise error
        err = type("Err", (), {"message": "API Error"})()
        error = LineBotApiError(400, {}, error=err)
        line_service.line_bot_api.reply_message = Mock(side_effect=error)
        
        with pytest.raises(LineBotApiError):
            line_service._send_message(reply_token, message_text)
    
    def test_send_push_message_success(self, line_service):
        """Test successful push message sending"""
        user_id = "user_123"
        message_text = "Push message"
        
        line_service.line_bot_api.push_message = Mock()
        
        result = line_service.send_push_message(user_id, message_text)
        
        assert result['success'] is True
        line_service.line_bot_api.push_message.assert_called_once()
        call_args = line_service.line_bot_api.push_message.call_args
        assert call_args[0][0] == user_id
        assert call_args[0][1].text == message_text
    
    def test_send_push_message_api_error(self, line_service):
        """Test push message sending with API error"""
        user_id = "user_123"
        message_text = "Push message"
        
        err = type("Err", (), {"message": "API Error"})()
        error = LineBotApiError(400, {}, error=err)
        line_service.line_bot_api.push_message = Mock(side_effect=error)
        
        result = line_service.send_push_message(user_id, message_text)
        
        assert result['success'] is False
        assert "LINE API error" in result['error']
    
    def test_send_push_message_truncation(self, line_service):
        """Test push message truncation"""
        user_id = "user_123"
        long_message = "x" * 6000
        
        line_service.line_bot_api.push_message = Mock()
        
        result = line_service.send_push_message(user_id, long_message)
        
        assert result['success'] is True
        call_args = line_service.line_bot_api.push_message.call_args
        sent_message = call_args[0][1].text
        assert len(sent_message) <= 5000
        assert "[訊息過長已截斷 / Message truncated]" in sent_message
    
    def test_message_handler_registration(self, mock_settings, openai_service, conversation_service):
        """Test that message handlers are properly registered"""
        with patch('src.services.line_service.LineBotApi'), \
             patch('src.services.line_service.WebhookHandler') as mock_handler:
            
            mock_handler_instance = Mock()
            mock_handler.return_value = mock_handler_instance
            
            service = LineService(mock_settings, openai_service, conversation_service)
            
            # Verify handler.add was called for TextMessage
            assert mock_handler_instance.add.called
            calls = mock_handler_instance.add.call_args_list
            
            # Should have at least one call for TextMessage
            assert len(calls) >= 1
    
    def test_signature_verification_error_handling(self, line_service):
        """Test signature verification error handling"""
        body = "test_body"
        
        # Test with None signature
        assert line_service._verify_signature(None, body) is False
        
        # Test with invalid base64 in signature creation (should handle gracefully)
        line_service.settings.LINE_CHANNEL_SECRET = None
        assert line_service._verify_signature("signature", body) is False
    
    def test_user_privacy_in_logs(self, line_service, sample_line_message_event, caplog):
        """Test that user IDs are truncated in logs for privacy"""
        import logging
        
        # Mock successful AI response
        mock_ai_response = {
            'success': True,
            'message': 'Test response',
            'tokens_used': 25
        }
        line_service.openai_service.get_response = Mock(return_value=mock_ai_response)
        line_service._send_message = Mock()
        
        with caplog.at_level(logging.INFO):
            line_service._handle_text_message(sample_line_message_event)
        
        log_output = caplog.text
        # Check that truncated user ID is in logs
        truncated_id = sample_line_message_event.source.user_id[:8]
        assert truncated_id in log_output
    
    # Rich Message Tests
    def test_send_rich_message_success(self, line_service):
        """Test successful Rich Message sending"""
        user_id = "user_123"
        mock_flex_message = Mock(spec=FlexSendMessage)
        
        line_service.line_bot_api.push_message = Mock()
        
        result = line_service.send_rich_message(user_id, mock_flex_message)
        
        assert result['success'] is True
        line_service.line_bot_api.push_message.assert_called_once_with(user_id, mock_flex_message)
    
    def test_send_rich_message_invalid_type(self, line_service):
        """Test Rich Message sending with invalid message type"""
        user_id = "user_123"
        invalid_message = "Not a FlexSendMessage"
        
        result = line_service.send_rich_message(user_id, invalid_message)
        
        assert result['success'] is False
        assert "Invalid message type" in result['error']
    
    def test_send_rich_message_api_error(self, line_service):
        """Test Rich Message sending with API error"""
        user_id = "user_123"
        mock_flex_message = Mock(spec=FlexSendMessage)
        
        err = type("Err", (), {"message": "API Error"})()
        error = LineBotApiError(400, {}, error=err)
        line_service.line_bot_api.push_message = Mock(side_effect=error)
        
        result = line_service.send_rich_message(user_id, mock_flex_message)
        
        assert result['success'] is False
        assert "LINE API error" in result['error']
    
    def test_broadcast_rich_message_success(self, line_service):
        """Test successful Rich Message broadcasting"""
        mock_flex_message = Mock(spec=FlexSendMessage)
        mock_rich_message_service = Mock()
        mock_rich_message_service.broadcast_rich_message.return_value = {'success': True}
        
        line_service.rich_message_service = mock_rich_message_service
        
        result = line_service.broadcast_rich_message(mock_flex_message)
        
        assert result['success'] is True
        mock_rich_message_service.broadcast_rich_message.assert_called_once_with(
            mock_flex_message, target_audience=None
        )
    
    def test_broadcast_rich_message_no_service(self, line_service):
        """Test Rich Message broadcasting without RichMessageService"""
        mock_flex_message = Mock(spec=FlexSendMessage)
        
        result = line_service.broadcast_rich_message(mock_flex_message)
        
        assert result['success'] is False
        assert "RichMessageService not available" in result['error']
    
    def test_create_and_set_rich_menu_success(self, line_service):
        """Test successful Rich Menu creation and setting"""
        mock_rich_message_service = Mock()
        mock_rich_message_service.create_rich_menu.return_value = "richmenu-123"
        mock_rich_message_service.set_default_rich_menu.return_value = True
        
        line_service.rich_message_service = mock_rich_message_service
        
        result = line_service.create_and_set_rich_menu("default", "/path/to/image.png")
        
        assert result['success'] is True
        assert result['rich_menu_id'] == "richmenu-123"
    
    def test_create_and_set_rich_menu_creation_failure(self, line_service):
        """Test Rich Menu creation failure"""
        mock_rich_message_service = Mock()
        mock_rich_message_service.create_rich_menu.return_value = None
        
        line_service.rich_message_service = mock_rich_message_service
        
        result = line_service.create_and_set_rich_menu()
        
        assert result['success'] is False
        assert "Failed to create Rich Menu" in result['error']
    
    def test_handle_postback_event_view_content(self, line_service):
        """Test postback event handling for view content action"""
        mock_event = Mock(spec=PostbackEvent)
        mock_event.source = Mock()
        mock_event.source.user_id = "user_12345678"
        mock_event.postback = Mock()
        mock_event.postback.data = "action=view_content&menu=daily_inspiration"
        mock_event.reply_token = "reply_token_123"
        
        line_service._send_message = Mock()
        
        line_service._handle_postback_event(mock_event)
        
        line_service._send_message.assert_called_once()
        call_args = line_service._send_message.call_args
        assert "daily_inspiration" in call_args[0][1]
    
    def test_handle_postback_event_share_action(self, line_service):
        """Test postback event handling for share action"""
        mock_event = Mock(spec=PostbackEvent)
        mock_event.source = Mock()
        mock_event.source.user_id = "user_12345678"
        mock_event.postback = Mock()
        mock_event.postback.data = "action=share&content_id=content_123"
        mock_event.reply_token = "reply_token_123"
        
        line_service._send_message = Mock()
        
        line_service._handle_postback_event(mock_event)
        
        line_service._send_message.assert_called_once()
        call_args = line_service._send_message.call_args
        assert "分享" in call_args[0][1] or "sharing" in call_args[0][1].lower()
    
    def test_handle_postback_event_save_action(self, line_service):
        """Test postback event handling for save action"""
        mock_event = Mock(spec=PostbackEvent)
        mock_event.source = Mock()
        mock_event.source.user_id = "user_12345678"
        mock_event.postback = Mock()
        mock_event.postback.data = "action=save&content_id=content_123"
        mock_event.reply_token = "reply_token_123"
        
        line_service._send_message = Mock()
        
        line_service._handle_postback_event(mock_event)
        
        line_service._send_message.assert_called_once()
        call_args = line_service._send_message.call_args
        assert "保存" in call_args[0][1] or "saved" in call_args[0][1].lower()
    
    def test_handle_postback_event_like_action(self, line_service):
        """Test postback event handling for like action"""
        mock_event = Mock(spec=PostbackEvent)
        mock_event.source = Mock()
        mock_event.source.user_id = "user_12345678"
        mock_event.postback = Mock()
        mock_event.postback.data = "action=like&content_id=content_123&reaction=like"
        mock_event.reply_token = "reply_token_123"
        
        line_service._send_message = Mock()
        
        line_service._handle_postback_event(mock_event)
        
        line_service._send_message.assert_called_once()
        call_args = line_service._send_message.call_args
        assert "反饋" in call_args[0][1] or "feedback" in call_args[0][1].lower()
    
    def test_handle_postback_event_unknown_action(self, line_service, caplog):
        """Test postback event handling for unknown action"""
        import logging
        
        mock_event = Mock(spec=PostbackEvent)
        mock_event.source = Mock()
        mock_event.source.user_id = "user_12345678"
        mock_event.postback = Mock()
        mock_event.postback.data = "action=unknown_action"
        
        with caplog.at_level(logging.WARNING):
            line_service._handle_postback_event(mock_event)
        
        assert "Unknown postback action" in caplog.text
    
    def test_postback_handler_registration(self, mock_settings, openai_service, conversation_service):
        """Test that postback handler is properly registered"""
        with patch('src.services.line_service.LineBotApi'), \
             patch('src.services.line_service.WebhookHandler') as mock_handler:
            
            mock_handler_instance = Mock()
            mock_handler.return_value = mock_handler_instance
            
            service = LineService(mock_settings, openai_service, conversation_service)
            
            # Verify handler.add was called for PostbackEvent
            calls = mock_handler_instance.add.call_args_list
            postback_calls = [call for call in calls if len(call[0]) > 0 and 'PostbackEvent' in str(call[0][0])]
            assert len(postback_calls) >= 1