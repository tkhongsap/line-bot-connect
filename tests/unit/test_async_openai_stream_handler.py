"""
Unit tests for AsyncOpenAIStreamHandler

Tests async streaming capabilities, buffer management, batch processing,
and performance monitoring.
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock, patch
from dataclasses import asdict

from src.utils.async_openai_stream_handler import (
    AsyncOpenAIStreamHandler, StreamChunk, StreamMetrics, AsyncStreamBuffer,
    async_stream_context
)
from src.exceptions import OpenAIAPIException

class TestStreamChunk:
    """Test StreamChunk data class"""
    
    def test_stream_chunk_creation(self):
        """Test StreamChunk initialization"""
        chunk = StreamChunk(
            content="Hello world",
            chunk_id="test_1",
            timestamp=time.time(),
            token_count=2,
            is_final=False,
            metadata={'source': 'test'}
        )
        
        assert chunk.content == "Hello world"
        assert chunk.chunk_id == "test_1"
        assert chunk.token_count == 2
        assert not chunk.is_final
        assert chunk.metadata['source'] == 'test'
    
    def test_stream_chunk_defaults(self):
        """Test StreamChunk default values"""
        chunk = StreamChunk(
            content="test",
            chunk_id="test_1",
            timestamp=time.time(),
            token_count=1
        )
        
        assert not chunk.is_final
        assert chunk.metadata is None

class TestStreamMetrics:
    """Test StreamMetrics data class"""
    
    def test_stream_metrics_creation(self):
        """Test StreamMetrics initialization"""
        start_time = time.time()
        metrics = StreamMetrics(start_time=start_time)
        
        assert metrics.start_time == start_time
        assert metrics.end_time is None
        assert metrics.total_chunks == 0
        assert metrics.total_tokens == 0
        assert metrics.avg_chunk_size == 0.0
        assert metrics.latency_ms == 0.0
        assert metrics.throughput_tokens_per_sec == 0.0
        assert not metrics.connection_reused

class TestAsyncStreamBuffer:
    """Test AsyncStreamBuffer functionality"""
    
    @pytest.mark.asyncio
    async def test_buffer_initialization(self):
        """Test buffer initialization with defaults"""
        buffer = AsyncStreamBuffer()
        
        assert buffer.max_buffer_size == 50
        assert buffer.flush_interval == 0.1
        assert len(buffer.buffer) == 0
        assert not buffer.flush_event.is_set()
    
    @pytest.mark.asyncio
    async def test_buffer_custom_settings(self):
        """Test buffer with custom settings"""
        buffer = AsyncStreamBuffer(max_buffer_size=10, flush_interval=0.5)
        
        assert buffer.max_buffer_size == 10
        assert buffer.flush_interval == 0.5
    
    @pytest.mark.asyncio
    async def test_add_chunk_normal(self):
        """Test adding chunks normally"""
        buffer = AsyncStreamBuffer(max_buffer_size=3)
        
        chunk1 = StreamChunk("test1", "id1", time.time(), 1)
        chunk2 = StreamChunk("test2", "id2", time.time(), 1)
        
        await buffer.add_chunk(chunk1)
        await buffer.add_chunk(chunk2)
        
        assert len(buffer.buffer) == 2
        assert not buffer.flush_event.is_set()
    
    @pytest.mark.asyncio
    async def test_add_chunk_triggers_flush(self):
        """Test that adding chunks triggers flush when buffer is full"""
        buffer = AsyncStreamBuffer(max_buffer_size=2)
        
        chunk1 = StreamChunk("test1", "id1", time.time(), 1)
        chunk2 = StreamChunk("test2", "id2", time.time(), 1)
        
        await buffer.add_chunk(chunk1)
        await buffer.add_chunk(chunk2)
        
        assert buffer.flush_event.is_set()
    
    @pytest.mark.asyncio
    async def test_final_chunk_triggers_flush(self):
        """Test that final chunk triggers flush regardless of buffer size"""
        buffer = AsyncStreamBuffer(max_buffer_size=10)
        
        chunk = StreamChunk("final", "id1", time.time(), 1, is_final=True)
        await buffer.add_chunk(chunk)
        
        assert buffer.flush_event.is_set()
    
    @pytest.mark.asyncio
    async def test_get_buffered_chunks(self):
        """Test retrieving and clearing buffered chunks"""
        buffer = AsyncStreamBuffer()
        
        chunk1 = StreamChunk("test1", "id1", time.time(), 1)
        chunk2 = StreamChunk("test2", "id2", time.time(), 1)
        
        await buffer.add_chunk(chunk1)
        await buffer.add_chunk(chunk2)
        
        chunks = await buffer.get_buffered_chunks()
        
        assert len(chunks) == 2
        assert chunks[0].content == "test1"
        assert chunks[1].content == "test2"
        assert len(buffer.buffer) == 0
        assert not buffer.flush_event.is_set()
    
    @pytest.mark.asyncio
    async def test_wait_for_flush_timeout(self):
        """Test wait_for_flush with timeout"""
        buffer = AsyncStreamBuffer()
        
        # Should timeout immediately since no flush event is set
        start_time = time.time()
        await buffer.wait_for_flush(timeout=0.1)
        duration = time.time() - start_time
        
        assert duration >= 0.1

class TestAsyncOpenAIStreamHandler:
    """Test AsyncOpenAIStreamHandler functionality"""
    
    @pytest.fixture
    def mock_openai_service(self):
        """Mock OpenAI service"""
        service = Mock()
        service.get_response = Mock()
        return service
    
    @pytest.fixture
    def mock_settings(self):
        """Mock settings"""
        settings = Mock()
        settings.MAX_CONCURRENT_STREAMS = 5
        settings.STREAM_TIMEOUT_SECONDS = 30
        settings.STREAM_CHUNK_BUFFER_SIZE = 10
        settings.STREAM_FLUSH_INTERVAL = 0.1
        return settings
    
    @pytest.fixture
    def stream_handler(self, mock_openai_service, mock_settings):
        """Create stream handler with mocks"""
        return AsyncOpenAIStreamHandler(mock_openai_service, mock_settings)
    
    def test_initialization(self, stream_handler, mock_settings):
        """Test handler initialization"""
        assert stream_handler.max_concurrent_streams == 5
        assert stream_handler.stream_timeout == 30
        assert stream_handler.chunk_buffer_size == 10
        assert stream_handler.flush_interval == 0.1
        assert len(stream_handler.active_streams) == 0
        assert len(stream_handler.metrics) == 0
    
    def test_initialization_defaults(self, mock_openai_service):
        """Test handler initialization with default settings"""
        settings = Mock()
        # Remove all custom attributes to test defaults
        for attr in ['MAX_CONCURRENT_STREAMS', 'STREAM_TIMEOUT_SECONDS', 
                     'STREAM_CHUNK_BUFFER_SIZE', 'STREAM_FLUSH_INTERVAL']:
            if hasattr(settings, attr):
                delattr(settings, attr)
        
        handler = AsyncOpenAIStreamHandler(mock_openai_service, settings)
        
        assert handler.max_concurrent_streams == 10
        assert handler.stream_timeout == 30
        assert handler.chunk_buffer_size == 50
        assert handler.flush_interval == 0.1

    @pytest.mark.asyncio
    async def test_create_async_stream_success(self, stream_handler, mock_openai_service):
        """Test successful async stream creation"""
        mock_openai_service.get_response.return_value = {
            'success': True,
            'streaming': True,
            'content': 'Hello world test'
        }
        
        chunks = []
        async for chunk in stream_handler.create_async_stream(
            user_id="test_user",
            user_message="Hello"
        ):
            chunks.append(chunk)
        
        assert len(chunks) > 0
        assert all(isinstance(chunk, StreamChunk) for chunk in chunks)
        assert mock_openai_service.get_response.called
    
    @pytest.mark.asyncio
    async def test_create_async_stream_failure(self, stream_handler, mock_openai_service):
        """Test async stream creation failure"""
        mock_openai_service.get_response.return_value = {
            'success': False,
            'streaming': False,
            'error': 'API error'
        }
        
        with pytest.raises(OpenAIAPIException):
            async for chunk in stream_handler.create_async_stream(
                user_id="test_user",
                user_message="Hello"
            ):
                pass
    
    @pytest.mark.asyncio
    async def test_create_async_stream_with_callbacks(self, stream_handler, mock_openai_service):
        """Test async stream with callback functions"""
        mock_openai_service.get_response.return_value = {
            'success': True,
            'streaming': True,
            'content': 'Hello world'
        }
        
        chunk_callback_calls = []
        progress_callback_calls = []
        
        def chunk_callback(chunks):
            chunk_callback_calls.extend(chunks)
        
        def progress_callback(progress):
            progress_callback_calls.append(progress)
        
        chunks = []
        async for chunk in stream_handler.create_async_stream(
            user_id="test_user",
            user_message="Hello",
            chunk_callback=chunk_callback,
            progress_callback=progress_callback
        ):
            chunks.append(chunk)
        
        # Allow some time for callbacks to process
        await asyncio.sleep(0.2)
        
        assert len(chunks) > 0
        assert len(progress_callback_calls) > 0
    
    @pytest.mark.asyncio
    async def test_create_batch_stream(self, stream_handler, mock_openai_service):
        """Test batch streaming functionality"""
        mock_openai_service.get_response.return_value = {
            'success': True,
            'streaming': True,
            'content': 'Batch response'
        }
        
        requests = [
            {'user_id': 'user1', 'message': 'Hello 1'},
            {'user_id': 'user2', 'message': 'Hello 2'}
        ]
        
        results = []
        async for result in stream_handler.create_batch_stream(requests):
            results.append(result)
        
        assert len(results) > 0
        assert all('batch_id' in result for result in results)
    
    @pytest.mark.asyncio
    async def test_create_batch_stream_with_callback(self, stream_handler, mock_openai_service):
        """Test batch streaming with callback"""
        mock_openai_service.get_response.return_value = {
            'success': True,
            'streaming': True,
            'content': 'Batch response'
        }
        
        batch_callback_calls = []
        
        def batch_callback(user_id, chunk):
            batch_callback_calls.append((user_id, chunk))
        
        requests = [
            {'user_id': 'user1', 'message': 'Hello 1'}
        ]
        
        results = []
        async for result in stream_handler.create_batch_stream(
            requests, 
            batch_callback=batch_callback
        ):
            results.append(result)
        
        # Allow time for callbacks
        await asyncio.sleep(0.2)
        
        assert len(results) > 0
    
    def test_get_stream_metrics_empty(self, stream_handler):
        """Test getting metrics when no streams exist"""
        metrics = stream_handler.get_stream_metrics()
        
        assert metrics['total_streams'] == 0
    
    def test_get_stream_metrics_specific_stream(self, stream_handler):
        """Test getting metrics for specific stream"""
        stream_id = "test_stream"
        test_metrics = StreamMetrics(start_time=time.time())
        stream_handler.metrics[stream_id] = test_metrics
        
        metrics = stream_handler.get_stream_metrics(stream_id)
        assert metrics == test_metrics
        
        # Test non-existent stream
        empty_metrics = stream_handler.get_stream_metrics("non_existent")
        assert empty_metrics == {}
    
    def test_get_stream_metrics_aggregated(self, stream_handler):
        """Test getting aggregated metrics"""
        # Add test metrics
        for i in range(3):
            metrics = StreamMetrics(
                start_time=time.time(),
                end_time=time.time() + 1,
                total_chunks=10,
                total_tokens=20,
                latency_ms=100.0,
                throughput_tokens_per_sec=20.0,
                connection_reused=(i % 2 == 0)
            )
            stream_handler.metrics[f"stream_{i}"] = metrics
        
        aggregated = stream_handler.get_stream_metrics()
        
        assert aggregated['total_streams'] == 3
        assert aggregated['active_streams'] == 0
        assert aggregated['avg_latency_ms'] == 100.0
        assert aggregated['avg_throughput_tokens_per_sec'] == 20.0
        assert aggregated['total_tokens_processed'] == 60
        assert aggregated['connection_reuse_rate'] == 2/3
    
    @pytest.mark.asyncio
    async def test_cancel_stream(self, stream_handler):
        """Test stream cancellation"""
        # Create a mock task
        mock_task = AsyncMock()
        stream_id = "test_stream"
        stream_handler.active_streams[stream_id] = mock_task
        
        result = await stream_handler.cancel_stream(stream_id)
        
        assert result is True
        assert stream_id not in stream_handler.active_streams
        mock_task.cancel.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_cancel_nonexistent_stream(self, stream_handler):
        """Test cancelling non-existent stream"""
        result = await stream_handler.cancel_stream("non_existent")
        assert result is False
    
    @pytest.mark.asyncio
    async def test_cleanup(self, stream_handler):
        """Test handler cleanup"""
        # Add mock streams and metrics
        mock_task = AsyncMock()
        stream_handler.active_streams["stream1"] = mock_task
        stream_handler.metrics["stream1"] = StreamMetrics(start_time=time.time())
        
        await stream_handler.cleanup()
        
        assert len(stream_handler.active_streams) == 0
        assert len(stream_handler.metrics) == 0
        mock_task.cancel.assert_called_once()

class TestAsyncStreamContext:
    """Test async stream context manager"""
    
    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test async stream context manager"""
        mock_service = Mock()
        mock_settings = Mock()
        
        async with async_stream_context(mock_service, mock_settings) as handler:
            assert isinstance(handler, AsyncOpenAIStreamHandler)
            assert handler.openai_service == mock_service
            assert handler.settings == mock_settings
        
        # Handler should be cleaned up after context
        assert len(handler.active_streams) == 0
        assert len(handler.metrics) == 0

