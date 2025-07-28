"""
Comprehensive Redis Fallback Tests for Phase 1 Critical Stability

This test module validates that both ConversationService and RichMessageService
handle Redis failures gracefully with automatic fallback to in-memory storage.
"""

import pytest
import time
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import redis
from redis.exceptions import ConnectionError, TimeoutError, RedisError

from src.services.conversation_service import ConversationService
from src.services.rich_message_service import RichMessageService
from src.utils.redis_manager import RedisConnectionManager, CircuitState


@pytest.mark.unit
class TestConversationServiceRedisFallback:
    """Test ConversationService Redis fallback functionality"""
    
    def setup_method(self):
        """Setup for each test method"""
        self.redis_url = "redis://localhost:6379/0"
        
    def teardown_method(self):
        """Cleanup after each test method"""
        # Reset global Redis manager state
        from src.utils.redis_manager import reset_global_manager
        reset_global_manager()
    
    @patch('src.utils.redis_manager.RedisConnectionManager')
    def test_conversation_service_redis_disabled(self, mock_redis_manager):
        """Test ConversationService works without Redis enabled"""
        service = ConversationService(enable_redis=False)
        
        # Verify Redis is disabled
        assert not service.enable_redis
        assert service.redis_manager is None
        assert not service._redis_available
        
        # Test basic functionality still works
        service.add_message("user1", "user", "Hello")
        history = service.get_conversation_history("user1")
        
        assert len(history) == 1
        assert history[0]["content"] == "Hello"
        
        # Verify no Redis manager was created
        mock_redis_manager.assert_not_called()
    
    @patch('src.services.conversation_service.get_redis_manager')
    def test_conversation_service_redis_initialization_failure(self, mock_get_manager):
        """Test ConversationService handles Redis initialization failure gracefully"""
        # Mock Redis manager to raise exception during initialization
        mock_get_manager.side_effect = Exception("Redis connection failed")
        
        # Service should initialize successfully but fall back to in-memory
        service = ConversationService(enable_redis=True)
        
        assert service.enable_redis  # Redis was requested
        assert service.redis_manager is None  # But initialization failed
        assert not service._redis_available  # So it's not available
        
        # Functionality should still work with in-memory storage
        service.add_message("user1", "user", "Test message")
        history = service.get_conversation_history("user1")
        
        assert len(history) == 1
        assert history[0]["content"] == "Test message"
    
    @patch('src.services.conversation_service.get_redis_manager')
    def test_conversation_service_redis_health_check_failure(self, mock_get_manager):
        """Test ConversationService handles Redis health check failure"""
        # Mock Redis manager that fails health check
        mock_manager = Mock(spec=RedisConnectionManager)
        mock_manager.health_check.return_value = {'is_healthy': False}
        mock_get_manager.return_value = mock_manager
        
        service = ConversationService(enable_redis=True)
        
        # Service should recognize Redis is unhealthy
        assert not service._redis_available
        
        # Operations should work with in-memory fallback
        service.add_message("user1", "user", "Fallback test")
        history = service.get_conversation_history("user1")
        
        assert len(history) == 1
        assert history[0]["content"] == "Fallback test"
    
    @patch('src.services.conversation_service.get_redis_manager')
    def test_conversation_service_redis_operation_failure(self, mock_get_manager):
        """Test ConversationService handles Redis operation failures during runtime"""
        # Mock Redis manager that initially works but then fails
        mock_manager = Mock(spec=RedisConnectionManager)
        mock_manager.health_check.side_effect = [
            {'is_healthy': True},  # Initial health check passes
            {'is_healthy': False}, # Later health checks fail
        ]
        
        # Mock execute_with_fallback to simulate Redis operation failure
        mock_manager.execute_with_fallback.return_value = None
        mock_get_manager.return_value = mock_manager
        
        service = ConversationService(enable_redis=True)
        
        # Initially Redis should be available
        assert service._redis_available
        
        # Add message - should trigger Redis failure and fallback
        service.add_message("user1", "user", "Test with Redis failure")
        
        # Verify fallback functionality works
        history = service.get_conversation_history("user1")
        assert len(history) == 1
        assert history[0]["content"] == "Test with Redis failure"
    
    @patch('src.services.conversation_service.get_redis_manager')
    def test_conversation_service_redis_recovery(self, mock_get_manager):
        """Test ConversationService recovers when Redis comes back online"""
        mock_manager = Mock(spec=RedisConnectionManager)
        
        # Initially Redis is down
        mock_manager.health_check.return_value = {'is_healthy': False}
        mock_get_manager.return_value = mock_manager
        
        service = ConversationService(enable_redis=True)
        
        # Initially Redis should be unavailable
        assert not service._redis_available
        
        # Force Redis health check - still down
        assert not service._check_redis_health()
        
        # Now simulate Redis recovery by changing the return value
        mock_manager.health_check.return_value = {'is_healthy': True}
        
        # Reset the last check time to force a new health check
        service._last_redis_check = None
        
        # Force Redis health check - now recovered
        assert service._check_redis_health()
        assert service._redis_available
    
    @patch('src.services.conversation_service.get_redis_manager')
    def test_conversation_service_data_consistency_during_fallback(self, mock_get_manager):
        """Test data consistency when switching between Redis and in-memory storage"""
        mock_manager = Mock(spec=RedisConnectionManager)
        mock_manager.health_check.return_value = {'is_healthy': True}
        
        # Mock Redis operations to simulate successful storage/retrieval
        mock_conversation_data = {
            "messages": [{"role": "user", "content": "Redis message", "message_type": "text", "metadata": {}, "timestamp": "2024-01-01T12:00:00"}],
            "created_at": "2024-01-01T12:00:00",
            "last_activity": "2024-01-01T12:00:00",
            "last_response_id": None
        }
        
        mock_manager.execute_with_fallback.side_effect = [
            mock_conversation_data,  # Successful Redis read
            True,  # Successful Redis write
        ]
        
        mock_get_manager.return_value = mock_manager
        
        service = ConversationService(enable_redis=True)
        assert service._redis_available
        
        # Add message - should use Redis
        service.add_message("user1", "user", "New message")
        
        # Verify the conversation was loaded from Redis and updated
        conv = service.conversations["user1"]
        assert len(conv["messages"]) >= 1
        
        # Verify Redis operations were called
        assert mock_manager.execute_with_fallback.call_count >= 1


