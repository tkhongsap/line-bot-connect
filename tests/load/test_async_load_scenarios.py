"""
Load Testing Scenarios for Async Processing Capabilities

This module provides comprehensive load testing scenarios for the LINE Bot's
async processing systems including streaming, batch processing, and monitoring
with realistic user behavior simulation and performance benchmarking.
"""

import asyncio
import time
import random
import logging
import json
import statistics
from typing import List, Dict, Any, Optional, Callable, Tuple
from dataclasses import dataclass, field
from contextlib import asynccontextmanager
from unittest.mock import Mock, AsyncMock

import pytest

from src.utils.async_openai_stream_handler import (
    AsyncOpenAIStreamHandler, async_stream_context
)
from src.utils.async_batch_processor import (
    AsyncBatchProcessor, BatchOperationType, BatchPriority,
    async_batch_context, setup_standard_handlers
)
from src.utils.async_performance_monitor import (
    PerformanceMonitor, OperationType, MetricType,
    performance_monitor_context
)

logger = logging.getLogger(__name__)

@dataclass
class LoadTestConfig:
    """Configuration for load testing scenarios"""
    # Test duration and scaling
    duration_seconds: int = 60
    concurrent_users: int = 10
    ramp_up_seconds: int = 10
    
    # Request patterns
    requests_per_user: int = 20
    request_interval_seconds: float = 1.0
    request_variance: float = 0.5  # ±50% variance in timing
    
    # Operation mix (percentages should sum to 100)
    operation_mix: Dict[str, int] = field(default_factory=lambda: {
        'streaming': 40,
        'batch_processing': 30,
        'image_processing': 15,
        'rich_message_generation': 15
    })
    
    # Performance thresholds
    max_response_time_ms: float = 5000
    max_error_rate: float = 0.05  # 5%
    min_throughput_rps: float = 10.0  # requests per second
    
    # Resource limits
    max_memory_mb: int = 512
    max_cpu_percent: float = 80.0
    max_concurrent_operations: int = 100

@dataclass
class LoadTestResult:
    """Results from a load test scenario"""
    test_name: str
    config: LoadTestConfig
    
    # Timing metrics
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_duration_seconds: float = 0.0
    
    # Response time metrics (in milliseconds)
    response_times: List[float] = field(default_factory=list)
    min_response_time: float = 0.0
    max_response_time: float = 0.0
    avg_response_time: float = 0.0
    p50_response_time: float = 0.0
    p90_response_time: float = 0.0
    p95_response_time: float = 0.0
    p99_response_time: float = 0.0
    
    # Throughput metrics
    requests_per_second: float = 0.0
    peak_rps: float = 0.0
    
    # Error metrics
    error_rate: float = 0.0
    errors_by_type: Dict[str, int] = field(default_factory=dict)
    
    # Resource metrics
    peak_memory_mb: float = 0.0
    avg_cpu_percent: float = 0.0
    peak_concurrent_operations: int = 0
    
    # Test status
    passed: bool = False
    failure_reasons: List[str] = field(default_factory=list)
    
    def calculate_metrics(self):
        """Calculate derived metrics from raw data"""
        if self.response_times:
            sorted_times = sorted(self.response_times)
            self.min_response_time = sorted_times[0]
            self.max_response_time = sorted_times[-1]
            self.avg_response_time = statistics.mean(sorted_times)
            
            # Percentiles
            count = len(sorted_times)
            self.p50_response_time = sorted_times[int(count * 0.5)]
            self.p90_response_time = sorted_times[int(count * 0.9)]
            self.p95_response_time = sorted_times[int(count * 0.95)]
            self.p99_response_time = sorted_times[int(count * 0.99)]
        
        # Calculate rates
        if self.total_duration_seconds > 0:
            self.requests_per_second = self.total_requests / self.total_duration_seconds
        
        if self.total_requests > 0:
            self.error_rate = self.failed_requests / self.total_requests
        
        # Determine if test passed
        self.passed = self._check_pass_criteria()
    
    def _check_pass_criteria(self) -> bool:
        """Check if test meets pass criteria"""
        self.failure_reasons.clear()
        
        # Check error rate
        if self.error_rate > self.config.max_error_rate:
            self.failure_reasons.append(
                f"Error rate {self.error_rate:.3f} exceeds threshold {self.config.max_error_rate}"
            )
        
        # Check response time
        if self.p95_response_time > self.config.max_response_time_ms:
            self.failure_reasons.append(
                f"P95 response time {self.p95_response_time:.1f}ms exceeds threshold {self.config.max_response_time_ms}ms"
            )
        
        # Check throughput
        if self.requests_per_second < self.config.min_throughput_rps:
            self.failure_reasons.append(
                f"Throughput {self.requests_per_second:.1f} RPS below threshold {self.config.min_throughput_rps} RPS"
            )
        
        # Check memory usage
        if self.peak_memory_mb > self.config.max_memory_mb:
            self.failure_reasons.append(
                f"Peak memory {self.peak_memory_mb:.1f}MB exceeds threshold {self.config.max_memory_mb}MB"
            )
        
        # Check CPU usage
        if self.avg_cpu_percent > self.config.max_cpu_percent:
            self.failure_reasons.append(
                f"Average CPU {self.avg_cpu_percent:.1f}% exceeds threshold {self.config.max_cpu_percent}%"
            )
        
        return len(self.failure_reasons) == 0

