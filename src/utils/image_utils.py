import os
import logging
import tempfile
import base64
import requests
import signal
from typing import Dict, Optional, Tuple
from PIL import Image
import io

logger = logging.getLogger(__name__)

class TimeoutError(Exception):
    """Custom timeout exception"""
    pass

def timeout_handler(signum, frame):
    """Signal handler for timeout"""
    raise TimeoutError("Operation timed out")

class ImageProcessor:
    """Handles image download, processing, and cleanup for LINE Bot integration"""
    
    # Supported image formats
    SUPPORTED_FORMATS = {'JPEG', 'PNG', 'GIF', 'WEBP'}
    SUPPORTED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
    
    # Size limits (10MB max for LINE, 5MB recommended for Azure OpenAI)
    MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB in bytes
    MAX_DIMENSION = 2048  # Max width/height for processing
    
    def __init__(self):
        self.temp_files = []  # Track temporary files for cleanup
    
    def download_image_from_line(self, line_bot_api, message_id: str, timeout_seconds: int = 10) -> Optional[Dict]:
        """
        Download image from LINE Bot API using message ID with timeout
        
        Args:
            line_bot_api: LINE Bot API instance
            message_id: LINE message ID for the image
            timeout_seconds: Timeout for download operation
            
        Returns:
            Dict with success status and image data/error info
        """
        try:
            logger.info(f"Downloading image with message_id: {message_id} (timeout: {timeout_seconds}s)")
            
            # Set up timeout
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(timeout_seconds)
            
            try:
                # Get image content from LINE API
                image_content = line_bot_api.get_message_content(message_id)
                
                # Read image data
                image_data = b''
                for chunk in image_content.iter_content():
                    image_data += chunk
                
            finally:
                # Cancel timeout
                signal.alarm(0)
            
            # Validate file size
            if len(image_data) > self.MAX_FILE_SIZE:
                logger.warning(f"Image too large: {len(image_data)} bytes > {self.MAX_FILE_SIZE}")
                return {
                    'success': False,
                    'error': 'Image file too large (max 5MB)',
                    'error_code': 'FILE_TOO_LARGE'
                }
            
            # Validate and get image info
            validation_result = self._validate_image(image_data)
            if not validation_result['success']:
                return validation_result
            
            # Create temporary file
            temp_file_path = self._create_temp_file(image_data, validation_result['format'])
            
            return {
                'success': True,
                'image_data': image_data,
                'temp_file_path': temp_file_path,
                'format': validation_result['format'],
                'size': len(image_data),
                'dimensions': validation_result['dimensions']
            }
            
        except TimeoutError:
            logger.error(f"Timeout downloading image {message_id}")
            return {
                'success': False,
                'error': f'Image download timed out after {timeout_seconds} seconds',
                'error_code': 'DOWNLOAD_TIMEOUT'
            }
        except Exception as e:
            logger.error(f"Error downloading image {message_id}: {str(e)}")
            return {
                'success': False,
                'error': f'Failed to download image: {str(e)}',
                'error_code': 'DOWNLOAD_FAILED'
            }
    
    def _validate_image(self, image_data: bytes) -> Dict:
        """Validate image format and dimensions"""
        try:
            # Open image with PIL to validate
            image = Image.open(io.BytesIO(image_data))
            
            # Check format
            if image.format not in self.SUPPORTED_FORMATS:
                logger.warning(f"Unsupported image format: {image.format}")
                return {
                    'success': False,
                    'error': f'Unsupported image format: {image.format}. Supported: {", ".join(self.SUPPORTED_FORMATS)}',
                    'error_code': 'UNSUPPORTED_FORMAT'
                }
            
            # Get dimensions
            width, height = image.size
            logger.debug(f"Image dimensions: {width}x{height}, format: {image.format}")
            
            return {
                'success': True,
                'format': image.format,
                'dimensions': (width, height)
            }
            
        except Exception as e:
            logger.error(f"Error validating image: {str(e)}")
            return {
                'success': False,
                'error': f'Invalid image data: {str(e)}',
                'error_code': 'INVALID_IMAGE'
            }
    
    def _create_temp_file(self, image_data: bytes, image_format: str) -> str:
        """Create temporary file for image data"""
        try:
            # Determine file extension
            ext_map = {
                'JPEG': '.jpg',
                'PNG': '.png', 
                'GIF': '.gif',
                'WEBP': '.webp'
            }
            extension = ext_map.get(image_format, '.jpg')
            
            # Create temporary file
            temp_fd, temp_path = tempfile.mkstemp(suffix=extension, prefix='line_image_')
            
            # Write image data
            with os.fdopen(temp_fd, 'wb') as temp_file:
                temp_file.write(image_data)
            
            # Track for cleanup
            self.temp_files.append(temp_path)
            
            logger.debug(f"Created temporary file: {temp_path}")
            return temp_path
            
        except Exception as e:
            logger.error(f"Error creating temporary file: {str(e)}")
            raise
    
    def image_to_base64(self, image_data: bytes, image_format: str) -> str:
        """Convert image data to base64 string for GPT-4.1 vision API"""
        try:
            # Convert to base64
            base64_string = base64.b64encode(image_data).decode('utf-8')
            
            # Create data URL format for OpenAI API
            mime_type_map = {
                'JPEG': 'image/jpeg',
                'PNG': 'image/png',
                'GIF': 'image/gif',
                'WEBP': 'image/webp'
            }
            mime_type = mime_type_map.get(image_format, 'image/jpeg')
            
            logger.debug(f"Converted image to base64, format: {image_format}, size: {len(base64_string)} chars")
            return f"data:{mime_type};base64,{base64_string}"
            
        except Exception as e:
            logger.error(f"Error converting image to base64: {str(e)}")
            raise
    
    def preprocess_image_if_needed(self, image_data: bytes, max_dimension: int = None) -> bytes:
        """
        Preprocess image if it exceeds size limits
        
        Args:
            image_data: Original image data
            max_dimension: Maximum width/height (default: self.MAX_DIMENSION)
            
        Returns:
            Processed image data (may be same as input if no processing needed)
        """
        if max_dimension is None:
            max_dimension = self.MAX_DIMENSION
            
        try:
            image = Image.open(io.BytesIO(image_data))
            width, height = image.size
            
            # Check if resizing is needed
            if width <= max_dimension and height <= max_dimension:
                logger.debug("Image dimensions within limits, no preprocessing needed")
                return image_data
            
            # Calculate new dimensions maintaining aspect ratio
            if width > height:
                new_width = max_dimension
                new_height = int((height * max_dimension) / width)
            else:
                new_height = max_dimension
                new_width = int((width * max_dimension) / height)
            
            # Resize image
            resized_image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # Save to bytes
            output_buffer = io.BytesIO()
            # Preserve original format, default to JPEG for unsupported formats
            save_format = image.format if image.format in {'JPEG', 'PNG'} else 'JPEG'
            resized_image.save(output_buffer, format=save_format, quality=85, optimize=True)
            
            processed_data = output_buffer.getvalue()
            
            logger.info(f"Resized image from {width}x{height} to {new_width}x{new_height}, "
                       f"size reduced from {len(image_data)} to {len(processed_data)} bytes")
            
            return processed_data
            
        except Exception as e:
            logger.error(f"Error preprocessing image: {str(e)}")
            # Return original data if preprocessing fails
            return image_data
    
    def cleanup_temp_files(self):
        """Clean up all temporary files created by this instance"""
        cleaned_count = 0
        for temp_path in self.temp_files:
            try:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                    cleaned_count += 1
                    logger.debug(f"Cleaned up temporary file: {temp_path}")
            except Exception as e:
                logger.warning(f"Failed to cleanup temporary file {temp_path}: {str(e)}")
        
        self.temp_files.clear()
        if cleaned_count > 0:
            logger.info(f"Cleaned up {cleaned_count} temporary image files")
    
    def __del__(self):
        """Ensure cleanup on object destruction"""
        self.cleanup_temp_files()

# Convenience functions for backward compatibility
def download_image_from_line(line_bot_api, message_id: str) -> Optional[Dict]:
    """Convenience function to download image from LINE"""
    processor = ImageProcessor()
    return processor.download_image_from_line(line_bot_api, message_id)

def image_to_base64(image_data: bytes, image_format: str) -> str:
    """Convenience function to convert image to base64"""
    processor = ImageProcessor()
    return processor.image_to_base64(image_data, image_format)