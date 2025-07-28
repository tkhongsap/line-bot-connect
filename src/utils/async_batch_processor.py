"""
Async Batch Processing System

This module provides comprehensive async batch processing capabilities for 
LINE Bot operations including message processing, Rich Message generation,
image processing, and OpenAI API calls with advanced queue management,
load balancing, and error recovery.
"""

import asyncio
import time
import logging
import json
from typing import (
    List, Dict, Any, Optional, Callable, AsyncGenerator, 
    Union, Tuple, TypeVar, Generic, Awaitable
)
from dataclasses import dataclass, field
from enum import Enum
from contextlib import asynccontextmanager
import heapq
from collections import defaultdict, deque

from ..exceptions import (
    BaseBotException, create_correlation_id, wrap_api_exception
)
from ..utils.error_handler import StructuredLogger, error_handler, retry_with_backoff

logger = StructuredLogger(__name__)

T = TypeVar('T')
R = TypeVar('R')

class BatchOperationType(Enum):
    """Types of batch operations supported"""
    MESSAGE_PROCESSING = "message_processing"
    RICH_MESSAGE_GENERATION = "rich_message_generation"
    IMAGE_PROCESSING = "image_processing"
    OPENAI_API_CALLS = "openai_api_calls"
    WEBHOOK_PROCESSING = "webhook_processing"
    ANALYTICS_PROCESSING = "analytics_processing"
    TEMPLATE_PROCESSING = "template_processing"

class BatchPriority(Enum):
    """Priority levels for batch operations"""
    CRITICAL = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4
    BACKGROUND = 5

class BatchJobStatus(Enum):
    """Status of batch jobs"""
    PENDING = "pending"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"

@dataclass
class BatchJob(Generic[T, R]):
    """Represents a single job in a batch operation"""
    job_id: str
    operation_type: BatchOperationType
    priority: BatchPriority
    payload: T
    callback: Optional[Callable[[R], Awaitable[None]]] = None
    error_callback: Optional[Callable[[Exception], Awaitable[None]]] = None
    timeout: float = 30.0
    max_retries: int = 3
    retry_delay: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Internal tracking
    status: BatchJobStatus = BatchJobStatus.PENDING
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    retry_count: int = 0
    result: Optional[R] = None
    error: Optional[Exception] = None
    correlation_id: str = field(default_factory=create_correlation_id)
    
    def __lt__(self, other):
        """Priority comparison for heap queue"""
        return self.priority.value < other.priority.value

@dataclass
class BatchProcessingStats:
    """Statistics for batch processing operations"""
    total_jobs: int = 0
    completed_jobs: int = 0
    failed_jobs: int = 0
    retried_jobs: int = 0
    cancelled_jobs: int = 0
    avg_processing_time: float = 0.0
    throughput_jobs_per_sec: float = 0.0
    queue_size: int = 0
    active_workers: int = 0
    
    # Per-operation-type stats
    stats_by_type: Dict[BatchOperationType, Dict[str, Any]] = field(default_factory=dict)

class AsyncBatchQueue:
    """Thread-safe async priority queue for batch jobs"""
    
    def __init__(self, max_size: int = 10000):
        self.max_size = max_size
        self._queue = []
        self._condition = asyncio.Condition()
        self._shutdown = False
        
    async def put(self, job: BatchJob):
        """Add job to priority queue"""
        async with self._condition:
            if self._shutdown:
                raise RuntimeError("Queue is shutdown")
            
            if len(self._queue) >= self.max_size:
                raise RuntimeError(f"Queue is full (max size: {self.max_size})")
            
            heapq.heappush(self._queue, job)
            job.status = BatchJobStatus.QUEUED
            self._condition.notify()
            
            logger.debug(f"Added job {job.job_id} to queue", extra={
                'job_id': job.job_id,
                'operation_type': job.operation_type.value,
                'priority': job.priority.value,
                'queue_size': len(self._queue)
            })
    
    async def get(self, timeout: Optional[float] = None) -> Optional[BatchJob]:
        """Get highest priority job from queue"""
        async with self._condition:
            while not self._queue and not self._shutdown:
                try:
                    await asyncio.wait_for(self._condition.wait(), timeout=timeout)
                except asyncio.TimeoutError:
                    return None
            
            if not self._queue:
                return None
            
            job = heapq.heappop(self._queue)
            job.status = BatchJobStatus.PROCESSING
            job.started_at = time.time()
            
            return job
    
    async def size(self) -> int:
        """Get current queue size"""
        async with self._condition:
            return len(self._queue)
    
    async def shutdown(self):
        """Shutdown the queue"""
        async with self._condition:
            self._shutdown = True
            self._condition.notify_all()

