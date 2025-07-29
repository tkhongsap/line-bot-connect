"""
Unit tests for enhanced connection pool manager with leak detection and monitoring.
"""

import pytest
import threading
import time
import weakref
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

from src.utils.connection_pool import (
    ConnectionPoolManager, LeakDetector, ResourceMonitor,
    ConnectionState, HealthMetrics, ConnectionLeak,
    ExponentialBackoff, CircuitBreaker, HealthMonitor,
    OptimizedLineBotApi, connection_pool_manager
)


class TestLeakDetector:
    """Test leak detection functionality."""
    
    @pytest.fixture
    def leak_detector(self):
        """Create a leak detector for testing."""
        return LeakDetector(cleanup_interval=1, max_idle_time=2)
    
    def test_leak_detector_initialization(self, leak_detector):
        """Test leak detector initialization."""
        assert leak_detector.cleanup_interval == 1
        assert leak_detector.max_idle_time == 2
        assert leak_detector.tracked_connections == {}
        assert not leak_detector._cleanup_running
    
    def test_register_connection(self, leak_detector):
        """Test connection registration."""
        mock_connection = Mock()
        connection_id = "test_conn_1"
        
        leak_detector.register_connection(connection_id, mock_connection, "test_type")
        
        assert connection_id in leak_detector.tracked_connections
        leak_info = leak_detector.tracked_connections[connection_id]
        assert leak_info.connection_id == connection_id
        assert leak_info.connection_type == "test_type"
        assert leak_info.is_active
        assert isinstance(leak_info.created_at, datetime)
    
    def test_update_connection_usage(self, leak_detector):
        """Test connection usage updates."""
        mock_connection = Mock()
        connection_id = "test_conn_2"
        
        leak_detector.register_connection(connection_id, mock_connection)
        original_time = leak_detector.tracked_connections[connection_id].last_used
        
        time.sleep(0.1)  # Small delay
        leak_detector.update_connection_usage(connection_id)
        
        updated_time = leak_detector.tracked_connections[connection_id].last_used
        assert updated_time > original_time
    
    def test_unregister_connection(self, leak_detector):
        """Test connection unregistration."""
        mock_connection = Mock()
        connection_id = "test_conn_3"
        
        leak_detector.register_connection(connection_id, mock_connection)
        assert leak_detector.tracked_connections[connection_id].is_active
        
        leak_detector.unregister_connection(connection_id)
        assert not leak_detector.tracked_connections[connection_id].is_active
    
    def test_start_stop_cleanup(self, leak_detector):
        """Test cleanup thread lifecycle."""
        leak_detector.start_cleanup()
        assert leak_detector._cleanup_running
        assert leak_detector._cleanup_thread is not None
        
        leak_detector.stop_cleanup()
        assert not leak_detector._cleanup_running
    
    def test_leak_detection(self, leak_detector):
        """Test leak detection functionality."""
        mock_connection = Mock()
        connection_id = "test_conn_4"
        
        # Register connection
        leak_detector.register_connection(connection_id, mock_connection)
        
        # Manually set last_used to simulate idle connection
        leak_info = leak_detector.tracked_connections[connection_id]
        leak_info.last_used = datetime.now() - timedelta(seconds=3)  # Older than max_idle_time
        
        # Run leak detection
        leak_detector._detect_and_cleanup_leaks()
        
        # Verify leak was detected
        assert not leak_info.is_active
        assert leak_detector.cleanup_stats['leaks_detected'] > 0
    
    def test_get_leak_stats(self, leak_detector):
        """Test leak statistics retrieval."""
        # Register some connections
        for i in range(3):
            mock_connection = Mock()
            leak_detector.register_connection(f"test_conn_{i}", mock_connection)
        
        stats = leak_detector.get_leak_stats()
        
        assert 'active_connections' in stats
        assert 'total_connections' in stats
        assert 'avg_connection_age' in stats
        assert stats['active_connections'] == 3
        assert stats['total_connections'] == 3