class LoadTestClient:
    """Simulates a user client for load testing"""
    
    def __init__(
        self,
        client_id: str,
        config: LoadTestConfig,
        stream_handler: AsyncOpenAIStreamHandler,
        batch_processor: AsyncBatchProcessor,
        monitor: PerformanceMonitor
    ):
        self.client_id = client_id
        self.config = config
        self.stream_handler = stream_handler
        self.batch_processor = batch_processor
        self.monitor = monitor
        
        # Client state
        self.requests_made = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.response_times: List[float] = []
        self.errors: List[Dict[str, Any]] = []
    
    async def run_client_session(self, start_delay: float = 0.0) -> Dict[str, Any]:
        """Run a complete client session"""
        logger.info(f"Starting client {self.client_id} with {start_delay}s delay")
        
        # Wait for ramp-up delay
        await asyncio.sleep(start_delay)
        
        session_start = time.time()
        
        try:
            while self.requests_made < self.config.requests_per_user:
                # Choose operation type based on configured mix
                operation_type = self._choose_operation_type()
                
                # Execute operation with timing
                start_time = time.time()
                try:
                    await self._execute_operation(operation_type)
                    self.successful_requests += 1
                except Exception as e:
                    self.failed_requests += 1
                    self.errors.append({
                        'timestamp': time.time(),
                        'operation_type': operation_type,
                        'error': str(e),
                        'error_type': type(e).__name__
                    })
                    logger.warning(f"Client {self.client_id} operation failed: {str(e)}")
                
                # Record response time
                response_time_ms = (time.time() - start_time) * 1000
                self.response_times.append(response_time_ms)
                self.requests_made += 1
                
                # Wait before next request with variance
                base_interval = self.config.request_interval_seconds
                variance = base_interval * self.config.request_variance
                actual_interval = base_interval + random.uniform(-variance, variance)
                await asyncio.sleep(max(0.01, actual_interval))  # Min 10ms
            
        except Exception as e:
            logger.error(f"Client {self.client_id} session error: {str(e)}")
        
        session_duration = time.time() - session_start
        
        return {
            'client_id': self.client_id,
            'session_duration': session_duration,
            'requests_made': self.requests_made,
            'successful_requests': self.successful_requests,
            'failed_requests': self.failed_requests,
            'response_times': self.response_times,
            'errors': self.errors
        }
    
    def _choose_operation_type(self) -> str:
        """Choose operation type based on configured mix"""
        rand_val = random.randint(1, 100)
        cumulative = 0
        
        for op_type, percentage in self.config.operation_mix.items():
            cumulative += percentage
            if rand_val <= cumulative:
                return op_type
        
        # Fallback to first operation type
        return list(self.config.operation_mix.keys())[0]
    
    async def _execute_operation(self, operation_type: str):
        """Execute a specific type of operation"""
        if operation_type == 'streaming':
            await self._execute_streaming_operation()
        elif operation_type == 'batch_processing':
            await self._execute_batch_operation()
        elif operation_type == 'image_processing':
            await self._execute_image_processing()
        elif operation_type == 'rich_message_generation':
            await self._execute_rich_message_generation()
        else:
            raise ValueError(f"Unknown operation type: {operation_type}")
    
    async def _execute_streaming_operation(self):
        """Execute a streaming operation"""
        user_id = f"load_test_user_{self.client_id}"
        message = f"Stream test message {self.requests_made} from {self.client_id}"
        
        chunks_received = 0
        async for chunk in self.stream_handler.create_async_stream(
            user_id=user_id,
            user_message=message
        ):
            chunks_received += 1
            # Simulate processing chunk
            await asyncio.sleep(0.001)  # 1ms processing time
        
        if chunks_received == 0:
            raise RuntimeError("No chunks received from stream")
    
    async def _execute_batch_operation(self):
        """Execute a batch processing operation"""
        job_id = await self.batch_processor.submit_job(
            operation_type=BatchOperationType.MESSAGE_PROCESSING,
            payload={'message': f'Batch test {self.requests_made} from {self.client_id}'},
            priority=BatchPriority.NORMAL
        )
        
        # Wait a bit and check job status
        await asyncio.sleep(0.1)
        status = await self.batch_processor.get_job_status(job_id)
        
        if not status:
            raise RuntimeError(f"Job {job_id} not found")
    
    async def _execute_image_processing(self):
        """Execute an image processing operation"""
        job_id = await self.batch_processor.submit_job(
            operation_type=BatchOperationType.IMAGE_PROCESSING,
            payload={
                'image_id': f'img_{self.client_id}_{self.requests_made}',
                'image_path': f'/mock/path/image_{self.requests_made}.jpg'
            },
            priority=BatchPriority.NORMAL
        )
        
        # Brief wait to simulate processing
        await asyncio.sleep(0.05)
    
    async def _execute_rich_message_generation(self):
        """Execute a Rich Message generation operation"""
        job_id = await self.batch_processor.submit_job(
            operation_type=BatchOperationType.RICH_MESSAGE_GENERATION,
            payload={
                'template_id': random.choice(['motivation', 'wellness', 'productivity']),
                'content': f'Rich message content {self.requests_made}',
                'user_id': f'load_test_user_{self.client_id}'
            },
            priority=BatchPriority.NORMAL
        )
        
        # Brief wait to simulate generation
        await asyncio.sleep(0.08)