class AsyncBatchWorker:
    """Worker for processing batch jobs"""
    
    def __init__(
        self, 
        worker_id: str,
        batch_processor: 'AsyncBatchProcessor',
        operation_handlers: Dict[BatchOperationType, Callable]
    ):
        self.worker_id = worker_id
        self.batch_processor = batch_processor
        self.operation_handlers = operation_handlers
        self.is_running = False
        self.current_job: Optional[BatchJob] = None
        self.processed_jobs = 0
        self.failed_jobs = 0
        
    async def start(self):
        """Start the worker"""
        self.is_running = True
        logger.info(f"Starting batch worker {self.worker_id}")
        
        try:
            while self.is_running:
                try:
                    # Get next job from queue
                    job = await self.batch_processor.queue.get(timeout=1.0)
                    if not job:
                        continue
                    
                    self.current_job = job
                    await self._process_job(job)
                    self.current_job = None
                    
                except Exception as e:
                    logger.error(f"Worker {self.worker_id} error: {str(e)}", extra={
                        'worker_id': self.worker_id,
                        'error_type': type(e).__name__
                    })
                    
        except asyncio.CancelledError:
            logger.info(f"Worker {self.worker_id} cancelled")
        finally:
            self.is_running = False
            logger.info(f"Worker {self.worker_id} stopped")
    
    async def _process_job(self, job: BatchJob):
        """Process a single batch job"""
        logger.debug(f"Processing job {job.job_id}", extra={
            'job_id': job.job_id,
            'worker_id': self.worker_id,
            'operation_type': job.operation_type.value
        })
        
        try:
            # Get operation handler
            handler = self.operation_handlers.get(job.operation_type)
            if not handler:
                raise ValueError(f"No handler for operation type: {job.operation_type}")
            
            # Execute with timeout
            result = await asyncio.wait_for(
                handler(job.payload),
                timeout=job.timeout
            )
            
            # Job completed successfully
            job.result = result
            job.status = BatchJobStatus.COMPLETED
            job.completed_at = time.time()
            self.processed_jobs += 1
            
            # Execute success callback if provided
            if job.callback:
                try:
                    await job.callback(result)
                except Exception as callback_error:
                    logger.warning(f"Callback error for job {job.job_id}: {str(callback_error)}")
            
            # Update processor stats
            await self.batch_processor._update_job_stats(job, success=True)
            
            logger.debug(f"Job {job.job_id} completed successfully", extra={
                'job_id': job.job_id,
                'processing_time': job.completed_at - job.started_at
            })
            
        except Exception as e:
            await self._handle_job_error(job, e)
    
    async def _handle_job_error(self, job: BatchJob, error: Exception):
        """Handle job processing error with retry logic"""
        job.error = error
        job.retry_count += 1
        self.failed_jobs += 1
        
        logger.error(f"Job {job.job_id} failed: {str(error)}", extra={
            'job_id': job.job_id,
            'error_type': type(error).__name__,
            'retry_count': job.retry_count,
            'max_retries': job.max_retries
        })
        
        # Check if we should retry
        if job.retry_count <= job.max_retries:
            job.status = BatchJobStatus.RETRYING
            
            # Wait before retry
            await asyncio.sleep(job.retry_delay * (2 ** (job.retry_count - 1)))
            
            # Re-queue the job
            await self.batch_processor.queue.put(job)
            
            logger.info(f"Retrying job {job.job_id} (attempt {job.retry_count})")
        else:
            # Max retries exceeded
            job.status = BatchJobStatus.FAILED
            job.completed_at = time.time()
            
            # Execute error callback if provided
            if job.error_callback:
                try:
                    await job.error_callback(error)
                except Exception as callback_error:
                    logger.warning(f"Error callback failed for job {job.job_id}: {str(callback_error)}")
            
            # Update processor stats
            await self.batch_processor._update_job_stats(job, success=False)
    
    async def stop(self):
        """Stop the worker"""
        self.is_running = False
        
        # Cancel current job if running
        if self.current_job:
            self.current_job.status = BatchJobStatus.CANCELLED
            self.current_job.completed_at = time.time()

