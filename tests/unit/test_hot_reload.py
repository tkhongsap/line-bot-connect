"""
Unit tests for configuration hot reload functionality.

This module tests the hot reload system that allows configuration changes
to be applied without restarting the application.
"""

import os
import time
import tempfile
import json
from unittest.mock import patch, MagicMock
import pytest
from pathlib import Path

from src.config.hot_reload import (
    ConfigurationHotReloader,
    get_hot_reloader,
    start_hot_reload,
    stop_hot_reload,
    add_reload_callback,
    remove_reload_callback,
    trigger_reload,
    get_reload_status,
    get_change_log,
    HotReloadPause,
    reload_on_config_change
)


class TestConfigurationHotReloader:
    """Test the ConfigurationHotReloader class."""
    
    def setup_method(self):
        """Set up test environment."""
        # Clear global instances
        import src.config.hot_reload
        src.config.hot_reload._hot_reloader = None
        
        # Create temporary test environment
        self.test_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.test_dir, '.env')
        
        # Create initial config file
        with open(self.config_file, 'w') as f:
            f.write('TEST_VALUE=initial\n')
    
    def teardown_method(self):
        """Clean up test environment."""
        # Clean up temporary files
        if os.path.exists(self.config_file):
            os.remove(self.config_file)
        if os.path.exists(self.test_dir):
            os.rmdir(self.test_dir)
        
        # Stop any running hot reloader
        try:
            stop_hot_reload()
        except:
            pass
    
    def test_hot_reloader_initialization(self):
        """Test ConfigurationHotReloader initialization."""
        reloader = ConfigurationHotReloader()
        
        assert not reloader.is_running
        assert not reloader.is_active()
        assert len(reloader.config_files) > 0
        assert len(reloader.watch_directories) > 0
        assert len(reloader.reload_callbacks) == 0
        assert len(reloader.change_log) == 0
    
    def test_callback_management(self):
        """Test adding and removing reload callbacks."""
        reloader = ConfigurationHotReloader()
        
        # Test callback
        callback_called = []
        def test_callback():
            callback_called.append(True)
        
        # Add callback
        reloader.add_reload_callback(test_callback)
        assert len(reloader.reload_callbacks) == 1
        
        # Remove callback
        reloader.remove_reload_callback(test_callback)
        assert len(reloader.reload_callbacks) == 0
        
        # Add callback again for further testing
        reloader.add_reload_callback(test_callback)
        
        # Trigger manual reload to test callback execution
        with patch('src.config.hot_reload.reload_config') as mock_reload:
            mock_config = MagicMock()
            mock_config.config_version = "test_version"
            mock_reload.return_value = mock_config
            
            reloader.trigger_reload()
            
            # Check callback was called
            assert len(callback_called) == 1
            assert len(reloader.change_log) == 1
            assert reloader.change_log[0]['success'] is True
    
    def test_manual_reload_trigger(self):
        """Test manual configuration reload triggering."""
        reloader = ConfigurationHotReloader()
        
        with patch('src.config.hot_reload.reload_config') as mock_reload:
            mock_config = MagicMock()
            mock_config.config_version = "manual_test_version"
            mock_reload.return_value = mock_config
            
            reloader.trigger_reload()
            
            # Verify reload was called
            mock_reload.assert_called_once()
            
            # Check change log
            assert len(reloader.change_log) == 1
            change_entry = reloader.change_log[0]
            assert change_entry['event'] == 'configuration_reloaded'
            assert change_entry['success'] is True
            assert change_entry['config_version'] == 'manual_test_version'
    
    def test_reload_failure_handling(self):
        """Test handling of configuration reload failures."""
        reloader = ConfigurationHotReloader()
        
        with patch('src.config.hot_reload.reload_config') as mock_reload:
            mock_reload.side_effect = Exception("Test reload failure")
            
            reloader.trigger_reload()
            
            # Check failure was logged
            assert len(reloader.change_log) == 1
            change_entry = reloader.change_log[0]
            assert change_entry['event'] == 'configuration_reload_failed'
            assert change_entry['success'] is False
            assert 'Test reload failure' in change_entry['error']
    
    def test_change_log_management(self):
        """Test configuration change log management."""
        reloader = ConfigurationHotReloader()
        
        # Test change log limit
        reloader.max_log_entries = 3
        
        with patch('src.config.hot_reload.reload_config') as mock_reload:
            mock_config = MagicMock()
            mock_config.config_version = "test_version"
            mock_reload.return_value = mock_config
            
            # Trigger multiple reloads
            for i in range(5):
                reloader.trigger_reload()
            
            # Check log is limited
            assert len(reloader.change_log) == 3
        
        # Test log clearing
        reloader.clear_change_log()
        assert len(reloader.change_log) == 0
    
    def test_watch_file_management(self):
        """Test adding and removing files from watch list."""
        reloader = ConfigurationHotReloader()
        initial_count = len(reloader.config_files)
        
        # Add new file
        reloader.add_watch_file('custom_config.json')
        assert len(reloader.config_files) == initial_count + 1
        assert 'custom_config.json' in reloader.config_files
        
        # Remove file
        reloader.remove_watch_file('custom_config.json')
        assert len(reloader.config_files) == initial_count
        assert 'custom_config.json' not in reloader.config_files
    
    def test_status_reporting(self):
        """Test hot reloader status reporting."""
        reloader = ConfigurationHotReloader()
        
        status = reloader.get_status()
        
        # Check status structure
        required_keys = [
            'is_running', 'is_active', 'watched_files',
            'watched_directories', 'change_log_entries', 'callbacks_registered'
        ]
        
        for key in required_keys:
            assert key in status
        
        # Check initial values
        assert status['is_running'] is False
        assert status['is_active'] is False
        assert isinstance(status['watched_files'], list)
        assert isinstance(status['watched_directories'], list)
        assert status['change_log_entries'] == 0
        assert status['callbacks_registered'] == 0


