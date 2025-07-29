"""
Unit tests for Memory Alert System
"""

import pytest
import json
import tempfile
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from src.utils.memory_monitor import (
    MemoryAlert, MemoryAlertLevel, MemoryStats, 
    MemoryThreshold, MemoryMonitor, get_memory_monitor
)
from src.utils.memory_alerts import MemoryAlertHandler, create_default_alert_handler, setup_memory_alerting


@pytest.mark.unit
class TestMemoryAlert:
    """Test suite for MemoryAlert dataclass"""
    
    def test_memory_alert_creation(self):
        """Test memory alert creation with all fields"""
        # Create mock memory stats
        memory_stats = MemoryStats(
            total_memory=8*1024**3, available_memory=2*1024**3, used_memory=6*1024**3,
            memory_percent=75.0, swap_total=4*1024**3, swap_used=1*1024**3,
            swap_percent=25.0, process_memory=500*1024**2, process_memory_percent=5.0,
            timestamp=datetime.now()
        )
        
        # Create mock threshold
        threshold = MemoryThreshold(
            level=MemoryAlertLevel.WARNING,
            memory_percent=70.0,
            swap_percent=25.0,
            description="Memory usage is high"
        )
        
        # Create alert
        alert = MemoryAlert(
            alert_id="test_alert_123",
            level=MemoryAlertLevel.WARNING,
            title="Test Alert",
            message="This is a test alert",
            memory_stats=memory_stats,
            threshold=threshold,
            timestamp=datetime.now()
        )
        
        assert alert.alert_id == "test_alert_123"
        assert alert.level == MemoryAlertLevel.WARNING
        assert alert.title == "Test Alert"
        assert alert.message == "This is a test alert"
        assert alert.memory_stats == memory_stats
        assert alert.threshold == threshold
        assert not alert.acknowledged
    
    def test_memory_alert_to_dict(self):
        """Test memory alert serialization to dictionary"""
        memory_stats = MemoryStats(
            total_memory=8*1024**3, available_memory=2*1024**3, used_memory=6*1024**3,
            memory_percent=75.0, swap_total=4*1024**3, swap_used=1*1024**3,
            swap_percent=25.0, process_memory=500*1024**2, process_memory_percent=5.0,
            timestamp=datetime.now()
        )
        
        threshold = MemoryThreshold(
            level=MemoryAlertLevel.CRITICAL,
            memory_percent=90.0,
            swap_percent=50.0,
            description="Critical memory usage"
        )
        
        alert = MemoryAlert(
            alert_id="critical_alert_456",
            level=MemoryAlertLevel.CRITICAL,
            title="Critical Memory Alert",
            message="Memory usage is critical",
            memory_stats=memory_stats,
            threshold=threshold,
            timestamp=datetime.now(),
            acknowledged=True
        )
        
        alert_dict = alert.to_dict()
        
        assert alert_dict['alert_id'] == "critical_alert_456"
        assert alert_dict['level'] == "critical"
        assert alert_dict['title'] == "Critical Memory Alert"
        assert alert_dict['message'] == "Memory usage is critical"
        assert alert_dict['memory_percent'] == 75.0
        assert alert_dict['swap_percent'] == 25.0
        assert alert_dict['process_memory_mb'] == 500.0
        assert alert_dict['threshold_percent'] == 90.0
        assert alert_dict['threshold_description'] == "Critical memory usage"
        assert alert_dict['acknowledged'] is True


