"""
Async image processing pipeline for improved performance and scalability.

This module provides asynchronous image processing capabilities including
download, validation, transformation, and cleanup with queue management.
"""

import asyncio
import aiohttp
import aiofiles
import time
import logging
from typing import Optional, Dict, Any, List, Tuple, AsyncGenerator
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
import base64
from PIL import Image, ImageOps
import io
import tempfile
import os

from ..exceptions import (
    ImageProcessingException, NetworkException, TimeoutException,
    ValidationException, BaseBotException, create_correlation_id
)
from ..utils.error_handler import StructuredLogger


logger = StructuredLogger(__name__)


@dataclass
class ImageProcessingTask:
    """Image processing task metadata."""
    task_id: str
    user_id: str
    image_url: Optional[str] = None
    image_data: Optional[bytes] = None
    target_format: str = "JPEG"
    max_size: Tuple[int, int] = (2048, 2048)
    quality: int = 85
    created_at: datetime = None
    status: str = "pending"
    correlation_id: Optional[str] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.correlation_id is None:
            self.correlation_id = create_correlation_id()


@dataclass
class ProcessingResult:
    """Image processing result."""
    success: bool
    task_id: str
    processed_data: Optional[bytes] = None
    base64_data: Optional[str] = None
    original_size: Optional[Tuple[int, int]] = None
    processed_size: Optional[Tuple[int, int]] = None
    format: Optional[str] = None
    file_size: Optional[int] = None
    processing_time: Optional[float] = None
    error: Optional[str] = None
    correlation_id: Optional[str] = None


