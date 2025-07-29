"""
Unit tests for LRU Cache Manager
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

from src.utils.lru_cache_manager import (
    LRUCacheManager,
    CacheEntry,
    CacheType,
    get_lru_cache,
    get_all_caches,
    clear_all_caches,
    get_cache_summary,
    _cache_registry
)
from src.utils.memory_monitor import MemoryStats


@pytest.mark.unit
class TestCacheEntry:
    """Test suite for CacheEntry dataclass"""
    
    def test_cache_entry_creation(self):
        """Test cache entry creation with all fields"""
        entry = CacheEntry(
            key="test_key",
            value={"data": "test"},
            created_at=datetime.now(),
            last_accessed=datetime.now(),
            access_count=1,
            size_bytes=1024,
            ttl_seconds=3600,
            cache_type=CacheType.CONTENT
        )
        
        assert entry.key == "test_key"
        assert entry.value == {"data": "test"}
        assert entry.access_count == 1
        assert entry.size_bytes == 1024
        assert entry.ttl_seconds == 3600
        assert entry.cache_type == CacheType.CONTENT
    
    def test_is_expired_no_ttl(self):
        """Test expiration check when no TTL is set"""
        entry = CacheEntry(
            key="test",
            value="data",
            created_at=datetime.now() - timedelta(hours=48),
            last_accessed=datetime.now(),
            access_count=1,
            size_bytes=100,
            ttl_seconds=None
        )
        
        assert not entry.is_expired()
    
    def test_is_expired_with_ttl(self):
        """Test expiration check with TTL"""
        # Expired entry
        expired_entry = CacheEntry(
            key="expired",
            value="data",
            created_at=datetime.now() - timedelta(seconds=7200),
            last_accessed=datetime.now(),
            access_count=1,
            size_bytes=100,
            ttl_seconds=3600  # 1 hour
        )
        
        assert expired_entry.is_expired()
        
        # Non-expired entry
        fresh_entry = CacheEntry(
            key="fresh",
            value="data",
            created_at=datetime.now() - timedelta(seconds=1800),
            last_accessed=datetime.now(),
            access_count=1,
            size_bytes=100,
            ttl_seconds=3600  # 1 hour
        )
        
        assert not fresh_entry.is_expired()
    
    def test_priority_score_calculation(self):
        """Test priority score calculation for eviction decisions"""
        now = datetime.now()
        
        # High priority entry (recent, frequently accessed, important type)
        high_priority = CacheEntry(
            key="high",
            value="data",
            created_at=now - timedelta(minutes=30),
            last_accessed=now - timedelta(minutes=5),
            access_count=20,
            size_bytes=100,
            cache_type=CacheType.TEMPLATE
        )
        
        # Low priority entry (old, rarely accessed, less important type)
        low_priority = CacheEntry(
            key="low",
            value="data",
            created_at=now - timedelta(hours=10),
            last_accessed=now - timedelta(hours=8),
            access_count=1,
            size_bytes=100,
            cache_type=CacheType.GENERAL
        )
        
        high_score = high_priority.calculate_priority_score()
        low_score = low_priority.calculate_priority_score()
        
        assert high_score > low_score
        assert high_score > 5.0  # Should have decent score
        assert low_score < 2.0   # Should have low score


@pytest.mark.unit
class TestLRUCacheManager:
    """Test suite for LRUCacheManager"""
    
    def setup_method(self):
        """Setup for each test method"""
        self.cache = None
    
    def teardown_method(self):
        """Cleanup after each test method"""
        if self.cache:
            self.cache.clear()
    
    def test_cache_initialization(self):
        """Test cache initialization with default parameters"""
        self.cache = LRUCacheManager(
            name="test_cache",
            max_size=100,
            max_memory_mb=10.0,
            enable_memory_monitoring=False  # Disable for testing
        )
        
        assert self.cache.name == "test_cache"
        assert self.cache.max_size == 100
        assert self.cache.max_memory_bytes == 10 * 1024 * 1024
        assert self.cache.size() == 0
        assert self.cache.memory_usage_mb() == 0.0
    
    def test_basic_put_get_operations(self):
        """Test basic put and get operations"""
        self.cache = LRUCacheManager("test", enable_memory_monitoring=False)
        
        # Test successful put and get
        assert self.cache.put("key1", "value1")
        assert self.cache.get("key1") == "value1"
        assert self.cache.size() == 1
        
        # Test cache miss
        assert self.cache.get("nonexistent") is None
        
        # Test overwrite
        assert self.cache.put("key1", "new_value1")
        assert self.cache.get("key1") == "new_value1"
        assert self.cache.size() == 1
    
    def test_lru_eviction_by_size(self):
        """Test LRU eviction when size limit is reached"""
        self.cache = LRUCacheManager("test", max_size=3, enable_memory_monitoring=False)
        
        # Fill cache to capacity
        self.cache.put("key1", "value1")
        self.cache.put("key2", "value2")
        self.cache.put("key3", "value3")
        assert self.cache.size() == 3
        
        # Add another item, should evict oldest (key1)
        self.cache.put("key4", "value4")
        assert self.cache.size() == 3
        assert self.cache.get("key1") is None  # Should be evicted
        assert self.cache.get("key2") == "value2"
        assert self.cache.get("key3") == "value3"
        assert self.cache.get("key4") == "value4"
    
    def test_lru_order_maintenance(self):
        """Test that LRU order is maintained correctly"""
        self.cache = LRUCacheManager("test", max_size=3, enable_memory_monitoring=False)
        
        # Add items
        self.cache.put("key1", "value1")
        self.cache.put("key2", "value2")
        self.cache.put("key3", "value3")
        
        # Access key1 to make it most recently used
        self.cache.get("key1")
        
        # Add new item, should evict key2 (now least recently used)
        self.cache.put("key4", "value4")
        assert self.cache.get("key1") == "value1"  # Should still be there
        assert self.cache.get("key2") is None      # Should be evicted
        assert self.cache.get("key3") == "value3"  # Should still be there
        assert self.cache.get("key4") == "value4"  # Should be there
    
    def test_ttl_expiration(self):
        """Test TTL-based expiration"""
        self.cache = LRUCacheManager("test", enable_memory_monitoring=False)
        
        # Add item with short TTL
        self.cache.put("key1", "value1", ttl=1)  # 1 second TTL
        assert self.cache.get("key1") == "value1"
        
        # Wait for expiration
        time.sleep(1.1)
        assert self.cache.get("key1") is None  # Should be expired
        assert self.cache.size() == 0
    
    def test_cache_type_prioritization(self):
        """Test that cache types affect eviction priority"""
        self.cache = LRUCacheManager("test", max_size=3, enable_memory_monitoring=False)
        
        # Add items of different types
        self.cache.put("template", "template_data", cache_type=CacheType.TEMPLATE)
        self.cache.put("content", "content_data", cache_type=CacheType.CONTENT)
        self.cache.put("general", "general_data", cache_type=CacheType.GENERAL)
        
        # Access all items to make them equal in recency
        self.cache.get("template")
        self.cache.get("content")
        self.cache.get("general")
        
        # Add new item, should preferentially evict GENERAL type
        self.cache.put("new_item", "new_data", cache_type=CacheType.CONTENT)
        
        # Template should still be there (highest priority)
        assert self.cache.get("template") == "template_data"
        # General might be evicted (lowest priority)
        assert self.cache.get("general") is None or self.cache.get("content") is None
    
    def test_memory_cleanup_callback_integration(self):
        """Test integration with memory monitor cleanup callbacks"""
        # Create cache with larger memory limit to test cleanup levels
        self.cache = LRUCacheManager("test", max_size=10, max_memory_mb=1.0, enable_memory_monitoring=False)
        
        # Add items with some having TTL
        for i in range(5):
            self.cache.put(f"key{i}", f"value{i}", ttl=1 if i < 2 else None)
        
        assert self.cache.size() == 5
        
        # Simulate memory cleanup callback
        mock_stats = MemoryStats(
            total_memory=8*1024**3, available_memory=1*1024**3, used_memory=7*1024**3,
            memory_percent=87.5, swap_total=2*1024**3, swap_used=1*1024**3,
            swap_percent=50.0, process_memory=200*1024**2, process_memory_percent=2.5,
            timestamp=datetime.now()
        )
        
        # Test light cleanup (should remove expired items)
        time.sleep(1.1)  # Let TTL items expire
        self.cache._memory_cleanup_callback("light", mock_stats)
        size_after_light = self.cache.size()
        assert size_after_light == 3  # Should have removed 2 expired items
        
        # Add more items to test memory-based cleanup
        for i in range(5, 10):
            large_value = "x" * 10000  # Large values to fill cache
            self.cache.put(f"key{i}", large_value)
        
        size_before_aggressive = self.cache.size()
        
        # Test aggressive cleanup (should evict for memory)
        self.cache._memory_cleanup_callback("aggressive", mock_stats)
        size_after_aggressive = self.cache.size()
        assert size_after_aggressive <= size_before_aggressive
        
        # Test emergency cleanup (should evict more aggressively)
        self.cache._memory_cleanup_callback("emergency", mock_stats)
        size_after_emergency = self.cache.size()
        assert size_after_emergency <= size_after_aggressive
    
    def test_remove_operation(self):
        """Test explicit remove operation"""
        self.cache = LRUCacheManager("test", enable_memory_monitoring=False)
        
        self.cache.put("key1", "value1")
        assert self.cache.get("key1") == "value1"
        assert self.cache.size() == 1
        
        # Remove item
        assert self.cache.remove("key1") is True
        assert self.cache.get("key1") is None
        assert self.cache.size() == 0
        
        # Remove non-existent item
        assert self.cache.remove("nonexistent") is False
    
    def test_clear_operation(self):
        """Test cache clear operation"""
        self.cache = LRUCacheManager("test", enable_memory_monitoring=False)
        
        # Add multiple items
        for i in range(5):
            self.cache.put(f"key{i}", f"value{i}")
        
        assert self.cache.size() == 5
        
        # Clear cache
        self.cache.clear()
        assert self.cache.size() == 0
        assert self.cache.memory_usage_mb() == 0.0
        
        # Verify all items are gone
        for i in range(5):
            assert self.cache.get(f"key{i}") is None
    
    def test_statistics_collection(self):
        """Test statistics collection and accuracy"""
        self.cache = LRUCacheManager("test", enable_memory_monitoring=False)
        
        # Generate some cache activity
        self.cache.put("key1", "value1")
        self.cache.put("key2", "value2")
        
        # Generate hits and misses
        self.cache.get("key1")  # Hit
        self.cache.get("key1")  # Hit
        self.cache.get("nonexistent")  # Miss
        
        stats = self.cache.get_statistics()
        
        assert stats['cache_name'] == "test"
        assert stats['size'] == 2
        assert stats['total_hits'] == 2
        assert stats['total_misses'] == 1
        assert stats['hit_rate'] == 2/3
        assert 'memory_usage_mb' in stats
        assert 'type_distribution' in stats
    
    def test_health_status(self):
        """Test health status reporting"""
        self.cache = LRUCacheManager("test", max_size=10, max_memory_mb=1.0, enable_memory_monitoring=False)
        
        # Empty cache should be healthy
        health = self.cache.get_health_status()
        assert health['status'] == 'healthy'
        assert health['memory_pressure'] is False
        assert health['size_pressure'] is False
        
        # Fill cache to create pressure
        for i in range(12):  # Exceed max_size
            self.cache.put(f"key{i}", "x" * 1000)  # Large values
        
        health = self.cache.get_health_status()
        # Should show some pressure indicators
        assert 'utilization' in health
        assert health['utilization']['size_percent'] <= 100  # Should be capped by eviction
    
    def test_force_cleanup_operations(self):
        """Test manual cleanup operations"""
        self.cache = LRUCacheManager("test", enable_memory_monitoring=False)
        
        # Add items with different TTLs
        self.cache.put("key1", "value1", ttl=1)  # Will expire
        self.cache.put("key2", "value2", ttl=3600)  # Won't expire
        self.cache.put("key3", "value3")  # No TTL
        
        assert self.cache.size() == 3
        
        # Wait for some items to expire
        time.sleep(1.1)
        
        # Test light cleanup (should remove expired)
        results = self.cache.force_cleanup("light")
        assert results['expired_removed'] >= 1
        assert self.cache.size() == 2
        
        # Test aggressive cleanup
        results = self.cache.force_cleanup("aggressive")
        assert 'memory_evicted' in results
        
        # Test emergency cleanup
        results = self.cache.force_cleanup("emergency")
        assert 'memory_evicted' in results
        assert 'size_evicted' in results


@pytest.mark.unit
class TestGlobalCacheRegistry:
    """Test suite for global cache registry functions"""
    
    def setup_method(self):
        """Setup before each test"""
        # Clear registry to start fresh
        _cache_registry.clear()
    
    def teardown_method(self):
        """Clean up after each test"""
        clear_all_caches()
        # Also clear the registry itself
        _cache_registry.clear()
    
    def test_get_lru_cache_singleton(self):
        """Test that get_lru_cache returns same instance for same name"""
        cache1 = get_lru_cache("test_cache")
        cache2 = get_lru_cache("test_cache")
        
        assert cache1 is cache2
        assert cache1.name == "test_cache"
    
    def test_get_different_caches(self):
        """Test that different names return different cache instances"""
        cache1 = get_lru_cache("cache1")
        cache2 = get_lru_cache("cache2")
        
        assert cache1 is not cache2
        assert cache1.name == "cache1"
        assert cache2.name == "cache2"
    
    def test_get_all_caches(self):
        """Test getting all registered caches"""
        cache1 = get_lru_cache("cache1")
        cache2 = get_lru_cache("cache2")
        
        all_caches = get_all_caches()
        
        assert len(all_caches) == 2
        assert "cache1" in all_caches
        assert "cache2" in all_caches
        assert all_caches["cache1"] is cache1
        assert all_caches["cache2"] is cache2
    
    def test_clear_all_caches(self):
        """Test clearing all registered caches"""
        cache1 = get_lru_cache("cache1")
        cache2 = get_lru_cache("cache2")
        
        # Add data to caches
        cache1.put("key1", "value1")
        cache2.put("key2", "value2")
        
        assert cache1.size() == 1
        assert cache2.size() == 1
        
        # Clear all caches
        clear_all_caches()
        
        assert cache1.size() == 0
        assert cache2.size() == 0
    
    def test_cache_summary(self):
        """Test getting cache summary statistics"""
        cache1 = get_lru_cache("cache1", max_size=10)
        cache2 = get_lru_cache("cache2", max_size=20)
        
        # Add some data
        cache1.put("key1", "value1")
        cache2.put("key2", "value2")
        cache2.put("key3", "value3")
        
        summary = get_cache_summary()
        
        assert summary['total_caches'] == 2
        assert summary['total_entries'] == 3
        assert 'total_memory_mb' in summary
        assert 'caches' in summary
        assert 'cache1' in summary['caches']
        assert 'cache2' in summary['caches']
        assert summary['caches']['cache1']['size'] == 1
        assert summary['caches']['cache2']['size'] == 2


@pytest.mark.unit
class TestMemoryIntegration:
    """Integration tests with memory monitoring"""
    
    def test_memory_monitor_registration(self):
        """Test that cache properly registers with memory monitor"""
        with patch('src.utils.lru_cache_manager.get_memory_monitor') as mock_get_monitor:
            mock_monitor = Mock()
            mock_get_monitor.return_value = mock_monitor
            
            cache = LRUCacheManager("test", enable_memory_monitoring=True)
            
            # Should have called get_memory_monitor and add_cleanup_callback
            mock_get_monitor.assert_called_once()
            mock_monitor.add_cleanup_callback.assert_called_once()
            
            assert cache._memory_monitor_registered is True
    
    def test_memory_size_estimation(self):
        """Test memory size estimation for different value types"""
        cache = LRUCacheManager("test", enable_memory_monitoring=False)
        
        # Test different data types
        test_cases = [
            ("string", "hello world"),
            ("integer", 12345),
            ("float", 123.45),
            ("list", [1, 2, 3, 4, 5]),
            ("dict", {"key1": "value1", "key2": "value2"}),
            ("large_string", "x" * 10000)
        ]
        
        for key, value in test_cases:
            cache.put(key, value)
            estimated_size = cache._estimate_size(value)
            assert estimated_size > 0
            print(f"{key}: estimated {estimated_size} bytes")
        
        # Total memory usage should be reasonable
        total_memory = cache.memory_usage_mb()
        assert total_memory > 0
        assert total_memory < 100  # Should be reasonable for test data
    
    def test_memory_pressure_eviction(self):
        """Test eviction under memory pressure"""
        # Create cache with very small memory limit
        cache = LRUCacheManager("test", max_size=100, max_memory_mb=0.001, enable_memory_monitoring=False)
        
        # Add items until memory limit is hit
        for i in range(10):
            large_value = "x" * 1000  # 1KB per item
            cache.put(f"key{i}", large_value)
        
        # Should have evicted items to stay under memory limit
        assert cache.memory_usage_mb() <= 0.001
        assert cache.size() < 10  # Should have evicted some items