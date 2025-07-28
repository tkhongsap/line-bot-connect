"""
Async Operation Monitoring and Performance Metrics System

This module provides comprehensive monitoring and performance metrics collection
for async operations in the LINE Bot system including streaming, batch processing,
API calls, and system resources with real-time dashboards and alerting.
"""

import asyncio
import time
import logging
import json
import psutil
import threading
from typing import Dict, List, Any, Optional, Callable, Union, AsyncGenerator
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import defaultdict, deque
from contextlib import asynccontextmanager
import weakref

from ..exceptions import BaseBotException, create_correlation_id
from ..utils.error_handler import StructuredLogger, error_handler

logger = StructuredLogger(__name__)

class MetricType(Enum):
    """Types of metrics collected"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMING = "timing"
    RATE = "rate"

class OperationType(Enum):
    """Types of operations being monitored"""
    ASYNC_STREAM = "async_stream"
    BATCH_PROCESSING = "batch_processing"
    HTTP_REQUEST = "http_request"
    DATABASE_QUERY = "database_query"
    CACHE_OPERATION = "cache_operation"
    FILE_OPERATION = "file_operation"
    OPENAI_API_CALL = "openai_api_call"
    LINE_API_CALL = "line_api_call"
    IMAGE_PROCESSING = "image_processing"
    RICH_MESSAGE_GENERATION = "rich_message_generation"

class AlertLevel(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

@dataclass
class MetricPoint:
    """Single metric data point"""
    metric_name: str
    metric_type: MetricType
    value: Union[int, float]
    timestamp: float
    labels: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class OperationMetrics:
    """Metrics for a specific operation"""
    operation_id: str
    operation_type: OperationType
    start_time: float
    end_time: Optional[float] = None
    duration_ms: Optional[float] = None
    success: bool = False
    error_message: Optional[str] = None
    
    # Performance metrics
    cpu_usage_percent: float = 0.0
    memory_usage_mb: float = 0.0
    network_bytes_sent: int = 0
    network_bytes_received: int = 0
    
    # Operation-specific metrics
    throughput: float = 0.0
    latency_ms: float = 0.0
    queue_size: int = 0
    concurrent_operations: int = 0
    
    # Labels and metadata
    labels: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def complete(self, success: bool = True, error_message: Optional[str] = None):
        """Mark operation as completed"""
        self.end_time = time.time()
        self.duration_ms = (self.end_time - self.start_time) * 1000
        self.success = success
        self.error_message = error_message

@dataclass
class SystemMetrics:
    """System-wide performance metrics"""
    timestamp: float
    cpu_percent: float
    memory_percent: float
    memory_available_mb: float
    disk_usage_percent: float
    network_bytes_sent: int
    network_bytes_received: int
    active_connections: int
    process_count: int
    thread_count: int
    
    # Async-specific metrics
    event_loop_load: float = 0.0
    pending_tasks: int = 0
    running_tasks: int = 0
    
    # Application metrics
    active_users: int = 0
    total_requests: int = 0
    error_rate: float = 0.0
    avg_response_time_ms: float = 0.0

@dataclass
class Alert:
    """Performance alert"""
    alert_id: str
    level: AlertLevel
    message: str
    metric_name: str
    threshold_value: Union[int, float]
    actual_value: Union[int, float]
    timestamp: float
    operation_type: Optional[OperationType] = None
    labels: Dict[str, str] = field(default_factory=dict)
    resolved: bool = False
    resolved_at: Optional[float] = None

class MetricCollector:
    """Collects and aggregates metrics"""
    
    def __init__(self, max_points: int = 10000, retention_seconds: int = 3600):
        self.max_points = max_points
        self.retention_seconds = retention_seconds
        
        # Storage for different metric types
        self.counters: Dict[str, float] = defaultdict(float)
        self.gauges: Dict[str, float] = {}
        self.histograms: Dict[str, List[float]] = defaultdict(list)
        self.timings: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.rates: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        
        # Raw metric points
        self.metric_points: deque = deque(maxlen=max_points)
        
        # Lock for thread safety
        self.lock = threading.RLock()
    
    def record_counter(self, name: str, value: Union[int, float] = 1, labels: Dict[str, str] = None):
        """Record a counter metric"""
        with self.lock:
            key = self._make_key(name, labels)
            self.counters[key] += value
            
            self.metric_points.append(MetricPoint(
                metric_name=name,
                metric_type=MetricType.COUNTER,
                value=self.counters[key],
                timestamp=time.time(),
                labels=labels or {}
            ))
    
    def record_gauge(self, name: str, value: Union[int, float], labels: Dict[str, str] = None):
        """Record a gauge metric"""
        with self.lock:
            key = self._make_key(name, labels)
            self.gauges[key] = value
            
            self.metric_points.append(MetricPoint(
                metric_name=name,
                metric_type=MetricType.GAUGE,
                value=value,
                timestamp=time.time(),
                labels=labels or {}
            ))
    
    def record_histogram(self, name: str, value: Union[int, float], labels: Dict[str, str] = None):
        """Record a histogram metric"""
        with self.lock:
            key = self._make_key(name, labels)
            self.histograms[key].append(value)
            
            # Keep only recent values
            if len(self.histograms[key]) > 1000:
                self.histograms[key] = self.histograms[key][-1000:]
            
            self.metric_points.append(MetricPoint(
                metric_name=name,
                metric_type=MetricType.HISTOGRAM,
                value=value,
                timestamp=time.time(),
                labels=labels or {}
            ))
    
    def record_timing(self, name: str, duration_ms: float, labels: Dict[str, str] = None):
        """Record a timing metric"""
        with self.lock:
            key = self._make_key(name, labels)
            self.timings[key].append((time.time(), duration_ms))
            
            self.metric_points.append(MetricPoint(
                metric_name=name,
                metric_type=MetricType.TIMING,
                value=duration_ms,
                timestamp=time.time(),
                labels=labels or {}
            ))
    
    def record_rate(self, name: str, count: Union[int, float], labels: Dict[str, str] = None):
        """Record a rate metric"""
        with self.lock:
            key = self._make_key(name, labels)
            self.rates[key].append((time.time(), count))
            
            self.metric_points.append(MetricPoint(
                metric_name=name,
                metric_type=MetricType.RATE,
                value=count,
                timestamp=time.time(),
                labels=labels or {}
            ))
    
    def get_counter(self, name: str, labels: Dict[str, str] = None) -> float:
        """Get current counter value"""
        with self.lock:
            key = self._make_key(name, labels)
            return self.counters.get(key, 0.0)
    
    def get_gauge(self, name: str, labels: Dict[str, str] = None) -> Optional[float]:
        """Get current gauge value"""
        with self.lock:
            key = self._make_key(name, labels)
            return self.gauges.get(key)
    
    def get_histogram_stats(self, name: str, labels: Dict[str, str] = None) -> Dict[str, float]:
        """Get histogram statistics"""
        with self.lock:
            key = self._make_key(name, labels)
            values = self.histograms.get(key, [])
            
            if not values:
                return {}
            
            sorted_values = sorted(values)
            count = len(sorted_values)
            
            return {
                'count': count,
                'min': sorted_values[0],
                'max': sorted_values[-1],
                'mean': sum(sorted_values) / count,
                'p50': sorted_values[int(count * 0.5)],
                'p90': sorted_values[int(count * 0.9)],
                'p95': sorted_values[int(count * 0.95)],
                'p99': sorted_values[int(count * 0.99)]
            }
    
    def get_rate(self, name: str, window_seconds: int = 60, labels: Dict[str, str] = None) -> float:
        """Get rate over time window"""
        with self.lock:
            key = self._make_key(name, labels)
            points = self.rates.get(key, deque())
            
            current_time = time.time()
            cutoff_time = current_time - window_seconds
            
            # Filter points within window
            recent_points = [
                count for timestamp, count in points 
                if timestamp >= cutoff_time
            ]
            
            if not recent_points:
                return 0.0
            
            return sum(recent_points) / window_seconds
    
    def cleanup_old_metrics(self):
        """Clean up old metric data"""
        cutoff_time = time.time() - self.retention_seconds
        
        with self.lock:
            # Clean up metric points
            while self.metric_points and self.metric_points[0].timestamp < cutoff_time:
                self.metric_points.popleft()
            
            # Clean up timing data
            for key in list(self.timings.keys()):
                timing_data = self.timings[key]
                while timing_data and timing_data[0][0] < cutoff_time:
                    timing_data.popleft()
                
                if not timing_data:
                    del self.timings[key]
            
            # Clean up rate data
            for key in list(self.rates.keys()):
                rate_data = self.rates[key]
                while rate_data and rate_data[0][0] < cutoff_time:
                    rate_data.popleft()
                
                if not rate_data:
                    del self.rates[key]
    
    def _make_key(self, name: str, labels: Dict[str, str] = None) -> str:
        """Create key for metric storage"""
        if not labels:
            return name
        
        label_parts = [f"{k}={v}" for k, v in sorted(labels.items())]
        return f"{name}{{{','.join(label_parts)}}}"

class PerformanceMonitor:
    """Main performance monitoring system"""
    
    def __init__(self, settings):
        self.settings = settings
        
        # Configuration
        self.collection_interval = getattr(settings, 'METRICS_COLLECTION_INTERVAL', 10.0)
        self.system_metrics_interval = getattr(settings, 'SYSTEM_METRICS_INTERVAL', 30.0)
        self.alert_check_interval = getattr(settings, 'ALERT_CHECK_INTERVAL', 60.0)
        self.metrics_retention_seconds = getattr(settings, 'METRICS_RETENTION_SECONDS', 3600)
        
        # Components
        self.metric_collector = MetricCollector(
            retention_seconds=self.metrics_retention_seconds
        )
        
        # Active operations tracking
        self.active_operations: Dict[str, OperationMetrics] = {}
        self.operation_history: deque = deque(maxlen=1000)
        
        # System metrics tracking
        self.system_metrics_history: deque = deque(maxlen=1000)
        
        # Alerting
        self.alert_thresholds: Dict[str, Dict[str, Any]] = {}
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_callbacks: List[Callable[[Alert], None]] = []
        
        # Background tasks
        self.monitoring_tasks: List[asyncio.Task] = []
        self.is_running = False
        
        # Event loop reference for async metrics
        self.event_loop = None
        
        logger.info("Initialized PerformanceMonitor")
    
    async def start(self):
        """Start the monitoring system"""
        if self.is_running:
            return
        
        self.is_running = True
        self.event_loop = asyncio.get_event_loop()
        
        # Start background monitoring tasks
        self.monitoring_tasks = [
            asyncio.create_task(self._system_metrics_loop()),
            asyncio.create_task(self._metrics_cleanup_loop()),
            asyncio.create_task(self._alert_check_loop())
        ]
        
        logger.info("Started PerformanceMonitor background tasks")
    
    async def stop(self):
        """Stop the monitoring system"""
        if not self.is_running:
            return
        
        self.is_running = False
        
        # Cancel background tasks
        for task in self.monitoring_tasks:
            task.cancel()
        
        # Wait for tasks to complete
        if self.monitoring_tasks:
            await asyncio.gather(*self.monitoring_tasks, return_exceptions=True)
        
        self.monitoring_tasks.clear()
        
        logger.info("Stopped PerformanceMonitor")
    
    def start_operation(
        self,
        operation_type: OperationType,
        operation_id: Optional[str] = None,
        labels: Dict[str, str] = None,
        metadata: Dict[str, Any] = None
    ) -> str:
        """Start tracking an operation"""
        if not operation_id:
            operation_id = f"{operation_type.value}_{create_correlation_id()}"
        
        operation_metrics = OperationMetrics(
            operation_id=operation_id,
            operation_type=operation_type,
            start_time=time.time(),
            labels=labels or {},
            metadata=metadata or {}
        )
        
        # Capture initial system metrics
        try:
            process = psutil.Process()
            operation_metrics.cpu_usage_percent = process.cpu_percent()
            operation_metrics.memory_usage_mb = process.memory_info().rss / 1024 / 1024
        except Exception:
            pass  # Ignore psutil errors
        
        self.active_operations[operation_id] = operation_metrics
        
        # Record counter metric
        self.metric_collector.record_counter(
            f"{operation_type.value}_started",
            labels=labels
        )
        
        logger.debug(f"Started operation tracking: {operation_id}", extra={
            'operation_id': operation_id,
            'operation_type': operation_type.value
        })
        
        return operation_id
    
    def complete_operation(
        self,
        operation_id: str,
        success: bool = True,
        error_message: Optional[str] = None,
        metadata: Dict[str, Any] = None
    ):
        """Complete operation tracking"""
        if operation_id not in self.active_operations:
            logger.warning(f"Attempted to complete unknown operation: {operation_id}")
            return
        
        operation_metrics = self.active_operations[operation_id]
        operation_metrics.complete(success=success, error_message=error_message)
        
        if metadata:
            operation_metrics.metadata.update(metadata)
        
        # Capture final system metrics
        try:
            process = psutil.Process()
            operation_metrics.cpu_usage_percent = process.cpu_percent()
            operation_metrics.memory_usage_mb = process.memory_info().rss / 1024 / 1024
        except Exception:
            pass
        
        # Record completion metrics
        labels = operation_metrics.labels.copy()
        labels['success'] = str(success)
        
        self.metric_collector.record_counter(
            f"{operation_metrics.operation_type.value}_completed",
            labels=labels
        )
        
        if operation_metrics.duration_ms:
            self.metric_collector.record_timing(
                f"{operation_metrics.operation_type.value}_duration",
                operation_metrics.duration_ms,
                labels=operation_metrics.labels
            )
        
        # Move to history
        self.operation_history.append(operation_metrics)
        del self.active_operations[operation_id]
        
        logger.debug(f"Completed operation tracking: {operation_id}", extra={
            'operation_id': operation_id,
            'success': success,
            'duration_ms': operation_metrics.duration_ms
        })
    
    def record_custom_metric(
        self,
        metric_name: str,
        metric_type: MetricType,
        value: Union[int, float],
        labels: Dict[str, str] = None
    ):
        """Record a custom metric"""
        if metric_type == MetricType.COUNTER:
            self.metric_collector.record_counter(metric_name, value, labels)
        elif metric_type == MetricType.GAUGE:
            self.metric_collector.record_gauge(metric_name, value, labels)
        elif metric_type == MetricType.HISTOGRAM:
            self.metric_collector.record_histogram(metric_name, value, labels)
        elif metric_type == MetricType.TIMING:
            self.metric_collector.record_timing(metric_name, value, labels)
        elif metric_type == MetricType.RATE:
            self.metric_collector.record_rate(metric_name, value, labels)
    
    def set_alert_threshold(
        self,
        metric_name: str,
        threshold_value: Union[int, float],
        level: AlertLevel = AlertLevel.WARNING,
        comparison: str = "gt",  # gt, lt, eq, ne
        operation_type: Optional[OperationType] = None
    ):
        """Set alert threshold for a metric"""
        self.alert_thresholds[metric_name] = {
            'threshold_value': threshold_value,
            'level': level,
            'comparison': comparison,
            'operation_type': operation_type
        }
        
        logger.info(f"Set alert threshold for {metric_name}: {comparison} {threshold_value}")
    
    def add_alert_callback(self, callback: Callable[[Alert], None]):
        """Add callback for alert notifications"""
        self.alert_callbacks.append(callback)
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get comprehensive metrics summary"""
        # Operation metrics
        total_operations = len(self.operation_history) + len(self.active_operations)
        successful_operations = sum(
            1 for op in self.operation_history if op.success
        )
        
        # Calculate average durations by operation type
        operation_stats = defaultdict(lambda: {'count': 0, 'total_duration': 0, 'success_count': 0})
        
        for op in self.operation_history:
            stats = operation_stats[op.operation_type]
            stats['count'] += 1
            if op.duration_ms:
                stats['total_duration'] += op.duration_ms
            if op.success:
                stats['success_count'] += 1
        
        avg_durations = {
            op_type.value: {
                'avg_duration_ms': stats['total_duration'] / stats['count'] if stats['count'] > 0 else 0,
                'success_rate': stats['success_count'] / stats['count'] if stats['count'] > 0 else 0,
                'total_operations': stats['count']
            }
            for op_type, stats in operation_stats.items()
        }
        
        # System metrics
        latest_system_metrics = None
        if self.system_metrics_history:
            latest_system_metrics = asdict(self.system_metrics_history[-1])
        
        # Alert metrics
        active_alert_count = len(self.active_alerts)
        alert_counts_by_level = defaultdict(int)
        for alert in self.active_alerts.values():
            alert_counts_by_level[alert.level.value] += 1
        
        return {
            'operations': {
                'total_operations': total_operations,
                'active_operations': len(self.active_operations),
                'completed_operations': len(self.operation_history),
                'success_rate': successful_operations / len(self.operation_history) if self.operation_history else 0,
                'by_type': avg_durations
            },
            'system': latest_system_metrics,
            'alerts': {
                'active_count': active_alert_count,
                'by_level': dict(alert_counts_by_level)
            },
            'metrics': {
                'counter_count': len(self.metric_collector.counters),
                'gauge_count': len(self.metric_collector.gauges),
                'histogram_count': len(self.metric_collector.histograms),
                'total_metric_points': len(self.metric_collector.metric_points)
            }
        }
    
    def get_operation_metrics(self, operation_type: Optional[OperationType] = None) -> List[Dict[str, Any]]:
        """Get detailed operation metrics"""
        operations = []
        
        # Active operations
        for op in self.active_operations.values():
            if not operation_type or op.operation_type == operation_type:
                operations.append(asdict(op))
        
        # Historical operations
        for op in self.operation_history:
            if not operation_type or op.operation_type == operation_type:
                operations.append(asdict(op))
        
        return operations
    
    def get_active_alerts(self) -> List[Dict[str, Any]]:
        """Get active alerts"""
        return [asdict(alert) for alert in self.active_alerts.values()]
    
    async def _system_metrics_loop(self):
        """Background task to collect system metrics"""
        try:
            while self.is_running:
                try:
                    metrics = self._collect_system_metrics()
                    self.system_metrics_history.append(metrics)
                    
                    # Record as gauge metrics
                    timestamp = metrics.timestamp
                    self.metric_collector.record_gauge('system_cpu_percent', metrics.cpu_percent)
                    self.metric_collector.record_gauge('system_memory_percent', metrics.memory_percent)
                    self.metric_collector.record_gauge('system_disk_usage_percent', metrics.disk_usage_percent)
                    self.metric_collector.record_gauge('system_active_connections', metrics.active_connections)
                    self.metric_collector.record_gauge('system_process_count', metrics.process_count)
                    self.metric_collector.record_gauge('system_thread_count', metrics.thread_count)
                    
                    # Async-specific metrics
                    if self.event_loop:
                        all_tasks = asyncio.all_tasks(self.event_loop)
                        running_tasks = sum(1 for task in all_tasks if not task.done())
                        metrics.running_tasks = running_tasks
                        
                        self.metric_collector.record_gauge('async_running_tasks', running_tasks)
                    
                except Exception as e:
                    logger.error(f"Error collecting system metrics: {str(e)}")
                
                await asyncio.sleep(self.system_metrics_interval)
                
        except asyncio.CancelledError:
            pass
    
    def _collect_system_metrics(self) -> SystemMetrics:
        """Collect current system metrics"""
        try:
            # CPU and memory
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_percent = (disk.total - disk.free) / disk.total * 100
            
            # Network stats
            net_io = psutil.net_io_counters()
            
            # Process stats
            process = psutil.Process()
            connections = len(process.connections())
            
            return SystemMetrics(
                timestamp=time.time(),
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                memory_available_mb=memory.available / 1024 / 1024,
                disk_usage_percent=disk_percent,
                network_bytes_sent=net_io.bytes_sent,
                network_bytes_received=net_io.bytes_recv,
                active_connections=connections,
                process_count=len(psutil.pids()),
                thread_count=threading.active_count()
            )
            
        except Exception as e:
            logger.error(f"Error collecting system metrics: {str(e)}")
            return SystemMetrics(
                timestamp=time.time(),
                cpu_percent=0.0,
                memory_percent=0.0,
                memory_available_mb=0.0,
                disk_usage_percent=0.0,
                network_bytes_sent=0,
                network_bytes_received=0,
                active_connections=0,
                process_count=0,
                thread_count=0
            )
    
    async def _metrics_cleanup_loop(self):
        """Background task to clean up old metrics"""
        try:
            while self.is_running:
                try:
                    self.metric_collector.cleanup_old_metrics()
                except Exception as e:
                    logger.error(f"Error cleaning up metrics: {str(e)}")
                
                await asyncio.sleep(300)  # Clean up every 5 minutes
                
        except asyncio.CancelledError:
            pass
    
    async def _alert_check_loop(self):
        """Background task to check for alerts"""
        try:
            while self.is_running:
                try:
                    await self._check_alerts()
                except Exception as e:
                    logger.error(f"Error checking alerts: {str(e)}")
                
                await asyncio.sleep(self.alert_check_interval)
                
        except asyncio.CancelledError:
            pass
    
    async def _check_alerts(self):
        """Check metrics against alert thresholds"""
        for metric_name, threshold_config in self.alert_thresholds.items():
            threshold_value = threshold_config['threshold_value']
            level = threshold_config['level']
            comparison = threshold_config['comparison']
            operation_type = threshold_config.get('operation_type')
            
            # Get current metric value
            current_value = self.metric_collector.get_gauge(metric_name)
            if current_value is None:
                current_value = self.metric_collector.get_counter(metric_name)
            
            if current_value is None:
                continue
            
            # Check threshold
            alert_triggered = False
            if comparison == "gt" and current_value > threshold_value:
                alert_triggered = True
            elif comparison == "lt" and current_value < threshold_value:
                alert_triggered = True
            elif comparison == "eq" and current_value == threshold_value:
                alert_triggered = True
            elif comparison == "ne" and current_value != threshold_value:
                alert_triggered = True
            
            alert_id = f"{metric_name}_{comparison}_{threshold_value}"
            
            if alert_triggered:
                if alert_id not in self.active_alerts:
                    # Create new alert
                    alert = Alert(
                        alert_id=alert_id,
                        level=level,
                        message=f"Metric {metric_name} is {current_value} (threshold: {comparison} {threshold_value})",
                        metric_name=metric_name,
                        threshold_value=threshold_value,
                        actual_value=current_value,
                        timestamp=time.time(),
                        operation_type=operation_type
                    )
                    
                    self.active_alerts[alert_id] = alert
                    
                    # Notify callbacks
                    for callback in self.alert_callbacks:
                        try:
                            callback(alert)
                        except Exception as e:
                            logger.error(f"Alert callback error: {str(e)}")
                    
                    logger.warning(f"Alert triggered: {alert.message}", extra={
                        'alert_id': alert_id,
                        'level': level.value,
                        'metric_name': metric_name
                    })
            else:
                # Resolve alert if it exists
                if alert_id in self.active_alerts:
                    alert = self.active_alerts[alert_id]
                    alert.resolved = True
                    alert.resolved_at = time.time()
                    
                    del self.active_alerts[alert_id]
                    
                    logger.info(f"Alert resolved: {alert.message}", extra={
                        'alert_id': alert_id
                    })

