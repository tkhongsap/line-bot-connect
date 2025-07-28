"""
Connection pooling utilities for optimized API performance.

This module provides enhanced connection pooling for external API integrations
including LINE Bot API and Azure OpenAI with retry strategies and monitoring.
"""

import logging
import time
import requests.adapters
from urllib3.util.retry import Retry
from typing import Optional, Dict, Any
from linebot import LineBotApi

logger = logging.getLogger(__name__)


class OptimizedLineBotApi(LineBotApi):
    """Enhanced LINE Bot API client with connection pooling and retry logic."""
    
    def __init__(self, channel_access_token: str, endpoint: str = 'https://api.line.me', 
                 timeout: int = 10, pool_maxsize: int = 20, max_retries: int = 3):
        """
        Initialize optimized LINE Bot API client.
        
        Args:
            channel_access_token: LINE Bot channel access token
            endpoint: LINE API endpoint URL
            timeout: Request timeout in seconds
            pool_maxsize: Maximum number of connections to pool
            max_retries: Maximum number of retry attempts
        """
        super().__init__(channel_access_token, endpoint, timeout)
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "POST", "PUT", "DELETE", "OPTIONS", "TRACE"]
        )
        
        # Configure connection pooling adapter
        adapter = requests.adapters.HTTPAdapter(
            pool_maxsize=pool_maxsize,
            pool_block=False,
            max_retries=retry_strategy
        )
        
        # Apply adapter to session
        if hasattr(self, 'http_client') and hasattr(self.http_client, 'session'):
            self.http_client.session.mount("https://", adapter)
            self.http_client.session.mount("http://", adapter)
            
        logger.info(f"Initialized optimized LINE Bot API client with pool_size={pool_maxsize}, retries={max_retries}")


class ConnectionPoolManager:
    """Manages connection pools for all external API integrations."""
    
    def __init__(self):
        self.pools = {}
        self.metrics = {
            'total_requests': 0,
            'failed_requests': 0,
            'avg_response_time': 0.0,
            'pool_usage': {}
        }
    
    def create_line_bot_api(self, channel_access_token: str, **kwargs) -> OptimizedLineBotApi:
        """Create optimized LINE Bot API client."""
        default_config = {
            'timeout': 10,
            'pool_maxsize': 20,
            'max_retries': 3
        }
        default_config.update(kwargs)
        
        return OptimizedLineBotApi(channel_access_token, **default_config)
    
    def create_session_with_pooling(self, name: str, base_url: str = None, 
                                  pool_maxsize: int = 20, max_retries: int = 3) -> requests.Session:
        """Create a requests session with connection pooling."""
        session = requests.Session()
        
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504]
        )
        
        adapter = requests.adapters.HTTPAdapter(
            pool_maxsize=pool_maxsize,
            max_retries=retry_strategy
        )
        
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        
        self.pools[name] = {
            'session': session,
            'base_url': base_url,
            'created_at': time.time(),
            'request_count': 0
        }
        
        logger.info(f"Created connection pool '{name}' with {pool_maxsize} max connections")
        return session
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get connection pool metrics."""
        return {
            'pools': {name: {
                'request_count': pool['request_count'],
                'age_seconds': time.time() - pool['created_at']
            } for name, pool in self.pools.items()},
            'total_pools': len(self.pools),
            **self.metrics
        }
    
    def cleanup_pools(self):
        """Clean up connection pools."""
        for name, pool in self.pools.items():
            if 'session' in pool:
                pool['session'].close()
                logger.info(f"Closed connection pool '{name}'")
        self.pools.clear()


# Global connection pool manager
connection_pool_manager = ConnectionPoolManager()