class AsyncLoadTestRunner:
    """Main load test runner for async operations"""
    
    def __init__(self):
        self.results: List[LoadTestResult] = []
    
    async def run_load_test(
        self,
        test_name: str,
        config: LoadTestConfig,
        setup_callback: Optional[Callable] = None
    ) -> LoadTestResult:
        """Run a complete load test scenario"""
        logger.info(f"Starting load test: {test_name}")
        logger.info(f"Config: {config.concurrent_users} users, {config.duration_seconds}s duration")
        
        result = LoadTestResult(test_name=test_name, config=config)
        test_start_time = time.time()
        
        try:
            # Set up test environment
            async with self._setup_test_environment() as (stream_handler, batch_processor, monitor):
                
                # Custom setup if provided
                if setup_callback:
                    await setup_callback(stream_handler, batch_processor, monitor)
                
                # Create clients
                clients = []
                for i in range(config.concurrent_users):
                    client = LoadTestClient(
                        client_id=f"client_{i}",
                        config=config,
                        stream_handler=stream_handler,
                        batch_processor=batch_processor,
                        monitor=monitor
                    )
                    clients.append(client)
                
                # Start resource monitoring
                monitor_task = asyncio.create_task(
                    self._monitor_resources(monitor, result)
                )
                
                # Run clients with ramp-up
                client_tasks = []
                for i, client in enumerate(clients):
                    # Stagger client starts over ramp-up period
                    start_delay = (i / config.concurrent_users) * config.ramp_up_seconds
                    task = asyncio.create_task(client.run_client_session(start_delay))
                    client_tasks.append(task)
                
                # Wait for all clients to complete or timeout
                try:
                    client_results = await asyncio.wait_for(
                        asyncio.gather(*client_tasks, return_exceptions=True),
                        timeout=config.duration_seconds + config.ramp_up_seconds + 30
                    )
                except asyncio.TimeoutError:
                    logger.warning(f"Load test {test_name} timed out")
                    # Cancel remaining tasks
                    for task in client_tasks:
                        if not task.done():
                            task.cancel()
                    client_results = [None] * len(clients)
                
                # Stop resource monitoring
                monitor_task.cancel()
                try:
                    await monitor_task
                except asyncio.CancelledError:
                    pass
                
                # Aggregate results
                self._aggregate_client_results(result, client_results)
        
        except Exception as e:
            logger.error(f"Load test {test_name} failed: {str(e)}")
            result.failure_reasons.append(f"Test setup/execution error: {str(e)}")
        
        # Calculate final metrics
        result.total_duration_seconds = time.time() - test_start_time
        result.calculate_metrics()
        
        # Log results
        self._log_test_results(result)
        
        self.results.append(result)
        return result
    
    @asynccontextmanager
    async def _setup_test_environment(self):
        """Set up test environment with all components"""
        # Mock settings
        settings = Mock()
        settings.MAX_CONCURRENT_STREAMS = 50
        settings.STREAM_TIMEOUT_SECONDS = 30
        settings.STREAM_CHUNK_BUFFER_SIZE = 20
        settings.STREAM_FLUSH_INTERVAL = 0.05
        settings.BATCH_MAX_WORKERS = 10
        settings.BATCH_QUEUE_MAX_SIZE = 1000
        settings.BATCH_DEFAULT_TIMEOUT = 10.0
        settings.BATCH_STATS_INTERVAL = 1.0
        settings.METRICS_COLLECTION_INTERVAL = 1.0
        settings.SYSTEM_METRICS_INTERVAL = 2.0
        settings.ALERT_CHECK_INTERVAL = 5.0
        settings.METRICS_RETENTION_SECONDS = 3600
        
        # Mock OpenAI service
        mock_openai_service = Mock()
        mock_openai_service.get_response = AsyncMock(return_value={
            'success': True,
            'streaming': True,
            'content': 'Mock response content for load testing'
        })
        
        try:
            # Start all components
            async with async_stream_context(mock_openai_service, settings) as stream_handler, \
                     async_batch_context(settings) as batch_processor, \
                     performance_monitor_context(settings) as monitor:
                
                # Set up batch processor handlers
                setup_standard_handlers(batch_processor)
                
                yield stream_handler, batch_processor, monitor
        
        except Exception as e:
            logger.error(f"Failed to set up test environment: {str(e)}")
            raise
    
    async def _monitor_resources(self, monitor: PerformanceMonitor, result: LoadTestResult):
        """Monitor system resources during test"""
        try:
            while True:
                # Get current metrics
                summary = monitor.get_metrics_summary()
                
                # Update peak values
                if summary.get('system'):
                    system_metrics = summary['system']
                    if system_metrics.get('memory_usage_mb', 0) > result.peak_memory_mb:
                        result.peak_memory_mb = system_metrics['memory_usage_mb']
                    
                    # Track CPU (would need to implement averaging)
                    cpu_percent = system_metrics.get('cpu_percent', 0)
                    if cpu_percent > 0:
                        # Simple moving average
                        if result.avg_cpu_percent == 0:
                            result.avg_cpu_percent = cpu_percent
                        else:
                            result.avg_cpu_percent = (result.avg_cpu_percent + cpu_percent) / 2
                
                # Track concurrent operations
                active_ops = summary.get('operations', {}).get('active_operations', 0)
                if active_ops > result.peak_concurrent_operations:
                    result.peak_concurrent_operations = active_ops
                
                await asyncio.sleep(1.0)  # Monitor every second
                
        except asyncio.CancelledError:
            pass
    
    def _aggregate_client_results(self, result: LoadTestResult, client_results: List[Any]):
        """Aggregate results from all clients"""
        all_response_times = []
        total_errors_by_type = {}
        
        for client_result in client_results:
            if client_result and not isinstance(client_result, Exception):
                result.total_requests += client_result.get('requests_made', 0)
                result.successful_requests += client_result.get('successful_requests', 0)
                result.failed_requests += client_result.get('failed_requests', 0)
                
                # Collect response times
                all_response_times.extend(client_result.get('response_times', []))
                
                # Aggregate errors
                for error in client_result.get('errors', []):
                    error_type = error.get('error_type', 'Unknown')
                    total_errors_by_type[error_type] = total_errors_by_type.get(error_type, 0) + 1
        
        result.response_times = all_response_times
        result.errors_by_type = total_errors_by_type
    
    def _log_test_results(self, result: LoadTestResult):
        """Log comprehensive test results"""
        logger.info(f"Load test '{result.test_name}' completed:")
        logger.info(f"  Total requests: {result.total_requests}")
        logger.info(f"  Success rate: {((result.successful_requests / result.total_requests) * 100):.1f}%")
        logger.info(f"  Error rate: {(result.error_rate * 100):.2f}%")
        logger.info(f"  Throughput: {result.requests_per_second:.1f} RPS")
        logger.info(f"  Response times - P50: {result.p50_response_time:.1f}ms, P95: {result.p95_response_time:.1f}ms")
        logger.info(f"  Peak memory: {result.peak_memory_mb:.1f}MB")
        logger.info(f"  Peak concurrent ops: {result.peak_concurrent_operations}")
        logger.info(f"  Test passed: {result.passed}")
        
        if not result.passed:
            logger.warning(f"  Failure reasons: {', '.join(result.failure_reasons)}")

