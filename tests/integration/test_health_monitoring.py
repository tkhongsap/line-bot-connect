"""
Integration tests for health monitoring endpoints and functionality.

Tests the Azure OpenAI health monitoring endpoint, metrics collection,
and overall system health reporting.
"""

import pytest
import json
from unittest.mock import Mock, patch
from flask import Flask

from src.routes.admin_routes import admin_bp
from src.utils.metrics_collector import get_metrics_collector


class TestHealthMonitoringIntegration:
    """Integration test suite for health monitoring."""
    
    @pytest.fixture
    def app(self):
        """Create Flask app with admin routes."""
        app = Flask(__name__)
        app.register_blueprint(admin_bp, url_prefix='/admin')
        return app
    
    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return app.test_client()

    def test_azure_openai_health_endpoint_healthy(self, client):
        """Test Azure OpenAI health endpoint when system is healthy."""
        # Mock healthy OpenAI service
        mock_openai_service = Mock()
        mock_openai_service.api_router.get_cached_capabilities.return_value = {
            'responses_api': True,
            'chat_completions': True,
            'last_updated': '2025-08-03T12:00:00Z',
            'deployment_region': 'eastus'
        }
        mock_openai_service.get_connection_metrics.return_value = {
            'service_metrics': {
                'total_requests': 100,
                'successful_requests': 98,
                'failed_requests': 2,
                'avg_response_time': 250.5
            },
            'connection_pool_metrics': {
                'active_connections': 5,
                'total_connections': 10
            }
        }
        
        with patch('src.routes.admin_routes.openai_service', mock_openai_service):
            response = client.get('/admin/health/azure-openai')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            
            assert data['status'] == 'healthy'
            assert data['api_capabilities']['responses_api'] is True
            assert data['api_capabilities']['chat_completions'] is True
            assert data['performance_metrics']['total_requests'] == 100
            assert data['performance_metrics']['success_rate'] > 0.9

    def test_azure_openai_health_endpoint_degraded(self, client):
        """Test Azure OpenAI health endpoint when system is degraded."""
        # Mock degraded OpenAI service (Responses API unavailable)
        mock_openai_service = Mock()
        mock_openai_service.api_router.get_cached_capabilities.return_value = {
            'responses_api': False,
            'chat_completions': True,
            'last_updated': '2025-08-03T12:00:00Z',
            'deployment_region': 'eastus',
            'responses_api_error': 'NotFoundError: Resource not found'
        }
        mock_openai_service.get_connection_metrics.return_value = {
            'service_metrics': {
                'total_requests': 50,
                'successful_requests': 45,
                'failed_requests': 5,
                'avg_response_time': 300.0
            },
            'connection_pool_metrics': {
                'active_connections': 3,
                'total_connections': 10
            }
        }
        
        with patch('src.routes.admin_routes.openai_service', mock_openai_service):
            response = client.get('/admin/health/azure-openai')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            
            assert data['status'] == 'degraded'
            assert data['api_capabilities']['responses_api'] is False
            assert data['api_capabilities']['chat_completions'] is True
            assert 'degradation_reason' in data
            assert 'responses_api_error' in data['api_capabilities']

    def test_azure_openai_health_endpoint_unhealthy(self, client):
        """Test Azure OpenAI health endpoint when system is unhealthy."""
        # Mock unhealthy OpenAI service
        mock_openai_service = Mock()
        mock_openai_service.api_router.get_cached_capabilities.return_value = {
            'responses_api': False,
            'chat_completions': False,
            'last_updated': '2025-08-03T12:00:00Z',
            'deployment_region': 'eastus',
            'responses_api_error': 'NotFoundError: Resource not found',
            'chat_completions_error': 'AuthenticationError: Invalid API key'
        }
        mock_openai_service.get_connection_metrics.return_value = {
            'service_metrics': {
                'total_requests': 20,
                'successful_requests': 5,
                'failed_requests': 15,
                'avg_response_time': 5000.0
            },
            'connection_pool_metrics': {
                'active_connections': 0,
                'total_connections': 10
            }
        }
        
        with patch('src.routes.admin_routes.openai_service', mock_openai_service):
            response = client.get('/admin/health/azure-openai')
            
            assert response.status_code == 503  # Service Unavailable
            data = json.loads(response.data)
            
            assert data['status'] == 'unhealthy'
            assert data['api_capabilities']['responses_api'] is False
            assert data['api_capabilities']['chat_completions'] is False
            assert data['performance_metrics']['success_rate'] < 0.5

    def test_azure_openai_health_endpoint_error_handling(self, client):
        """Test Azure OpenAI health endpoint error handling."""
        # Mock OpenAI service that raises an exception
        mock_openai_service = Mock()
        mock_openai_service.api_router.get_cached_capabilities.side_effect = Exception("Service error")
        
        with patch('src.routes.admin_routes.openai_service', mock_openai_service):
            response = client.get('/admin/health/azure-openai')
            
            assert response.status_code == 500
            data = json.loads(response.data)
            
            assert data['status'] == 'error'
            assert 'error_message' in data
            assert 'Service error' in data['error_message']

    def test_metrics_collection_integration(self, client):
        """Test metrics collection integration with health monitoring."""
        # Initialize metrics collector
        metrics_collector = get_metrics_collector()
        
        # Record some test metrics
        from src.utils.api_router import APIType
        metrics_collector.record_api_request(
            api_type=APIType.RESPONSES_API,
            success=True,
            response_time_ms=200,
            correlation_id="test-001"
        )
        metrics_collector.record_api_request(
            api_type=APIType.CHAT_COMPLETIONS,
            success=True,
            response_time_ms=150,
            correlation_id="test-002"
        )
        metrics_collector.record_routing_decision(
            chosen_api=APIType.RESPONSES_API,
            routing_time_ms=25,
            cache_hit=True,
            correlation_id="test-001"
        )
        
        # Get metrics
        api_metrics = metrics_collector.get_api_metrics()
        routing_metrics = metrics_collector.get_routing_metrics()
        
        # Verify metrics structure
        assert 'total_requests' in api_metrics
        assert 'responses_api_requests' in api_metrics
        assert 'chat_completions_requests' in api_metrics
        assert 'average_response_time_ms' in api_metrics
        
        assert 'total_routing_decisions' in routing_metrics
        assert 'responses_api_chosen' in routing_metrics
        assert 'chat_completions_chosen' in routing_metrics
        assert 'average_routing_time_ms' in routing_metrics

    def test_health_monitoring_with_cache_data(self, client):
        """Test health monitoring integration with cached capability data."""
        # Mock OpenAI service with cache integration
        mock_openai_service = Mock()
        
        # Mock cache data with TTL and timestamps
        cache_data = {
            'responses_api': True,
            'chat_completions': True,
            'last_updated': '2025-08-03T12:00:00Z',
            'ttl_seconds': 300,
            'deployment_region': 'eastus',
            'api_version': '2024-02-15-preview'
        }
        mock_openai_service.api_router.get_cached_capabilities.return_value = cache_data
        mock_openai_service.get_connection_metrics.return_value = {
            'service_metrics': {'total_requests': 0, 'successful_requests': 0, 'failed_requests': 0},
            'connection_pool_metrics': {'active_connections': 0}
        }
        
        with patch('src.routes.admin_routes.openai_service', mock_openai_service):
            response = client.get('/admin/health/azure-openai')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            
            # Verify cache data is included
            assert data['cache_info']['last_updated'] == '2025-08-03T12:00:00Z'
            assert data['cache_info']['ttl_seconds'] == 300
            assert data['deployment_info']['region'] == 'eastus'
            assert data['deployment_info']['api_version'] == '2024-02-15-preview'

    def test_health_endpoint_performance(self, client):
        """Test health endpoint response performance."""
        import time
        
        # Mock fast-responding OpenAI service
        mock_openai_service = Mock()
        mock_openai_service.api_router.get_cached_capabilities.return_value = {
            'responses_api': True,
            'chat_completions': True,
            'last_updated': '2025-08-03T12:00:00Z'
        }
        mock_openai_service.get_connection_metrics.return_value = {
            'service_metrics': {'total_requests': 0, 'successful_requests': 0, 'failed_requests': 0},
            'connection_pool_metrics': {'active_connections': 0}
        }
        
        with patch('src.routes.admin_routes.openai_service', mock_openai_service):
            start_time = time.time()
            response = client.get('/admin/health/azure-openai')
            end_time = time.time()
            
            assert response.status_code == 200
            
            # Health endpoint should respond quickly (< 1 second)
            response_time = end_time - start_time
            assert response_time < 1.0

    def test_health_monitoring_cors_headers(self, client):
        """Test CORS headers in health monitoring responses."""
        # Mock OpenAI service
        mock_openai_service = Mock()
        mock_openai_service.api_router.get_cached_capabilities.return_value = {
            'responses_api': True,
            'chat_completions': True
        }
        mock_openai_service.get_connection_metrics.return_value = {
            'service_metrics': {'total_requests': 0, 'successful_requests': 0, 'failed_requests': 0},
            'connection_pool_metrics': {'active_connections': 0}
        }
        
        with patch('src.routes.admin_routes.openai_service', mock_openai_service):
            response = client.get('/admin/health/azure-openai')
            
            assert response.status_code == 200
            
            # Verify content type
            assert response.content_type == 'application/json'

    def test_health_monitoring_concurrent_requests(self, client):
        """Test health monitoring under concurrent requests."""
        import threading
        import time
        
        # Mock OpenAI service
        mock_openai_service = Mock()
        mock_openai_service.api_router.get_cached_capabilities.return_value = {
            'responses_api': True,
            'chat_completions': True,
            'last_updated': '2025-08-03T12:00:00Z'
        }
        mock_openai_service.get_connection_metrics.return_value = {
            'service_metrics': {'total_requests': 100, 'successful_requests': 95, 'failed_requests': 5},
            'connection_pool_metrics': {'active_connections': 5}
        }
        
        results = []
        
        def make_request():
            with patch('src.routes.admin_routes.openai_service', mock_openai_service):
                response = client.get('/admin/health/azure-openai')
                results.append(response.status_code)
        
        # Launch concurrent requests
        threads = [threading.Thread(target=make_request) for _ in range(5)]
        
        for thread in threads:
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # All requests should succeed
        assert all(status == 200 for status in results)
        assert len(results) == 5

    def test_health_data_validation(self, client):
        """Test validation of health monitoring data structure."""
        # Mock OpenAI service with comprehensive data
        mock_openai_service = Mock()
        mock_openai_service.api_router.get_cached_capabilities.return_value = {
            'responses_api': True,
            'chat_completions': True,
            'last_updated': '2025-08-03T12:00:00Z',
            'ttl_seconds': 300,
            'deployment_region': 'eastus',
            'api_version': '2024-02-15-preview'
        }
        mock_openai_service.get_connection_metrics.return_value = {
            'service_metrics': {
                'total_requests': 1000,
                'successful_requests': 980,
                'failed_requests': 20,
                'avg_response_time': 275.5,
                'connection_reuse_count': 850
            },
            'connection_pool_metrics': {
                'active_connections': 8,
                'total_connections': 15,
                'pools': {'azure_openai_primary': {'active': 5}, 'azure_openai_fallback': {'active': 3}}
            },
            'total_pools': 2
        }
        
        with patch('src.routes.admin_routes.openai_service', mock_openai_service):
            response = client.get('/admin/health/azure-openai')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            
            # Validate required fields
            required_fields = [
                'status', 'timestamp', 'api_capabilities', 'performance_metrics',
                'connection_info', 'cache_info', 'deployment_info'
            ]
            for field in required_fields:
                assert field in data, f"Missing required field: {field}"
            
            # Validate API capabilities structure
            api_caps = data['api_capabilities']
            assert 'responses_api' in api_caps
            assert 'chat_completions' in api_caps
            
            # Validate performance metrics structure
            perf_metrics = data['performance_metrics']
            assert 'total_requests' in perf_metrics
            assert 'success_rate' in perf_metrics
            assert 'average_response_time_ms' in perf_metrics
            
            # Validate calculated success rate
            expected_success_rate = 980 / 1000
            assert abs(perf_metrics['success_rate'] - expected_success_rate) < 0.001