class TestResourceMonitor:
    """Test resource monitoring functionality."""
    
    @pytest.fixture
    def resource_monitor(self):
        """Create a resource monitor for testing."""
        return ResourceMonitor(monitoring_interval=1)
    
    def test_resource_monitor_initialization(self, resource_monitor):
        """Test resource monitor initialization."""
        assert resource_monitor.monitoring_interval == 1
        assert not resource_monitor._monitoring
        assert resource_monitor._monitor_thread is None
    
    def test_start_stop_monitoring(self, resource_monitor):
        """Test monitoring lifecycle."""
        resource_monitor.start_monitoring()
        assert resource_monitor._monitoring
        assert resource_monitor._monitor_thread is not None
        
        resource_monitor.stop_monitoring()
        assert not resource_monitor._monitoring
    
    @patch('psutil.virtual_memory')
    @patch('psutil.cpu_percent')
    @patch('psutil.Process')
    def test_resource_collection(self, mock_process, mock_cpu, mock_memory, resource_monitor):
        """Test resource metrics collection."""
        # Setup mocks
        mock_memory.return_value = Mock(percent=50.0, available=1000000, used=500000)
        mock_cpu.return_value = 25.0
        
        mock_process_instance = Mock()
        mock_process_instance.memory_info.return_value = Mock(rss=100000, vms=200000)
        mock_process_instance.open_files.return_value = []
        mock_process_instance.connections.return_value = []
        mock_process.return_value = mock_process_instance
        
        # Collect metrics
        resource_monitor._collect_resource_metrics()
        
        # Verify metrics were collected
        assert len(resource_monitor.resource_history) > 0
        assert 'memory_percent' in resource_monitor.resource_history
        assert 'cpu_percent' in resource_monitor.resource_history
    
    def test_get_resource_stats(self, resource_monitor):
        """Test resource statistics retrieval."""
        # Add some test data
        resource_monitor.resource_history['memory_percent'] = [40.0, 50.0, 60.0]
        resource_monitor.resource_history['cpu_percent'] = [10.0, 20.0, 30.0]
        
        stats = resource_monitor.get_resource_stats()
        
        assert 'memory_percent' in stats
        assert 'cpu_percent' in stats
        assert stats['memory_percent']['current'] == 60.0
        assert stats['memory_percent']['avg'] == 50.0
        assert stats['cpu_percent']['max'] == 30.0


