"""
Integration tests for multiple file types support
"""
import pytest
import sys
import os

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '../../src'))

from src.utils.file_utils import FileProcessor


class TestDocumentFileTypes:
    """Test document file type support"""
    
    @pytest.fixture
    def file_processor(self):
        return FileProcessor()
    
    def test_pdf_files(self, file_processor):
        """Test PDF file detection and validation"""
        # Standard PDF header
        pdf_content = b'%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog'
        
        result = file_processor.detect_file_type(pdf_content, "document.pdf")
        assert result['extension'] == '.pdf'
        assert result['mime_type'] == 'application/pdf'
        assert result['is_supported'] == True
        
        validation = file_processor.validate_file_type("report.pdf", pdf_content)
        assert validation['success'] == True
    
    def test_word_documents(self, file_processor):
        """Test Word document detection"""
        # Modern Word documents are ZIP-based
        docx_content = b'PK\x03\x04' + b'[Content_Types].xml'
        
        result = file_processor.detect_file_type(docx_content, "document.docx")
        assert result['extension'] == '.docx'
        assert result['is_supported'] == True
        
        # Legacy DOC format would need different detection
        validation = file_processor.validate_file_type("legacy.doc", b"some content")
        assert validation['success'] == True  # Based on extension
    
    def test_text_files(self, file_processor):
        """Test various text file formats"""
        text_files = [
            ("readme.txt", b"This is a text file with some content."),
            ("document.md", b"# Markdown Document\n\nThis is **bold** text."),
            ("config.rtf", b"{\\rtf1\\ansi\\deff0 {\\fonttbl {\\f0 Times New Roman;}}"),
        ]
        
        for filename, content in text_files:
            result = file_processor.detect_file_type(content, filename)
            assert result['is_supported'] == True, f"Failed for {filename}"
            
            validation = file_processor.validate_file_type(filename, content)
            assert validation['success'] == True, f"Validation failed for {filename}"


class TestSpreadsheetFileTypes:
    """Test spreadsheet file type support"""
    
    @pytest.fixture
    def file_processor(self):
        return FileProcessor()
    
    def test_excel_files(self, file_processor):
        """Test Excel file detection"""
        # Modern Excel files are ZIP-based
        xlsx_content = b'PK\x03\x04' + b'xl/workbook.xml'
        
        result = file_processor.detect_file_type(xlsx_content, "spreadsheet.xlsx")
        assert result['extension'] == '.xlsx'
        assert result['is_supported'] == True
        
        # Legacy XLS format
        validation = file_processor.validate_file_type("legacy.xls", b"some content")
        assert validation['success'] == True
    
    def test_csv_files(self, file_processor):
        """Test CSV file detection and validation"""
        csv_content = b'Name,Age,City,Country\nJohn Doe,30,New York,USA\nJane Smith,25,London,UK'
        
        result = file_processor.detect_file_type(csv_content, "data.csv")
        assert result['extension'] == '.csv'
        assert result['is_supported'] == True
        
        # Test with different delimiters
        tsv_content = b'Name\tAge\tCity\nJohn\t30\tNYC\nJane\t25\tLondon'
        result = file_processor.detect_file_type(tsv_content, "data.tsv")
        assert result['extension'] == '.tsv'
        assert result['is_supported'] == True
    
    def test_csv_edge_cases(self, file_processor):
        """Test CSV files with various formats"""
        csv_variants = [
            ("simple.csv", b'a,b,c\n1,2,3'),
            ("quoted.csv", b'"Name","Value","Description"\n"John","123","Test"'),
            ("with_newlines.csv", b'col1,col2\n"Line 1\nLine 2","Value"'),
            ("empty_fields.csv", b'a,b,c\n1,,3\n,2,'),
        ]
        
        for filename, content in csv_variants:
            validation = file_processor.validate_file_type(filename, content)
            assert validation['success'] == True, f"Failed for {filename}"


class TestPresentationFileTypes:
    """Test presentation file type support"""
    
    @pytest.fixture
    def file_processor(self):
        return FileProcessor()
    
    def test_powerpoint_files(self, file_processor):
        """Test PowerPoint file detection"""
        # Modern PowerPoint files are ZIP-based
        pptx_content = b'PK\x03\x04' + b'ppt/presentation.xml'
        
        result = file_processor.detect_file_type(pptx_content, "presentation.pptx")
        assert result['extension'] == '.pptx'
        assert result['is_supported'] == True
        
        # Legacy PPT format
        validation = file_processor.validate_file_type("legacy.ppt", b"some content")
        assert validation['success'] == True