# Context manager for performance monitoring
@asynccontextmanager
async def performance_monitor_context(settings):
    """Context manager for performance monitoring"""
    monitor = PerformanceMonitor(settings)
    try:
        await monitor.start()
        yield monitor
    finally:
        await monitor.stop()

# Decorator for automatic operation tracking
def monitor_async_operation(
    operation_type: OperationType,
    labels: Dict[str, str] = None,
    metadata: Dict[str, Any] = None
):
    """Decorator to automatically monitor async operations"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Get monitor from global state or arguments
            monitor = getattr(func, '_performance_monitor', None)
            
            if monitor:
                operation_id = monitor.start_operation(
                    operation_type=operation_type,
                    labels=labels,
                    metadata=metadata
                )
                
                try:
                    result = await func(*args, **kwargs)
                    monitor.complete_operation(operation_id, success=True)
                    return result
                except Exception as e:
                    monitor.complete_operation(
                        operation_id, 
                        success=False, 
                        error_message=str(e)
                    )
                    raise
            else:
                return await func(*args, **kwargs)
        
        return wrapper
    return decorator

# Global monitor instance for easy access
_global_monitor: Optional[PerformanceMonitor] = None

def set_global_monitor(monitor: PerformanceMonitor):
    """Set global monitor instance"""
    global _global_monitor
    _global_monitor = monitor

def get_global_monitor() -> Optional[PerformanceMonitor]:
    """Get global monitor instance"""
    return _global_monitor