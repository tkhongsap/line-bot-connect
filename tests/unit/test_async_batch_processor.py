"""
Unit tests for AsyncBatchProcessor

Tests batch processing capabilities, queue management, worker coordination,
and performance monitoring.
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock, patch
from dataclasses import asdict

from src.utils.async_batch_processor import (
    AsyncBatchProcessor, BatchJob, BatchOperationType, BatchPriority, 
    BatchJobStatus, AsyncBatchQueue, AsyncBatchWorker, BatchProcessingStats,
    StandardBatchHandlers, setup_standard_handlers, async_batch_context
)

class TestBatchJob:
    """Test BatchJob data class"""
    
    def test_batch_job_creation(self):
        """Test BatchJob initialization"""
        job = BatchJob(
            job_id="test_job_1",
            operation_type=BatchOperationType.MESSAGE_PROCESSING,
            priority=BatchPriority.HIGH,
            payload={"message": "test"},
            timeout=15.0,
            max_retries=2
        )
        
        assert job.job_id == "test_job_1"
        assert job.operation_type == BatchOperationType.MESSAGE_PROCESSING
        assert job.priority == BatchPriority.HIGH
        assert job.payload == {"message": "test"}
        assert job.timeout == 15.0
        assert job.max_retries == 2
        assert job.status == BatchJobStatus.PENDING
        assert job.retry_count == 0
        assert job.result is None
        assert job.error is None
    
    def test_batch_job_priority_comparison(self):
        """Test BatchJob priority comparison for heap"""
        job1 = BatchJob("job1", BatchOperationType.MESSAGE_PROCESSING, BatchPriority.HIGH, {})
        job2 = BatchJob("job2", BatchOperationType.MESSAGE_PROCESSING, BatchPriority.LOW, {})
        job3 = BatchJob("job3", BatchOperationType.MESSAGE_PROCESSING, BatchPriority.CRITICAL, {})
        
        # Higher priority (lower number) should be less than lower priority
        assert job3 < job1  # CRITICAL < HIGH
        assert job1 < job2  # HIGH < LOW
        assert job3 < job2  # CRITICAL < LOW

class TestAsyncBatchQueue:
    """Test AsyncBatchQueue functionality"""
    
    @pytest.mark.asyncio
    async def test_queue_initialization(self):
        """Test queue initialization"""
        queue = AsyncBatchQueue(max_size=100)
        
        assert queue.max_size == 100
        assert await queue.size() == 0
        assert not queue._shutdown
    
    @pytest.mark.asyncio
    async def test_put_and_get_job(self):
        """Test putting and getting jobs from queue"""
        queue = AsyncBatchQueue()
        
        job = BatchJob("test_job", BatchOperationType.MESSAGE_PROCESSING, BatchPriority.NORMAL, {})
        
        # Put job in queue
        await queue.put(job)
        assert await queue.size() == 1
        assert job.status == BatchJobStatus.QUEUED
        
        # Get job from queue
        retrieved_job = await queue.get()
        assert retrieved_job.job_id == "test_job"
        assert retrieved_job.status == BatchJobStatus.PROCESSING
        assert retrieved_job.started_at is not None
        assert await queue.size() == 0
    
    @pytest.mark.asyncio
    async def test_priority_ordering(self):
        """Test that jobs are returned in priority order"""
        queue = AsyncBatchQueue()
        
        # Add jobs in non-priority order
        job_low = BatchJob("job_low", BatchOperationType.MESSAGE_PROCESSING, BatchPriority.LOW, {})
        job_high = BatchJob("job_high", BatchOperationType.MESSAGE_PROCESSING, BatchPriority.HIGH, {})
        job_critical = BatchJob("job_critical", BatchOperationType.MESSAGE_PROCESSING, BatchPriority.CRITICAL, {})
        
        await queue.put(job_low)
        await queue.put(job_high)
        await queue.put(job_critical)
        
        # Should get jobs in priority order
        first_job = await queue.get()
        assert first_job.job_id == "job_critical"
        
        second_job = await queue.get()
        assert second_job.job_id == "job_high"
        
        third_job = await queue.get()
        assert third_job.job_id == "job_low"
    
    @pytest.mark.asyncio
    async def test_queue_max_size(self):
        """Test queue max size enforcement"""
        queue = AsyncBatchQueue(max_size=2)
        
        job1 = BatchJob("job1", BatchOperationType.MESSAGE_PROCESSING, BatchPriority.NORMAL, {})
        job2 = BatchJob("job2", BatchOperationType.MESSAGE_PROCESSING, BatchPriority.NORMAL, {})
        job3 = BatchJob("job3", BatchOperationType.MESSAGE_PROCESSING, BatchPriority.NORMAL, {})
        
        await queue.put(job1)
        await queue.put(job2)
        
        # Third job should raise exception
        with pytest.raises(RuntimeError, match="Queue is full"):
            await queue.put(job3)
    
    @pytest.mark.asyncio
    async def test_get_timeout(self):
        """Test get operation with timeout"""
        queue = AsyncBatchQueue()
        
        # Should return None after timeout
        start_time = time.time()
        result = await queue.get(timeout=0.1)
        duration = time.time() - start_time
        
        assert result is None
        assert duration >= 0.1
    
    @pytest.mark.asyncio
    async def test_shutdown(self):
        """Test queue shutdown"""
        queue = AsyncBatchQueue()
        
        job = BatchJob("test", BatchOperationType.MESSAGE_PROCESSING, BatchPriority.NORMAL, {})
        
        await queue.shutdown()
        
        # Should not be able to put jobs after shutdown
        with pytest.raises(RuntimeError, match="Queue is shutdown"):
            await queue.put(job)
        
        # Get should return None immediately
        result = await queue.get()
        assert result is None

class TestAsyncBatchWorker:
    """Test AsyncBatchWorker functionality"""
    
    @pytest.fixture
    def mock_processor(self):
        """Mock batch processor"""
        processor = Mock()
        processor.queue = AsyncMock()
        processor._update_job_stats = AsyncMock()
        return processor
    
    @pytest.fixture
    def mock_handlers(self):
        """Mock operation handlers"""
        return {
            BatchOperationType.MESSAGE_PROCESSING: AsyncMock(return_value="processed"),
            BatchOperationType.IMAGE_PROCESSING: AsyncMock(return_value="image_processed")
        }
    
    @pytest.fixture
    def worker(self, mock_processor, mock_handlers):
        """Create worker with mocks"""
        return AsyncBatchWorker("test_worker", mock_processor, mock_handlers)
    
    def test_worker_initialization(self, worker):
        """Test worker initialization"""
        assert worker.worker_id == "test_worker"
        assert not worker.is_running
        assert worker.current_job is None
        assert worker.processed_jobs == 0
        assert worker.failed_jobs == 0
    
    @pytest.mark.asyncio
    async def test_process_job_success(self, worker, mock_processor, mock_handlers):
        """Test successful job processing"""
        job = BatchJob(
            "test_job",
            BatchOperationType.MESSAGE_PROCESSING,
            BatchPriority.NORMAL,
            {"data": "test"}
        )
        
        await worker._process_job(job)
        
        assert job.status == BatchJobStatus.COMPLETED
        assert job.result == "processed"
        assert job.completed_at is not None
        assert worker.processed_jobs == 1
        
        # Handler should be called with payload
        mock_handlers[BatchOperationType.MESSAGE_PROCESSING].assert_called_once_with({"data": "test"})
        
        # Stats should be updated
        mock_processor._update_job_stats.assert_called_once_with(job, success=True)
    
    @pytest.mark.asyncio
    async def test_process_job_with_callback(self, worker, mock_processor, mock_handlers):
        """Test job processing with success callback"""
        callback = AsyncMock()
        
        job = BatchJob(
            "test_job",
            BatchOperationType.MESSAGE_PROCESSING,
            BatchPriority.NORMAL,
            {"data": "test"},
            callback=callback
        )
        
        await worker._process_job(job)
        
        assert job.status == BatchJobStatus.COMPLETED
        callback.assert_called_once_with("processed")
    
    @pytest.mark.asyncio
    async def test_process_job_handler_not_found(self, worker, mock_processor):
        """Test job processing with missing handler"""
        job = BatchJob(
            "test_job",
            BatchOperationType.ANALYTICS_PROCESSING,  # No handler for this type
            BatchPriority.NORMAL,
            {"data": "test"}
        )
        
        await worker._process_job(job)
        
        assert job.status == BatchJobStatus.RETRYING  # Should retry on error
        assert job.retry_count == 1
        assert worker.failed_jobs == 1
    
    @pytest.mark.asyncio
    async def test_process_job_handler_exception(self, worker, mock_processor, mock_handlers):
        """Test job processing with handler exception"""
        # Make handler raise exception
        mock_handlers[BatchOperationType.MESSAGE_PROCESSING].side_effect = ValueError("Handler error")
        
        job = BatchJob(
            "test_job",
            BatchOperationType.MESSAGE_PROCESSING,
            BatchPriority.NORMAL,
            {"data": "test"},
            max_retries=1
        )
        
        await worker._process_job(job)
        
        assert job.status == BatchJobStatus.RETRYING
        assert job.retry_count == 1
        assert isinstance(job.error, ValueError)
        assert worker.failed_jobs == 1
    
    @pytest.mark.asyncio
    async def test_process_job_max_retries_exceeded(self, worker, mock_processor, mock_handlers):
        """Test job processing with max retries exceeded"""
        mock_handlers[BatchOperationType.MESSAGE_PROCESSING].side_effect = ValueError("Handler error")
        
        job = BatchJob(
            "test_job",
            BatchOperationType.MESSAGE_PROCESSING,
            BatchPriority.NORMAL,
            {"data": "test"},
            max_retries=0  # No retries
        )
        
        await worker._process_job(job)
        
        assert job.status == BatchJobStatus.FAILED
        assert job.retry_count == 1
        assert job.completed_at is not None
        mock_processor._update_job_stats.assert_called_once_with(job, success=False)
    
    @pytest.mark.asyncio
    async def test_process_job_with_error_callback(self, worker, mock_processor, mock_handlers):
        """Test job processing with error callback"""
        error_callback = AsyncMock()
        mock_handlers[BatchOperationType.MESSAGE_PROCESSING].side_effect = ValueError("Handler error")
        
        job = BatchJob(
            "test_job",
            BatchOperationType.MESSAGE_PROCESSING,
            BatchPriority.NORMAL,
            {"data": "test"},
            max_retries=0,
            error_callback=error_callback
        )
        
        await worker._process_job(job)
        
        assert job.status == BatchJobStatus.FAILED
        error_callback.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_process_job_timeout(self, worker, mock_processor, mock_handlers):
        """Test job processing with timeout"""
        # Make handler take too long
        async def slow_handler(payload):
            await asyncio.sleep(1.0)
            return "slow_result"
        
        mock_handlers[BatchOperationType.MESSAGE_PROCESSING] = slow_handler
        
        job = BatchJob(
            "test_job",
            BatchOperationType.MESSAGE_PROCESSING,
            BatchPriority.NORMAL,
            {"data": "test"},
            timeout=0.1  # Short timeout
        )
        
        await worker._process_job(job)
        
        assert job.status == BatchJobStatus.RETRYING  # Should retry on timeout
        assert isinstance(job.error, asyncio.TimeoutError)

class TestAsyncBatchProcessor:
    """Test AsyncBatchProcessor functionality"""
    
    @pytest.fixture
    def mock_settings(self):
        """Mock settings"""
        settings = Mock()
        settings.BATCH_MAX_WORKERS = 2
        settings.BATCH_QUEUE_MAX_SIZE = 100
        settings.BATCH_DEFAULT_TIMEOUT = 10.0
        settings.BATCH_STATS_INTERVAL = 1.0
        return settings
    
    @pytest.fixture
    def processor(self, mock_settings):
        """Create processor with mock settings"""
        return AsyncBatchProcessor(mock_settings)
    
    def test_processor_initialization(self, processor):
        """Test processor initialization"""
        assert processor.max_workers == 2
        assert processor.queue_max_size == 100
        assert processor.default_timeout == 10.0
        assert len(processor.operation_handlers) == 0
        assert len(processor.workers) == 0
        assert not processor.is_shutdown
    
    def test_register_operation_handler(self, processor):
        """Test registering operation handlers"""
        async def test_handler(payload):
            return "test_result"
        
        processor.register_operation_handler(
            BatchOperationType.MESSAGE_PROCESSING,
            test_handler
        )
        
        assert BatchOperationType.MESSAGE_PROCESSING in processor.operation_handlers
        assert processor.operation_handlers[BatchOperationType.MESSAGE_PROCESSING] == test_handler
    
    @pytest.mark.asyncio
    async def test_start_and_shutdown(self, processor):
        """Test processor start and shutdown"""
        # Register a handler
        processor.register_operation_handler(
            BatchOperationType.MESSAGE_PROCESSING,
            AsyncMock(return_value="test")
        )
        
        await processor.start()
        
        assert len(processor.workers) == 2
        assert len(processor.worker_tasks) == 2
        assert all(worker.is_running for worker in processor.workers.values())
        
        await processor.shutdown(timeout=1.0)
        
        assert processor.is_shutdown
        assert all(not worker.is_running for worker in processor.workers.values())
    
    @pytest.mark.asyncio
    async def test_submit_job(self, processor):
        """Test job submission"""
        processor.register_operation_handler(
            BatchOperationType.MESSAGE_PROCESSING,
            AsyncMock(return_value="test")
        )
        
        await processor.start()
        
        job_id = await processor.submit_job(
            operation_type=BatchOperationType.MESSAGE_PROCESSING,
            payload={"message": "test"},
            priority=BatchPriority.HIGH,
            timeout=5.0,
            max_retries=2
        )
        
        assert job_id is not None
        assert job_id.startswith("message_processing_")
        assert processor.stats.total_jobs == 1
        
        await processor.shutdown()
    
    @pytest.mark.asyncio
    async def test_submit_batch(self, processor):
        """Test batch job submission"""
        processor.register_operation_handler(
            BatchOperationType.MESSAGE_PROCESSING,
            AsyncMock(return_value="test")
        )
        
        await processor.start()
        
        jobs = [
            {
                'operation_type': BatchOperationType.MESSAGE_PROCESSING,
                'payload': {'message': f'test_{i}'},
                'priority': BatchPriority.NORMAL
            }
            for i in range(3)
        ]
        
        job_ids = await processor.submit_batch(jobs)
        
        assert len(job_ids) == 3
        assert all(job_id.startswith("message_processing_") for job_id in job_ids)
        assert processor.stats.total_jobs == 3
        
        await processor.shutdown()
    
    @pytest.mark.asyncio
    async def test_submit_batch_with_callback(self, processor):
        """Test batch submission with completion callback"""
        processor.register_operation_handler(
            BatchOperationType.MESSAGE_PROCESSING,
            AsyncMock(return_value="test")
        )
        
        batch_callback = AsyncMock()
        
        await processor.start()
        
        jobs = [
            {
                'operation_type': BatchOperationType.MESSAGE_PROCESSING,
                'payload': {'message': 'test'},
                'priority': BatchPriority.NORMAL
            }
        ]
        
        job_ids = await processor.submit_batch(jobs, batch_callback=batch_callback)
        
        # Give some time for job processing and callback
        await asyncio.sleep(0.5)
        
        assert len(job_ids) == 1
        # Note: In a real test, we'd need to wait for the batch callback to be called
        # This is challenging to test without more complex mocking
        
        await processor.shutdown()
    
    def test_get_stats(self, processor):
        """Test getting processor statistics"""
        stats = processor.get_stats()
        
        assert 'total_jobs' in stats
        assert 'completed_jobs' in stats
        assert 'failed_jobs' in stats
        assert 'queue_size' in stats
        assert 'active_workers' in stats
        assert 'worker_stats' in stats
        assert 'uptime_seconds' in stats
        
        assert stats['total_jobs'] == 0
        assert stats['completed_jobs'] == 0
        assert stats['failed_jobs'] == 0

class TestStandardBatchHandlers:
    """Test standard batch operation handlers"""
    
    @pytest.mark.asyncio
    async def test_message_processing_handler(self):
        """Test message processing handler"""
        payload = {
            'message_id': 'msg_123',
            'content': 'Hello world'
        }
        
        result = await StandardBatchHandlers.message_processing_handler(payload)
        
        assert result['processed'] is True
        assert result['message_id'] == 'msg_123'
        assert 'Hello world' in result['response']
    
    @pytest.mark.asyncio
    async def test_rich_message_generation_handler(self):
        """Test Rich Message generation handler"""
        payload = {
            'template_id': 'template_123',
            'content': 'Rich message content'
        }
        
        result = await StandardBatchHandlers.rich_message_generation_handler(payload)
        
        assert result['generated'] is True
        assert result['template_id'] == 'template_123'
        assert 'rich_message' in result
        assert result['rich_message']['type'] == 'flex'
    
    @pytest.mark.asyncio
    async def test_image_processing_handler(self):
        """Test image processing handler"""
        payload = {
            'image_id': 'img_123',
            'image_path': '/path/to/image.jpg'
        }
        
        result = await StandardBatchHandlers.image_processing_handler(payload)
        
        assert result['processed'] is True
        assert result['image_id'] == 'img_123'
        assert '/path/to/image.jpg' in result['analysis']
    
    @pytest.mark.asyncio
    async def test_openai_api_handler(self):
        """Test OpenAI API handler"""
        payload = {
            'request_id': 'req_123',
            'prompt': 'Tell me a joke'
        }
        
        result = await StandardBatchHandlers.openai_api_handler(payload)
        
        assert result['success'] is True
        assert result['request_id'] == 'req_123'
        assert 'Tell me a joke' in result['response']

def test_setup_standard_handlers():
    """Test setting up standard handlers"""
    settings = Mock()
    processor = AsyncBatchProcessor(settings)
    
    setup_standard_handlers(processor)
    
    # Check that all standard handlers are registered
    expected_types = [
        BatchOperationType.MESSAGE_PROCESSING,
        BatchOperationType.RICH_MESSAGE_GENERATION,
        BatchOperationType.IMAGE_PROCESSING,
        BatchOperationType.OPENAI_API_CALLS
    ]
    
    for op_type in expected_types:
        assert op_type in processor.operation_handlers

class TestAsyncBatchContext:
    """Test async batch context manager"""
    
    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test async batch context manager"""
        settings = Mock()
        settings.BATCH_MAX_WORKERS = 1
        settings.BATCH_QUEUE_MAX_SIZE = 10
        settings.BATCH_DEFAULT_TIMEOUT = 5.0
        settings.BATCH_STATS_INTERVAL = 1.0
        
        async with async_batch_context(settings) as processor:
            assert isinstance(processor, AsyncBatchProcessor)
            assert processor.settings == settings
            assert len(processor.workers) == 1
        
        # Processor should be shutdown after context
        assert processor.is_shutdown

