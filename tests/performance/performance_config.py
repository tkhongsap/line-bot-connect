"""
Performance testing configuration and benchmarks for Rich Message automation.

This module defines performance thresholds, test configurations, and
benchmark standards for the Rich Message generation system.
"""

from dataclasses import dataclass
from typing import Dict, Any, List
from enum import Enum


class PerformanceLevel(Enum):
    """Performance testing levels"""
    BASIC = "basic"
    STANDARD = "standard"
    STRESS = "stress"
    LOAD = "load"


@dataclass
class PerformanceBenchmarks:
    """Performance benchmark thresholds for different operations"""
    
    # Single message creation benchmarks (milliseconds)
    single_message_creation_avg_ms: float = 50.0
    single_message_creation_max_ms: float = 100.0
    
    # Batch creation benchmarks
    small_batch_total_ms: float = 1000.0  # 10 messages
    medium_batch_total_ms: float = 5000.0  # 50 messages
    large_batch_total_ms: float = 10000.0  # 100 messages
    
    # Throughput benchmarks (operations per second)
    min_message_creation_throughput: float = 10.0
    min_broadcast_throughput: float = 5.0
    min_interaction_processing_throughput: float = 20.0
    
    # Delivery benchmarks (milliseconds)
    broadcast_avg_ms: float = 200.0
    broadcast_max_ms: float = 500.0
    narrowcast_avg_ms: float = 150.0
    narrowcast_max_ms: float = 400.0
    
    # Image composition benchmarks (milliseconds)
    simple_composition_ms: float = 200.0
    medium_composition_ms: float = 500.0
    complex_composition_ms: float = 1000.0
    
    # Content generation benchmarks (milliseconds)
    content_generation_avg_ms: float = 300.0
    content_generation_max_ms: float = 800.0
    
    # Template selection benchmarks (milliseconds)
    template_selection_avg_ms: float = 50.0
    template_selection_max_ms: float = 150.0
    
    # End-to-end pipeline benchmarks (milliseconds)
    pipeline_avg_ms: float = 1000.0
    pipeline_max_ms: float = 1500.0
    
    # Interaction handling benchmarks
    interaction_processing_avg_ms: float = 50.0
    interaction_processing_max_ms: float = 200.0
    
    # Analytics processing benchmarks
    analytics_processing_ms: float = 5000.0  # For 500 events
    analytics_throughput: float = 50.0  # Events per second
    metrics_calculation_ms: float = 1000.0
    
    # Memory usage benchmarks (MB)
    max_memory_increase_mb: float = 500.0
    max_memory_after_cleanup_mb: float = 100.0
    
    # Concurrent processing benchmarks
    concurrent_processing_ms: float = 5000.0  # 4 threads, 10 messages each
    concurrent_avg_message_ms: float = 100.0
    concurrent_throughput: float = 5.0
    
    # Database/Storage benchmarks (milliseconds)
    metrics_storage_avg_ms: float = 10.0
    metrics_retrieval_avg_ms: float = 50.0
    bulk_storage_ms: float = 1000.0  # For 100 metrics


@dataclass
class TestConfiguration:
    """Configuration for different types of performance tests"""
    
    # Test data sizes
    small_batch_size: int = 10
    medium_batch_size: int = 50
    large_batch_size: int = 100
    stress_batch_size: int = 500
    
    # Concurrent testing parameters
    num_threads: int = 4
    messages_per_thread: int = 10
    max_concurrent_threads: int = 8
    
    # Load testing parameters
    load_test_duration_seconds: int = 60
    load_test_requests_per_second: int = 10
    
    # Stress testing parameters
    stress_test_max_memory_mb: int = 1000
    stress_test_max_duration_seconds: int = 300
    
    # Analytics load testing
    analytics_events_count: int = 500
    analytics_users_count: int = 50
    analytics_content_count: int = 10
    
    # Performance sampling
    performance_samples: int = 20  # Number of iterations for averaging
    warmup_iterations: int = 3  # Warmup runs before measurement


# Performance test configurations for different levels
PERFORMANCE_CONFIGS = {
    PerformanceLevel.BASIC: TestConfiguration(
        small_batch_size=5,
        medium_batch_size=20,
        large_batch_size=50,
        num_threads=2,
        messages_per_thread=5,
        analytics_events_count=100,
        performance_samples=10
    ),
    
    PerformanceLevel.STANDARD: TestConfiguration(
        small_batch_size=10,
        medium_batch_size=50,
        large_batch_size=100,
        num_threads=4,
        messages_per_thread=10,
        analytics_events_count=500,
        performance_samples=20
    ),
    
    PerformanceLevel.STRESS: TestConfiguration(
        small_batch_size=50,
        medium_batch_size=200,
        large_batch_size=500,
        stress_batch_size=1000,
        num_threads=8,
        messages_per_thread=25,
        analytics_events_count=2000,
        performance_samples=10,
        stress_test_max_memory_mb=2000,
        stress_test_max_duration_seconds=600
    ),
    
    PerformanceLevel.LOAD: TestConfiguration(
        load_test_duration_seconds=300,  # 5 minutes
        load_test_requests_per_second=20,
        max_concurrent_threads=16,
        analytics_events_count=5000,
        performance_samples=5
    )
}

# Default benchmarks for standard performance level
DEFAULT_BENCHMARKS = PerformanceBenchmarks()

