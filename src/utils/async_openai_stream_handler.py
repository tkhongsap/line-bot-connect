"""
Async OpenAI Streaming Response Handler

This module provides async streaming capabilities for OpenAI responses with enhanced
user experience features including real-time response streaming, chunk buffering,
and connection management.
"""

import asyncio
import time
import json
import logging
from typing import AsyncGenerator, Dict, Any, Optional, Callable, List
from dataclasses import dataclass
from contextlib import asynccontextmanager

from ..exceptions import (
    OpenAIAPIException, NetworkException, TimeoutException,
    create_correlation_id, wrap_api_exception
)
from ..utils.error_handler import StructuredLogger, error_handler, retry_with_backoff

logger = StructuredLogger(__name__)

@dataclass
class StreamChunk:
    """Represents a streaming response chunk with metadata"""
    content: str
    chunk_id: str
    timestamp: float
    token_count: int
    is_final: bool = False
    metadata: Optional[Dict[str, Any]] = None

@dataclass
class StreamMetrics:
    """Streaming response performance metrics"""
    start_time: float
    end_time: Optional[float] = None
    total_chunks: int = 0
    total_tokens: int = 0
    avg_chunk_size: float = 0.0
    latency_ms: float = 0.0
    throughput_tokens_per_sec: float = 0.0
    connection_reused: bool = False

