"""
LRU Cache Manager with Memory-Aware Eviction

This module provides a comprehensive LRU (Least Recently Used) cache implementation
with memory monitoring integration for Rich Message template and content caching.
"""

import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple, Union, Callable
from collections import OrderedDict
from dataclasses import dataclass
from enum import Enum
import sys

from src.utils.memory_monitor import get_memory_monitor, MemoryStats

logger = logging.getLogger(__name__)


class CacheType(Enum):
    """Types of caches for different use cases"""
    CONTENT = "content"
    TEMPLATE = "template" 
    MOOD = "mood"
    IMAGE = "image"
    GENERAL = "general"


@dataclass
class CacheEntry:
    """Entry in the LRU cache with metadata"""
    key: str
    value: Any
    created_at: datetime
    last_accessed: datetime
    access_count: int
    size_bytes: int
    ttl_seconds: Optional[int] = None
    cache_type: CacheType = CacheType.GENERAL
    
    def is_expired(self) -> bool:
        """Check if the entry has expired based on TTL"""
        if self.ttl_seconds is None:
            return False
        return (datetime.now() - self.created_at).total_seconds() > self.ttl_seconds
    
    def calculate_priority_score(self) -> float:
        """Calculate priority score for eviction decisions"""
        # Higher score = higher priority to keep
        age_hours = (datetime.now() - self.created_at).total_seconds() / 3600
        time_since_access = (datetime.now() - self.last_accessed).total_seconds() / 3600
        
        # Base score from access frequency
        frequency_score = min(self.access_count / max(age_hours, 0.1), 10.0)
        
        # Recency bonus (recently accessed items get higher scores)
        recency_score = max(0, 5.0 - time_since_access)
        
        # Type-based priority (templates are more expensive to recreate)
        type_priority = {
            CacheType.TEMPLATE: 3.0,
            CacheType.CONTENT: 2.0,
            CacheType.IMAGE: 1.5,
            CacheType.MOOD: 1.0,
            CacheType.GENERAL: 0.5
        }
        
        return frequency_score + recency_score + type_priority.get(self.cache_type, 0.5)


