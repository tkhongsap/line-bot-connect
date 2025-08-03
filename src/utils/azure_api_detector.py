"""
Azure OpenAI API Capability Detection

This module provides capability detection for Azure OpenAI APIs, allowing the application
to intelligently route requests based on available features and endpoints.
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, Any
import httpx
from dataclasses import dataclass

from src.config.centralized_config import get_config

logger = logging.getLogger(__name__)


@dataclass
class APICapability:
    """Represents the capability of a specific API endpoint"""
    available: bool
    last_checked: datetime
    error_message: Optional[str] = None
    response_time_ms: Optional[float] = None


class AzureOpenAICapabilityDetector:
    """
    Detects Azure OpenAI API capabilities and caches results with TTL management.
    
    This class tests various Azure OpenAI endpoints to determine which APIs are available
    and routes requests accordingly to eliminate 404 errors.
    """
    
    def __init__(self, settings=None, cache_ttl: int = 300):
        """
        Initialize the capability detector.
        
        Args:
            settings: Configuration settings (defaults to centralized config)
            cache_ttl: Cache time-to-live in seconds (defaults to 300)
        """
        self.settings = settings or get_config()
        self.cache_ttl = cache_ttl
        self.capabilities: Dict[str, APICapability] = {}
        self.last_full_check: Optional[datetime] = None
        
        # HTTP client configuration
        self.timeout = httpx.Timeout(10.0, connect=5.0)
        self.client = None
        
        logger.info(f"Initialized AzureOpenAICapabilityDetector with TTL={cache_ttl}s")
    
    async def __aenter__(self):
        """Async context manager entry"""
        self.client = httpx.AsyncClient(timeout=self.timeout)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.client:
            await self.client.aclose()
    
    def _is_cache_valid(self, capability_name: str) -> bool:
        """Check if cached capability is still valid based on TTL"""
        if capability_name not in self.capabilities:
            return False
            
        capability = self.capabilities[capability_name]
        age = datetime.now() - capability.last_checked
        return age.total_seconds() < self.cache_ttl
    
    async def detect_capabilities(self, force_refresh: bool = False) -> Dict[str, bool]:
        """
        Detect available Azure OpenAI API capabilities.
        
        Args:
            force_refresh: Force refresh cache regardless of TTL
            
        Returns:
            Dict mapping capability names to availability status
        """
        logger.info("Starting Azure OpenAI capability detection")
        start_time = time.time()
        
        try:
            # Check if we can use cached results
            if not force_refresh and self._is_full_cache_valid():
                logger.info("Using cached capability results")
                return {name: cap.available for name, cap in self.capabilities.items()}
            
            async with self:
                # Test all endpoints concurrently
                tasks = {
                    'responses_api_available': self._test_responses_api(),
                    'chat_completions_available': self._test_chat_completions(),
                    'models_endpoint_available': self._test_models_endpoint(),
                    'deployment_accessible': self._test_deployment_access()
                }
                
                results = await asyncio.gather(*tasks.values(), return_exceptions=True)
                
                # Process results
                capabilities = {}
                for i, (name, task) in enumerate(tasks.items()):
                    if isinstance(results[i], Exception):
                        logger.error(f"Error testing {name}: {results[i]}")
                        capabilities[name] = False
                        self.capabilities[name] = APICapability(
                            available=False,
                            last_checked=datetime.now(),
                            error_message=str(results[i])
                        )
                    else:
                        capabilities[name] = results[i]
                
                self.last_full_check = datetime.now()
                
                detection_time = (time.time() - start_time) * 1000
                logger.info(f"Capability detection completed in {detection_time:.1f}ms: {capabilities}")
                
                return capabilities
                
        except Exception as e:
            logger.error(f"Capability detection failed: {e}")
            # Return conservative fallback - only chat completions available
            return {
                'responses_api_available': False,
                'chat_completions_available': True,
                'models_endpoint_available': False,
                'deployment_accessible': True
            }
    
    def _is_full_cache_valid(self) -> bool:
        """Check if the full cache is still valid"""
        if not self.last_full_check:
            return False
        
        age = datetime.now() - self.last_full_check
        return age.total_seconds() < self.cache_ttl
    
    async def _test_responses_api(self) -> bool:
        """Test Azure OpenAI Responses API availability"""
        if not self.client:
            raise RuntimeError("HTTP client not initialized. Use within async context manager.")
            
        try:
            start_time = time.time()
            endpoint = f"{self.settings.azure_openai.endpoint.rstrip('/')}/openai/v1/responses"
            
            # Make a minimal test request to check if endpoint exists
            headers = {
                "api-key": self.settings.azure_openai.api_key.get_secret_value(),
                "Content-Type": "application/json"
            }
            
            # Use a minimal test payload
            test_payload = {
                "model": self.settings.azure_openai.deployment_name,
                "messages": [{"role": "user", "content": "test"}],
                "max_tokens": 1
            }
            
            params = {"api-version": "preview"}
            
            response = await self.client.post(
                endpoint,
                json=test_payload,
                headers=headers,
                params=params
            )
            
            response_time = (time.time() - start_time) * 1000
            is_available = response.status_code != 404
            
            self.capabilities['responses_api_available'] = APICapability(
                available=is_available,
                last_checked=datetime.now(),
                response_time_ms=response_time,
                error_message=None if is_available else f"HTTP {response.status_code}"
            )
            
            logger.info(f"Responses API test: available={is_available}, response_time={response_time:.1f}ms")
            return is_available
            
        except Exception as e:
            logger.warning(f"Responses API test failed: {e}")
            self.capabilities['responses_api_available'] = APICapability(
                available=False,
                last_checked=datetime.now(),
                error_message=str(e)
            )
            return False
    
    async def _test_chat_completions(self) -> bool:
        """Test Azure OpenAI Chat Completions API availability"""
        if not self.client:
            raise RuntimeError("HTTP client not initialized. Use within async context manager.")
            
        try:
            start_time = time.time()
            endpoint = f"{self.settings.azure_openai.endpoint.rstrip('/')}/openai/deployments/{self.settings.azure_openai.deployment_name}/chat/completions"
            
            headers = {
                "api-key": self.settings.azure_openai.api_key.get_secret_value(),
                "Content-Type": "application/json"
            }
            
            test_payload = {
                "messages": [{"role": "user", "content": "test"}],
                "max_tokens": 1
            }
            
            params = {"api-version": self.settings.azure_openai.api_version}
            
            response = await self.client.post(
                endpoint,
                json=test_payload,
                headers=headers,
                params=params
            )
            
            response_time = (time.time() - start_time) * 1000
            is_available = response.status_code in [200, 400, 429]  # 400 is OK for test payload
            
            self.capabilities['chat_completions_available'] = APICapability(
                available=is_available,
                last_checked=datetime.now(),
                response_time_ms=response_time,
                error_message=None if is_available else f"HTTP {response.status_code}"
            )
            
            logger.info(f"Chat Completions API test: available={is_available}, response_time={response_time:.1f}ms")
            return is_available
            
        except Exception as e:
            logger.warning(f"Chat Completions API test failed: {e}")
            self.capabilities['chat_completions_available'] = APICapability(
                available=False,
                last_checked=datetime.now(),
                error_message=str(e)
            )
            return False
    
    async def _test_models_endpoint(self) -> bool:
        """Test Azure OpenAI Models endpoint as feature flag indicator"""
        if not self.client:
            raise RuntimeError("HTTP client not initialized. Use within async context manager.")
            
        try:
            start_time = time.time()
            endpoint = f"{self.settings.azure_openai.endpoint.rstrip('/')}/openai/v1/models"
            
            headers = {
                "api-key": self.settings.azure_openai.api_key.get_secret_value()
            }
            
            params = {"api-version": "preview"}
            
            response = await self.client.get(
                endpoint,
                headers=headers,
                params=params
            )
            
            response_time = (time.time() - start_time) * 1000
            is_available = response.status_code == 200
            
            self.capabilities['models_endpoint_available'] = APICapability(
                available=is_available,
                last_checked=datetime.now(),
                response_time_ms=response_time,
                error_message=None if is_available else f"HTTP {response.status_code}"
            )
            
            logger.info(f"Models endpoint test: available={is_available}, response_time={response_time:.1f}ms")
            return is_available
            
        except Exception as e:
            logger.warning(f"Models endpoint test failed: {e}")
            self.capabilities['models_endpoint_available'] = APICapability(
                available=False,
                last_checked=datetime.now(),
                error_message=str(e)
            )
            return False
    
    async def _test_deployment_access(self) -> bool:
        """Test if the configured deployment is accessible"""
        try:
            # If chat completions is available, deployment is accessible
            if 'chat_completions_available' in self.capabilities:
                deployment_accessible = self.capabilities['chat_completions_available'].available
            else:
                # Fallback test using models endpoint
                deployment_accessible = await self._test_models_endpoint()
            
            self.capabilities['deployment_accessible'] = APICapability(
                available=deployment_accessible,
                last_checked=datetime.now(),
                error_message=None if deployment_accessible else "Deployment not accessible"
            )
            
            logger.info(f"Deployment access test: available={deployment_accessible}")
            return deployment_accessible
            
        except Exception as e:
            logger.warning(f"Deployment access test failed: {e}")
            self.capabilities['deployment_accessible'] = APICapability(
                available=False,
                last_checked=datetime.now(),
                error_message=str(e)
            )
            return False
    
    def get_capability_status(self) -> Dict[str, Dict[str, Any]]:
        """Get detailed status of all capabilities including metadata"""
        status = {}
        for name, capability in self.capabilities.items():
            status[name] = {
                'available': capability.available,
                'last_checked': capability.last_checked.isoformat() if capability.last_checked else None,
                'error_message': capability.error_message,
                'response_time_ms': capability.response_time_ms,
                'cache_age_seconds': (datetime.now() - capability.last_checked).total_seconds() if capability.last_checked else None
            }
        return status
    
    def clear_cache(self):
        """Clear all cached capability data"""
        self.capabilities.clear()
        self.last_full_check = None
        logger.info("Cleared capability detection cache")
    
    async def validate_startup_capabilities(self, timeout: int = 30, max_retries: int = 3) -> Dict[str, bool]:
        """
        Validate API capabilities during application startup with retry logic.
        
        Args:
            timeout: Maximum time to wait for validation in seconds
            max_retries: Maximum number of retry attempts
            
        Returns:
            Dict of capability validation results
        """
        logger.info(f"Starting startup capability validation (timeout={timeout}s, retries={max_retries})")
        start_time = time.time()
        
        for attempt in range(max_retries + 1):
            try:
                # Run detection with timeout
                capabilities = await asyncio.wait_for(
                    self.detect_capabilities(force_refresh=True),
                    timeout=timeout
                )
                
                elapsed = time.time() - start_time
                logger.info(f"Startup validation completed in {elapsed:.1f}s on attempt {attempt + 1}: {capabilities}")
                return capabilities
                
            except asyncio.TimeoutError:
                elapsed = time.time() - start_time
                logger.warning(f"Startup validation timeout after {elapsed:.1f}s on attempt {attempt + 1}")
                
                if attempt < max_retries:
                    wait_time = min(2 ** attempt, 10)  # Exponential backoff, max 10s
                    logger.info(f"Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"Startup validation failed after {max_retries + 1} attempts")
                    # Return conservative fallback
                    return {
                        'responses_api_available': False,
                        'chat_completions_available': True,
                        'models_endpoint_available': False,
                        'deployment_accessible': True
                    }
                    
            except Exception as e:
                elapsed = time.time() - start_time
                logger.error(f"Startup validation error after {elapsed:.1f}s on attempt {attempt + 1}: {e}")
                
                if attempt < max_retries:
                    wait_time = min(2 ** attempt, 10)
                    logger.info(f"Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"Startup validation failed with errors after {max_retries + 1} attempts")
                    # Return conservative fallback
                    return {
                        'responses_api_available': False,
                        'chat_completions_available': True,
                        'models_endpoint_available': False,
                        'deployment_accessible': True
                    }
    
    async def background_refresh(self, interval: int = 300):
        """
        Background task to periodically refresh capability cache.
        
        Args:
            interval: Refresh interval in seconds
        """
        logger.info(f"Starting background capability refresh (interval={interval}s)")
        
        while True:
            try:
                await asyncio.sleep(interval)
                
                # Check if cache needs refresh
                if self._is_full_cache_valid():
                    logger.debug("Cache still valid, skipping background refresh")
                    continue
                
                logger.info("Running background capability refresh")
                await self.detect_capabilities(force_refresh=True)
                
            except asyncio.CancelledError:
                logger.info("Background refresh task cancelled")
                break
            except Exception as e:
                logger.error(f"Background refresh error: {e}")
                # Continue running even if refresh fails