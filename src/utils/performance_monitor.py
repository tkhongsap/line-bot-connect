"""
Performance monitoring utilities for system optimization.

This module provides comprehensive performance monitoring, metrics collection,
and health check capabilities for the LINE Bot application.
"""

import time
import psutil
import logging
import threading
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import wraps
from contextlib import contextmanager

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Container for performance metrics."""
    timestamp: datetime = field(default_factory=datetime.now)
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    memory_mb: float = 0.0
    response_time_ms: float = 0.0
    request_count: int = 0
    error_count: int = 0
    cache_hit_rate: float = 0.0
    active_connections: int = 0


class PerformanceMonitor:
    """Real-time performance monitoring and metrics collection."""
    
    def __init__(self, collection_interval: int = 60):
        """
        Initialize performance monitor.
        
        Args:
            collection_interval: Metrics collection interval in seconds
        """
        self.collection_interval = collection_interval
        self.metrics_history: List[PerformanceMetrics] = []
        self.max_history_size = 1440  # 24 hours of minute-by-minute data
        self.operation_metrics = {}
        self.lock = threading.Lock()
        self.running = False
        self.monitor_thread = None
        
        # Performance thresholds
        self.thresholds = {
            'cpu_warning': 70.0,
            'cpu_critical': 90.0,
            'memory_warning': 70.0,
            'memory_critical': 90.0,
            'response_time_warning': 500.0,  # ms
            'response_time_critical': 1000.0,  # ms
            'error_rate_warning': 5.0,  # %
            'error_rate_critical': 10.0  # %
        }
    
    def start_monitoring(self):
        """Start background performance monitoring."""
        if self.running:
            return
            
        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        logger.info("Performance monitoring started")
    
    def stop_monitoring(self):
        """Stop background performance monitoring."""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        logger.info("Performance monitoring stopped")
    
    def _monitor_loop(self):
        """Background monitoring loop."""
        while self.running:
            try:
                metrics = self._collect_system_metrics()
                with self.lock:
                    self.metrics_history.append(metrics)
                    if len(self.metrics_history) > self.max_history_size:
                        self.metrics_history.pop(0)
                
                # Check thresholds and log warnings
                self._check_thresholds(metrics)
                
            except Exception as e:
                logger.error(f"Error in performance monitoring: {e}")
            
            time.sleep(self.collection_interval)
    
    def _collect_system_metrics(self) -> PerformanceMetrics:
        """Collect current system metrics."""
        try:
            process = psutil.Process()
            
            # CPU and memory metrics
            cpu_percent = process.cpu_percent()
            memory_info = process.memory_info()
            memory_percent = process.memory_percent()
            memory_mb = memory_info.rss / 1024 / 1024
            
            # Get operation metrics
            total_requests = sum(m.get('count', 0) for m in self.operation_metrics.values())
            total_errors = sum(m.get('errors', 0) for m in self.operation_metrics.values())
            avg_response_time = self._calculate_avg_response_time()
            
            return PerformanceMetrics(
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                memory_mb=memory_mb,
                response_time_ms=avg_response_time,
                request_count=total_requests,
                error_count=total_errors
            )
            
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
            return PerformanceMetrics()
    
    def _calculate_avg_response_time(self) -> float:
        """Calculate average response time across all operations."""
        total_time = 0.0
        total_count = 0
        
        for operation, metrics in self.operation_metrics.items():
            if 'total_time' in metrics and 'count' in metrics:
                total_time += metrics['total_time']
                total_count += metrics['count']
        
        return (total_time / total_count * 1000) if total_count > 0 else 0.0
    
    def _check_thresholds(self, metrics: PerformanceMetrics):
        """Check metrics against thresholds and log warnings."""
        warnings = []
        
        if metrics.cpu_percent > self.thresholds['cpu_critical']:
            warnings.append(f"CRITICAL: CPU usage {metrics.cpu_percent:.1f}%")
        elif metrics.cpu_percent > self.thresholds['cpu_warning']:
            warnings.append(f"WARNING: CPU usage {metrics.cpu_percent:.1f}%")
        
        if metrics.memory_percent > self.thresholds['memory_critical']:
            warnings.append(f"CRITICAL: Memory usage {metrics.memory_percent:.1f}%")
        elif metrics.memory_percent > self.thresholds['memory_warning']:
            warnings.append(f"WARNING: Memory usage {metrics.memory_percent:.1f}%")
        
        if metrics.response_time_ms > self.thresholds['response_time_critical']:
            warnings.append(f"CRITICAL: Response time {metrics.response_time_ms:.1f}ms")
        elif metrics.response_time_ms > self.thresholds['response_time_warning']:
            warnings.append(f"WARNING: Response time {metrics.response_time_ms:.1f}ms")
        
        for warning in warnings:
            logger.warning(f"Performance threshold exceeded: {warning}")
    
    @contextmanager
    def measure_operation(self, operation_name: str):
        """Context manager to measure operation performance."""
        start_time = time.perf_counter()
        error_occurred = False
        
        try:
            yield
        except Exception as e:
            error_occurred = True
            raise
        finally:
            end_time = time.perf_counter()
            duration = end_time - start_time
            
            with self.lock:
                if operation_name not in self.operation_metrics:
                    self.operation_metrics[operation_name] = {
                        'count': 0,
                        'total_time': 0.0,
                        'errors': 0,
                        'min_time': float('inf'),
                        'max_time': 0.0
                    }
                
                metrics = self.operation_metrics[operation_name]
                metrics['count'] += 1
                metrics['total_time'] += duration
                metrics['min_time'] = min(metrics['min_time'], duration)
                metrics['max_time'] = max(metrics['max_time'], duration)
                
                if error_occurred:
                    metrics['errors'] += 1
    
    def track_operation(self, operation_name: str):
        """Decorator to track operation performance."""
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                with self.measure_operation(operation_name):
                    return func(*args, **kwargs)
            return wrapper
        return decorator
    
    def get_current_metrics(self) -> PerformanceMetrics:
        """Get current system metrics."""
        return self._collect_system_metrics()
    
    def get_metrics_summary(self, hours: int = 1) -> Dict[str, Any]:
        """Get performance metrics summary for specified time period."""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        with self.lock:
            recent_metrics = [
                m for m in self.metrics_history 
                if m.timestamp >= cutoff_time
            ]
        
        if not recent_metrics:
            return {}
        
        return {
            'period_hours': hours,
            'sample_count': len(recent_metrics),
            'cpu': {
                'avg': sum(m.cpu_percent for m in recent_metrics) / len(recent_metrics),
                'max': max(m.cpu_percent for m in recent_metrics),
                'min': min(m.cpu_percent for m in recent_metrics)
            },
            'memory': {
                'avg_percent': sum(m.memory_percent for m in recent_metrics) / len(recent_metrics),
                'avg_mb': sum(m.memory_mb for m in recent_metrics) / len(recent_metrics),
                'max_mb': max(m.memory_mb for m in recent_metrics)
            },
            'response_time': {
                'avg_ms': sum(m.response_time_ms for m in recent_metrics) / len(recent_metrics),
                'max_ms': max(m.response_time_ms for m in recent_metrics)
            },
            'requests': {
                'total': sum(m.request_count for m in recent_metrics),
                'errors': sum(m.error_count for m in recent_metrics)
            }
        }
    
    def get_operation_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get detailed statistics for all tracked operations."""
        with self.lock:
            stats = {}
            for operation, metrics in self.operation_metrics.items():
                if metrics['count'] > 0:
                    avg_time = metrics['total_time'] / metrics['count']
                    error_rate = (metrics['errors'] / metrics['count']) * 100
                    
                    stats[operation] = {
                        'count': metrics['count'],
                        'avg_time_ms': avg_time * 1000,
                        'min_time_ms': metrics['min_time'] * 1000,
                        'max_time_ms': metrics['max_time'] * 1000,
                        'error_count': metrics['errors'],
                        'error_rate_percent': error_rate,
                        'total_time_seconds': metrics['total_time']
                    }
            
            return stats
    
    def health_check(self) -> Dict[str, Any]:
        """Perform comprehensive health check."""
        current_metrics = self.get_current_metrics()
        
        # Determine overall health status
        health_issues = []
        
        if current_metrics.cpu_percent > self.thresholds['cpu_critical']:
            health_issues.append(f"Critical CPU usage: {current_metrics.cpu_percent:.1f}%")
        
        if current_metrics.memory_percent > self.thresholds['memory_critical']:
            health_issues.append(f"Critical memory usage: {current_metrics.memory_percent:.1f}%")
        
        if current_metrics.response_time_ms > self.thresholds['response_time_critical']:
            health_issues.append(f"Critical response time: {current_metrics.response_time_ms:.1f}ms")
        
        # Calculate error rate
        total_requests = current_metrics.request_count
        error_rate = (current_metrics.error_count / total_requests * 100) if total_requests > 0 else 0
        
        if error_rate > self.thresholds['error_rate_critical']:
            health_issues.append(f"Critical error rate: {error_rate:.1f}%")
        
        status = "unhealthy" if health_issues else "healthy"
        
        return {
            'status': status,
            'timestamp': datetime.now().isoformat(),
            'metrics': {
                'cpu_percent': current_metrics.cpu_percent,
                'memory_percent': current_metrics.memory_percent,
                'memory_mb': current_metrics.memory_mb,
                'response_time_ms': current_metrics.response_time_ms,
                'error_rate_percent': error_rate
            },
            'issues': health_issues,
            'thresholds': self.thresholds
        }


# Global performance monitor instance
performance_monitor = PerformanceMonitor()


def monitored_operation(operation_name: str):
    """Decorator for monitoring operation performance."""
    return performance_monitor.track_operation(operation_name)


@contextmanager
def measure_performance(operation_name: str):
    """Context manager for measuring operation performance."""
    with performance_monitor.measure_operation(operation_name):
        yield