class LRUCacheManager:
    """
    Memory-aware LRU cache with intelligent eviction strategies.
    
    Features:
    - Least Recently Used eviction policy
    - Memory pressure-based cleanup
    - TTL (Time To Live) support
    - Multi-level eviction strategies
    - Cache type-based prioritization
    - Statistics and monitoring
    """
    
    def __init__(self, 
                 name: str,
                 max_size: int = 1000,
                 max_memory_mb: float = 100.0,
                 default_ttl: Optional[int] = None,
                 enable_memory_monitoring: bool = True):
        """
        Initialize LRU cache manager.
        
        Args:
            name: Name identifier for this cache instance
            max_size: Maximum number of entries
            max_memory_mb: Maximum memory usage in MB
            default_ttl: Default TTL in seconds (None = no expiration)
            enable_memory_monitoring: Whether to integrate with memory monitor
        """
        self.name = name
        self.max_size = max_size
        self.max_memory_bytes = int(max_memory_mb * 1024 * 1024)
        self.default_ttl = default_ttl
        self.enable_memory_monitoring = enable_memory_monitoring
        
        # Thread-safe ordered dictionary for LRU implementation
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.RLock()
        
        # Statistics
        self._stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'memory_cleanups': 0,
            'expired_cleanups': 0,
            'total_size_bytes': 0,
            'created_at': datetime.now()
        }
        
        # Memory monitoring integration
        self.memory_monitor = None
        self._memory_monitor_registered = False
        
        if self.enable_memory_monitoring:
            self._register_memory_monitoring()
        
        logger.info(f"LRUCacheManager '{name}' initialized: max_size={max_size}, max_memory={max_memory_mb}MB")
    
    def _register_memory_monitoring(self):
        """Register with the global memory monitor for cleanup callbacks."""
        if self._memory_monitor_registered:
            return
        
        try:
            self.memory_monitor = get_memory_monitor()
            self.memory_monitor.add_cleanup_callback(self._memory_cleanup_callback)
            self._memory_monitor_registered = True
            logger.info(f"LRUCacheManager '{self.name}' registered with memory monitor")
        except Exception as e:
            logger.warning(f"Failed to register memory monitoring for cache '{self.name}': {e}")
    
    def _memory_cleanup_callback(self, cleanup_level: str, memory_stats: MemoryStats):
        """Callback for memory monitor to trigger cache cleanup."""
        try:
            if cleanup_level == "light":
                self._cleanup_expired_entries()
                self._stats['memory_cleanups'] += 1
            elif cleanup_level == "aggressive":
                self._cleanup_expired_entries()
                self._evict_to_memory_limit(target_ratio=0.7)  # Keep 70% of max memory
                self._stats['memory_cleanups'] += 1
            elif cleanup_level == "emergency":
                self._cleanup_expired_entries()
                self._evict_to_memory_limit(target_ratio=0.3)  # Keep 30% of max memory
                self._evict_to_size_limit(target_ratio=0.4)   # Keep 40% of max entries
                self._stats['memory_cleanups'] += 1
            
            logger.info(f"Completed {cleanup_level} memory cleanup for cache '{self.name}'")
            
        except Exception as e:
            logger.error(f"Error during {cleanup_level} memory cleanup for cache '{self.name}': {e}")
    
    def _estimate_size(self, value: Any) -> int:
        """Estimate memory size of a value in bytes."""
        try:
            if hasattr(value, '__sizeof__'):
                return sys.getsizeof(value)
            elif isinstance(value, str):
                return len(value.encode('utf-8'))
            elif isinstance(value, (int, float)):
                return sys.getsizeof(value)
            elif isinstance(value, (list, tuple)):
                return sum(self._estimate_size(item) for item in value)
            elif isinstance(value, dict):
                return sum(self._estimate_size(k) + self._estimate_size(v) for k, v in value.items())
            else:
                # Fallback estimation
                return sys.getsizeof(str(value))
        except Exception:
            # Safe fallback if size estimation fails
            return 1024  # 1KB default
    
    def _cleanup_expired_entries(self) -> int:
        """Remove expired entries from cache."""
        with self._lock:
            expired_keys = []
            
            for key, entry in self._cache.items():
                if entry.is_expired():
                    expired_keys.append(key)
            
            for key in expired_keys:
                entry = self._cache.pop(key, None)
                if entry:
                    self._stats['total_size_bytes'] -= entry.size_bytes
                    self._stats['expired_cleanups'] += 1
            
            if expired_keys:
                logger.debug(f"Cache '{self.name}': Cleaned up {len(expired_keys)} expired entries")
            
            return len(expired_keys)
    
    def _evict_to_memory_limit(self, target_ratio: float = 0.8) -> int:
        """Evict entries to reach target memory usage."""
        with self._lock:
            target_bytes = int(self.max_memory_bytes * target_ratio)
            
            if self._stats['total_size_bytes'] <= target_bytes:
                return 0
            
            # Get entries sorted by priority (lowest priority first for eviction)
            entries_by_priority = [
                (key, entry, entry.calculate_priority_score())
                for key, entry in self._cache.items()
            ]
            entries_by_priority.sort(key=lambda x: x[2])  # Sort by priority score
            
            evicted_count = 0
            for key, entry, priority in entries_by_priority:
                if self._stats['total_size_bytes'] <= target_bytes:
                    break
                
                self._cache.pop(key, None)
                self._stats['total_size_bytes'] -= entry.size_bytes
                self._stats['evictions'] += 1
                evicted_count += 1
            
            if evicted_count > 0:
                logger.debug(f"Cache '{self.name}': Evicted {evicted_count} entries for memory limit")
            
            return evicted_count
    
    def _evict_to_size_limit(self, target_ratio: float = 0.8) -> int:
        """Evict entries to reach target size limit."""
        with self._lock:
            target_size = int(self.max_size * target_ratio)
            
            if len(self._cache) <= target_size:
                return 0
            
            # For size-based eviction, use priority-based selection if we have different cache types
            cache_types = set(entry.cache_type for entry in self._cache.values())
            use_priority_eviction = len(cache_types) > 1
            
            evicted_count = 0
            
            if use_priority_eviction:
                # Get entries sorted by priority (lowest priority first for eviction)
                entries_by_priority = [
                    (key, entry, entry.calculate_priority_score())
                    for key, entry in self._cache.items()
                ]
                entries_by_priority.sort(key=lambda x: x[2])  # Sort by priority score
                
                for key, entry, priority in entries_by_priority:
                    if len(self._cache) <= target_size:
                        break
                    
                    self._cache.pop(key, None)
                    self._stats['total_size_bytes'] -= entry.size_bytes
                    self._stats['evictions'] += 1
                    evicted_count += 1
            else:
                # Use simple LRU for homogeneous cache types
                while len(self._cache) > target_size:
                    key, entry = self._cache.popitem(last=False)  # Remove from beginning (LRU)
                    self._stats['total_size_bytes'] -= entry.size_bytes
                    self._stats['evictions'] += 1
                    evicted_count += 1
            
            if evicted_count > 0:
                logger.debug(f"Cache '{self.name}': Evicted {evicted_count} entries for size limit")
            
            return evicted_count
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache, updating access information."""
        with self._lock:
            entry = self._cache.get(key)
            
            if entry is None:
                self._stats['misses'] += 1
                return None
            
            # Check if expired
            if entry.is_expired():
                self._cache.pop(key, None)
                self._stats['total_size_bytes'] -= entry.size_bytes
                self._stats['misses'] += 1
                self._stats['expired_cleanups'] += 1
                return None
            
            # Update access information
            entry.last_accessed = datetime.now()
            entry.access_count += 1
            
            # Move to end (most recently used)
            self._cache.move_to_end(key)
            
            self._stats['hits'] += 1
            return entry.value
    
    def put(self, key: str, value: Any, 
            ttl: Optional[int] = None,
            cache_type: CacheType = CacheType.GENERAL) -> bool:
        """Put value in cache with LRU eviction if necessary."""
        with self._lock:
            try:
                # Use provided TTL or default
                effective_ttl = ttl if ttl is not None else self.default_ttl
                
                # Estimate size
                size_bytes = self._estimate_size(value)
                
                # Check if single item exceeds memory limit
                if size_bytes > self.max_memory_bytes:
                    logger.warning(f"Cache '{self.name}': Item too large ({size_bytes} bytes), skipping")
                    return False
                
                # Remove existing entry if updating
                if key in self._cache:
                    old_entry = self._cache.pop(key)
                    self._stats['total_size_bytes'] -= old_entry.size_bytes
                
                # Create new entry
                entry = CacheEntry(
                    key=key,
                    value=value,
                    created_at=datetime.now(),
                    last_accessed=datetime.now(),
                    access_count=1,
                    size_bytes=size_bytes,
                    ttl_seconds=effective_ttl,
                    cache_type=cache_type
                )
                
                # Add to cache
                self._cache[key] = entry
                self._stats['total_size_bytes'] += size_bytes
                
                # Cleanup expired entries periodically
                if len(self._cache) % 100 == 0:  # Every 100 additions
                    self._cleanup_expired_entries()
                
                # Evict if necessary (ensure we don't evict the item we just added)
                while len(self._cache) > self.max_size:
                    # Check if we have different cache types for priority-based eviction
                    cache_types = set(entry.cache_type for entry in self._cache.values())
                    
                    if len(cache_types) > 1:
                        # Use priority-based eviction for mixed cache types
                        entries_by_priority = [
                            (key, entry, entry.calculate_priority_score())
                            for key, entry in self._cache.items()
                        ]
                        entries_by_priority.sort(key=lambda x: x[2])  # Sort by priority score
                        
                        # Evict lowest priority item
                        key_to_evict, entry_to_evict, _ = entries_by_priority[0]
                        self._cache.pop(key_to_evict)
                        self._stats['total_size_bytes'] -= entry_to_evict.size_bytes
                        self._stats['evictions'] += 1
                    else:
                        # Use simple LRU for homogeneous cache types
                        oldest_key = next(iter(self._cache))  # Get first (oldest) key
                        oldest_entry = self._cache.pop(oldest_key)
                        self._stats['total_size_bytes'] -= oldest_entry.size_bytes
                        self._stats['evictions'] += 1
                
                if self._stats['total_size_bytes'] > self.max_memory_bytes:
                    self._evict_to_memory_limit()
                
                return True
                
            except Exception as e:
                logger.error(f"Error putting item in cache '{self.name}': {e}")
                return False
    
    def remove(self, key: str) -> bool:
        """Remove item from cache."""
        with self._lock:
            entry = self._cache.pop(key, None)
            if entry:
                self._stats['total_size_bytes'] -= entry.size_bytes
                return True
            return False
    
    def clear(self) -> None:
        """Clear all entries from cache."""
        with self._lock:
            self._cache.clear()
            self._stats['total_size_bytes'] = 0
            logger.info(f"Cache '{self.name}' cleared")
    
    def keys(self) -> List[str]:
        """Get all keys in cache (most recently used last)."""
        with self._lock:
            return list(self._cache.keys())
    
    def size(self) -> int:
        """Get number of entries in cache."""
        with self._lock:
            return len(self._cache)
    
    def memory_usage_mb(self) -> float:
        """Get current memory usage in MB."""
        with self._lock:
            return self._stats['total_size_bytes'] / (1024 * 1024)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics."""
        with self._lock:
            total_requests = self._stats['hits'] + self._stats['misses']
            hit_rate = self._stats['hits'] / max(total_requests, 1)
            uptime_hours = (datetime.now() - self._stats['created_at']).total_seconds() / 3600
            
            # Cache type distribution
            type_distribution = {}
            for entry in self._cache.values():
                cache_type = entry.cache_type.value
                type_distribution[cache_type] = type_distribution.get(cache_type, 0) + 1
            
            return {
                'cache_name': self.name,
                'size': len(self._cache),
                'max_size': self.max_size,
                'memory_usage_mb': self.memory_usage_mb(),
                'max_memory_mb': self.max_memory_bytes / (1024 * 1024),
                'memory_utilization': self.memory_usage_mb() / (self.max_memory_bytes / (1024 * 1024)) if self.max_memory_bytes > 0 else 0,
                'hit_rate': hit_rate,
                'total_hits': self._stats['hits'],
                'total_misses': self._stats['misses'],
                'total_evictions': self._stats['evictions'],
                'memory_cleanups': self._stats['memory_cleanups'],
                'expired_cleanups': self._stats['expired_cleanups'],
                'uptime_hours': uptime_hours,
                'type_distribution': type_distribution,
                'memory_monitoring_enabled': self.enable_memory_monitoring,
                'default_ttl': self.default_ttl
            }
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get health status of the cache."""
        stats = self.get_statistics()
        
        # Determine health status
        memory_pressure = stats['memory_utilization'] > 0.9
        size_pressure = stats['size'] / stats['max_size'] > 0.9
        low_hit_rate = stats['hit_rate'] < 0.5 and stats['total_hits'] + stats['total_misses'] > 100
        
        if memory_pressure or size_pressure:
            status = "critical"
        elif low_hit_rate:
            status = "warning"
        else:
            status = "healthy"
        
        return {
            'service': f'LRUCacheManager-{self.name}',
            'status': status,
            'memory_pressure': memory_pressure,
            'size_pressure': size_pressure,
            'hit_rate': stats['hit_rate'],
            'utilization': {
                'memory_percent': stats['memory_utilization'] * 100,
                'size_percent': (stats['size'] / stats['max_size']) * 100
            }
        }
    
    def force_cleanup(self, cleanup_level: str = "aggressive") -> Dict[str, int]:
        """Manually trigger cleanup operations."""
        with self._lock:
            results = {
                'expired_removed': 0,
                'memory_evicted': 0,
                'size_evicted': 0
            }
            
            # Always clean expired entries
            results['expired_removed'] = self._cleanup_expired_entries()
            
            if cleanup_level == "light":
                # Only remove expired entries
                pass
            elif cleanup_level == "aggressive":
                # Remove expired + evict for memory
                results['memory_evicted'] = self._evict_to_memory_limit(target_ratio=0.7)
            elif cleanup_level == "emergency":
                # Full cleanup
                results['memory_evicted'] = self._evict_to_memory_limit(target_ratio=0.5)
                results['size_evicted'] = self._evict_to_size_limit(target_ratio=0.5)
            
            logger.info(f"Manual cleanup '{cleanup_level}' for cache '{self.name}': {results}")
            return results


# Global cache registry for easy access
_cache_registry: Dict[str, LRUCacheManager] = {}
_registry_lock = threading.Lock()


def get_lru_cache(name: str, 
                  max_size: int = 1000,
                  max_memory_mb: float = 100.0,
                  default_ttl: Optional[int] = None,
                  enable_memory_monitoring: bool = True) -> LRUCacheManager:
    """
    Get or create an LRU cache instance.
    
    Args:
        name: Cache name (creates new if doesn't exist)
        max_size: Maximum number of entries
        max_memory_mb: Maximum memory usage in MB
        default_ttl: Default TTL in seconds
        enable_memory_monitoring: Whether to enable memory monitoring
    
    Returns:
        LRUCacheManager instance
    """
    with _registry_lock:
        if name not in _cache_registry:
            _cache_registry[name] = LRUCacheManager(
                name=name,
                max_size=max_size,
                max_memory_mb=max_memory_mb,
                default_ttl=default_ttl,
                enable_memory_monitoring=enable_memory_monitoring
            )
        
        return _cache_registry[name]


def get_all_caches() -> Dict[str, LRUCacheManager]:
    """Get all registered cache instances."""
    with _registry_lock:
        return _cache_registry.copy()


def clear_all_caches() -> None:
    """Clear all registered caches."""
    with _registry_lock:
        for cache in _cache_registry.values():
            cache.clear()
        logger.info("All LRU caches cleared")


def get_cache_summary() -> Dict[str, Any]:
    """Get summary statistics for all caches."""
    with _registry_lock:
        summary = {
            'total_caches': len(_cache_registry),
            'total_entries': 0,
            'total_memory_mb': 0.0,
            'caches': {}
        }
        
        for name, cache in _cache_registry.items():
            stats = cache.get_statistics()
            summary['total_entries'] += stats['size']
            summary['total_memory_mb'] += stats['memory_usage_mb']
            summary['caches'][name] = {
                'size': stats['size'],
                'memory_mb': stats['memory_usage_mb'],
                'hit_rate': stats['hit_rate'],
                'status': cache.get_health_status()['status']
            }
        
        return summary