"""
Advanced caching system with LRU, TTL, and intelligent cache management.

This module provides a comprehensive caching solution for the LINE Bot application
with support for multiple cache types, intelligent key generation, and monitoring.
"""

import time
import threading
import hashlib
import json
import pickle
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, List, Tuple, Callable, Union
from collections import OrderedDict
from dataclasses import dataclass, asdict
from enum import Enum
import logging

from ..exceptions import BaseBotException, ErrorSeverity, ErrorCategory


class CacheType(Enum):
    """Types of cache storage."""
    MEMORY = "memory"
    REDIS = "redis"
    HYBRID = "hybrid"


class EvictionPolicy(Enum):
    """Cache eviction policies."""
    LRU = "lru"           # Least Recently Used
    LFU = "lfu"           # Least Frequently Used
    TTL = "ttl"           # Time To Live only
    HYBRID = "hybrid"     # Combination of LRU and TTL


@dataclass
class CacheEntry:
    """Cache entry with metadata."""
    value: Any
    created_at: float
    accessed_at: float
    access_count: int = 1
    ttl: Optional[float] = None
    size_bytes: int = 0
    
    @property
    def is_expired(self) -> bool:
        """Check if entry has expired."""
        if self.ttl is None:
            return False
        return time.time() - self.created_at > self.ttl
    
    @property
    def age_seconds(self) -> float:
        """Get age of entry in seconds."""
        return time.time() - self.created_at
    
    def touch(self):
        """Update access metadata."""
        self.accessed_at = time.time()
        self.access_count += 1


@dataclass
class CacheStats:
    """Cache performance statistics."""
    hits: int = 0
    misses: int = 0
    sets: int = 0
    deletes: int = 0
    evictions: int = 0
    size_bytes: int = 0
    entry_count: int = 0
    
    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0
    
    @property
    def miss_rate(self) -> float:
        """Calculate cache miss rate."""
        return 1.0 - self.hit_rate


class CacheException(BaseBotException):
    """Cache-specific exceptions."""
    
    def __init__(self, message: str, cache_name: str, **kwargs):
        super().__init__(
            message=message,
            category=ErrorCategory.SERVICE_ERROR,
            **kwargs
        )
        self.cache_name = cache_name
        self.context.update({'cache_name': cache_name})


class IntelligentKeyGenerator:
    """Intelligent cache key generation with collision avoidance."""
    
    @staticmethod
    def generate_key(
        prefix: str,
        *args,
        **kwargs
    ) -> str:
        """
        Generate cache key from prefix and parameters.
        
        Args:
            prefix: Key prefix for namespacing
            *args: Positional arguments to include in key
            **kwargs: Keyword arguments to include in key
            
        Returns:
            str: Generated cache key
        """
        # Create deterministic key from arguments
        key_parts = [str(prefix)]
        
        # Add positional arguments
        for arg in args:
            if isinstance(arg, (dict, list, tuple)):
                # Convert complex types to deterministic strings
                arg_str = json.dumps(arg, sort_keys=True, default=str)
            else:
                arg_str = str(arg)
            key_parts.append(arg_str)
        
        # Add keyword arguments (sorted for consistency)
        for key, value in sorted(kwargs.items()):
            if isinstance(value, (dict, list, tuple)):
                value_str = json.dumps(value, sort_keys=True, default=str)
            else:
                value_str = str(value)
            key_parts.append(f"{key}={value_str}")
        
        # Create hash of the combined key to avoid length issues
        combined_key = "|".join(key_parts)
        if len(combined_key) > 200:  # Limit key length
            hash_key = hashlib.sha256(combined_key.encode()).hexdigest()[:16]
            return f"{prefix}:{hash_key}"
        
        return combined_key.replace(" ", "_")
    
    @staticmethod
    def generate_openai_key(
        user_id: str,
        message: str,
        context_hash: Optional[str] = None,
        model: str = "gpt-4",
        temperature: float = 0.7
    ) -> str:
        """Generate cache key for OpenAI API responses."""
        return IntelligentKeyGenerator.generate_key(
            "openai",
            user_id=user_id[:8],  # Truncate for privacy
            message_hash=hashlib.sha256(message.encode()).hexdigest()[:16],
            context_hash=context_hash,
            model=model,
            temperature=temperature
        )
    
    @staticmethod
    def generate_template_key(
        template_id: str,
        category: str,
        modification_time: Optional[float] = None
    ) -> str:
        """Generate cache key for template images."""
        return IntelligentKeyGenerator.generate_key(
            "template",
            template_id=template_id,
            category=category,
            mtime=modification_time
        )
    
    @staticmethod
    def generate_search_key(
        query: str,
        language: str = "en",
        max_results: int = 5
    ) -> str:
        """Generate cache key for web search results."""
        return IntelligentKeyGenerator.generate_key(
            "search",
            query_hash=hashlib.sha256(query.encode()).hexdigest()[:16],
            language=language,
            max_results=max_results
        )