class TestHotReloadGlobalFunctions:
    """Test global hot reload functions."""
    
    def setup_method(self):
        """Set up test environment."""
        # Clear global instances
        import src.config.hot_reload
        src.config.hot_reload._hot_reloader = None
    
    def teardown_method(self):
        """Clean up test environment."""
        try:
            stop_hot_reload()
        except:
            pass
    
    def test_get_hot_reloader_singleton(self):
        """Test that get_hot_reloader returns the same instance."""
        reloader1 = get_hot_reloader()
        reloader2 = get_hot_reloader()
        
        assert reloader1 is reloader2
        assert isinstance(reloader1, ConfigurationHotReloader)
    
    def test_global_callback_management(self):
        """Test global callback management functions."""
        callback_called = []
        
        def test_callback():
            callback_called.append(True)
        
        # Add callback
        add_reload_callback(test_callback)
        
        # Trigger reload to test callback
        with patch('src.config.hot_reload.reload_config') as mock_reload:
            mock_config = MagicMock()
            mock_config.config_version = "test_version"
            mock_reload.return_value = mock_config
            
            trigger_reload()
            
            assert len(callback_called) == 1
        
        # Remove callback
        remove_reload_callback(test_callback)
        
        # Trigger again - callback should not be called
        callback_called.clear()
        with patch('src.config.hot_reload.reload_config') as mock_reload:
            mock_config = MagicMock()
            mock_config.config_version = "test_version"
            mock_reload.return_value = mock_config
            
            trigger_reload()
            
            assert len(callback_called) == 0
    
    @patch('src.config.hot_reload.Observer')
    def test_start_stop_hot_reload(self, mock_observer):
        """Test starting and stopping hot reload."""
        mock_observer_instance = MagicMock()
        mock_observer.return_value = mock_observer_instance
        
        # Test start
        start_hot_reload()
        
        status = get_reload_status()
        assert status['is_running'] is True
        
        # Test stop
        stop_hot_reload()
        
        status = get_reload_status()
        assert status['is_running'] is False
    
    def test_get_reload_status(self):
        """Test getting reload status."""
        status = get_reload_status()
        
        assert isinstance(status, dict)
        assert 'is_running' in status
        assert 'is_active' in status
    
    def test_get_change_log(self):
        """Test getting change log."""
        # Trigger a reload to create log entry
        with patch('src.config.hot_reload.reload_config') as mock_reload:
            mock_config = MagicMock()
            mock_config.config_version = "test_version"
            mock_reload.return_value = mock_config
            
            trigger_reload()
        
        log = get_change_log()
        assert isinstance(log, list)
        assert len(log) > 0


