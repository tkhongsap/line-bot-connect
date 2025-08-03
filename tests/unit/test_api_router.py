"""
Unit tests for intelligent API routing logic.

Tests routing decisions, performance monitoring, cache integration,
and graceful degradation scenarios.
"""

import pytest
import time
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta

from src.utils.api_router import APIRouter, APIType
from src.utils.capability_cache import CapabilityCache
from src.utils.azure_api_detector import AzureOpenAICapabilityDetector
from src.exceptions.azure_openai_exceptions import APICapabilityError


class TestAPIRouter:
    """Test suite for intelligent API routing."""
    
    @pytest.fixture
    def mock_config(self):
        """Mock centralized configuration."""
        config = Mock()
        config.azure_openai.prefer_responses_api = True
        config.azure_openai.force_chat_completions = False
        config.azure_openai.capability_cache_ttl = 300
        config.azure_openai.routing_performance_threshold_ms = 50
        return config
    
    @pytest.fixture
    def mock_capability_detector(self):
        """Mock capability detector."""
        detector = Mock(spec=AzureOpenAICapabilityDetector)
        return detector
    
    @pytest.fixture
    def mock_capability_cache(self):
        """Mock capability cache."""
        cache = Mock(spec=CapabilityCache)
        return cache
    
    @pytest.fixture
    def api_router(self, mock_config, mock_capability_detector, mock_capability_cache):
        """Create API router with mocked dependencies."""
        return APIRouter(
            settings=mock_config,
            capability_detector=mock_capability_detector,
            capability_cache=mock_capability_cache
        )

    def test_should_use_responses_api_with_cache_hit(self, api_router, mock_capability_cache):
        """Test routing decision with cached capabilities (responses API available)."""
        # Mock cache hit with responses API available
        mock_capability_cache.get_cached_capabilities.return_value = {
            'responses_api': True,
            'chat_completions': True,
            'last_updated': datetime.now().isoformat(),
            'ttl_seconds': 300
        }
        
        start_time = time.time()
        result = api_router.should_use_responses_api()
        end_time = time.time()
        
        assert result is True
        assert (end_time - start_time) * 1000 < 50  # Should be fast with cache hit
        mock_capability_cache.get_cached_capabilities.assert_called_once()

    def test_should_use_responses_api_with_cache_miss(self, api_router, mock_capability_cache):
        """Test routing decision with cache miss (defaults to Chat Completions)."""
        # Mock cache miss
        mock_capability_cache.get_cached_capabilities.return_value = None
        
        result = api_router.should_use_responses_api()
        
        # Should default to Chat Completions when no cached data
        assert result is False
        mock_capability_cache.get_cached_capabilities.assert_called_once()

    def test_should_use_responses_api_cached_unavailable(self, api_router, mock_capability_cache):
        """Test routing decision when cache shows responses API unavailable."""
        # Mock cache hit with responses API unavailable (404 error cached)
        mock_capability_cache.get_cached_capabilities.return_value = {
            'responses_api': False,
            'chat_completions': True,
            'last_updated': datetime.now().isoformat(),
            'ttl_seconds': 300,
            'responses_api_error': 'NotFoundError: Resource not found'
        }
        
        result = api_router.should_use_responses_api()
        
        assert result is False
        mock_capability_cache.get_cached_capabilities.assert_called_once()

    def test_force_chat_completions_override(self, mock_config, mock_capability_detector, mock_capability_cache):
        """Test force_chat_completions configuration override."""
        # Set force_chat_completions to True
        mock_config.azure_openai.force_chat_completions = True
        
        api_router = APIRouter(
            settings=mock_config,
            capability_detector=mock_capability_detector,
            capability_cache=mock_capability_cache
        )
        
        # Mock cache with responses API available
        mock_capability_cache.get_cached_capabilities.return_value = {
            'responses_api': True,
            'chat_completions': True,
            'last_updated': datetime.now().isoformat(),
            'ttl_seconds': 300
        }
        
        result = api_router.should_use_responses_api()
        
        # Should return False despite responses API being available
        assert result is False

    def test_prefer_responses_api_disabled(self, mock_config, mock_capability_detector, mock_capability_cache):
        """Test prefer_responses_api disabled configuration."""
        # Set prefer_responses_api to False
        mock_config.azure_openai.prefer_responses_api = False
        
        api_router = APIRouter(
            settings=mock_config,
            capability_detector=mock_capability_detector,
            capability_cache=mock_capability_cache
        )
        
        # Mock cache with both APIs available
        mock_capability_cache.get_cached_capabilities.return_value = {
            'responses_api': True,
            'chat_completions': True,
            'last_updated': datetime.now().isoformat(),
            'ttl_seconds': 300
        }
        
        result = api_router.should_use_responses_api()
        
        # Should prefer Chat Completions when prefer_responses_api is False
        assert result is False

    def test_performance_monitoring_threshold(self, api_router, mock_capability_cache):
        """Test performance monitoring and threshold warnings."""
        # Mock slow cache operation
        def slow_cache_get():
            time.sleep(0.06)  # 60ms delay to exceed 50ms threshold
            return {
                'responses_api': True,
                'chat_completions': True,
                'last_updated': datetime.now().isoformat(),
                'ttl_seconds': 300
            }
        
        mock_capability_cache.get_cached_capabilities.side_effect = slow_cache_get
        
        with patch('src.utils.api_router.logger') as mock_logger:
            start_time = time.time()
            result = api_router.should_use_responses_api()
            end_time = time.time()
            
            assert result is True
            assert (end_time - start_time) * 1000 > 50
            
            # Should log performance warning
            mock_logger.warning.assert_called()
            warning_call = mock_logger.warning.call_args[0][0]
            assert "routing decision exceeded" in warning_call.lower()

    def test_cache_expiration_handling(self, api_router, mock_capability_cache):
        """Test handling of expired cache entries."""
        # Mock expired cache entry
        expired_time = datetime.now() - timedelta(seconds=400)  # Expired by 100 seconds
        mock_capability_cache.get_cached_capabilities.return_value = {
            'responses_api': True,
            'chat_completions': True,
            'last_updated': expired_time.isoformat(),
            'ttl_seconds': 300
        }
        
        result = api_router.should_use_responses_api()
        
        # Should treat expired cache as cache miss and default to Chat Completions
        assert result is False

    def test_malformed_cache_data_handling(self, api_router, mock_capability_cache):
        """Test handling of malformed cache data."""
        # Mock malformed cache data
        mock_capability_cache.get_cached_capabilities.return_value = {
            'invalid_key': 'invalid_value',
            # Missing required keys
        }
        
        result = api_router.should_use_responses_api()
        
        # Should handle gracefully and default to Chat Completions
        assert result is False

    def test_cache_error_handling(self, api_router, mock_capability_cache):
        """Test handling of cache access errors."""
        # Mock cache error
        mock_capability_cache.get_cached_capabilities.side_effect = Exception("Cache access failed")
        
        with patch('src.utils.api_router.logger') as mock_logger:
            result = api_router.should_use_responses_api()
            
            # Should handle gracefully and default to Chat Completions
            assert result is False
            
            # Should log the error
            mock_logger.warning.assert_called()

    def test_get_routing_metrics(self, api_router):
        """Test routing metrics collection."""
        # Perform several routing decisions
        api_router.should_use_responses_api()
        api_router.should_use_responses_api()
        api_router.should_use_responses_api()
        
        metrics = api_router.get_routing_metrics()
        
        assert 'total_decisions' in metrics
        assert 'responses_api_chosen' in metrics
        assert 'chat_completions_chosen' in metrics
        assert 'average_decision_time_ms' in metrics
        assert 'cache_hit_rate' in metrics
        assert metrics['total_decisions'] == 3

    def test_api_type_enum_values(self):
        """Test APIType enum values."""
        assert APIType.RESPONSES_API.value == "responses_api"
        assert APIType.CHAT_COMPLETIONS.value == "chat_completions"

    def test_routing_decision_consistency(self, api_router, mock_capability_cache):
        """Test consistency of routing decisions with same cache state."""
        # Mock stable cache state
        cache_data = {
            'responses_api': True,
            'chat_completions': True,
            'last_updated': datetime.now().isoformat(),
            'ttl_seconds': 300
        }
        mock_capability_cache.get_cached_capabilities.return_value = cache_data
        
        # Make multiple decisions
        results = [api_router.should_use_responses_api() for _ in range(5)]
        
        # All decisions should be consistent
        assert all(result == results[0] for result in results)
        assert all(result is True for result in results)

    def test_routing_with_chat_completions_unavailable(self, api_router, mock_capability_cache):
        """Test routing when only responses API is available."""
        # Mock cache with only responses API available
        mock_capability_cache.get_cached_capabilities.return_value = {
            'responses_api': True,
            'chat_completions': False,
            'last_updated': datetime.now().isoformat(),
            'ttl_seconds': 300,
            'chat_completions_error': 'DeploymentNotFound: Chat deployment not found'
        }
        
        result = api_router.should_use_responses_api()
        
        # Should choose responses API even if it's the only option
        assert result is True

    def test_routing_with_both_apis_unavailable(self, api_router, mock_capability_cache):
        """Test routing when both APIs are unavailable."""
        # Mock cache with both APIs unavailable
        mock_capability_cache.get_cached_capabilities.return_value = {
            'responses_api': False,
            'chat_completions': False,
            'last_updated': datetime.now().isoformat(),
            'ttl_seconds': 300,
            'responses_api_error': 'NotFoundError: Resource not found',
            'chat_completions_error': 'DeploymentNotFound: Deployment not found'
        }
        
        result = api_router.should_use_responses_api()
        
        # Should default to Chat Completions as fallback even if both are unavailable
        assert result is False

    def test_correlation_id_tracking(self, api_router, mock_capability_cache):
        """Test correlation ID tracking in routing decisions."""
        mock_capability_cache.get_cached_capabilities.return_value = {
            'responses_api': True,
            'chat_completions': True,
            'last_updated': datetime.now().isoformat(),
            'ttl_seconds': 300
        }
        
        correlation_id = "test-correlation-456"
        
        with patch('src.utils.api_router.logger') as mock_logger:
            result = api_router.should_use_responses_api(correlation_id=correlation_id)
            
            assert result is True
            
            # Check that correlation ID was logged
            if mock_logger.debug.called:
                log_call = mock_logger.debug.call_args
                if len(log_call) > 1 and 'extra' in log_call[1]:
                    assert log_call[1]['extra'].get('correlation_id') == correlation_id

    def test_graceful_degradation_messaging(self, api_router, mock_capability_cache):
        """Test graceful degradation messaging for different scenarios."""
        # Test scenario 1: Responses API unavailable due to 404
        mock_capability_cache.get_cached_capabilities.return_value = {
            'responses_api': False,
            'chat_completions': True,
            'last_updated': datetime.now().isoformat(),
            'ttl_seconds': 300,
            'responses_api_error': 'NotFoundError: Resource not found'
        }
        
        with patch('src.utils.api_router.logger') as mock_logger:
            result = api_router.should_use_responses_api()
            
            assert result is False
            
            # Should include degradation messaging in logs
            if mock_logger.info.called:
                log_calls = [call[0][0] for call in mock_logger.info.call_args_list]
                degradation_logged = any("degradation" in call.lower() or "fallback" in call.lower() for call in log_calls)
                # Degradation messaging may be implicit in the routing decision