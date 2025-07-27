"""
Load testing for Rich Message automation system.

This module provides comprehensive load testing capabilities to validate
system performance under realistic production loads.
"""

import pytest
import time
import threading
import queue
import json
import statistics
from unittest.mock import patch, Mock, MagicMock
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Tuple, Optional
import logging

from src.services.rich_message_service import RichMessageService
from src.utils.interaction_handler import get_interaction_handler
from src.utils.analytics_tracker import get_analytics_tracker
from src.utils.admin_controller import get_admin_controller
from tests.performance.performance_config import (
    PerformanceLevel, PerformanceTestUtils, PERFORMANCE_CONFIGS, PERFORMANCE_BENCHMARKS
)

logger = logging.getLogger(__name__)


class LoadTestMetrics:
    """Collects and manages load test metrics"""
    
    def __init__(self):
        self.start_time = None
        self.end_time = None
        self.request_times = []
        self.error_count = 0
        self.success_count = 0
        self.concurrent_users = 0
        self.throughput_samples = []
        self.memory_samples = []
        self.cpu_samples = []
        
    def start_test(self):
        """Mark the start of load testing"""
        self.start_time = time.perf_counter()
        
    def end_test(self):
        """Mark the end of load testing"""
        self.end_time = time.perf_counter()
        
    def record_request(self, response_time: float, success: bool = True):
        """Record a request result"""
        self.request_times.append(response_time)
        if success:
            self.success_count += 1
        else:
            self.error_count += 1
            
    def record_throughput_sample(self, requests_per_second: float):
        """Record throughput sample"""
        self.throughput_samples.append(requests_per_second)
        
    def record_resource_usage(self, memory_mb: float, cpu_percent: float):
        """Record resource usage sample"""
        self.memory_samples.append(memory_mb)
        self.cpu_samples.append(cpu_percent)
        
    def get_summary(self) -> Dict[str, Any]:
        """Get comprehensive test summary"""
        if not self.request_times:
            return {"error": "No requests recorded"}
            
        total_time = self.end_time - self.start_time if self.end_time else 0
        total_requests = len(self.request_times)
        
        percentiles = PerformanceTestUtils.calculate_percentiles(self.request_times)
        
        return {
            "test_duration_seconds": total_time,
            "total_requests": total_requests,
            "successful_requests": self.success_count,
            "failed_requests": self.error_count,
            "success_rate": self.success_count / total_requests if total_requests > 0 else 0,
            "requests_per_second": total_requests / total_time if total_time > 0 else 0,
            "response_times": percentiles,
            "average_throughput": statistics.mean(self.throughput_samples) if self.throughput_samples else 0,
            "peak_memory_mb": max(self.memory_samples) if self.memory_samples else 0,
            "average_cpu_percent": statistics.mean(self.cpu_samples) if self.cpu_samples else 0,
            "concurrent_users": self.concurrent_users
        }