@pytest.mark.unit  
class TestRichMessageServiceRedisFallback:
    """Test RichMessageService Redis fallback functionality"""
    
    def setup_method(self):
        """Setup for each test method"""
        self.mock_line_api = Mock()
        
    def teardown_method(self):
        """Cleanup after each test method"""
        from src.utils.redis_manager import reset_global_manager
        reset_global_manager()
    
    @patch('src.utils.redis_manager.RedisConnectionManager')
    def test_rich_message_service_redis_disabled(self, mock_redis_manager):
        """Test RichMessageService works without Redis enabled"""
        service = RichMessageService(
            line_bot_api=self.mock_line_api,
            enable_redis=False
        )
        
        # Verify Redis is disabled
        assert not service.enable_redis
        assert service.redis_manager is None
        assert not service._redis_available
        
        # Test rate limiting functionality works with in-memory fallback
        rate_limit = service.check_send_rate_limit("user1")
        assert rate_limit["allowed"] is True
        
        service.record_message_sent("user1")
        
        # Verify no Redis manager was created
        mock_redis_manager.assert_not_called()
    
    @patch('src.services.rich_message_service.get_redis_manager')
    def test_rich_message_service_redis_initialization_failure(self, mock_get_manager):
        """Test RichMessageService handles Redis initialization failure gracefully"""
        mock_get_manager.side_effect = Exception("Redis connection failed")
        
        service = RichMessageService(
            line_bot_api=self.mock_line_api,
            enable_redis=True
        )
        
        assert service.enable_redis  # Redis was requested
        assert service.redis_manager is None  # But initialization failed
        assert not service._redis_available  # So it's not available
        
        # Rate limiting should work with in-memory fallback
        rate_limit = service.check_send_rate_limit("user1")
        assert rate_limit["allowed"] is True
        
        service.record_message_sent("user1")
        
        # Check rate limit again - should now have cooldown
        rate_limit = service.check_send_rate_limit("user1")
        assert rate_limit["allowed"] is False
        assert rate_limit["reason"] == "cooldown"
    
    @patch('src.services.rich_message_service.get_redis_manager')
    def test_rich_message_service_content_caching_fallback(self, mock_get_manager):
        """Test content caching falls back to in-memory when Redis fails"""
        mock_manager = Mock(spec=RedisConnectionManager)
        mock_manager.health_check.return_value = {'is_healthy': False}
        mock_get_manager.return_value = mock_manager
        
        service = RichMessageService(
            line_bot_api=self.mock_line_api,
            enable_redis=True
        )
        
        # Redis should be unavailable
        assert not service._redis_available
        
        # Test content caching with in-memory fallback
        cache_key = service._get_cache_key("motivation", "template1")
        test_content = {"title": "Test Title", "content": "Test Content"}
        
        # Cache content - should use in-memory
        service._cache_content(cache_key, test_content)
        
        # Retrieve content - should use in-memory
        cached = service._get_cached_content(cache_key)
        assert cached == test_content
    
    @patch('src.services.rich_message_service.get_redis_manager')
    def test_rich_message_service_rate_limiting_redis_failure(self, mock_get_manager):
        """Test rate limiting handles Redis failures during operation"""
        mock_manager = Mock(spec=RedisConnectionManager)
        mock_manager.health_check.side_effect = [
            {'is_healthy': True},   # Initial health check passes
            {'is_healthy': False},  # Later health checks fail
        ]
        mock_manager.execute_with_fallback.return_value = None  # Redis operations fail
        mock_get_manager.return_value = mock_manager
        
        service = RichMessageService(
            line_bot_api=self.mock_line_api,
            enable_redis=True
        )
        
        # Initially Redis should be available
        assert service._redis_available
        
        # Record message sent - should trigger Redis failure and fallback
        service.record_message_sent("user1")
        
        # Check rate limit - should work with in-memory fallback
        rate_limit = service.check_send_rate_limit("user1")
        assert rate_limit["allowed"] is False  # Should be in cooldown
        assert rate_limit["reason"] == "cooldown"
    
    @patch('src.services.rich_message_service.get_redis_manager')
    def test_rich_message_service_mood_caching_fallback(self, mock_get_manager):
        """Test mood caching falls back to in-memory when Redis fails"""
        mock_manager = Mock(spec=RedisConnectionManager)
        mock_manager.health_check.return_value = {'is_healthy': False}
        mock_get_manager.return_value = mock_manager
        
        service = RichMessageService(
            line_bot_api=self.mock_line_api,
            enable_redis=True
        )
        
        # Test mood caching with in-memory fallback
        template_name = "test_template"
        mood = "energetic"
        
        # Cache mood - should use in-memory
        service._set_mood_cache(template_name, mood)
        
        # Retrieve mood - should use in-memory
        cached_mood = service._get_mood_cache(template_name)
        assert cached_mood == mood
    
    @patch('src.services.rich_message_service.get_redis_manager')
    def test_rich_message_service_health_status_with_redis_failures(self, mock_get_manager):
        """Test health status reporting handles Redis failures correctly"""
        mock_manager = Mock(spec=RedisConnectionManager)
        mock_manager.health_check.return_value = {'is_healthy': False, 'circuit_state': 'open'}
        mock_manager.get_statistics.return_value = {'total_requests': 10, 'failed_requests': 5}
        mock_get_manager.return_value = mock_manager
        
        service = RichMessageService(
            line_bot_api=self.mock_line_api,
            enable_redis=True
        )
        
        # Get health status
        health = service.health_check()
        
        assert health['service'] == 'RichMessageService'
        assert health['cache_backend'] == 'in-memory'
        assert health['redis_available'] is False
        assert 'redis_health' in health
        assert 'redis_statistics' in health


