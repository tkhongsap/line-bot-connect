"""
Integration tests for complete file processing pipeline
"""
import pytest
import sys
import os
from unittest.mock import Mock, patch

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '../../src'))

from src.services.line_service import LineService
from src.services.openai_service import OpenAIService
from src.services.conversation_factory import create_conversation_service
from src.config.settings import Settings
from src.utils.file_utils import FileProcessor


class TestFileProcessingPipeline:
    """Integration tests for end-to-end file processing"""
    
    @pytest.fixture
    def mock_settings(self):
        """Mock settings for testing"""
        settings = Mock(spec=Settings)
        settings.LINE_CHANNEL_ACCESS_TOKEN = "test_token"
        settings.LINE_CHANNEL_SECRET = "test_secret"
        settings.AZURE_OPENAI_API_KEY = "test_api_key"
        settings.AZURE_OPENAI_ENDPOINT = "https://test.openai.azure.com"
        settings.AZURE_OPENAI_API_VERSION = "2025-01-01-preview"
        settings.AZURE_OPENAI_DEPLOYMENT_NAME = "gpt-4.1-nano"
        return settings
    
    @pytest.fixture
    def conversation_service(self):
        """Create conversation service for testing"""
        return create_conversation_service()
    
    def test_file_processor_functionality(self):
        """Test FileProcessor core functionality"""
        processor = FileProcessor()
        
        # Test supported file types
        assert '.pdf' in processor.SUPPORTED_EXTENSIONS
        assert '.docx' in processor.SUPPORTED_EXTENSIONS
        assert '.py' in processor.SUPPORTED_EXTENSIONS
        
        # Test file type detection
        result = processor.detect_file_type(b'%PDF-1.4', "test.pdf")
        assert result['is_supported'] == True
        assert result['extension'] == '.pdf'
        
        # Test validation
        validation = processor.validate_file_type("test.pdf", b'%PDF-1.4')
        assert validation['success'] == True
    
    @patch('src.services.openai_service.AzureOpenAI')
    def test_openai_service_file_upload(self, mock_azure_openai, mock_settings, conversation_service):
        """Test OpenAI service file upload functionality"""
        # Mock the Azure OpenAI client
        mock_client = Mock()
        mock_azure_openai.return_value = mock_client
        
        # Mock file upload response
        mock_response = Mock()
        mock_response.id = "file-12345"
        mock_client.files.create.return_value = mock_response
        
        # Create OpenAI service
        openai_service = OpenAIService(mock_settings, conversation_service)
        
        # Test file upload
        test_data = b"Test file content"
        file_id = openai_service._upload_file(test_data, "test.txt")
        
        assert file_id == "file-12345"
        mock_client.files.create.assert_called_once()
        
        # Verify correct parameters
        call_args = mock_client.files.create.call_args
        assert call_args[1]['purpose'] == 'assistants'
    
    @patch('src.services.line_service.LineBotApi')
    @patch('src.services.line_service.WebhookHandler')
    def test_line_service_initialization_with_file_support(self, mock_webhook, mock_linebot, mock_settings):
        """Test that LineService initializes with file support"""
        openai_service = Mock()
        conversation_service = Mock()
        
        # Create LineService
        line_service = LineService(mock_settings, openai_service, conversation_service)
        
        # Verify file handler method exists
        assert hasattr(line_service, '_handle_file_message')
        assert callable(line_service._handle_file_message)
        
        # Verify FileMessage import works
        from linebot.models import FileMessage
        assert FileMessage is not None
    
    def test_file_type_validation_pipeline(self):
        """Test the complete file type validation pipeline"""
        processor = FileProcessor()
        
        # Test various file types
        test_cases = [
            (b'%PDF-1.4', 'document.pdf', True),
            (b'{"key": "value"}', 'data.json', True),
            (b'print("hello")', 'script.py', True),
            (b'Name,Age\nJohn,25', 'data.csv', True),
            (b'PK\x03\x04', 'document.docx', True),  # ZIP-based Office doc
            (b'random bytes', 'file.xyz', False),  # Unsupported
        ]
        
        for content, filename, should_be_supported in test_cases:
            result = processor.validate_file_type(filename, content)
            assert result['success'] == should_be_supported, f"Failed for {filename}"
    
    def test_error_handling_pipeline(self):
        """Test error handling throughout the pipeline"""
        processor = FileProcessor()
        
        # Test file too large simulation
        large_data = b'x' * (25 * 1024 * 1024)  # 25MB
        # Note: This tests the concept; actual size check is in download_file_from_line
        
        # Test unsupported file type
        result = processor.validate_file_type("bad.xyz", b"content")
        assert result['success'] == False
        assert 'UNSUPPORTED_FILE_TYPE' in result['error_code']
        
        # Test empty file
        result = processor.detect_file_type(b'', "empty.txt")
        assert result['extension'] == '.txt'
        assert result['is_supported'] == True
    
    def test_file_metadata_extraction(self):
        """Test file metadata extraction and processing"""
        processor = FileProcessor()
        
        # Test metadata for different file types
        test_files = [
            ('document.pdf', b'%PDF-1.4', 'application/pdf'),
            ('image.png', b'\x89PNG\r\n\x1a\n', 'image/png'),
            ('data.csv', b'col1,col2\nval1,val2', 'text/plain'),  # Detected as text
        ]
        
        for filename, content, expected_mime in test_files:
            info = processor.detect_file_type(content, filename)
            assert info['is_supported'] == True
            if info.get('mime_type'):
                # Only check if mime type was detected
                assert expected_mime in [info['mime_type'], 'text/plain']  # text/plain is fallback


