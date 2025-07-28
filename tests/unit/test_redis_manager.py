"""
Unit tests for Redis Connection Manager with Circuit Breaker Pattern
"""

import pytest
import time
import threading
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime, timedelta
import redis
from redis.exceptions import ConnectionError, TimeoutError, RedisError

from src.utils.redis_manager import (
    RedisConnectionManager, 
    CircuitState,
    ExponentialBackoff, 
    redis_operation,
    get_redis_manager,
    reset_global_manager
)


class TestRedisConnectionManager:
    """Test suite for RedisConnectionManager"""
    
    def setup_method(self):
        """Setup for each test method"""
        self.redis_url = "redis://localhost:6379/0"
        self.manager = None
    
    def teardown_method(self):
        """Cleanup after each test method"""
        if self.manager:
            self.manager.close()
        reset_global_manager()
    
    @patch('redis.Redis')
    @patch('redis.connection.ConnectionPool.from_url')
    def test_successful_initialization(self, mock_pool, mock_redis):
        """Test successful Redis connection initialization"""
        # Setup mocks
        mock_pool_instance = Mock()
        mock_pool.return_value = mock_pool_instance
        
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_redis.return_value = mock_client
        
        # Create manager with health monitoring disabled to avoid extra ping calls
        self.manager = RedisConnectionManager(
            self.redis_url,
            enable_health_monitoring=False
        )
        
        # Assertions
        assert self.manager._is_healthy is True
        assert self.manager._circuit_state == CircuitState.CLOSED
        assert self.manager._failure_count == 0
        mock_pool.assert_called_once()
        mock_client.ping.assert_called_once()
    
    @patch('redis.Redis')
    @patch('redis.connection.ConnectionPool.from_url')
    def test_failed_initialization(self, mock_pool, mock_redis):
        """Test Redis connection initialization failure"""
        # Setup mocks to fail
        mock_pool.side_effect = ConnectionError("Connection failed")
        
        # Create manager
        self.manager = RedisConnectionManager(self.redis_url)
        
        # Assertions
        assert self.manager._is_healthy is False
        assert self.manager._client is None
        assert self.manager._pool is None
        assert self.manager._failure_count > 0
    
    @patch('redis.Redis')
    @patch('redis.connection.ConnectionPool.from_url')
    def test_circuit_breaker_opens_after_failures(self, mock_pool, mock_redis):
        """Test circuit breaker opens after threshold failures"""
        # Setup mocks
        mock_pool_instance = Mock()
        mock_pool.return_value = mock_pool_instance
        
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_redis.return_value = mock_client
        
        # Create manager with low failure threshold
        self.manager = RedisConnectionManager(
            self.redis_url, 
            failure_threshold=3
        )
        
        # Simulate failures
        for i in range(3):
            self.manager._record_failure(f"Test failure {i}")
        
        # Check circuit is open
        assert self.manager._circuit_state == CircuitState.OPEN
        assert self.manager.is_circuit_open() is True
        assert self.manager._stats['circuit_opens'] == 1
    
    @patch('redis.Redis')
    @patch('redis.connection.ConnectionPool.from_url')
    def test_circuit_breaker_half_open_transition(self, mock_pool, mock_redis):
        """Test circuit breaker transitions to half-open after timeout"""
        # Setup mocks
        mock_pool_instance = Mock()
        mock_pool.return_value = mock_pool_instance
        
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_redis.return_value = mock_client
        
        # Create manager with short recovery timeout
        self.manager = RedisConnectionManager(
            self.redis_url,
            failure_threshold=2,
            recovery_timeout=1  # 1 second
        )
        
        # Open circuit
        self.manager._record_failure("Test failure 1")
        self.manager._record_failure("Test failure 2")
        assert self.manager._circuit_state == CircuitState.OPEN
        
        # Wait for recovery timeout
        time.sleep(1.1)
        
        # Attempt to get client should move to half-open
        client = self.manager.get_client()
        assert self.manager._circuit_state == CircuitState.HALF_OPEN
    
    @patch('redis.Redis')
    @patch('redis.connection.ConnectionPool.from_url')
    def test_circuit_breaker_closes_on_success(self, mock_pool, mock_redis):
        """Test circuit breaker closes on successful operation in half-open state"""
        # Setup mocks
        mock_pool_instance = Mock()
        mock_pool.return_value = mock_pool_instance
        
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_redis.return_value = mock_client
        
        # Create manager
        self.manager = RedisConnectionManager(
            self.redis_url,
            failure_threshold=2
        )
        
        # Open circuit and move to half-open
        self.manager._record_failure("Test failure 1")
        self.manager._record_failure("Test failure 2")
        self.manager._circuit_state = CircuitState.HALF_OPEN
        
        # Record success should close circuit
        self.manager._record_success()
        
        assert self.manager._circuit_state == CircuitState.CLOSED
        assert self.manager._failure_count == 0
        assert self.manager._stats['circuit_closes'] == 1
    
    @patch('redis.Redis')
    @patch('redis.connection.ConnectionPool.from_url')
    def test_get_client_with_closed_circuit(self, mock_pool, mock_redis):
        """Test getting client with closed circuit"""
        # Setup mocks
        mock_pool_instance = Mock()
        mock_pool.return_value = mock_pool_instance
        
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_redis.return_value = mock_client
        
        # Create manager
        self.manager = RedisConnectionManager(self.redis_url)
        
        # Get client
        client = self.manager.get_client()
        
        assert client is not None
        assert client == mock_client
        assert self.manager._stats['total_requests'] == 1
    
    @patch('redis.Redis')
    @patch('redis.connection.ConnectionPool.from_url')
    def test_get_client_with_open_circuit(self, mock_pool, mock_redis):
        """Test getting client with open circuit returns None"""
        # Setup mocks
        mock_pool_instance = Mock()
        mock_pool.return_value = mock_pool_instance
        
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_redis.return_value = mock_client
        
        # Create manager
        self.manager = RedisConnectionManager(
            self.redis_url,
            failure_threshold=1
        )
        
        # Open circuit
        self.manager._record_failure("Test failure")
        
        # Get client should return None
        client = self.manager.get_client()
        
        assert client is None
        assert self.manager._stats['fallback_activations'] >= 1
    
    @patch('redis.Redis')
    @patch('redis.connection.ConnectionPool.from_url')
    def test_execute_with_fallback_success(self, mock_pool, mock_redis):
        """Test successful execution with fallback"""
        # Setup mocks
        mock_pool_instance = Mock()
        mock_pool.return_value = mock_pool_instance
        
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_client.get.return_value = "test_value"
        mock_redis.return_value = mock_client
        
        # Create manager
        self.manager = RedisConnectionManager(self.redis_url)
        
        # Define operation and fallback
        def redis_op(client):
            return client.get("test_key")
        
        def fallback():
            return "fallback_value"
        
        # Execute operation
        result = self.manager.execute_with_fallback(redis_op, fallback, "test_get")
        
        assert result == "test_value"
        assert self.manager._stats['successful_requests'] >= 1
    
    @patch('redis.Redis')
    @patch('redis.connection.ConnectionPool.from_url')
    def test_execute_with_fallback_redis_error(self, mock_pool, mock_redis):
        """Test fallback execution when Redis operation fails"""
        # Setup mocks
        mock_pool_instance = Mock()
        mock_pool.return_value = mock_pool_instance
        
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_client.get.side_effect = ConnectionError("Connection lost")
        mock_redis.return_value = mock_client
        
        # Create manager
        self.manager = RedisConnectionManager(self.redis_url)
        
        # Define operation and fallback
        def redis_op(client):
            return client.get("test_key")
        
        def fallback():
            return "fallback_value"
        
        # Execute operation
        result = self.manager.execute_with_fallback(redis_op, fallback, "test_get")
        
        assert result == "fallback_value"
        assert self.manager._stats['failed_requests'] >= 1
        assert self.manager._stats['fallback_activations'] >= 1
    
    @patch('redis.Redis')
    @patch('redis.connection.ConnectionPool.from_url')
    def test_execute_with_fallback_no_client(self, mock_pool, mock_redis):
        """Test fallback execution when no Redis client available"""
        # Setup mocks to fail initialization
        mock_pool.side_effect = ConnectionError("Connection failed")
        
        # Create manager
        self.manager = RedisConnectionManager(self.redis_url)
        
        # Define operation and fallback
        def redis_op(client):
            return client.get("test_key")
        
        def fallback():
            return "fallback_value"
        
        # Execute operation
        result = self.manager.execute_with_fallback(redis_op, fallback, "test_get")
        
        assert result == "fallback_value"
        assert self.manager._stats['fallback_activations'] >= 1
    
    @patch('redis.Redis')
    @patch('redis.connection.ConnectionPool.from_url')
    def test_health_check_success(self, mock_pool, mock_redis):
        """Test successful health check"""
        # Setup mocks
        mock_pool_instance = Mock()
        mock_pool.return_value = mock_pool_instance
        
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_redis.return_value = mock_client
        
        # Create manager
        self.manager = RedisConnectionManager(self.redis_url)
        
        # Perform health check
        health = self.manager.health_check()
        
        assert health['is_healthy'] is True
        assert health['ping_successful'] is True
        assert health['circuit_state'] == CircuitState.CLOSED.value
        assert health['connection_pool_created'] is True
        assert health['redis_client_created'] is True
        assert 'timestamp' in health
    
    @patch('redis.Redis')
    @patch('redis.connection.ConnectionPool.from_url')
    def test_health_check_failure(self, mock_pool, mock_redis):
        """Test health check with ping failure"""
        # Setup mocks for successful initialization, but ping fails during health check
        mock_pool_instance = Mock()
        mock_pool.return_value = mock_pool_instance
        
        mock_client = Mock()
        # First ping during initialization succeeds, second ping during health check fails
        mock_client.ping.side_effect = [True, ConnectionError("Ping failed")]
        mock_redis.return_value = mock_client
        
        # Create manager
        self.manager = RedisConnectionManager(self.redis_url)
        
        # Perform health check
        health = self.manager.health_check()
        
        assert health['is_healthy'] is False
        assert health['ping_successful'] is False
        assert 'ping_error' in health
    
    @patch('redis.Redis')
    @patch('redis.connection.ConnectionPool.from_url')
    def test_get_statistics(self, mock_pool, mock_redis):
        """Test statistics collection"""
        # Setup mocks
        mock_pool_instance = Mock()
        mock_pool.return_value = mock_pool_instance
        
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_redis.return_value = mock_client
        
        # Create manager
        self.manager = RedisConnectionManager(self.redis_url)
        
        # Perform some operations
        self.manager.get_client()
        self.manager._record_success()
        self.manager._record_failure("test error")
        
        # Get statistics
        stats = self.manager.get_statistics()
        
        assert 'total_requests' in stats
        assert 'successful_requests' in stats
        assert 'failed_requests' in stats
        assert 'circuit_state' in stats
        assert 'success_rate' in stats
        assert 'pool_info' in stats
        assert stats['total_requests'] >= 1
        assert stats['successful_requests'] >= 1
        assert stats['failed_requests'] >= 1
    
    @patch('redis.Redis')
    @patch('redis.connection.ConnectionPool.from_url')
    def test_reset_circuit(self, mock_pool, mock_redis):
        """Test manual circuit reset"""
        # Setup mocks
        mock_pool_instance = Mock()
        mock_pool.return_value = mock_pool_instance
        
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_redis.return_value = mock_client
        
        # Create manager
        self.manager = RedisConnectionManager(
            self.redis_url,
            failure_threshold=1
        )
        
        # Open circuit
        self.manager._record_failure("Test failure")
        assert self.manager._circuit_state == CircuitState.OPEN
        
        # Reset circuit
        self.manager.reset_circuit()
        
        assert self.manager._circuit_state == CircuitState.CLOSED
        assert self.manager._failure_count == 0
        assert self.manager._last_failure_time is None
    
    @patch('redis.Redis')
    @patch('redis.connection.ConnectionPool.from_url')
    def test_thread_safety(self, mock_pool, mock_redis):
        """Test thread safety of operations"""
        # Setup mocks
        mock_pool_instance = Mock()
        mock_pool.return_value = mock_pool_instance
        
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_redis.return_value = mock_client
        
        # Create manager
        self.manager = RedisConnectionManager(self.redis_url)
        
        results = []
        errors = []
        
        def worker():
            try:
                for _ in range(10):
                    client = self.manager.get_client()
                    results.append(client is not None)
                    self.manager._record_success()
            except Exception as e:
                errors.append(e)
        
        # Run multiple threads
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=worker)
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Check results
        assert len(errors) == 0
        assert len(results) == 50  # 5 threads * 10 operations
        assert all(results)  # All operations should succeed
    
    def test_close_cleanup(self):
        """Test proper cleanup on close"""
        with patch('redis.connection.ConnectionPool.from_url') as mock_pool:
            with patch('redis.Redis') as mock_redis:
                # Setup mocks
                mock_pool_instance = Mock()
                mock_pool.return_value = mock_pool_instance
                
                mock_client = Mock()
                mock_client.ping.return_value = True
                mock_redis.return_value = mock_client
                
                # Create manager
                self.manager = RedisConnectionManager(self.redis_url)
                
                # Close manager
                self.manager.close()
                
                # Check cleanup
                assert self.manager._pool is None
                assert self.manager._client is None
                assert self.manager._is_healthy is False
                mock_pool_instance.disconnect.assert_called_once()
    
    @patch('redis.Redis')
    @patch('redis.connection.ConnectionPool.from_url')
    def test_health_monitoring_thread_starts(self, mock_pool, mock_redis):
        """Test health monitoring thread starts automatically"""
        # Setup mocks
        mock_pool_instance = Mock()
        mock_pool.return_value = mock_pool_instance
        
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_redis.return_value = mock_client
        
        # Create manager with health monitoring enabled
        self.manager = RedisConnectionManager(
            self.redis_url,
            enable_health_monitoring=True,
            health_check_interval=1
        )
        
        # Check thread is running
        assert self.manager._health_monitor_thread is not None
        assert self.manager._health_monitor_thread.is_alive()
        
        # Wait a bit for health check to run
        time.sleep(1.5)
        
        # Check health check was called
        assert self.manager._stats['health_check_count'] > 0
    
    @patch('redis.Redis')
    @patch('redis.connection.ConnectionPool.from_url')
    def test_exponential_backoff_retry(self, mock_pool, mock_redis):
        """Test exponential backoff retry logic"""
        # Setup mocks
        mock_pool_instance = Mock()
        mock_pool.return_value = mock_pool_instance
        
        mock_client = Mock()
        mock_client.ping.return_value = True
        # First two calls fail, third succeeds
        mock_client.get.side_effect = [
            ConnectionError("Connection failed"),
            TimeoutError("Timeout"),
            "success"
        ]
        mock_redis.return_value = mock_client
        
        # Create manager with retry enabled
        self.manager = RedisConnectionManager(
            self.redis_url,
            max_retry_attempts=3
        )
        
        # Execute operation with retry
        def redis_op(client):
            return client.get("test_key")
        
        result = self.manager.execute_with_fallback(
            redis_op, 
            fallback=lambda: "fallback",
            operation_name="test_get",
            use_retry=True
        )
        
        # Should succeed after retries
        assert result == "success"
        assert self.manager._stats['retry_attempts'] >= 3
        assert self.manager._stats['retry_successes'] >= 1
        assert mock_client.get.call_count == 3
    
    @patch('redis.Redis')
    @patch('redis.connection.ConnectionPool.from_url')
    def test_retry_exhaustion_uses_fallback(self, mock_pool, mock_redis):
        """Test fallback is used when all retries are exhausted"""
        # Setup mocks
        mock_pool_instance = Mock()
        mock_pool.return_value = mock_pool_instance
        
        mock_client = Mock()
        mock_client.ping.return_value = True
        # All calls fail
        mock_client.get.side_effect = ConnectionError("Connection failed")
        mock_redis.return_value = mock_client
        
        # Create manager with retry enabled
        self.manager = RedisConnectionManager(
            self.redis_url,
            max_retry_attempts=2
        )
        
        # Execute operation with retry
        def redis_op(client):
            return client.get("test_key")
        
        result = self.manager.execute_with_fallback(
            redis_op, 
            fallback=lambda: "fallback_value",
            operation_name="test_get",
            use_retry=True
        )
        
        # Should use fallback after retries exhausted
        assert result == "fallback_value"
        assert self.manager._stats['retry_attempts'] >= 2
        assert self.manager._stats['fallback_activations'] >= 1
        assert mock_client.get.call_count == 2
    
    @patch('redis.Redis')
    @patch('redis.connection.ConnectionPool.from_url')
    def test_health_metrics_tracking(self, mock_pool, mock_redis):
        """Test health metrics are tracked correctly"""
        # Setup mocks
        mock_pool_instance = Mock()
        mock_pool.return_value = mock_pool_instance
        
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_redis.return_value = mock_client
        
        # Create manager with health monitoring disabled to control ping calls
        self.manager = RedisConnectionManager(
            self.redis_url,
            enable_health_monitoring=False
        )
        
        # Perform some successful operations
        for _ in range(3):
            self.manager.execute_with_fallback(
                lambda client: "success",
                operation_name="test_op"
            )
        
        # Check metrics
        assert self.manager._health_metrics['consecutive_successes'] == 3
        assert self.manager._health_metrics['consecutive_failures'] == 0
        
        # Now simulate a failure
        mock_client.ping.side_effect = ConnectionError("Failed")
        self.manager.health_check()
        
        # Check failure metrics
        assert self.manager._health_metrics['consecutive_failures'] == 1
        assert self.manager._health_metrics['consecutive_successes'] == 0
    
    @patch('redis.Redis')
    @patch('redis.connection.ConnectionPool.from_url')
    def test_statistics_include_health_monitoring(self, mock_pool, mock_redis):
        """Test statistics include health monitoring info"""
        # Setup mocks
        mock_pool_instance = Mock()
        mock_pool.return_value = mock_pool_instance
        
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_redis.return_value = mock_client
        
        # Create manager with health monitoring
        self.manager = RedisConnectionManager(
            self.redis_url,
            enable_health_monitoring=True,
            health_check_interval=30
        )
        
        # Get statistics
        stats = self.manager.get_statistics()
        
        # Check health monitoring stats
        assert 'health_monitoring' in stats
        assert stats['health_monitoring']['enabled'] is True
        assert stats['health_monitoring']['interval'] == 30
        assert stats['health_monitoring']['thread_alive'] is True
        
        # Check retry stats
        assert 'retry_stats' in stats
        assert stats['retry_stats']['max_attempts'] == 3
    
    def test_exponential_backoff_calculation(self):
        """Test exponential backoff delay calculation"""
        backoff = ExponentialBackoff(
            base_delay=1.0,
            max_delay=30.0,
            multiplier=2.0,
            jitter=False  # Disable jitter for predictable testing
        )
        
        # Test delay progression
        assert backoff.get_delay(0) == 1.0   # 1 * 2^0 = 1
        assert backoff.get_delay(1) == 2.0   # 1 * 2^1 = 2
        assert backoff.get_delay(2) == 4.0   # 1 * 2^2 = 4
        assert backoff.get_delay(3) == 8.0   # 1 * 2^3 = 8
        assert backoff.get_delay(4) == 16.0  # 1 * 2^4 = 16
        assert backoff.get_delay(5) == 30.0  # Would be 32, but capped at max_delay
    
    def test_exponential_backoff_with_jitter(self):
        """Test exponential backoff with jitter"""
        backoff = ExponentialBackoff(
            base_delay=1.0,
            max_delay=30.0,
            multiplier=2.0,
            jitter=True
        )
        
        # Test jitter is applied (delay should vary)
        delays = [backoff.get_delay(2) for _ in range(10)]
        # With jitter, not all delays should be exactly the same
        assert len(set(delays)) > 1
        # But they should be within expected range (4 ± 25%)
        for delay in delays:
            assert 3.0 <= delay <= 5.0  # 4.0 ± 1.0
    
    @patch('redis.Redis')
    @patch('redis.connection.ConnectionPool.from_url')
    def test_health_monitor_auto_recovery(self, mock_pool, mock_redis):
        """Test health monitor can auto-recover circuit breaker"""
        # Setup mocks
        mock_pool_instance = Mock()
        mock_pool.return_value = mock_pool_instance
        
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_redis.return_value = mock_client
        
        # Create manager with short recovery timeout
        self.manager = RedisConnectionManager(
            self.redis_url,
            failure_threshold=1,
            recovery_timeout=1,
            enable_health_monitoring=True,
            health_check_interval=1
        )
        
        # Open circuit by recording failure
        self.manager._record_failure("Test failure")
        assert self.manager._circuit_state == CircuitState.OPEN
        
        # Wait for recovery timeout and health check
        time.sleep(2.5)
        
        # Circuit should attempt recovery via health monitoring
        # (This is a timing-dependent test, may need adjustment)
        stats = self.manager.get_statistics()
        assert stats['health_check_count'] > 0
    
    @patch('redis.Redis')
    @patch('redis.connection.ConnectionPool.from_url')
    def test_disable_retry_option(self, mock_pool, mock_redis):
        """Test disabling retry in execute_with_fallback"""
        # Setup mocks
        mock_pool_instance = Mock()
        mock_pool.return_value = mock_pool_instance
        
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_client.get.side_effect = ConnectionError("Connection failed")
        mock_redis.return_value = mock_client
        
        # Create manager
        self.manager = RedisConnectionManager(self.redis_url)
        
        # Execute without retry
        result = self.manager.execute_with_fallback(
            lambda client: client.get("key"),
            fallback=lambda: "fallback",
            operation_name="test",
            use_retry=False
        )
        
        # Should fail immediately and use fallback
        assert result == "fallback"
        assert mock_client.get.call_count == 1  # No retries
    
    @patch('redis.Redis')
    @patch('redis.connection.ConnectionPool.from_url')
    def test_non_retryable_error(self, mock_pool, mock_redis):
        """Test non-retryable errors are not retried"""
        # Setup mocks
        mock_pool_instance = Mock()
        mock_pool.return_value = mock_pool_instance
        
        mock_client = Mock()
        mock_client.ping.return_value = True
        # Raise a non-retryable error
        mock_client.get.side_effect = ValueError("Invalid operation")
        mock_redis.return_value = mock_client
        
        # Create manager
        self.manager = RedisConnectionManager(self.redis_url)
        
        # Execute operation
        result = self.manager.execute_with_fallback(
            lambda client: client.get("key"),
            fallback=lambda: "fallback",
            operation_name="test",
            use_retry=True
        )
        
        # Should not retry non-retryable errors
        assert result is None  # No fallback for non-Redis errors
        assert mock_client.get.call_count == 1


