"""
Unit tests for Memory Monitor utility
"""

import pytest
import time
import threading
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

from src.utils.memory_monitor import (
    MemoryMonitor, 
    MemoryStats, 
    MemoryThreshold, 
    MemoryAlertLevel,
    get_memory_monitor,
    reset_global_monitor
)


@pytest.mark.unit
class TestMemoryMonitor:
    """Test suite for MemoryMonitor"""
    
    def setup_method(self):
        """Setup for each test method"""
        self.monitor = None
        reset_global_monitor()
    
    def teardown_method(self):
        """Cleanup after each test method"""
        if self.monitor:
            self.monitor.stop_monitoring()
        reset_global_monitor()
    
    def test_memory_monitor_initialization(self):
        """Test MemoryMonitor initialization with default settings"""
        self.monitor = MemoryMonitor()
        
        assert self.monitor.monitoring_interval == 30
        assert self.monitor.history_retention_hours == 24
        assert self.monitor.enable_process_monitoring is True
        assert self.monitor.enable_system_monitoring is True
        assert self.monitor.enable_automatic_cleanup is True
        assert len(self.monitor._thresholds) == 4  # Default thresholds
        assert not self.monitor._is_monitoring
    
    def test_memory_monitor_custom_initialization(self):
        """Test MemoryMonitor initialization with custom settings"""
        self.monitor = MemoryMonitor(
            monitoring_interval=60,
            history_retention_hours=48,
            enable_process_monitoring=False,
            enable_automatic_cleanup=False
        )
        
        assert self.monitor.monitoring_interval == 60
        assert self.monitor.history_retention_hours == 48
        assert self.monitor.enable_process_monitoring is False
        assert self.monitor.enable_automatic_cleanup is False
    
    @patch('psutil.virtual_memory')
    @patch('psutil.swap_memory')
    @patch('psutil.Process')
    def test_get_memory_stats(self, mock_process, mock_swap, mock_virtual):
        """Test getting current memory statistics"""
        # Mock system memory
        mock_virtual.return_value = Mock(
            total=8*1024**3,     # 8GB
            available=4*1024**3,  # 4GB
            used=4*1024**3,      # 4GB
            percent=50.0
        )
        
        # Mock swap memory
        mock_swap.return_value = Mock(
            total=2*1024**3,     # 2GB
            used=512*1024**2,    # 512MB
            percent=25.0
        )
        
        # Mock process memory
        mock_process_instance = Mock()
        mock_process_instance.memory_info.return_value = Mock(rss=100*1024**2)  # 100MB
        mock_process_instance.memory_percent.return_value = 1.25
        mock_process.return_value = mock_process_instance
        
        self.monitor = MemoryMonitor()
        stats = self.monitor.get_memory_stats()
        
        assert isinstance(stats, MemoryStats)
        assert stats.total_memory == 8*1024**3
        assert stats.available_memory == 4*1024**3
        assert stats.used_memory == 4*1024**3
        assert stats.memory_percent == 50.0
        assert stats.swap_total == 2*1024**3
        assert stats.swap_used == 512*1024**2
        assert stats.swap_percent == 25.0
        assert stats.process_memory == 100*1024**2
        assert stats.process_memory_percent == 1.25
        assert isinstance(stats.timestamp, datetime)
    
    def test_add_custom_threshold(self):
        """Test adding custom memory thresholds"""
        self.monitor = MemoryMonitor()
        initial_count = len(self.monitor._thresholds)
        
        custom_threshold = MemoryThreshold(
            level=MemoryAlertLevel.WARNING,
            memory_percent=75.0,
            swap_percent=30.0,
            description="Custom threshold"
        )
        
        self.monitor.add_threshold(custom_threshold)
        
        assert len(self.monitor._thresholds) == initial_count + 1
        assert custom_threshold in self.monitor._thresholds
    
    def test_remove_threshold(self):
        """Test removing memory thresholds"""
        self.monitor = MemoryMonitor()
        initial_count = len(self.monitor._thresholds)
        
        self.monitor.remove_threshold(MemoryAlertLevel.WARNING)
        
        assert len(self.monitor._thresholds) == initial_count - 1
        assert not any(t.level == MemoryAlertLevel.WARNING for t in self.monitor._thresholds)
    
    def test_add_cleanup_callback(self):
        """Test adding cleanup callbacks"""
        self.monitor = MemoryMonitor()
        
        callback = Mock()
        self.monitor.add_cleanup_callback(callback)
        
        assert callback in self.monitor._cleanup_callbacks
    
    @patch('psutil.virtual_memory')
    @patch('psutil.swap_memory')
    @patch('psutil.Process')
    def test_threshold_triggering(self, mock_process, mock_swap, mock_virtual):
        """Test that thresholds are triggered correctly"""
        # Mock high memory usage
        mock_virtual.return_value = Mock(
            total=8*1024**3, available=1*1024**3, used=7*1024**3, percent=87.5
        )
        mock_swap.return_value = Mock(total=2*1024**3, used=1*1024**3, percent=50.0)
        mock_process_instance = Mock()
        mock_process_instance.memory_info.return_value = Mock(rss=200*1024**2)
        mock_process_instance.memory_percent.return_value = 2.5
        mock_process.return_value = mock_process_instance
        
        self.monitor = MemoryMonitor(enable_automatic_cleanup=False)
        
        # Mock the cleanup method to track calls
        self.monitor._trigger_light_cleanup = Mock()
        
        # Manually check thresholds
        stats = self.monitor.get_memory_stats()
        self.monitor._check_thresholds(stats)
        
        # Should have triggered an alert
        assert len(self.monitor._alert_history) > 0
        assert self.monitor._stats['alerts_triggered'] > 0
    
    def test_cleanup_callback_execution(self):
        """Test that cleanup callbacks are executed during cleanup"""
        self.monitor = MemoryMonitor()
        
        callback = Mock()
        self.monitor.add_cleanup_callback(callback)
        
        # Create mock memory stats
        mock_stats = MemoryStats(
            total_memory=8*1024**3, available_memory=1*1024**3, used_memory=7*1024**3,
            memory_percent=87.5, swap_total=2*1024**3, swap_used=1*1024**3,
            swap_percent=50.0, process_memory=200*1024**2, process_memory_percent=2.5,
            timestamp=datetime.now()
        )
        
        # Trigger light cleanup
        self.monitor._trigger_light_cleanup(mock_stats, {})
        
        # Verify callback was called
        callback.assert_called_once_with("light", mock_stats)
    
    @patch('gc.collect')
    def test_garbage_collection_during_cleanup(self, mock_gc_collect):
        """Test that garbage collection is triggered during cleanup"""
        self.monitor = MemoryMonitor()
        
        mock_stats = MemoryStats(
            total_memory=8*1024**3, available_memory=1*1024**3, used_memory=7*1024**3,
            memory_percent=87.5, swap_total=2*1024**3, swap_used=1*1024**3,
            swap_percent=50.0, process_memory=200*1024**2, process_memory_percent=2.5,
            timestamp=datetime.now()
        )
        
        self.monitor._trigger_light_cleanup(mock_stats, {})
        
        # Verify garbage collection was called
        mock_gc_collect.assert_called()
    
    @patch('gc.collect')
    def test_aggressive_cleanup(self, mock_gc_collect):
        """Test aggressive cleanup operations"""
        self.monitor = MemoryMonitor()
        
        callback = Mock()
        self.monitor.add_cleanup_callback(callback)
        
        mock_stats = MemoryStats(
            total_memory=8*1024**3, available_memory=1*1024**3, used_memory=7*1024**3,
            memory_percent=92.0, swap_total=2*1024**3, swap_used=1*1024**3,
            swap_percent=60.0, process_memory=200*1024**2, process_memory_percent=2.5,
            timestamp=datetime.now()
        )
        
        self.monitor._trigger_aggressive_cleanup(mock_stats, {})
        
        # Verify aggressive callback was called
        callback.assert_called_with("aggressive", mock_stats)
        
        # Verify multiple GC calls for aggressive cleanup
        assert mock_gc_collect.call_count >= 3
        
        # Verify memory pressure event was recorded
        assert self.monitor._stats['memory_pressure_events'] > 0
    
    def test_emergency_cleanup(self):
        """Test emergency cleanup operations"""
        self.monitor = MemoryMonitor()
        
        callback = Mock()
        self.monitor.add_cleanup_callback(callback)
        
        mock_stats = MemoryStats(
            total_memory=8*1024**3, available_memory=200*1024**2, used_memory=7800*1024**2,
            memory_percent=97.5, swap_total=2*1024**3, swap_used=1800*1024**2,
            swap_percent=90.0, process_memory=300*1024**2, process_memory_percent=3.75,
            timestamp=datetime.now()
        )
        
        # Add some history to test cleanup
        for i in range(50):
            self.monitor._memory_history.append(mock_stats)
            self.monitor._alert_history.append({
                'level': 'test',
                'timestamp': datetime.now().isoformat()
            })
        
        self.monitor._trigger_emergency_cleanup(mock_stats, {})
        
        # Verify emergency callback was called
        callback.assert_called_with("emergency", mock_stats)
        
        # Verify history was trimmed to prevent memory issues
        assert len(self.monitor._memory_history) <= 10
        assert len(self.monitor._alert_history) <= 10
    
    def test_memory_usage_summary(self):
        """Test getting memory usage summary"""
        self.monitor = MemoryMonitor()
        
        # Add some test data
        self.monitor._stats['alerts_triggered'] = 5
        self.monitor._stats['cleanup_operations'] = 2
        
        summary = self.monitor.get_memory_usage_summary()
        
        assert 'current' in summary
        assert 'statistics' in summary
        assert 'monitoring' in summary
        assert 'thresholds' in summary
        assert 'recent_alerts' in summary
        
        assert summary['statistics']['alerts_triggered'] == 5
        assert summary['statistics']['cleanup_operations'] == 2
        assert summary['monitoring']['is_monitoring'] is False
        assert len(summary['thresholds']) == 4  # Default thresholds
    
    def test_memory_history_tracking(self):
        """Test memory history tracking and retrieval"""
        self.monitor = MemoryMonitor()
        
        # Add test history entries
        for i in range(5):
            stats = MemoryStats(
                total_memory=8*1024**3, available_memory=4*1024**3, used_memory=4*1024**3,
                memory_percent=50.0 + i*5, swap_total=2*1024**3, swap_used=500*1024**2,
                swap_percent=25.0, process_memory=100*1024**2, process_memory_percent=1.25,
                timestamp=datetime.now() - timedelta(minutes=i*15)
            )
            self.monitor._add_to_history(stats)
        
        # Get recent history
        history = self.monitor.get_memory_history(hours=2)
        
        assert len(history) == 5
        assert all('timestamp' in entry for entry in history)
        assert all('memory_percent' in entry for entry in history)
    
    def test_history_cleanup(self):
        """Test automatic cleanup of old history entries"""
        self.monitor = MemoryMonitor(history_retention_hours=1)
        
        # Add old entries
        old_stats = MemoryStats(
            total_memory=8*1024**3, available_memory=4*1024**3, used_memory=4*1024**3,
            memory_percent=50.0, swap_total=2*1024**3, swap_used=500*1024**2,
            swap_percent=25.0, process_memory=100*1024**2, process_memory_percent=1.25,
            timestamp=datetime.now() - timedelta(hours=2)  # 2 hours old
        )
        
        # Add recent entries
        recent_stats = MemoryStats(
            total_memory=8*1024**3, available_memory=4*1024**3, used_memory=4*1024**3,
            memory_percent=50.0, swap_total=2*1024**3, swap_used=500*1024**2,
            swap_percent=25.0, process_memory=100*1024**2, process_memory_percent=1.25,
            timestamp=datetime.now() - timedelta(minutes=30)  # 30 minutes old
        )
        
        self.monitor._add_to_history(old_stats)
        self.monitor._add_to_history(recent_stats)
        
        assert len(self.monitor._memory_history) == 2
        
        # Trigger cleanup
        self.monitor._cleanup_history()
        
        # Only recent entry should remain
        assert len(self.monitor._memory_history) == 1
        assert self.monitor._memory_history[0].timestamp == recent_stats.timestamp
    
    def test_force_cleanup(self):
        """Test manual cleanup triggering"""
        self.monitor = MemoryMonitor()
        
        callback = Mock()
        self.monitor.add_cleanup_callback(callback)
        
        # Test light cleanup
        self.monitor.force_cleanup("light")
        callback.assert_called_with("light", self.monitor.get_memory_stats())
        
        # Test aggressive cleanup
        callback.reset_mock()
        self.monitor.force_cleanup("aggressive")
        callback.assert_called_with("aggressive", self.monitor.get_memory_stats())
    
    def test_health_status(self):
        """Test getting health status"""
        self.monitor = MemoryMonitor()
        
        health = self.monitor.get_health_status()
        
        assert health['service'] == 'MemoryMonitor'
        assert 'status' in health
        assert 'is_monitoring' in health
        assert 'current_memory_percent' in health
        assert 'current_swap_percent' in health
        assert 'total_alerts' in health
        assert 'cleanup_operations' in health
        assert 'monitoring_cycles' in health
    
    @patch('threading.Thread')
    def test_start_stop_monitoring(self, mock_thread):
        """Test starting and stopping monitoring"""
        mock_thread_instance = Mock()
        mock_thread.return_value = mock_thread_instance
        
        self.monitor = MemoryMonitor()
        
        assert not self.monitor._is_monitoring
        
        # Start monitoring
        self.monitor.start_monitoring()
        
        assert self.monitor._is_monitoring
        mock_thread.assert_called_once()
        mock_thread_instance.start.assert_called_once()
        
        # Stop monitoring
        self.monitor.stop_monitoring()
        
        assert not self.monitor._is_monitoring
        mock_thread_instance.join.assert_called_once_with(timeout=5)
    
    def test_global_memory_monitor(self):
        """Test global memory monitor singleton"""
        monitor1 = get_memory_monitor()
        monitor2 = get_memory_monitor()
        
        assert monitor1 is monitor2  # Same instance
        assert isinstance(monitor1, MemoryMonitor)
        
        # Cleanup
        reset_global_monitor()
        
        monitor3 = get_memory_monitor()
        assert monitor3 is not monitor1  # New instance after reset
    
    def test_monitoring_with_disabled_features(self):
        """Test monitoring with various features disabled"""
        self.monitor = MemoryMonitor(
            enable_process_monitoring=False,
            enable_system_monitoring=False,
            enable_automatic_cleanup=False
        )
        
        stats = self.monitor.get_memory_stats()
        
        # Process monitoring disabled, so process memory should be 0
        assert stats.process_memory == 0
        assert stats.process_memory_percent == 0.0
    
    def test_threshold_with_process_memory_check(self):
        """Test thresholds that include process memory checks"""
        self.monitor = MemoryMonitor()
        
        # Add threshold with process memory requirement
        process_threshold = MemoryThreshold(
            level=MemoryAlertLevel.WARNING,
            memory_percent=60.0,
            swap_percent=20.0,
            process_memory_mb=150,  # Require 150MB process memory
            description="Process memory threshold"
        )
        
        self.monitor.add_threshold(process_threshold)
        
        # Create stats with high process memory
        stats = MemoryStats(
            total_memory=8*1024**3, available_memory=3*1024**3, used_memory=5*1024**3,
            memory_percent=62.5, swap_total=2*1024**3, swap_used=400*1024**2,
            swap_percent=20.0, process_memory=200*1024**2, process_memory_percent=2.5,
            timestamp=datetime.now()
        )
        
        self.monitor._check_thresholds(stats)
        
        # Should trigger alert because both memory and process memory thresholds are met
        assert len(self.monitor._alert_history) > 0