@pytest.mark.unit
class TestMemoryMonitorAlerting:
    """Test suite for MemoryMonitor alert functionality"""
    
    def setup_method(self):
        """Setup for each test method"""
        self.monitor = None
    
    def teardown_method(self):
        """Cleanup after each test method"""
        if self.monitor:
            self.monitor.stop_monitoring()
    
    @patch('src.utils.memory_monitor.psutil')
    def test_alert_callback_registration(self, mock_psutil):
        """Test alert callback registration and removal"""
        # Mock psutil
        mock_psutil.virtual_memory.return_value = Mock(
            total=8*1024**3, available=4*1024**3, used=4*1024**3, percent=50.0
        )
        mock_psutil.swap_memory.return_value = Mock(
            total=4*1024**3, used=1*1024**3, percent=25.0
        )
        mock_psutil.Process.return_value.memory_info.return_value = Mock(rss=500*1024**2)
        mock_psutil.Process.return_value.memory_percent.return_value = 5.0
        
        self.monitor = MemoryMonitor(enable_automatic_cleanup=False)
        
        # Test callback registration
        callback = Mock()
        self.monitor.add_alert_callback(callback)
        
        assert callback in self.monitor._alert_callbacks
        
        # Test callback removal
        self.monitor.remove_alert_callback(callback)
        assert callback not in self.monitor._alert_callbacks
    
    @patch('src.utils.memory_monitor.psutil')
    def test_alert_generation_and_cooldown(self, mock_psutil):
        """Test alert generation with cooldown period"""
        # Mock high memory usage
        mock_psutil.virtual_memory.return_value = Mock(
            total=8*1024**3, available=1*1024**3, used=7*1024**3, percent=85.0
        )
        mock_psutil.swap_memory.return_value = Mock(
            total=4*1024**3, used=2*1024**3, percent=50.0
        )
        mock_psutil.Process.return_value.memory_info.return_value = Mock(rss=600*1024**2)
        mock_psutil.Process.return_value.memory_percent.return_value = 7.0
        
        self.monitor = MemoryMonitor(enable_automatic_cleanup=False)
        self.monitor.set_alert_cooldown(1)  # 1 minute cooldown
        
        alert_callback = Mock()
        self.monitor.add_alert_callback(alert_callback)
        
        # Get memory stats and trigger alert check
        memory_stats = self.monitor.get_memory_stats()
        self.monitor._check_thresholds(memory_stats)
        
        # Should trigger WARNING level alert (85% > 70%)
        assert alert_callback.called
        assert len(self.monitor.get_active_alerts()) == 1
        
        # Reset mock and trigger again immediately (should be blocked by cooldown)
        alert_callback.reset_mock()
        self.monitor._check_thresholds(memory_stats)
        assert not alert_callback.called  # Should not be called due to cooldown
    
    @patch('src.utils.memory_monitor.psutil')
    def test_alert_acknowledgment(self, mock_psutil):
        """Test alert acknowledgment functionality"""
        # Mock critical memory usage
        mock_psutil.virtual_memory.return_value = Mock(
            total=8*1024**3, available=500*1024**2, used=7.5*1024**3, percent=95.0
        )
        mock_psutil.swap_memory.return_value = Mock(
            total=4*1024**3, used=3*1024**3, percent=75.0
        )
        mock_psutil.Process.return_value.memory_info.return_value = Mock(rss=800*1024**2)
        mock_psutil.Process.return_value.memory_percent.return_value = 10.0
        
        self.monitor = MemoryMonitor(enable_automatic_cleanup=False)
        
        # Trigger alert
        memory_stats = self.monitor.get_memory_stats()
        self.monitor._check_thresholds(memory_stats)
        
        # Should have active alerts
        active_alerts = self.monitor.get_active_alerts()
        assert len(active_alerts) > 0
        
        # Acknowledge the first alert
        alert_id = active_alerts[0].alert_id
        result = self.monitor.acknowledge_alert(alert_id)
        assert result is True
        
        # Check that alert is acknowledged
        acknowledged_alert = self.monitor._active_alerts[alert_id]
        assert acknowledged_alert.acknowledged is True
        
        # Test acknowledging non-existent alert
        result = self.monitor.acknowledge_alert("non_existent_id")
        assert result is False
    
    @patch('src.utils.memory_monitor.psutil')
    def test_clear_acknowledged_alerts(self, mock_psutil):
        """Test clearing acknowledged alerts"""
        # Mock high memory usage
        mock_psutil.virtual_memory.return_value = Mock(
            total=8*1024**3, available=1*1024**3, used=7*1024**3, percent=85.0
        )
        mock_psutil.swap_memory.return_value = Mock(
            total=4*1024**3, used=2*1024**3, percent=50.0
        )
        mock_psutil.Process.return_value.memory_info.return_value = Mock(rss=600*1024**2)
        mock_psutil.Process.return_value.memory_percent.return_value = 7.0
        
        self.monitor = MemoryMonitor(enable_automatic_cleanup=False)
        
        # Trigger alert
        memory_stats = self.monitor.get_memory_stats()
        self.monitor._check_thresholds(memory_stats)
        
        active_alerts = self.monitor.get_active_alerts()
        assert len(active_alerts) == 1
        
        # Acknowledge the alert
        alert_id = active_alerts[0].alert_id
        self.monitor.acknowledge_alert(alert_id)
        
        # Clear acknowledged alerts
        self.monitor.clear_acknowledged_alerts()
        
        # Should have no active alerts now
        assert len(self.monitor.get_active_alerts()) == 0
    
    @patch('src.utils.memory_monitor.psutil')
    def test_memory_usage_summary_with_alerts(self, mock_psutil):
        """Test memory usage summary includes alert information"""
        # Mock memory usage
        mock_psutil.virtual_memory.return_value = Mock(
            total=8*1024**3, available=2*1024**3, used=6*1024**3, percent=75.0
        )
        mock_psutil.swap_memory.return_value = Mock(
            total=4*1024**3, used=1*1024**3, percent=25.0
        )
        mock_psutil.Process.return_value.memory_info.return_value = Mock(rss=500*1024**2)
        mock_psutil.Process.return_value.memory_percent.return_value = 5.0
        
        self.monitor = MemoryMonitor(enable_automatic_cleanup=False)
        
        # Trigger alert
        memory_stats = self.monitor.get_memory_stats()
        self.monitor._check_thresholds(memory_stats)
        
        # Get summary
        summary = self.monitor.get_memory_usage_summary()
        
        assert 'active_alerts' in summary
        assert 'total_active_alerts' in summary
        assert 'total_acknowledged_alerts' in summary
        assert summary['total_active_alerts'] >= 0


