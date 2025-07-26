"""
Async HTTP utilities for external API calls
"""

import aiohttp
import asyncio
import logging
from typing import Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor
import functools

logger = logging.getLogger(__name__)

class AsyncHTTPClient:
    """Async HTTP client with connection pooling and timeout handling"""
    
    def __init__(self, timeout: int = 10, max_connections: int = 100):
        self.timeout = timeout
        self.max_connections = max_connections
        self._session = None
        self._executor = ThreadPoolExecutor(max_workers=5)
    
    async def __aenter__(self):
        """Async context manager entry"""
        connector = aiohttp.TCPConnector(
            limit=self.max_connections,
            limit_per_host=20,
            keepalive_timeout=30,
            enable_cleanup_closed=True
        )
        
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        
        self._session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={
                'User-Agent': 'LINE-Bot-Connect/1.0',
                'Accept': 'application/json, image/*'
            }
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self._session:
            await self._session.close()
        self._executor.shutdown(wait=False)
    
    async def get(self, url: str, headers: Dict[str, str] = None) -> Optional[bytes]:
        """Async GET request"""
        try:
            async with self._session.get(url, headers=headers or {}) as response:
                if response.status == 200:
                    return await response.read()
                else:
                    logger.error(f"HTTP {response.status} for {url}")
                    return None
        except asyncio.TimeoutError:
            logger.error(f"Timeout fetching {url}")
            return None
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None
    
    async def post(self, url: str, data: Any = None, json: Dict = None, headers: Dict[str, str] = None) -> Optional[Dict]:
        """Async POST request"""
        try:
            async with self._session.post(url, data=data, json=json, headers=headers or {}) as response:
                if response.content_type == 'application/json':
                    return await response.json()
                else:
                    return {"status": response.status, "text": await response.text()}
        except asyncio.TimeoutError:
            logger.error(f"Timeout posting to {url}")
            return None
        except Exception as e:
            logger.error(f"Error posting to {url}: {e}")
            return None
    
    def run_sync(self, coro):
        """Run async function in sync context"""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're already in an event loop, use executor
                return self._run_in_executor(coro)
            else:
                return loop.run_until_complete(coro)
        except RuntimeError:
            # No event loop, create one
            return asyncio.run(coro)
    
    def _run_in_executor(self, coro):
        """Run coroutine in thread executor"""
        def run_coro():
            return asyncio.run(coro)
        
        future = self._executor.submit(run_coro)
        return future.result()

def async_to_sync(async_func):
    """Decorator to make async functions callable from sync code"""
    @functools.wraps(async_func)
    def wrapper(*args, **kwargs):
        coro = async_func(*args, **kwargs)
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Create new event loop in thread
                executor = ThreadPoolExecutor(max_workers=1)
                future = executor.submit(asyncio.run, coro)
                return future.result()
            else:
                return loop.run_until_complete(coro)
        except RuntimeError:
            return asyncio.run(coro)
    
    return wrapper

async def download_image_async(url: str, headers: Dict[str, str] = None, timeout: int = 10) -> Optional[bytes]:
    """
    Async image download utility
    
    Args:
        url: Image URL to download
        headers: Optional headers for request
        timeout: Request timeout in seconds
    
    Returns:
        Image bytes or None if failed
    """
    async with AsyncHTTPClient(timeout=timeout) as client:
        return await client.get(url, headers=headers)

# Sync wrapper for backwards compatibility
download_image_sync = async_to_sync(download_image_async)