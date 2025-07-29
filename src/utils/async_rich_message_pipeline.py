"""
Async Rich Message Generation Pipeline with Queue Management

This module provides asynchronous processing capabilities for Rich Message
generation, delivery, and batch operations with comprehensive queue management.
"""

import asyncio
import aiofiles
import logging
import time
import json
from typing import Dict, List, Optional, Any, Tuple, Union, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
from collections import defaultdict
import concurrent.futures
import threading
from pathlib import Path

from src.utils.async_image_processor import AsyncImageProcessor
from src.utils.connection_pool import connection_pool_manager
from src.exceptions import (
    DataProcessingException, NetworkException, TimeoutException,
    create_correlation_id, BaseBotException
)
from src.utils.error_handler import StructuredLogger, error_handler

logger = StructuredLogger(__name__)


class MessagePriority(Enum):
    """Priority levels for Rich Message generation tasks."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4


class TaskStatus(Enum):
    """Status of Rich Message generation tasks."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class RichMessageTask:
    """Represents a Rich Message generation task."""
    task_id: str
    task_type: str  # 'daily_message', 'user_request', 'batch_delivery', etc.
    priority: MessagePriority
    user_ids: List[str]
    content_template: Optional[str] = None
    template_category: Optional[str] = None
    scheduled_time: Optional[datetime] = None
    created_at: datetime = None
    status: TaskStatus = TaskStatus.PENDING
    progress: float = 0.0
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    correlation_id: Optional[str] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.correlation_id is None:
            self.correlation_id = create_correlation_id()


@dataclass
class PipelineMetrics:
    """Metrics for the async Rich Message pipeline."""
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    cancelled_tasks: int = 0
    avg_processing_time: float = 0.0
    queue_size: int = 0
    active_workers: int = 0
    throughput_per_minute: float = 0.0
    success_rate: float = 0.0
    last_updated: datetime = None
    
    def __post_init__(self):
        if self.last_updated is None:
            self.last_updated = datetime.now()


class AsyncRichMessageQueue:
    """Priority queue for Rich Message generation tasks."""
    
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self._queues = {
            MessagePriority.URGENT: asyncio.Queue(),
            MessagePriority.HIGH: asyncio.Queue(),
            MessagePriority.NORMAL: asyncio.Queue(),
            MessagePriority.LOW: asyncio.Queue()
        }
        self._size = 0
        self._lock = asyncio.Lock()
        self._condition = asyncio.Condition(self._lock)
    
    async def put(self, task: RichMessageTask) -> bool:
        """Add a task to the appropriate priority queue."""
        async with self._lock:
            if self._size >= self.max_size:
                logger.warning(f"Queue is full, rejecting task {task.task_id}")
                return False
            
            await self._queues[task.priority].put(task)
            self._size += 1
            
            logger.debug(f"Added task {task.task_id} to {task.priority.name} queue")
            self._condition.notify()
            return True
    
    async def get(self) -> Optional[RichMessageTask]:
        """Get the highest priority task from the queue."""
        async with self._lock:
            # Wait for tasks to be available
            while self._size == 0:
                await self._condition.wait()
            
            # Try to get task from highest priority queue first
            for priority in [MessagePriority.URGENT, MessagePriority.HIGH, 
                           MessagePriority.NORMAL, MessagePriority.LOW]:
                if not self._queues[priority].empty():
                    task = await self._queues[priority].get()
                    self._size -= 1
                    logger.debug(f"Retrieved task {task.task_id} from {priority.name} queue")
                    return task
            
            return None
    
    async def get_nowait(self) -> Optional[RichMessageTask]:
        """Get a task without waiting if queue is empty."""
        async with self._lock:
            if self._size == 0:
                return None
            
            for priority in [MessagePriority.URGENT, MessagePriority.HIGH, 
                           MessagePriority.NORMAL, MessagePriority.LOW]:
                if not self._queues[priority].empty():
                    task = self._queues[priority].get_nowait()
                    self._size -= 1
                    return task
            
            return None
    
    def qsize(self) -> int:
        """Get the total size of all queues."""
        return self._size
    
    def empty(self) -> bool:
        """Check if all queues are empty."""
        return self._size == 0
    
    async def clear(self):
        """Clear all queues."""
        async with self._lock:
            for queue in self._queues.values():
                while not queue.empty():
                    try:
                        queue.get_nowait()
                    except asyncio.QueueEmpty:
                        break
            self._size = 0
            logger.info("Cleared all task queues")