class AsyncBatchProcessor:
    """Main async batch processing coordinator"""
    
    def __init__(self, settings):
        self.settings = settings
        
        # Configuration
        self.max_workers = getattr(settings, 'BATCH_MAX_WORKERS', 5)
        self.queue_max_size = getattr(settings, 'BATCH_QUEUE_MAX_SIZE', 10000)
        self.default_timeout = getattr(settings, 'BATCH_DEFAULT_TIMEOUT', 30.0)
        self.stats_update_interval = getattr(settings, 'BATCH_STATS_INTERVAL', 10.0)
        
        # Initialize components
        self.queue = AsyncBatchQueue(max_size=self.queue_max_size)
        self.workers: Dict[str, AsyncBatchWorker] = {}
        self.worker_tasks: Dict[str, asyncio.Task] = {}
        
        # Operation handlers
        self.operation_handlers: Dict[BatchOperationType, Callable] = {}
        
        # Statistics and monitoring
        self.stats = BatchProcessingStats()
        self.job_history: deque = deque(maxlen=1000)
        self.start_time = time.time()
        
        # Shutdown flag
        self.is_shutdown = False
        
        logger.info(f"Initialized AsyncBatchProcessor with {self.max_workers} workers")
    
    def register_operation_handler(
        self, 
        operation_type: BatchOperationType, 
        handler: Callable[[Any], Awaitable[Any]]
    ):
        """Register a handler for a specific operation type"""
        self.operation_handlers[operation_type] = handler
        logger.info(f"Registered handler for {operation_type.value}")
    
    async def start(self):
        """Start the batch processor and workers"""
        if self.is_shutdown:
            raise RuntimeError("Processor is shutdown")
        
        logger.info("Starting AsyncBatchProcessor")
        
        # Start workers
        for i in range(self.max_workers):
            worker_id = f"worker_{i}"
            worker = AsyncBatchWorker(
                worker_id=worker_id,
                batch_processor=self,
                operation_handlers=self.operation_handlers
            )
            
            task = asyncio.create_task(worker.start())
            
            self.workers[worker_id] = worker
            self.worker_tasks[worker_id] = task
        
        # Start stats update task
        self.stats_task = asyncio.create_task(self._update_stats_loop())
        
        logger.info(f"Started {len(self.workers)} batch workers")
    
    async def submit_job(
        self,
        operation_type: BatchOperationType,
        payload: Any,
        priority: BatchPriority = BatchPriority.NORMAL,
        timeout: float = None,
        callback: Optional[Callable] = None,
        error_callback: Optional[Callable] = None,
        max_retries: int = 3,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Submit a job for batch processing"""
        
        if self.is_shutdown:
            raise RuntimeError("Processor is shutdown")
        
        job_id = f"{operation_type.value}_{create_correlation_id()}"
        
        job = BatchJob(
            job_id=job_id,
            operation_type=operation_type,
            priority=priority,
            payload=payload,
            callback=callback,
            error_callback=error_callback,
            timeout=timeout or self.default_timeout,
            max_retries=max_retries,
            metadata=metadata or {}
        )
        
        await self.queue.put(job)
        self.stats.total_jobs += 1
        
        logger.info(f"Submitted job {job_id}", extra={
            'job_id': job_id,
            'operation_type': operation_type.value,
            'priority': priority.value
        })
        
        return job_id
    
    async def submit_batch(
        self,
        jobs: List[Dict[str, Any]],
        batch_callback: Optional[Callable[[List[Any]], Awaitable[None]]] = None
    ) -> List[str]:
        """Submit multiple jobs as a batch"""
        
        job_ids = []
        batch_id = create_correlation_id()
        
        logger.info(f"Submitting batch {batch_id} with {len(jobs)} jobs")
        
        for i, job_config in enumerate(jobs):
            # Add batch metadata
            metadata = job_config.get('metadata', {})
            metadata.update({
                'batch_id': batch_id,
                'batch_index': i,
                'batch_size': len(jobs)
            })
            job_config['metadata'] = metadata
            
            job_id = await self.submit_job(**job_config)
            job_ids.append(job_id)
        
        # If batch callback provided, monitor batch completion
        if batch_callback:
            asyncio.create_task(
                self._monitor_batch_completion(batch_id, job_ids, batch_callback)
            )
        
        return job_ids
    
    async def _monitor_batch_completion(
        self,
        batch_id: str,
        job_ids: List[str],
        batch_callback: Callable
    ):
        """Monitor batch completion and execute callback"""
        logger.info(f"Monitoring batch {batch_id} completion")
        
        while True:
            # Check if all jobs in batch are completed
            completed_jobs = [
                job for job in self.job_history 
                if job.job_id in job_ids and job.status in [
                    BatchJobStatus.COMPLETED, BatchJobStatus.FAILED, BatchJobStatus.CANCELLED
                ]
            ]
            
            if len(completed_jobs) == len(job_ids):
                # All jobs completed, execute batch callback
                results = [job.result for job in completed_jobs if job.result is not None]
                
                try:
                    await batch_callback(results)
                    logger.info(f"Batch {batch_id} callback executed successfully")
                except Exception as e:
                    logger.error(f"Batch {batch_id} callback failed: {str(e)}")
                
                break
            
            # Wait before checking again
            await asyncio.sleep(1.0)
    
    async def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a specific job"""
        # Check active jobs first
        for worker in self.workers.values():
            if worker.current_job and worker.current_job.job_id == job_id:
                job = worker.current_job
                return {
                    'job_id': job.job_id,
                    'status': job.status.value,
                    'operation_type': job.operation_type.value,
                    'priority': job.priority.value,
                    'created_at': job.created_at,
                    'started_at': job.started_at,
                    'completed_at': job.completed_at,
                    'retry_count': job.retry_count,
                    'metadata': job.metadata
                }
        
        # Check job history
        for job in self.job_history:
            if job.job_id == job_id:
                return {
                    'job_id': job.job_id,
                    'status': job.status.value,
                    'operation_type': job.operation_type.value,
                    'priority': job.priority.value,
                    'created_at': job.created_at,
                    'started_at': job.started_at,
                    'completed_at': job.completed_at,
                    'retry_count': job.retry_count,
                    'result': str(job.result) if job.result else None,
                    'error': str(job.error) if job.error else None,
                    'metadata': job.metadata
                }
        
        return None
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current processing statistics"""
        return {
            'total_jobs': self.stats.total_jobs,
            'completed_jobs': self.stats.completed_jobs,
            'failed_jobs': self.stats.failed_jobs,
            'retried_jobs': self.stats.retried_jobs,
            'cancelled_jobs': self.stats.cancelled_jobs,
            'avg_processing_time': self.stats.avg_processing_time,
            'throughput_jobs_per_sec': self.stats.throughput_jobs_per_sec,
            'queue_size': self.stats.queue_size,
            'active_workers': sum(1 for w in self.workers.values() if w.is_running),
            'worker_stats': {
                worker_id: {
                    'processed_jobs': worker.processed_jobs,
                    'failed_jobs': worker.failed_jobs,
                    'is_running': worker.is_running,
                    'current_job': worker.current_job.job_id if worker.current_job else None
                }
                for worker_id, worker in self.workers.items()
            },
            'stats_by_type': dict(self.stats.stats_by_type),
            'uptime_seconds': time.time() - self.start_time
        }
    
    async def _update_job_stats(self, job: BatchJob, success: bool):
        """Update statistics for completed job"""
        if success:
            self.stats.completed_jobs += 1
        else:
            self.stats.failed_jobs += 1
        
        if job.retry_count > 0:
            self.stats.retried_jobs += 1
        
        # Update per-operation-type stats
        op_type = job.operation_type
        if op_type not in self.stats.stats_by_type:
            self.stats.stats_by_type[op_type] = {
                'total': 0, 'completed': 0, 'failed': 0, 'avg_time': 0.0
            }
        
        type_stats = self.stats.stats_by_type[op_type]
        type_stats['total'] += 1
        
        if success:
            type_stats['completed'] += 1
        else:
            type_stats['failed'] += 1
        
        # Update average processing time
        if job.started_at and job.completed_at:
            processing_time = job.completed_at - job.started_at
            
            # Update global average
            total_completed = self.stats.completed_jobs + self.stats.failed_jobs
            if total_completed > 1:
                self.stats.avg_processing_time = (
                    (self.stats.avg_processing_time * (total_completed - 1) + processing_time) 
                    / total_completed
                )
            else:
                self.stats.avg_processing_time = processing_time
            
            # Update type-specific average
            type_total = type_stats['completed'] + type_stats['failed']
            if type_total > 1:
                type_stats['avg_time'] = (
                    (type_stats['avg_time'] * (type_total - 1) + processing_time) 
                    / type_total
                )
            else:
                type_stats['avg_time'] = processing_time
        
        # Add to job history
        self.job_history.append(job)
    
    async def _update_stats_loop(self):
        """Background task to update statistics"""
        try:
            while not self.is_shutdown:
                # Update queue size
                self.stats.queue_size = await self.queue.size()
                
                # Update active workers count
                self.stats.active_workers = sum(1 for w in self.workers.values() if w.is_running)
                
                # Calculate throughput
                uptime = time.time() - self.start_time
                if uptime > 0:
                    self.stats.throughput_jobs_per_sec = self.stats.completed_jobs / uptime
                
                await asyncio.sleep(self.stats_update_interval)
                
        except asyncio.CancelledError:
            pass
    
    async def shutdown(self, timeout: float = 30.0):
        """Shutdown the batch processor gracefully"""
        logger.info("Shutting down AsyncBatchProcessor")
        self.is_shutdown = True
        
        # Stop accepting new jobs
        await self.queue.shutdown()
        
        # Stop workers
        for worker in self.workers.values():
            await worker.stop()
        
        # Cancel worker tasks with timeout
        if self.worker_tasks:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self.worker_tasks.values(), return_exceptions=True),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                logger.warning("Worker shutdown timeout, forcing cancellation")
                for task in self.worker_tasks.values():
                    task.cancel()
        
        # Cancel stats task
        if hasattr(self, 'stats_task'):
            self.stats_task.cancel()
            try:
                await self.stats_task
            except asyncio.CancelledError:
                pass
        
        logger.info("AsyncBatchProcessor shutdown completed")

# Context manager for batch processor
@asynccontextmanager
async def async_batch_context(settings):
    """Context manager for async batch processor"""
    processor = AsyncBatchProcessor(settings)
    try:
        await processor.start()
        yield processor
    finally:
        await processor.shutdown()

# Predefined operation handlers for common LINE Bot operations
class StandardBatchHandlers:
    """Standard batch operation handlers for LINE Bot"""
    
    @staticmethod
    async def message_processing_handler(payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handler for message processing operations"""
        # Mock implementation - replace with actual message processing logic
        await asyncio.sleep(0.1)  # Simulate processing time
        return {
            'processed': True,
            'message_id': payload.get('message_id'),
            'response': f"Processed: {payload.get('content', '')}"
        }
    
    @staticmethod
    async def rich_message_generation_handler(payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handler for Rich Message generation operations"""
        # Mock implementation - replace with actual Rich Message generation logic
        await asyncio.sleep(0.5)  # Simulate generation time
        return {
            'generated': True,
            'template_id': payload.get('template_id'),
            'rich_message': {
                'type': 'flex',
                'content': f"Generated rich message for: {payload.get('content', '')}"
            }
        }
    
    @staticmethod
    async def image_processing_handler(payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handler for image processing operations"""
        # Mock implementation - replace with actual image processing logic
        await asyncio.sleep(0.3)  # Simulate processing time
        return {
            'processed': True,
            'image_id': payload.get('image_id'),
            'analysis': f"Processed image: {payload.get('image_path', '')}"
        }
    
    @staticmethod
    async def openai_api_handler(payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handler for OpenAI API operations"""
        # Mock implementation - replace with actual OpenAI API calls
        await asyncio.sleep(0.8)  # Simulate API call time
        return {
            'success': True,
            'request_id': payload.get('request_id'),
            'response': f"AI response to: {payload.get('prompt', '')}"
        }

def setup_standard_handlers(processor: AsyncBatchProcessor):
    """Set up standard batch handlers for LINE Bot operations"""
    processor.register_operation_handler(
        BatchOperationType.MESSAGE_PROCESSING,
        StandardBatchHandlers.message_processing_handler
    )
    processor.register_operation_handler(
        BatchOperationType.RICH_MESSAGE_GENERATION,
        StandardBatchHandlers.rich_message_generation_handler
    )
    processor.register_operation_handler(
        BatchOperationType.IMAGE_PROCESSING,
        StandardBatchHandlers.image_processing_handler
    )
    processor.register_operation_handler(
        BatchOperationType.OPENAI_API_CALLS,
        StandardBatchHandlers.openai_api_handler
    )