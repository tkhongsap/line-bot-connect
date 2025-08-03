"""
Unit tests for Azure OpenAI API capability detection.

Tests comprehensive scenarios including 404 errors, successful API calls,
timeouts, and various Azure OpenAI deployment configurations.
"""

import pytest
import asyncio
import json
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
from pathlib import Path

from src.utils.azure_api_detector import AzureOpenAICapabilityDetector
from src.exceptions.azure_openai_exceptions import (
    FeatureNotEnabledError, 
    DeploymentNotFoundError,
    AuthenticationFailedError,
    QuotaExceededError,
    APICapabilityError
)
from src.config.centralized_config import get_config


class TestAzureAPIDetector:
    """Test suite for Azure OpenAI API capability detection."""
    
    @pytest.fixture
    def mock_config(self):
        """Mock centralized configuration."""
        config = Mock()
        config.azure_openai.capability_cache_ttl = 300
        config.azure_openai.enable_startup_validation = True
        config.azure_openai.api_timeout = 30
        config.azure_openai.max_retries = 3
        return config
    
    @pytest.fixture
    def detector(self, mock_config):
        """Create detector instance with mocked config."""
        return AzureOpenAICapabilityDetector(settings=mock_config)
    
    @pytest.fixture
    def mock_openai_client(self):
        """Mock Azure OpenAI client."""
        client = Mock()
        client.chat = Mock()
        client.chat.completions = Mock()
        return client

    @pytest.mark.asyncio
    async def test_responses_api_available(self, detector, mock_openai_client):
        """Test successful Responses API detection."""
        # Mock successful Responses API call
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.usage = Mock()
        
        mock_openai_client.chat.completions.create = AsyncMock(return_value=mock_response)
        
        # Test detection
        result = await detector.detect_responses_api_availability(mock_openai_client)
        
        assert result is True
        mock_openai_client.chat.completions.create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_responses_api_404_error(self, detector, mock_openai_client):
        """Test Responses API 404 error detection."""
        # Mock 404 error from Azure OpenAI
        from openai import NotFoundError
        mock_openai_client.chat.completions.create = AsyncMock(
            side_effect=NotFoundError("The requested resource was not found", response=None, body=None)
        )
        
        # Test detection
        result = await detector.detect_responses_api_availability(mock_openai_client)
        
        assert result is False
        mock_openai_client.chat.completions.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_responses_api_authentication_error(self, detector, mock_openai_client):
        """Test Responses API authentication error handling."""
        from openai import AuthenticationError
        mock_openai_client.chat.completions.create = AsyncMock(
            side_effect=AuthenticationError("Invalid API key", response=None, body=None)
        )
        
        # Test detection - should raise structured exception
        with pytest.raises(AuthenticationFailedError) as exc_info:
            await detector.detect_responses_api_availability(mock_openai_client)
        
        assert "Invalid API key" in str(exc_info.value)
        assert exc_info.value.correlation_id is not None

    @pytest.mark.asyncio
    async def test_responses_api_quota_exceeded(self, detector, mock_openai_client):
        """Test Responses API quota exceeded error handling."""
        from openai import RateLimitError
        mock_openai_client.chat.completions.create = AsyncMock(
            side_effect=RateLimitError("Rate limit exceeded", response=None, body=None)
        )
        
        # Test detection - should raise structured exception
        with pytest.raises(QuotaExceededError) as exc_info:
            await detector.detect_responses_api_availability(mock_openai_client)
        
        assert "Rate limit exceeded" in str(exc_info.value)
        assert exc_info.value.correlation_id is not None

    @pytest.mark.asyncio
    async def test_chat_completions_fallback(self, detector, mock_openai_client):
        """Test Chat Completions API fallback detection."""
        # Mock successful Chat Completions call
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.usage = Mock()
        
        mock_openai_client.chat.completions.create = AsyncMock(return_value=mock_response)
        
        # Test detection
        result = await detector.detect_chat_completions_availability(mock_openai_client)
        
        assert result is True
        mock_openai_client.chat.completions.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_comprehensive_capability_detection(self, detector, mock_openai_client):
        """Test comprehensive capability detection across both APIs."""
        # Mock Responses API 404, Chat Completions success
        def mock_create_side_effect(*args, **kwargs):
            # Check if this is a Responses API call (has 'response_format' with specific structure)
            response_format = kwargs.get('response_format')
            if response_format and isinstance(response_format, dict):
                from openai import NotFoundError
                raise NotFoundError("Responses API not available", response=None, body=None)
            else:
                # Chat Completions API call
                mock_response = Mock()
                mock_response.choices = [Mock()]
                mock_response.choices[0].message = Mock()
                mock_response.usage = Mock()
                return mock_response
        
        mock_openai_client.chat.completions.create = AsyncMock(side_effect=mock_create_side_effect)
        
        # Test comprehensive detection
        capabilities = await detector.detect_api_capabilities(mock_openai_client)
        
        assert capabilities['responses_api'] is False
        assert capabilities['chat_completions'] is True
        assert capabilities['last_updated'] is not None
        assert capabilities['deployment_region'] is not None

    @pytest.mark.asyncio
    async def test_timeout_handling(self, detector, mock_openai_client):
        """Test timeout handling in API detection."""
        import asyncio
        
        mock_openai_client.chat.completions.create = AsyncMock(
            side_effect=asyncio.TimeoutError("Request timed out")
        )
        
        # Test timeout handling
        with pytest.raises(APICapabilityError) as exc_info:
            await detector.detect_responses_api_availability(mock_openai_client)
        
        assert "timeout" in str(exc_info.value).lower()
        assert exc_info.value.correlation_id is not None

    @pytest.mark.asyncio
    async def test_deployment_region_detection(self, detector, mock_openai_client):
        """Test deployment region detection from endpoint."""
        # Mock successful API call
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.usage = Mock()
        
        mock_openai_client.chat.completions.create = AsyncMock(return_value=mock_response)
        
        # Mock the detector's endpoint analysis
        with patch.object(detector, '_extract_region_from_endpoint', return_value='eastus'):
            capabilities = await detector.detect_api_capabilities(mock_openai_client)
        
        assert capabilities['deployment_region'] == 'eastus'

    def test_error_classification(self, detector):
        """Test proper error classification for different Azure OpenAI errors."""
        from openai import NotFoundError, AuthenticationError, RateLimitError, BadRequestError
        
        # Test 404 classification
        error_404 = NotFoundError("Resource not found", response=None, body=None)
        classified = detector._classify_openai_error(error_404)
        assert isinstance(classified, DeploymentNotFoundError)
        
        # Test authentication classification  
        error_auth = AuthenticationError("Invalid key", response=None, body=None)
        classified = detector._classify_openai_error(error_auth)
        assert isinstance(classified, AuthenticationFailedError)
        
        # Test rate limit classification
        error_rate = RateLimitError("Rate limit exceeded", response=None, body=None)
        classified = detector._classify_openai_error(error_rate)
        assert isinstance(classified, QuotaExceededError)
        
        # Test feature not enabled classification
        error_feature = BadRequestError("Feature not enabled", response=None, body=None)
        classified = detector._classify_openai_error(error_feature)
        assert isinstance(classified, FeatureNotEnabledError)

    @pytest.mark.asyncio
    async def test_cache_integration(self, detector, mock_openai_client, tmp_path):
        """Test integration with capability cache."""
        # Mock successful detection
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.usage = Mock()
        
        mock_openai_client.chat.completions.create = AsyncMock(return_value=mock_response)
        
        # Mock cache file path
        cache_file = tmp_path / "api_capabilities.json"
        
        with patch('src.utils.azure_api_detector.Path') as mock_path:
            mock_path.return_value = cache_file
            
            # Test detection with cache integration
            capabilities = await detector.detect_api_capabilities(mock_openai_client)
            
            # Verify capabilities structure
            assert 'responses_api' in capabilities
            assert 'chat_completions' in capabilities
            assert 'last_updated' in capabilities
            assert 'ttl_seconds' in capabilities
            assert capabilities['ttl_seconds'] == 300

    @pytest.mark.asyncio  
    async def test_concurrent_detection_calls(self, detector, mock_openai_client):
        """Test handling of concurrent capability detection calls."""
        # Mock delayed response to test concurrency
        async def delayed_response(*args, **kwargs):
            await asyncio.sleep(0.1)
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message = Mock()
            mock_response.usage = Mock()
            return mock_response
        
        mock_openai_client.chat.completions.create = AsyncMock(side_effect=delayed_response)
        
        # Launch multiple concurrent detection calls
        tasks = [
            detector.detect_responses_api_availability(mock_openai_client)
            for _ in range(3)
        ]
        
        results = await asyncio.gather(*tasks)
        
        # All should succeed
        assert all(result is True for result in results)
        
        # Verify API was called for each detection
        assert mock_openai_client.chat.completions.create.call_count == 3

    def test_correlation_id_propagation(self, detector):
        """Test correlation ID propagation through error handling."""
        from openai import AuthenticationError
        
        test_correlation_id = "test-correlation-123"
        error = AuthenticationError("Test error", response=None, body=None)
        
        classified_error = detector._classify_openai_error(error, correlation_id=test_correlation_id)
        
        assert classified_error.correlation_id == test_correlation_id

    @pytest.mark.asyncio
    async def test_performance_monitoring(self, detector, mock_openai_client):
        """Test performance monitoring during capability detection."""
        # Mock fast response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.usage = Mock()
        
        mock_openai_client.chat.completions.create = AsyncMock(return_value=mock_response)
        
        start_time = asyncio.get_event_loop().time()
        
        # Test detection with performance monitoring
        result = await detector.detect_responses_api_availability(mock_openai_client)
        
        end_time = asyncio.get_event_loop().time()
        duration_ms = (end_time - start_time) * 1000
        
        assert result is True
        assert duration_ms < 5000  # Should complete within 5 seconds for mocked calls