class AsyncRichMessageWorker:
    """Async worker for processing Rich Message generation tasks."""
    
    def __init__(self, worker_id: str, pipeline: 'AsyncRichMessagePipeline'):
        self.worker_id = worker_id
        self.pipeline = pipeline
        self.is_running = False
        self.current_task: Optional[RichMessageTask] = None
        self.tasks_processed = 0
        self.start_time = datetime.now()
        self._task = None
    
    async def start(self):
        """Start the worker."""
        if self.is_running:
            return
        
        self.is_running = True
        self._task = asyncio.create_task(self._worker_loop())
        logger.info(f"Started async Rich Message worker {self.worker_id}")
    
    async def stop(self):
        """Stop the worker gracefully."""
        if not self.is_running:
            return
        
        self.is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        logger.info(f"Stopped async Rich Message worker {self.worker_id}")
    
    async def _worker_loop(self):
        """Main worker processing loop."""
        while self.is_running:
            try:
                # Get next task from queue
                task = await self.pipeline.queue.get()
                if not task:
                    await asyncio.sleep(0.1)
                    continue
                
                self.current_task = task
                
                # Process the task
                await self._process_task(task)
                
                self.tasks_processed += 1
                self.current_task = None
                
            except asyncio.CancelledError:
                logger.info(f"Worker {self.worker_id} cancelled")
                break
            except Exception as e:
                logger.error(f"Worker {self.worker_id} error: {e}")
                if self.current_task:
                    await self._handle_task_error(self.current_task, e)
                await asyncio.sleep(1)  # Brief pause on error
    
    async def _process_task(self, task: RichMessageTask):
        """Process a Rich Message generation task."""
        start_time = time.time()
        
        with logger.context(
            correlation_id=task.correlation_id,
            task_id=task.task_id,
            worker_id=self.worker_id
        ):
            logger.info(f"Processing Rich Message task {task.task_type}")
            
            try:
                # Update task status
                task.status = TaskStatus.PROCESSING
                await self.pipeline._update_task_status(task)
                
                # Route task to appropriate processor
                if task.task_type == 'daily_message':
                    result = await self._process_daily_message(task)
                elif task.task_type == 'user_request':
                    result = await self._process_user_request(task)
                elif task.task_type == 'batch_delivery':
                    result = await self._process_batch_delivery(task)
                else:
                    raise ValueError(f"Unknown task type: {task.task_type}")
                
                # Update task with results
                task.result = result
                task.status = TaskStatus.COMPLETED
                task.progress = 100.0
                
                processing_time = time.time() - start_time
                logger.info(
                    f"Completed Rich Message task in {processing_time:.2f}s",
                    extra_context={'processing_time': processing_time}
                )
                
            except Exception as e:
                await self._handle_task_error(task, e)
            finally:
                await self.pipeline._update_task_status(task)
    
    async def _process_daily_message(self, task: RichMessageTask) -> Dict[str, Any]:
        """Process a daily Rich Message generation task."""
        # Generate content using AI
        content_result = await self._generate_content_async(task)
        
        # Update progress
        task.progress = 30.0
        await self.pipeline._update_task_status(task)
        
        # Generate images
        image_result = await self._generate_images_async(task, content_result)
        
        # Update progress
        task.progress = 60.0
        await self.pipeline._update_task_status(task)
        
        # Create Rich Message
        rich_message = await self._create_rich_message_async(task, content_result, image_result)
        
        # Update progress
        task.progress = 80.0
        await self.pipeline._update_task_status(task)
        
        # Deliver messages
        delivery_result = await self._deliver_messages_async(task, rich_message)
        
        return {
            'content': content_result,
            'images': image_result,
            'rich_message': rich_message,
            'delivery': delivery_result
        }
    
    async def _process_user_request(self, task: RichMessageTask) -> Dict[str, Any]:
        """Process a user-requested Rich Message generation task."""
        # Similar to daily message but with user-specific content
        return await self._process_daily_message(task)
    
    async def _process_batch_delivery(self, task: RichMessageTask) -> Dict[str, Any]:
        """Process a batch delivery task."""
        delivered_count = 0
        failed_count = 0
        results = []
        
        # Process users in batches to avoid overwhelming APIs
        batch_size = 10
        user_batches = [task.user_ids[i:i + batch_size] 
                       for i in range(0, len(task.user_ids), batch_size)]
        
        for i, batch in enumerate(user_batches):
            try:
                # Create individual tasks for each user in batch
                batch_tasks = []
                for user_id in batch:
                    user_task = RichMessageTask(
                        task_id=f"{task.task_id}_batch_{i}_{user_id}",
                        task_type='user_request',
                        priority=MessagePriority.NORMAL,
                        user_ids=[user_id],
                        content_template=task.content_template,
                        template_category=task.template_category
                    )
                    batch_tasks.append(self._process_user_request(user_task))
                
                # Process batch concurrently
                batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
                
                # Collect results
                for result in batch_results:
                    if isinstance(result, Exception):
                        failed_count += 1
                        results.append({'error': str(result)})
                    else:
                        delivered_count += 1
                        results.append(result)
                
                # Update progress
                progress = ((i + 1) / len(user_batches)) * 100
                task.progress = progress
                await self.pipeline._update_task_status(task)
                
            except Exception as e:
                logger.error(f"Batch processing error: {e}")
                failed_count += len(batch)
        
        return {
            'delivered_count': delivered_count,
            'failed_count': failed_count,
            'total_users': len(task.user_ids),
            'results': results
        }
    
    async def _generate_content_async(self, task: RichMessageTask) -> Dict[str, Any]:
        """Generate content asynchronously."""
        # Use thread pool for CPU-bound content generation
        loop = asyncio.get_event_loop()
        
        def generate_content():
            # This would call the actual content generator
            # For now, return mock content
            return {
                'title': 'Daily Inspiration',
                'message': 'Today is a great day to learn something new!',
                'mood': 'motivational',
                'category': task.template_category or 'motivation'
            }
        
        with concurrent.futures.ThreadPoolExecutor() as executor:
            content = await loop.run_in_executor(executor, generate_content)
        
        return content
    
    async def _generate_images_async(self, task: RichMessageTask, content: Dict[str, Any]) -> Dict[str, Any]:
        """Generate images asynchronously."""
        # Use async image processor for image generation
        async_processor = AsyncImageProcessor()
        
        # This would generate template-based images
        # For now, return mock image data
        return {
            'background_image': '/static/backgrounds/motivation_bg.png',
            'composed_image': '/tmp/composed_message.png',
            'dimensions': {'width': 800, 'height': 600}
        }
    
    async def _create_rich_message_async(self, task: RichMessageTask, 
                                       content: Dict[str, Any], 
                                       images: Dict[str, Any]) -> Dict[str, Any]:
        """Create Rich Message structure asynchronously."""
        # This would create the actual LINE Flex Message
        # For now, return mock message structure
        return {
            'type': 'flex',
            'alt_text': content['title'],
            'contents': {
                'type': 'bubble',
                'hero': {
                    'type': 'image',
                    'url': images['composed_image'],
                    'size': 'full'
                },
                'body': {
                    'type': 'box',
                    'layout': 'vertical',
                    'contents': [
                        {
                            'type': 'text',
                            'text': content['title'],
                            'weight': 'bold',
                            'size': 'xl'
                        },
                        {
                            'type': 'text',
                            'text': content['message'],
                            'wrap': True
                        }
                    ]
                }
            }
        }
    
    async def _deliver_messages_async(self, task: RichMessageTask, 
                                    rich_message: Dict[str, Any]) -> Dict[str, Any]:
        """Deliver Rich Messages asynchronously."""
        delivered_count = 0
        failed_deliveries = []
        
        # Use connection pooling for delivery
        for user_id in task.user_ids:
            try:
                # This would use the LINE Bot API to send the message
                # For now, simulate delivery
                await asyncio.sleep(0.1)  # Simulate API call
                delivered_count += 1
                
            except Exception as e:
                failed_deliveries.append({
                    'user_id': user_id,
                    'error': str(e)
                })
        
        return {
            'delivered_count': delivered_count,
            'failed_count': len(failed_deliveries),
            'failed_deliveries': failed_deliveries
        }
    
    async def _handle_task_error(self, task: RichMessageTask, error: Exception):
        """Handle task processing errors with retry logic."""
        task.error = str(error)
        task.retry_count += 1
        
        if task.retry_count <= task.max_retries:
            # Retry with exponential backoff
            delay = min(2 ** task.retry_count, 60)  # Max 60 seconds
            logger.warning(
                f"Task {task.task_id} failed, retrying in {delay}s (attempt {task.retry_count}/{task.max_retries})"
            )
            
            # Reset status for retry
            task.status = TaskStatus.PENDING
            task.progress = 0.0
            
            # Re-queue the task after delay
            await asyncio.sleep(delay)
            await self.pipeline.queue.put(task)
        else:
            # Max retries exceeded
            task.status = TaskStatus.FAILED
            task.progress = 0.0
            logger.error(f"Task {task.task_id} failed after {task.max_retries} retries: {error}")


