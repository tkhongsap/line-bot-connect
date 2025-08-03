"""
Intelligent API Routing for Azure OpenAI

This module provides intelligent routing decisions between Azure OpenAI Responses API 
and Chat Completions API based on capability detection and configuration preferences.
"""

import logging
import time
from enum import Enum
from typing import Dict, Optional, Any, Tuple
from dataclasses import dataclass

from src.config.centralized_config import get_config
from src.utils.azure_api_detector import AzureOpenAICapabilityDetector
from src.utils.capability_cache import get_capability_cache

logger = logging.getLogger(__name__)


class APIType(Enum):
    """Available Azure OpenAI API types"""
    RESPONSES_API = "responses_api"
    CHAT_COMPLETIONS = "chat_completions"


@dataclass
class RoutingDecision:
    """Represents a routing decision with metadata"""
    api_type: APIType
    reason: str
    confidence: float  # 0.0 to 1.0
    fallback_available: bool
    estimated_success_rate: float  # 0.0 to 1.0
    routing_time_ms: float


class APIRouter:
    """
    Intelligent router for Azure OpenAI API endpoints.
    
    Makes routing decisions based on:
    - API capability detection results
    - Configuration preferences
    - Historical success rates
    - Current system state
    """
    
    def __init__(self, settings=None, capability_detector=None, capability_cache=None):
        """
        Initialize the API router.
        
        Args:
            settings: Configuration settings (defaults to centralized config)
            capability_detector: Capability detector instance
            capability_cache: Capability cache instance
        """
        self.settings = settings or get_config()
        self.capability_detector = capability_detector
        self.capability_cache = capability_cache or get_capability_cache(
            ttl=self.settings.azure_openai.capability_cache_ttl
        )
        
        # Success rate tracking for adaptive routing
        self.success_rates = {
            APIType.RESPONSES_API: 0.95,  # Start optimistic
            APIType.CHAT_COMPLETIONS: 0.98  # Chat completions generally more stable
        }
        
        # Request tracking for success rate calculation
        self.request_history = {
            APIType.RESPONSES_API: {'total': 0, 'successful': 0},
            APIType.CHAT_COMPLETIONS: {'total': 0, 'successful': 0}
        }
        
        logger.info("Initialized intelligent API router")
    
    async def decide_api_route(self, force_refresh_capabilities: bool = False) -> RoutingDecision:
        """
        Decide which API to use for the current request.
        
        Args:
            force_refresh_capabilities: Force refresh of capability detection
            
        Returns:
            RoutingDecision with routing choice and metadata
        """
        start_time = time.time()
        
        try:
            # Get current capabilities
            capabilities = await self._get_current_capabilities(force_refresh_capabilities)
            
            # Apply configuration overrides first
            if self.settings.azure_openai.force_chat_completions:
                decision = RoutingDecision(
                    api_type=APIType.CHAT_COMPLETIONS,
                    reason="Configuration forces Chat Completions API",
                    confidence=1.0,
                    fallback_available=False,
                    estimated_success_rate=self.success_rates[APIType.CHAT_COMPLETIONS],
                    routing_time_ms=(time.time() - start_time) * 1000
                )
                logger.info(f"Routing decision (forced): {decision.api_type.value} - {decision.reason}")
                return decision
            
            # Check Responses API availability and preference
            responses_available = capabilities.get('responses_api_available', False)
            chat_available = capabilities.get('chat_completions_available', True)
            
            if responses_available and self.settings.azure_openai.prefer_responses_api:
                # Check success rate threshold
                responses_success_rate = self.success_rates[APIType.RESPONSES_API]
                
                if responses_success_rate >= 0.8:  # 80% success threshold
                    decision = RoutingDecision(
                        api_type=APIType.RESPONSES_API,
                        reason=f"Responses API available and preferred (success rate: {responses_success_rate:.1%})",
                        confidence=0.9,
                        fallback_available=chat_available,
                        estimated_success_rate=responses_success_rate,
                        routing_time_ms=(time.time() - start_time) * 1000
                    )
                else:
                    decision = RoutingDecision(
                        api_type=APIType.CHAT_COMPLETIONS,
                        reason=f"Responses API success rate too low ({responses_success_rate:.1%}), using Chat Completions",
                        confidence=0.8,
                        fallback_available=False,
                        estimated_success_rate=self.success_rates[APIType.CHAT_COMPLETIONS],
                        routing_time_ms=(time.time() - start_time) * 1000
                    )
            
            elif chat_available:
                decision = RoutingDecision(
                    api_type=APIType.CHAT_COMPLETIONS,
                    reason="Chat Completions API available" + (" (Responses API unavailable)" if not responses_available else " (not preferred)"),
                    confidence=0.95,
                    fallback_available=False,
                    estimated_success_rate=self.success_rates[APIType.CHAT_COMPLETIONS],
                    routing_time_ms=(time.time() - start_time) * 1000
                )
            
            else:
                # Emergency fallback - should not happen with proper capability detection
                decision = RoutingDecision(
                    api_type=APIType.CHAT_COMPLETIONS,
                    reason="Emergency fallback - no APIs detected as available",
                    confidence=0.3,
                    fallback_available=False,
                    estimated_success_rate=0.5,
                    routing_time_ms=(time.time() - start_time) * 1000
                )
                logger.warning("No APIs detected as available, using emergency fallback")
            
            logger.info(f"Routing decision: {decision.api_type.value} - {decision.reason} (confidence: {decision.confidence:.1%})")
            return decision
            
        except Exception as e:
            # Error fallback
            decision = RoutingDecision(
                api_type=APIType.CHAT_COMPLETIONS,
                reason=f"Routing error, using safe fallback: {e}",
                confidence=0.1,
                fallback_available=False,
                estimated_success_rate=0.8,
                routing_time_ms=(time.time() - start_time) * 1000
            )
            logger.error(f"API routing error: {e}, using fallback")
            return decision
    
    async def _get_current_capabilities(self, force_refresh: bool = False) -> Dict[str, bool]:
        """Get current API capabilities from cache or detection"""
        try:
            # Try cache first unless force refresh
            if not force_refresh:
                cached_capabilities = await self.capability_cache.get_capabilities()
                if cached_capabilities:
                    logger.debug("Using cached capabilities for routing")
                    return cached_capabilities
            
            # Use detector if available
            if self.capability_detector:
                logger.debug("Running fresh capability detection for routing")
                capabilities = await self.capability_detector.detect_capabilities(force_refresh=True)
                await self.capability_cache.set_capabilities(capabilities)
                return capabilities
            
            # Conservative fallback
            logger.warning("No capability detector available, using conservative defaults")
            return {
                'responses_api_available': False,
                'chat_completions_available': True,
                'models_endpoint_available': False,
                'deployment_accessible': True
            }
            
        except Exception as e:
            logger.error(f"Error getting capabilities: {e}")
            # Conservative fallback
            return {
                'responses_api_available': False,
                'chat_completions_available': True,
                'models_endpoint_available': False,
                'deployment_accessible': True
            }
    
    def record_request_result(self, api_type: APIType, success: bool):
        """
        Record the result of an API request for success rate tracking.
        
        Args:
            api_type: Which API was used
            success: Whether the request was successful
        """
        history = self.request_history[api_type]
        history['total'] += 1
        if success:
            history['successful'] += 1
        
        # Update success rate (weighted moving average)
        if history['total'] > 0:
            current_rate = history['successful'] / history['total']
            # Weight recent results more heavily
            weight = 0.8 if history['total'] < 10 else 0.9
            self.success_rates[api_type] = (weight * self.success_rates[api_type] + 
                                          (1 - weight) * current_rate)
        
        logger.debug(f"Updated {api_type.value} success rate: {self.success_rates[api_type]:.1%} "
                    f"({history['successful']}/{history['total']})")
    
    def get_routing_stats(self) -> Dict[str, Any]:
        """Get detailed routing statistics"""
        return {
            'success_rates': {api.value: rate for api, rate in self.success_rates.items()},
            'request_history': {
                api.value: {
                    'total': history['total'],
                    'successful': history['successful'],
                    'success_rate': history['successful'] / max(history['total'], 1)
                } for api, history in self.request_history.items()
            },
            'configuration': {
                'prefer_responses_api': self.settings.azure_openai.prefer_responses_api,
                'force_chat_completions': self.settings.azure_openai.force_chat_completions,
                'capability_cache_ttl': self.settings.azure_openai.capability_cache_ttl
            }
        }
    
    def reset_statistics(self):
        """Reset all routing statistics"""
        self.success_rates = {
            APIType.RESPONSES_API: 0.95,
            APIType.CHAT_COMPLETIONS: 0.98
        }
        self.request_history = {
            APIType.RESPONSES_API: {'total': 0, 'successful': 0},
            APIType.CHAT_COMPLETIONS: {'total': 0, 'successful': 0}
        }
        logger.info("Reset routing statistics")
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform a health check of the routing system"""
        start_time = time.time()
        
        try:
            # Test capability detection
            capabilities = await self._get_current_capabilities(force_refresh=False)
            
            # Test routing decision
            decision = await self.decide_api_route(force_refresh=False)
            
            health_time = (time.time() - start_time) * 1000
            
            return {
                'status': 'healthy',
                'capabilities': capabilities,
                'routing_decision': {
                    'api_type': decision.api_type.value,
                    'reason': decision.reason,
                    'confidence': decision.confidence
                },
                'statistics': self.get_routing_stats(),
                'health_check_time_ms': health_time
            }
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'health_check_time_ms': (time.time() - start_time) * 1000
            }


# Global router instance
_api_router: Optional[APIRouter] = None


def get_api_router(settings=None, capability_detector=None, capability_cache=None) -> APIRouter:
    """
    Get or create the global API router instance.
    
    Args:
        settings: Configuration settings
        capability_detector: Capability detector instance
        capability_cache: Capability cache instance
        
    Returns:
        APIRouter instance
    """
    global _api_router
    if _api_router is None:
        _api_router = APIRouter(settings, capability_detector, capability_cache)
    return _api_router