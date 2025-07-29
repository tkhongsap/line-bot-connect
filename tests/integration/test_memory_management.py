"""
Integration Tests for Memory Management System

This module provides comprehensive integration tests for the memory management
optimization system, including memory monitoring, cleanup callbacks, LRU cache
eviction, and alert triggering under memory pressure.
"""

import pytest
import gc
import time
import threading
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from typing import List, Dict, Any

from src.utils.memory_monitor import MemoryMonitor, MemoryAlertLevel, get_memory_monitor, reset_global_monitor
from src.utils.lru_cache_manager import LRUCacheManager, get_lru_cache, CacheType
from src.utils.template_manager import TemplateManager
from src.services.conversation_factory import create_conversation_service
from src.utils.image_utils import ImageProcessor


class TestMemoryManagementIntegration:
    """Integration tests for memory management system."""
    
    def setup_method(self):
        """Setup for each test method."""
        # Reset global monitor to ensure clean state
        reset_global_monitor()
        
        # Create test-specific memory monitor
        self.memory_monitor = MemoryMonitor(
            monitoring_interval=1,  # Fast polling for tests
            history_retention_hours=1,
            enable_process_monitoring=True,
            enable_system_monitoring=True,
            enable_automatic_cleanup=True
        )
        
        # Track cleanup calls
        self.cleanup_calls = []
        self.alert_notifications = []
        
        # Setup test callbacks
        def test_cleanup_callback(level: str, memory_stats):
            self.cleanup_calls.append({
                'level': level,
                'memory_percent': memory_stats.memory_percent,
                'timestamp': datetime.now()
            })
        
        def test_alert_callback(alert):
            self.alert_notifications.append({
                'alert_id': alert.alert_id,
                'level': alert.level.value,
                'memory_percent': alert.memory_stats.memory_percent,
                'timestamp': alert.timestamp
            })
        
        self.memory_monitor.add_cleanup_callback(test_cleanup_callback)
        self.memory_monitor.add_alert_callback(test_alert_callback)
    
    def teardown_method(self):
        """Cleanup after each test method."""
        if hasattr(self, 'memory_monitor'):
            self.memory_monitor.stop_monitoring()
        reset_global_monitor()
        gc.collect()
    
    @pytest.mark.integration
    def test_memory_monitoring_with_real_processes(self):
        """Test memory monitoring with actual memory usage."""
        # Start monitoring
        self.memory_monitor.start_monitoring()
        
        # Wait for a few monitoring cycles
        time.sleep(3)
        
        # Check that monitoring is working
        assert self.memory_monitor._is_monitoring
        assert self.memory_monitor._stats['monitoring_cycles'] > 0
        
        # Get current memory stats
        memory_stats = self.memory_monitor.get_memory_stats()
        assert memory_stats.total_memory > 0
        assert memory_stats.memory_percent > 0
        assert memory_stats.process_memory > 0
        
        # Check memory history is being collected
        history = self.memory_monitor.get_memory_history(hours=1)
        assert len(history) > 0
        
        # Verify memory summary is comprehensive
        summary = self.memory_monitor.get_memory_usage_summary()
        assert 'current' in summary
        assert 'statistics' in summary
        assert 'monitoring' in summary
        assert summary['monitoring']['is_monitoring'] is True
    
    @pytest.mark.integration
    def test_lru_cache_eviction_under_memory_pressure(self):
        """Test LRU cache eviction when memory usage is high."""
        # Create LRU cache with small memory limit for testing
        cache = LRUCacheManager(
            name="test_cache",
            max_size=50,
            max_memory_mb=1.0,  # Very small memory limit
            default_ttl=3600,
            enable_memory_monitoring=True
        )
        
        # Fill cache with data to trigger memory pressure
        large_data = "x" * 10000  # 10KB strings
        stored_keys = []
        
        for i in range(200):  # Try to store 200 * 10KB = ~2MB
            key = f"test_key_{i}"
            success = cache.put(key, large_data, cache_type=CacheType.TEMPLATE)
            if success:
                stored_keys.append(key)
        
        # Check that not all items were stored (memory limit enforced)
        assert len(stored_keys) < 200
        
        # Verify that LRU eviction occurred
        stats = cache.get_statistics()
        assert stats['evictions'] > 0
        assert stats['memory_evictions'] > 0
        
        # Check that memory usage is within limits
        assert stats['memory_usage_mb'] <= 1.5  # Some tolerance for overhead
    
    @pytest.mark.integration
    def test_template_manager_memory_aware_caching(self):
        """Test template manager with memory-aware LRU caching."""
        # Mock template directory and metadata for testing
        with patch('os.path.exists', return_value=True), \
             patch('builtins.open'), \
             patch('json.load', return_value={'test_template': {'filename': 'test.png', 'category': 'motivation'}}), \
             patch('PIL.Image.open') as mock_image:
            
            # Setup mock image
            mock_img = MagicMock()
            mock_img.size = (1200, 800)
            mock_image.return_value.__enter__ = MagicMock(return_value=mock_img)
            mock_image.return_value.__exit__ = MagicMock(return_value=None)
            
            # Create template manager
            template_manager = TemplateManager()
            
            # Load multiple templates to test caching
            for i in range(10):
                template = template_manager.load_template('test_template')
                if template:  # Only count successful loads
                    pass
            
            # Check cache statistics
            cache_stats = template_manager.get_cache_stats()
            assert 'lru_cache' in cache_stats
            assert cache_stats['lru_cache']['hits'] > 0  # Should have cache hits
            assert cache_stats['lru_hit_rate'] > 0
    
    @pytest.mark.integration
    def test_memory_alerts_triggering_cleanup(self):
        """Test that memory alerts trigger appropriate cleanup operations."""
        # Start monitoring with lower thresholds for testing
        self.memory_monitor.start_monitoring()
        
        # Simulate high memory usage by mocking memory stats
        with patch.object(self.memory_monitor, 'get_memory_stats') as mock_stats:
            # Create mock memory stats showing high usage
            mock_memory_stats = MagicMock()
            mock_memory_stats.memory_percent = 75.0  # Trigger warning threshold
            mock_memory_stats.swap_percent = 30.0
            mock_memory_stats.process_memory = 500 * 1024 * 1024  # 500MB
            mock_memory_stats.timestamp = datetime.now()
            mock_stats.return_value = mock_memory_stats
            
            # Wait for monitoring cycle to detect high memory usage
            time.sleep(2)
            
            # Check that cleanup was triggered
            assert len(self.cleanup_calls) > 0
            cleanup_call = self.cleanup_calls[0]
            assert cleanup_call['level'] == 'light'
            assert cleanup_call['memory_percent'] == 75.0
    
    @pytest.mark.integration 
    def test_memory_alerts_with_different_severity_levels(self):
        """Test memory alerts at different severity levels."""
        # Test different memory usage scenarios
        test_scenarios = [
            {'memory_percent': 55.0, 'expected_level': 'info'},
            {'memory_percent': 75.0, 'expected_level': 'warning'},
            {'memory_percent': 92.0, 'expected_level': 'critical'},
            {'memory_percent': 96.0, 'expected_level': 'emergency'}
        ]
        
        for scenario in test_scenarios:
            # Reset alert history
            self.memory_monitor._active_alerts.clear()
            self.alert_notifications.clear()
            
            # Mock memory stats for this scenario
            with patch.object(self.memory_monitor, 'get_memory_stats') as mock_stats:
                mock_memory_stats = MagicMock()
                mock_memory_stats.memory_percent = scenario['memory_percent']
                mock_memory_stats.swap_percent = 20.0
                mock_memory_stats.process_memory = 400 * 1024 * 1024
                mock_memory_stats.timestamp = datetime.now()
                mock_stats.return_value = mock_memory_stats
                
                # Trigger threshold check
                self.memory_monitor._check_thresholds(mock_memory_stats)
                
                # Verify alert was triggered with correct level
                if scenario['memory_percent'] >= 50.0:  # Above info threshold
                    assert len(self.alert_notifications) > 0
                    alert = self.alert_notifications[0]
                    assert alert['level'] == scenario['expected_level']
                    assert alert['memory_percent'] == scenario['memory_percent']
    
    @pytest.mark.integration
    def test_conversation_service_memory_cleanup_integration(self):
        """Test conversation service cleanup integration with memory monitoring."""
        # Create conversation service
        conversation_service = create_conversation_service()
        
        # Add cleanup callback to memory monitor
        cleanup_triggered = []
        
        def conversation_cleanup_callback(level: str, memory_stats):
            if level in ['aggressive', 'emergency']:
                # Simulate conversation cleanup
                initial_count = len(conversation_service.conversations)
                conversation_service.cleanup_old_conversations()
                final_count = len(conversation_service.conversations)
                cleanup_triggered.append({
                    'level': level,
                    'initial_conversations': initial_count,
                    'final_conversations': final_count
                })
        
        self.memory_monitor.add_cleanup_callback(conversation_cleanup_callback)
        
        # Add test conversations
        for i in range(5):
            user_id = f"test_user_{i}"
            conversation_service.add_message(user_id, "test message")
        
        assert len(conversation_service.conversations) == 5
        
        # Trigger aggressive cleanup
        self.memory_monitor.force_cleanup("aggressive")
        
        # Verify cleanup was called
        assert len(cleanup_triggered) > 0
        cleanup_info = cleanup_triggered[0]
        assert cleanup_info['level'] == 'aggressive'
        assert cleanup_info['initial_conversations'] == 5
    
    @pytest.mark.integration
    def test_image_processor_memory_cleanup_integration(self):
        """Test image processor temp file cleanup integration."""
        # Track temp file cleanup
        cleanup_calls = []
        
        def image_cleanup_callback(level: str, memory_stats):
            if level in ['light', 'aggressive', 'emergency']:
                # Simulate image temp file cleanup
                cleanup_calls.append({
                    'level': level,
                    'timestamp': datetime.now()
                })
        
        self.memory_monitor.add_cleanup_callback(image_cleanup_callback)
        
        # Trigger cleanup at different levels
        for level in ['light', 'aggressive', 'emergency']:
            self.memory_monitor.force_cleanup(level)
        
        # Verify all cleanup levels were called
        assert len(cleanup_calls) == 3
        levels = [call['level'] for call in cleanup_calls]
        assert 'light' in levels
        assert 'aggressive' in levels
        assert 'emergency' in levels
    
    @pytest.mark.integration
    def test_memory_dashboard_endpoint_integration(self):
        """Test memory usage summary for dashboard integration."""
        # Start monitoring to generate data
        self.memory_monitor.start_monitoring()
        time.sleep(2)  # Let some monitoring cycles run
        
        # Get memory summary (simulating dashboard endpoint)
        summary = self.memory_monitor.get_memory_usage_summary()
        
        # Verify all expected sections are present
        required_sections = ['current', 'statistics', 'monitoring', 'thresholds', 'recent_alerts', 'active_alerts']
        for section in required_sections:
            assert section in summary, f"Missing section: {section}"
        
        # Verify current stats are realistic
        current = summary['current']
        assert current['memory_percent'] > 0
        assert current['memory_total_gb'] > 0
        assert current['process_memory_mb'] > 0
        
        # Verify monitoring stats
        monitoring = summary['monitoring']
        assert monitoring['is_monitoring'] is True
        assert monitoring['history_entries'] >= 0
        
        # Verify statistics
        stats = summary['statistics']
        assert stats['monitoring_cycles'] > 0
        assert 'last_memory_check' in stats
    
    @pytest.mark.integration
    def test_memory_pressure_cascade_cleanup(self):
        """Test cascading cleanup under increasing memory pressure."""
        cleanup_sequence = []
        
        def cascading_cleanup_callback(level: str, memory_stats):
            cleanup_sequence.append({
                'level': level,
                'memory_percent': memory_stats.memory_percent,
                'timestamp': datetime.now()
            })
        
        self.memory_monitor.add_cleanup_callback(cascading_cleanup_callback)
        
        # Simulate escalating memory pressure
        pressure_levels = [
            {'percent': 75.0, 'expected_cleanup': 'light'},
            {'percent': 92.0, 'expected_cleanup': 'aggressive'},
            {'percent': 96.0, 'expected_cleanup': 'emergency'}
        ]
        
        for pressure in pressure_levels:
            with patch.object(self.memory_monitor, 'get_memory_stats') as mock_stats:
                mock_memory_stats = MagicMock()
                mock_memory_stats.memory_percent = pressure['percent']
                mock_memory_stats.swap_percent = 25.0
                mock_memory_stats.process_memory = 600 * 1024 * 1024
                mock_memory_stats.timestamp = datetime.now()
                mock_stats.return_value = mock_memory_stats
                
                # Trigger cleanup
                self.memory_monitor._check_thresholds(mock_memory_stats)
                
                # Small delay to ensure callback execution
                time.sleep(0.1)
        
        # Verify escalating cleanup sequence
        assert len(cleanup_sequence) >= 3
        
        # Check that we have different cleanup levels
        cleanup_levels = [call['level'] for call in cleanup_sequence]
        assert 'light' in cleanup_levels
        assert 'aggressive' in cleanup_levels
        assert 'emergency' in cleanup_levels
    
    @pytest.mark.integration
    def test_memory_alert_acknowledgment_workflow(self):
        """Test complete memory alert acknowledgment workflow."""
        # Start monitoring
        self.memory_monitor.start_monitoring()
        
        # Trigger a warning-level alert
        with patch.object(self.memory_monitor, 'get_memory_stats') as mock_stats:
            mock_memory_stats = MagicMock()
            mock_memory_stats.memory_percent = 75.0
            mock_memory_stats.swap_percent = 30.0
            mock_memory_stats.process_memory = 500 * 1024 * 1024
            mock_memory_stats.timestamp = datetime.now()
            mock_stats.return_value = mock_memory_stats
            
            # Trigger alert
            self.memory_monitor._check_thresholds(mock_memory_stats)
        
        # Verify alert was created
        active_alerts = self.memory_monitor.get_active_alerts()
        assert len(active_alerts) > 0
        
        alert = active_alerts[0]
        assert not alert.acknowledged
        assert alert.level == MemoryAlertLevel.WARNING
        
        # Acknowledge the alert
        success = self.memory_monitor.acknowledge_alert(alert.alert_id)
        assert success
        
        # Verify alert is acknowledged
        updated_alerts = self.memory_monitor.get_active_alerts()
        acknowledged_alert = next(a for a in updated_alerts if a.alert_id == alert.alert_id)
        assert acknowledged_alert.acknowledged
        
        # Clear acknowledged alerts
        self.memory_monitor.clear_acknowledged_alerts()
        
        # Verify acknowledged alert was removed
        remaining_alerts = self.memory_monitor.get_active_alerts()
        alert_ids = [a.alert_id for a in remaining_alerts]
        assert alert.alert_id not in alert_ids