class AsyncStreamBuffer:
    """Async buffer for streaming chunks with configurable batching"""
    
    def __init__(self, max_buffer_size: int = 50, flush_interval: float = 0.1):
        self.max_buffer_size = max_buffer_size
        self.flush_interval = flush_interval
        self.buffer: List[StreamChunk] = []
        self.lock = asyncio.Lock()
        self.flush_event = asyncio.Event()
        
    async def add_chunk(self, chunk: StreamChunk):
        """Add chunk to buffer and trigger flush if needed"""
        async with self.lock:
            self.buffer.append(chunk)
            if len(self.buffer) >= self.max_buffer_size or chunk.is_final:
                self.flush_event.set()
    
    async def get_buffered_chunks(self) -> List[StreamChunk]:
        """Get and clear buffered chunks"""
        async with self.lock:
            chunks = self.buffer.copy()
            self.buffer.clear()
            self.flush_event.clear()
            return chunks
    
    async def wait_for_flush(self, timeout: float = None):
        """Wait for buffer flush event"""
        try:
            await asyncio.wait_for(self.flush_event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            pass

class AsyncOpenAIStreamHandler:
    """Async handler for OpenAI streaming responses with enhanced UX"""
    
    def __init__(self, openai_service, settings):
        self.openai_service = openai_service
        self.settings = settings
        
        # Streaming configuration
        self.max_concurrent_streams = getattr(settings, 'MAX_CONCURRENT_STREAMS', 10)
        self.stream_timeout = getattr(settings, 'STREAM_TIMEOUT_SECONDS', 30)
        self.chunk_buffer_size = getattr(settings, 'STREAM_CHUNK_BUFFER_SIZE', 50)
        self.flush_interval = getattr(settings, 'STREAM_FLUSH_INTERVAL', 0.1)
        
        # Connection semaphore for concurrent stream management
        self.stream_semaphore = asyncio.Semaphore(self.max_concurrent_streams)
        
        # Active streams tracking
        self.active_streams: Dict[str, asyncio.Task] = {}
        
        # Performance metrics
        self.metrics: Dict[str, StreamMetrics] = {}
        
        logger.info(f"Initialized AsyncOpenAIStreamHandler with {self.max_concurrent_streams} max concurrent streams")
    
    async def create_async_stream(
        self,
        user_id: str,
        user_message: str,
        image_data: Optional[str] = None,
        chunk_callback: Optional[Callable[[StreamChunk], None]] = None,
        progress_callback: Optional[Callable[[float], None]] = None
    ) -> AsyncGenerator[StreamChunk, None]:
        """Create async streaming response with enhanced UX features"""
        
        correlation_id = create_correlation_id()
        stream_id = f"{user_id}_{correlation_id}"
        
        logger.info(f"Starting async stream for user {user_id}", extra={
            'correlation_id': correlation_id,
            'stream_id': stream_id
        })
        
        # Initialize metrics
        metrics = StreamMetrics(start_time=time.time())
        self.metrics[stream_id] = metrics
        
        try:
            async with self.stream_semaphore:  # Limit concurrent streams
                await self._create_streaming_response(
                    stream_id, user_id, user_message, image_data, 
                    chunk_callback, progress_callback, metrics
                )
                
        except Exception as e:
            logger.error(f"Async stream error for user {user_id}: {str(e)}", extra={
                'correlation_id': correlation_id,
                'error_type': type(e).__name__
            })
            raise wrap_api_exception(e, context={
                'user_id': user_id,
                'stream_id': stream_id,
                'correlation_id': correlation_id
            })
        finally:
            # Clean up active stream tracking
            self.active_streams.pop(stream_id, None)
            
            # Finalize metrics
            metrics.end_time = time.time()
            if metrics.total_chunks > 0:
                metrics.avg_chunk_size = metrics.total_tokens / metrics.total_chunks
                duration = metrics.end_time - metrics.start_time
                metrics.latency_ms = duration * 1000
                metrics.throughput_tokens_per_sec = metrics.total_tokens / duration if duration > 0 else 0
    
    async def _create_streaming_response(
        self,
        stream_id: str,
        user_id: str,
        user_message: str,
        image_data: Optional[str],
        chunk_callback: Optional[Callable],
        progress_callback: Optional[Callable],
        metrics: StreamMetrics
    ):
        """Internal method to handle streaming response creation"""
        
        # Create async buffer for chunk batching
        buffer = AsyncStreamBuffer(
            max_buffer_size=self.chunk_buffer_size,
            flush_interval=self.flush_interval
        )
        
        # Start buffer flush task
        flush_task = asyncio.create_task(
            self._buffer_flush_loop(buffer, chunk_callback)
        )
        
        try:
            # Get streaming response from OpenAI service
            response = await asyncio.to_thread(
                self.openai_service.get_response,
                user_id=user_id,
                user_message=user_message,
                use_streaming=True,
                image_data=image_data
            )
            
            if not response.get('success') or not response.get('streaming'):
                raise OpenAIAPIException(
                    message="Failed to initiate streaming response",
                    context={'user_id': user_id, 'response': response}
                )
            
            # Process streaming chunks
            chunk_count = 0
            async for chunk in self._process_stream_chunks(response, stream_id, metrics):
                await buffer.add_chunk(chunk)
                
                # Update progress callback
                if progress_callback:
                    progress = min(chunk_count / 100, 1.0)  # Estimate progress
                    await asyncio.to_thread(progress_callback, progress)
                
                chunk_count += 1
                yield chunk
                
                # Check for stream timeout
                if time.time() - metrics.start_time > self.stream_timeout:
                    logger.warning(f"Stream timeout for {stream_id}")
                    break
            
            # Add final chunk to buffer
            final_chunk = StreamChunk(
                content="",
                chunk_id=f"{stream_id}_final",
                timestamp=time.time(),
                token_count=0,
                is_final=True
            )
            await buffer.add_chunk(final_chunk)
            
        finally:
            # Cancel buffer flush task
            flush_task.cancel()
            try:
                await flush_task
            except asyncio.CancelledError:
                pass
    
    async def _process_stream_chunks(
        self, 
        response: Dict[str, Any], 
        stream_id: str, 
        metrics: StreamMetrics
    ) -> AsyncGenerator[StreamChunk, None]:
        """Process individual stream chunks from OpenAI response"""
        
        # Mock implementation - in real scenario, this would process the actual stream
        # from the OpenAI service response
        
        # For now, simulate streaming by yielding chunks from response content
        content = response.get('content', '')
        words = content.split()
        
        for i, word in enumerate(words):
            chunk = StreamChunk(
                content=word + " ",
                chunk_id=f"{stream_id}_{i}",
                timestamp=time.time(),
                token_count=1,  # Simplified token counting
                metadata={'chunk_index': i, 'total_chunks': len(words)}
            )
            
            # Update metrics
            metrics.total_chunks += 1
            metrics.total_tokens += chunk.token_count
            
            yield chunk
            
            # Small delay to simulate streaming
            await asyncio.sleep(0.05)
    
    async def _buffer_flush_loop(
        self, 
        buffer: AsyncStreamBuffer, 
        chunk_callback: Optional[Callable]
    ):
        """Background task to flush buffered chunks"""
        try:
            while True:
                await buffer.wait_for_flush(timeout=buffer.flush_interval)
                
                chunks = await buffer.get_buffered_chunks()
                if chunks and chunk_callback:
                    # Execute callback in thread to avoid blocking
                    await asyncio.to_thread(chunk_callback, chunks)
                    
        except asyncio.CancelledError:
            # Handle final flush on cancellation
            chunks = await buffer.get_buffered_chunks()
            if chunks and chunk_callback:
                await asyncio.to_thread(chunk_callback, chunks)
            raise
    
    async def create_batch_stream(
        self,
        requests: List[Dict[str, Any]],
        batch_callback: Optional[Callable[[str, StreamChunk], None]] = None
    ) -> AsyncGenerator[Dict[str, StreamChunk], None]:
        """Create multiple concurrent streaming responses"""
        
        batch_id = create_correlation_id()
        logger.info(f"Starting batch stream with {len(requests)} requests", extra={
            'batch_id': batch_id
        })
        
        # Create concurrent streams
        stream_tasks = []
        for i, request in enumerate(requests):
            task = asyncio.create_task(
                self._single_batch_stream(
                    request=request,
                    batch_id=batch_id,
                    request_index=i,
                    batch_callback=batch_callback
                )
            )
            stream_tasks.append(task)
        
        # Yield results as they complete
        try:
            async for result in self._yield_batch_results(stream_tasks, batch_id):
                yield result
        finally:
            # Clean up any remaining tasks
            for task in stream_tasks:
                if not task.done():
                    task.cancel()
    
    async def _single_batch_stream(
        self,
        request: Dict[str, Any],
        batch_id: str,
        request_index: int,
        batch_callback: Optional[Callable]
    ) -> AsyncGenerator[StreamChunk, None]:
        """Handle single stream in batch processing"""
        
        user_id = request.get('user_id', f'batch_{batch_id}_{request_index}')
        user_message = request.get('message', '')
        image_data = request.get('image_data')
        
        async for chunk in self.create_async_stream(
            user_id=user_id,
            user_message=user_message,
            image_data=image_data,
            chunk_callback=lambda c: batch_callback(user_id, c) if batch_callback else None
        ):
            yield chunk
    
    async def _yield_batch_results(
        self, 
        stream_tasks: List[asyncio.Task], 
        batch_id: str
    ) -> AsyncGenerator[Dict[str, StreamChunk], None]:
        """Yield batch results as they become available"""
        
        pending_tasks = set(stream_tasks)
        
        while pending_tasks:
            done, pending_tasks = await asyncio.wait(
                pending_tasks, 
                return_when=asyncio.FIRST_COMPLETED,
                timeout=1.0  # Check every second
            )
            
            for task in done:
                try:
                    result = await task
                    yield {'task_result': result, 'batch_id': batch_id}
                except Exception as e:
                    logger.error(f"Batch task failed: {str(e)}", extra={
                        'batch_id': batch_id,
                        'error_type': type(e).__name__
                    })
                    yield {'error': str(e), 'batch_id': batch_id}
    
    def get_stream_metrics(self, stream_id: Optional[str] = None) -> Dict[str, Any]:
        """Get streaming performance metrics"""
        if stream_id:
            return self.metrics.get(stream_id, {})
        
        # Return aggregated metrics
        total_streams = len(self.metrics)
        if total_streams == 0:
            return {'total_streams': 0}
        
        avg_latency = sum(m.latency_ms for m in self.metrics.values()) / total_streams
        avg_throughput = sum(m.throughput_tokens_per_sec for m in self.metrics.values()) / total_streams
        total_tokens = sum(m.total_tokens for m in self.metrics.values())
        
        return {
            'total_streams': total_streams,
            'active_streams': len(self.active_streams),
            'avg_latency_ms': avg_latency,
            'avg_throughput_tokens_per_sec': avg_throughput,
            'total_tokens_processed': total_tokens,
            'connection_reuse_rate': sum(1 for m in self.metrics.values() if m.connection_reused) / total_streams
        }
    
    async def cancel_stream(self, stream_id: str) -> bool:
        """Cancel an active stream"""
        if stream_id in self.active_streams:
            task = self.active_streams[stream_id]
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            
            logger.info(f"Cancelled stream {stream_id}")
            return True
        
        return False
    
    async def cleanup(self):
        """Clean up all active streams and resources"""
        logger.info("Cleaning up AsyncOpenAIStreamHandler")
        
        # Cancel all active streams
        for stream_id in list(self.active_streams.keys()):
            await self.cancel_stream(stream_id)
        
        # Clear metrics
        self.metrics.clear()
        
        logger.info("AsyncOpenAIStreamHandler cleanup completed")

# Context manager for easy async stream handling
@asynccontextmanager
async def async_stream_context(openai_service, settings):
    """Context manager for async OpenAI stream handler"""
    handler = AsyncOpenAIStreamHandler(openai_service, settings)
    try:
        yield handler
    finally:
        await handler.cleanup()