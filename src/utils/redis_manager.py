"""
Redis Connection Manager with Circuit Breaker Pattern

This module provides a centralized Redis connection manager with circuit breaker pattern,
connection health monitoring, automatic retry logic, and graceful fallback capabilities.
It replaces scattered Redis connection logic across the codebase with a unified approach.
"""

import logging
import time
import threading
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Dict, Any, Callable, Union
from functools import wraps
import redis
from redis.connection import ConnectionPool
from redis.exceptions import RedisError, ConnectionError, TimeoutError
import random
import atexit

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Circuit is open, failing fast
    HALF_OPEN = "half_open"  # Testing if service is back


class ExponentialBackoff:
    """Exponential backoff with jitter for retry logic."""
    
    def __init__(self, base_delay: float = 1.0, max_delay: float = 30.0, 
                 multiplier: float = 2.0, jitter: bool = True):
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.multiplier = multiplier
        self.jitter = jitter
    
    def get_delay(self, attempt: int) -> float:
        """Calculate delay for the given attempt number."""
        delay = min(self.base_delay * (self.multiplier ** attempt), self.max_delay)
        
        if self.jitter:
            # Add random jitter (±25%) to prevent thundering herd
            jitter_amount = delay * 0.25
            delay += random.uniform(-jitter_amount, jitter_amount)
        
        return max(delay, 0.1)  # Minimum 100ms delay