# Adjusted benchmarks for different performance levels
PERFORMANCE_BENCHMARKS = {
    PerformanceLevel.BASIC: PerformanceBenchmarks(
        # More relaxed thresholds for basic testing
        single_message_creation_avg_ms=100.0,
        single_message_creation_max_ms=200.0,
        small_batch_total_ms=2000.0,
        medium_batch_total_ms=10000.0,
        min_message_creation_throughput=5.0,
        pipeline_avg_ms=2000.0,
        pipeline_max_ms=3000.0
    ),
    
    PerformanceLevel.STANDARD: DEFAULT_BENCHMARKS,
    
    PerformanceLevel.STRESS: PerformanceBenchmarks(
        # Tighter thresholds for stress testing
        single_message_creation_avg_ms=30.0,
        single_message_creation_max_ms=80.0,
        small_batch_total_ms=500.0,
        medium_batch_total_ms=3000.0,
        large_batch_total_ms=8000.0,
        min_message_creation_throughput=15.0,
        pipeline_avg_ms=800.0,
        pipeline_max_ms=1200.0,
        max_memory_increase_mb=1000.0,
        concurrent_processing_ms=3000.0
    ),
    
    PerformanceLevel.LOAD: PerformanceBenchmarks(
        # Focus on sustained performance under load
        min_message_creation_throughput=8.0,
        min_broadcast_throughput=3.0,
        min_interaction_processing_throughput=15.0,
        analytics_throughput=30.0,
        concurrent_throughput=3.0,
        pipeline_avg_ms=1200.0,
        pipeline_max_ms=2000.0
    )
}


class PerformanceTestUtils:
    """Utility functions for performance testing"""
    
    @staticmethod
    def get_config(level: PerformanceLevel = PerformanceLevel.STANDARD) -> TestConfiguration:
        """Get test configuration for specified performance level"""
        return PERFORMANCE_CONFIGS[level]
    
    @staticmethod
    def get_benchmarks(level: PerformanceLevel = PerformanceLevel.STANDARD) -> PerformanceBenchmarks:
        """Get performance benchmarks for specified level"""
        return PERFORMANCE_BENCHMARKS[level]
    
    @staticmethod
    def format_performance_result(
        test_name: str,
        measured_value: float,
        threshold: float,
        unit: str = "ms",
        higher_is_better: bool = False
    ) -> str:
        """Format performance test result for display"""
        if higher_is_better:
            passed = measured_value >= threshold
            comparison = "≥" if passed else "<"
        else:
            passed = measured_value <= threshold
            comparison = "≤" if passed else ">"
        
        status = "PASS" if passed else "FAIL"
        
        return (
            f"{test_name}: {measured_value:.2f}{unit} "
            f"({comparison} {threshold:.2f}{unit}) - {status}"
        )
    
    @staticmethod
    def generate_test_content(
        count: int,
        title_template: str = "Test Message {i}",
        content_template: str = "Test content for message {i}. " * 5,
        category: str = "performance_test"
    ) -> List[Dict[str, Any]]:
        """Generate test content for performance testing"""
        content_list = []
        
        for i in range(count):
            content_list.append({
                "title": title_template.format(i=i),
                "content": content_template.format(i=i),
                "image_url": f"https://example.com/test_image_{i % 5}.jpg",
                "content_id": f"perf_content_{i:04d}",
                "category": category,
                "template_id": f"template_{i % 3}",
                "user_id": f"perf_user_{i % 10}"
            })
        
        return content_list
    
    @staticmethod
    def calculate_percentiles(values: List[float]) -> Dict[str, float]:
        """Calculate performance percentiles"""
        import statistics
        
        sorted_values = sorted(values)
        length = len(sorted_values)
        
        return {
            "p50": statistics.median(sorted_values),
            "p90": sorted_values[int(length * 0.9)] if length > 10 else max(sorted_values),
            "p95": sorted_values[int(length * 0.95)] if length > 20 else max(sorted_values),
            "p99": sorted_values[int(length * 0.99)] if length > 100 else max(sorted_values),
            "min": min(sorted_values),
            "max": max(sorted_values),
            "mean": statistics.mean(sorted_values),
            "std_dev": statistics.stdev(sorted_values) if length > 1 else 0.0
        }


# Test data templates
PERFORMANCE_TEST_TEMPLATES = {
    "simple": {
        "title": "Simple Test Message",
        "content": "Simple test content.",
        "complexity_factor": 1.0
    },
    
    "medium": {
        "title": "Medium Complexity Test Message with More Details",
        "content": "Medium complexity test content with substantial text. " * 10,
        "complexity_factor": 2.0
    },
    
    "complex": {
        "title": "Very Detailed and Comprehensive Test Message for Complex Scenario Testing with Multiple Elements",
        "content": "Complex test content with extensive details and multiple paragraphs. " * 25,
        "complexity_factor": 5.0
    }
}

# Performance monitoring configuration
PERFORMANCE_MONITORING = {
    "enable_detailed_logging": True,
    "log_percentiles": True,
    "save_raw_measurements": True,
    "generate_performance_report": True,
    "report_format": "json",  # json, csv, html
    "monitor_memory_usage": True,
    "monitor_cpu_usage": True,
    "profile_slow_operations": True,
    "slow_operation_threshold_ms": 500.0
}