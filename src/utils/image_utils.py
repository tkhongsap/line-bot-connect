import os
import logging
import tempfile
import base64
import requests
import signal
import threading
import glob
import time
from typing import Dict, Optional, Tuple, List
from datetime import datetime, timedelta
from PIL import Image
import io
from src.utils.memory_monitor import get_memory_monitor, MemoryStats
from src.utils.connection_pool import connection_pool_manager, ExponentialBackoff

# Global temp file tracking for memory-aware cleanup
_global_temp_files = []
_temp_files_lock = threading.RLock()
_max_temp_files = 100  # Maximum number of temp files to track
_memory_monitor_registered = False

# Enable comprehensive mobile image format support
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
    logger = logging.getLogger(__name__)
    logger.info("HEIC/HEIF image format support enabled")
except ImportError:
    logger = logging.getLogger(__name__)
    logger.warning("HEIC/HEIF support not available - install pillow-heif for Samsung screenshot support")
except Exception as e:
    logger = logging.getLogger(__name__)
    logger.warning(f"Error enabling HEIC/HEIF support: {e}")

# Enable AVIF support (modern Android devices)
try:
    import pillow_avif_plugin
    logger.info("AVIF image format support enabled")
except ImportError:
    logger.warning("AVIF support not available - install pillow-avif-plugin for modern Android support")
except Exception as e:
    logger.warning(f"Error enabling AVIF support: {e}")

# Enable JPEG XL support (emerging format)
try:
    import pillow_jxl_plugin
    logger.info("JPEG XL image format support enabled")
except ImportError:
    logger.warning("JPEG XL support not available - install pillow-jxl-plugin for cutting-edge format support")
except Exception as e:
    logger.warning(f"Error enabling JPEG XL support: {e}")

logger = logging.getLogger(__name__)


def _register_memory_cleanup():
    """Register memory cleanup callbacks with the global memory monitor."""
    global _memory_monitor_registered
    
    if _memory_monitor_registered:
        return
    
    try:
        memory_monitor = get_memory_monitor()
        memory_monitor.add_cleanup_callback(_memory_cleanup_callback)
        _memory_monitor_registered = True
        logger.info("Registered image processing memory cleanup callbacks")
    except Exception as e:
        logger.warning(f"Failed to register memory cleanup callbacks: {e}")


def _memory_cleanup_callback(cleanup_level: str, memory_stats: MemoryStats):
    """
    Callback function for memory monitor to clean up temp files.
    
    Args:
        cleanup_level: Level of cleanup ('light', 'aggressive', 'emergency')
        memory_stats: Current memory statistics
    """
    try:
        if cleanup_level == "light":
            _cleanup_old_temp_files(max_age_minutes=30)
        elif cleanup_level == "aggressive":
            _cleanup_old_temp_files(max_age_minutes=15)
        elif cleanup_level == "emergency":
            _cleanup_old_temp_files(max_age_minutes=5)
            _cleanup_excess_temp_files(max_files=20)
        
        logger.info(f"Completed {cleanup_level} temp file cleanup")
        
    except Exception as e:
        logger.error(f"Error during {cleanup_level} temp file cleanup: {e}")


def _cleanup_old_temp_files(max_age_minutes: int):
    """Clean up temp files older than specified minutes."""
    with _temp_files_lock:
        cutoff_time = datetime.now() - timedelta(minutes=max_age_minutes)
        files_to_remove = []
        cleanup_count = 0
        
        for file_info in _global_temp_files[:]:
            if file_info['created_at'] < cutoff_time:
                file_path = file_info['path']
                try:
                    if os.path.exists(file_path):
                        os.unlink(file_path)
                        cleanup_count += 1
                    files_to_remove.append(file_info)
                except OSError as e:
                    logger.warning(f"Failed to remove old temp file {file_path}: {e}")
                    files_to_remove.append(file_info)  # Remove from tracking anyway
        
        # Remove from tracking list
        for file_info in files_to_remove:
            if file_info in _global_temp_files:
                _global_temp_files.remove(file_info)
        
        if cleanup_count > 0:
            logger.info(f"Cleaned up {cleanup_count} old temp files (age > {max_age_minutes} minutes)")


