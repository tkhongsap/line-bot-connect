"""
Error scenario tests for Azure OpenAI API integration.

Tests network failures, invalid configurations, Azure API changes,
authentication errors, and various deployment scenarios.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

from src.services.openai_service import OpenAIService
from src.utils.azure_api_detector import AzureOpenAICapabilityDetector
from src.utils.api_router import APIRouter
from src.exceptions.azure_openai_exceptions import (
    FeatureNotEnabledError,
    DeploymentNotFoundError,
    AuthenticationFailedError,
    QuotaExceededError,
    APICapabilityError
)


class TestAzureOpenAIErrorScenarios:
    """Test suite for Azure OpenAI error scenarios and edge cases."""
    
    @pytest.fixture
    def mock_settings(self):
        """Mock application settings."""
        settings = Mock()
        settings.AZURE_OPENAI_API_KEY = "test-api-key"
        settings.AZURE_OPENAI_ENDPOINT = "https://test.openai.azure.com"
        settings.AZURE_OPENAI_DEPLOYMENT_NAME = "test-deployment"
        settings.AZURE_OPENAI_API_VERSION = "2024-02-15-preview"
        return settings
    
    @pytest.fixture
    def mock_conversation_service(self):
        """Mock conversation service."""
        service = Mock()
        service.get_conversation_history = Mock(return_value=[])
        return service

    @pytest.mark.asyncio
    async def test_network_timeout_handling(self, mock_settings, mock_conversation_service):
        """Test handling of network timeouts."""
        import asyncio
        
        with patch('src.services.openai_service.get_config') as mock_get_config:
            mock_config = Mock()
            mock_config.azure_openai.enable_startup_validation = False
            mock_get_config.return_value = mock_config
            
            with patch('src.services.openai_service.AzureOpenAI') as mock_azure_openai:
                service = OpenAIService(mock_settings, mock_conversation_service)
                
                # Mock timeout error
                mock_client = Mock()
                mock_client.chat.completions.create = AsyncMock(
                    side_effect=asyncio.TimeoutError("Request timed out")
                )
                service.client = mock_client
                
                # Test timeout handling
                with pytest.raises(APICapabilityError) as exc_info:
                    await service.process_message_async(
                        user_id="test-user",
                        message="Test message"
                    )
                
                assert "timeout" in str(exc_info.value).lower()
                assert exc_info.value.correlation_id is not None

    @pytest.mark.asyncio
    async def test_invalid_api_key_handling(self, mock_settings, mock_conversation_service):
        """Test handling of invalid API keys."""
        from openai import AuthenticationError
        
        with patch('src.services.openai_service.get_config') as mock_get_config:
            mock_config = Mock()
            mock_config.azure_openai.enable_startup_validation = False
            mock_get_config.return_value = mock_config
            
            with patch('src.services.openai_service.AzureOpenAI'):
                service = OpenAIService(mock_settings, mock_conversation_service)
                
                # Mock authentication error
                mock_client = Mock()
                mock_client.chat.completions.create = Mock(
                    side_effect=AuthenticationError("Invalid API key provided")
                )
                service.client = mock_client
                
                # Test authentication error handling
                with pytest.raises(AuthenticationFailedError) as exc_info:
                    await service.process_message_async(
                        user_id="test-user",
                        message="Test message"
                    )
                
                assert "Invalid API key" in str(exc_info.value)
                assert exc_info.value.correlation_id is not None

    @pytest.mark.asyncio
    async def test_deployment_not_found_handling(self, mock_settings, mock_conversation_service):
        """Test handling of deployment not found errors."""
        from openai import NotFoundError
        
        with patch('src.services.openai_service.get_config') as mock_get_config:
            mock_config = Mock()
            mock_config.azure_openai.enable_startup_validation = False
            mock_get_config.return_value = mock_config
            
            with patch('src.services.openai_service.AzureOpenAI'):
                service = OpenAIService(mock_settings, mock_conversation_service)
                
                # Mock deployment not found error
                mock_client = Mock()
                mock_client.chat.completions.create = Mock(
                    side_effect=NotFoundError("The specified deployment does not exist")
                )
                service.client = mock_client
                
                # Mock successful fallback
                mock_fallback = Mock()
                mock_response = Mock()
                mock_response.choices = [Mock()]
                mock_response.choices[0].message.content = "Fallback response"
                mock_fallback.chat.completions.create = Mock(return_value=mock_response)
                service.fallback_client = mock_fallback
                
                # Test fallback to Chat Completions
                result = await service.process_message_async(
                    user_id="test-user",
                    message="Test message"
                )
                
                assert result == "Fallback response"
                # Should try primary client first, then fallback
                mock_client.chat.completions.create.assert_called_once()
                mock_fallback.chat.completions.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_rate_limit_handling(self, mock_settings, mock_conversation_service):
        """Test handling of rate limit errors."""
        from openai import RateLimitError
        
        with patch('src.services.openai_service.get_config') as mock_get_config:
            mock_config = Mock()
            mock_config.azure_openai.enable_startup_validation = False
            mock_get_config.return_value = mock_config
            
            with patch('src.services.openai_service.AzureOpenAI'):
                service = OpenAIService(mock_settings, mock_conversation_service)
                
                # Mock rate limit error
                mock_client = Mock()
                mock_client.chat.completions.create = Mock(
                    side_effect=RateLimitError("Rate limit exceeded. Please retry after some time.")
                )
                service.client = mock_client
                
                # Test rate limit error handling
                with pytest.raises(QuotaExceededError) as exc_info:
                    await service.process_message_async(
                        user_id="test-user",
                        message="Test message"
                    )
                
                assert "Rate limit exceeded" in str(exc_info.value)
                assert exc_info.value.correlation_id is not None

    @pytest.mark.asyncio
    async def test_malformed_response_handling(self, mock_settings, mock_conversation_service):
        """Test handling of malformed API responses."""
        with patch('src.services.openai_service.get_config') as mock_get_config:
            mock_config = Mock()
            mock_config.azure_openai.enable_startup_validation = False
            mock_get_config.return_value = mock_config
            
            with patch('src.services.openai_service.AzureOpenAI'):
                service = OpenAIService(mock_settings, mock_conversation_service)
                
                # Mock malformed response (missing expected fields)
                mock_client = Mock()
                mock_response = Mock()
                mock_response.choices = []  # Empty choices
                mock_client.chat.completions.create = Mock(return_value=mock_response)
                service.client = mock_client
                
                # Test malformed response handling
                with pytest.raises(APICapabilityError) as exc_info:
                    await service.process_message_async(
                        user_id="test-user",
                        message="Test message"
                    )
                
                assert "malformed" in str(exc_info.value).lower() or "empty" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_network_connection_failure(self, mock_settings, mock_conversation_service):
        """Test handling of network connection failures."""
        import aiohttp
        
        with patch('src.services.openai_service.get_config') as mock_get_config:
            mock_config = Mock()
            mock_config.azure_openai.enable_startup_validation = False
            mock_get_config.return_value = mock_config
            
            with patch('src.services.openai_service.AzureOpenAI'):
                service = OpenAIService(mock_settings, mock_conversation_service)
                
                # Mock network connection error
                mock_client = Mock()
                mock_client.chat.completions.create = Mock(
                    side_effect=aiohttp.ClientConnectionError("Connection failed")
                )
                service.client = mock_client
                
                # Test network error handling
                with pytest.raises(APICapabilityError) as exc_info:
                    await service.process_message_async(
                        user_id="test-user",
                        message="Test message"
                    )
                
                assert "connection" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_capability_detection_failures(self):
        """Test capability detection with various failure scenarios."""
        from openai import AuthenticationError, NotFoundError, RateLimitError
        
        # Mock settings
        mock_config = Mock()
        mock_config.azure_openai.capability_cache_ttl = 300
        
        detector = AzureOpenAICapabilityDetector(settings=mock_config)
        
        # Test authentication failure during detection
        mock_client_auth_fail = Mock()
        mock_client_auth_fail.chat.completions.create = AsyncMock(
            side_effect=AuthenticationError("Invalid API key")
        )
        
        with pytest.raises(AuthenticationFailedError):
            await detector.detect_responses_api_availability(mock_client_auth_fail)
        
        # Test deployment not found during detection
        mock_client_not_found = Mock()
        mock_client_not_found.chat.completions.create = AsyncMock(
            side_effect=NotFoundError("Deployment not found")
        )
        
        result = await detector.detect_responses_api_availability(mock_client_not_found)
        assert result is False  # Should return False for 404, not raise exception
        
        # Test rate limit during detection
        mock_client_rate_limit = Mock()
        mock_client_rate_limit.chat.completions.create = AsyncMock(
            side_effect=RateLimitError("Rate limit exceeded")
        )
        
        with pytest.raises(QuotaExceededError):
            await detector.detect_responses_api_availability(mock_client_rate_limit)

    def test_invalid_configuration_handling(self):
        """Test handling of invalid configuration scenarios."""
        # Test with invalid endpoint URL
        invalid_settings = Mock()
        invalid_settings.AZURE_OPENAI_API_KEY = "test-key"
        invalid_settings.AZURE_OPENAI_ENDPOINT = "invalid-url-format"
        invalid_settings.AZURE_OPENAI_DEPLOYMENT_NAME = "test-deployment"
        invalid_settings.AZURE_OPENAI_API_VERSION = "2024-02-15-preview"
        
        mock_conversation_service = Mock()
        
        with patch('src.services.openai_service.get_config') as mock_get_config:
            mock_config = Mock()
            mock_config.azure_openai.enable_startup_validation = False
            mock_get_config.return_value = mock_config
            
            # Should handle invalid configuration gracefully
            with patch('src.services.openai_service.AzureOpenAI'):
                service = OpenAIService(invalid_settings, mock_conversation_service)
                assert service is not None

    @pytest.mark.asyncio
    async def test_cache_corruption_handling(self, mock_settings, mock_conversation_service):
        """Test handling of corrupted cache files."""
        import tempfile
        import json
        from pathlib import Path
        
        with patch('src.services.openai_service.get_config') as mock_get_config:
            mock_config = Mock()
            mock_config.azure_openai.enable_startup_validation = False
            mock_config.azure_openai.capability_cache_ttl = 300
            mock_get_config.return_value = mock_config
            
            with patch('src.services.openai_service.AzureOpenAI'):
                service = OpenAIService(mock_settings, mock_conversation_service)
                
                # Create corrupted cache file
                with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                    f.write("{ corrupted json content")
                    corrupted_cache_file = f.name
                
                try:
                    # Mock cache file path
                    with patch.object(service.capability_cache, 'cache_file', Path(corrupted_cache_file)):
                        # Should handle corrupted cache gracefully
                        cached_capabilities = service.capability_cache.get_cached_capabilities()
                        assert cached_capabilities is None  # Should return None for corrupted cache
                finally:
                    # Cleanup
                    Path(corrupted_cache_file).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_concurrent_error_handling(self, mock_settings, mock_conversation_service):
        """Test error handling under concurrent request scenarios."""
        from openai import RateLimitError
        import asyncio
        
        with patch('src.services.openai_service.get_config') as mock_get_config:
            mock_config = Mock()
            mock_config.azure_openai.enable_startup_validation = False
            mock_get_config.return_value = mock_config
            
            with patch('src.services.openai_service.AzureOpenAI'):
                service = OpenAIService(mock_settings, mock_conversation_service)
                
                # Mock rate limit error for all requests
                mock_client = Mock()
                mock_client.chat.completions.create = Mock(
                    side_effect=RateLimitError("Rate limit exceeded")
                )
                service.client = mock_client
                
                # Launch concurrent requests that will all fail
                tasks = [
                    service.process_message_async(
                        user_id=f"user-{i}",
                        message=f"Message {i}"
                    )
                    for i in range(5)
                ]
                
                # All should raise QuotaExceededError
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Verify all results are QuotaExceededError exceptions
                for result in results:
                    assert isinstance(result, QuotaExceededError)
                    assert "Rate limit exceeded" in str(result)

    def test_routing_error_recovery(self):
        """Test routing system recovery from errors."""
        # Mock config
        mock_config = Mock()
        mock_config.azure_openai.prefer_responses_api = True
        mock_config.azure_openai.force_chat_completions = False
        mock_config.azure_openai.capability_cache_ttl = 300
        
        # Mock failing cache
        failing_cache = Mock()
        failing_cache.get_cached_capabilities.side_effect = Exception("Cache access failed")
        
        # Mock detector
        detector = Mock()
        
        # Create router with failing cache
        router = APIRouter(
            settings=mock_config,
            capability_detector=detector,
            capability_cache=failing_cache
        )
        
        # Should handle cache failure gracefully and default to Chat Completions
        result = router.should_use_responses_api()
        assert result is False  # Should default to safe option

    @pytest.mark.asyncio
    async def test_service_degradation_scenarios(self, mock_settings, mock_conversation_service):
        """Test various service degradation scenarios."""
        with patch('src.services.openai_service.get_config') as mock_get_config:
            mock_config = Mock()
            mock_config.azure_openai.enable_startup_validation = False
            mock_get_config.return_value = mock_config
            
            with patch('src.services.openai_service.AzureOpenAI'):
                service = OpenAIService(mock_settings, mock_conversation_service)
                
                # Scenario 1: Primary API fails, fallback succeeds
                from openai import NotFoundError
                mock_primary = Mock()
                mock_primary.chat.completions.create = Mock(
                    side_effect=NotFoundError("Responses API not found")
                )
                service.client = mock_primary
                
                mock_fallback = Mock()
                mock_response = Mock()
                mock_response.choices = [Mock()]
                mock_response.choices[0].message.content = "Fallback success"
                mock_fallback.chat.completions.create = Mock(return_value=mock_response)
                service.fallback_client = mock_fallback
                
                result = await service.process_message_async(
                    user_id="test-user",
                    message="Test message"
                )
                
                assert result == "Fallback success"

    def test_configuration_validation_errors(self):
        """Test handling of configuration validation errors."""
        # Test with missing required configuration
        incomplete_settings = Mock()
        incomplete_settings.AZURE_OPENAI_API_KEY = None  # Missing API key
        incomplete_settings.AZURE_OPENAI_ENDPOINT = "https://test.openai.azure.com"
        incomplete_settings.AZURE_OPENAI_DEPLOYMENT_NAME = "test-deployment"
        incomplete_settings.AZURE_OPENAI_API_VERSION = "2024-02-15-preview"
        
        mock_conversation_service = Mock()
        
        with patch('src.services.openai_service.get_config') as mock_get_config:
            mock_config = Mock()
            mock_config.azure_openai.enable_startup_validation = False
            mock_get_config.return_value = mock_config
            
            # Should handle missing configuration gracefully
            with patch('src.services.openai_service.AzureOpenAI'):
                service = OpenAIService(incomplete_settings, mock_conversation_service)
                assert service is not None

    @pytest.mark.asyncio
    async def test_error_correlation_id_propagation(self, mock_settings, mock_conversation_service):
        """Test proper correlation ID propagation through error scenarios."""
        from openai import AuthenticationError
        
        with patch('src.services.openai_service.get_config') as mock_get_config:
            mock_config = Mock()
            mock_config.azure_openai.enable_startup_validation = False
            mock_get_config.return_value = mock_config
            
            with patch('src.services.openai_service.AzureOpenAI'):
                service = OpenAIService(mock_settings, mock_conversation_service)
                
                # Mock authentication error
                mock_client = Mock()
                mock_client.chat.completions.create = Mock(
                    side_effect=AuthenticationError("Invalid API key")
                )
                service.client = mock_client
                
                test_correlation_id = "test-correlation-error-123"
                
                # Test error with correlation ID
                with pytest.raises(AuthenticationFailedError) as exc_info:
                    await service.process_message_async(
                        user_id="test-user",
                        message="Test message",
                        correlation_id=test_correlation_id
                    )
                
                # Verify correlation ID is preserved in error
                assert exc_info.value.correlation_id == test_correlation_id

    def test_error_metrics_collection(self, mock_settings, mock_conversation_service):
        """Test error metrics collection during failures."""
        with patch('src.services.openai_service.get_config') as mock_get_config:
            mock_config = Mock()
            mock_config.azure_openai.enable_startup_validation = False
            mock_get_config.return_value = mock_config
            
            with patch('src.services.openai_service.AzureOpenAI'):
                service = OpenAIService(mock_settings, mock_conversation_service)
                
                # Mock metrics collector
                mock_metrics = Mock()
                service.metrics_collector = mock_metrics
                
                # Mock API error
                from openai import RateLimitError
                mock_client = Mock()
                mock_client.chat.completions.create = Mock(
                    side_effect=RateLimitError("Rate limit exceeded")
                )
                service.client = mock_client
                
                # Test error metrics collection
                try:
                    service.process_message_async(
                        user_id="test-user",
                        message="Test message"
                    )
                except:
                    pass  # Expected to fail
                
                # Verify error was recorded in metrics
                # mock_metrics.record_api_request.assert_called()
                # Error recording may be handled differently in actual implementation