@pytest.mark.unit
class TestMemoryAlertHandler:
    """Test suite for MemoryAlertHandler"""
    
    def setup_method(self):
        """Setup for each test method"""
        self.temp_dir = tempfile.mkdtemp()
        self.handler = None
    
    def teardown_method(self):
        """Cleanup after each test method"""
        if self.temp_dir:
            shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def create_test_alert(self, level: MemoryAlertLevel = MemoryAlertLevel.WARNING) -> MemoryAlert:
        """Helper method to create test alerts"""
        memory_stats = MemoryStats(
            total_memory=8*1024**3, available_memory=2*1024**3, used_memory=6*1024**3,
            memory_percent=75.0, swap_total=4*1024**3, swap_used=1*1024**3,
            swap_percent=25.0, process_memory=500*1024**2, process_memory_percent=5.0,
            timestamp=datetime.now()
        )
        
        threshold = MemoryThreshold(
            level=level,
            memory_percent=70.0,
            swap_percent=25.0,
            description=f"{level.value} memory usage"
        )
        
        return MemoryAlert(
            alert_id=f"test_alert_{level.value}_{int(datetime.now().timestamp())}",
            level=level,
            title=f"Test {level.value.upper()} Alert",
            message=f"This is a test {level.value} alert",
            memory_stats=memory_stats,
            threshold=threshold,
            timestamp=datetime.now()
        )
    
    def test_alert_handler_initialization(self):
        """Test alert handler initialization"""
        self.handler = MemoryAlertHandler(
            enable_file_logging=True,
            alerts_directory=self.temp_dir,
            enable_console_alerts=True,
            critical_alert_file=f"{self.temp_dir}/critical.jsonl"
        )
        
        assert self.handler.enable_file_logging is True
        assert self.handler.enable_console_alerts is True
        assert self.handler.alerts_directory == Path(self.temp_dir)
        assert Path(self.temp_dir).exists()
        
        # Check statistics initialization
        stats = self.handler.get_alert_statistics()
        assert stats['alert_counts']['total'] == 0
        assert stats['file_logging_enabled'] is True
        assert stats['console_alerts_enabled'] is True
    
    def test_handle_warning_alert(self):
        """Test handling warning level alerts"""
        self.handler = MemoryAlertHandler(
            enable_file_logging=True,
            alerts_directory=self.temp_dir,
            enable_console_alerts=False  # Disable to avoid log noise in tests
        )
        
        alert = self.create_test_alert(MemoryAlertLevel.WARNING)
        
        with patch('src.utils.memory_alerts.logger') as mock_logger:
            self.handler.handle_alert(alert)
        
        # Check statistics updated
        stats = self.handler.get_alert_statistics()
        assert stats['alert_counts']['warning'] == 1
        assert stats['alert_counts']['total'] == 1
        
        # Check file was created
        alert_files = list(Path(self.temp_dir).glob("memory_alert_warning_*.json"))
        assert len(alert_files) == 1
        
        # Verify file content
        with open(alert_files[0], 'r') as f:
            saved_data = json.load(f)
        
        assert saved_data['alert_id'] == alert.alert_id
        assert saved_data['level'] == 'warning'
        assert saved_data['handler'] == 'MemoryAlertHandler'
    
    def test_handle_critical_alert(self):
        """Test handling critical level alerts"""
        critical_file = f"{self.temp_dir}/critical.jsonl"
        self.handler = MemoryAlertHandler(
            enable_file_logging=True,
            alerts_directory=self.temp_dir,
            enable_console_alerts=False,
            critical_alert_file=critical_file
        )
        
        alert = self.create_test_alert(MemoryAlertLevel.CRITICAL)
        
        with patch('src.utils.memory_alerts.logger') as mock_logger:
            self.handler.handle_alert(alert)
        
        # Check statistics
        stats = self.handler.get_alert_statistics()
        assert stats['alert_counts']['critical'] == 1
        
        # Check regular alert file
        alert_files = list(Path(self.temp_dir).glob("memory_alert_critical_*.json"))
        assert len(alert_files) == 1
        
        # Check critical alert file
        assert Path(critical_file).exists()
        with open(critical_file, 'r') as f:
            lines = f.readlines()
            assert len(lines) == 1
            critical_data = json.loads(lines[0])
            assert critical_data['alert_id'] == alert.alert_id
            assert critical_data['level'] == 'critical'
    
    def test_handle_emergency_alert(self):
        """Test handling emergency level alerts"""
        self.handler = MemoryAlertHandler(
            enable_file_logging=True,
            alerts_directory=self.temp_dir,
            enable_console_alerts=False
        )
        
        alert = self.create_test_alert(MemoryAlertLevel.EMERGENCY)
        
        with patch('src.utils.memory_alerts.logger') as mock_logger:
            self.handler.handle_alert(alert)
        
        # Check statistics
        stats = self.handler.get_alert_statistics()
        assert stats['alert_counts']['emergency'] == 1
        
        # Check that critical logging was called
        mock_logger.critical.assert_called()
    
    def test_clear_alert_files(self):
        """Test clearing old alert files"""
        self.handler = MemoryAlertHandler(
            enable_file_logging=True,
            alerts_directory=self.temp_dir,
            enable_console_alerts=False
        )
        
        # Create test alerts with different levels to create multiple files
        levels = [MemoryAlertLevel.INFO, MemoryAlertLevel.WARNING, MemoryAlertLevel.CRITICAL]
        for level in levels:
            alert = self.create_test_alert(level)
            self.handler.handle_alert(alert)
        
        # Check files were created
        alert_files = list(Path(self.temp_dir).glob("memory_alert_*.json"))
        assert len(alert_files) == 3
        
        # Modify file times to simulate old files
        old_time = datetime.now().timestamp() - (10 * 24 * 3600)  # 10 days ago
        for alert_file in alert_files[:2]:  # Make 2 files "old"
            import os
            os.utime(alert_file, (old_time, old_time))
        
        # Clear old files (older than 7 days)
        self.handler.clear_alert_files(older_than_days=7)
        
        # Should have only 1 file remaining
        remaining_files = list(Path(self.temp_dir).glob("memory_alert_*.json"))
        assert len(remaining_files) == 1
    
    def test_disabled_file_logging(self):
        """Test handler with file logging disabled"""
        self.handler = MemoryAlertHandler(
            enable_file_logging=False,
            alerts_directory=self.temp_dir,
            enable_console_alerts=False
        )
        
        alert = self.create_test_alert(MemoryAlertLevel.WARNING)
        self.handler.handle_alert(alert)
        
        # Check no files were created
        alert_files = list(Path(self.temp_dir).glob("memory_alert_*.json"))
        assert len(alert_files) == 0
        
        # But statistics should still be updated
        stats = self.handler.get_alert_statistics()
        assert stats['alert_counts']['warning'] == 1


