import logging
import signal
import mimetypes
import os
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class TimeoutError(Exception):
    """Custom timeout exception for file operations"""
    pass


def timeout_handler(signum, frame):
    raise TimeoutError("Operation timed out")


class FileProcessor:
    """Utility for downloading files from LINE"""

    MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB
    
    # Common file types supported by OpenAI API
    SUPPORTED_EXTENSIONS = {
        # Documents
        '.pdf', '.doc', '.docx', '.txt', '.rtf', '.md',
        # Spreadsheets
        '.xls', '.xlsx', '.csv', '.tsv',
        # Presentations
        '.ppt', '.pptx',
        # Code files
        '.py', '.js', '.html', '.css', '.json', '.xml', '.sql', '.yaml', '.yml',
        # Data files
        '.log', '.jsonl',
        # Images (already supported via ImageMessage but included for completeness)
        '.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff', '.tif'
    }

    def download_file_from_line(self, line_bot_api, message_id: str, timeout_seconds: int = 10) -> Optional[Dict]:
        """Download a file from LINE using the message ID"""
        try:
            logger.info(f"Downloading file with message_id: {message_id} (timeout: {timeout_seconds}s)")

            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(timeout_seconds)

            try:
                file_content = line_bot_api.get_message_content(message_id)
                file_data = b"".join(chunk for chunk in file_content.iter_content())
            finally:
                signal.alarm(0)

            if len(file_data) > self.MAX_FILE_SIZE:
                logger.warning(f"File too large: {len(file_data)} bytes > {self.MAX_FILE_SIZE}")
                return {
                    "success": False,
                    "error": "File too large (max 20MB)",
                    "error_code": "FILE_TOO_LARGE",
                }

            # Detect file type (this will be enhanced with actual file content analysis)
            file_type_info = self.detect_file_type(file_data, None)
            
            return {
                "success": True, 
                "file_data": file_data, 
                "size": len(file_data),
                "file_type": file_type_info.get("mime_type"),
                "extension": file_type_info.get("extension")
            }
        except TimeoutError:
            logger.error(f"Timeout downloading file {message_id}")
            return {
                "success": False,
                "error": f"File download timed out after {timeout_seconds} seconds",
                "error_code": "DOWNLOAD_TIMEOUT",
            }
        except Exception as e:
            logger.error(f"Error downloading file {message_id}: {str(e)}")
            return {
                "success": False,
                "error": f"Failed to download file: {str(e)}",
                "error_code": "DOWNLOAD_FAILED",
            }
    
    def detect_file_type(self, file_data: bytes, file_name: str = None) -> Dict:
        """Detect file type from file data and/or filename"""
        result = {"mime_type": None, "extension": None, "is_supported": False}
        
        # Try to detect from file name first if available
        if file_name:
            mime_type, _ = mimetypes.guess_type(file_name)
            if mime_type:
                result["mime_type"] = mime_type
                
            # Extract extension
            extension = os.path.splitext(file_name.lower())[1]
            if extension:
                result["extension"] = extension
                result["is_supported"] = extension in self.SUPPORTED_EXTENSIONS
        
        # Basic file signature detection (magic bytes)
        if file_data:
            file_type_from_content = self._detect_from_content(file_data)
            if file_type_from_content:
                # Prefer content-based detection over filename
                result.update(file_type_from_content)
        
        return result
    
    def _detect_from_content(self, file_data: bytes) -> Dict:
        """Detect file type from file content using magic bytes"""
        if not file_data:
            return {}
            
        # Common file signatures (magic bytes)
        signatures = {
            b'%PDF-': {'mime_type': 'application/pdf', 'extension': '.pdf'},
            b'PK\x03\x04': {'mime_type': 'application/zip', 'extension': '.zip'},  # Also .docx, .xlsx, .pptx
            b'\xff\xd8\xff': {'mime_type': 'image/jpeg', 'extension': '.jpg'},
            b'\x89PNG': {'mime_type': 'image/png', 'extension': '.png'},
            b'GIF8': {'mime_type': 'image/gif', 'extension': '.gif'},
        }
        
        for signature, file_info in signatures.items():
            if file_data.startswith(signature):
                result = file_info.copy()
                result["is_supported"] = result["extension"] in self.SUPPORTED_EXTENSIONS
                return result
        
        # If text-based, assume it's a text file
        try:
            file_data[:1024].decode('utf-8')
            return {
                'mime_type': 'text/plain', 
                'extension': '.txt',
                'is_supported': '.txt' in self.SUPPORTED_EXTENSIONS
            }
        except UnicodeDecodeError:
            pass
        
        return {}
    
    def validate_file_type(self, file_name: str = None, file_data: bytes = None) -> Dict:
        """Validate if file type is supported"""
        file_type_info = self.detect_file_type(file_data, file_name)
        
        if not file_type_info.get("is_supported", False):
            supported_list = ", ".join(sorted(self.SUPPORTED_EXTENSIONS))
            return {
                "success": False,
                "error": f"Unsupported file type. Supported extensions: {supported_list}",
                "error_code": "UNSUPPORTED_FILE_TYPE",
                "detected_type": file_type_info
            }
        
        return {
            "success": True,
            "file_type_info": file_type_info
        }