class RedisConnectionManager:
    """
    Centralized Redis connection manager with circuit breaker pattern.
    
    Features:
    - Circuit breaker pattern for resilience
    - Connection health monitoring
    - Automatic retry logic with exponential backoff
    - Connection pooling with configurable limits
    - Graceful fallback support
    - Thread-safe operations
    """
    
    def __init__(self, 
                 redis_url: str = "redis://localhost:6379/0",
                 max_connections: int = 50,
                 socket_connect_timeout: int = 5,
                 socket_timeout: int = 5,
                 failure_threshold: int = 5,
                 recovery_timeout: int = 60,
                 retry_on_timeout: bool = True,
                 health_check_interval: int = 30,
                 max_retry_attempts: int = 3,
                 enable_health_monitoring: bool = True):
        """
        Initialize Redis connection manager.
        
        Args:
            redis_url: Redis connection URL
            max_connections: Maximum connections in pool
            socket_connect_timeout: Connection timeout in seconds
            socket_timeout: Socket timeout in seconds
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Time to wait before trying recovery (seconds)
            retry_on_timeout: Whether to retry on timeout errors
            health_check_interval: Interval between health checks (seconds)
            max_retry_attempts: Maximum retry attempts for operations
            enable_health_monitoring: Whether to enable automatic health monitoring
        """
        self.redis_url = redis_url
        self.max_connections = max_connections
        self.socket_connect_timeout = socket_connect_timeout
        self.socket_timeout = socket_timeout
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.retry_on_timeout = retry_on_timeout
        self.health_check_interval = health_check_interval
        self.max_retry_attempts = max_retry_attempts
        self.enable_health_monitoring = enable_health_monitoring
        
        # Circuit breaker state
        self._circuit_state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time = None
        self._half_open_start_time = None
        self._lock = threading.RLock()
        
        # Connection pool and client
        self._pool = None
        self._client = None
        self._is_healthy = False
        
        # Exponential backoff for retries
        self._backoff = ExponentialBackoff(
            base_delay=1.0,
            max_delay=30.0,
            multiplier=2.0,
            jitter=True
        )
        
        # Health monitoring
        self._health_monitor_thread = None
        self._health_monitor_stop = threading.Event()
        self._last_health_check_time = None
        self._health_metrics = {
            'response_times': [],
            'consecutive_failures': 0,
            'consecutive_successes': 0,
            'last_response_time': None
        }
        
        # Statistics
        self._stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'circuit_opens': 0,
            'circuit_closes': 0,
            'fallback_activations': 0,
            'last_health_check': None,
            'last_error': None,
            'retry_attempts': 0,
            'retry_successes': 0,
            'health_check_count': 0
        }
        
        # Initialize connection
        self._initialize_connection()
        
        # Start health monitoring if enabled
        if self.enable_health_monitoring:
            self._start_health_monitoring()
        
        # Register cleanup on exit
        atexit.register(self.close)
    
    def _initialize_connection(self) -> bool:
        """Initialize Redis connection pool and client."""
        try:
            with self._lock:
                # Create connection pool
                self._pool = ConnectionPool.from_url(
                    self.redis_url,
                    max_connections=self.max_connections,
                    retry_on_timeout=self.retry_on_timeout,
                    socket_connect_timeout=self.socket_connect_timeout,
                    socket_timeout=self.socket_timeout,
                    health_check_interval=30  # Health check every 30 seconds
                )
                
                # Create Redis client
                self._client = redis.Redis(connection_pool=self._pool)
                
                # Test connection
                self._client.ping()
                self._is_healthy = True
                self._circuit_state = CircuitState.CLOSED
                self._failure_count = 0
                
                logger.info(f"Redis connection manager initialized successfully")
                logger.info(f"Redis URL: {self.redis_url}")
                logger.info(f"Max connections: {self.max_connections}")
                logger.info(f"Circuit breaker threshold: {self.failure_threshold}")
                
                return True
                
        except Exception as e:
            logger.error(f"Failed to initialize Redis connection: {e}")
            self._is_healthy = False
            self._client = None
            self._pool = None
            self._record_failure(str(e))
            return False
    
    def _record_failure(self, error_msg: str):
        """Record a failure and update circuit breaker state."""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = datetime.now()
            self._stats['failed_requests'] += 1
            self._stats['last_error'] = error_msg
            
            # Check if we should open the circuit
            if (self._circuit_state == CircuitState.CLOSED and 
                self._failure_count >= self.failure_threshold):
                self._open_circuit()
    
    def _record_success(self):
        """Record a successful operation."""
        with self._lock:
            self._stats['successful_requests'] += 1
            
            # If we're in half-open state and got a success, close the circuit
            if self._circuit_state == CircuitState.HALF_OPEN:
                self._close_circuit()
    
    def _open_circuit(self):
        """Open the circuit breaker."""
        with self._lock:
            if self._circuit_state != CircuitState.OPEN:
                self._circuit_state = CircuitState.OPEN
                self._stats['circuit_opens'] += 1
                logger.warning(f"Circuit breaker opened after {self._failure_count} failures")
    
    def _close_circuit(self):
        """Close the circuit breaker."""
        with self._lock:
            if self._circuit_state != CircuitState.CLOSED:
                self._circuit_state = CircuitState.CLOSED
                self._failure_count = 0
                self._stats['circuit_closes'] += 1
                logger.info("Circuit breaker closed - Redis connection restored")
    
    def _should_attempt_reset(self) -> bool:
        """Check if we should attempt to reset the circuit."""
        with self._lock:
            if self._circuit_state != CircuitState.OPEN:
                return False
            
            if not self._last_failure_time:
                return True
            
            time_since_failure = (datetime.now() - self._last_failure_time).total_seconds()
            return time_since_failure >= self.recovery_timeout
    
    def _attempt_reset(self):
        """Attempt to reset the circuit to half-open state."""
        with self._lock:
            if self._should_attempt_reset():
                self._circuit_state = CircuitState.HALF_OPEN
                self._half_open_start_time = datetime.now()
                logger.info("Circuit breaker moved to half-open state - testing connection")
    
    def is_circuit_open(self) -> bool:
        """Check if circuit breaker is open."""
        with self._lock:
            return self._circuit_state == CircuitState.OPEN
    
    def get_client(self) -> Optional[redis.Redis]:
        """
        Get Redis client if available.
        
        Returns:
            Redis client if connection is healthy and circuit is not open,
            None otherwise.
        """
        with self._lock:
            self._stats['total_requests'] += 1
            
            # Check circuit breaker state
            if self._circuit_state == CircuitState.OPEN:
                self._attempt_reset()
                if self._circuit_state == CircuitState.OPEN:
                    # Still open, fail fast
                    self._stats['fallback_activations'] += 1
                    return None
            
            # Return client if available
            if self._client and self._is_healthy:
                return self._client
            
            # Try to reinitialize connection
            if self._initialize_connection():
                return self._client
            
            return None
    
    def execute_with_fallback(self, 
                            operation: Callable[[redis.Redis], Any],
                            fallback: Callable[[], Any] = None,
                            operation_name: str = "redis_operation",
                            use_retry: bool = True) -> Any:
        """
        Execute Redis operation with automatic retry and fallback.
        
        Args:
            operation: Function that takes Redis client and returns result
            fallback: Function to call if Redis operation fails
            operation_name: Name of operation for logging
            use_retry: Whether to use automatic retry with exponential backoff
            
        Returns:
            Result from operation or fallback
        """
        client = self.get_client()
        
        if not client:
            logger.warning(f"Redis unavailable for {operation_name}, using fallback")
            self._stats['fallback_activations'] += 1
            return fallback() if fallback else None
        
        try:
            if use_retry:
                # Execute with retry logic
                result = self._execute_with_retry(
                    lambda: operation(client),
                    operation_name
                )
            else:
                # Execute without retry
                result = operation(client)
            
            self._record_success()
            
            # Update health metrics
            with self._lock:
                self._health_metrics['consecutive_successes'] += 1
                self._health_metrics['consecutive_failures'] = 0
            
            return result
            
        except (ConnectionError, TimeoutError, RedisError) as e:
            logger.error(f"Redis operation '{operation_name}' failed: {e}")
            self._record_failure(str(e))
            
            # Update health metrics
            with self._lock:
                self._health_metrics['consecutive_failures'] += 1
                self._health_metrics['consecutive_successes'] = 0
            
            # Use fallback if available
            if fallback:
                logger.info(f"Using fallback for {operation_name}")
                self._stats['fallback_activations'] += 1
                return fallback()
            
            return None
        
        except Exception as e:
            logger.error(f"Unexpected error in Redis operation '{operation_name}': {e}")
            self._record_failure(str(e))
            return None
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform comprehensive health check.
        
        Returns:
            Dictionary with health status and metrics
        """
        with self._lock:
            self._last_health_check_time = datetime.now()
            health_status = {
                'is_healthy': False,
                'circuit_state': self._circuit_state.value,
                'failure_count': self._failure_count,
                'last_failure_time': self._last_failure_time.isoformat() if self._last_failure_time else None,
                'connection_pool_created': self._pool is not None,
                'redis_client_created': self._client is not None,
                'ping_successful': False,
                'timestamp': self._last_health_check_time.isoformat()
            }
            
            # Try to ping Redis if client exists
            if self._client:
                try:
                    ping_result = self._client.ping()
                    health_status['ping_successful'] = ping_result
                    health_status['is_healthy'] = ping_result
                    self._is_healthy = ping_result
                    
                    if ping_result:
                        self._record_success()
                        self._health_metrics['consecutive_successes'] += 1
                        self._health_metrics['consecutive_failures'] = 0
                    
                except Exception as e:
                    logger.error(f"Health check ping failed: {e}")
                    health_status['ping_error'] = str(e)
                    self._is_healthy = False
                    self._record_failure(str(e))
                    self._health_metrics['consecutive_failures'] += 1
                    self._health_metrics['consecutive_successes'] = 0
            
            self._stats['last_health_check'] = health_status['timestamp']
            return health_status
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get connection manager statistics."""
        with self._lock:
            stats = self._stats.copy()
            
            # Calculate average response time
            avg_response_time = None
            if self._health_metrics['response_times']:
                avg_response_time = sum(self._health_metrics['response_times']) / len(self._health_metrics['response_times'])
            
            stats.update({
                'circuit_state': self._circuit_state.value,
                'failure_count': self._failure_count,
                'is_healthy': self._is_healthy,
                'pool_info': self._get_pool_info(),
                'success_rate': self._calculate_success_rate(),
                'health_monitoring': {
                    'enabled': self.enable_health_monitoring,
                    'thread_alive': self._health_monitor_thread.is_alive() if self._health_monitor_thread else False,
                    'interval': self.health_check_interval,
                    'last_check': self._last_health_check_time.isoformat() if self._last_health_check_time else None,
                    'consecutive_failures': self._health_metrics['consecutive_failures'],
                    'consecutive_successes': self._health_metrics['consecutive_successes'],
                    'avg_response_time': avg_response_time,
                    'last_response_time': self._health_metrics['last_response_time']
                },
                'retry_stats': {
                    'max_attempts': self.max_retry_attempts,
                    'total_retries': self._stats.get('retry_attempts', 0),
                    'successful_retries': self._stats.get('retry_successes', 0),
                    'retry_success_rate': (
                        (self._stats.get('retry_successes', 0) / self._stats.get('retry_attempts', 0) * 100)
                        if self._stats.get('retry_attempts', 0) > 0 else 0
                    )
                }
            })
            return stats
    
    def _get_pool_info(self) -> Dict[str, Any]:
        """Get connection pool information."""
        if not self._pool:
            return {'status': 'not_initialized'}
        
        try:
            return {
                'max_connections': self._pool.max_connections,
                'created_connections': len(self._pool._created_connections),
                'available_connections': len(self._pool._available_connections),
                'in_use_connections': len(self._pool._in_use_connections)
            }
        except Exception as e:
            logger.error(f"Error getting pool info: {e}")
            return {'error': str(e)}
    
    def _calculate_success_rate(self) -> float:
        """Calculate success rate percentage."""
        total = self._stats['total_requests']
        if total == 0:
            return 100.0
        
        successful = self._stats['successful_requests']
        return (successful / total) * 100.0
    
    def reset_circuit(self):
        """Manually reset circuit breaker (for testing/admin purposes)."""
        with self._lock:
            logger.info("Manually resetting circuit breaker")
            self._circuit_state = CircuitState.CLOSED
            self._failure_count = 0
            self._last_failure_time = None
            self._half_open_start_time = None
            
            # Try to reinitialize connection
            self._initialize_connection()
    
    def _start_health_monitoring(self):
        """Start the background health monitoring thread."""
        if self._health_monitor_thread and self._health_monitor_thread.is_alive():
            logger.warning("Health monitoring thread already running")
            return
        
        self._health_monitor_stop.clear()
        self._health_monitor_thread = threading.Thread(
            target=self._health_monitor_loop,
            name="redis-health-monitor",
            daemon=True
        )
        self._health_monitor_thread.start()
        logger.info(f"Started Redis health monitoring thread (interval: {self.health_check_interval}s)")
    
    def _stop_health_monitoring(self):
        """Stop the background health monitoring thread."""
        if self._health_monitor_thread:
            logger.info("Stopping Redis health monitoring thread")
            self._health_monitor_stop.set()
            self._health_monitor_thread.join(timeout=5)
            self._health_monitor_thread = None
    
    def _health_monitor_loop(self):
        """Background health monitoring loop."""
        while not self._health_monitor_stop.is_set():
            try:
                # Perform health check
                start_time = time.time()
                health_status = self.health_check()
                response_time = time.time() - start_time
                
                # Update health metrics
                with self._lock:
                    self._health_metrics['response_times'].append(response_time)
                    # Keep only last 100 response times
                    if len(self._health_metrics['response_times']) > 100:
                        self._health_metrics['response_times'].pop(0)
                    
                    self._health_metrics['last_response_time'] = response_time
                    self._stats['health_check_count'] += 1
                
                # Log health status changes
                if health_status['is_healthy'] and not self._is_healthy:
                    logger.info("Redis connection recovered - health check successful")
                elif not health_status['is_healthy'] and self._is_healthy:
                    logger.warning("Redis connection degraded - health check failed")
                
                # Auto-recover circuit if health improves
                if (health_status['is_healthy'] and 
                    self._circuit_state == CircuitState.OPEN and
                    self._should_attempt_reset()):
                    logger.info("Auto-recovering circuit breaker based on health check")
                    self._attempt_reset()
                
            except Exception as e:
                logger.error(f"Error in health monitor loop: {e}")
            
            # Wait for next check interval
            self._health_monitor_stop.wait(self.health_check_interval)
    
    def _execute_with_retry(self, operation: Callable, operation_name: str = "redis_operation") -> Any:
        """Execute operation with exponential backoff retry logic."""
        last_error = None
        
        for attempt in range(self.max_retry_attempts):
            try:
                self._stats['retry_attempts'] += 1
                result = operation()
                
                if attempt > 0:
                    self._stats['retry_successes'] += 1
                    logger.info(f"Redis operation '{operation_name}' succeeded after {attempt + 1} attempts")
                
                return result
                
            except (ConnectionError, TimeoutError) as e:
                last_error = e
                
                if attempt < self.max_retry_attempts - 1:
                    delay = self._backoff.get_delay(attempt)
                    logger.warning(
                        f"Redis operation '{operation_name}' failed (attempt {attempt + 1}/{self.max_retry_attempts}), "
                        f"retrying in {delay:.2f}s: {e}"
                    )
                    time.sleep(delay)
                else:
                    logger.error(
                        f"Redis operation '{operation_name}' failed after {self.max_retry_attempts} attempts: {e}"
                    )
            
            except Exception as e:
                # Non-retryable error
                logger.error(f"Non-retryable error in Redis operation '{operation_name}': {e}")
                raise
        
        # All retries exhausted
        raise last_error
    
    def close(self):
        """Close all connections and cleanup resources."""
        with self._lock:
            # Stop health monitoring
            if self.enable_health_monitoring:
                self._stop_health_monitoring()
            
            # Close connections
            if self._pool:
                try:
                    self._pool.disconnect()
                    logger.info("Redis connection pool closed")
                except Exception as e:
                    logger.error(f"Error closing Redis pool: {e}")
                finally:
                    self._pool = None
                    self._client = None
                    self._is_healthy = False


