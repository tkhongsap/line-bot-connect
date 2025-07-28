#!/usr/bin/env python3
"""
Performance benchmarks for connection pool optimization.

This script provides benchmarks to evaluate the performance improvements
from connection pooling, leak detection, and monitoring systems.
"""

import asyncio
import time
import statistics
import concurrent.futures
import threading
from typing import List, Dict, Any
import requests
from contextlib import contextmanager

from src.utils.connection_pool import connection_pool_manager, ConnectionPoolManager
from src.services.openai_service import OpenAIService
from src.services.line_service import LineService
from src.config.settings import Settings


class ConnectionPoolBenchmark:
    """Benchmark suite for connection pool performance evaluation."""
    
    def __init__(self):
        self.results = {}
        self.test_url = "https://httpbin.org/delay/0.1"  # Simple test endpoint
        
    def run_all_benchmarks(self) -> Dict[str, Any]:
        """Run all benchmark tests and return comprehensive results."""
        print("🚀 Starting Connection Pool Performance Benchmarks")
        print("=" * 60)
        
        # Benchmark 1: Connection pooling vs non-pooled requests
        print("\n📊 Benchmark 1: Connection Pooling Performance")
        self.results['connection_pooling'] = self.benchmark_connection_pooling()
        
        # Benchmark 2: Concurrent request handling
        print("\n📊 Benchmark 2: Concurrent Request Handling")
        self.results['concurrent_requests'] = self.benchmark_concurrent_requests()
        
        # Benchmark 3: Connection reuse efficiency
        print("\n📊 Benchmark 3: Connection Reuse Efficiency")
        self.results['connection_reuse'] = self.benchmark_connection_reuse()
        
        # Benchmark 4: Memory usage with leak detection
        print("\n📊 Benchmark 4: Memory Usage & Leak Detection")
        self.results['memory_efficiency'] = self.benchmark_memory_efficiency()
        
        # Benchmark 5: Health monitoring overhead
        print("\n📊 Benchmark 5: Monitoring Overhead")
        self.results['monitoring_overhead'] = self.benchmark_monitoring_overhead()
        
        # Generate summary report
        self.generate_benchmark_report()
        
        return self.results
    
    def benchmark_connection_pooling(self) -> Dict[str, Any]:
        """Compare pooled vs non-pooled connection performance."""
        num_requests = 50
        
        # Test without connection pooling
        print("  Testing without connection pooling...")
        start_time = time.time()
        non_pooled_times = []
        
        for _ in range(num_requests):
            request_start = time.time()
            try:
                response = requests.get(self.test_url, timeout=5)
                request_time = time.time() - request_start
                non_pooled_times.append(request_time)
            except Exception as e:
                print(f"    Non-pooled request failed: {e}")
        
        non_pooled_total = time.time() - start_time
        
        # Test with connection pooling
        print("  Testing with connection pooling...")
        session = connection_pool_manager.create_session_with_pooling(
            name="benchmark_test",
            pool_maxsize=10,
            enable_keep_alive=True
        )
        
        start_time = time.time()
        pooled_times = []
        
        for _ in range(num_requests):
            request_start = time.time()
            try:
                response = session.get(self.test_url, timeout=5)
                request_time = time.time() - request_start
                pooled_times.append(request_time)
            except Exception as e:
                print(f"    Pooled request failed: {e}")
        
        pooled_total = time.time() - start_time
        
        # Cleanup
        connection_pool_manager.force_cleanup_connection("benchmark_test")
        
        # Calculate metrics
        improvement = ((non_pooled_total - pooled_total) / non_pooled_total) * 100
        
        result = {
            'num_requests': num_requests,
            'non_pooled': {
                'total_time': non_pooled_total,
                'avg_request_time': statistics.mean(non_pooled_times) if non_pooled_times else 0,
                'median_request_time': statistics.median(non_pooled_times) if non_pooled_times else 0,
                'successful_requests': len(non_pooled_times)
            },
            'pooled': {
                'total_time': pooled_total,
                'avg_request_time': statistics.mean(pooled_times) if pooled_times else 0,
                'median_request_time': statistics.median(pooled_times) if pooled_times else 0,
                'successful_requests': len(pooled_times)
            },
            'improvement_percent': improvement
        }
        
        print(f"  ✅ Pooled connections {improvement:.1f}% faster")
        print(f"     Non-pooled: {non_pooled_total:.2f}s total, {statistics.mean(non_pooled_times) if non_pooled_times else 0:.3f}s avg")
        print(f"     Pooled: {pooled_total:.2f}s total, {statistics.mean(pooled_times) if pooled_times else 0:.3f}s avg")
        
        return result
    
    def benchmark_concurrent_requests(self) -> Dict[str, Any]:
        """Benchmark concurrent request handling with connection pooling."""
        num_threads = 10
        requests_per_thread = 20
        
        # Test with connection pooling
        session = connection_pool_manager.create_session_with_pooling(
            name="concurrent_benchmark",
            pool_maxsize=num_threads,
            enable_keep_alive=True
        )
        
        def make_requests(thread_id: int) -> List[float]:
            """Make multiple requests from a single thread."""
            times = []
            for i in range(requests_per_thread):
                start_time = time.time()
                try:
                    response = session.get(self.test_url, timeout=5)
                    request_time = time.time() - start_time
                    times.append(request_time)
                except Exception as e:
                    print(f"    Thread {thread_id} request {i} failed: {e}")
            return times
        
        print(f"  Running {num_threads} threads × {requests_per_thread} requests...")
        start_time = time.time()
        
        # Execute concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(make_requests, i) for i in range(num_threads)]
            thread_results = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        total_time = time.time() - start_time
        
        # Cleanup
        connection_pool_manager.force_cleanup_connection("concurrent_benchmark")
        
        # Aggregate results
        all_times = [time for thread_times in thread_results for time in thread_times]
        total_requests = len(all_times)
        requests_per_second = total_requests / total_time
        
        result = {
            'num_threads': num_threads,
            'requests_per_thread': requests_per_thread,
            'total_requests': total_requests,
            'total_time': total_time,
            'requests_per_second': requests_per_second,
            'avg_request_time': statistics.mean(all_times) if all_times else 0,
            'p95_request_time': statistics.quantiles(all_times, n=20)[18] if len(all_times) > 20 else 0,
            'successful_requests': total_requests
        }
        
        print(f"  ✅ Handled {requests_per_second:.1f} requests/second")
        print(f"     Total: {total_requests} requests in {total_time:.2f}s")
        print(f"     Avg: {statistics.mean(all_times) if all_times else 0:.3f}s, P95: {result['p95_request_time']:.3f}s")
        
        return result
    
    def benchmark_connection_reuse(self) -> Dict[str, Any]:
        """Benchmark connection reuse efficiency."""
        num_requests = 100
        
        # Create session with small pool to force reuse
        session = connection_pool_manager.create_session_with_pooling(
            name="reuse_benchmark",
            pool_maxsize=3,  # Small pool to force connection reuse
            enable_keep_alive=True
        )
        
        print(f"  Making {num_requests} requests with pool_maxsize=3...")
        
        start_time = time.time()
        request_times = []
        
        for i in range(num_requests):
            request_start = time.time()
            try:
                response = session.get(self.test_url, timeout=5)
                request_time = time.time() - request_start
                request_times.append(request_time)
                
                # Track connection reuse by checking if request time improves over time
                if i > 0 and i % 10 == 0:
                    recent_avg = statistics.mean(request_times[-10:])
                    early_avg = statistics.mean(request_times[:10])
                    print(f"    Request {i}: Recent avg {recent_avg:.3f}s vs Early avg {early_avg:.3f}s")
                    
            except Exception as e:
                print(f"    Request {i} failed: {e}")
        
        total_time = time.time() - start_time
        
        # Get connection pool metrics
        pool_metrics = connection_pool_manager.get_metrics()
        reuse_metrics = pool_metrics.get('pools', {}).get('reuse_benchmark', {})
        
        # Cleanup
        connection_pool_manager.force_cleanup_connection("reuse_benchmark")
        
        # Analyze connection reuse efficiency
        early_requests = request_times[:20] if len(request_times) >= 20 else request_times[:len(request_times)//2]
        later_requests = request_times[-20:] if len(request_times) >= 20 else request_times[len(request_times)//2:]
        
        reuse_improvement = 0
        if early_requests and later_requests:
            early_avg = statistics.mean(early_requests)
            later_avg = statistics.mean(later_requests)
            reuse_improvement = ((early_avg - later_avg) / early_avg) * 100
        
        result = {
            'num_requests': len(request_times),
            'total_time': total_time,
            'avg_request_time': statistics.mean(request_times) if request_times else 0,
            'early_avg_time': statistics.mean(early_requests) if early_requests else 0,
            'later_avg_time': statistics.mean(later_requests) if later_requests else 0,
            'reuse_improvement_percent': reuse_improvement,
            'pool_max_size': 3,
            'connection_reuse_count': reuse_metrics.get('request_count', 0)
        }
        
        print(f"  ✅ Connection reuse improved performance by {reuse_improvement:.1f}%")
        print(f"     Early requests: {result['early_avg_time']:.3f}s avg")
        print(f"     Later requests: {result['later_avg_time']:.3f}s avg")
        
        return result
    
    def benchmark_memory_efficiency(self) -> Dict[str, Any]:
        """Benchmark memory usage with leak detection."""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        
        # Measure baseline memory
        baseline_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        print(f"  Baseline memory: {baseline_memory:.1f} MB")
        
        # Create many connections to test memory efficiency
        num_sessions = 20
        sessions = []
        
        print(f"  Creating {num_sessions} connection pool sessions...")
        for i in range(num_sessions):
            session = connection_pool_manager.create_session_with_pooling(
                name=f"memory_test_{i}",
                pool_maxsize=5,
                enable_keep_alive=True
            )
            sessions.append(session)
        
        # Measure memory after creating sessions
        after_creation_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = after_creation_memory - baseline_memory
        
        print(f"  Memory after creating sessions: {after_creation_memory:.1f} MB (+{memory_increase:.1f} MB)")
        
        # Make some requests to populate connections
        print("  Making requests to populate connection pools...")
        for i, session in enumerate(sessions[:5]):  # Use only first 5 to avoid overwhelming test server
            try:
                response = session.get(self.test_url, timeout=5)
            except Exception as e:
                print(f"    Session {i} request failed: {e}")
        
        # Measure memory after requests
        after_requests_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Get leak detection stats
        leak_stats = {}
        if connection_pool_manager.leak_detector:
            leak_stats = connection_pool_manager.leak_detector.get_leak_stats()
        
        # Cleanup sessions
        print("  Cleaning up sessions...")
        for i in range(num_sessions):
            connection_pool_manager.force_cleanup_connection(f"memory_test_{i}")
        
        # Force garbage collection and measure final memory
        import gc
        gc.collect()
        time.sleep(1)  # Allow time for cleanup
        
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_recovered = after_requests_memory - final_memory
        
        result = {
            'baseline_memory_mb': baseline_memory,
            'peak_memory_mb': after_requests_memory,
            'final_memory_mb': final_memory,
            'memory_increase_mb': memory_increase,
            'memory_recovered_mb': memory_recovered,
            'recovery_rate_percent': (memory_recovered / memory_increase * 100) if memory_increase > 0 else 0,
            'leak_detection_stats': leak_stats,
            'num_sessions_tested': num_sessions
        }
        
        print(f"  ✅ Memory recovery: {memory_recovered:.1f} MB recovered ({result['recovery_rate_percent']:.1f}%)")
        print(f"     Peak usage: {after_requests_memory:.1f} MB, Final: {final_memory:.1f} MB")
        
        return result
    
    def benchmark_monitoring_overhead(self) -> Dict[str, Any]:
        """Benchmark the overhead of connection pool monitoring."""
        num_requests = 50
        
        # Test with monitoring disabled
        test_manager = ConnectionPoolManager(enable_leak_detection=False)
        session_no_monitor = test_manager.create_session_with_pooling(
            name="no_monitor_test",
            pool_maxsize=5
        )
        
        print("  Testing without monitoring...")
        start_time = time.time()
        no_monitor_times = []
        
        for _ in range(num_requests):
            request_start = time.time()
            try:
                response = session_no_monitor.get(self.test_url, timeout=5)
                request_time = time.time() - request_start
                no_monitor_times.append(request_time)
            except Exception as e:
                print(f"    No-monitor request failed: {e}")
        
        no_monitor_total = time.time() - start_time
        
        # Test with monitoring enabled
        session_with_monitor = connection_pool_manager.create_session_with_pooling(
            name="with_monitor_test",
            pool_maxsize=5
        )
        
        print("  Testing with monitoring enabled...")
        start_time = time.time()
        with_monitor_times = []
        
        for _ in range(num_requests):
            request_start = time.time()
            try:
                response = session_with_monitor.get(self.test_url, timeout=5)
                request_time = time.time() - request_start
                with_monitor_times.append(request_time)
            except Exception as e:
                print(f"    With-monitor request failed: {e}")
        
        with_monitor_total = time.time() - start_time
        
        # Cleanup
        test_manager.cleanup_pools()
        connection_pool_manager.force_cleanup_connection("with_monitor_test")
        
        # Calculate overhead
        overhead_percent = ((with_monitor_total - no_monitor_total) / no_monitor_total * 100) if no_monitor_total > 0 else 0
        
        result = {
            'num_requests': num_requests,
            'without_monitoring': {
                'total_time': no_monitor_total,
                'avg_request_time': statistics.mean(no_monitor_times) if no_monitor_times else 0
            },
            'with_monitoring': {
                'total_time': with_monitor_total,
                'avg_request_time': statistics.mean(with_monitor_times) if with_monitor_times else 0
            },
            'overhead_percent': overhead_percent
        }
        
        print(f"  ✅ Monitoring overhead: {overhead_percent:.2f}%")
        print(f"     Without: {no_monitor_total:.2f}s, With: {with_monitor_total:.2f}s")
        
        return result
    
    def generate_benchmark_report(self):
        """Generate a comprehensive benchmark report."""
        print("\n" + "=" * 60)
        print("📈 CONNECTION POOL BENCHMARK REPORT")
        print("=" * 60)
        
        # Summary of key improvements
        pooling_improvement = self.results.get('connection_pooling', {}).get('improvement_percent', 0)
        reuse_improvement = self.results.get('connection_reuse', {}).get('reuse_improvement_percent', 0)
        memory_recovery = self.results.get('memory_efficiency', {}).get('recovery_rate_percent', 0)
        monitoring_overhead = self.results.get('monitoring_overhead', {}).get('overhead_percent', 0)
        
        print(f"\n🎯 KEY PERFORMANCE IMPROVEMENTS:")
        print(f"   • Connection Pooling: {pooling_improvement:+.1f}% faster")
        print(f"   • Connection Reuse: {reuse_improvement:+.1f}% improvement over time")
        print(f"   • Memory Recovery: {memory_recovery:.1f}% of allocated memory recovered")
        print(f"   • Monitoring Overhead: {monitoring_overhead:.2f}% performance cost")
        
        # Concurrent performance
        concurrent_rps = self.results.get('concurrent_requests', {}).get('requests_per_second', 0)
        print(f"   • Concurrent Throughput: {concurrent_rps:.1f} requests/second")
        
        print(f"\n💡 RECOMMENDATIONS:")
        if pooling_improvement > 10:
            print("   ✅ Connection pooling provides significant performance benefits")
        else:
            print("   ⚠️  Consider tuning pool sizes for better performance")
        
        if reuse_improvement > 5:
            print("   ✅ Connection reuse is working effectively")
        else:
            print("   ⚠️  Connection reuse may need optimization")
        
        if memory_recovery > 80:
            print("   ✅ Memory management and leak detection are working well")
        else:
            print("   ⚠️  Consider reviewing memory cleanup strategies")
        
        if monitoring_overhead < 5:
            print("   ✅ Monitoring overhead is acceptable")
        else:
            print("   ⚠️  Consider reducing monitoring frequency to improve performance")
        
        print("\n" + "=" * 60)


def main():
    """Run connection pool benchmarks."""
    benchmark = ConnectionPoolBenchmark()
    results = benchmark.run_all_benchmarks()
    
    # Save results to file
    import json
    with open('benchmark_results.json', 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n📝 Detailed results saved to: benchmark_results.json")
    return results


if __name__ == "__main__":
    main()