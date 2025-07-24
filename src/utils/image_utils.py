import os
import base64
import tempfile
import logging
from typing import Optional, Tuple, Dict, Any

logger = logging.getLogger(__name__)

# Supported image formats
SUPPORTED_FORMATS = {'.jpg', '.jpeg', '.png', '.gif'}
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB limit

def download_image_from_line(line_bot_api, message_id: str) -> Optional[Tuple[bytes, str]]:
    """
    Download image from LINE Bot API message content endpoint
    
    Args:
        line_bot_api: LINE Bot API instance
        message_id: Message ID from LINE webhook
        
    Returns:
        Tuple of (image_data, content_type) or None if failed
    """
    try:
        logger.debug(f"Downloading image for message ID: {message_id}")
        
        # Get message content from LINE API
        message_content = line_bot_api.get_message_content(message_id)
        
        # Read the content
        image_data = b""
        for chunk in message_content.iter_content():
            image_data += chunk
            
        # Check file size
        if len(image_data) > MAX_IMAGE_SIZE:
            logger.warning(f"Image too large: {len(image_data)} bytes (max: {MAX_IMAGE_SIZE})")
            return None
            
        # Try to determine content type from response headers
        content_type = getattr(message_content, 'headers', {}).get('content-type', 'image/jpeg')
        
        logger.info(f"Successfully downloaded image: {len(image_data)} bytes, type: {content_type}")
        return image_data, content_type
        
    except Exception as e:
        logger.error(f"Failed to download image {message_id}: {str(e)}")
        return None

def validate_image_format(image_data: bytes, content_type: str = "") -> bool:
    """
    Validate image format and basic integrity
    
    Args:
        image_data: Raw image bytes
        content_type: Content type from HTTP headers
        
    Returns:
        True if image is valid and supported
    """
    try:
        # Check if we have data
        if not image_data or len(image_data) < 10:
            return False
            
        # Check file size
        if len(image_data) > MAX_IMAGE_SIZE:
            logger.warning(f"Image too large: {len(image_data)} bytes")
            return False
            
        # Check magic bytes for common formats
        if image_data.startswith(b'\xff\xd8\xff'):  # JPEG
            return True
        elif image_data.startswith(b'\x89PNG\r\n\x1a\n'):  # PNG
            return True
        elif image_data.startswith(b'GIF87a') or image_data.startswith(b'GIF89a'):  # GIF
            return True
        elif 'image/' in content_type.lower():
            # Fallback to content-type if magic bytes don't match
            logger.debug(f"Accepting image based on content-type: {content_type}")
            return True
            
        logger.warning(f"Unsupported image format detected")
        return False
        
    except Exception as e:
        logger.error(f"Error validating image format: {str(e)}")
        return False

def image_to_base64(image_data: bytes, content_type: str = "image/jpeg") -> str:
    """
    Convert image data to base64 string for GPT-4 vision API
    
    Args:
        image_data: Raw image bytes
        content_type: MIME type of the image
        
    Returns:
        Base64 encoded string with data URL prefix
    """
    try:
        # Encode to base64
        base64_string = base64.b64encode(image_data).decode('utf-8')
        
        # Clean up content type
        if not content_type or not content_type.startswith('image/'):
            content_type = "image/jpeg"
            
        # Return data URL format
        return f"data:{content_type};base64,{base64_string}"
        
    except Exception as e:
        logger.error(f"Error converting image to base64: {str(e)}")
        raise

def create_temp_image_file(image_data: bytes, suffix: str = ".jpg") -> Optional[str]:
    """
    Create temporary file for image processing
    
    Args:
        image_data: Raw image bytes
        suffix: File extension
        
    Returns:
        Path to temporary file or None if failed
    """
    try:
        # Create temporary file
        temp_fd, temp_path = tempfile.mkstemp(suffix=suffix, prefix="line_image_")
        
        # Write image data
        with os.fdopen(temp_fd, 'wb') as temp_file:
            temp_file.write(image_data)
            
        logger.debug(f"Created temporary image file: {temp_path}")
        return temp_path
        
    except Exception as e:
        logger.error(f"Error creating temporary image file: {str(e)}")
        return None

def cleanup_temp_file(file_path: str) -> bool:
    """
    Clean up temporary image file
    
    Args:
        file_path: Path to temporary file
        
    Returns:
        True if successfully cleaned up
    """
    try:
        if file_path and os.path.exists(file_path):
            os.unlink(file_path)
            logger.debug(f"Cleaned up temporary file: {file_path}")
            return True
        return False
        
    except Exception as e:
        logger.error(f"Error cleaning up temporary file {file_path}: {str(e)}")
        return False

def get_image_metadata(image_data: bytes) -> Dict[str, Any]:
    """
    Extract basic metadata from image
    
    Args:
        image_data: Raw image bytes
        
    Returns:
        Dictionary with image metadata
    """
    try:
        metadata = {
            'size_bytes': len(image_data),
            'format': 'unknown'
        }
        
        # Determine format from magic bytes
        if image_data.startswith(b'\xff\xd8\xff'):
            metadata['format'] = 'jpeg'
        elif image_data.startswith(b'\x89PNG\r\n\x1a\n'):
            metadata['format'] = 'png'
        elif image_data.startswith(b'GIF87a') or image_data.startswith(b'GIF89a'):
            metadata['format'] = 'gif'
            
        return metadata
        
    except Exception as e:
        logger.error(f"Error extracting image metadata: {str(e)}")
        return {'size_bytes': 0, 'format': 'unknown'}

class ImageProcessor:
    """Context manager for handling image processing with automatic cleanup"""
    
    def __init__(self, line_bot_api, message_id: str):
        self.line_bot_api = line_bot_api
        self.message_id = message_id
        self.temp_files = []
        self.image_data = None
        self.content_type = None
        
    def __enter__(self):
        """Download and prepare image for processing"""
        try:
            # Download image from LINE
            result = download_image_from_line(self.line_bot_api, self.message_id)
            if not result:
                raise Exception("Failed to download image from LINE")
                
            self.image_data, self.content_type = result
            
            # Validate image
            if not validate_image_format(self.image_data, self.content_type):
                raise Exception("Invalid or unsupported image format")
                
            return self
            
        except Exception as e:
            logger.error(f"Error preparing image processor: {str(e)}")
            raise
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Clean up temporary files"""
        for temp_file in self.temp_files:
            cleanup_temp_file(temp_file)
        self.temp_files.clear()
        
    def to_base64(self) -> str:
        """Convert image to base64 for API"""
        if not self.image_data:
            raise Exception("No image data available")
        return image_to_base64(self.image_data, self.content_type or "image/jpeg")
        
    def get_metadata(self) -> Dict[str, Any]:
        """Get image metadata"""
        if not self.image_data:
            return {'size_bytes': 0, 'format': 'unknown'}
        return get_image_metadata(self.image_data)
        
    def create_temp_file(self, suffix: str = None) -> str:
        """Create temporary file and track for cleanup"""
        if not self.image_data:
            raise Exception("No image data available")
            
        if not suffix:
            # Determine suffix from content type
            content_type_lower = (self.content_type or "").lower()
            if 'png' in content_type_lower:
                suffix = '.png'
            elif 'gif' in content_type_lower:
                suffix = '.gif'
            else:
                suffix = '.jpg'
                
        temp_path = create_temp_image_file(self.image_data, suffix)
        if temp_path:
            self.temp_files.append(temp_path)
            return temp_path
        else:
            raise Exception("Failed to create temporary image file")