class LRUCache:
    """
    Thread-safe LRU cache with TTL support and size limits.
    
    Features:
    - Least Recently Used eviction
    - Time To Live expiration
    - Size-based eviction
    - Thread-safe operations
    - Performance monitoring
    """
    
    def __init__(
        self,
        max_size: int = 1000,
        default_ttl: Optional[float] = None,
        max_memory_mb: Optional[float] = None,
        eviction_policy: EvictionPolicy = EvictionPolicy.HYBRID
    ):
        """
        Initialize LRU cache.
        
        Args:
            max_size: Maximum number of entries
            default_ttl: Default TTL in seconds
            max_memory_mb: Maximum memory usage in MB
            eviction_policy: Eviction policy to use
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.max_memory_bytes = int(max_memory_mb * 1024 * 1024) if max_memory_mb else None
        self.eviction_policy = eviction_policy
        
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.RLock()
        self._stats = CacheStats()
        
        # Background cleanup thread
        self._cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self._cleanup_running = True
        self._cleanup_thread.start()
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        with self._lock:
            entry = self._cache.get(key)
            
            if entry is None:
                self._stats.misses += 1
                return None
            
            # Check if expired
            if entry.is_expired:
                self._remove_entry(key)
                self._stats.misses += 1
                return None
            
            # Update access metadata
            entry.touch()
            
            # Move to end for LRU
            if self.eviction_policy in (EvictionPolicy.LRU, EvictionPolicy.HYBRID):
                self._cache.move_to_end(key)
            
            self._stats.hits += 1
            return entry.value
    
    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[float] = None,
        size_hint: Optional[int] = None
    ) -> bool:
        """Set value in cache."""
        with self._lock:
            # Calculate size
            if size_hint:
                size_bytes = size_hint
            else:
                try:
                    size_bytes = len(pickle.dumps(value))
                except (pickle.PickleError, TypeError):
                    size_bytes = len(str(value).encode('utf-8'))
            
            # Check memory limits
            if self.max_memory_bytes:
                if size_bytes > self.max_memory_bytes:
                    return False  # Single item too large
                
                # Evict entries if needed to make room
                while (self._stats.size_bytes + size_bytes > self.max_memory_bytes 
                       and len(self._cache) > 0):
                    self._evict_one()
            
            # Create cache entry
            entry = CacheEntry(
                value=value,
                created_at=time.time(),
                accessed_at=time.time(),
                ttl=ttl or self.default_ttl,
                size_bytes=size_bytes
            )
            
            # Remove existing entry if present
            if key in self._cache:
                self._remove_entry(key)
            
            # Add new entry
            self._cache[key] = entry
            self._stats.sets += 1
            self._stats.size_bytes += size_bytes
            self._stats.entry_count += 1
            
            # Evict if over size limit
            while len(self._cache) > self.max_size:
                self._evict_one()
            
            return True
    
    def delete(self, key: str) -> bool:
        """Delete entry from cache."""
        with self._lock:
            if key in self._cache:
                self._remove_entry(key)
                self._stats.deletes += 1
                return True
            return False
    
    def clear(self):
        """Clear all entries from cache."""
        with self._lock:
            self._cache.clear()
            self._stats = CacheStats()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            stats_dict = asdict(self._stats)
            stats_dict.update({
                'current_size': len(self._cache),
                'max_size': self.max_size,
                'memory_usage_mb': self._stats.size_bytes / (1024 * 1024),
                'max_memory_mb': self.max_memory_bytes / (1024 * 1024) if self.max_memory_bytes else None
            })
            return stats_dict
    
    def get_keys(self, pattern: Optional[str] = None) -> List[str]:
        """Get all cache keys, optionally filtered by pattern."""
        with self._lock:
            keys = list(self._cache.keys())
            if pattern:
                keys = [k for k in keys if pattern in k]
            return keys
    
    def _remove_entry(self, key: str):
        """Remove entry and update stats."""
        if key in self._cache:
            entry = self._cache.pop(key)
            self._stats.size_bytes -= entry.size_bytes
            self._stats.entry_count -= 1
    
    def _evict_one(self):
        """Evict one entry based on eviction policy."""
        if not self._cache:
            return
        
        if self.eviction_policy == EvictionPolicy.LRU:
            # Remove least recently used (first item)
            key = next(iter(self._cache))
        elif self.eviction_policy == EvictionPolicy.LFU:
            # Remove least frequently used
            key = min(self._cache.keys(), key=lambda k: self._cache[k].access_count)
        elif self.eviction_policy == EvictionPolicy.TTL:
            # Remove oldest entry
            key = min(self._cache.keys(), key=lambda k: self._cache[k].created_at)
        else:  # HYBRID
            # Remove expired entries first, then LRU
            now = time.time()
            expired_keys = [k for k, v in self._cache.items() if v.is_expired]
            if expired_keys:
                key = expired_keys[0]
            else:
                key = next(iter(self._cache))
        
        self._remove_entry(key)
        self._stats.evictions += 1
    
    def _cleanup_loop(self):
        """Background cleanup of expired entries."""
        while self._cleanup_running:
            try:
                with self._lock:
                    now = time.time()
                    expired_keys = [
                        k for k, v in self._cache.items()
                        if v.is_expired
                    ]
                    
                    for key in expired_keys:
                        self._remove_entry(key)
                        self._stats.evictions += 1
                
                time.sleep(60)  # Cleanup every minute
                
            except Exception as e:
                logging.getLogger(__name__).error(f"Cache cleanup error: {e}")
                time.sleep(5)
    
    def shutdown(self):
        """Shutdown background cleanup thread."""
        self._cleanup_running = False
        if self._cleanup_thread.is_alive():
            self._cleanup_thread.join(timeout=5)


class CacheManager:
    """
    Advanced cache manager with multiple cache instances and intelligent routing.
    
    Features:
    - Multiple named cache instances
    - Intelligent key generation
    - Cache warming strategies
    - Performance monitoring
    - Redis integration support
    """
    
    def __init__(self, redis_client=None):
        """
        Initialize cache manager.
        
        Args:
            redis_client: Optional Redis client for distributed caching
        """
        self.redis_client = redis_client
        self._caches: Dict[str, LRUCache] = {}
        self._cache_configs: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        
        # Initialize default caches
        self._setup_default_caches()
    
    def _setup_default_caches(self):
        """Setup default cache instances for common use cases."""
        # OpenAI response cache
        self.create_cache(
            name="openai_responses",
            max_size=500,
            default_ttl=3600,  # 1 hour
            max_memory_mb=100,
            eviction_policy=EvictionPolicy.HYBRID
        )
        
        # Template image cache
        self.create_cache(
            name="template_images",
            max_size=100,
            default_ttl=86400,  # 24 hours
            max_memory_mb=200,
            eviction_policy=EvictionPolicy.LRU
        )
        
        # Web search results cache
        self.create_cache(
            name="search_results",
            max_size=200,
            default_ttl=900,  # 15 minutes
            max_memory_mb=50,
            eviction_policy=EvictionPolicy.TTL
        )
        
        # Conversation context cache
        self.create_cache(
            name="conversation_context",
            max_size=1000,
            default_ttl=7200,  # 2 hours
            max_memory_mb=150,
            eviction_policy=EvictionPolicy.LRU
        )
    
    def create_cache(
        self,
        name: str,
        max_size: int = 1000,
        default_ttl: Optional[float] = None,
        max_memory_mb: Optional[float] = None,
        eviction_policy: EvictionPolicy = EvictionPolicy.HYBRID
    ) -> LRUCache:
        """Create a new named cache instance."""
        with self._lock:
            if name in self._caches:
                raise CacheException(
                    message=f"Cache '{name}' already exists",
                    cache_name=name
                )
            
            cache = LRUCache(
                max_size=max_size,
                default_ttl=default_ttl,
                max_memory_mb=max_memory_mb,
                eviction_policy=eviction_policy
            )
            
            self._caches[name] = cache
            self._cache_configs[name] = {
                'max_size': max_size,
                'default_ttl': default_ttl,
                'max_memory_mb': max_memory_mb,
                'eviction_policy': eviction_policy.value
            }
            
            return cache
    
    def get_cache(self, name: str) -> Optional[LRUCache]:
        """Get cache instance by name."""
        return self._caches.get(name)
    
    def cache_openai_response(
        self,
        user_id: str,
        message: str,
        response: str,
        context_hash: Optional[str] = None,
        model: str = "gpt-4",
        temperature: float = 0.7,
        ttl: Optional[float] = None
    ) -> bool:
        """Cache OpenAI API response with intelligent key generation."""
        cache = self.get_cache("openai_responses")
        if not cache:
            return False
        
        key = IntelligentKeyGenerator.generate_openai_key(
            user_id=user_id,
            message=message,
            context_hash=context_hash,
            model=model,
            temperature=temperature
        )
        
        return cache.set(key, response, ttl=ttl)
    
    def get_cached_openai_response(
        self,
        user_id: str,
        message: str,
        context_hash: Optional[str] = None,
        model: str = "gpt-4",
        temperature: float = 0.7
    ) -> Optional[str]:
        """Get cached OpenAI response."""
        cache = self.get_cache("openai_responses")
        if not cache:
            return None
        
        key = IntelligentKeyGenerator.generate_openai_key(
            user_id=user_id,
            message=message,
            context_hash=context_hash,
            model=model,
            temperature=temperature
        )
        
        return cache.get(key)
    
    def cache_template_image(
        self,
        template_id: str,
        category: str,
        image_data: bytes,
        modification_time: Optional[float] = None,
        ttl: Optional[float] = None
    ) -> bool:
        """Cache template image with smart invalidation."""
        cache = self.get_cache("template_images")
        if not cache:
            return False
        
        key = IntelligentKeyGenerator.generate_template_key(
            template_id=template_id,
            category=category,
            modification_time=modification_time
        )
        
        return cache.set(key, image_data, ttl=ttl, size_hint=len(image_data))
    
    def get_cached_template_image(
        self,
        template_id: str,
        category: str,
        modification_time: Optional[float] = None
    ) -> Optional[bytes]:
        """Get cached template image."""
        cache = self.get_cache("template_images")
        if not cache:
            return None
        
        key = IntelligentKeyGenerator.generate_template_key(
            template_id=template_id,
            category=category,
            modification_time=modification_time
        )
        
        return cache.get(key)
    
    def cache_search_results(
        self,
        query: str,
        results: List[Dict[str, Any]],
        language: str = "en",
        max_results: int = 5,
        ttl: Optional[float] = None
    ) -> bool:
        """Cache web search results."""
        cache = self.get_cache("search_results")
        if not cache:
            return False
        
        key = IntelligentKeyGenerator.generate_search_key(
            query=query,
            language=language,
            max_results=max_results
        )
        
        return cache.set(key, results, ttl=ttl)
    
    def get_cached_search_results(
        self,
        query: str,
        language: str = "en",
        max_results: int = 5
    ) -> Optional[List[Dict[str, Any]]]:
        """Get cached search results."""
        cache = self.get_cache("search_results")
        if not cache:
            return None
        
        key = IntelligentKeyGenerator.generate_search_key(
            query=query,
            language=language,
            max_results=max_results
        )
        
        return cache.get(key)
    
    def warm_cache(
        self,
        cache_name: str,
        warm_func: Callable[[], Dict[str, Any]],
        key_prefix: str = "warm"
    ):
        """Warm cache with precomputed data."""
        cache = self.get_cache(cache_name)
        if not cache:
            return
        
        try:
            warm_data = warm_func()
            for key, value in warm_data.items():
                cache.set(f"{key_prefix}:{key}", value)
        except Exception as e:
            raise CacheException(
                message=f"Cache warming failed: {str(e)}",
                cache_name=cache_name,
                original_exception=e
            )
    
    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all caches."""
        stats = {}
        for name, cache in self._caches.items():
            stats[name] = cache.get_stats()
            stats[name]['config'] = self._cache_configs[name]
        return stats
    
    def clear_all_caches(self):
        """Clear all cache instances."""
        for cache in self._caches.values():
            cache.clear()
    
    def shutdown(self):
        """Shutdown all cache instances."""
        for cache in self._caches.values():
            cache.shutdown()


# Global cache manager instance
cache_manager = CacheManager()


def get_cache_manager() -> CacheManager:
    """Get the global cache manager instance."""
    return cache_manager


# Export main classes and functions
__all__ = [
    'CacheManager',
    'LRUCache',
    'IntelligentKeyGenerator',
    'CacheType',
    'EvictionPolicy', 
    'CacheEntry',
    'CacheStats',
    'CacheException',
    'cache_manager',
    'get_cache_manager'
]