@pytest.mark.integration
class TestRedisFailoverIntegration:
    """Integration tests for Redis failover scenarios"""
    
    def setup_method(self):
        """Setup for each test method"""
        self.mock_line_api = Mock()
        
    def teardown_method(self):
        """Cleanup after each test method"""
        from src.utils.redis_manager import reset_global_manager
        reset_global_manager()
    
    @patch('src.services.conversation_service.get_redis_manager')
    @patch('src.services.rich_message_service.get_redis_manager')
    def test_both_services_handle_redis_failure_consistently(self, mock_rich_manager, mock_conv_manager):
        """Test both services handle Redis failures in a consistent manner"""
        # Mock Redis manager that fails
        mock_manager = Mock(spec=RedisConnectionManager)
        mock_manager.health_check.return_value = {'is_healthy': False}
        mock_manager.execute_with_fallback.return_value = None
        mock_conv_manager.return_value = mock_manager
        mock_rich_manager.return_value = mock_manager
        
        # Initialize both services
        conv_service = ConversationService(enable_redis=True)
        rich_service = RichMessageService(
            line_bot_api=self.mock_line_api,
            enable_redis=True
        )
        
        # Both should fall back to in-memory storage
        assert not conv_service._redis_available
        assert not rich_service._redis_available
        
        # Both should continue to function
        conv_service.add_message("user1", "user", "Test message")
        rich_service.record_message_sent("user1")
        
        # Verify functionality
        history = conv_service.get_conversation_history("user1")
        assert len(history) == 1
        
        rate_limit = rich_service.check_send_rate_limit("user1")
        assert rate_limit["allowed"] is False  # Should be in cooldown
    
    @patch('src.services.conversation_service.get_redis_manager')
    @patch('src.services.rich_message_service.get_redis_manager')
    def test_services_recover_when_redis_restored(self, mock_rich_manager, mock_conv_manager):
        """Test both services recover when Redis is restored"""
        # Create separate mock managers for each service
        mock_conv_mgr = Mock(spec=RedisConnectionManager)
        mock_rich_mgr = Mock(spec=RedisConnectionManager)
        
        # Initially Redis is down for both services
        mock_conv_mgr.health_check.return_value = {'is_healthy': False}
        mock_rich_mgr.health_check.return_value = {'is_healthy': False}
        mock_conv_manager.return_value = mock_conv_mgr
        mock_rich_manager.return_value = mock_rich_mgr
        
        # Initialize services during Redis failure
        conv_service = ConversationService(enable_redis=True)
        rich_service = RichMessageService(
            line_bot_api=self.mock_line_api,
            enable_redis=True
        )
        
        # Initially should be unavailable
        assert not conv_service._redis_available
        assert not rich_service._redis_available
        
        # Simulate Redis recovery by changing return values
        mock_conv_mgr.health_check.return_value = {'is_healthy': True}
        mock_rich_mgr.health_check.return_value = {'is_healthy': True}
        
        # Reset the last check times to force new health checks
        conv_service._last_redis_check = None
        rich_service._last_redis_check = None
        
        # Force health check - should recover
        assert conv_service._check_redis_health()
        assert rich_service._check_redis_health()
        
        # Both should now be available
        assert conv_service._redis_available
        assert rich_service._redis_available
    
    @patch('src.services.conversation_service.get_redis_manager')
    @patch('src.services.rich_message_service.get_redis_manager')
    def test_circuit_breaker_protects_both_services(self, mock_rich_manager, mock_conv_manager):
        """Test circuit breaker pattern protects both services from Redis failures"""
        mock_manager = Mock(spec=RedisConnectionManager)
        mock_manager.health_check.return_value = {'is_healthy': False}
        mock_manager.is_circuit_open.return_value = True  # Circuit is open
        mock_conv_manager.return_value = mock_manager
        mock_rich_manager.return_value = mock_manager
        
        conv_service = ConversationService(enable_redis=True)
        rich_service = RichMessageService(
            line_bot_api=self.mock_line_api,
            enable_redis=True
        )
        
        # Both services should respect the circuit breaker
        assert not conv_service._redis_available
        assert not rich_service._redis_available
        
        # Operations should still work with fallback
        conv_service.add_message("user1", "user", "Circuit breaker test")
        rich_service.record_message_sent("user1")
        
        # Verify functionality is maintained
        history = conv_service.get_conversation_history("user1")
        assert len(history) == 1
        assert history[0]["content"] == "Circuit breaker test"