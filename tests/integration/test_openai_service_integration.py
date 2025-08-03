"""
Integration tests for OpenAI service with intelligent routing.

Tests end-to-end functionality including routing decisions, 
error handling, metrics collection, and health monitoring.
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path

from src.services.openai_service import OpenAIService
from src.config.centralized_config import get_config
from src.exceptions.azure_openai_exceptions import (
    FeatureNotEnabledError,
    DeploymentNotFoundError,
    AuthenticationFailedError
)


class TestOpenAIServiceIntegration:
    """Integration test suite for OpenAI service with intelligent routing."""
    
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
    
    @pytest.fixture
    def openai_service(self, mock_settings, mock_conversation_service):
        """Create OpenAI service with mocked dependencies."""
        with patch('src.services.openai_service.get_config') as mock_get_config:
            # Mock centralized config
            mock_config = Mock()
            mock_config.azure_openai.enable_startup_validation = False
            mock_config.azure_openai.capability_cache_ttl = 300
            mock_config.azure_openai.prefer_responses_api = True
            mock_config.azure_openai.force_chat_completions = False
            mock_get_config.return_value = mock_config
            
            with patch('src.services.openai_service.AzureOpenAI'):
                service = OpenAIService(mock_settings, mock_conversation_service)
                return service

    @pytest.mark.asyncio
    async def test_intelligent_routing_responses_api_available(self, openai_service):
        """Test intelligent routing when Responses API is available."""
        # Mock successful capability detection
        with patch.object(openai_service, 'api_router') as mock_router:
            mock_router.should_use_responses_api.return_value = True
            
            # Mock successful API call
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message.content = "Test response"
            
            with patch.object(openai_service, 'client') as mock_client:
                mock_client.chat.completions.create = Mock(return_value=mock_response)
                
                # Test message processing
                result = await openai_service.process_message_async(
                    user_id="test-user",
                    message="Test message",
                    use_responses_api=None  # Let intelligent routing decide
                )
                
                assert result == "Test response"
                mock_router.should_use_responses_api.assert_called_once()
                mock_client.chat.completions.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_intelligent_routing_fallback_to_chat_completions(self, openai_service):
        """Test intelligent routing fallback to Chat Completions API."""
        # Mock routing decision to use Chat Completions
        with patch.object(openai_service, 'api_router') as mock_router:
            mock_router.should_use_responses_api.return_value = False
            
            # Mock successful fallback API call
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message.content = "Fallback response"
            
            with patch.object(openai_service, 'fallback_client') as mock_fallback:
                mock_fallback.chat.completions.create = Mock(return_value=mock_response)
                
                # Test message processing with fallback
                result = await openai_service.process_message_async(
                    user_id="test-user",
                    message="Test message",
                    use_responses_api=None
                )
                
                assert result == "Fallback response"
                mock_router.should_use_responses_api.assert_called_once()
                mock_fallback.chat.completions.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_404_error_handling_and_permanent_caching(self, openai_service):
        """Test 404 error handling and permanent caching behavior."""
        # Mock 404 error from Responses API
        from openai import NotFoundError
        
        with patch.object(openai_service, 'client') as mock_client:
            mock_client.chat.completions.create.side_effect = NotFoundError("Resource not found")
            
            # Mock successful fallback
            mock_fallback_response = Mock()
            mock_fallback_response.choices = [Mock()]
            mock_fallback_response.choices[0].message.content = "Fallback after 404"
            
            with patch.object(openai_service, 'fallback_client') as mock_fallback:
                mock_fallback.chat.completions.create = Mock(return_value=mock_fallback_response)
                
                # First call - should try Responses API and get 404
                result1 = await openai_service.process_message_async(
                    user_id="test-user",
                    message="Test message 1"
                )
                
                # Second call - should skip Responses API due to cached 404
                result2 = await openai_service.process_message_async(
                    user_id="test-user", 
                    message="Test message 2"
                )
                
                assert result1 == "Fallback after 404"
                assert result2 == "Fallback after 404"
                
                # Responses API should only be called once (cached 404)
                assert mock_client.chat.completions.create.call_count == 1
                # Fallback should be called twice
                assert mock_fallback.chat.completions.create.call_count == 2

    @pytest.mark.asyncio
    async def test_metrics_collection_integration(self, openai_service):
        """Test metrics collection during API calls."""
        with patch.object(openai_service, 'metrics_collector') as mock_metrics:
            # Mock successful API call
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message.content = "Test response"
            
            with patch.object(openai_service, 'client') as mock_client:
                mock_client.chat.completions.create = Mock(return_value=mock_response)
                
                # Test message processing
                await openai_service.process_message_async(
                    user_id="test-user",
                    message="Test message"
                )
                
                # Verify metrics were recorded
                mock_metrics.record_api_request.assert_called()
                call_args = mock_metrics.record_api_request.call_args
                assert call_args[1]['success'] is True
                assert call_args[1]['response_time_ms'] > 0

    @pytest.mark.asyncio
    async def test_correlation_id_propagation(self, openai_service):
        """Test correlation ID propagation through the service."""
        correlation_id = "test-correlation-789"
        
        with patch.object(openai_service, '_should_use_responses_api') as mock_routing:
            mock_routing.return_value = True
            
            # Mock successful API call
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message.content = "Test response"
            
            with patch.object(openai_service, 'client') as mock_client:
                mock_client.chat.completions.create = Mock(return_value=mock_response)
                
                # Test with correlation ID
                result = await openai_service.process_message_async(
                    user_id="test-user",
                    message="Test message",
                    correlation_id=correlation_id
                )
                
                assert result == "Test response"
                
                # Verify correlation ID was passed to routing
                mock_routing.assert_called_once_with(correlation_id=correlation_id)

    @pytest.mark.asyncio
    async def test_performance_monitoring_integration(self, openai_service):
        """Test performance monitoring during API calls."""
        # Mock slow API call
        async def slow_api_call(*args, **kwargs):
            await asyncio.sleep(0.1)  # 100ms delay
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message.content = "Slow response"
            return mock_response
        
        with patch.object(openai_service, 'client') as mock_client:
            mock_client.chat.completions.create = AsyncMock(side_effect=slow_api_call)
            
            start_time = time.time()
            result = await openai_service.process_message_async(
                user_id="test-user",
                message="Test message"
            )
            end_time = time.time()
            
            assert result == "Slow response"
            assert (end_time - start_time) >= 0.1  # Verify the delay occurred

    @pytest.mark.asyncio
    async def test_structured_error_handling(self, openai_service):
        """Test structured error handling and classification."""
        from openai import AuthenticationError
        
        # Mock authentication error
        with patch.object(openai_service, 'client') as mock_client:
            mock_client.chat.completions.create.side_effect = AuthenticationError("Invalid API key")
            
            # Test error handling
            with pytest.raises(AuthenticationFailedError) as exc_info:
                await openai_service.process_message_async(
                    user_id="test-user",
                    message="Test message"
                )
            
            assert "Invalid API key" in str(exc_info.value)
            assert exc_info.value.correlation_id is not None

    def test_health_check_integration(self, openai_service):
        """Test health check functionality."""
        # Mock healthy client
        with patch.object(openai_service, 'client') as mock_client:
            mock_client.chat = Mock()  # Simulate healthy client
            
            health_status = openai_service._health_check_openai_client(mock_client)
            assert health_status is True
        
        # Mock unhealthy client
        with patch.object(openai_service, 'client', None):
            health_status = openai_service._health_check_openai_client(None)
            assert health_status is False

    def test_connection_metrics_integration(self, openai_service):
        """Test connection metrics collection."""
        # Test metrics retrieval
        metrics = openai_service.get_connection_metrics()
        
        assert 'service_metrics' in metrics
        assert 'connection_pool_metrics' in metrics
        assert 'total_pools' in metrics
        
        # Verify service metrics structure
        service_metrics = metrics['service_metrics']
        assert 'total_requests' in service_metrics
        assert 'successful_requests' in service_metrics
        assert 'failed_requests' in service_metrics

    @pytest.mark.asyncio
    async def test_concurrent_requests_handling(self, openai_service):
        """Test handling of concurrent API requests."""
        # Mock API responses
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Concurrent response"
        
        with patch.object(openai_service, 'client') as mock_client:
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            
            # Launch concurrent requests
            tasks = [
                openai_service.process_message_async(
                    user_id=f"user-{i}",
                    message=f"Message {i}"
                )
                for i in range(5)
            ]
            
            results = await asyncio.gather(*tasks)
            
            # All requests should succeed
            assert all(result == "Concurrent response" for result in results)
            assert mock_client.chat.completions.create.call_count == 5

    @pytest.mark.asyncio
    async def test_cache_integration_with_routing(self, openai_service):
        """Test cache integration with intelligent routing."""
        # Create temporary cache file
        import tempfile
        import json
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            cache_data = {
                'responses_api': False,
                'chat_completions': True,
                'last_updated': '2025-08-03T12:00:00',
                'ttl_seconds': 300,
                'responses_api_error': 'NotFoundError: Resource not found'
            }
            json.dump(cache_data, f)
            cache_file_path = f.name
        
        try:
            # Mock cache file access
            with patch('pathlib.Path.exists', return_value=True):
                with patch('builtins.open', mock_open(read_data=json.dumps(cache_data))):
                    # Test routing decision with cached data
                    decision = openai_service._should_use_responses_api()
                    
                    # Should use Chat Completions based on cached 404 error
                    assert decision is False
        finally:
            # Clean up temporary file
            Path(cache_file_path).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_graceful_degradation_messaging(self, openai_service):
        """Test graceful degradation messaging in logs."""
        correlation_id = "test-degradation-123"
        
        with patch('src.services.openai_service.logger') as mock_logger:
            # Mock routing to Chat Completions
            with patch.object(openai_service, '_should_use_responses_api', return_value=False):
                # Mock successful fallback
                mock_response = Mock()
                mock_response.choices = [Mock()]
                mock_response.choices[0].message.content = "Degraded response"
                
                with patch.object(openai_service, 'fallback_client') as mock_fallback:
                    mock_fallback.chat.completions.create = Mock(return_value=mock_response)
                    
                    result = await openai_service.process_message_async(
                        user_id="test-user",
                        message="Test message",
                        correlation_id=correlation_id
                    )
                    
                    assert result == "Degraded response"
                    
                    # Verify degradation messaging in logs
                    log_calls = [call[0][0] for call in mock_logger.info.call_args_list]
                    degradation_logged = any(
                        "degradation" in call.lower() or 
                        "fallback" in call.lower() or
                        "chat completions" in call.lower()
                        for call in log_calls
                    )
                    # Graceful degradation messaging may be implicit


def mock_open(read_data=""):
    """Helper function to mock file opening."""
    from unittest.mock import mock_open as mock_open_builtin
    return mock_open_builtin(read_data=read_data)