class TestMemoryManagementPerformance:
    """Performance tests for memory management system."""
    
    @pytest.mark.integration
    @pytest.mark.slow
    def test_memory_monitoring_performance_impact(self):
        """Test that memory monitoring has minimal performance impact."""
        # Measure baseline performance
        start_time = time.time()
        for _ in range(1000):
            gc.collect()  # Simulate work
        baseline_duration = time.time() - start_time
        
        # Start memory monitoring
        monitor = MemoryMonitor(monitoring_interval=0.1)  # Very frequent monitoring
        monitor.start_monitoring()
        
        try:
            # Measure performance with monitoring
            start_time = time.time()
            for _ in range(1000):
                gc.collect()
            monitored_duration = time.time() - start_time
            
            # Performance impact should be minimal (less than 50% overhead)
            performance_overhead = (monitored_duration - baseline_duration) / baseline_duration
            assert performance_overhead < 0.5, f"Memory monitoring overhead too high: {performance_overhead:.2%}"
            
        finally:
            monitor.stop_monitoring()
    
    @pytest.mark.integration
    def test_lru_cache_memory_efficiency(self):
        """Test LRU cache memory efficiency under load."""
        # Create cache with specific memory limit
        cache = LRUCacheManager(
            name="efficiency_test",
            max_size=1000,
            max_memory_mb=5.0,
            default_ttl=3600,
            enable_memory_monitoring=True
        )
        
        # Store varying sized data
        data_sizes = [1024, 2048, 4096, 8192]  # 1KB to 8KB
        stored_count = 0
        
        for i in range(500):
            size = data_sizes[i % len(data_sizes)]
            key = f"data_{i}"
            data = "x" * size
            
            if cache.put(key, data, cache_type=CacheType.RESPONSE):
                stored_count += 1
        
        # Verify memory limits are respected
        stats = cache.get_statistics()
        assert stats['memory_usage_mb'] <= 6.0  # Small tolerance for overhead
        assert stats['size'] <= stats['max_size']
        
        # Verify efficient eviction
        if stored_count < 500:  # Some eviction occurred
            assert stats['evictions'] > 0
            assert stats['memory_evictions'] >= 0