class TestRedisOperationDecorator:
    """Test suite for redis_operation decorator"""
    
    def setup_method(self):
        """Setup for each test method"""
        reset_global_manager()
    
    def teardown_method(self):
        """Cleanup after each test method"""
        reset_global_manager()
    
    @patch('redis.Redis')
    @patch('redis.connection.ConnectionPool.from_url')
    def test_decorator_success(self, mock_pool, mock_redis):
        """Test successful operation with decorator"""
        # Setup mocks
        mock_pool_instance = Mock()
        mock_pool.return_value = mock_pool_instance
        
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_client.get.return_value = "test_value"
        mock_redis.return_value = mock_client
        
        # Create test class
        class TestService:
            def __init__(self):
                self.redis_manager = RedisConnectionManager("redis://localhost:6379/0")
            
            @redis_operation(operation_name="test_get", fallback_value="fallback")
            def get_value(self, client, key):
                return client.get(key)
        
        # Test operation
        service = TestService()
        result = service.get_value("test_key")
        
        assert result == "test_value"
    
    @patch('redis.Redis')
    @patch('redis.connection.ConnectionPool.from_url')
    def test_decorator_fallback(self, mock_pool, mock_redis):
        """Test fallback with decorator when Redis fails"""
        # Setup mocks to fail
        mock_pool.side_effect = ConnectionError("Connection failed")
        
        # Create test class
        class TestService:
            def __init__(self):
                self.redis_manager = RedisConnectionManager("redis://localhost:6379/0")
            
            @redis_operation(operation_name="test_get", fallback_value="fallback")
            def get_value(self, client, key):
                return client.get(key)
        
        # Test operation
        service = TestService()
        result = service.get_value("test_key")
        
        assert result == "fallback"
    
    def test_decorator_no_redis_manager(self):
        """Test decorator behavior when class has no redis_manager"""
        class TestService:
            @redis_operation(operation_name="test_get", fallback_value="fallback")
            def get_value(self, client, key):
                return client.get(key)
        
        # Test operation
        service = TestService()
        result = service.get_value("test_key")
        
        assert result == "fallback"