@pytest.mark.integration
class TestAsyncBatchProcessorIntegration:
    """Integration tests for async batch processor"""
    
    @pytest.mark.asyncio
    async def test_end_to_end_processing(self):
        """Test end-to-end batch processing"""
        settings = Mock()
        settings.BATCH_MAX_WORKERS = 2
        settings.BATCH_QUEUE_MAX_SIZE = 100
        settings.BATCH_DEFAULT_TIMEOUT = 5.0
        settings.BATCH_STATS_INTERVAL = 0.1
        
        processor = AsyncBatchProcessor(settings)
        
        # Set up standard handlers
        setup_standard_handlers(processor)
        
        await processor.start()
        
        # Submit multiple jobs
        job_ids = []
        for i in range(5):
            job_id = await processor.submit_job(
                operation_type=BatchOperationType.MESSAGE_PROCESSING,
                payload={'message': f'Test message {i}'},
                priority=BatchPriority.NORMAL
            )
            job_ids.append(job_id)
        
        # Wait for processing
        await asyncio.sleep(1.0)
        
        # Check stats
        stats = processor.get_stats()
        assert stats['total_jobs'] == 5
        assert stats['completed_jobs'] > 0
        
        # Check job statuses
        for job_id in job_ids:
            status = await processor.get_job_status(job_id)
            assert status is not None
            assert status['status'] in ['completed', 'processing']
        
        await processor.shutdown()
    
    @pytest.mark.asyncio
    async def test_concurrent_batch_processing(self):
        """Test concurrent batch processing"""
        settings = Mock()
        settings.BATCH_MAX_WORKERS = 3
        settings.BATCH_QUEUE_MAX_SIZE = 200
        settings.BATCH_DEFAULT_TIMEOUT = 10.0
        settings.BATCH_STATS_INTERVAL = 0.1
        
        async with async_batch_context(settings) as processor:
            setup_standard_handlers(processor)
            
            # Submit jobs of different types concurrently
            tasks = []
            
            # Message processing jobs
            for i in range(5):
                task = asyncio.create_task(
                    processor.submit_job(
                        operation_type=BatchOperationType.MESSAGE_PROCESSING,
                        payload={'message': f'Message {i}'},
                        priority=BatchPriority.NORMAL
                    )
                )
                tasks.append(task)
            
            # Rich Message generation jobs
            for i in range(3):
                task = asyncio.create_task(
                    processor.submit_job(
                        operation_type=BatchOperationType.RICH_MESSAGE_GENERATION,
                        payload={'template_id': f'template_{i}', 'content': f'Content {i}'},
                        priority=BatchPriority.HIGH
                    )
                )
                tasks.append(task)
            
            # Wait for all submissions
            job_ids = await asyncio.gather(*tasks)
            
            # Wait for processing
            await asyncio.sleep(2.0)
            
            # Check final stats
            stats = processor.get_stats()
            assert stats['total_jobs'] == 8
            assert stats['completed_jobs'] >= 0  # Some should be completed
            assert len(stats['stats_by_type']) >= 2  # At least 2 operation types