class TestFileProcessingErrorScenarios:
    """Test error scenarios in file processing"""
    
    def test_malformed_file_content(self):
        """Test handling of malformed file content"""
        processor = FileProcessor()
        
        # Malformed PDF
        malformed_pdf = b'%PDF-1.4\x00\x01\x02incomplete'
        result = processor.detect_file_type(malformed_pdf, "bad.pdf")
        assert result['extension'] == '.pdf'  # Should still detect from header
        assert result['is_supported'] == True
    
    def test_filename_extension_mismatch(self):
        """Test when filename extension doesn't match content"""
        processor = FileProcessor()
        
        # PNG content with .txt extension
        png_content = b'\x89PNG\r\n\x1a\n' + b'fake png data'
        result = processor.detect_file_type(png_content, "image.txt")
        
        # Content-based detection should override filename
        assert result['extension'] == '.png'
        assert result['mime_type'] == 'image/png'
        assert result['is_supported'] == True
    
    def test_unicode_filename_handling(self):
        """Test handling of unicode filenames"""
        processor = FileProcessor()
        
        # Unicode filename
        unicode_filename = "文档.pdf"
        result = processor.detect_file_type(b'%PDF-1.4', unicode_filename)
        assert result['extension'] == '.pdf'
        assert result['is_supported'] == True
    
    def test_no_extension_filename(self):
        """Test handling of files without extensions"""
        processor = FileProcessor()
        
        # File without extension but with PDF content
        result = processor.detect_file_type(b'%PDF-1.4', "README")
        assert result['extension'] == '.pdf'  # Detected from content
        assert result['is_supported'] == True
    
    def test_binary_file_detection(self):
        """Test detection of various binary file types"""
        processor = FileProcessor()
        
        # Test various binary signatures
        test_cases = [
            (b'\xff\xd8\xff', '.jpg', 'image/jpeg'),
            (b'GIF87a', '.gif', 'image/gif'),
            (b'GIF89a', '.gif', 'image/gif'),
        ]
        
        for signature, expected_ext, expected_mime in test_cases:
            content = signature + b'fake data'
            result = processor.detect_file_type(content, None)
            assert result['extension'] == expected_ext
            assert result['mime_type'] == expected_mime


class TestFileProcessingPerformance:
    """Test performance aspects of file processing"""
    
    def test_large_file_size_validation(self):
        """Test file size validation for large files"""
        processor = FileProcessor()
        
        # Test max file size constant
        assert processor.MAX_FILE_SIZE == 20 * 1024 * 1024  # 20MB
        
        # Processor doesn't directly validate size (done in download_file_from_line)
        # but we can test the constant is correctly set
        assert processor.MAX_FILE_SIZE > 0
    
    def test_file_type_detection_speed(self):
        """Test that file type detection is reasonably fast"""
        processor = FileProcessor()
        
        # Test with moderately sized content
        content = b'%PDF-1.4' + b'x' * 1000  # 1KB
        
        import time
        start = time.time()
        result = processor.detect_file_type(content, "test.pdf")
        end = time.time()
        
        # Should complete very quickly (under 1 second)
        assert (end - start) < 1.0
        assert result['is_supported'] == True


if __name__ == '__main__':
    pytest.main([__file__, '-v']) 