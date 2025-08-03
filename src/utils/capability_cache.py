"""
Azure OpenAI Capability Cache Management

This module provides file-based caching for Azure OpenAI API capability detection
with TTL management and in-memory fallback for high availability.
"""

import json
import logging
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Any
from threading import Lock
import aiofiles

logger = logging.getLogger(__name__)


class CapabilityCache:
    """
    File-based cache for Azure OpenAI API capabilities with in-memory fallback.
    
    Provides persistent storage of capability detection results with TTL management
    and thread-safe operations.
    """
    
    def __init__(self, cache_file: str = "data/api_capabilities.json", default_ttl: int = 300):
        """
        Initialize the capability cache.
        
        Args:
            cache_file: Path to the JSON cache file
            default_ttl: Default TTL for cached entries in seconds
        """
        self.cache_file = Path(cache_file)
        self.default_ttl = default_ttl
        self._lock = Lock()
        self._memory_cache: Dict[str, Any] = {}
        self._ensure_cache_directory()
        
        logger.info(f"Initialized CapabilityCache: file={cache_file}, ttl={default_ttl}s")
    
    def _ensure_cache_directory(self):
        """Ensure the cache directory exists"""
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.warning(f"Could not create cache directory: {e}")
    
    async def get_capabilities(self) -> Optional[Dict[str, Any]]:
        """
        Get cached capabilities if they are still valid.
        
        Returns:
            Cached capabilities dict or None if cache is invalid/empty
        """
        try:
            # Try file-based cache first
            if self.cache_file.exists():
                async with aiofiles.open(self.cache_file, 'r') as f:
                    content = await f.read()
                    cache_data = json.loads(content)
                    
                    if self._is_cache_valid(cache_data):
                        logger.info("Retrieved valid capabilities from file cache")
                        return cache_data['capabilities']
                    else:
                        logger.info("File cache expired")
            
            # Fall back to memory cache
            with self._lock:
                if self._memory_cache and self._is_cache_valid(self._memory_cache):
                    logger.info("Retrieved valid capabilities from memory cache")
                    return self._memory_cache['capabilities']
            
            logger.info("No valid cached capabilities found")
            return None
            
        except Exception as e:
            logger.warning(f"Error reading capabilities cache: {e}")
            # Try memory fallback
            with self._lock:
                if self._memory_cache and self._is_cache_valid(self._memory_cache):
                    logger.info("Using memory cache fallback after file error")
                    return self._memory_cache['capabilities']
            return None
    
    async def set_capabilities(self, capabilities: Dict[str, bool], ttl: Optional[int] = None) -> bool:
        """
        Cache capabilities with TTL.
        
        Args:
            capabilities: Dict of capability names to availability status
            ttl: TTL in seconds (uses default if None)
            
        Returns:
            True if caching was successful, False otherwise
        """
        ttl = ttl or self.default_ttl
        cache_data = {
            'last_updated': datetime.now().isoformat(),
            'ttl_seconds': ttl,
            'capabilities': capabilities,
            'detection_history': self._get_detection_history() + [{
                'timestamp': datetime.now().isoformat(),
                'capabilities': capabilities
            }]
        }
        
        # Keep only last 10 history entries
        cache_data['detection_history'] = cache_data['detection_history'][-10:]
        
        success = False
        
        # Try to save to file
        try:
            self._ensure_cache_directory()
            async with aiofiles.open(self.cache_file, 'w') as f:
                await f.write(json.dumps(cache_data, indent=2))
            success = True
            logger.info(f"Cached capabilities to file: {capabilities}")
        except Exception as e:
            logger.warning(f"Could not write capabilities to file: {e}")
        
        # Always update memory cache as fallback
        with self._lock:
            self._memory_cache = cache_data.copy()
            logger.info(f"Cached capabilities in memory: {capabilities}")
        
        return success
    
    def _is_cache_valid(self, cache_data: Dict[str, Any]) -> bool:
        """Check if cached data is still valid based on TTL"""
        try:
            last_updated = datetime.fromisoformat(cache_data['last_updated'])
            ttl = cache_data.get('ttl_seconds', self.default_ttl)
            age = datetime.now() - last_updated
            is_valid = age.total_seconds() < ttl
            
            if not is_valid:
                logger.debug(f"Cache expired: age={age.total_seconds():.1f}s, ttl={ttl}s")
            
            return is_valid
        except (KeyError, ValueError, TypeError) as e:
            logger.warning(f"Invalid cache data format: {e}")
            return False
    
    def _get_detection_history(self) -> list:
        """Get existing detection history from cache"""
        try:
            if self.cache_file.exists():
                with open(self.cache_file, 'r') as f:
                    cache_data = json.load(f)
                    return cache_data.get('detection_history', [])
        except Exception as e:
            logger.debug(f"Could not read detection history: {e}")
        
        # Try memory cache
        with self._lock:
            return self._memory_cache.get('detection_history', [])
    
    async def get_cache_status(self) -> Dict[str, Any]:
        """Get detailed cache status information"""
        status = {
            'cache_file': str(self.cache_file),
            'file_exists': self.cache_file.exists(),
            'memory_cache_active': bool(self._memory_cache),
            'default_ttl': self.default_ttl
        }
        
        try:
            if self.cache_file.exists():
                stat = self.cache_file.stat()
                status['file_size_bytes'] = stat.st_size
                status['file_modified'] = datetime.fromtimestamp(stat.st_mtime).isoformat()
                
                async with aiofiles.open(self.cache_file, 'r') as f:
                    content = await f.read()
                    cache_data = json.loads(content)
                    status['file_cache_valid'] = self._is_cache_valid(cache_data)
                    status['file_last_updated'] = cache_data.get('last_updated')
                    status['file_ttl'] = cache_data.get('ttl_seconds')
        except Exception as e:
            status['file_error'] = str(e)
        
        with self._lock:
            if self._memory_cache:
                status['memory_cache_valid'] = self._is_cache_valid(self._memory_cache)
                status['memory_last_updated'] = self._memory_cache.get('last_updated')
                status['memory_ttl'] = self._memory_cache.get('ttl_seconds')
        
        return status
    
    async def clear_cache(self) -> bool:
        """Clear both file and memory cache"""
        success = True
        
        # Clear file cache
        try:
            if self.cache_file.exists():
                self.cache_file.unlink()
                logger.info("Cleared file cache")
        except Exception as e:
            logger.warning(f"Could not clear file cache: {e}")
            success = False
        
        # Clear memory cache
        with self._lock:
            self._memory_cache.clear()
            logger.info("Cleared memory cache")
        
        return success
    
    async def invalidate_cache(self) -> bool:
        """Invalidate cache by setting old timestamp"""
        try:
            # Update both file and memory cache with old timestamp
            old_data = {
                'last_updated': (datetime.now() - timedelta(hours=1)).isoformat(),
                'ttl_seconds': self.default_ttl,
                'capabilities': {},
                'detection_history': []
            }
            
            # Update file
            if self.cache_file.exists():
                async with aiofiles.open(self.cache_file, 'w') as f:
                    await f.write(json.dumps(old_data, indent=2))
            
            # Update memory
            with self._lock:
                self._memory_cache = old_data.copy()
            
            logger.info("Invalidated capability cache")
            return True
            
        except Exception as e:
            logger.warning(f"Could not invalidate cache: {e}")
            return False
    
    def get_cache_age_seconds(self) -> Optional[float]:
        """Get the age of the current cache in seconds"""
        try:
            # Try file cache first
            if self.cache_file.exists():
                with open(self.cache_file, 'r') as f:
                    cache_data = json.load(f)
                    last_updated = datetime.fromisoformat(cache_data['last_updated'])
                    return (datetime.now() - last_updated).total_seconds()
        except Exception:
            pass
        
        # Try memory cache
        with self._lock:
            if self._memory_cache:
                try:
                    last_updated = datetime.fromisoformat(self._memory_cache['last_updated'])
                    return (datetime.now() - last_updated).total_seconds()
                except Exception:
                    pass
        
        return None
    
    async def refresh_cache_if_needed(self, detector_func, max_age_seconds: int = None) -> Dict[str, bool]:
        """
        Refresh cache if it's older than max_age_seconds.
        
        Args:
            detector_func: Async function that returns fresh capabilities
            max_age_seconds: Max age before refresh (uses TTL if None)
            
        Returns:
            Current capabilities (from cache or fresh detection)
        """
        max_age = max_age_seconds or self.default_ttl
        current_age = self.get_cache_age_seconds()
        
        if current_age is None or current_age > max_age:
            logger.info(f"Cache age ({current_age}s) exceeds max ({max_age}s), refreshing")
            try:
                fresh_capabilities = await detector_func()
                await self.set_capabilities(fresh_capabilities)
                return fresh_capabilities
            except Exception as e:
                logger.error(f"Failed to refresh capabilities: {e}")
                # Return stale cache if available
                stale_capabilities = await self.get_capabilities()
                return stale_capabilities or {}
        else:
            logger.info(f"Cache is fresh (age: {current_age:.1f}s)")
            capabilities = await self.get_capabilities()
            return capabilities or {}


# Global cache instance
_capability_cache: Optional[CapabilityCache] = None


def get_capability_cache(cache_file: str = "data/api_capabilities.json", ttl: int = 300) -> CapabilityCache:
    """
    Get or create the global capability cache instance.
    
    Args:
        cache_file: Path to cache file
        ttl: Default TTL in seconds
        
    Returns:
        CapabilityCache instance
    """
    global _capability_cache
    if _capability_cache is None:
        _capability_cache = CapabilityCache(cache_file, ttl)
    return _capability_cache