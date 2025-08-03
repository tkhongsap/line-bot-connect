"""
Unit tests for capability cache functionality.

Tests TTL behavior, file operations, in-memory fallback,
cache invalidation, and concurrent access scenarios.
"""

import pytest
import json
import time
from unittest.mock import Mock, patch, mock_open
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import threading

from src.utils.capability_cache import CapabilityCache, get_capability_cache


class TestCapabilityCache:
    """Test suite for capability cache functionality."""
    
    @pytest.fixture
    def temp_cache_file(self):
        """Create temporary cache file for testing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
        yield temp_path
        # Cleanup
        Path(temp_path).unlink(missing_ok=True)
    
    @pytest.fixture
    def cache(self, temp_cache_file):
        """Create capability cache with temporary file."""
        return CapabilityCache(cache_file=temp_cache_file, ttl_seconds=300)

    def test_cache_initialization(self, temp_cache_file):
        """Test cache initialization with different parameters."""
        cache = CapabilityCache(cache_file=temp_cache_file, ttl_seconds=600)
        
        assert cache.cache_file == Path(temp_cache_file)
        assert cache.ttl_seconds == 600
        assert cache._memory_cache == {}

    def test_cache_capabilities_to_file(self, cache, temp_cache_file):
        """Test caching capabilities to file."""
        test_capabilities = {
            'responses_api': True,
            'chat_completions': True,
            'deployment_region': 'eastus',
            'api_version': '2024-02-15-preview'
        }
        
        # Cache the capabilities
        cache.cache_capabilities(test_capabilities)
        
        # Verify file was created and contains correct data
        assert Path(temp_cache_file).exists()
        
        with open(temp_cache_file, 'r') as f:
            cached_data = json.load(f)
        
        assert cached_data['responses_api'] == True
        assert cached_data['chat_completions'] == True
        assert cached_data['deployment_region'] == 'eastus'
        assert 'last_updated' in cached_data
        assert 'ttl_seconds' in cached_data
        assert cached_data['ttl_seconds'] == 300

    def test_get_cached_capabilities_from_file(self, cache, temp_cache_file):
        """Test retrieving cached capabilities from file."""
        # Create test cache data
        test_data = {
            'responses_api': False,
            'chat_completions': True,
            'last_updated': datetime.now().isoformat(),
            'ttl_seconds': 300,
            'deployment_region': 'westus'
        }
        
        # Write to cache file
        with open(temp_cache_file, 'w') as f:
            json.dump(test_data, f)
        
        # Retrieve cached capabilities
        result = cache.get_cached_capabilities()
        
        assert result is not None
        assert result['responses_api'] == False
        assert result['chat_completions'] == True
        assert result['deployment_region'] == 'westus'

    def test_cache_ttl_expiration(self, cache, temp_cache_file):
        """Test TTL expiration behavior."""
        # Create expired cache data
        expired_time = datetime.now() - timedelta(seconds=400)  # Expired by 100 seconds
        test_data = {
            'responses_api': True,
            'chat_completions': True,
            'last_updated': expired_time.isoformat(),
            'ttl_seconds': 300
        }
        
        # Write expired data to cache file
        with open(temp_cache_file, 'w') as f:
            json.dump(test_data, f)
        
        # Should return None for expired cache
        result = cache.get_cached_capabilities()
        assert result is None

    def test_cache_ttl_valid(self, cache, temp_cache_file):
        """Test TTL validation for fresh cache data."""
        # Create fresh cache data
        fresh_time = datetime.now() - timedelta(seconds=100)  # Fresh by 200 seconds
        test_data = {
            'responses_api': True,
            'chat_completions': True,
            'last_updated': fresh_time.isoformat(),
            'ttl_seconds': 300
        }
        
        # Write fresh data to cache file
        with open(temp_cache_file, 'w') as f:
            json.dump(test_data, f)
        
        # Should return valid cache data
        result = cache.get_cached_capabilities()
        assert result is not None
        assert result['responses_api'] == True

    def test_in_memory_fallback_on_file_error(self, temp_cache_file):
        """Test in-memory fallback when file operations fail."""
        cache = CapabilityCache(cache_file=temp_cache_file, ttl_seconds=300)
        
        # Populate in-memory cache first
        test_capabilities = {
            'responses_api': True,
            'chat_completions': False,
            'deployment_region': 'centralus'
        }
        cache.cache_capabilities(test_capabilities)
        
        # Mock file read error
        with patch('builtins.open', side_effect=IOError("File read error")):
            # Should fall back to in-memory cache
            result = cache.get_cached_capabilities()
            
            assert result is not None
            assert result['responses_api'] == True
            assert result['chat_completions'] == False

    def test_cache_invalidation(self, cache, temp_cache_file):
        """Test manual cache invalidation."""
        # Cache some data
        test_capabilities = {
            'responses_api': True,
            'chat_completions': True
        }
        cache.cache_capabilities(test_capabilities)
        
        # Verify data is cached
        result = cache.get_cached_capabilities()
        assert result is not None
        
        # Invalidate cache
        cache.invalidate_cache()
        
        # Cache should be empty
        result = cache.get_cached_capabilities()
        assert result is None
        
        # File should be removed
        assert not Path(temp_cache_file).exists()

    def test_concurrent_cache_access(self, cache):
        """Test concurrent access to cache."""
        results = []
        errors = []
        
        def cache_operation(thread_id):
            try:
                # Each thread caches different data
                capabilities = {
                    'responses_api': thread_id % 2 == 0,
                    'chat_completions': True,
                    'thread_id': thread_id
                }
                cache.cache_capabilities(capabilities)
                
                # Try to read back
                result = cache.get_cached_capabilities()
                results.append(result)
            except Exception as e:
                errors.append(e)
        
        # Launch concurrent operations
        threads = [threading.Thread(target=cache_operation, args=(i,)) for i in range(5)]
        
        for thread in threads:
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Should have no errors
        assert len(errors) == 0
        
        # Should have results from all threads
        assert len(results) == 5

    def test_malformed_cache_file_handling(self, cache, temp_cache_file):
        """Test handling of malformed cache files."""
        # Write malformed JSON to cache file
        with open(temp_cache_file, 'w') as f:
            f.write("{ invalid json content")
        
        # Should handle gracefully and return None
        result = cache.get_cached_capabilities()
        assert result is None

    def test_empty_cache_file_handling(self, cache, temp_cache_file):
        """Test handling of empty cache files."""
        # Create empty cache file
        Path(temp_cache_file).touch()
        
        # Should handle gracefully and return None
        result = cache.get_cached_capabilities()
        assert result is None

    def test_cache_file_permissions_error(self, temp_cache_file):
        """Test handling of file permission errors."""
        cache = CapabilityCache(cache_file=temp_cache_file, ttl_seconds=300)
        
        test_capabilities = {
            'responses_api': True,
            'chat_completions': True
        }
        
        # Mock permission error on file write
        with patch('builtins.open', side_effect=PermissionError("Permission denied")):
            # Should not raise exception, should use in-memory fallback
            cache.cache_capabilities(test_capabilities)
            
            # In-memory cache should still work
            result = cache.get_cached_capabilities()
            assert result is not None

    def test_cache_directory_creation(self):
        """Test automatic cache directory creation."""
        # Use non-existent directory
        cache_path = Path("/tmp/test_cache_dir/capabilities.json")
        
        with patch('pathlib.Path.mkdir') as mock_mkdir:
            with patch('pathlib.Path.exists', return_value=False):
                cache = CapabilityCache(cache_file=str(cache_path), ttl_seconds=300)
                
                test_capabilities = {'responses_api': True}
                cache.cache_capabilities(test_capabilities)
                
                # Directory creation should be attempted
                mock_mkdir.assert_called_once()

    def test_cache_size_limits(self, cache):
        """Test cache behavior with large data."""
        # Create large capability data
        large_capabilities = {
            'responses_api': True,
            'chat_completions': True,
            'large_data': 'x' * 10000,  # 10KB of data
            'deployment_region': 'eastus'
        }
        
        # Should handle large data gracefully
        cache.cache_capabilities(large_capabilities)
        result = cache.get_cached_capabilities()
        
        assert result is not None
        assert len(result['large_data']) == 10000

    def test_get_capability_cache_singleton(self):
        """Test singleton behavior of get_capability_cache."""
        cache1 = get_capability_cache()
        cache2 = get_capability_cache()
        
        # Should return the same instance
        assert cache1 is cache2

    def test_get_capability_cache_with_custom_ttl(self):
        """Test get_capability_cache with custom TTL."""
        cache = get_capability_cache(ttl=600)
        
        assert cache.ttl_seconds == 600

    def test_cache_update_behavior(self, cache, temp_cache_file):
        """Test cache update behavior with new data."""
        # Cache initial data
        initial_data = {
            'responses_api': True,
            'chat_completions': False,
            'deployment_region': 'eastus'
        }
        cache.cache_capabilities(initial_data)
        
        # Verify initial data
        result = cache.get_cached_capabilities()
        assert result['responses_api'] == True
        assert result['chat_completions'] == False
        
        # Update with new data
        updated_data = {
            'responses_api': False,
            'chat_completions': True,
            'deployment_region': 'westus',
            'new_field': 'test_value'
        }
        cache.cache_capabilities(updated_data)
        
        # Verify updated data
        result = cache.get_cached_capabilities()
        assert result['responses_api'] == False
        assert result['chat_completions'] == True
        assert result['deployment_region'] == 'westus'
        assert result['new_field'] == 'test_value'

    def test_cache_timestamp_accuracy(self, cache):
        """Test accuracy of cache timestamps."""
        before_cache = datetime.now()
        
        test_capabilities = {
            'responses_api': True,
            'chat_completions': True
        }
        cache.cache_capabilities(test_capabilities)
        
        after_cache = datetime.now()
        
        result = cache.get_cached_capabilities()
        cached_time = datetime.fromisoformat(result['last_updated'])
        
        # Timestamp should be between before and after
        assert before_cache <= cached_time <= after_cache

    def test_cache_data_integrity(self, cache):
        """Test data integrity in cache operations."""
        original_data = {
            'responses_api': True,
            'chat_completions': False,
            'deployment_region': 'southcentralus',
            'api_version': '2024-02-15-preview',
            'model_capabilities': ['chat', 'embeddings'],
            'quota_info': {'daily_limit': 1000, 'current_usage': 250}
        }
        
        # Cache the data
        cache.cache_capabilities(original_data)
        
        # Retrieve and verify integrity
        retrieved_data = cache.get_cached_capabilities()
        
        # All original fields should be preserved
        for key, value in original_data.items():
            assert retrieved_data[key] == value
        
        # Additional metadata should be present
        assert 'last_updated' in retrieved_data
        assert 'ttl_seconds' in retrieved_data

    def test_cache_performance(self, cache):
        """Test cache operation performance."""
        test_capabilities = {
            'responses_api': True,
            'chat_completions': True,
            'deployment_region': 'eastus'
        }
        
        # Measure cache write performance
        start_time = time.time()
        cache.cache_capabilities(test_capabilities)
        write_time = time.time() - start_time
        
        # Measure cache read performance
        start_time = time.time()
        result = cache.get_cached_capabilities()
        read_time = time.time() - start_time
        
        # Operations should be fast (< 100ms each)
        assert write_time < 0.1
        assert read_time < 0.1
        assert result is not None