class AsyncImageProcessor:
    """
    Asynchronous image processor with queue management and batch processing.
    
    Features:
    - Async image download from URLs or LINE API
    - Concurrent processing with configurable limits
    - Automatic format conversion and optimization
    - Size validation and resizing
    - Temporary file management with automatic cleanup
    - Error handling and retry logic
    - Progress tracking and monitoring
    """
    
    def __init__(
        self,
        max_concurrent_tasks: int = 10,
        max_image_size_mb: float = 10.0,
        max_dimensions: Tuple[int, int] = (4096, 4096),
        temp_dir: Optional[str] = None,
        cleanup_interval: int = 300  # 5 minutes
    ):
        """
        Initialize async image processor.
        
        Args:
            max_concurrent_tasks: Maximum number of concurrent processing tasks
            max_image_size_mb: Maximum image size in MB
            max_dimensions: Maximum image dimensions (width, height)
            temp_dir: Temporary directory for file processing
            cleanup_interval: Cleanup interval in seconds
        """
        self.max_concurrent_tasks = max_concurrent_tasks
        self.max_image_size_bytes = int(max_image_size_mb * 1024 * 1024)
        self.max_dimensions = max_dimensions
        self.temp_dir = Path(temp_dir) if temp_dir else Path(tempfile.gettempdir()) / "line_bot_images"
        self.cleanup_interval = cleanup_interval
        
        # Create temp directory
        self.temp_dir.mkdir(exist_ok=True, parents=True)
        
        # Processing queues and state
        self.task_queue: asyncio.Queue = asyncio.Queue()
        self.processing_tasks: Dict[str, asyncio.Task] = {}
        self.results: Dict[str, ProcessingResult] = {}
        
        # Semaphore for concurrent processing limit
        self.semaphore = asyncio.Semaphore(max_concurrent_tasks)
        
        # Background tasks
        self._cleanup_task: Optional[asyncio.Task] = None
        self._processor_task: Optional[asyncio.Task] = None
        self._running = False
        
        # Statistics
        self.stats = {
            'total_processed': 0,
            'successful_processed': 0,
            'failed_processed': 0,
            'total_processing_time': 0.0,
            'average_processing_time': 0.0
        }
    
    async def start(self):
        """Start the async image processor."""
        if self._running:
            return
        
        self._running = True
        
        # Start background tasks
        self._processor_task = asyncio.create_task(self._process_queue())
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        logger.info("Async image processor started")
    
    async def stop(self):
        """Stop the async image processor."""
        if not self._running:
            return
        
        self._running = False
        
        # Cancel background tasks
        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass
        
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Cancel any remaining processing tasks
        for task in self.processing_tasks.values():
            if not task.done():
                task.cancel()
        
        await asyncio.gather(*self.processing_tasks.values(), return_exceptions=True)
        
        logger.info("Async image processor stopped")
    
    async def process_image_url(
        self,
        user_id: str,
        image_url: str,
        target_format: str = "JPEG",
        max_size: Tuple[int, int] = None,
        quality: int = 85
    ) -> str:
        """
        Process image from URL asynchronously.
        
        Args:
            user_id: User ID for tracking
            image_url: URL of image to process
            target_format: Target image format
            max_size: Maximum dimensions (width, height)
            quality: JPEG quality (1-100)
            
        Returns:
            str: Task ID for tracking progress
        """
        task = ImageProcessingTask(
            task_id=create_correlation_id(),
            user_id=user_id,
            image_url=image_url,
            target_format=target_format,
            max_size=max_size or (2048, 2048),
            quality=quality
        )
        
        await self.task_queue.put(task)
        
        logger.info(
            f"Image processing task queued",
            correlation_id=task.correlation_id,
            extra_context={
                'task_id': task.task_id,
                'user_id': user_id[:8] + '...',
                'image_url': image_url[:50] + '...' if len(image_url) > 50 else image_url
            }
        )
        
        return task.task_id
    
    async def process_image_data(
        self,
        user_id: str,
        image_data: bytes,
        target_format: str = "JPEG",
        max_size: Tuple[int, int] = None,
        quality: int = 85
    ) -> str:
        """
        Process image from binary data asynchronously.
        
        Args:
            user_id: User ID for tracking
            image_data: Binary image data
            target_format: Target image format
            max_size: Maximum dimensions (width, height)
            quality: JPEG quality (1-100)
            
        Returns:
            str: Task ID for tracking progress
        """
        task = ImageProcessingTask(
            task_id=create_correlation_id(),
            user_id=user_id,
            image_data=image_data,
            target_format=target_format,
            max_size=max_size or (2048, 2048),
            quality=quality
        )
        
        await self.task_queue.put(task)
        
        logger.info(
            f"Image processing task queued",
            correlation_id=task.correlation_id,
            extra_context={
                'task_id': task.task_id,
                'user_id': user_id[:8] + '...',
                'data_size': len(image_data)
            }
        )
        
        return task.task_id
    
    async def get_result(self, task_id: str, timeout: float = 30.0) -> Optional[ProcessingResult]:
        """
        Get processing result by task ID.
        
        Args:
            task_id: Task ID to check
            timeout: Maximum wait time in seconds
            
        Returns:
            ProcessingResult or None if not ready/timeout
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if task_id in self.results:
                return self.results[task_id]
            
            # Check if task is still processing
            if task_id in self.processing_tasks:
                await asyncio.sleep(0.1)
                continue
            
            # Task might be in queue
            await asyncio.sleep(0.5)
        
        return None
    
    async def wait_for_result(self, task_id: str, timeout: float = 30.0) -> ProcessingResult:
        """
        Wait for processing result with timeout.
        
        Args:
            task_id: Task ID to wait for
            timeout: Maximum wait time in seconds
            
        Returns:
            ProcessingResult
            
        Raises:
            TimeoutException: If processing takes too long
        """
        result = await self.get_result(task_id, timeout)
        
        if result is None:
            raise TimeoutException(
                message=f"Image processing timeout after {timeout} seconds",
                operation="async_image_processing",
                timeout_seconds=timeout,
                context={'task_id': task_id}
            )
        
        return result
    
    async def _process_queue(self):
        """Background task to process queued images."""
        while self._running:
            try:
                # Get task from queue with timeout
                try:
                    task = await asyncio.wait_for(self.task_queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue
                
                # Create processing task
                processing_task = asyncio.create_task(self._process_single_image(task))
                self.processing_tasks[task.task_id] = processing_task
                
                # Don't await here - let it run concurrently
                # The semaphore will limit concurrency
                
            except Exception as e:
                logger.error(
                    f"Error in processing queue: {str(e)}",
                    exception=e
                )
                await asyncio.sleep(1)
    
    async def _process_single_image(self, task: ImageProcessingTask) -> ProcessingResult:
        """Process a single image processing task."""
        start_time = time.time()
        
        async with self.semaphore:  # Limit concurrent processing
            try:
                logger.info(
                    f"Starting image processing",
                    correlation_id=task.correlation_id,
                    extra_context={'task_id': task.task_id}
                )
                
                # Download image if URL provided
                if task.image_url:
                    image_data = await self._download_image(task.image_url, task.correlation_id)
                else:
                    image_data = task.image_data
                
                if not image_data:
                    raise ImageProcessingException(
                        message="No image data available",
                        image_type="unknown",
                        correlation_id=task.correlation_id
                    )
                
                # Validate image size
                if len(image_data) > self.max_image_size_bytes:
                    raise ValidationException(
                        message=f"Image too large: {len(image_data)} bytes (max: {self.max_image_size_bytes})",
                        field="image_size",
                        value=len(image_data),
                        correlation_id=task.correlation_id
                    )
                
                # Process image
                processed_data, metadata = await self._process_image_data(
                    image_data, task
                )
                
                # Generate base64 if requested
                base64_data = base64.b64encode(processed_data).decode('utf-8')
                
                processing_time = time.time() - start_time
                
                # Update statistics
                self.stats['total_processed'] += 1
                self.stats['successful_processed'] += 1
                self.stats['total_processing_time'] += processing_time
                self.stats['average_processing_time'] = (
                    self.stats['total_processing_time'] / self.stats['total_processed']
                )
                
                result = ProcessingResult(
                    success=True,
                    task_id=task.task_id,
                    processed_data=processed_data,
                    base64_data=base64_data,
                    original_size=metadata.get('original_size'),
                    processed_size=metadata.get('processed_size'),
                    format=metadata.get('format'),
                    file_size=len(processed_data),
                    processing_time=processing_time,
                    correlation_id=task.correlation_id
                )
                
                logger.info(
                    f"Image processing completed successfully",
                    correlation_id=task.correlation_id,
                    extra_context={
                        'task_id': task.task_id,
                        'processing_time': processing_time,
                        'original_size': metadata.get('original_size'),
                        'processed_size': metadata.get('processed_size'),
                        'file_size': len(processed_data)
                    }
                )
                
            except Exception as e:
                processing_time = time.time() - start_time
                
                # Update statistics
                self.stats['total_processed'] += 1
                self.stats['failed_processed'] += 1
                
                logger.exception(
                    f"Image processing failed",
                    exception=e,
                    correlation_id=task.correlation_id,
                    extra_context={
                        'task_id': task.task_id,
                        'processing_time': processing_time
                    }
                )
                
                result = ProcessingResult(
                    success=False,
                    task_id=task.task_id,
                    processing_time=processing_time,
                    error=str(e),
                    correlation_id=task.correlation_id
                )
            
            finally:
                # Store result and cleanup
                self.results[task.task_id] = result
                if task.task_id in self.processing_tasks:
                    del self.processing_tasks[task.task_id]
        
        return result
    
    async def _download_image(self, url: str, correlation_id: str) -> bytes:
        """Download image from URL."""
        try:
            timeout = aiohttp.ClientTimeout(total=30)
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        raise NetworkException(
                            message=f"Failed to download image: HTTP {response.status}",
                            operation="image_download",
                            correlation_id=correlation_id
                        )
                    
                    # Check content length
                    content_length = response.headers.get('Content-Length')
                    if content_length and int(content_length) > self.max_image_size_bytes:
                        raise ValidationException(
                            message=f"Image too large: {content_length} bytes",
                            field="content_length",
                            value=content_length,
                            correlation_id=correlation_id
                        )
                    
                    image_data = await response.read()
                    
                    logger.debug(
                        f"Image downloaded successfully",
                        correlation_id=correlation_id,
                        extra_context={
                            'url': url[:50] + '...' if len(url) > 50 else url,
                            'size': len(image_data),
                            'content_type': response.headers.get('Content-Type')
                        }
                    )
                    
                    return image_data
                    
        except aiohttp.ClientError as e:
            raise NetworkException(
                message=f"Network error downloading image: {str(e)}",
                operation="image_download",
                correlation_id=correlation_id,
                original_exception=e
            )
        except asyncio.TimeoutError as e:
            raise TimeoutException(
                message="Image download timeout",
                operation="image_download",
                timeout_seconds=30,
                correlation_id=correlation_id,
                original_exception=e
            )
    
    async def _process_image_data(
        self,
        image_data: bytes,
        task: ImageProcessingTask
    ) -> Tuple[bytes, Dict[str, Any]]:
        """Process image data with resizing and format conversion."""
        
        # Run CPU-intensive image processing in thread pool
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._process_image_sync,
            image_data,
            task
        )
    
    def _process_image_sync(
        self,
        image_data: bytes,
        task: ImageProcessingTask
    ) -> Tuple[bytes, Dict[str, Any]]:
        """Synchronous image processing (runs in thread pool)."""
        try:
            # Open image
            with Image.open(io.BytesIO(image_data)) as img:
                original_size = img.size
                original_format = img.format
                
                # Convert to RGB if necessary
                if img.mode in ('RGBA', 'LA', 'P'):
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                    img = background
                elif img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Auto-orient based on EXIF
                img = ImageOps.exif_transpose(img)
                
                # Resize if needed
                if (img.size[0] > task.max_size[0] or 
                    img.size[1] > task.max_size[1] or
                    img.size[0] > self.max_dimensions[0] or 
                    img.size[1] > self.max_dimensions[1]):
                    
                    # Calculate resize dimensions maintaining aspect ratio
                    max_w = min(task.max_size[0], self.max_dimensions[0])
                    max_h = min(task.max_size[1], self.max_dimensions[1])
                    
                    img.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
                
                processed_size = img.size
                
                # Save to bytes
                output = io.BytesIO()
                save_format = task.target_format.upper()
                
                if save_format == 'JPEG':
                    img.save(output, format='JPEG', quality=task.quality, optimize=True)
                elif save_format == 'PNG':
                    img.save(output, format='PNG', optimize=True)
                elif save_format == 'WEBP':
                    img.save(output, format='WEBP', quality=task.quality, optimize=True)
                else:
                    img.save(output, format='JPEG', quality=task.quality, optimize=True)
                    save_format = 'JPEG'
                
                processed_data = output.getvalue()
                
                metadata = {
                    'original_size': original_size,
                    'processed_size': processed_size,
                    'original_format': original_format,
                    'format': save_format,
                    'compression_ratio': len(image_data) / len(processed_data) if processed_data else 1.0
                }
                
                return processed_data, metadata
                
        except Exception as e:
            raise ImageProcessingException(
                message=f"Image processing failed: {str(e)}",
                image_type=task.target_format,
                correlation_id=task.correlation_id,
                original_exception=e
            )
    
    async def _cleanup_loop(self):
        """Background cleanup of old results and temp files."""
        while self._running:
            try:
                await asyncio.sleep(self.cleanup_interval)
                
                # Clean up old results (keep for 1 hour)
                current_time = time.time()
                expired_results = [
                    task_id for task_id, result in self.results.items()
                    if hasattr(result, 'created_at') and 
                    current_time - result.created_at.timestamp() > 3600
                ]
                
                for task_id in expired_results:
                    del self.results[task_id]
                
                # Clean up temp files
                await self._cleanup_temp_files()
                
                if expired_results:
                    logger.debug(f"Cleaned up {len(expired_results)} expired results")
                    
            except Exception as e:
                logger.error(f"Cleanup error: {str(e)}", exception=e)
    
    async def _cleanup_temp_files(self):
        """Clean up old temporary files."""
        try:
            current_time = time.time()
            
            for file_path in self.temp_dir.glob("*"):
                if file_path.is_file():
                    # Remove files older than 1 hour
                    if current_time - file_path.stat().st_mtime > 3600:
                        file_path.unlink()
                        
        except Exception as e:
            logger.warning(f"Temp file cleanup error: {str(e)}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get processing statistics."""
        return {
            **self.stats.copy(),
            'queue_size': self.task_queue.qsize(),
            'active_tasks': len(self.processing_tasks),
            'cached_results': len(self.results),
            'max_concurrent_tasks': self.max_concurrent_tasks
        }
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.stop()


# Global async image processor instance
_async_processor: Optional[AsyncImageProcessor] = None


async def get_async_image_processor() -> AsyncImageProcessor:
    """Get or create the global async image processor."""
    global _async_processor
    
    if _async_processor is None:
        _async_processor = AsyncImageProcessor()
        await _async_processor.start()
    
    return _async_processor


# Export main classes
__all__ = [
    'AsyncImageProcessor',
    'ImageProcessingTask',
    'ProcessingResult',
    'get_async_image_processor'
]