def _cleanup_excess_temp_files(max_files: int):
    """Clean up excess temp files when limit is exceeded."""
    with _temp_files_lock:
        if len(_global_temp_files) <= max_files:
            return
        
        # Sort by creation time (oldest first)
        _global_temp_files.sort(key=lambda x: x['created_at'])
        
        # Remove oldest files beyond the limit
        files_to_remove = _global_temp_files[:-max_files]
        cleanup_count = 0
        
        for file_info in files_to_remove:
            file_path = file_info['path']
            try:
                if os.path.exists(file_path):
                    os.unlink(file_path)
                    cleanup_count += 1
            except OSError as e:
                logger.warning(f"Failed to remove excess temp file {file_path}: {e}")
        
        # Keep only the most recent files
        _global_temp_files[:] = _global_temp_files[-max_files:]
        
        if cleanup_count > 0:
            logger.warning(f"Emergency cleanup: removed {cleanup_count} excess temp files")


def _track_temp_file(file_path: str):
    """Add temp file to global tracking system."""
    with _temp_files_lock:
        file_info = {
            'path': file_path,
            'created_at': datetime.now(),
            'process_id': os.getpid()
        }
        
        _global_temp_files.append(file_info)
        
        # Prevent memory leaks from tracking too many files
        if len(_global_temp_files) > _max_temp_files:
            # Remove oldest tracking entries (but don't delete the files)
            _global_temp_files[:] = _global_temp_files[-_max_temp_files:]
        
        logger.debug(f"Tracking temp file: {file_path} (total tracked: {len(_global_temp_files)})")


def _untrack_temp_file(file_path: str):
    """Remove temp file from global tracking system."""
    with _temp_files_lock:
        _global_temp_files[:] = [
            file_info for file_info in _global_temp_files 
            if file_info['path'] != file_path
        ]
        logger.debug(f"Untracked temp file: {file_path}")


def get_temp_file_stats() -> Dict:
    """Get statistics about tracked temp files."""
    with _temp_files_lock:
        if not _global_temp_files:
            return {
                'total_tracked': 0,
                'oldest_file_age_minutes': 0,
                'newest_file_age_minutes': 0,
                'memory_monitor_registered': _memory_monitor_registered
            }
        
        now = datetime.now()
        ages_minutes = [
            (now - file_info['created_at']).total_seconds() / 60
            for file_info in _global_temp_files
        ]
        
        return {
            'total_tracked': len(_global_temp_files),
            'oldest_file_age_minutes': max(ages_minutes),
            'newest_file_age_minutes': min(ages_minutes),
            'average_age_minutes': sum(ages_minutes) / len(ages_minutes),
            'memory_monitor_registered': _memory_monitor_registered
        }

class TimeoutError(Exception):
    """Custom timeout exception"""
    pass

def timeout_handler(signum, frame):
    """Signal handler for timeout"""
    raise TimeoutError("Operation timed out")