@pytest.mark.unit
class TestMemoryAlertingIntegration:
    """Test suite for memory alerting system integration"""
    
    def test_create_default_alert_handler(self):
        """Test creating default alert handler"""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('src.utils.memory_alerts.MemoryAlertHandler') as mock_handler_class:
                mock_handler = Mock()
                mock_handler_class.return_value = mock_handler
                
                handler = create_default_alert_handler()
                
                # Check that handler was created with correct parameters
                mock_handler_class.assert_called_once_with(
                    enable_file_logging=True,
                    alerts_directory="logs/memory_alerts",
                    enable_console_alerts=True,
                    critical_alert_file="logs/critical_memory_alerts.jsonl"
                )
                
                assert handler == mock_handler
    
    @patch('src.utils.memory_monitor.get_memory_monitor')
    @patch('src.utils.memory_alerts.create_default_alert_handler')
    def test_setup_memory_alerting(self, mock_create_handler, mock_get_monitor):
        """Test setting up memory alerting system"""
        # Mock components
        mock_monitor = Mock()
        mock_monitor._is_monitoring = False
        mock_get_monitor.return_value = mock_monitor
        
        mock_handler = Mock()
        mock_create_handler.return_value = mock_handler
        
        # Setup alerting
        result = setup_memory_alerting()
        
        # Verify calls
        mock_get_monitor.assert_called_once()
        mock_create_handler.assert_called_once()
        mock_monitor.add_alert_callback.assert_called_once_with(mock_handler.handle_alert)
        mock_monitor.start_monitoring.assert_called_once()
        
        assert result == mock_handler
    
    @patch('src.utils.memory_monitor.get_memory_monitor')
    @patch('src.utils.memory_alerts.create_default_alert_handler')
    def test_setup_memory_alerting_already_monitoring(self, mock_create_handler, mock_get_monitor):
        """Test setup when monitoring is already active"""
        # Mock components
        mock_monitor = Mock()
        mock_monitor._is_monitoring = True  # Already monitoring
        mock_get_monitor.return_value = mock_monitor
        
        mock_handler = Mock()
        mock_create_handler.return_value = mock_handler
        
        # Setup alerting
        result = setup_memory_alerting()
        
        # Verify monitoring was not started again
        mock_monitor.start_monitoring.assert_not_called()
        
        assert result == mock_handler
    
    @patch('src.utils.memory_monitor.get_memory_monitor')
    def test_setup_memory_alerting_error_handling(self, mock_get_monitor):
        """Test error handling in setup_memory_alerting"""
        # Mock exception
        mock_get_monitor.side_effect = Exception("Test error")
        
        with patch('src.utils.memory_alerts.logger') as mock_logger:
            result = setup_memory_alerting()
        
        # Should return None on error
        assert result is None
        mock_logger.error.assert_called_once()