# Pre-defined load test scenarios
class LoadTestScenarios:
    """Collection of pre-defined load test scenarios"""
    
    @staticmethod
    def light_load_scenario() -> LoadTestConfig:
        """Light load scenario for smoke testing"""
        return LoadTestConfig(
            duration_seconds=30,
            concurrent_users=5,
            ramp_up_seconds=5,
            requests_per_user=10,
            request_interval_seconds=1.0,
            operation_mix={
                'streaming': 50,
                'batch_processing': 30,
                'image_processing': 10,
                'rich_message_generation': 10
            },
            max_response_time_ms=3000,
            max_error_rate=0.02,
            min_throughput_rps=2.0
        )
    
    @staticmethod
    def moderate_load_scenario() -> LoadTestConfig:
        """Moderate load scenario for regular testing"""
        return LoadTestConfig(
            duration_seconds=60,
            concurrent_users=20,
            ramp_up_seconds=10,
            requests_per_user=15,
            request_interval_seconds=0.8,
            operation_mix={
                'streaming': 40,
                'batch_processing': 35,
                'image_processing': 15,
                'rich_message_generation': 10
            },
            max_response_time_ms=4000,
            max_error_rate=0.03,
            min_throughput_rps=8.0
        )
    
    @staticmethod
    def heavy_load_scenario() -> LoadTestConfig:
        """Heavy load scenario for stress testing"""
        return LoadTestConfig(
            duration_seconds=120,
            concurrent_users=50,
            ramp_up_seconds=20,
            requests_per_user=25,
            request_interval_seconds=0.5,
            operation_mix={
                'streaming': 35,
                'batch_processing': 40,
                'image_processing': 15,
                'rich_message_generation': 10
            },
            max_response_time_ms=6000,
            max_error_rate=0.05,
            min_throughput_rps=15.0,
            max_memory_mb=1024,
            max_concurrent_operations=200
        )
    
    @staticmethod
    def burst_load_scenario() -> LoadTestConfig:
        """Burst load scenario with high concurrency"""
        return LoadTestConfig(
            duration_seconds=60,
            concurrent_users=100,
            ramp_up_seconds=5,  # Fast ramp-up
            requests_per_user=10,
            request_interval_seconds=0.3,
            request_variance=0.8,  # High variance
            operation_mix={
                'streaming': 60,  # Heavy on streaming
                'batch_processing': 25,
                'image_processing': 10,
                'rich_message_generation': 5
            },
            max_response_time_ms=8000,
            max_error_rate=0.08,
            min_throughput_rps=20.0,
            max_memory_mb=1024,
            max_concurrent_operations=300
        )
    
    @staticmethod
    def endurance_scenario() -> LoadTestConfig:
        """Long-running endurance test"""
        return LoadTestConfig(
            duration_seconds=300,  # 5 minutes
            concurrent_users=15,
            ramp_up_seconds=15,
            requests_per_user=50,
            request_interval_seconds=1.2,
            operation_mix={
                'streaming': 30,
                'batch_processing': 35,
                'image_processing': 20,
                'rich_message_generation': 15
            },
            max_response_time_ms=5000,
            max_error_rate=0.03,
            min_throughput_rps=5.0
        )