class ImageProcessor:
    """Handles image download, processing, and cleanup for LINE Bot integration"""
    
    # Supported image formats (comprehensive mobile device support)
    SUPPORTED_FORMATS = {'JPEG', 'PNG', 'GIF', 'WEBP', 'HEIC', 'HEIF', 'BMP', 'TIFF', 'AVIF', 'JXL', 'ICO'}
    SUPPORTED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.heic', '.heif', '.bmp', '.tiff', '.tif', '.avif', '.jxl', '.ico'}
    
    # Size limits (optimized for mobile screenshots)
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB for mobile screenshots (increased from 5MB)
    MAX_DIMENSION = 4096  # 4K resolution support for high-DPI mobile screens
    MOBILE_DIMENSION_THRESHOLD = 2048  # Threshold for aggressive mobile optimization
    
    def __init__(self):
        self.temp_files = []  # Track temporary files for cleanup
        self._cleanup_completed = False  # Track cleanup state
        
        # Register global memory cleanup on first initialization
        _register_memory_cleanup()
        
        # Set up connection pooling for image downloads
        self._setup_image_connection_pools()
        
        # Download metrics
        self.download_metrics = {
            'total_downloads': 0,
            'successful_downloads': 0,
            'failed_downloads': 0,
            'avg_download_time': 0.0,
            'total_bytes_downloaded': 0
        }
    
    def _setup_image_connection_pools(self):
        """Set up connection pools optimized for image downloads."""
        # Create session for LINE content API (image downloads) if not already created
        try:
            # Check if session already exists
            if 'line_content_api' not in connection_pool_manager.pools:
                self.image_session = connection_pool_manager.create_session_with_pooling(
                    name="line_content_api",
                    base_url="https://api-data.line.me",
                    pool_maxsize=8,  # Smaller pool for image downloads
                    max_retries=2,
                    enable_keep_alive=True
                )
                logger.info("Created connection pool for image downloads")
            else:
                # Use existing session
                self.image_session = connection_pool_manager.pools['line_content_api']['session']
                logger.debug("Using existing connection pool for image downloads")
        except Exception as e:
            logger.warning(f"Failed to set up image connection pool: {e}")
            self.image_session = None
    
    def __enter__(self):
        """Context manager entry point"""
        logger.debug("ImageProcessor context manager entered")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit point - ensures cleanup even if exceptions occur"""
        try:
            if exc_type:
                logger.warning(f"ImageProcessor exiting due to exception: {exc_type.__name__}: {exc_val}")
            else:
                logger.debug("ImageProcessor context manager exiting normally")
            
            # Always attempt cleanup
            self.cleanup_temp_files()
            
        except Exception as cleanup_error:
            logger.error(f"Error during ImageProcessor cleanup in __exit__: {cleanup_error}")
            # Don't suppress the original exception, just log the cleanup error
        
        # Return False to propagate any exception that occurred in the with block
        return False
    
    def download_image_from_line(self, line_bot_api, message_id: str, timeout_seconds: int = 10) -> Optional[Dict]:
        """
        Download image from LINE Bot API using message ID with connection pooling and timeout
        
        Args:
            line_bot_api: LINE Bot API instance
            message_id: LINE message ID for the image
            timeout_seconds: Timeout for download operation
            
        Returns:
            Dict with success status and image data/error info
        """
        start_time = time.time()
        
        try:
            logger.info(f"Downloading image with message_id: {message_id} (timeout: {timeout_seconds}s, pooled: {self.image_session is not None})")
            
            # Update download metrics
            self.download_metrics['total_downloads'] += 1
            
            # Define download operation for connection pooling
            def download_operation():
                # Set up timeout
                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(timeout_seconds)
                
                try:
                    # Get image content from LINE API
                    image_content = line_bot_api.get_message_content(message_id)
                    
                    # Read image data with streaming for better memory management
                    image_data = b''
                    chunk_size = 8192  # 8KB chunks for better memory usage
                    
                    for chunk in image_content.iter_content(chunk_size=chunk_size):
                        if chunk:  # Filter out keep-alive chunks
                            image_data += chunk
                            
                            # Check size limit during download to avoid memory issues
                            if len(image_data) > self.MAX_FILE_SIZE:
                                raise ValueError(f"Image too large: {len(image_data)} bytes > {self.MAX_FILE_SIZE}")
                    
                    return image_data
                    
                finally:
                    # Cancel timeout
                    signal.alarm(0)
            
            # Execute download with connection pooling and retry logic
            if self.image_session:
                backoff = ExponentialBackoff(base_delay=0.5, max_delay=5.0, multiplier=1.5)
                # Ensure max_attempts is an integer to prevent type errors
                image_data = connection_pool_manager.execute_with_retry(
                    "line_content_api",
                    download_operation,
                    max_attempts=int(2),  # Explicitly cast to int
                    backoff=backoff
                )
            else:
                # Fallback to direct download without pooling
                logger.warning("No connection pool available, using direct download")
                image_data = download_operation()
            
            # Validate and get image info
            validation_result = self._validate_image(image_data)
            if not validation_result['success']:
                self.download_metrics['failed_downloads'] += 1
                return validation_result
            
            # Create temporary file
            temp_file_path = self._create_temp_file(image_data, validation_result['format'])
            
            # Update success metrics
            download_time = time.time() - start_time
            self.download_metrics['successful_downloads'] += 1
            self.download_metrics['total_bytes_downloaded'] += len(image_data)
            self.download_metrics['avg_download_time'] = (
                (self.download_metrics['avg_download_time'] * (self.download_metrics['successful_downloads'] - 1) + download_time) /
                self.download_metrics['successful_downloads']
            )
            
            logger.info(
                f"Image downloaded successfully with connection pooling",
                extra={
                    'message_id': message_id,
                    'size_bytes': len(image_data),
                    'format': validation_result['format'],
                    'download_time': download_time,
                    'pooled': self.image_session is not None
                }
            )
            
            return {
                'success': True,
                'image_data': image_data,
                'temp_file_path': temp_file_path,
                'format': validation_result['format'],
                'size': len(image_data),
                'dimensions': validation_result['dimensions'],
                'download_time': download_time,
                'pooled': self.image_session is not None
            }
            
        except TimeoutError:
            self.download_metrics['failed_downloads'] += 1
            logger.error(f"Timeout downloading image {message_id} with connection pooling")
            return {
                'success': False,
                'error': f'Image download timed out after {timeout_seconds} seconds',
                'error_code': 'DOWNLOAD_TIMEOUT',
                'download_time': time.time() - start_time
            }
        except ValueError as e:
            # Handle size limit errors specifically
            self.download_metrics['failed_downloads'] += 1
            logger.warning(f"Image size validation failed for {message_id}: {str(e)}")
            return {
                'success': False,
                'error': 'Image file too large (max 10MB)',
                'error_code': 'FILE_TOO_LARGE',
                'download_time': time.time() - start_time
            }
        except Exception as e:
            self.download_metrics['failed_downloads'] += 1
            error_type = type(e).__name__
            logger.error(f"Error downloading image {message_id} with connection pooling: {error_type}: {str(e)}")
            
            # More specific error messages based on exception type
            if "connection" in str(e).lower():
                error_msg = "Connection error - please check your network"
                error_code = "CONNECTION_ERROR"
            elif "timeout" in str(e).lower():
                error_msg = "Request timed out - please try again"
                error_code = "REQUEST_TIMEOUT"
            elif "permission" in str(e).lower() or "forbidden" in str(e).lower():
                error_msg = "Access denied - unable to download image"
                error_code = "ACCESS_DENIED"
            elif "not found" in str(e).lower():
                error_msg = "Image not found or expired"
                error_code = "IMAGE_NOT_FOUND"
            else:
                error_msg = f'Failed to download image: {str(e)}'
                error_code = 'DOWNLOAD_FAILED'
            
            return {
                'success': False,
                'error': error_msg,
                'error_code': error_code,
                'error_type': error_type,
                'download_time': time.time() - start_time,
                'debug_info': {
                    'message_id': message_id,
                    'pooled': self.image_session is not None,
                    'timeout_seconds': timeout_seconds
                }
            }
    
    def get_download_metrics(self) -> Dict:
        """Get image download metrics."""
        pool_metrics = connection_pool_manager.get_metrics()
        
        # Filter for image-related pools
        image_pools = {k: v for k, v in pool_metrics.get('pools', {}).items() if 'content' in k}
        
        return {
            'download_metrics': self.download_metrics,
            'connection_pools': image_pools,
            'pool_health': {k: v for k, v in pool_metrics.get('health', {}).items() if 'content' in k},
            'temp_file_stats': get_temp_file_stats()
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
            # Determine file extension (comprehensive mobile support)
            ext_map = {
                'JPEG': '.jpg',
                'PNG': '.png', 
                'GIF': '.gif',
                'WEBP': '.webp',
                'HEIC': '.heic',
                'HEIF': '.heif',
                'BMP': '.bmp',
                'TIFF': '.tiff',
                'AVIF': '.avif',
                'JXL': '.jxl',
                'ICO': '.ico'
            }
            extension = ext_map.get(image_format, '.jpg')
            
            # Create temporary file
            temp_fd, temp_path = tempfile.mkstemp(suffix=extension, prefix='line_image_')
            
            # Write image data
            with os.fdopen(temp_fd, 'wb') as temp_file:
                temp_file.write(image_data)
            
            # Track for cleanup (both local and global)
            self.temp_files.append(temp_path)
            _track_temp_file(temp_path)
            
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
            
            # Create data URL format for OpenAI API (comprehensive mobile support)
            mime_type_map = {
                'JPEG': 'image/jpeg',
                'PNG': 'image/png',
                'GIF': 'image/gif',
                'WEBP': 'image/webp',
                'HEIC': 'image/heic',
                'HEIF': 'image/heif',
                'BMP': 'image/bmp',
                'TIFF': 'image/tiff',
                'AVIF': 'image/avif',
                'JXL': 'image/jxl',
                'ICO': 'image/x-icon'
            }
            mime_type = mime_type_map.get(image_format, 'image/jpeg')
            
            logger.debug(f"Converted image to base64, format: {image_format}, size: {len(base64_string)} chars")
            return f"data:{mime_type};base64,{base64_string}"
            
        except Exception as e:
            logger.error(f"Error converting image to base64: {str(e)}")
            raise
    
    def preprocess_image_if_needed(self, image_data: bytes, max_dimension: Optional[int] = None) -> bytes:
        """
        Preprocess image if it exceeds size limits (optimized for mobile screenshots)
        
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
            
            # MOBILE OPTIMIZATION: Correct orientation from EXIF data
            image = self._correct_image_orientation(image)
            
            width, height = image.size
            
            # Check if resizing is needed
            if width <= max_dimension and height <= max_dimension:
                # Even if dimensions are OK, we might need to save with corrected orientation
                if hasattr(image, '_getexif') and image.getexif().get(274, 1) != 1:
                    logger.debug("Saving image with corrected orientation")
                    output_buffer = io.BytesIO()
                    save_format = image.format if image.format in {'JPEG', 'PNG', 'WEBP'} else 'JPEG'
                    image.save(output_buffer, format=save_format, quality=90, optimize=True)
                    return output_buffer.getvalue()
                else:
                    logger.debug("Image dimensions within limits, no preprocessing needed")
                    return image_data
            
            # Calculate new dimensions maintaining aspect ratio
            if width > height:
                new_width = max_dimension
                new_height = int((height * max_dimension) / width)
            else:
                new_height = max_dimension
                new_width = int((width * max_dimension) / height)
            
            # Resize image with high quality resampling
            resized_image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # Save to bytes with mobile-optimized settings
            output_buffer = io.BytesIO()
            
            # MOBILE OPTIMIZATION: Better format preservation and quality
            if image.format in {'JPEG', 'HEIC', 'HEIF'}:
                save_format = 'JPEG'
                quality = 85
            elif image.format in {'PNG', 'TIFF', 'BMP'}:
                save_format = 'PNG'
                quality = 90
            elif image.format == 'WEBP':
                save_format = 'WEBP'
                quality = 80
            else:
                save_format = 'JPEG'
                quality = 85
            
            resized_image.save(output_buffer, format=save_format, quality=quality, optimize=True)
            
            processed_data = output_buffer.getvalue()
            
            logger.info(f"Mobile-optimized: Resized image from {width}x{height} to {new_width}x{new_height}, "
                       f"size reduced from {len(image_data)} to {len(processed_data)} bytes")
            
            return processed_data
            
        except Exception as e:
            logger.error(f"Error preprocessing mobile image: {str(e)}")
            # Return original data if preprocessing fails
            return image_data
    
    def optimize_mobile_screenshot(self, image_data: bytes) -> bytes:
        """
        Aggressively optimize mobile screenshots for API processing
        
        Args:
            image_data: Original mobile screenshot data
            
        Returns:
            Optimized image data suitable for AI processing
        """
        try:
            image = Image.open(io.BytesIO(image_data))
            
            # Correct orientation first
            image = self._correct_image_orientation(image)
            
            width, height = image.size
            original_size = len(image_data)
            
            # Check if this looks like a mobile screenshot (high resolution)
            is_mobile_screenshot = (
                width > self.MOBILE_DIMENSION_THRESHOLD or 
                height > self.MOBILE_DIMENSION_THRESHOLD or 
                original_size > 3 * 1024 * 1024  # > 3MB
            )
            
            if not is_mobile_screenshot:
                # Use regular preprocessing for smaller images
                return self.preprocess_image_if_needed(image_data)
            
            logger.info(f"Mobile screenshot detected: {width}x{height}, {original_size/1024/1024:.1f}MB")
            
            # Aggressive mobile optimization
            target_dimension = min(self.MAX_DIMENSION, 2048)  # Cap at 2048 for mobile
            
            if width > target_dimension or height > target_dimension:
                # Calculate new dimensions
                if width > height:
                    new_width = target_dimension
                    new_height = int((height * target_dimension) / width)
                else:
                    new_height = target_dimension
                    new_width = int((width * target_dimension) / height)
                
                # Resize with high-quality resampling
                image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                logger.info(f"Mobile screenshot resized to: {new_width}x{new_height}")
            
            # Convert to RGB if necessary (for JPEG compression)
            if image.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', image.size, (255, 255, 255))
                if image.mode == 'P':
                    image = image.convert('RGBA')
                background.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
                image = background
            
            # Save with mobile-optimized settings
            output_buffer = io.BytesIO()
            
            # Use JPEG for mobile screenshots to reduce file size
            image.save(output_buffer, format='JPEG', quality=80, optimize=True, progressive=True)
            
            optimized_data = output_buffer.getvalue()
            compression_ratio = original_size / len(optimized_data)
            
            logger.info(f"Mobile screenshot optimized: {original_size/1024/1024:.1f}MB → {len(optimized_data)/1024/1024:.1f}MB "
                       f"(compression: {compression_ratio:.1f}x)")
            
            return optimized_data
            
        except Exception as e:
            logger.error(f"Error optimizing mobile screenshot: {str(e)}")
            # Fallback to regular preprocessing
            return self.preprocess_image_if_needed(image_data)
    
    def _correct_image_orientation(self, image):
        """
        Correct image orientation based on EXIF data (important for mobile photos)
        
        Args:
            image: PIL Image object
            
        Returns:
            PIL Image object with corrected orientation
        """
        try:
            # Get EXIF data
            exif = image.getexif()
            
            # EXIF orientation tag is 274
            orientation = exif.get(274, 1)
            
            # Apply rotation based on orientation
            if orientation == 2:
                image = image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
            elif orientation == 3:
                image = image.rotate(180, expand=True)
            elif orientation == 4:
                image = image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
            elif orientation == 5:
                image = image.transpose(Image.Transpose.FLIP_LEFT_RIGHT).rotate(90, expand=True)
            elif orientation == 6:
                image = image.rotate(270, expand=True)
            elif orientation == 7:
                image = image.transpose(Image.Transpose.FLIP_LEFT_RIGHT).rotate(270, expand=True)
            elif orientation == 8:
                image = image.rotate(90, expand=True)
            
            # Remove EXIF data to avoid issues and reduce file size
            if hasattr(image, '_getexif'):
                image = image.copy()
                
            logger.debug(f"Corrected image orientation from EXIF tag: {orientation}")
            return image
            
        except Exception as e:
            logger.debug(f"Could not read EXIF orientation data: {e}")
            return image
    
    def cleanup_temp_files(self):
        """Clean up all temporary files created by this instance with robust error handling"""
        # Prevent duplicate cleanup attempts
        if self._cleanup_completed:
            logger.debug("Cleanup already completed, skipping")
            return
        
        if not self.temp_files:
            logger.debug("No temporary files to clean up")
            self._cleanup_completed = True
            return
        
        cleaned_count = 0
        failed_count = 0
        failed_files = []
        
        logger.debug(f"Starting cleanup of {len(self.temp_files)} temporary files")
        
        for temp_path in self.temp_files:
            try:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                    cleaned_count += 1
                    logger.debug(f"Successfully cleaned up temporary file: {temp_path}")
                else:
                    logger.debug(f"Temporary file already removed: {temp_path}")
                
                # Remove from global tracking
                _untrack_temp_file(temp_path)
                
            except OSError as e:
                failed_count += 1
                failed_files.append(temp_path)
                logger.warning(f"Failed to cleanup temporary file {temp_path}: {str(e)}")
                # Still remove from tracking even if cleanup failed
                _untrack_temp_file(temp_path)
            except Exception as e:
                failed_count += 1
                failed_files.append(temp_path)
                logger.error(f"Unexpected error cleaning up temporary file {temp_path}: {str(e)}")
                # Still remove from tracking even if cleanup failed
                _untrack_temp_file(temp_path)
        
        # Clear the list regardless of individual cleanup success
        self.temp_files.clear()
        self._cleanup_completed = True
        
        # Log summary
        if cleaned_count > 0:
            logger.info(f"Successfully cleaned up {cleaned_count} temporary image files")
        
        if failed_count > 0:
            logger.warning(f"Failed to clean up {failed_count} temporary files: {failed_files}")
        
        if cleaned_count == 0 and failed_count == 0:
            logger.debug("Cleanup completed - no files required removal")
    

# Convenience functions for backward compatibility
def download_image_from_line(line_bot_api, message_id: str) -> Optional[Dict]:
    """Convenience function to download image from LINE"""
    with ImageProcessor() as processor:
        return processor.download_image_from_line(line_bot_api, message_id)

def image_to_base64(image_data: bytes, image_format: str) -> str:
    """Convenience function to convert image to base64"""
    with ImageProcessor() as processor:
        return processor.image_to_base64(image_data, image_format)