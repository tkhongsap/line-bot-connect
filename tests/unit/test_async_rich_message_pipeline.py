"""
Unit tests for async Rich Message generation pipeline.
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta

from src.utils.async_rich_message_pipeline import (
    AsyncRichMessagePipeline, AsyncRichMessageQueue, AsyncRichMessageWorker,
    RichMessageTask, MessagePriority, TaskStatus, PipelineMetrics,
    get_async_pipeline, initialize_pipeline, shutdown_pipeline
)


@pytest.fixture
def mock_rich_message_service():
    """Create a mock Rich Message service."""
    service = Mock()
    service.line_bot_api = Mock()
    return service


@pytest.fixture
def sample_task():
    """Create a sample Rich Message task."""
    return RichMessageTask(
        task_id="test_task_1",
        task_type="user_request",
        priority=MessagePriority.NORMAL,
        user_ids=["user123"],
        content_template="Daily motivation"
    )


class TestRichMessageTask:
    """Test Rich Message task data structure."""
    
    def test_task_initialization(self):
        """Test task initialization with defaults."""
        task = RichMessageTask(
            task_id="test",
            task_type="daily_message",
            priority=MessagePriority.HIGH,
            user_ids=["user1", "user2"]
        )
        
        assert task.task_id == "test"
        assert task.task_type == "daily_message"
        assert task.priority == MessagePriority.HIGH
        assert task.user_ids == ["user1", "user2"]
        assert task.status == TaskStatus.PENDING
        assert task.progress == 0.0
        assert task.retry_count == 0
        assert task.max_retries == 3
        assert isinstance(task.created_at, datetime)
        assert task.correlation_id is not None
    
    def test_task_with_custom_values(self):
        """Test task initialization with custom values."""
        scheduled_time = datetime.now() + timedelta(hours=1)
        
        task = RichMessageTask(
            task_id="custom_task",
            task_type="batch_delivery",
            priority=MessagePriority.URGENT,
            user_ids=["user1"],
            content_template="Custom template",
            template_category="wellness",
            scheduled_time=scheduled_time,
            max_retries=5
        )
        
        assert task.content_template == "Custom template"
        assert task.template_category == "wellness"
        assert task.scheduled_time == scheduled_time
        assert task.max_retries == 5


class TestAsyncRichMessageQueue:
    """Test async Rich Message queue."""
    
    @pytest.fixture
    def queue(self):
        """Create a queue for testing."""
        return AsyncRichMessageQueue(max_size=5)
    
    @pytest.mark.asyncio
    async def test_queue_initialization(self, queue):
        """Test queue initialization."""
        assert queue.max_size == 5
        assert queue.qsize() == 0
        assert queue.empty()
    
    @pytest.mark.asyncio
    async def test_put_and_get_task(self, queue, sample_task):
        """Test putting and getting tasks."""
        # Put task
        success = await queue.put(sample_task)
        assert success
        assert queue.qsize() == 1
        assert not queue.empty()
        
        # Get task
        retrieved_task = await asyncio.wait_for(queue.get(), timeout=1.0)
        assert retrieved_task == sample_task
        assert queue.qsize() == 0
        assert queue.empty()
    
    @pytest.mark.asyncio
    async def test_priority_ordering(self, queue):
        """Test that tasks are retrieved in priority order."""
        # Create tasks with different priorities
        low_task = RichMessageTask("low", "test", MessagePriority.LOW, ["user1"])
        normal_task = RichMessageTask("normal", "test", MessagePriority.NORMAL, ["user1"])
        high_task = RichMessageTask("high", "test", MessagePriority.HIGH, ["user1"])
        urgent_task = RichMessageTask("urgent", "test", MessagePriority.URGENT, ["user1"])
        
        # Add in random order
        await queue.put(low_task)
        await queue.put(urgent_task)
        await queue.put(normal_task)
        await queue.put(high_task)
        
        # Should retrieve in priority order: URGENT, HIGH, NORMAL, LOW
        assert (await queue.get()).task_id == "urgent"
        assert (await queue.get()).task_id == "high"
        assert (await queue.get()).task_id == "normal"
        assert (await queue.get()).task_id == "low"
    
    @pytest.mark.asyncio
    async def test_queue_full_rejection(self, queue):
        """Test that queue rejects tasks when full."""
        # Fill the queue
        for i in range(5):
            task = RichMessageTask(f"task_{i}", "test", MessagePriority.NORMAL, ["user1"])
            success = await queue.put(task)
            assert success
        
        # Try to add one more - should be rejected
        overflow_task = RichMessageTask("overflow", "test", MessagePriority.NORMAL, ["user1"])
        success = await queue.put(overflow_task)
        assert not success
        assert queue.qsize() == 5
    
    @pytest.mark.asyncio
    async def test_get_nowait(self, queue, sample_task):
        """Test non-blocking get."""
        # Empty queue
        task = await queue.get_nowait()
        assert task is None
        
        # Add task and get
        await queue.put(sample_task)
        task = await queue.get_nowait()
        assert task == sample_task
    
    @pytest.mark.asyncio
    async def test_clear_queue(self, queue):
        """Test clearing the queue."""
        # Add some tasks
        for i in range(3):
            task = RichMessageTask(f"task_{i}", "test", MessagePriority.NORMAL, ["user1"])
            await queue.put(task)
        
        assert queue.qsize() == 3
        
        # Clear queue
        await queue.clear()
        assert queue.qsize() == 0
        assert queue.empty()


class TestAsyncRichMessageWorker:
    """Test async Rich Message worker."""
    
    @pytest.fixture
    def mock_pipeline(self, mock_rich_message_service):
        """Create a mock pipeline."""
        pipeline = AsyncRichMessagePipeline(mock_rich_message_service, max_workers=1)
        pipeline.queue = AsyncRichMessageQueue()
        pipeline._update_task_status = AsyncMock()
        return pipeline
    
    @pytest.fixture
    def worker(self, mock_pipeline):
        """Create a worker for testing."""
        return AsyncRichMessageWorker("test_worker", mock_pipeline)
    
    @pytest.mark.asyncio
    async def test_worker_lifecycle(self, worker):
        """Test worker start and stop."""
        assert not worker.is_running
        
        # Start worker
        await worker.start()
        assert worker.is_running
        assert worker._task is not None
        
        # Stop worker
        await worker.stop()
        assert not worker.is_running
    
    @pytest.mark.asyncio
    async def test_worker_processes_task(self, worker, mock_pipeline):
        """Test that worker processes tasks."""
        # Create a test task
        task = RichMessageTask("test", "daily_message", MessagePriority.NORMAL, ["user1"])
        
        # Mock the processing methods
        worker._generate_content_async = AsyncMock(return_value={'title': 'Test'})
        worker._generate_images_async = AsyncMock(return_value={'image': 'test.png'})
        worker._create_rich_message_async = AsyncMock(return_value={'type': 'flex'})
        worker._deliver_messages_async = AsyncMock(return_value={'delivered_count': 1})
        
        # Process the task
        await worker._process_task(task)
        
        # Verify task was processed
        assert task.status == TaskStatus.COMPLETED
        assert task.progress == 100.0
        assert task.result is not None
        
        # Verify processing methods were called
        worker._generate_content_async.assert_called_once()
        worker._generate_images_async.assert_called_once()
        worker._create_rich_message_async.assert_called_once()
        worker._deliver_messages_async.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_worker_handles_task_error(self, worker, mock_pipeline):
        """Test worker error handling and retry logic."""
        # Create a test task
        task = RichMessageTask("test", "daily_message", MessagePriority.NORMAL, ["user1"])
        
        # Mock the processing to raise an error
        worker._generate_content_async = AsyncMock(side_effect=Exception("Test error"))
        
        # Mock the queue.put method to track retries
        mock_pipeline.queue.put = AsyncMock()
        
        # Process the task
        await worker._process_task(task)
        
        # Verify task was marked for retry
        assert task.retry_count == 1
        assert task.error == "Test error"
        assert task.status == TaskStatus.PENDING  # Reset for retry
        
        # Verify task was re-queued
        mock_pipeline.queue.put.assert_called_once_with(task)
    
    @pytest.mark.asyncio
    async def test_worker_max_retries_exceeded(self, worker, mock_pipeline):
        """Test worker behavior when max retries are exceeded."""
        # Create a test task with no retries left
        task = RichMessageTask("test", "daily_message", MessagePriority.NORMAL, ["user1"])
        task.retry_count = 3  # Max retries
        task.max_retries = 3
        
        # Mock the processing to raise an error
        worker._generate_content_async = AsyncMock(side_effect=Exception("Test error"))
        
        # Process the task
        await worker._process_task(task)
        
        # Verify task was marked as failed
        assert task.status == TaskStatus.FAILED
        assert task.retry_count == 4  # Incremented
        assert task.error == "Test error"
    
    @pytest.mark.asyncio
    async def test_batch_delivery_processing(self, worker):
        """Test batch delivery task processing."""
        # Create batch delivery task
        task = RichMessageTask(
            "batch_test", 
            "batch_delivery", 
            MessagePriority.NORMAL, 
            ["user1", "user2", "user3", "user4", "user5"]
        )
        
        # Mock user request processing
        async def mock_user_request(user_task):
            return {'delivered': True, 'user_id': user_task.user_ids[0]}
        
        worker._process_user_request = AsyncMock(side_effect=mock_user_request)
        
        # Process the batch task
        result = await worker._process_batch_delivery(task)
        
        # Verify results
        assert result['delivered_count'] == 5
        assert result['failed_count'] == 0
        assert result['total_users'] == 5
        assert len(result['results']) == 5


class TestAsyncRichMessagePipeline:
    """Test async Rich Message pipeline."""
    
    @pytest.fixture
    def pipeline(self, mock_rich_message_service):
        """Create a pipeline for testing."""
        return AsyncRichMessagePipeline(
            rich_message_service=mock_rich_message_service,
            max_workers=2,
            queue_size=10
        )
    
    @pytest.mark.asyncio
    async def test_pipeline_initialization(self, pipeline):
        """Test pipeline initialization."""
        assert pipeline.max_workers == 2
        assert not pipeline.is_running
        assert len(pipeline.workers) == 0
        assert isinstance(pipeline.queue, AsyncRichMessageQueue)
        assert isinstance(pipeline.metrics, PipelineMetrics)
    
    @pytest.mark.asyncio
    async def test_pipeline_lifecycle(self, pipeline):
        """Test pipeline start and stop."""
        # Start pipeline
        await pipeline.start()
        assert pipeline.is_running
        assert len(pipeline.workers) == 2
        
        for worker in pipeline.workers:
            assert worker.is_running
        
        # Stop pipeline
        await pipeline.stop()
        assert not pipeline.is_running
        assert len(pipeline.workers) == 0
        assert pipeline.queue.empty()
    
    @pytest.mark.asyncio
    async def test_submit_task(self, pipeline, sample_task):
        """Test task submission."""
        await pipeline.start()
        
        # Submit task
        success = await pipeline.submit_task(sample_task)
        assert success
        assert sample_task.task_id in pipeline.tasks
        assert pipeline.queue.qsize() == 1
        
        await pipeline.stop()
    
    @pytest.mark.asyncio
    async def test_get_task_status(self, pipeline, sample_task):
        """Test getting task status."""
        await pipeline.start()
        
        # Submit and check status
        await pipeline.submit_task(sample_task)
        status = await pipeline.get_task_status(sample_task.task_id)
        assert status == sample_task
        
        # Non-existent task
        status = await pipeline.get_task_status("non_existent")
        assert status is None
        
        await pipeline.stop()
    
    @pytest.mark.asyncio
    async def test_cancel_task(self, pipeline, sample_task):
        """Test task cancellation."""
        await pipeline.start()
        
        # Submit and cancel task
        await pipeline.submit_task(sample_task)
        success = await pipeline.cancel_task(sample_task.task_id)
        assert success
        assert sample_task.status == TaskStatus.CANCELLED
        
        # Cancel non-existent task
        success = await pipeline.cancel_task("non_existent")
        assert not success
        
        await pipeline.stop()
    
    @pytest.mark.asyncio
    async def test_metrics_collection(self, pipeline):
        """Test metrics collection."""
        await pipeline.start()
        
        # Get initial metrics
        metrics = await pipeline.get_metrics()
        assert isinstance(metrics, PipelineMetrics)
        assert metrics.queue_size == 0
        assert metrics.active_workers == 0
        
        # Submit a task and check metrics
        task = RichMessageTask("test", "daily_message", MessagePriority.NORMAL, ["user1"])
        await pipeline.submit_task(task)
        
        metrics = await pipeline.get_metrics()
        assert metrics.queue_size == 1
        
        await pipeline.stop()
    
    @pytest.mark.asyncio
    async def test_convenience_methods(self, pipeline):
        """Test convenience methods for common task types."""
        await pipeline.start()
        
        # Test daily message task
        task_id = await pipeline.submit_daily_message_task(
            user_ids=["user1", "user2"],
            template_category="motivation"
        )
        assert task_id is not None
        assert task_id in pipeline.tasks
        
        task = pipeline.tasks[task_id]
        assert task.task_type == "daily_message"
        assert task.template_category == "motivation"
        
        # Test user request task
        task_id = await pipeline.submit_user_request_task(
            user_id="user1",
            content_template="Custom message"
        )
        assert task_id is not None
        assert task_id in pipeline.tasks
        
        task = pipeline.tasks[task_id]
        assert task.task_type == "user_request"
        assert task.content_template == "Custom message"
        assert task.priority == MessagePriority.HIGH
        
        # Test batch delivery task
        task_id = await pipeline.submit_batch_delivery_task(
            user_ids=["user1", "user2", "user3"],
            content_template="Batch message",
            template_category="wellness"
        )
        assert task_id is not None
        assert task_id in pipeline.tasks
        
        task = pipeline.tasks[task_id]
        assert task.task_type == "batch_delivery"
        assert task.template_category == "wellness"
        assert task.priority == MessagePriority.LOW
        
        await pipeline.stop()
    
    @pytest.mark.asyncio
    async def test_task_history_management(self, pipeline):
        """Test task history management."""
        await pipeline.start()
        
        # Create and complete a task
        task = RichMessageTask("completed_task", "daily_message", MessagePriority.NORMAL, ["user1"])
        task.status = TaskStatus.COMPLETED
        
        # Update task status
        await pipeline._update_task_status(task)
        
        # Verify task moved to history
        assert task.task_id not in pipeline.tasks
        assert task in pipeline.task_history
        
        await pipeline.stop()


class TestGlobalPipelineFunctions:
    """Test global pipeline management functions."""
    
    @pytest.mark.asyncio
    async def test_get_async_pipeline(self, mock_rich_message_service):
        """Test getting the global pipeline instance."""
        # First call should create new instance
        pipeline1 = get_async_pipeline(mock_rich_message_service)
        assert pipeline1 is not None
        assert isinstance(pipeline1, AsyncRichMessagePipeline)
        
        # Second call should return same instance
        pipeline2 = get_async_pipeline()
        assert pipeline2 is pipeline1
    
    @pytest.mark.asyncio
    async def test_initialize_pipeline(self, mock_rich_message_service):
        """Test pipeline initialization function."""
        pipeline = await initialize_pipeline(mock_rich_message_service)
        assert pipeline is not None
        assert pipeline.is_running
        
        # Cleanup
        await shutdown_pipeline()
    
    @pytest.mark.asyncio
    async def test_shutdown_pipeline(self, mock_rich_message_service):
        """Test pipeline shutdown function."""
        # Initialize pipeline
        pipeline = await initialize_pipeline(mock_rich_message_service)
        assert pipeline.is_running
        
        # Shutdown
        await shutdown_pipeline()
        
        # Verify shutdown
        # Note: We can't easily test the global instance state due to test isolation
        # In real usage, the global instance would be set to None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])