# Test classes for pytest integration
@pytest.mark.load
class TestAsyncLoadScenarios:
    """Load test scenarios as pytest tests"""
    
    @pytest.fixture
    def load_runner(self):
        """Create load test runner"""
        return AsyncLoadTestRunner()
    
    @pytest.mark.asyncio
    async def test_light_load_scenario(self, load_runner):
        """Test light load scenario"""
        config = LoadTestScenarios.light_load_scenario()
        result = await load_runner.run_load_test("Light Load Test", config)
        
        assert result.passed, f"Light load test failed: {result.failure_reasons}"
        assert result.total_requests > 0
        assert result.error_rate <= config.max_error_rate
    
    @pytest.mark.asyncio
    async def test_moderate_load_scenario(self, load_runner):
        """Test moderate load scenario"""
        config = LoadTestScenarios.moderate_load_scenario()
        result = await load_runner.run_load_test("Moderate Load Test", config)
        
        assert result.passed, f"Moderate load test failed: {result.failure_reasons}"
        assert result.requests_per_second >= config.min_throughput_rps
        assert result.p95_response_time <= config.max_response_time_ms
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_heavy_load_scenario(self, load_runner):
        """Test heavy load scenario"""
        config = LoadTestScenarios.heavy_load_scenario()
        result = await load_runner.run_load_test("Heavy Load Test", config)
        
        # Heavy load test may have higher tolerance
        assert result.total_requests > 0
        assert result.error_rate <= config.max_error_rate * 1.5  # Allow 50% higher error rate
        
        # Log performance metrics even if test doesn't fully pass
        logger.info(f"Heavy load test metrics:")
        logger.info(f"  Throughput: {result.requests_per_second:.1f} RPS")
        logger.info(f"  P95 Response Time: {result.p95_response_time:.1f}ms")
        logger.info(f"  Error Rate: {(result.error_rate * 100):.2f}%")
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_burst_load_scenario(self, load_runner):
        """Test burst load scenario"""
        config = LoadTestScenarios.burst_load_scenario()
        result = await load_runner.run_load_test("Burst Load Test", config)
        
        # Burst test focuses on handling spikes
        assert result.total_requests > 0
        assert result.successful_requests > result.failed_requests  # More successes than failures
        
        # Check that system handled the burst without complete failure
        assert result.error_rate <= 0.15  # Allow up to 15% errors in burst scenario
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_endurance_scenario(self, load_runner):
        """Test endurance scenario"""
        config = LoadTestScenarios.endurance_scenario()
        result = await load_runner.run_load_test("Endurance Test", config)
        
        # Endurance test focuses on stability over time
        assert result.total_requests > 0
        assert result.error_rate <= config.max_error_rate
        
        # Check memory didn't grow excessively
        assert result.peak_memory_mb <= config.max_memory_mb
    
    @pytest.mark.asyncio
    async def test_streaming_focused_load(self, load_runner):
        """Test streaming-focused load scenario"""
        config = LoadTestConfig(
            duration_seconds=45,
            concurrent_users=25,
            ramp_up_seconds=8,
            requests_per_user=12,
            request_interval_seconds=0.7,
            operation_mix={
                'streaming': 80,  # Focus on streaming
                'batch_processing': 15,
                'image_processing': 3,
                'rich_message_generation': 2
            },
            max_response_time_ms=4500,
            max_error_rate=0.04,
            min_throughput_rps=12.0
        )
        
        result = await load_runner.run_load_test("Streaming Focused Load", config)
        
        assert result.total_requests > 0
        assert result.error_rate <= config.max_error_rate
        
        # Streaming should handle the focused load well
        assert result.p90_response_time <= config.max_response_time_ms
    
    @pytest.mark.asyncio
    async def test_batch_processing_focused_load(self, load_runner):
        """Test batch processing-focused load scenario"""
        config = LoadTestConfig(
            duration_seconds=45,
            concurrent_users=15,
            ramp_up_seconds=10,
            requests_per_user=20,
            request_interval_seconds=0.8,
            operation_mix={
                'streaming': 10,
                'batch_processing': 70,  # Focus on batch processing
                'image_processing': 15,
                'rich_message_generation': 5
            },
            max_response_time_ms=5000,
            max_error_rate=0.04,
            min_throughput_rps=8.0
        )
        
        result = await load_runner.run_load_test("Batch Processing Focused Load", config)
        
        assert result.total_requests > 0
        assert result.error_rate <= config.max_error_rate
        
        # Batch processing should queue and handle requests efficiently
        assert result.requests_per_second >= config.min_throughput_rps * 0.8  # Allow 20% tolerance