class TestEnhancedConnectionPoolManager:
    """Test enhanced connection pool manager."""
    
    @pytest.fixture
    def pool_manager(self):
        """Create a connection pool manager for testing."""
        return ConnectionPoolManager(health_check_interval=1, enable_leak_detection=True)
    
    def test_initialization(self, pool_manager):
        """Test connection pool manager initialization."""
        assert pool_manager.pools == {}
        assert pool_manager.leak_detector is not None
        assert pool_manager.resource_monitor is not None
        assert pool_manager._connection_counter == 0
    
    def test_create_session_with_pooling(self, pool_manager):
        """Test session creation with enhanced pooling."""
        session = pool_manager.create_session_with_pooling(
            name="test_session",
            base_url="https://api.example.com",
            pool_maxsize=10,
            enable_keep_alive=True
        )
        
        assert session is not None
        assert "test_session" in pool_manager.pools
        
        pool_info = pool_manager.pools["test_session"]
        assert pool_info["session"] == session
        assert pool_info["base_url"] == "https://api.example.com"
        assert pool_info["pool_maxsize"] == 10
        assert pool_info["keep_alive"] is True
        assert "connection_id" in pool_info
    
    def test_connection_usage_tracking(self, pool_manager):
        """Test connection usage tracking."""
        session = pool_manager.create_session_with_pooling("test_session")
        
        original_count = pool_manager.pools["test_session"]["request_count"]
        pool_manager.update_connection_usage("test_session")
        
        updated_count = pool_manager.pools["test_session"]["request_count"]
        assert updated_count == original_count + 1
    
    def test_force_cleanup_connection(self, pool_manager):
        """Test force cleanup of specific connection."""
        session = pool_manager.create_session_with_pooling("test_session")
        assert "test_session" in pool_manager.pools
        
        result = pool_manager.force_cleanup_connection("test_session")
        assert result is True
        assert "test_session" not in pool_manager.pools
    
    def test_cleanup_idle_connections(self, pool_manager):
        """Test cleanup of idle connections."""
        # Create some sessions
        pool_manager.create_session_with_pooling("session1")
        pool_manager.create_session_with_pooling("session2")
        
        # Manually set one as old
        pool_manager.pools["session1"]["last_used"] = time.time() - 7200  # 2 hours ago
        
        cleaned_count = pool_manager.cleanup_idle_connections(max_idle_time=3600)  # 1 hour
        
        assert cleaned_count == 1
        assert "session1" not in pool_manager.pools
        assert "session2" in pool_manager.pools
    
    def test_comprehensive_metrics(self, pool_manager):
        """Test comprehensive metrics collection."""
        # Create some sessions
        pool_manager.create_session_with_pooling("session1")
        pool_manager.create_session_with_pooling("session2")
        
        metrics = pool_manager.get_metrics()
        
        assert "pools" in metrics
        assert "health" in metrics
        assert "leak_detection" in metrics
        assert "resources" in metrics
        assert metrics["total_pools"] == 2
        assert "session1" in metrics["pools"]
        assert "session2" in metrics["pools"]
    
    def test_monitoring_lifecycle(self, pool_manager):
        """Test monitoring start/stop lifecycle."""
        pool_manager.start_monitoring()
        
        # Check that all monitors are started
        assert pool_manager.health_monitor._monitoring
        assert pool_manager.leak_detector._cleanup_running
        assert pool_manager.resource_monitor._monitoring
        
        pool_manager.stop_monitoring()
        
        # Check that all monitors are stopped
        assert not pool_manager.health_monitor._monitoring
        assert not pool_manager.leak_detector._cleanup_running
        assert not pool_manager.resource_monitor._monitoring
    
    def test_execute_with_retry_tracking(self, pool_manager):
        """Test retry execution with usage tracking."""
        pool_manager.create_session_with_pooling("test_session")
        original_count = pool_manager.pools["test_session"]["request_count"]
        
        # Mock function that succeeds
        mock_func = Mock(return_value="success")
        
        result = pool_manager.execute_with_retry("test_session", mock_func)
        
        assert result == "success"
        assert pool_manager.pools["test_session"]["request_count"] > original_count
    
    def test_cleanup_pools(self, pool_manager):
        """Test complete pool cleanup."""
        # Create some sessions
        pool_manager.create_session_with_pooling("session1")
        pool_manager.create_session_with_pooling("session2")
        
        # Start monitoring
        pool_manager.start_monitoring()
        
        # Cleanup all pools
        pool_manager.cleanup_pools()
        
        # Verify cleanup
        assert len(pool_manager.pools) == 0
        assert not pool_manager.health_monitor._monitoring
        assert not pool_manager.leak_detector._cleanup_running
        assert not pool_manager.resource_monitor._monitoring


class TestExponentialBackoff:
    """Test exponential backoff functionality."""
    
    def test_exponential_backoff_calculation(self):
        """Test backoff delay calculation."""
        backoff = ExponentialBackoff(base_delay=1.0, max_delay=10.0, multiplier=2.0, jitter=False)
        
        # Test delay progression
        assert backoff.get_delay(0) == 1.0  # 1.0 * 2^0
        assert backoff.get_delay(1) == 2.0  # 1.0 * 2^1
        assert backoff.get_delay(2) == 4.0  # 1.0 * 2^2
        assert backoff.get_delay(3) == 8.0  # 1.0 * 2^3
        assert backoff.get_delay(4) == 10.0  # Capped at max_delay
    
    def test_backoff_with_jitter(self):
        """Test backoff with jitter."""
        backoff = ExponentialBackoff(base_delay=1.0, jitter=True)
        
        # With jitter, delays should vary slightly
        delays = [backoff.get_delay(1) for _ in range(10)]
        
        # All delays should be around 2.0 but with some variation
        assert all(1.5 <= delay <= 2.5 for delay in delays)
        assert len(set(delays)) > 1  # Should have variation


