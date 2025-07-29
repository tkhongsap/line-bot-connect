"""
Unit tests for Image Utils Memory Integration
"""

import pytest
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

from src.utils.image_utils import (
    ImageProcessor,
    _register_memory_cleanup,
    _memory_cleanup_callback,
    _cleanup_old_temp_files,
    _cleanup_excess_temp_files,
    _track_temp_file,
    _untrack_temp_file,
    get_temp_file_stats,
    _global_temp_files,
    _temp_files_lock
)
from src.utils.memory_monitor import MemoryStats


@pytest.mark.unit
class TestImageUtilsMemoryIntegration:
    """Test suite for Image Utils Memory Integration"""
    
    def setup_method(self):
        """Setup for each test method"""
        # Clear global temp files for clean test environment
        with _temp_files_lock:
            _global_temp_files.clear()
    
    def teardown_method(self):
        """Cleanup after each test method"""
        # Clear global temp files
        with _temp_files_lock:
            _global_temp_files.clear()
    
    def test_temp_file_tracking(self):
        """Test temp file tracking functionality"""
        test_path = "/tmp/test_file.jpg"
        
        # Track a temp file
        _track_temp_file(test_path)
        
        # Verify it's tracked
        stats = get_temp_file_stats()
        assert stats['total_tracked'] == 1
        assert stats['memory_monitor_registered'] is False  # Not registered yet
        
        # Untrack the file
        _untrack_temp_file(test_path)
        
        # Verify it's no longer tracked
        stats = get_temp_file_stats()
        assert stats['total_tracked'] == 0
    
    def test_temp_file_stats_empty(self):
        """Test temp file stats when no files are tracked"""
        stats = get_temp_file_stats()
        
        assert stats['total_tracked'] == 0
        assert stats['oldest_file_age_minutes'] == 0
        assert stats['newest_file_age_minutes'] == 0
        assert 'memory_monitor_registered' in stats
    
    def test_temp_file_stats_with_files(self):
        """Test temp file stats with tracked files"""
        # Create some test temp files with different ages
        old_time = datetime.now() - timedelta(minutes=30)
        recent_time = datetime.now() - timedelta(minutes=5)
        
        with _temp_files_lock:
            _global_temp_files.extend([
                {
                    'path': '/tmp/old_file.jpg',
                    'created_at': old_time,
                    'process_id': os.getpid()
                },
                {
                    'path': '/tmp/recent_file.jpg',
                    'created_at': recent_time,
                    'process_id': os.getpid()
                }
            ])
        
        stats = get_temp_file_stats()
        
        assert stats['total_tracked'] == 2
        assert stats['oldest_file_age_minutes'] > 25  # Should be around 30 minutes
        assert stats['newest_file_age_minutes'] < 10  # Should be around 5 minutes
        assert 'average_age_minutes' in stats
    
    @patch('os.path.exists')
    @patch('os.unlink')
    def test_cleanup_old_temp_files(self, mock_unlink, mock_exists):
        """Test cleanup of old temp files"""
        mock_exists.return_value = True
        
        # Create test files with different ages
        old_time = datetime.now() - timedelta(minutes=45)
        recent_time = datetime.now() - timedelta(minutes=10)
        
        with _temp_files_lock:
            _global_temp_files.extend([
                {
                    'path': '/tmp/old_file.jpg',
                    'created_at': old_time,
                    'process_id': os.getpid()
                },
                {
                    'path': '/tmp/recent_file.jpg',
                    'created_at': recent_time,
                    'process_id': os.getpid()
                }
            ])
        
        # Clean up files older than 30 minutes
        _cleanup_old_temp_files(max_age_minutes=30)
        
        # Verify only the old file was removed
        mock_unlink.assert_called_once_with('/tmp/old_file.jpg')
        
        # Verify tracking list is updated
        assert len(_global_temp_files) == 1
        assert _global_temp_files[0]['path'] == '/tmp/recent_file.jpg'
    
    @patch('os.path.exists')
    @patch('os.unlink')
    def test_cleanup_excess_temp_files(self, mock_unlink, mock_exists):
        """Test cleanup of excess temp files"""
        mock_exists.return_value = True
        
        # Create more files than the limit
        base_time = datetime.now()
        with _temp_files_lock:
            for i in range(25):
                _global_temp_files.append({
                    'path': f'/tmp/file_{i}.jpg',
                    'created_at': base_time - timedelta(minutes=i),
                    'process_id': os.getpid()
                })
        
        # Clean up excess files (keep only 20)
        _cleanup_excess_temp_files(max_files=20)
        
        # Verify excess files were removed (oldest 5)
        assert mock_unlink.call_count == 5
        
        # Verify tracking list size
        assert len(_global_temp_files) == 20
    
    def test_memory_cleanup_callback(self):
        """Test memory cleanup callback with different levels"""
        # Create some test temp files
        with _temp_files_lock:
            for i in range(5):
                _global_temp_files.append({
                    'path': f'/tmp/test_file_{i}.jpg',
                    'created_at': datetime.now() - timedelta(minutes=40),
                    'process_id': os.getpid()
                })
        
        mock_stats = MemoryStats(
            total_memory=8*1024**3, available_memory=1*1024**3, used_memory=7*1024**3,
            memory_percent=87.5, swap_total=2*1024**3, swap_used=1*1024**3,
            swap_percent=50.0, process_memory=200*1024**2, process_memory_percent=2.5,
            timestamp=datetime.now()
        )
        
        # Test light cleanup (should clean files older than 30 minutes)
        with patch('src.utils.image_utils._cleanup_old_temp_files') as mock_cleanup_old:
            _memory_cleanup_callback("light", mock_stats)
            mock_cleanup_old.assert_called_once_with(max_age_minutes=30)
        
        # Test aggressive cleanup
        with patch('src.utils.image_utils._cleanup_old_temp_files') as mock_cleanup_old:
            _memory_cleanup_callback("aggressive", mock_stats)
            mock_cleanup_old.assert_called_once_with(max_age_minutes=15)
        
        # Test emergency cleanup
        with patch('src.utils.image_utils._cleanup_old_temp_files') as mock_cleanup_old, \
             patch('src.utils.image_utils._cleanup_excess_temp_files') as mock_cleanup_excess:
            _memory_cleanup_callback("emergency", mock_stats)
            mock_cleanup_old.assert_called_once_with(max_age_minutes=5)
            mock_cleanup_excess.assert_called_once_with(max_files=20)
    
    @patch('src.utils.image_utils.get_memory_monitor')
    def test_register_memory_cleanup(self, mock_get_monitor):
        """Test memory cleanup registration"""
        mock_monitor = Mock()
        mock_get_monitor.return_value = mock_monitor
        
        # Reset registration state
        import src.utils.image_utils
        src.utils.image_utils._memory_monitor_registered = False
        
        # Register cleanup
        _register_memory_cleanup()
        
        # Verify monitor callback was added
        mock_monitor.add_cleanup_callback.assert_called_once()
        
        # Verify global state is updated
        assert src.utils.image_utils._memory_monitor_registered is True
    
    def test_image_processor_temp_file_integration(self):
        """Test ImageProcessor integration with temp file tracking"""
        processor = ImageProcessor()
        
        # Mock the temp file creation
        with patch('tempfile.mkstemp') as mock_mkstemp, \
             patch('os.fdopen') as mock_fdopen:
            
            mock_mkstemp.return_value = (123, '/tmp/test_image.jpg')
            mock_file = Mock()
            mock_fdopen.return_value.__enter__.return_value = mock_file
            
            # Create a temp file
            temp_path = processor._create_temp_file(b'test_data', 'JPEG')
            
            # Verify it's tracked both locally and globally
            assert temp_path in processor.temp_files
            
            # Verify global tracking
            stats = get_temp_file_stats()
            assert stats['total_tracked'] == 1
            
            # Cleanup should remove from both tracking systems
            with patch('os.path.exists', return_value=True), \
                 patch('os.unlink') as mock_unlink:
                
                processor.cleanup_temp_files()
                
                # Verify file was deleted
                mock_unlink.assert_called_once_with('/tmp/test_image.jpg')
                
                # Verify it's removed from global tracking
                stats = get_temp_file_stats()
                assert stats['total_tracked'] == 0
    
    def test_max_temp_files_limit(self):
        """Test that temp file tracking respects maximum limits"""
        # Track more files than the maximum
        import src.utils.image_utils
        original_max = src.utils.image_utils._max_temp_files
        src.utils.image_utils._max_temp_files = 10  # Set low limit for testing
        
        try:
            # Track more files than the limit
            for i in range(15):
                _track_temp_file(f'/tmp/file_{i}.jpg')
            
            # Verify only the maximum are tracked
            stats = get_temp_file_stats()
            assert stats['total_tracked'] == 10
            
        finally:
            # Restore original limit
            src.utils.image_utils._max_temp_files = original_max