class LoadTestWorker:
    """Worker for executing load test operations"""
    
    def __init__(self, worker_id: int, rich_message_service: RichMessageService):
        self.worker_id = worker_id
        self.rich_message_service = rich_message_service
        self.metrics = LoadTestMetrics()
        
    def create_messages_workload(self, content_batch: List[Dict], duration_seconds: int) -> LoadTestMetrics:
        """Execute message creation workload for specified duration"""
        self.metrics.start_test()
        end_time = time.time() + duration_seconds
        request_count = 0
        
        while time.time() < end_time:
            content = content_batch[request_count % len(content_batch)]
            
            start_request = time.perf_counter()
            try:
                flex_message = self.rich_message_service.create_flex_message(
                    title=content["title"],
                    content=content["content"],
                    image_url=content["image_url"],
                    content_id=f"{content['content_id']}_worker_{self.worker_id}_{request_count}",
                    include_interactions=True
                )
                
                end_request = time.perf_counter()
                response_time = (end_request - start_request) * 1000
                
                self.metrics.record_request(response_time, success=True)
                
            except Exception as e:
                end_request = time.perf_counter()
                response_time = (end_request - start_request) * 1000
                self.metrics.record_request(response_time, success=False)
                logger.error(f"Worker {self.worker_id} request failed: {str(e)}")
            
            request_count += 1
            
            # Small delay to prevent overwhelming the system
            time.sleep(0.01)
        
        self.metrics.end_test()
        return self.metrics
    
    def broadcast_messages_workload(self, messages: List, duration_seconds: int) -> LoadTestMetrics:
        """Execute message broadcast workload for specified duration"""
        self.metrics.start_test()
        end_time = time.time() + duration_seconds
        request_count = 0
        
        while time.time() < end_time:
            message = messages[request_count % len(messages)]
            
            start_request = time.perf_counter()
            try:
                result = self.rich_message_service.broadcast_rich_message(message)
                end_request = time.perf_counter()
                response_time = (end_request - start_request) * 1000
                
                self.metrics.record_request(response_time, success=result.get("success", False))
                
            except Exception as e:
                end_request = time.perf_counter()
                response_time = (end_request - start_request) * 1000
                self.metrics.record_request(response_time, success=False)
                logger.error(f"Worker {self.worker_id} broadcast failed: {str(e)}")
            
            request_count += 1
            time.sleep(0.05)  # Longer delay for broadcast operations
        
        self.metrics.end_test()
        return self.metrics
    
    def interaction_processing_workload(self, interactions: List[Dict], duration_seconds: int) -> LoadTestMetrics:
        """Execute interaction processing workload for specified duration"""
        interaction_handler = get_interaction_handler()
        
        self.metrics.start_test()
        end_time = time.time() + duration_seconds
        request_count = 0
        
        while time.time() < end_time:
            interaction = interactions[request_count % len(interactions)]
            
            start_request = time.perf_counter()
            try:
                result = interaction_handler.handle_user_interaction(
                    interaction["user_id"],
                    interaction["interaction_data"]
                )
                
                end_request = time.perf_counter()
                response_time = (end_request - start_request) * 1000
                
                self.metrics.record_request(response_time, success=result.get("success", False))
                
            except Exception as e:
                end_request = time.perf_counter()
                response_time = (end_request - start_request) * 1000
                self.metrics.record_request(response_time, success=False)
                logger.error(f"Worker {self.worker_id} interaction failed: {str(e)}")
            
            request_count += 1
            time.sleep(0.005)  # Short delay for interaction processing
        
        self.metrics.end_test()
        return self.metrics


