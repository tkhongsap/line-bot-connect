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
from typing import Optional, Dict, Any, Callable
from linebot import LineBotApi
from enum import Enum
from dataclasses import dataclass
from datetime import datetime, timedelta
import random

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


class ConnectionPoolManager:
    """Manages connection pools for all external API integrations with health monitoring."""
    
    def __init__(self, health_check_interval: int = 30):
        self.pools = {}
        self.metrics = {
            'total_requests': 0,
            'failed_requests': 0,
            'avg_response_time': 0.0,
            'pool_usage': {}
        }
        self.health_monitor = HealthMonitor(check_interval=health_check_interval)
        self._lock = threading.Lock()
    
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
                                  pool_maxsize: int = 20, max_retries: int = 3) -> requests.Session:
        """Create a requests session with connection pooling and health monitoring."""
        session = requests.Session()
        
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504]
        )
        
        adapter = requests.adapters.HTTPAdapter(
            pool_maxsize=pool_maxsize,
            max_retries=retry_strategy
        )
        
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        
        with self._lock:
            self.pools[name] = {
                'session': session,
                'base_url': base_url,
                'created_at': time.time(),
                'request_count': 0
            }
        
        # Register for health monitoring
        self.health_monitor.register_connection(
            name,
            lambda: self._health_check_session(session, base_url),
            failure_threshold=5
        )
        
        logger.info(f"Created connection pool '{name}' with {pool_maxsize} max connections")
        return session
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get comprehensive connection pool and health metrics."""
        with self._lock:
            pool_metrics = {
                'pools': {name: {
                    'request_count': pool['request_count'],
                    'age_seconds': time.time() - pool['created_at']
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
                'last_success': metrics.last_success.isoformat() if metrics.last_success else None,
                'last_failure': metrics.last_failure.isoformat() if metrics.last_failure else None
            }
        
        pool_metrics['health'] = health_metrics
        return pool_metrics
    
    def start_health_monitoring(self) -> None:
        """Start health monitoring for all connections."""
        self.health_monitor.start_monitoring()
    
    def stop_health_monitoring(self) -> None:
        """Stop health monitoring."""
        self.health_monitor.stop_monitoring()
    
    def execute_with_retry(self, connection_name: str, func: Callable, 
                          max_attempts: int = 3, backoff: Optional[ExponentialBackoff] = None) -> Any:
        """Execute function with automatic retry logic and health monitoring."""
        return self.health_monitor.execute_with_retry(connection_name, func, max_attempts, backoff)
    
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
    
    def cleanup_pools(self):
        """Clean up connection pools and stop monitoring."""
        # Stop health monitoring first
        self.stop_health_monitoring()
        
        # Clean up connection pools
        with self._lock:
            for name, pool in self.pools.items():
                if 'session' in pool:
                    pool['session'].close()
                    logger.info(f"Closed connection pool '{name}'")
            self.pools.clear()


# Global connection pool manager
connection_pool_manager = ConnectionPoolManager()