# Utility functions for manual load testing
async def run_manual_load_test(scenario_name: str = "moderate"):
    """Run a manual load test scenario"""
    runner = AsyncLoadTestRunner()
    
    scenarios = {
        "light": LoadTestScenarios.light_load_scenario(),
        "moderate": LoadTestScenarios.moderate_load_scenario(),
        "heavy": LoadTestScenarios.heavy_load_scenario(),
        "burst": LoadTestScenarios.burst_load_scenario(),
        "endurance": LoadTestScenarios.endurance_scenario()
    }
    
    if scenario_name not in scenarios:
        raise ValueError(f"Unknown scenario: {scenario_name}. Available: {list(scenarios.keys())}")
    
    config = scenarios[scenario_name]
    result = await runner.run_load_test(f"Manual {scenario_name.title()} Load Test", config)
    
    return result

if __name__ == "__main__":
    # Example of running a manual load test
    import sys
    
    async def main():
        scenario = sys.argv[1] if len(sys.argv) > 1 else "light"
        print(f"Running {scenario} load test scenario...")
        
        result = await run_manual_load_test(scenario)
        
        print(f"\nLoad Test Results:")
        print(f"Passed: {result.passed}")
        print(f"Total Requests: {result.total_requests}")
        print(f"Success Rate: {((result.successful_requests / result.total_requests) * 100):.1f}%")
        print(f"Throughput: {result.requests_per_second:.2f} RPS")
        print(f"P95 Response Time: {result.p95_response_time:.1f}ms")
        
        if not result.passed:
            print(f"Failure Reasons: {', '.join(result.failure_reasons)}")
    
    asyncio.run(main())