"""
Performance tests for API routing to validate <50ms overhead target.

Tests routing decision performance under various conditions
including cache hits, cache misses, and concurrent access.
"""

import pytest
import time
import asyncio
import threading
from unittest.mock import Mock, patch
from concurrent.futures import ThreadPoolExecutor
from statistics import mean, median

from src.utils.api_router import APIRouter, APIType
from src.utils.capability_cache import CapabilityCache
from src.utils.azure_api_detector import AzureOpenAICapabilityDetector
from src.services.openai_service import OpenAIService


class TestRoutingPerformance:
    """Performance test suite for API routing."""
    
    @pytest.fixture
    def mock_config(self):
        """Mock centralized configuration."""
        config = Mock()
        config.azure_openai.prefer_responses_api = True
        config.azure_openai.force_chat_completions = False
        config.azure_openai.capability_cache_ttl = 300
        config.azure_openai.routing_performance_threshold_ms = 50
        return config
    
    @pytest.fixture
    def fast_cache(self):
        """Mock fast cache for performance testing."""
        cache = Mock(spec=CapabilityCache)
        cache.get_cached_capabilities.return_value = {
            'responses_api': True,
            'chat_completions': True,
            'last_updated': '2025-08-03T12:00:00Z',
            'ttl_seconds': 300
        }
        return cache
    
    @pytest.fixture
    def api_router(self, mock_config, fast_cache):
        """Create API router with fast mocked dependencies."""
        detector = Mock(spec=AzureOpenAICapabilityDetector)
        return APIRouter(
            settings=mock_config,
            capability_detector=detector,
            capability_cache=fast_cache
        )

    def test_single_routing_decision_performance(self, api_router):
        """Test single routing decision stays under 50ms."""
        # Warm up
        api_router.should_use_responses_api()
        
        # Measure performance
        start_time = time.perf_counter()
        result = api_router.should_use_responses_api()
        end_time = time.perf_counter()
        
        duration_ms = (end_time - start_time) * 1000
        
        assert result is True
        assert duration_ms < 50, f"Routing decision took {duration_ms:.2f}ms, exceeds 50ms target"

    def test_multiple_routing_decisions_performance(self, api_router):
        """Test multiple consecutive routing decisions performance."""
        num_decisions = 100
        durations = []
        
        # Warm up
        api_router.should_use_responses_api()
        
        # Measure multiple decisions
        for _ in range(num_decisions):
            start_time = time.perf_counter()
            result = api_router.should_use_responses_api()
            end_time = time.perf_counter()
            
            duration_ms = (end_time - start_time) * 1000
            durations.append(duration_ms)
            assert result is True
        
        # Analyze performance statistics
        avg_duration = mean(durations)
        median_duration = median(durations)
        max_duration = max(durations)
        
        # All decisions should be under 50ms
        assert max_duration < 50, f"Max routing decision took {max_duration:.2f}ms"
        assert avg_duration < 25, f"Average routing decision took {avg_duration:.2f}ms"
        assert median_duration < 20, f"Median routing decision took {median_duration:.2f}ms"

    def test_concurrent_routing_decisions_performance(self, api_router):
        """Test concurrent routing decisions performance."""
        num_threads = 10
        decisions_per_thread = 20
        results = []
        
        def routing_task():
            thread_durations = []
            for _ in range(decisions_per_thread):
                start_time = time.perf_counter()
                result = api_router.should_use_responses_api()
                end_time = time.perf_counter()
                
                duration_ms = (end_time - start_time) * 1000
                thread_durations.append(duration_ms)
                assert result is True
            
            return thread_durations
        
        # Execute concurrent routing decisions
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(routing_task) for _ in range(num_threads)]
            
            for future in futures:
                thread_durations = future.result()
                results.extend(thread_durations)
        
        # Analyze concurrent performance
        avg_duration = mean(results)
        max_duration = max(results)
        
        # Performance should remain good under concurrency
        assert max_duration < 100, f"Max concurrent routing took {max_duration:.2f}ms"
        assert avg_duration < 50, f"Average concurrent routing took {avg_duration:.2f}ms"

    def test_cache_miss_performance(self, mock_config):
        """Test routing performance with cache miss."""
        # Mock cache that returns None (cache miss)
        slow_cache = Mock(spec=CapabilityCache)
        slow_cache.get_cached_capabilities.return_value = None
        
        detector = Mock(spec=AzureOpenAICapabilityDetector)
        api_router = APIRouter(
            settings=mock_config,
            capability_detector=detector,
            capability_cache=slow_cache
        )
        
        # Measure performance with cache miss
        start_time = time.perf_counter()
        result = api_router.should_use_responses_api()
        end_time = time.perf_counter()
        
        duration_ms = (end_time - start_time) * 1000
        
        # Should default to Chat Completions on cache miss
        assert result is False
        # Should still be fast even with cache miss
        assert duration_ms < 50, f"Cache miss routing took {duration_ms:.2f}ms"

    def test_routing_with_slow_cache(self, mock_config):
        """Test routing performance with artificially slow cache."""
        # Mock slow cache operation
        def slow_cache_get():
            time.sleep(0.01)  # 10ms delay
            return {
                'responses_api': True,
                'chat_completions': True,
                'last_updated': '2025-08-03T12:00:00Z',
                'ttl_seconds': 300
            }
        
        slow_cache = Mock(spec=CapabilityCache)
        slow_cache.get_cached_capabilities.side_effect = slow_cache_get
        
        detector = Mock(spec=AzureOpenAICapabilityDetector)
        api_router = APIRouter(
            settings=mock_config,
            capability_detector=detector,
            capability_cache=slow_cache
        )
        
        # Measure performance with slow cache
        start_time = time.perf_counter()
        result = api_router.should_use_responses_api()
        end_time = time.perf_counter()
        
        duration_ms = (end_time - start_time) * 1000
        
        assert result is True
        # Should still meet performance target despite slow cache
        assert duration_ms < 50, f"Slow cache routing took {duration_ms:.2f}ms"

    @pytest.mark.asyncio
    async def test_openai_service_routing_performance(self):
        """Test end-to-end OpenAI service routing performance."""
        # Mock settings
        mock_settings = Mock()
        mock_settings.AZURE_OPENAI_API_KEY = "test-key"
        mock_settings.AZURE_OPENAI_ENDPOINT = "https://test.openai.azure.com"
        mock_settings.AZURE_OPENAI_DEPLOYMENT_NAME = "test-deployment"
        mock_settings.AZURE_OPENAI_API_VERSION = "2024-02-15-preview"
        
        mock_conversation_service = Mock()
        
        with patch('src.services.openai_service.get_config') as mock_get_config:
            # Mock centralized config
            mock_config = Mock()
            mock_config.azure_openai.enable_startup_validation = False
            mock_config.azure_openai.capability_cache_ttl = 300
            mock_get_config.return_value = mock_config
            
            with patch('src.services.openai_service.AzureOpenAI'):
                service = OpenAIService(mock_settings, mock_conversation_service)
                
                # Mock fast routing decision
                service.api_router = Mock()
                service.api_router.should_use_responses_api.return_value = True
                
                # Test routing performance
                durations = []
                for _ in range(50):
                    start_time = time.perf_counter()
                    decision = service._should_use_responses_api()
                    end_time = time.perf_counter()
                    
                    duration_ms = (end_time - start_time) * 1000
                    durations.append(duration_ms)
                    assert decision is True
                
                # Analyze performance
                avg_duration = mean(durations)
                max_duration = max(durations)
                
                assert max_duration < 50, f"Max service routing took {max_duration:.2f}ms"
                assert avg_duration < 25, f"Average service routing took {avg_duration:.2f}ms"

    def test_memory_usage_during_routing(self, api_router):
        """Test memory usage stability during routing decisions."""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        # Perform many routing decisions
        for _ in range(1000):
            result = api_router.should_use_responses_api()
            assert result is True
        
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory
        
        # Memory increase should be minimal (< 1MB)
        assert memory_increase < 1024 * 1024, f"Memory increased by {memory_increase} bytes"

    def test_routing_decision_consistency_performance(self, api_router):
        """Test performance consistency across many routing decisions."""
        num_decisions = 500
        durations = []
        
        # Measure many routing decisions
        for _ in range(num_decisions):
            start_time = time.perf_counter()
            result = api_router.should_use_responses_api()
            end_time = time.perf_counter()
            
            duration_ms = (end_time - start_time) * 1000
            durations.append(duration_ms)
            assert result is True
        
        # Calculate performance metrics
        avg_duration = mean(durations)
        min_duration = min(durations)
        max_duration = max(durations)
        
        # Performance should be consistent
        assert max_duration < 50, f"Max duration: {max_duration:.2f}ms"
        assert avg_duration < 20, f"Average duration: {avg_duration:.2f}ms"
        
        # Variance should be low (consistent performance)
        variance = max_duration - min_duration
        assert variance < 30, f"Performance variance too high: {variance:.2f}ms"

    def test_routing_performance_under_load(self, api_router):
        """Test routing performance under simulated load."""
        import time
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        def load_test_worker(worker_id, num_operations):
            """Worker function for load testing."""
            durations = []
            for _ in range(num_operations):
                start_time = time.perf_counter()
                result = api_router.should_use_responses_api()
                end_time = time.perf_counter()
                
                duration_ms = (end_time - start_time) * 1000
                durations.append(duration_ms)
                assert result is True
            
            return durations
        
        # Simulate high load
        num_workers = 20
        operations_per_worker = 25
        all_durations = []
        
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            # Submit load test tasks
            futures = [
                executor.submit(load_test_worker, i, operations_per_worker)
                for i in range(num_workers)
            ]
            
            # Collect results
            for future in as_completed(futures):
                worker_durations = future.result()
                all_durations.extend(worker_durations)
        
        # Analyze load test results
        avg_duration = mean(all_durations)
        max_duration = max(all_durations)
        p95_duration = sorted(all_durations)[int(len(all_durations) * 0.95)]
        
        # Performance should remain acceptable under load
        assert max_duration < 100, f"Max duration under load: {max_duration:.2f}ms"
        assert avg_duration < 50, f"Average duration under load: {avg_duration:.2f}ms"
        assert p95_duration < 75, f"95th percentile duration: {p95_duration:.2f}ms"

    def test_routing_performance_warm_vs_cold(self, api_router):
        """Test routing performance comparison between cold and warm states."""
        # Cold start (first call)
        cold_start_time = time.perf_counter()
        cold_result = api_router.should_use_responses_api()
        cold_end_time = time.perf_counter()
        cold_duration_ms = (cold_end_time - cold_start_time) * 1000
        
        # Warm calls (subsequent calls)
        warm_durations = []
        for _ in range(10):
            warm_start_time = time.perf_counter()
            warm_result = api_router.should_use_responses_api()
            warm_end_time = time.perf_counter()
            warm_duration_ms = (warm_end_time - warm_start_time) * 1000
            warm_durations.append(warm_duration_ms)
            assert warm_result is True
        
        avg_warm_duration = mean(warm_durations)
        
        assert cold_result is True
        
        # Both cold and warm should meet performance targets
        assert cold_duration_ms < 50, f"Cold start took {cold_duration_ms:.2f}ms"
        assert avg_warm_duration < 25, f"Warm calls averaged {avg_warm_duration:.2f}ms"
        
        # Warm calls should be faster than cold start
        assert avg_warm_duration <= cold_duration_ms, "Warm calls should be faster than cold start"

    def measure_routing_overhead(self, api_router, num_samples=100):
        """Helper method to measure routing overhead."""
        durations = []
        
        for _ in range(num_samples):
            start_time = time.perf_counter()
            result = api_router.should_use_responses_api()
            end_time = time.perf_counter()
            
            duration_ms = (end_time - start_time) * 1000
            durations.append(duration_ms)
            assert result is True
        
        return {
            'avg': mean(durations),
            'min': min(durations),
            'max': max(durations),
            'median': median(durations),
            'samples': len(durations)
        }

    def test_comprehensive_performance_analysis(self, api_router):
        """Comprehensive performance analysis of routing decisions."""
        # Measure baseline performance
        baseline_metrics = self.measure_routing_overhead(api_router, 200)
        
        # Performance assertions
        assert baseline_metrics['max'] < 50, f"Max overhead: {baseline_metrics['max']:.2f}ms"
        assert baseline_metrics['avg'] < 25, f"Average overhead: {baseline_metrics['avg']:.2f}ms"
        assert baseline_metrics['median'] < 20, f"Median overhead: {baseline_metrics['median']:.2f}ms"
        
        # Log performance metrics for analysis
        print(f"Routing Performance Metrics:")
        print(f"  Average: {baseline_metrics['avg']:.2f}ms")
        print(f"  Median:  {baseline_metrics['median']:.2f}ms")
        print(f"  Min:     {baseline_metrics['min']:.2f}ms")
        print(f"  Max:     {baseline_metrics['max']:.2f}ms")
        print(f"  Samples: {baseline_metrics['samples']}")