class TestCircuitBreaker:
    """Test circuit breaker functionality."""
    
    def test_circuit_breaker_success(self):
        """Test circuit breaker with successful operations."""
        circuit_breaker = CircuitBreaker(failure_threshold=3)
        mock_func = Mock(return_value="success")
        
        result = circuit_breaker.call(mock_func)
        
        assert result == "success"
        assert circuit_breaker.state == ConnectionState.HEALTHY
        assert circuit_breaker.failure_count == 0
    
    def test_circuit_breaker_failure_threshold(self):
        """Test circuit breaker opening after failures."""
        circuit_breaker = CircuitBreaker(failure_threshold=2)
        mock_func = Mock(side_effect=Exception("Test error"))
        
        # First failure
        with pytest.raises(Exception):
            circuit_breaker.call(mock_func)
        assert circuit_breaker.state == ConnectionState.HEALTHY
        
        # Second failure - should open circuit
        with pytest.raises(Exception):
            circuit_breaker.call(mock_func)
        assert circuit_breaker.state == ConnectionState.CIRCUIT_OPEN
        
        # Third call should fail immediately
        with pytest.raises(ConnectionError, match="Circuit breaker is open"):
            circuit_breaker.call(mock_func)
    
    def test_circuit_breaker_recovery(self):
        """Test circuit breaker recovery after timeout."""
        circuit_breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=1, success_threshold=1)
        
        # Cause failure to open circuit
        mock_func = Mock(side_effect=Exception("Test error"))
        with pytest.raises(Exception):
            circuit_breaker.call(mock_func)
        
        assert circuit_breaker.state == ConnectionState.CIRCUIT_OPEN
        
        # Wait for recovery timeout
        time.sleep(1.1)
        
        # Success should close circuit
        mock_func = Mock(return_value="success")
        result = circuit_breaker.call(mock_func)
        
        assert result == "success"
        assert circuit_breaker.state == ConnectionState.HEALTHY


class TestOptimizedLineBotApi:
    """Test optimized LINE Bot API client."""
    
    @patch('src.utils.connection_pool.LineBotApi.__init__')
    def test_optimized_line_bot_api_initialization(self, mock_super_init):
        """Test optimized LINE Bot API initialization."""
        mock_super_init.return_value = None
        
        # Mock the http_client attribute
        mock_session = Mock()
        mock_http_client = Mock()
        mock_http_client.session = mock_session
        
        api = OptimizedLineBotApi("test_token", timeout=5, pool_maxsize=10)
        api.http_client = mock_http_client
        
        # Manually call the adapter setup since we mocked the parent init
        import requests.adapters
        from urllib3.util.retry import Retry
        
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "POST", "PUT", "DELETE", "OPTIONS", "TRACE"]
        )
        
        adapter = requests.adapters.HTTPAdapter(
            pool_maxsize=10,
            pool_block=False,
            max_retries=retry_strategy
        )
        
        mock_session.mount("https://", adapter)
        mock_session.mount("http://", adapter)
        
        # Verify mounts were called
        assert mock_session.mount.call_count == 2


class TestGlobalConnectionPoolManager:
    """Test global connection pool manager instance."""
    
    def test_global_manager_exists(self):
        """Test that global connection pool manager exists."""
        assert connection_pool_manager is not None
        assert isinstance(connection_pool_manager, ConnectionPoolManager)
        assert connection_pool_manager.leak_detector is not None
    
    def test_global_manager_functionality(self):
        """Test basic functionality of global manager."""
        # Create a session using global manager
        session = connection_pool_manager.create_session_with_pooling("global_test")
        
        assert session is not None
        assert "global_test" in connection_pool_manager.pools
        
        # Clean up
        connection_pool_manager.force_cleanup_connection("global_test")
        assert "global_test" not in connection_pool_manager.pools


if __name__ == "__main__":
    pytest.main([__file__, "-v"])