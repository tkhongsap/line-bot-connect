"""
Connection pooling utilities for optimized API performance.

This module provides enhanced connection pooling for external API integrations
including LINE Bot API and Azure OpenAI with retry strategies and monitoring.
"""

import logging
import time
import threading
import requests.adapters
from urllib3.util.retry import Retry
from typing import Optional, Dict, Any, Callable, Set
from linebot import LineBotApi
from enum import Enum
from dataclasses import dataclass
from datetime import datetime, timedelta
import random
import weakref
import gc
import psutil
import os
from collections import defaultdict

logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    """Connection health states."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    CIRCUIT_OPEN = "circuit_open"


@dataclass
class HealthMetrics:
    """Health monitoring metrics for a connection."""
    success_count: int = 0
    failure_count: int = 0
    last_success: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    avg_response_time: float = 0.0
    state: ConnectionState = ConnectionState.HEALTHY
    circuit_open_until: Optional[datetime] = None
    active_connections: int = 0
    peak_connections: int = 0
    leaked_connections: int = 0
    total_bytes_sent: int = 0
    total_bytes_received: int = 0


@dataclass
class ConnectionLeak:
    """Information about a detected connection leak."""
    connection_id: str
    created_at: datetime
    last_used: datetime
    connection_type: str
    stack_trace: Optional[str] = None
    is_active: bool = True


class ExponentialBackoff:
    """Exponential backoff with jitter for retry logic."""
    
    def __init__(self, base_delay: float = 1.0, max_delay: float = 60.0, 
                 multiplier: float = 2.0, jitter: bool = True):
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.multiplier = multiplier
        self.jitter = jitter
    
    def get_delay(self, attempt: int) -> float:
        """Calculate delay for the given attempt number."""
        delay = min(self.base_delay * (self.multiplier ** attempt), self.max_delay)
        
        if self.jitter:
            # Add random jitter (±25%)
            jitter_amount = delay * 0.25
            delay += random.uniform(-jitter_amount, jitter_amount)
        
        return max(delay, 0.1)  # Minimum 100ms delay


class CircuitBreaker:
    """Circuit breaker pattern for connection health management."""
    
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60,
                 success_threshold: int = 3):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.state = ConnectionState.HEALTHY
        self._lock = threading.Lock()
    
    def call(self, func: Callable, *args, **kwargs):
        """Execute function with circuit breaker protection."""
        with self._lock:
            if self.state == ConnectionState.CIRCUIT_OPEN:
                if (datetime.now() - self.last_failure_time).seconds >= self.recovery_timeout:
                    self.state = ConnectionState.DEGRADED
                    logger.info("Circuit breaker entering half-open state")
                else:
                    raise ConnectionError("Circuit breaker is open")
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise e
    
    def _on_success(self):
        """Handle successful operation."""
        with self._lock:
            self.failure_count = 0
            if self.state == ConnectionState.DEGRADED:
                self.success_count += 1
                if self.success_count >= self.success_threshold:
                    self.state = ConnectionState.HEALTHY
                    self.success_count = 0
                    logger.info("Circuit breaker closed - connection recovered")
    
    def _on_failure(self):
        """Handle failed operation."""
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = datetime.now()
            self.success_count = 0
            
            if self.failure_count >= self.failure_threshold:
                self.state = ConnectionState.CIRCUIT_OPEN
                logger.warning(f"Circuit breaker opened after {self.failure_count} failures")


class HealthMonitor:
    """Connection health monitoring with automatic retry logic."""
    
    def __init__(self, check_interval: int = 30):
        self.check_interval = check_interval
        self.health_metrics = {}
        self.circuit_breakers = {}
        self._monitoring = False
        self._monitor_thread = None
        self._lock = threading.Lock()
    
    def register_connection(self, name: str, health_check_func: Callable,
                          failure_threshold: int = 5) -> None:
        """Register a connection for health monitoring."""
        with self._lock:
            self.health_metrics[name] = HealthMetrics()
            self.circuit_breakers[name] = CircuitBreaker(failure_threshold=failure_threshold)
            logger.info(f"Registered connection '{name}' for health monitoring")
    
    def start_monitoring(self) -> None:
        """Start background health monitoring."""
        if self._monitoring:
            return
        
        self._monitoring = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        logger.info("Started connection health monitoring")
    
    def stop_monitoring(self) -> None:
        """Stop background health monitoring."""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        logger.info("Stopped connection health monitoring")
    
    def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while self._monitoring:
            try:
                self._perform_health_checks()
                time.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"Error in health monitoring loop: {e}")
                time.sleep(5)  # Shorter sleep on error
    
    def _perform_health_checks(self) -> None:
        """Perform health checks on all registered connections."""
        with self._lock:
            connections = list(self.health_metrics.keys())
        
        for name in connections:
            try:
                self._check_connection_health(name)
            except Exception as e:
                logger.error(f"Health check failed for '{name}': {e}")
    
    def _check_connection_health(self, name: str) -> None:
        """Check health of a specific connection."""
        metrics = self.health_metrics[name]
        
        try:
            start_time = time.time()
            # Perform a lightweight health check (to be implemented by specific services)
            # For now, we'll simulate a basic connectivity check
            response_time = time.time() - start_time
            
            # Update metrics on success
            metrics.success_count += 1
            metrics.last_success = datetime.now()
            metrics.avg_response_time = (
                (metrics.avg_response_time * (metrics.success_count - 1) + response_time) 
                / metrics.success_count
            )
            
            # Update state based on performance
            if response_time > 5.0:  # Slow response
                metrics.state = ConnectionState.DEGRADED
            else:
                metrics.state = ConnectionState.HEALTHY
                
        except Exception as e:
            # Update metrics on failure
            metrics.failure_count += 1
            metrics.last_failure = datetime.now()
            
            # Determine state based on failure rate
            total_requests = metrics.success_count + metrics.failure_count
            failure_rate = metrics.failure_count / total_requests if total_requests > 0 else 1.0
            
            if failure_rate > 0.5:  # More than 50% failures
                metrics.state = ConnectionState.UNHEALTHY
            else:
                metrics.state = ConnectionState.DEGRADED
    
    def get_connection_health(self, name: str) -> Optional[HealthMetrics]:
        """Get health metrics for a specific connection."""
        return self.health_metrics.get(name)
    
    def get_all_health_metrics(self) -> Dict[str, HealthMetrics]:
        """Get health metrics for all connections."""
        return self.health_metrics.copy()
    
    def is_connection_healthy(self, name: str) -> bool:
        """Check if a connection is healthy."""
        metrics = self.health_metrics.get(name)
        if not metrics:
            return False
        
        circuit_breaker = self.circuit_breakers.get(name)
        if circuit_breaker and circuit_breaker.state == ConnectionState.CIRCUIT_OPEN:
            return False
        
        return metrics.state in [ConnectionState.HEALTHY, ConnectionState.DEGRADED]
    
    def execute_with_retry(self, name: str, func: Callable, max_attempts: int = 3,
                          backoff: Optional[ExponentialBackoff] = None) -> Any:
        """Execute function with automatic retry logic and health monitoring."""
        if not backoff:
            backoff = ExponentialBackoff()
        
        circuit_breaker = self.circuit_breakers.get(name)
        last_exception = None
        
        for attempt in range(max_attempts):
            try:
                if circuit_breaker:
                    return circuit_breaker.call(func)
                else:
                    return func()
                    
            except Exception as e:
                last_exception = e
                logger.warning(f"Attempt {attempt + 1} failed for '{name}': {e}")
                
                if attempt < max_attempts - 1:  # Don't sleep on last attempt
                    delay = backoff.get_delay(attempt)
                    logger.info(f"Retrying '{name}' in {delay:.2f} seconds...")
                    time.sleep(delay)
        
        # All attempts failed
        logger.error(f"All {max_attempts} attempts failed for '{name}'")
        raise last_exception


class OptimizedLineBotApi(LineBotApi):
    """Enhanced LINE Bot API client with connection pooling and retry logic."""
    
    def __init__(self, channel_access_token: str, endpoint: str = 'https://api.line.me', 
                 timeout: int = 10, pool_maxsize: int = 20, max_retries: int = 3):
        """
        Initialize optimized LINE Bot API client.
        
        Args:
            channel_access_token: LINE Bot channel access token
            endpoint: LINE API endpoint URL
            timeout: Request timeout in seconds
            pool_maxsize: Maximum number of connections to pool
            max_retries: Maximum number of retry attempts
        """
        super().__init__(channel_access_token, endpoint, timeout)
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "POST", "PUT", "DELETE", "OPTIONS", "TRACE"]
        )
        
        # Configure connection pooling adapter
        adapter = requests.adapters.HTTPAdapter(
            pool_maxsize=pool_maxsize,
            pool_block=False,
            max_retries=retry_strategy
        )
        
        # Apply adapter to session
        if hasattr(self, 'http_client') and hasattr(self.http_client, 'session'):
            self.http_client.session.mount("https://", adapter)
            self.http_client.session.mount("http://", adapter)
            
        logger.info(f"Initialized optimized LINE Bot API client with pool_size={pool_maxsize}, retries={max_retries}")


class LeakDetector:
    """Detects and tracks connection leaks with automatic cleanup."""
    
    def __init__(self, cleanup_interval: int = 300, max_idle_time: int = 3600):
        self.cleanup_interval = cleanup_interval  # 5 minutes
        self.max_idle_time = max_idle_time  # 1 hour
        self.tracked_connections = {}  # connection_id -> ConnectionLeak
        self.connection_refs = weakref.WeakSet()  # Weak references to connections
        self.cleanup_stats = {
            'total_cleaned': 0,
            'leaks_detected': 0,
            'last_cleanup': None
        }
        self._cleanup_thread = None
        self._cleanup_running = False
        self._lock = threading.Lock()
        
        logger.info(f"Initialized leak detector with cleanup_interval={cleanup_interval}s, max_idle_time={max_idle_time}s")
    
    def register_connection(self, connection_id: str, connection_obj: Any, connection_type: str = 'unknown') -> None:
        """Register a connection for leak detection."""
        with self._lock:
            # Create weak reference to avoid keeping objects alive
            self.connection_refs.add(connection_obj)
            
            leak_info = ConnectionLeak(
                connection_id=connection_id,
                created_at=datetime.now(),
                last_used=datetime.now(),
                connection_type=connection_type
            )
            
            self.tracked_connections[connection_id] = leak_info
            logger.debug(f"Registered connection {connection_id} of type {connection_type}")
    
    def update_connection_usage(self, connection_id: str) -> None:
        """Update the last used timestamp for a connection."""
        with self._lock:
            if connection_id in self.tracked_connections:
                self.tracked_connections[connection_id].last_used = datetime.now()
    
    def unregister_connection(self, connection_id: str) -> None:
        """Unregister a connection (properly closed)."""
        with self._lock:
            if connection_id in self.tracked_connections:
                self.tracked_connections[connection_id].is_active = False
                logger.debug(f"Unregistered connection {connection_id}")
    
    def start_cleanup(self) -> None:
        """Start the background cleanup thread."""
        if self._cleanup_running:
            return
        
        self._cleanup_running = True
        self._cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self._cleanup_thread.start()
        logger.info("Started connection leak cleanup thread")
    
    def stop_cleanup(self) -> None:
        """Stop the background cleanup thread."""
        self._cleanup_running = False
        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=5)
        logger.info("Stopped connection leak cleanup thread")
    
    def _cleanup_loop(self) -> None:
        """Main cleanup loop running in background thread."""
        while self._cleanup_running:
            try:
                self._detect_and_cleanup_leaks()
                time.sleep(self.cleanup_interval)
            except Exception as e:
                logger.error(f"Error in leak detection cleanup loop: {e}")
                time.sleep(30)  # Shorter sleep on error
    
    def _detect_and_cleanup_leaks(self) -> None:
        """Detect and clean up leaked connections."""
        current_time = datetime.now()
        leaks_found = []
        connections_cleaned = 0
        
        with self._lock:
            # Check for idle connections that may be leaked
            for conn_id, leak_info in list(self.tracked_connections.items()):
                if not leak_info.is_active:
                    continue
                
                idle_time = (current_time - leak_info.last_used).total_seconds()
                
                if idle_time > self.max_idle_time:
                    leaks_found.append(conn_id)
                    leak_info.is_active = False
                    self.cleanup_stats['leaks_detected'] += 1
                    
                    logger.warning(
                        f"Detected potential connection leak: {conn_id} "
                        f"({leak_info.connection_type}) idle for {idle_time:.1f}s"
                    )
        
        # Clean up detected leaks
        for conn_id in leaks_found:
            try:
                self._cleanup_connection(conn_id)
                connections_cleaned += 1
            except Exception as e:
                logger.error(f"Failed to cleanup connection {conn_id}: {e}")
        
        # Update cleanup stats
        with self._lock:
            self.cleanup_stats['total_cleaned'] += connections_cleaned
            self.cleanup_stats['last_cleanup'] = current_time
        
        # Force garbage collection to help clean up orphaned objects
        if connections_cleaned > 0:
            collected = gc.collect()
            logger.info(f"Cleaned up {connections_cleaned} connections, collected {collected} objects")
    
    def _cleanup_connection(self, connection_id: str) -> None:
        """Clean up a specific connection."""
        # This is a placeholder for connection-specific cleanup logic
        # Actual implementation would depend on the connection type
        logger.info(f"Cleaning up connection {connection_id}")
    
    def get_leak_stats(self) -> Dict[str, Any]:
        """Get comprehensive leak detection statistics."""
        with self._lock:
            active_connections = sum(1 for leak in self.tracked_connections.values() if leak.is_active)
            total_connections = len(self.tracked_connections)
            
            # Calculate connection age statistics
            current_time = datetime.now()
            ages = []
            idle_times = []
            
            for leak in self.tracked_connections.values():
                if leak.is_active:
                    age = (current_time - leak.created_at).total_seconds()
                    idle_time = (current_time - leak.last_used).total_seconds()
                    ages.append(age)
                    idle_times.append(idle_time)
            
            return {
                'active_connections': active_connections,
                'total_connections': total_connections,
                'avg_connection_age': sum(ages) / len(ages) if ages else 0,
                'max_connection_age': max(ages) if ages else 0,
                'avg_idle_time': sum(idle_times) / len(idle_times) if idle_times else 0,
                'max_idle_time': max(idle_times) if idle_times else 0,
                **self.cleanup_stats
            }


class ResourceMonitor:
    """Monitors system resources and connection pool usage."""
    
    def __init__(self, monitoring_interval: int = 60):
        self.monitoring_interval = monitoring_interval
        self.resource_history = defaultdict(list)
        self.resource_thresholds = {
            'memory_percent': 85.0,
            'cpu_percent': 80.0,
            'open_files': 1000,
            'network_connections': 500
        }
        self._monitoring = False
        self._monitor_thread = None
        self._lock = threading.Lock()
    
    def start_monitoring(self) -> None:
        """Start resource monitoring."""
        if self._monitoring:
            return
        
        self._monitoring = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        logger.info("Started resource monitoring")
    
    def stop_monitoring(self) -> None:
        """Stop resource monitoring."""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        logger.info("Stopped resource monitoring")
    
    def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while self._monitoring:
            try:
                self._collect_resource_metrics()
                time.sleep(self.monitoring_interval)
            except Exception as e:
                logger.error(f"Error in resource monitoring loop: {e}")
                time.sleep(30)
    
    def _collect_resource_metrics(self) -> None:
        """Collect system resource metrics."""
        try:
            # Memory usage
            memory = psutil.virtual_memory()
            
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Process-specific metrics
            process = psutil.Process(os.getpid())
            process_memory = process.memory_info()
            open_files = len(process.open_files())
            
            # Network connections
            try:
                network_connections = len(process.connections())
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                network_connections = 0
            
            metrics = {
                'timestamp': time.time(),
                'memory_percent': memory.percent,
                'memory_available': memory.available,
                'memory_used': memory.used,
                'process_memory_rss': process_memory.rss,
                'process_memory_vms': process_memory.vms,
                'cpu_percent': cpu_percent,
                'open_files': open_files,
                'network_connections': network_connections
            }
            
            # Store metrics with history limit
            with self._lock:
                for key, value in metrics.items():
                    if key != 'timestamp':
                        self.resource_history[key].append(value)
                        # Keep only last 100 entries
                        if len(self.resource_history[key]) > 100:
                            self.resource_history[key].pop(0)
            
            # Check thresholds and log warnings
            self._check_resource_thresholds(metrics)
            
        except Exception as e:
            logger.error(f"Failed to collect resource metrics: {e}")
    
    def _check_resource_thresholds(self, metrics: Dict[str, Any]) -> None:
        """Check if any resource thresholds are exceeded."""
        for metric, threshold in self.resource_thresholds.items():
            if metric in metrics and metrics[metric] > threshold:
                logger.warning(
                    f"Resource threshold exceeded: {metric}={metrics[metric]:.2f} > {threshold}"
                )
    
    def get_resource_stats(self) -> Dict[str, Any]:
        """Get current resource statistics."""
        with self._lock:
            stats = {}
            for metric, history in self.resource_history.items():
                if history:
                    stats[metric] = {
                        'current': history[-1],
                        'avg': sum(history) / len(history),
                        'max': max(history),
                        'min': min(history)
                    }
            return stats


class ConnectionPoolManager:
    """Manages connection pools for all external API integrations with enhanced monitoring and leak detection."""
    
    def __init__(self, health_check_interval: int = 30, enable_leak_detection: bool = True):
        self.pools = {}
        self.metrics = {
            'total_requests': 0,
            'failed_requests': 0,
            'avg_response_time': 0.0,
            'pool_usage': {},
            'connection_leaks': 0,
            'resources_cleaned': 0
        }
        self.health_monitor = HealthMonitor(check_interval=health_check_interval)
        
        # Enhanced monitoring components
        self.leak_detector = LeakDetector() if enable_leak_detection else None
        self.resource_monitor = ResourceMonitor()
        
        self._lock = threading.Lock()
        self._connection_counter = 0
        
        logger.info(f"Initialized ConnectionPoolManager with leak_detection={enable_leak_detection}")
    
    def create_line_bot_api(self, channel_access_token: str, **kwargs) -> OptimizedLineBotApi:
        """Create optimized LINE Bot API client with health monitoring."""
        default_config = {
            'timeout': 10,
            'pool_maxsize': 20,
            'max_retries': 3
        }
        default_config.update(kwargs)
        
        line_bot_api = OptimizedLineBotApi(channel_access_token, **default_config)
        
        # Register for health monitoring
        self.health_monitor.register_connection(
            'line_bot_api',
            lambda: self._health_check_line_api(line_bot_api),
            failure_threshold=5
        )
        
        return line_bot_api
    
    def create_session_with_pooling(self, name: str, base_url: str = None, 
                                  pool_maxsize: int = 20, max_retries: int = 3, 
                                  enable_keep_alive: bool = True) -> requests.Session:
        """Create a requests session with enhanced connection pooling, leak detection, and health monitoring."""
        session = requests.Session()
        
        # Enhanced retry strategy with exponential backoff
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=2,  # Exponential backoff
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "POST", "PUT", "DELETE", "OPTIONS", "TRACE"]
        )
        
        # Enhanced adapter with connection pooling optimizations
        adapter = requests.adapters.HTTPAdapter(
            pool_maxsize=pool_maxsize,
            pool_block=False,  # Don't block when pool is full
            max_retries=retry_strategy
        )
        
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        
        # Configure keep-alive and connection reuse
        if enable_keep_alive:
            session.headers.update({
                'Connection': 'keep-alive',
                'Keep-Alive': 'timeout=30, max=100'
            })
        
        # Generate unique connection ID for tracking
        with self._lock:
            self._connection_counter += 1
            connection_id = f"{name}_{self._connection_counter}_{int(time.time())}"
            
            self.pools[name] = {
                'session': session,
                'base_url': base_url,
                'created_at': time.time(),
                'request_count': 0,
                'connection_id': connection_id,
                'pool_maxsize': pool_maxsize,
                'keep_alive': enable_keep_alive
            }
        
        # Register for leak detection
        if self.leak_detector:
            self.leak_detector.register_connection(connection_id, session, 'requests_session')
        
        # Register for health monitoring
        self.health_monitor.register_connection(
            name,
            lambda: self._health_check_session(session, base_url),
            failure_threshold=5
        )
        
        logger.info(
            f"Created enhanced connection pool '{name}' (ID: {connection_id}) "
            f"with {pool_maxsize} max connections, keep_alive={enable_keep_alive}"
        )
        return session
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get comprehensive connection pool, health, leak detection, and resource metrics."""
        with self._lock:
            pool_metrics = {
                'pools': {name: {
                    'request_count': pool['request_count'],
                    'age_seconds': time.time() - pool['created_at'],
                    'connection_id': pool.get('connection_id', 'unknown'),
                    'pool_maxsize': pool.get('pool_maxsize', 0),
                    'keep_alive': pool.get('keep_alive', False)
                } for name, pool in self.pools.items()},
                'total_pools': len(self.pools),
                **self.metrics
            }
        
        # Add health monitoring metrics
        health_metrics = {}
        for name, metrics in self.health_monitor.get_all_health_metrics().items():
            health_metrics[name] = {
                'state': metrics.state.value,
                'success_count': metrics.success_count,
                'failure_count': metrics.failure_count,
                'avg_response_time': metrics.avg_response_time,
                'active_connections': metrics.active_connections,
                'peak_connections': metrics.peak_connections,
                'leaked_connections': metrics.leaked_connections,
                'total_bytes_sent': metrics.total_bytes_sent,
                'total_bytes_received': metrics.total_bytes_received,
                'last_success': metrics.last_success.isoformat() if metrics.last_success else None,
                'last_failure': metrics.last_failure.isoformat() if metrics.last_failure else None
            }
        
        pool_metrics['health'] = health_metrics
        
        # Add leak detection metrics
        if self.leak_detector:
            pool_metrics['leak_detection'] = self.leak_detector.get_leak_stats()
        
        # Add resource monitoring metrics
        pool_metrics['resources'] = self.resource_monitor.get_resource_stats()
        
        return pool_metrics
    
    def start_monitoring(self) -> None:
        """Start comprehensive monitoring for all connections and resources."""
        self.health_monitor.start_monitoring()
        
        if self.leak_detector:
            self.leak_detector.start_cleanup()
            
        self.resource_monitor.start_monitoring()
        
        logger.info("Started comprehensive connection pool monitoring")
    
    def stop_monitoring(self) -> None:
        """Stop all monitoring activities."""
        self.health_monitor.stop_monitoring()
        
        if self.leak_detector:
            self.leak_detector.stop_cleanup()
            
        self.resource_monitor.stop_monitoring()
        
        logger.info("Stopped comprehensive connection pool monitoring")
    
    def start_health_monitoring(self) -> None:
        """Start health monitoring for all connections (backward compatibility)."""
        self.start_monitoring()
    
    def stop_health_monitoring(self) -> None:
        """Stop health monitoring (backward compatibility)."""
        self.stop_monitoring()
    
    def execute_with_retry(self, connection_name: str, func: Callable, 
                          max_attempts: int = 3, backoff: Optional[ExponentialBackoff] = None) -> Any:
        """Execute function with automatic retry logic, health monitoring, and usage tracking."""
        try:
            result = self.health_monitor.execute_with_retry(connection_name, func, max_attempts, backoff)
            # Update usage tracking on successful execution
            self.update_connection_usage(connection_name)
            return result
        except Exception as e:
            # Still update usage tracking even on failure
            self.update_connection_usage(connection_name)
            raise e
    
    def is_connection_healthy(self, name: str) -> bool:
        """Check if a connection is healthy."""
        return self.health_monitor.is_connection_healthy(name)
    
    def get_connection_health(self, name: str) -> Optional[HealthMetrics]:
        """Get health metrics for a specific connection."""
        return self.health_monitor.get_connection_health(name)
    
    def _health_check_line_api(self, line_api: OptimizedLineBotApi) -> bool:
        """Perform health check for LINE Bot API."""
        try:
            # Perform a lightweight API call to check connectivity
            # This is a placeholder - actual implementation would call a simple API endpoint
            # For now, we'll assume the connection is healthy if the object exists
            return line_api is not None
        except Exception as e:
            logger.warning(f"LINE API health check failed: {e}")
            return False
    
    def _health_check_session(self, session: requests.Session, base_url: Optional[str]) -> bool:
        """Perform health check for a requests session."""
        try:
            if base_url:
                # Try a simple HEAD request to the base URL
                response = session.head(base_url, timeout=5)
                return response.status_code < 500
            else:
                # If no base URL, just check if session is available
                return session is not None
        except Exception as e:
            logger.warning(f"Session health check failed: {e}")
            return False
    
    def force_cleanup_connection(self, connection_name: str) -> bool:
        """Force cleanup of a specific connection pool."""
        with self._lock:
            if connection_name not in self.pools:
                logger.warning(f"Connection pool '{connection_name}' not found for cleanup")
                return False
            
            pool = self.pools[connection_name]
            
            try:
                # Close the session if it exists
                if 'session' in pool:
                    pool['session'].close()
                
                # Unregister from leak detector
                if self.leak_detector and 'connection_id' in pool:
                    self.leak_detector.unregister_connection(pool['connection_id'])
                
                # Remove from pools
                del self.pools[connection_name]
                
                logger.info(f"Force cleaned up connection pool '{connection_name}'")
                return True
                
            except Exception as e:
                logger.error(f"Error during force cleanup of '{connection_name}': {e}")
                return False
    
    def cleanup_idle_connections(self, max_idle_time: int = 3600) -> int:
        """Clean up idle connection pools."""
        current_time = time.time()
        cleaned_count = 0
        
        connections_to_cleanup = []
        
        with self._lock:
            for name, pool in self.pools.items():
                last_used = pool.get('last_used', pool['created_at'])
                idle_time = current_time - last_used
                
                if idle_time > max_idle_time:
                    connections_to_cleanup.append(name)
        
        # Clean up idle connections
        for name in connections_to_cleanup:
            if self.force_cleanup_connection(name):
                cleaned_count += 1
        
        if cleaned_count > 0:
            logger.info(f"Cleaned up {cleaned_count} idle connection pools")
        
        return cleaned_count
    
    def cleanup_pools(self):
        """Clean up all connection pools and stop monitoring."""
        # Stop all monitoring first
        self.stop_monitoring()
        
        # Clean up connection pools
        with self._lock:
            for name, pool in list(self.pools.items()):
                try:
                    if 'session' in pool:
                        pool['session'].close()
                    
                    # Unregister from leak detector
                    if self.leak_detector and 'connection_id' in pool:
                        self.leak_detector.unregister_connection(pool['connection_id'])
                        
                    logger.info(f"Closed connection pool '{name}'")
                except Exception as e:
                    logger.error(f"Error closing connection pool '{name}': {e}")
            
            self.pools.clear()
        
        logger.info("Completed connection pool cleanup")


    def update_connection_usage(self, connection_name: str) -> None:
        """Update usage tracking for a connection."""
        with self._lock:
            if connection_name in self.pools:
                self.pools[connection_name]['last_used'] = time.time()
                self.pools[connection_name]['request_count'] += 1
                
                # Update leak detector
                if self.leak_detector and 'connection_id' in self.pools[connection_name]:
                    self.leak_detector.update_connection_usage(
                        self.pools[connection_name]['connection_id']
                    )


# Global connection pool manager with enhanced monitoring
connection_pool_manager = ConnectionPoolManager(enable_leak_detection=True)