class TestHotReloadPause:
    """Test the HotReloadPause context manager."""
    
    def setup_method(self):
        """Set up test environment."""
        import src.config.hot_reload
        src.config.hot_reload._hot_reloader = None
    
    def teardown_method(self):
        """Clean up test environment."""
        try:
            stop_hot_reload()
        except:
            pass
    
    @patch('src.config.hot_reload.Observer')
    def test_pause_context_manager(self, mock_observer):
        """Test HotReloadPause context manager."""
        mock_observer_instance = MagicMock()
        mock_observer.return_value = mock_observer_instance
        
        # Start hot reload
        start_hot_reload()
        assert get_reload_status()['is_running'] is True
        
        # Test pause
        with HotReloadPause():
            status = get_reload_status()
            assert status['is_running'] is False
        
        # After pause, should be running again
        status = get_reload_status()
        assert status['is_running'] is True
    
    @patch('src.config.hot_reload.Observer')
    def test_pause_when_not_running(self, mock_observer):
        """Test HotReloadPause when hot reload is not running."""
        # Ensure hot reload is not running
        stop_hot_reload()
        assert get_reload_status()['is_running'] is False
        
        # Test pause - should not start it
        with HotReloadPause():
            status = get_reload_status()
            assert status['is_running'] is False
        
        # After pause, should still not be running
        status = get_reload_status()
        assert status['is_running'] is False


class TestReloadDecorator:
    """Test the reload_on_config_change decorator."""
    
    def setup_method(self):
        """Set up test environment."""
        import src.config.hot_reload
        src.config.hot_reload._hot_reloader = None
    
    def teardown_method(self):
        """Clean up test environment."""
        try:
            stop_hot_reload()
        except:
            pass
    
    def test_reload_decorator(self):
        """Test the reload_on_config_change decorator."""
        call_count = []
        
        @reload_on_config_change
        def decorated_function():
            call_count.append(True)
            return "test_result"
        
        # Call decorated function
        result = decorated_function()
        assert result == "test_result"
        assert len(call_count) == 1
        
        # Check that callback was registered
        reloader = get_hot_reloader()
        assert len(reloader.reload_callbacks) == 1
        
        # Trigger reload to test callback
        with patch('src.config.hot_reload.reload_config') as mock_reload:
            mock_config = MagicMock()
            mock_config.config_version = "test_version"
            mock_reload.return_value = mock_config
            
            trigger_reload()
            
            # Function should have been called again via callback
            assert len(call_count) == 2


class TestConfigurationChangeHandler:
    """Test the ConfigurationChangeHandler class."""
    
    def test_handler_initialization(self):
        """Test ConfigurationChangeHandler initialization."""
        from src.config.hot_reload import ConfigurationChangeHandler
        
        callback_called = []
        def test_callback():
            callback_called.append(True)
        
        handler = ConfigurationChangeHandler(test_callback, ['.env', 'config.json'])
        
        assert handler.reload_callback == test_callback
        assert '.env' in handler.config_files
        assert 'config.json' in handler.config_files
        assert handler.reload_cooldown == 2.0
    
    def test_file_change_detection(self):
        """Test file change detection and callback triggering."""
        from src.config.hot_reload import ConfigurationChangeHandler
        from watchdog.events import FileModifiedEvent
        
        callback_called = []
        def test_callback():
            callback_called.append(True)
        
        handler = ConfigurationChangeHandler(test_callback, ['.env'])
        
        # Create a file modification event
        event = FileModifiedEvent('/path/to/.env')
        
        # Process the event
        handler.on_modified(event)
        
        # Check callback was called
        assert len(callback_called) == 1
    
    def test_cooldown_behavior(self):
        """Test cooldown behavior to prevent rapid reloads."""
        from src.config.hot_reload import ConfigurationChangeHandler
        from watchdog.events import FileModifiedEvent
        
        callback_called = []
        def test_callback():
            callback_called.append(True)
        
        handler = ConfigurationChangeHandler(test_callback, ['.env'])
        handler.reload_cooldown = 0.1  # Short cooldown for testing
        
        event = FileModifiedEvent('/path/to/.env')
        
        # First call should work
        handler.on_modified(event)
        assert len(callback_called) == 1
        
        # Immediate second call should be ignored
        handler.on_modified(event)
        assert len(callback_called) == 1
        
        # After cooldown, should work again
        time.sleep(0.2)
        handler.on_modified(event)
        assert len(callback_called) == 2
    
    def test_directory_events_ignored(self):
        """Test that directory events are ignored."""
        from src.config.hot_reload import ConfigurationChangeHandler
        from watchdog.events import DirModifiedEvent
        
        callback_called = []
        def test_callback():
            callback_called.append(True)
        
        handler = ConfigurationChangeHandler(test_callback, ['.env'])
        
        # Create a directory modification event
        event = DirModifiedEvent('/path/to/directory')
        
        # Process the event
        handler.on_modified(event)
        
        # Check callback was not called
        assert len(callback_called) == 0