class AsyncRichMessagePipeline:
    """Main async Rich Message generation pipeline with queue management."""
    
    def __init__(self, 
                 rich_message_service: Any,
                 max_workers: int = 4,
                 queue_size: int = 1000,
                 enable_metrics: bool = True):
        """
        Initialize the async Rich Message pipeline.
        
        Args:
            rich_message_service: The Rich Message service instance
            max_workers: Maximum number of concurrent workers
            queue_size: Maximum queue size
            enable_metrics: Whether to collect metrics
        """
        self.rich_message_service = rich_message_service
        self.max_workers = max_workers
        self.enable_metrics = enable_metrics
        
        # Initialize queue and workers
        self.queue = AsyncRichMessageQueue(max_size=queue_size)
        self.workers: List[AsyncRichMessageWorker] = []
        self.is_running = False
        
        # Task tracking
        self.tasks: Dict[str, RichMessageTask] = {}
        self.task_history: List[RichMessageTask] = []
        self.max_history = 1000
        
        # Metrics
        self.metrics = PipelineMetrics()
        self.metrics_lock = asyncio.Lock()
        
        logger.info(f"Initialized async Rich Message pipeline with {max_workers} workers")
    
    async def start(self):
        """Start the pipeline and all workers."""
        if self.is_running:
            return
        
        self.is_running = True
        
        # Create and start workers
        for i in range(self.max_workers):
            worker = AsyncRichMessageWorker(f"worker_{i}", self)
            self.workers.append(worker)
            await worker.start()
        
        # Start metrics collection if enabled
        if self.enable_metrics:
            asyncio.create_task(self._metrics_collection_loop())
        
        logger.info(f"Started async Rich Message pipeline with {len(self.workers)} workers")
    
    async def stop(self):
        """Stop the pipeline and all workers gracefully."""
        if not self.is_running:
            return
        
        self.is_running = False
        
        # Stop all workers
        await asyncio.gather(*[worker.stop() for worker in self.workers])
        self.workers.clear()
        
        # Clear queues
        await self.queue.clear()
        
        logger.info("Stopped async Rich Message pipeline")
    
    async def submit_task(self, task: RichMessageTask) -> bool:
        """Submit a task to the pipeline."""
        if not self.is_running:
            raise RuntimeError("Pipeline is not running")
        
        # Store task for tracking
        self.tasks[task.task_id] = task
        
        # Add to queue
        success = await self.queue.put(task)
        
        if success:
            logger.info(f"Submitted task {task.task_id} to pipeline")
        else:
            logger.warning(f"Failed to submit task {task.task_id} - queue full")
        
        return success
    
    async def get_task_status(self, task_id: str) -> Optional[RichMessageTask]:
        """Get the status of a specific task."""
        return self.tasks.get(task_id)
    
    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a specific task."""
        task = self.tasks.get(task_id)
        if not task:
            return False
        
        task.status = TaskStatus.CANCELLED
        logger.info(f"Cancelled task {task_id}")
        return True
    
    async def get_metrics(self) -> PipelineMetrics:
        """Get current pipeline metrics."""
        async with self.metrics_lock:
            # Update current metrics
            self.metrics.queue_size = self.queue.qsize()
            self.metrics.active_workers = len([w for w in self.workers if w.current_task])
            
            # Calculate success rate
            if self.metrics.total_tasks > 0:
                self.metrics.success_rate = (self.metrics.completed_tasks / self.metrics.total_tasks) * 100
            
            self.metrics.last_updated = datetime.now()
            
            return self.metrics
    
    async def _update_task_status(self, task: RichMessageTask):
        """Update task status and metrics."""
        # Move completed/failed tasks to history
        if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
            # Add to history
            self.task_history.append(task)
            if len(self.task_history) > self.max_history:
                self.task_history.pop(0)
            
            # Remove from active tasks
            if task.task_id in self.tasks:
                del self.tasks[task.task_id]
            
            # Update metrics
            async with self.metrics_lock:
                if task.status == TaskStatus.COMPLETED:
                    self.metrics.completed_tasks += 1
                elif task.status == TaskStatus.FAILED:
                    self.metrics.failed_tasks += 1
                elif task.status == TaskStatus.CANCELLED:
                    self.metrics.cancelled_tasks += 1
    
    async def _metrics_collection_loop(self):
        """Background loop for collecting metrics."""
        while self.is_running:
            try:
                await asyncio.sleep(60)  # Update metrics every minute
                
                # Calculate throughput
                now = datetime.now()
                minute_ago = now - timedelta(minutes=1)
                
                recent_completions = len([
                    task for task in self.task_history
                    if task.status == TaskStatus.COMPLETED and task.created_at >= minute_ago
                ])
                
                async with self.metrics_lock:
                    self.metrics.throughput_per_minute = recent_completions
                    
                    # Calculate average processing time
                    completed_tasks = [t for t in self.task_history if t.status == TaskStatus.COMPLETED]
                    if completed_tasks:
                        processing_times = []
                        for task in completed_tasks[-100:]:  # Last 100 tasks
                            if task.result and 'processing_time' in task.result:
                                processing_times.append(task.result['processing_time'])
                        
                        if processing_times:
                            self.metrics.avg_processing_time = sum(processing_times) / len(processing_times)
                
            except Exception as e:
                logger.error(f"Metrics collection error: {e}")
    
    # Convenience methods for common task types
    
    async def submit_daily_message_task(self, 
                                      user_ids: List[str],
                                      template_category: str = 'motivation',
                                      priority: MessagePriority = MessagePriority.NORMAL) -> str:
        """Submit a daily message generation task."""
        task = RichMessageTask(
            task_id=f"daily_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            task_type='daily_message',
            priority=priority,
            user_ids=user_ids,
            template_category=template_category
        )
        
        success = await self.submit_task(task)
        return task.task_id if success else None
    
    async def submit_user_request_task(self,
                                     user_id: str,
                                     content_template: str,
                                     priority: MessagePriority = MessagePriority.HIGH) -> str:
        """Submit a user-requested message generation task."""
        task = RichMessageTask(
            task_id=f"user_request_{user_id}_{int(time.time())}",
            task_type='user_request',
            priority=priority,
            user_ids=[user_id],
            content_template=content_template
        )
        
        success = await self.submit_task(task)
        return task.task_id if success else None
    
    async def submit_batch_delivery_task(self,
                                       user_ids: List[str],
                                       content_template: str,
                                       template_category: str = 'general',
                                       priority: MessagePriority = MessagePriority.LOW) -> str:
        """Submit a batch delivery task."""
        task = RichMessageTask(
            task_id=f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            task_type='batch_delivery',
            priority=priority,
            user_ids=user_ids,
            content_template=content_template,
            template_category=template_category
        )
        
        success = await self.submit_task(task)
        return task.task_id if success else None


# Global pipeline instance
_pipeline_instance: Optional[AsyncRichMessagePipeline] = None


def get_async_pipeline(rich_message_service: Any = None,
                      max_workers: int = 4,
                      queue_size: int = 1000) -> AsyncRichMessagePipeline:
    """Get or create the global async Rich Message pipeline."""
    global _pipeline_instance
    
    if _pipeline_instance is None and rich_message_service:
        _pipeline_instance = AsyncRichMessagePipeline(
            rich_message_service=rich_message_service,
            max_workers=max_workers,
            queue_size=queue_size
        )
    
    return _pipeline_instance


async def initialize_pipeline(rich_message_service: Any,
                            max_workers: int = 4,
                            queue_size: int = 1000) -> AsyncRichMessagePipeline:
    """Initialize and start the global async Rich Message pipeline."""
    pipeline = get_async_pipeline(rich_message_service, max_workers, queue_size)
    
    if not pipeline.is_running:
        await pipeline.start()
    
    return pipeline


async def shutdown_pipeline():
    """Shutdown the global async Rich Message pipeline."""
    global _pipeline_instance
    
    if _pipeline_instance and _pipeline_instance.is_running:
        await _pipeline_instance.stop()
        _pipeline_instance = None