def redis_operation(operation_name: str = None, fallback_value: Any = None):
    """
    Decorator for Redis operations with automatic circuit breaker and fallback.
    
    Args:
        operation_name: Name of the operation for logging
        fallback_value: Value to return if Redis operation fails
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            # Assume the decorated method is part of a class that has redis_manager
            if not hasattr(self, 'redis_manager'):
                logger.error(f"Class {self.__class__.__name__} doesn't have redis_manager attribute")
                return fallback_value
            
            op_name = operation_name or func.__name__
            
            def redis_op(client):
                # Call the original method with Redis client as first parameter
                return func(self, client, *args, **kwargs)
            
            def fallback():
                return fallback_value
            
            return self.redis_manager.execute_with_fallback(redis_op, fallback, op_name)
        
        return wrapper
    return decorator


# Global Redis connection manager instance
_global_redis_manager = None
_manager_lock = threading.Lock()


def get_redis_manager(redis_url: str = None, **kwargs) -> RedisConnectionManager:
    """
    Get global Redis connection manager instance (singleton pattern).
    
    Args:
        redis_url: Redis connection URL (only used for first initialization)
        **kwargs: Additional arguments for RedisConnectionManager
        
    Returns:
        RedisConnectionManager instance
    """
    global _global_redis_manager
    
    with _manager_lock:
        if _global_redis_manager is None:
            import os
            url = redis_url or os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
            _global_redis_manager = RedisConnectionManager(redis_url=url, **kwargs)
        
        return _global_redis_manager


def reset_global_manager():
    """Reset global Redis manager (mainly for testing)."""
    global _global_redis_manager
    
    with _manager_lock:
        if _global_redis_manager:
            _global_redis_manager.close()
            _global_redis_manager = None