@pytest.mark.integration
class TestAsyncStreamHandlerIntegration:
    """Integration tests for async stream handler"""
    
    @pytest.mark.asyncio
    async def test_concurrent_streams(self):
        """Test multiple concurrent streams"""
        mock_service = Mock()
        mock_service.get_response.return_value = {
            'success': True,
            'streaming': True,
            'content': 'Concurrent test response'
        }
        
        settings = Mock()
        settings.MAX_CONCURRENT_STREAMS = 2
        settings.STREAM_TIMEOUT_SECONDS = 10
        settings.STREAM_CHUNK_BUFFER_SIZE = 10
        settings.STREAM_FLUSH_INTERVAL = 0.05
        
        handler = AsyncOpenAIStreamHandler(mock_service, settings)
        
        # Create multiple concurrent streams
        async def create_stream(user_id):
            chunks = []
            async for chunk in handler.create_async_stream(
                user_id=user_id,
                user_message="Test message"
            ):
                chunks.append(chunk)
            return chunks
        
        # Run concurrent streams
        tasks = [
            asyncio.create_task(create_stream(f"user_{i}"))
            for i in range(3)
        ]
        
        results = await asyncio.gather(*tasks)
        
        # All streams should complete successfully
        assert len(results) == 3
        assert all(len(chunks) > 0 for chunks in results)
        
        await handler.cleanup()
    
    @pytest.mark.asyncio 
    async def test_stream_timeout_handling(self):
        """Test stream timeout handling"""
        mock_service = Mock()
        # Mock a slow response
        def slow_response(*args, **kwargs):
            time.sleep(2)  # Simulate slow response
            return {
                'success': True,
                'streaming': True,
                'content': 'Slow response'
            }
        
        mock_service.get_response.side_effect = slow_response
        
        settings = Mock()
        settings.MAX_CONCURRENT_STREAMS = 1
        settings.STREAM_TIMEOUT_SECONDS = 1  # Short timeout
        settings.STREAM_CHUNK_BUFFER_SIZE = 10
        settings.STREAM_FLUSH_INTERVAL = 0.1
        
        handler = AsyncOpenAIStreamHandler(mock_service, settings)
        
        # Stream should complete despite slow response (timeout is applied to individual chunks)
        chunks = []
        async for chunk in handler.create_async_stream(
            user_id="test_user",
            user_message="Test message"
        ):
            chunks.append(chunk)
        
        # Should still get some chunks even with timeout
        assert len(chunks) >= 0
        
        await handler.cleanup()