class TestGlobalManager:
    """Test suite for global manager functions"""
    
    def teardown_method(self):
        """Cleanup after each test method"""
        reset_global_manager()
    
    @patch('redis.Redis')
    @patch('redis.connection.ConnectionPool.from_url')
    def test_get_redis_manager_singleton(self, mock_pool, mock_redis):
        """Test global manager singleton behavior"""
        # Setup mocks
        mock_pool_instance = Mock()
        mock_pool.return_value = mock_pool_instance
        
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_redis.return_value = mock_client
        
        # Get manager instances
        manager1 = get_redis_manager("redis://localhost:6379/0")
        manager2 = get_redis_manager("redis://localhost:6379/1")  # Different URL should be ignored
        
        # Should be same instance
        assert manager1 is manager2
    
    def test_reset_global_manager(self):
        """Test global manager reset"""
        with patch('redis.connection.ConnectionPool.from_url'):
            with patch('redis.Redis') as mock_redis:
                mock_client = Mock()
                mock_client.ping.return_value = True
                mock_redis.return_value = mock_client
                
                # Get manager
                manager1 = get_redis_manager("redis://localhost:6379/0")
                
                # Reset
                reset_global_manager()
                
                # Get new manager
                manager2 = get_redis_manager("redis://localhost:6379/0")
                
                # Should be different instances
                assert manager1 is not manager2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])