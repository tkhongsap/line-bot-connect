"""
Redis caching utilities for performance optimization.

This module provides comprehensive Redis caching strategies for content,
templates, API responses, and performance optimization.
"""

import json
import logging
import pickle
import time
import hashlib
from typing import Any, Optional, Dict, List, Union
from datetime import datetime, timedelta
from functools import wraps
import redis
from redis.connection import ConnectionPool

logger = logging.getLogger(__name__)


class RedisCache:
    """Enhanced Redis caching with performance optimization features."""
    
    def __init__(self, redis_url: str = "redis://localhost:6379/0", 
                 default_ttl: int = 3600, max_connections: int = 50):
        """
        Initialize Redis cache with connection pooling.
        
        Args:
            redis_url: Redis connection URL
            default_ttl: Default time-to-live in seconds
            max_connections: Maximum number of connections in pool
        """
        try:
            # Create connection pool
            self.pool = ConnectionPool.from_url(
                redis_url,
                max_connections=max_connections,
                retry_on_timeout=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            
            self.redis_client = redis.Redis(connection_pool=self.pool)
            self.default_ttl = default_ttl
            
            # Test connection
            self.redis_client.ping()
            logger.info(f"Redis cache initialized with {max_connections} max connections")
            
        except Exception as e:
            logger.error(f"Failed to initialize Redis cache: {e}")
            self.redis_client = None
    
    def _make_key(self, key: str, prefix: str = "") -> str:
        """Create a prefixed cache key."""
        return f"{prefix}:{key}" if prefix else key
    
    def get(self, key: str, prefix: str = "", deserialize: bool = True) -> Optional[Any]:
        """Get value from cache."""
        if not self.redis_client:
            return None
            
        try:
            cache_key = self._make_key(key, prefix)
            value = self.redis_client.get(cache_key)
            
            if value is None:
                return None
                
            if deserialize:
                try:
                    return json.loads(value.decode('utf-8'))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    return pickle.loads(value)
            else:
                return value.decode('utf-8') if isinstance(value, bytes) else value
                
        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")
            return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None, 
            prefix: str = "", serialize: bool = True) -> bool:
        """Set value in cache."""
        if not self.redis_client:
            return False
            
        try:
            cache_key = self._make_key(key, prefix)
            ttl = ttl or self.default_ttl
            
            if serialize:
                try:
                    serialized_value = json.dumps(value, default=str)
                except (TypeError, ValueError):
                    serialized_value = pickle.dumps(value)
            else:
                serialized_value = value
                
            return self.redis_client.setex(cache_key, ttl, serialized_value)
            
        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
            return False
    
    def delete(self, key: str, prefix: str = "") -> bool:
        """Delete key from cache."""
        if not self.redis_client:
            return False
            
        try:
            cache_key = self._make_key(key, prefix)
            return bool(self.redis_client.delete(cache_key))
        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {e}")
            return False
    
    def exists(self, key: str, prefix: str = "") -> bool:
        """Check if key exists in cache."""
        if not self.redis_client:
            return False
            
        try:
            cache_key = self._make_key(key, prefix)
            return bool(self.redis_client.exists(cache_key))
        except Exception as e:
            logger.error(f"Cache exists error for key {key}: {e}")
            return False
    
    def increment(self, key: str, amount: int = 1, prefix: str = "", 
                  ttl: Optional[int] = None) -> Optional[int]:
        """Increment counter in cache."""
        if not self.redis_client:
            return None
            
        try:
            cache_key = self._make_key(key, prefix)
            pipeline = self.redis_client.pipeline()
            pipeline.incr(cache_key, amount)
            if ttl:
                pipeline.expire(cache_key, ttl)
            results = pipeline.execute()
            return results[0]
        except Exception as e:
            logger.error(f"Cache increment error for key {key}: {e}")
            return None
    
    def get_many(self, keys: List[str], prefix: str = "") -> Dict[str, Any]:
        """Get multiple values from cache."""
        if not self.redis_client or not keys:
            return {}
            
        try:
            cache_keys = [self._make_key(key, prefix) for key in keys]
            values = self.redis_client.mget(cache_keys)
            
            result = {}
            for i, (original_key, value) in enumerate(zip(keys, values)):
                if value is not None:
                    try:
                        result[original_key] = json.loads(value.decode('utf-8'))
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        result[original_key] = pickle.loads(value)
            
            return result
        except Exception as e:
            logger.error(f"Cache get_many error: {e}")
            return {}
    
    def set_many(self, mapping: Dict[str, Any], ttl: Optional[int] = None, 
                 prefix: str = "") -> bool:
        """Set multiple values in cache."""
        if not self.redis_client or not mapping:
            return False
            
        try:
            pipeline = self.redis_client.pipeline()
            ttl = ttl or self.default_ttl
            
            for key, value in mapping.items():
                cache_key = self._make_key(key, prefix)
                try:
                    serialized_value = json.dumps(value, default=str)
                except (TypeError, ValueError):
                    serialized_value = pickle.dumps(value)
                pipeline.setex(cache_key, ttl, serialized_value)
            
            pipeline.execute()
            return True
        except Exception as e:
            logger.error(f"Cache set_many error: {e}")
            return False
    
    def clear_pattern(self, pattern: str) -> int:
        """Clear all keys matching pattern."""
        if not self.redis_client:
            return 0
            
        try:
            keys = self.redis_client.keys(pattern)
            if keys:
                return self.redis_client.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"Cache clear_pattern error for {pattern}: {e}")
            return 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        if not self.redis_client:
            return {}
            
        try:
            info = self.redis_client.info()
            return {
                'connected_clients': info.get('connected_clients', 0),
                'used_memory': info.get('used_memory', 0),
                'used_memory_human': info.get('used_memory_human', '0B'),
                'total_commands_processed': info.get('total_commands_processed', 0),
                'instantaneous_ops_per_sec': info.get('instantaneous_ops_per_sec', 0),
                'keyspace_hits': info.get('keyspace_hits', 0),
                'keyspace_misses': info.get('keyspace_misses', 0),
                'hit_rate': self._calculate_hit_rate(info)
            }
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {}
    
    def _calculate_hit_rate(self, info: Dict) -> float:
        """Calculate cache hit rate."""
        hits = info.get('keyspace_hits', 0)
        misses = info.get('keyspace_misses', 0)
        total = hits + misses
        return (hits / total * 100) if total > 0 else 0.0
    
    def health_check(self) -> bool:
        """Check if Redis is healthy."""
        try:
            return self.redis_client.ping() if self.redis_client else False
        except Exception:
            return False


def cache_result(ttl: int = 3600, prefix: str = "", 
                cache_instance: Optional[RedisCache] = None):
    """Decorator for caching function results."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Use provided cache instance or create default
            cache = cache_instance or redis_cache
            
            # Create cache key from function name and arguments
            key_data = f"{func.__name__}:{str(args)}:{str(sorted(kwargs.items()))}"
            cache_key = hashlib.md5(key_data.encode()).hexdigest()
            
            # Try to get from cache
            cached_result = cache.get(cache_key, prefix)
            if cached_result is not None:
                logger.debug(f"Cache hit for {func.__name__}")
                return cached_result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            cache.set(cache_key, result, ttl, prefix)
            logger.debug(f"Cache miss for {func.__name__}, result cached")
            
            return result
        return wrapper
    return decorator


# Global Redis cache instance
redis_cache = RedisCache()