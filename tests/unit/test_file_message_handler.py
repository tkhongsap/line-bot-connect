"""
Unit tests for FileMessage handler functionality
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '../../src'))

from src.services.line_service import LineService
from src.services.openai_service import OpenAIService
from src.services.conversation_factory import create_conversation_service
from src.config.settings import Settings
from linebot.models import FileMessage, MessageEvent
from linebot.exceptions import LineBotApiError


class TestFileMessageHandler:
    """Test FileMessage handler registration and functionality"""
    
    @pytest.fixture
    def mock_settings(self):
        """Mock settings for testing"""
        settings = Mock(spec=Settings)
        settings.LINE_CHANNEL_ACCESS_TOKEN = "test_token"
        settings.LINE_CHANNEL_SECRET = "test_secret"
        return settings
    
    @pytest.fixture
    def mock_openai_service(self):
        """Mock OpenAI service for testing"""
        return Mock(spec=OpenAIService)
    
    @pytest.fixture
    def mock_conversation_service(self):
        """Mock conversation service for testing"""
        return Mock()
    
    @pytest.fixture
    def line_service(self, mock_settings, mock_openai_service, mock_conversation_service):
        """Create LineService instance for testing"""
        with patch('src.services.line_service.LineBotApi'), \
             patch('src.services.line_service.WebhookHandler') as mock_handler:
            
            service = LineService(mock_settings, mock_openai_service, mock_conversation_service)
            service.handler = mock_handler.return_value
            return service
    
    def test_filemessage_import_success(self):
        """Test that FileMessage can be imported successfully"""
        from linebot.models import FileMessage
        assert FileMessage is not None
    
    def test_filemessage_handler_registration(self, line_service):
        """Test that FileMessage handler is properly registered"""
        # Verify LineService initializes without errors
        assert line_service is not None
        assert hasattr(line_service, '_handle_file_message')
    
    @patch('src.utils.file_utils.FileProcessor')
    def test_handle_file_message_success(self, mock_file_processor, line_service):
        """Test successful file message handling"""
        # Setup mocks
        mock_event = Mock()
        mock_event.source.user_id = "test_user_123"
        mock_event.message.id = "test_message_456" 
        mock_event.message.file_name = "test.pdf"
        mock_event.reply_token = "reply_token_789"
        
        # Mock file processor
        mock_processor = mock_file_processor.return_value
        mock_processor.download_file_from_line.return_value = {
            "success": True,
            "file_data": b"test file content",
            "size": 100,
            "file_type": "application/pdf",
            "extension": ".pdf"
        }
        mock_processor.validate_file_type.return_value = {
            "success": True,
            "file_type_info": {"extension": ".pdf", "mime_type": "application/pdf"}
        }
        
        # Mock OpenAI service response
        line_service.openai_service.get_response.return_value = {
            "success": True,
            "message": "File analyzed successfully",
            "tokens_used": 150
        }
        
        # Mock LINE Bot API
        line_service.line_bot_api = Mock()
        
        # Execute test
        line_service._handle_file_message(mock_event)
        
        # Verify calls
        mock_processor.download_file_from_line.assert_called_once()
        mock_processor.validate_file_type.assert_called_once()
        line_service.openai_service.get_response.assert_called_once()
    
    @patch('src.utils.file_utils.FileProcessor')
    def test_handle_file_message_download_failure(self, mock_file_processor, line_service):
        """Test file message handling with download failure"""
        # Setup mocks
        mock_event = Mock()
        mock_event.source.user_id = "test_user_123"
        mock_event.message.id = "test_message_456"
        mock_event.reply_token = "reply_token_789"
        
        # Mock file processor with download failure
        mock_processor = mock_file_processor.return_value
        mock_processor.download_file_from_line.return_value = {
            "success": False,
            "error": "Download failed",
            "error_code": "DOWNLOAD_FAILED"
        }
        
        # Mock _send_message
        line_service._send_message = Mock()
        
        # Execute test
        line_service._handle_file_message(mock_event)
        
        # Verify error handling
        line_service._send_message.assert_called_once()
        args = line_service._send_message.call_args[0]
        assert "Cannot download file" in args[1]
    
    @patch('src.utils.file_utils.FileProcessor')
    def test_handle_file_message_file_too_large(self, mock_file_processor, line_service):
        """Test file message handling with file size limit exceeded"""
        # Setup mocks
        mock_event = Mock()
        mock_event.source.user_id = "test_user_123"
        mock_event.message.id = "test_message_456"
        mock_event.reply_token = "reply_token_789"
        
        # Mock file processor with size limit error
        mock_processor = mock_file_processor.return_value
        mock_processor.download_file_from_line.return_value = {
            "success": False,
            "error": "File too large (max 20MB)",
            "error_code": "FILE_TOO_LARGE"
        }
        
        # Mock _send_message
        line_service._send_message = Mock()
        
        # Execute test
        line_service._handle_file_message(mock_event)
        
        # Verify error handling
        line_service._send_message.assert_called_once()
        args = line_service._send_message.call_args[0]
        assert "File too large" in args[1]
        assert "20MB" in args[1]
    
    @patch('src.utils.file_utils.FileProcessor')
    def test_handle_file_message_unsupported_type(self, mock_file_processor, line_service):
        """Test file message handling with unsupported file type"""
        # Setup mocks
        mock_event = Mock()
        mock_event.source.user_id = "test_user_123"
        mock_event.message.id = "test_message_456"
        mock_event.message.file_name = "test.xyz"
        mock_event.reply_token = "reply_token_789"
        
        # Mock file processor
        mock_processor = mock_file_processor.return_value
        mock_processor.download_file_from_line.return_value = {
            "success": True,
            "file_data": b"test content",
            "size": 100
        }
        mock_processor.validate_file_type.return_value = {
            "success": False,
            "detected_type": {"extension": ".xyz"}
        }
        
        # Mock _send_message
        line_service._send_message = Mock()
        
        # Execute test
        line_service._handle_file_message(mock_event)
        
        # Verify error handling
        line_service._send_message.assert_called_once()
        args = line_service._send_message.call_args[0]
        assert "not supported" in args[1]
        assert "PDF, DOC, DOCX" in args[1]
    
    @patch('src.utils.file_utils.FileProcessor')
    def test_handle_file_message_openai_failure(self, mock_file_processor, line_service):
        """Test file message handling with OpenAI processing failure"""
        # Setup mocks
        mock_event = Mock()
        mock_event.source.user_id = "test_user_123"
        mock_event.message.id = "test_message_456"
        mock_event.message.file_name = "test.pdf"
        mock_event.reply_token = "reply_token_789"
        
        # Mock file processor
        mock_processor = mock_file_processor.return_value
        mock_processor.download_file_from_line.return_value = {
            "success": True,
            "file_data": b"test content",
            "size": 100
        }
        mock_processor.validate_file_type.return_value = {
            "success": True,
            "file_type_info": {"extension": ".pdf"}
        }
        
        # Mock OpenAI service failure
        line_service.openai_service.get_response.return_value = {
            "success": False,
            "error": "OpenAI API error",
            "message": None
        }
        
        # Mock _send_message and LINE Bot API
        line_service._send_message = Mock()
        line_service.line_bot_api = Mock()
        
        # Execute test
        line_service._handle_file_message(mock_event)
        
        # Verify error handling
        assert line_service._send_message.call_count == 2  # Status + error message
        # Check for processing status and error messages
        call_args = [call[0][1] for call in line_service._send_message.call_args_list]
        assert any("analysis failed" in arg.lower() for arg in call_args)
    
    def test_handle_file_message_exception_handling(self, line_service):
        """Test file message handling with unexpected exception"""
        # Setup mocks
        mock_event = Mock()
        mock_event.source.user_id = "test_user_123"
        mock_event.message.id = "test_message_456"
        mock_event.reply_token = "reply_token_789"
        
        # Mock to raise exception
        with patch('src.utils.file_utils.FileProcessor', side_effect=Exception("Unexpected error")):
            line_service._send_message = Mock()
            
            # Execute test
            line_service._handle_file_message(mock_event)
            
            # Verify error handling
            line_service._send_message.assert_called_once()
            args = line_service._send_message.call_args[0]
            assert "Error processing file" in args[1]


class TestFileMessageIntegration:
    """Integration tests for FileMessage with LINE Bot"""
    
    def test_line_service_initialization_with_filemessage(self):
        """Test that LineService initializes properly with FileMessage support"""
        with patch('src.services.line_service.LineBotApi'), \
             patch('src.services.line_service.WebhookHandler'):
            
            settings = Mock(spec=Settings)
            settings.LINE_CHANNEL_ACCESS_TOKEN = "test_token"
            settings.LINE_CHANNEL_SECRET = "test_secret"
            
            openai_service = Mock(spec=OpenAIService)
            conversation_service = Mock()
            
            # Should not raise any exceptions
            line_service = LineService(settings, openai_service, conversation_service)
            assert line_service is not None
    
    def test_filemessage_handler_method_exists(self):
        """Test that _handle_file_message method exists and is callable"""
        with patch('src.services.line_service.LineBotApi'), \
             patch('src.services.line_service.WebhookHandler'):
            
            settings = Mock(spec=Settings)
            settings.LINE_CHANNEL_ACCESS_TOKEN = "test_token"
            settings.LINE_CHANNEL_SECRET = "test_secret"
            
            line_service = LineService(settings, Mock(), Mock())
            
            assert hasattr(line_service, '_handle_file_message')
            assert callable(getattr(line_service, '_handle_file_message'))


if __name__ == '__main__':
    pytest.main([__file__, '-v']) 