class TestCodeFileTypes:
    """Test code file type support"""
    
    @pytest.fixture
    def file_processor(self):
        return FileProcessor()
    
    def test_python_files(self, file_processor):
        """Test Python file detection"""
        python_files = [
            ("script.py", b'#!/usr/bin/env python3\nprint("Hello, World!")\n'),
            ("module.py", b'def function():\n    return "result"\n'),
            ("class.py", b'class MyClass:\n    def __init__(self):\n        pass'),
        ]
        
        for filename, content in python_files:
            result = file_processor.detect_file_type(content, filename)
            assert result['extension'] == '.py'
            assert result['is_supported'] == True
            
            validation = file_processor.validate_file_type(filename, content)
            assert validation['success'] == True
    
    def test_javascript_files(self, file_processor):
        """Test JavaScript file detection"""
        js_files = [
            ("script.js", b'function hello() {\n    console.log("Hello!");\n}'),
            ("module.js", b'const express = require("express");\nconst app = express();'),
            ("app.js", b'document.addEventListener("DOMContentLoaded", function() {});'),
        ]
        
        for filename, content in js_files:
            result = file_processor.detect_file_type(content, filename)
            assert result['extension'] == '.js'
            assert result['is_supported'] == True
    
    def test_web_files(self, file_processor):
        """Test web development file types"""
        web_files = [
            ("index.html", b'<!DOCTYPE html>\n<html><head><title>Test</title></head></html>'),
            ("styles.css", b'body { margin: 0; padding: 0; }\n.class { color: red; }'),
            ("data.json", b'{"name": "John", "age": 30, "city": "New York"}'),
            ("config.xml", b'<?xml version="1.0"?>\n<root><item>value</item></root>'),
        ]
        
        for filename, content in web_files:
            result = file_processor.detect_file_type(content, filename)
            extension = os.path.splitext(filename.lower())[1]
            assert result['extension'] == extension
            assert result['is_supported'] == True
    
    def test_database_files(self, file_processor):
        """Test database-related file types"""
        db_files = [
            ("query.sql", b'SELECT * FROM users WHERE age > 18;\nINSERT INTO logs VALUES ("test");'),
            ("schema.sql", b'CREATE TABLE users (id INT, name VARCHAR(50));\nCREATE INDEX idx_name ON users(name);'),
        ]
        
        for filename, content in db_files:
            result = file_processor.detect_file_type(content, filename)
            assert result['extension'] == '.sql'
            assert result['is_supported'] == True


class TestDataFileTypes:
    """Test data file type support"""
    
    @pytest.fixture
    def file_processor(self):
        return FileProcessor()
    
    def test_json_files(self, file_processor):
        """Test JSON file variations"""
        json_files = [
            ("simple.json", b'{"key": "value", "number": 42}'),
            ("array.json", b'[{"id": 1, "name": "John"}, {"id": 2, "name": "Jane"}]'),
            ("nested.json", b'{"user": {"profile": {"name": "John", "settings": {"theme": "dark"}}}}'),
            ("config.json", b'{\n  "version": "1.0",\n  "features": ["auth", "api"]\n}'),
        ]
        
        for filename, content in json_files:
            result = file_processor.detect_file_type(content, filename)
            assert result['extension'] == '.json'
            assert result['is_supported'] == True
    
    def test_yaml_files(self, file_processor):
        """Test YAML file detection"""
        yaml_files = [
            ("config.yaml", b'version: 1.0\nservices:\n  - name: web\n    port: 8080'),
            ("docker.yml", b'version: "3"\nservices:\n  app:\n    image: nginx'),
        ]
        
        for filename, content in yaml_files:
            result = file_processor.detect_file_type(content, filename)
            extension = os.path.splitext(filename.lower())[1]
            assert result['extension'] == extension
            assert result['is_supported'] == True
    
    def test_log_files(self, file_processor):
        """Test log file detection"""
        log_content = b'2024-01-15 10:30:00 INFO Starting application\n2024-01-15 10:30:01 DEBUG Loading configuration'
        
        result = file_processor.detect_file_type(log_content, "application.log")
        assert result['extension'] == '.log'
        assert result['is_supported'] == True
        
        # JSONL (JSON Lines) format
        jsonl_content = b'{"timestamp": "2024-01-15", "level": "info", "message": "test"}\n{"timestamp": "2024-01-15", "level": "error", "message": "error"}'
        result = file_processor.detect_file_type(jsonl_content, "events.jsonl")
        assert result['extension'] == '.jsonl'
        assert result['is_supported'] == True


class TestImageFileTypes:
    """Test image file type support (for completeness)"""
    
    @pytest.fixture
    def file_processor(self):
        return FileProcessor()
    
    def test_common_image_formats(self, file_processor):
        """Test common image format detection"""
        image_files = [
            ("photo.jpg", b'\xff\xd8\xff\xe0', 'image/jpeg'),
            ("graphic.png", b'\x89PNG\r\n\x1a\n', 'image/png'),
            ("animation.gif", b'GIF87a', 'image/gif'),
            ("modern.webp", b'RIFF', None),  # WebP would need more complex detection
        ]
        
        for filename, signature, expected_mime in image_files:
            content = signature + b'fake image data'
            result = file_processor.detect_file_type(content, filename)
            assert result['is_supported'] == True
            
            if expected_mime:
                assert result['mime_type'] == expected_mime


class TestUnsupportedFileTypes:
    """Test handling of unsupported file types"""
    
    @pytest.fixture
    def file_processor(self):
        return FileProcessor()
    
    def test_unsupported_extensions(self, file_processor):
        """Test files with unsupported extensions"""
        unsupported_files = [
            "archive.zip",
            "executable.exe", 
            "movie.mp4",
            "audio.mp3",
            "unknown.xyz",
            "binary.bin"
        ]
        
        for filename in unsupported_files:
            result = file_processor.validate_file_type(filename, b"some content")
            assert result['success'] == False
            assert 'UNSUPPORTED_FILE_TYPE' in result['error_code']
            assert 'Supported extensions:' in result['error']
    
    def test_malicious_filename_attempts(self, file_processor):
        """Test handling of potentially malicious filenames"""
        malicious_names = [
            "../../../etc/passwd",
            "file\\with\\backslashes",
            "file|with|pipes",
            "file<script>alert('xss')</script>.txt",
        ]
        
        for filename in malicious_names:
            # Should still process based on detected extension
            try:
                result = file_processor.detect_file_type(b"content", filename)
                # The function should handle these gracefully
                assert isinstance(result, dict)
            except Exception as e:
                pytest.fail(f"Failed to handle filename {filename}: {e}")


if __name__ == '__main__':
    pytest.main([__file__, '-v']) 