class TestRichMessageLoadTesting:
    """Comprehensive load testing for Rich Message automation system"""
    
    @pytest.fixture
    def mock_line_bot_api(self):
        """Create mock LINE Bot API for load testing"""
        mock_api = Mock()
        mock_api.broadcast.return_value = None
        mock_api.narrowcast.return_value = None
        mock_api.create_rich_menu.return_value = "load_test_menu"
        mock_api.set_rich_menu_image.return_value = None
        
        # Add realistic delays for broadcast operations
        def mock_broadcast_with_delay(*args, **kwargs):
            time.sleep(0.05)  # 50ms delay
            return None
        
        def mock_narrowcast_with_delay(*args, **kwargs):
            time.sleep(0.03)  # 30ms delay
            return None
        
        mock_api.broadcast.side_effect = mock_broadcast_with_delay
        mock_api.narrowcast.side_effect = mock_narrowcast_with_delay
        
        return mock_api
    
    @pytest.fixture
    def rich_message_service(self, mock_line_bot_api):
        """Create RichMessageService for load testing"""
        return RichMessageService(line_bot_api=mock_line_bot_api)
    
    @pytest.fixture
    def load_test_content(self):
        """Generate content for load testing"""
        config = PerformanceTestUtils.get_config(PerformanceLevel.LOAD)
        return PerformanceTestUtils.generate_test_content(
            count=100,  # Fixed content pool for load testing
            title_template="Load Test Message {i}",
            content_template="Load test content for sustained performance testing. " * 8,
            category="load_testing"
        )
    
    @pytest.fixture
    def load_test_interactions(self):
        """Generate interactions for load testing"""
        interactions = []
        interaction_types = ["like", "share", "save", "react"]
        
        for user_id in range(50):  # 50 different users
            for content_id in range(20):  # 20 different content pieces
                for interaction_type in interaction_types:
                    interactions.append({
                        "user_id": f"load_user_{user_id:03d}",
                        "interaction_data": {
                            "action": "interaction",
                            "type": interaction_type,
                            "content_id": f"load_content_{content_id:03d}"
                        }
                    })
        
        return interactions
    
    def test_sustained_message_creation_load(self, rich_message_service, load_test_content):
        """Test sustained message creation under load"""
        config = PerformanceTestUtils.get_config(PerformanceLevel.LOAD)
        benchmarks = PerformanceTestUtils.get_benchmarks(PerformanceLevel.LOAD)
        
        num_workers = 8
        test_duration = 30  # 30 seconds for CI/CD compatibility
        
        # Create worker pool
        workers = []
        for i in range(num_workers):
            worker = LoadTestWorker(i, rich_message_service)
            workers.append(worker)
        
        # Execute load test
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = [
                executor.submit(
                    worker.create_messages_workload,
                    load_test_content,
                    test_duration
                )
                for worker in workers
            ]
            
            # Collect results
            worker_metrics = []
            for future in as_completed(futures):
                metrics = future.result()
                worker_metrics.append(metrics)
        
        # Aggregate metrics
        total_requests = sum(m.success_count + m.error_count for m in worker_metrics)
        total_successes = sum(m.success_count for m in worker_metrics)
        total_errors = sum(m.error_count for m in worker_metrics)
        
        all_response_times = []
        for metrics in worker_metrics:
            all_response_times.extend(metrics.request_times)
        
        overall_success_rate = total_successes / total_requests if total_requests > 0 else 0
        overall_throughput = total_requests / test_duration
        avg_response_time = statistics.mean(all_response_times) if all_response_times else 0
        max_response_time = max(all_response_times) if all_response_times else 0
        
        # Performance assertions
        assert overall_success_rate >= 0.95, f"Success rate {overall_success_rate:.2%} below 95%"
        assert overall_throughput >= benchmarks.min_message_creation_throughput, \
               f"Throughput {overall_throughput:.2f} below {benchmarks.min_message_creation_throughput}"
        assert avg_response_time <= benchmarks.single_message_creation_avg_ms, \
               f"Average response time {avg_response_time:.2f}ms above {benchmarks.single_message_creation_avg_ms}ms"
        
        print(f"Sustained Message Creation Load Test Results:")
        print(f"  Duration: {test_duration}s")
        print(f"  Workers: {num_workers}")
        print(f"  Total requests: {total_requests}")
        print(f"  Success rate: {overall_success_rate:.2%}")
        print(f"  Throughput: {overall_throughput:.2f} requests/sec")
        print(f"  Average response time: {avg_response_time:.2f}ms")
        print(f"  Maximum response time: {max_response_time:.2f}ms")
    
    def test_message_broadcast_load(self, rich_message_service, load_test_content):
        """Test message broadcast performance under load"""
        benchmarks = PerformanceTestUtils.get_benchmarks(PerformanceLevel.LOAD)
        
        # Pre-create messages for broadcasting
        messages = []
        for content in load_test_content[:20]:  # Use 20 messages for broadcast testing
            flex_message = rich_message_service.create_flex_message(
                title=content["title"],
                content=content["content"],
                image_url=content["image_url"],
                content_id=content["content_id"]
            )
            messages.append(flex_message)
        
        num_workers = 4  # Fewer workers for broadcast testing
        test_duration = 20  # Shorter duration due to API rate limits
        
        # Create worker pool for broadcast testing
        workers = []
        for i in range(num_workers):
            worker = LoadTestWorker(i, rich_message_service)
            workers.append(worker)
        
        # Execute broadcast load test
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = [
                executor.submit(
                    worker.broadcast_messages_workload,
                    messages,
                    test_duration
                )
                for worker in workers
            ]
            
            # Collect results
            worker_metrics = []
            for future in as_completed(futures):
                metrics = future.result()
                worker_metrics.append(metrics)
        
        # Aggregate broadcast metrics
        total_broadcasts = sum(m.success_count + m.error_count for m in worker_metrics)
        total_successes = sum(m.success_count for m in worker_metrics)
        
        all_response_times = []
        for metrics in worker_metrics:
            all_response_times.extend(metrics.request_times)
        
        broadcast_success_rate = total_successes / total_broadcasts if total_broadcasts > 0 else 0
        broadcast_throughput = total_broadcasts / test_duration
        avg_broadcast_time = statistics.mean(all_response_times) if all_response_times else 0
        
        # Performance assertions
        assert broadcast_success_rate >= 0.98, f"Broadcast success rate {broadcast_success_rate:.2%} below 98%"
        assert broadcast_throughput >= benchmarks.min_broadcast_throughput, \
               f"Broadcast throughput {broadcast_throughput:.2f} below {benchmarks.min_broadcast_throughput}"
        assert avg_broadcast_time <= benchmarks.broadcast_avg_ms, \
               f"Average broadcast time {avg_broadcast_time:.2f}ms above {benchmarks.broadcast_avg_ms}ms"
        
        print(f"Message Broadcast Load Test Results:")
        print(f"  Duration: {test_duration}s")
        print(f"  Workers: {num_workers}")
        print(f"  Total broadcasts: {total_broadcasts}")
        print(f"  Success rate: {broadcast_success_rate:.2%}")
        print(f"  Throughput: {broadcast_throughput:.2f} broadcasts/sec")
        print(f"  Average broadcast time: {avg_broadcast_time:.2f}ms")
    
    @patch('src.utils.metrics_storage.get_metrics_storage')
    def test_interaction_processing_load(self, mock_get_storage, load_test_interactions):
        """Test interaction processing under sustained load"""
        # Mock metrics storage
        mock_storage = Mock()
        mock_storage.store_metric.return_value = True
        mock_get_storage.return_value = mock_storage
        
        benchmarks = PerformanceTestUtils.get_benchmarks(PerformanceLevel.LOAD)
        
        num_workers = 6
        test_duration = 25
        
        # Create worker pool for interaction processing
        workers = []
        for i in range(num_workers):
            # Create a mock rich message service for each worker
            mock_api = Mock()
            mock_api.broadcast.return_value = None
            worker_service = RichMessageService(line_bot_api=mock_api)
            worker = LoadTestWorker(i, worker_service)
            workers.append(worker)
        
        # Execute interaction processing load test
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = [
                executor.submit(
                    worker.interaction_processing_workload,
                    load_test_interactions,
                    test_duration
                )
                for worker in workers
            ]
            
            # Collect results
            worker_metrics = []
            for future in as_completed(futures):
                metrics = future.result()
                worker_metrics.append(metrics)
        
        # Aggregate interaction metrics
        total_interactions = sum(m.success_count + m.error_count for m in worker_metrics)
        total_successes = sum(m.success_count for m in worker_metrics)
        
        all_response_times = []
        for metrics in worker_metrics:
            all_response_times.extend(metrics.request_times)
        
        interaction_success_rate = total_successes / total_interactions if total_interactions > 0 else 0
        interaction_throughput = total_interactions / test_duration
        avg_interaction_time = statistics.mean(all_response_times) if all_response_times else 0
        
        # Performance assertions
        assert interaction_success_rate >= 0.95, f"Interaction success rate {interaction_success_rate:.2%} below 95%"
        assert interaction_throughput >= benchmarks.min_interaction_processing_throughput, \
               f"Interaction throughput {interaction_throughput:.2f} below {benchmarks.min_interaction_processing_throughput}"
        assert avg_interaction_time <= benchmarks.interaction_processing_avg_ms, \
               f"Average interaction time {avg_interaction_time:.2f}ms above {benchmarks.interaction_processing_avg_ms}ms"
        
        print(f"Interaction Processing Load Test Results:")
        print(f"  Duration: {test_duration}s")
        print(f"  Workers: {num_workers}")
        print(f"  Total interactions: {total_interactions}")
        print(f"  Success rate: {interaction_success_rate:.2%}")
        print(f"  Throughput: {interaction_throughput:.2f} interactions/sec")
        print(f"  Average processing time: {avg_interaction_time:.2f}ms")
    
    @patch('src.utils.metrics_storage.get_metrics_storage')
    def test_analytics_system_load(self, mock_get_storage):
        """Test analytics system performance under high event load"""
        # Mock metrics storage with realistic performance
        mock_storage = Mock()
        
        def mock_store_metric(metric):
            time.sleep(0.001)  # 1ms storage delay
            return True
        
        mock_storage.store_metric.side_effect = mock_store_metric
        mock_storage.get_metrics.return_value = []
        mock_get_storage.return_value = mock_storage
        
        analytics_tracker = get_analytics_tracker()
        benchmarks = PerformanceTestUtils.get_benchmarks(PerformanceLevel.LOAD)
        
        # Generate high volume of analytics events
        num_events = 2000
        num_users = 100
        num_content = 20
        
        event_types = [
            ("delivery", analytics_tracker.track_message_delivery),
            ("open", lambda **kwargs: analytics_tracker.track_user_interaction(
                interaction_type=analytics_tracker.InteractionType.MESSAGE_OPENED, **kwargs)),
            ("interaction", lambda **kwargs: analytics_tracker.track_user_interaction(
                interaction_type=analytics_tracker.InteractionType.BUTTON_CLICKED, **kwargs)),
            ("share", lambda **kwargs: analytics_tracker.track_user_interaction(
                interaction_type=analytics_tracker.InteractionType.CONTENT_SHARED, **kwargs))
        ]
        
        # Test analytics event processing
        start_time = time.perf_counter()
        
        for i in range(num_events):
            event_type, track_function = event_types[i % len(event_types)]
            user_id = f"load_user_{i % num_users}"
            content_id = f"load_content_{i % num_content}"
            
            if event_type == "delivery":
                track_function(
                    user_id=user_id,
                    content_category="load_testing",
                    template_id=content_id,
                    delivery_time_ms=100 + (i % 50)
                )
            else:
                track_function(
                    user_id=user_id,
                    content_category="load_testing",
                    template_id=content_id
                )
        
        end_time = time.perf_counter()
        processing_time = (end_time - start_time) * 1000
        
        # Test system metrics calculation under load
        metrics_start = time.perf_counter()
        system_metrics = analytics_tracker.calculate_system_metrics(force_recalculate=True)
        metrics_end = time.perf_counter()
        metrics_calculation_time = (metrics_end - metrics_start) * 1000
        
        # Calculate analytics performance
        events_per_second = num_events / (processing_time / 1000)
        
        # Performance assertions
        assert processing_time <= benchmarks.analytics_processing_ms * 2, \
               f"Analytics processing {processing_time:.2f}ms exceeds threshold"
        assert events_per_second >= benchmarks.analytics_throughput / 2, \
               f"Analytics throughput {events_per_second:.2f} below threshold"
        assert metrics_calculation_time <= benchmarks.metrics_calculation_ms, \
               f"Metrics calculation {metrics_calculation_time:.2f}ms exceeds threshold"
        
        print(f"Analytics System Load Test Results:")
        print(f"  Total events: {num_events}")
        print(f"  Processing time: {processing_time:.2f}ms")
        print(f"  Events per second: {events_per_second:.2f}")
        print(f"  Metrics calculation time: {metrics_calculation_time:.2f}ms")
        print(f"  System metrics calculated: {system_metrics is not None}")
    
    def test_memory_stability_under_load(self, rich_message_service, load_test_content):
        """Test memory stability during sustained load"""
        import psutil
        import gc
        
        process = psutil.Process()
        benchmarks = PerformanceTestUtils.get_benchmarks(PerformanceLevel.LOAD)
        
        # Get baseline memory
        gc.collect()
        baseline_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        memory_samples = [baseline_memory]
        max_memory_increase = 0
        
        # Sustained load test with memory monitoring
        test_duration = 30  # 30 seconds
        end_time = time.time() + test_duration
        message_count = 0
        
        while time.time() < end_time:
            # Create batch of messages
            for content in load_test_content[:10]:  # Process in batches of 10
                flex_message = rich_message_service.create_flex_message(
                    title=content["title"],
                    content=content["content"],
                    image_url=content["image_url"],
                    content_id=f"{content['content_id']}_memory_test_{message_count}",
                    include_interactions=True
                )
                message_count += 1
                
                # Monitor memory every 20 messages
                if message_count % 20 == 0:
                    current_memory = process.memory_info().rss / 1024 / 1024
                    memory_increase = current_memory - baseline_memory
                    memory_samples.append(current_memory)
                    max_memory_increase = max(max_memory_increase, memory_increase)
        
        # Force garbage collection and check final memory
        gc.collect()
        final_memory = process.memory_info().rss / 1024 / 1024
        final_memory_increase = final_memory - baseline_memory
        
        # Calculate memory statistics
        avg_memory = statistics.mean(memory_samples)
        peak_memory = max(memory_samples)
        
        # Memory stability assertions
        assert max_memory_increase <= benchmarks.max_memory_increase_mb, \
               f"Peak memory increase {max_memory_increase:.2f}MB exceeds {benchmarks.max_memory_increase_mb}MB"
        assert final_memory_increase <= benchmarks.max_memory_after_cleanup_mb, \
               f"Final memory increase {final_memory_increase:.2f}MB indicates potential memory leak"
        
        print(f"Memory Stability Load Test Results:")
        print(f"  Test duration: {test_duration}s")
        print(f"  Messages created: {message_count}")
        print(f"  Baseline memory: {baseline_memory:.2f}MB")
        print(f"  Peak memory: {peak_memory:.2f}MB")
        print(f"  Max memory increase: {max_memory_increase:.2f}MB")
        print(f"  Final memory: {final_memory:.2f}MB")
        print(f"  Final memory increase: {final_memory_increase:.2f}MB")
        print(f"  Average memory: {avg_memory:.2f}MB")
    
    def test_concurrent_user_simulation(self, rich_message_service, load_test_content, load_test_interactions):
        """Simulate multiple concurrent users with mixed workloads"""
        benchmarks = PerformanceTestUtils.get_benchmarks(PerformanceLevel.LOAD)
        
        num_concurrent_users = 12
        test_duration = 20
        
        # Define mixed workload functions
        def user_workload(user_id: int, service: RichMessageService) -> Dict[str, Any]:
            """Simulate realistic user behavior with mixed operations"""
            metrics = {
                "user_id": user_id,
                "operations": 0,
                "errors": 0,
                "response_times": []
            }
            
            end_time = time.time() + test_duration
            interaction_handler = get_interaction_handler()
            
            while time.time() < end_time:
                operation_type = ["create", "interact", "create", "interact", "broadcast"][metrics["operations"] % 5]
                
                start_op = time.perf_counter()
                try:
                    if operation_type == "create":
                        content = load_test_content[metrics["operations"] % len(load_test_content)]
                        flex_message = service.create_flex_message(
                            title=content["title"],
                            content=content["content"],
                            image_url=content["image_url"],
                            content_id=f"user_{user_id}_op_{metrics['operations']}"
                        )
                        
                    elif operation_type == "interact":
                        interaction = load_test_interactions[metrics["operations"] % len(load_test_interactions)]
                        interaction_handler.handle_user_interaction(
                            f"concurrent_user_{user_id}",
                            interaction["interaction_data"]
                        )
                        
                    elif operation_type == "broadcast":
                        # Create and broadcast a message
                        content = load_test_content[metrics["operations"] % len(load_test_content)]
                        flex_message = service.create_flex_message(
                            title=content["title"],
                            content=content["content"],
                            content_id=f"broadcast_user_{user_id}_op_{metrics['operations']}"
                        )
                        service.broadcast_rich_message(flex_message)
                    
                    end_op = time.perf_counter()
                    response_time = (end_op - start_op) * 1000
                    metrics["response_times"].append(response_time)
                    metrics["operations"] += 1
                    
                except Exception as e:
                    end_op = time.perf_counter()
                    response_time = (end_op - start_op) * 1000
                    metrics["response_times"].append(response_time)
                    metrics["errors"] += 1
                    logger.error(f"User {user_id} operation failed: {str(e)}")
                
                # Realistic user pause between operations
                time.sleep(0.1 + (user_id % 3) * 0.05)  # 100-250ms between operations
            
            return metrics
        
        # Execute concurrent user simulation
        with ThreadPoolExecutor(max_workers=num_concurrent_users) as executor:
            futures = []
            
            for user_id in range(num_concurrent_users):
                # Each user gets their own service instance to avoid conflicts
                mock_api = Mock()
                mock_api.broadcast.return_value = None
                mock_api.narrowcast.return_value = None
                user_service = RichMessageService(line_bot_api=mock_api)
                
                future = executor.submit(user_workload, user_id, user_service)
                futures.append(future)
            
            # Collect results from all users
            user_results = []
            for future in as_completed(futures):
                result = future.result()
                user_results.append(result)
        
        # Aggregate concurrent user metrics
        total_operations = sum(r["operations"] for r in user_results)
        total_errors = sum(r["errors"] for r in user_results)
        
        all_response_times = []
        for result in user_results:
            all_response_times.extend(result["response_times"])
        
        overall_success_rate = (total_operations - total_errors) / total_operations if total_operations > 0 else 0
        operations_per_second = total_operations / test_duration
        avg_response_time = statistics.mean(all_response_times) if all_response_times else 0
        max_response_time = max(all_response_times) if all_response_times else 0
        
        # Performance assertions for concurrent users
        assert overall_success_rate >= 0.90, f"Concurrent user success rate {overall_success_rate:.2%} below 90%"
        assert operations_per_second >= 5.0, f"Operations per second {operations_per_second:.2f} too low"
        assert avg_response_time <= 500.0, f"Average response time {avg_response_time:.2f}ms too high"
        
        print(f"Concurrent User Simulation Results:")
        print(f"  Concurrent users: {num_concurrent_users}")
        print(f"  Test duration: {test_duration}s")
        print(f"  Total operations: {total_operations}")
        print(f"  Total errors: {total_errors}")
        print(f"  Success rate: {overall_success_rate:.2%}")
        print(f"  Operations per second: {operations_per_second:.2f}")
        print(f"  Average response time: {avg_response_time:.2f}ms")
        print(f"  Maximum response time: {max_response_time:.2f}ms")
        print(f"  Operations per user: {total_operations / num_concurrent_users:.1f}")