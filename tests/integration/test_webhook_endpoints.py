"""
Integration tests for Flask webhook endpoints
"""
import pytest
import json
import hmac
import hashlib
import base64
from unittest.mock import Mock, patch
from app import app


@pytest.fixture
def client():
    """Create test client"""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def valid_signature():
    """Generate valid LINE webhook signature"""
    def _generate_signature(body, secret):
        hash_digest = hmac.new(
            secret.encode('utf-8'),
            body.encode('utf-8'),
            hashlib.sha256
        ).digest()
        return base64.b64encode(hash_digest).decode('utf-8')
    return _generate_signature


@pytest.mark.integration
class TestWebhookEndpoints:
    """Test Flask webhook endpoints"""
    
    def test_index_endpoint(self, client):
        """Test main dashboard endpoint"""
        response = client.get('/')
        
        assert response.status_code == 200
        assert b'LINE Bot' in response.data or b'Dashboard' in response.data
    
    def test_health_endpoint(self, client):
        """Test health check endpoint"""
        response = client.get('/health')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert data['status'] == 'healthy'
        assert 'total_conversations' in data
        assert 'services' in data
        assert data['services']['line_service'] == 'active'
        assert data['services']['openai_service'] == 'active'
        assert data['services']['conversation_service'] == 'active'
    
    def test_conversations_endpoint(self, client):
        """Test conversations statistics endpoint"""
        response = client.get('/conversations')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert 'total_users' in data
        assert 'active_conversations' in data
        assert isinstance(data['total_users'], int)
        assert isinstance(data['active_conversations'], list)
    
    def test_webhook_get_verification(self, client):
        """Test webhook GET endpoint for verification"""
        response = client.get('/webhook')
        
        assert response.status_code == 200
        assert b'Webhook endpoint is active' in response.data
    
    @patch('src.services.line_service.LineService.handle_webhook')
    def test_webhook_post_success(self, mock_handle_webhook, client, valid_signature):
        """Test successful webhook POST request"""
        # Mock successful webhook handling
        mock_handle_webhook.return_value = {'success': True}
        
        body = json.dumps({
            "events": [{
                "type": "message",
                "message": {
                    "type": "text",
                    "text": "Hello"
                }
            }]
        })
        
        # Generate valid signature
        signature = valid_signature(body, "test_secret")
        
        response = client.post('/webhook', 
                             data=body,
                             headers={'X-Line-Signature': signature,
                                    'Content-Type': 'application/json'})
        
        assert response.status_code == 200
        assert response.data == b'OK'
        mock_handle_webhook.assert_called_once()
    
    @patch('src.services.line_service.LineService.handle_webhook')
    def test_webhook_post_invalid_signature(self, mock_handle_webhook, client):
        """Test webhook POST with invalid signature"""
        # Mock failed webhook handling due to invalid signature
        mock_handle_webhook.return_value = {'success': False, 'error': 'Invalid signature'}
        
        body = json.dumps({
            "events": [{
                "type": "message",
                "message": {
                    "type": "text",
                    "text": "Hello"
                }
            }]
        })
        
        response = client.post('/webhook',
                             data=body,
                             headers={'X-Line-Signature': 'invalid_signature',
                                    'Content-Type': 'application/json'})
        
        assert response.status_code == 400
        assert response.data == b'Bad Request'
        mock_handle_webhook.assert_called_once()
    
    @patch('src.services.line_service.LineService.handle_webhook')
    def test_webhook_post_exception(self, mock_handle_webhook, client):
        """Test webhook POST with exception"""
        # Mock exception in webhook handling
        mock_handle_webhook.side_effect = Exception("Internal error")
        
        body = json.dumps({
            "events": [{
                "type": "message",
                "message": {
                    "type": "text",
                    "text": "Hello"
                }
            }]
        })
        
        response = client.post('/webhook',
                             data=body,
                             headers={'X-Line-Signature': 'signature',
                                    'Content-Type': 'application/json'})
        
        assert response.status_code == 500
        assert response.data == b'Internal Server Error'
    
    def test_webhook_post_missing_signature(self, client):
        """Test webhook POST without signature header"""
        body = json.dumps({
            "events": [{
                "type": "message",
                "message": {
                    "type": "text",
                    "text": "Hello"
                }
            }]
        })
        
        # Mock the LINE service to expect no signature
        with patch('src.services.line_service.LineService.handle_webhook') as mock_handle:
            mock_handle.return_value = {'success': False, 'error': 'Invalid signature'}
            
            response = client.post('/webhook',
                                 data=body,
                                 headers={'Content-Type': 'application/json'})
            
            assert response.status_code == 400
            # Verify empty signature was passed
            call_args = mock_handle.call_args
            assert call_args[0][0] == ''  # signature parameter
    
    def test_invalid_endpoint(self, client):
        """Test request to non-existent endpoint"""
        response = client.get('/nonexistent')
        
        assert response.status_code == 404
    
    @patch.dict('os.environ', {
        'LINE_CHANNEL_ACCESS_TOKEN': 'test_token',
        'LINE_CHANNEL_SECRET': 'test_secret',
        'AZURE_OPENAI_API_KEY': 'test_key'
    })
    def test_app_initialization_with_environment(self, client):
        """Test that app initializes properly with environment variables"""
        response = client.get('/health')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'healthy'
    
    def test_cors_headers(self, client):
        """Test that appropriate headers are set"""
        response = client.get('/health')
        
        # Should have JSON content type
        assert 'application/json' in response.headers.get('Content-Type', '')
    
    def test_webhook_content_type_handling(self, client):
        """Test webhook handles different content types"""
        body = "plain text body"
        
        with patch('src.services.line_service.LineService.handle_webhook') as mock_handle:
            mock_handle.return_value = {'success': True}
            
            # Test with different content types
            response = client.post('/webhook',
                                 data=body,
                                 headers={'X-Line-Signature': 'signature',
                                        'Content-Type': 'text/plain'})
            
            assert response.status_code == 200
            mock_handle.assert_called_once()
            # Body should be passed as string regardless of content type
            call_args = mock_handle.call_args
            assert call_args[0][1] == body
    
    def test_large_webhook_payload(self, client):
        """Test webhook handling with large payload"""
        # Create a large payload
        large_events = []
        for i in range(100):
            large_events.append({
                "type": "message",
                "message": {
                    "type": "text",
                    "text": f"Message {i} with some additional content to make it larger"
                }
            })
        
        body = json.dumps({"events": large_events})
        
        with patch('src.services.line_service.LineService.handle_webhook') as mock_handle:
            mock_handle.return_value = {'success': True}
            
            response = client.post('/webhook',
                                 data=body,
                                 headers={'X-Line-Signature': 'signature',
                                        'Content-Type': 'application/json'})
            
            assert response.status_code == 200
            mock_handle.assert_called_once()
    
    def test_concurrent_webhook_requests(self, client):
        """Test handling of concurrent webhook requests"""
        import threading
        import time
        
        results = []
        
        def make_request():
            with patch('src.services.line_service.LineService.handle_webhook') as mock_handle:
                mock_handle.return_value = {'success': True}
                
                body = json.dumps({
                    "events": [{
                        "type": "message",
                        "message": {
                            "type": "text",
                            "text": "Concurrent test"
                        }
                    }]
                })
                
                response = client.post('/webhook',
                                     data=body,
                                     headers={'X-Line-Signature': 'signature',
                                            'Content-Type': 'application/json'})
                results.append(response.status_code)
        
        # Create multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=make_request)
            threads.append(thread)
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # All requests should succeed
        assert len(results) == 5
        assert all(status == 200 for status in results)