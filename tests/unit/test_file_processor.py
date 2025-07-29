"""
Unit tests for FileProcessor class and file type detection
"""
import pytest
import sys
import os

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '../../src'))

from src.utils.file_utils import FileProcessor


class TestFileProcessor:
    """Test FileProcessor class functionality"""
    
    @pytest.fixture
    def file_processor(self):
        """Create FileProcessor instance for testing"""
        return FileProcessor()
    
    def test_file_processor_initialization(self, file_processor):
        """Test FileProcessor initializes correctly"""
        assert file_processor is not None
        assert file_processor.MAX_FILE_SIZE == 20 * 1024 * 1024  # 20MB
        assert hasattr(file_processor, 'SUPPORTED_EXTENSIONS')
    
    def test_supported_file_extensions(self, file_processor):
        """Test that all expected file types are supported"""
        supported = file_processor.SUPPORTED_EXTENSIONS
        
        # Documents
        assert '.pdf' in supported
        assert '.doc' in supported
        assert '.docx' in supported
        assert '.txt' in supported
        
        # Spreadsheets
        assert '.xls' in supported
        assert '.xlsx' in supported
        assert '.csv' in supported
        
        # Presentations
        assert '.ppt' in supported
        assert '.pptx' in supported
        
        # Code files
        assert '.py' in supported
        assert '.js' in supported
        assert '.html' in supported
        assert '.json' in supported
    
    def test_detect_file_type_from_filename(self, file_processor):
        """Test file type detection from filename"""
        # Test PDF
        result = file_processor.detect_file_type(None, "document.pdf")
        assert result['extension'] == '.pdf'
        assert result['is_supported'] == True
        
        # Test TXT
        result = file_processor.detect_file_type(None, "readme.txt")
        assert result['extension'] == '.txt'
        assert result['is_supported'] == True
        
        # Test unsupported
        result = file_processor.detect_file_type(None, "file.xyz")
        assert result['extension'] == '.xyz'
        assert result['is_supported'] == False
    
    def test_detect_file_type_from_content(self, file_processor):
        """Test file type detection from content (magic bytes)"""
        # Test PDF content
        pdf_content = b'%PDF-1.4\n%some pdf content'
        result = file_processor.detect_file_type(pdf_content, None)
        assert result['extension'] == '.pdf'
        assert result['mime_type'] == 'application/pdf'
        assert result['is_supported'] == True
        
        # Test PNG content
        png_content = b'\x89PNG\r\n\x1a\n' + b'fake png data'
        result = file_processor.detect_file_type(png_content, None)
        assert result['extension'] == '.png'
        assert result['mime_type'] == 'image/png'
        assert result['is_supported'] == True
        
        # Test text content
        text_content = b'Hello, this is a text file with some content.'
        result = file_processor.detect_file_type(text_content, None)
        assert result['extension'] == '.txt'
        assert result['mime_type'] == 'text/plain'
        assert result['is_supported'] == True
    
    def test_validate_file_type_supported(self, file_processor):
        """Test file type validation for supported files"""
        # Supported file
        result = file_processor.validate_file_type("document.pdf", b'%PDF-1.4')
        assert result['success'] == True
        assert 'file_type_info' in result
        
        # Another supported file
        result = file_processor.validate_file_type("data.csv", b'name,age,city\nJohn,25,NYC')
        assert result['success'] == True
    
    def test_validate_file_type_unsupported(self, file_processor):
        """Test file type validation for unsupported files"""
        # Unsupported file
        result = file_processor.validate_file_type("file.xyz", b'some content')
        assert result['success'] == False
        assert 'error' in result
        assert 'UNSUPPORTED_FILE_TYPE' == result['error_code']
        assert 'Supported extensions:' in result['error']
    
    def test_content_based_detection_priority(self, file_processor):
        """Test that content-based detection takes priority over filename"""
        # File with .txt extension but PDF content
        pdf_content = b'%PDF-1.4\n%actual pdf content'
        result = file_processor.detect_file_type(pdf_content, "mislabeled.txt")
        
        # Should detect as PDF based on content, not filename
        assert result['extension'] == '.pdf'
        assert result['mime_type'] == 'application/pdf'
        assert result['is_supported'] == True
    
    def test_unknown_file_type(self, file_processor):
        """Test handling of unknown file types"""
        # Binary data that doesn't match any signature
        unknown_content = b'\x00\x01\x02\x03\x04\x05'
        result = file_processor.detect_file_type(unknown_content, None)
        
        # Should not have detected type info
        assert result.get('extension') is None or result.get('extension') == ''
        assert result.get('is_supported') == False
    
    def test_empty_file_handling(self, file_processor):
        """Test handling of empty files"""
        # Empty content
        result = file_processor.detect_file_type(b'', "empty.txt")
        assert result['extension'] == '.txt'
        assert result['is_supported'] == True
        
        # No content, no filename
        result = file_processor.detect_file_type(None, None)
        assert result['is_supported'] == False


class TestFileTypeDetection:
    """Test specific file type detection scenarios"""
    
    @pytest.fixture
    def file_processor(self):
        return FileProcessor()
    
    def test_office_document_detection(self, file_processor):
        """Test detection of Office documents (ZIP-based)"""
        # Office documents start with ZIP signature
        zip_content = b'PK\x03\x04' + b'fake office content'
        result = file_processor.detect_file_type(zip_content, "document.docx")
        
        # Should detect extension from filename since ZIP is used for many formats
        assert result['extension'] == '.docx'
        assert result['is_supported'] == True
    
    def test_csv_file_detection(self, file_processor):
        """Test CSV file detection"""
        csv_content = b'Name,Age,City\nJohn,25,New York\nJane,30,Los Angeles'
        result = file_processor.detect_file_type(csv_content, "data.csv")
        
        assert result['extension'] == '.csv'
        assert result['is_supported'] == True
    
    def test_json_file_detection(self, file_processor):
        """Test JSON file detection"""
        json_content = b'{"name": "John", "age": 25, "city": "New York"}'
        result = file_processor.detect_file_type(json_content, "data.json")
        
        assert result['extension'] == '.json'
        assert result['is_supported'] == True
    
    def test_python_file_detection(self, file_processor):
        """Test Python file detection"""
        python_content = b'#!/usr/bin/env python3\nprint("Hello, World!")'
        result = file_processor.detect_file_type(python_content, "script.py")
        
        assert result['extension'] == '.py'
        assert result['is_supported'] == True


if __name__ == '__main__':
    pytest.main([__file__, '-v']) 