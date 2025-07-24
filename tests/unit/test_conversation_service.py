"""
Unit tests for Conversation service
"""
import pytest
from datetime import datetime, timedelta
from src.services.conversation_service import ConversationService


@pytest.mark.unit
class TestConversationService:
    """Test conversation service functionality"""
    
    def test_init(self):
        """Test conversation service initialization"""
        service = ConversationService()
        
        assert service.conversations == {}
        assert service.max_messages_per_user == 100
        assert service.max_total_conversations == 1000
    
    def test_add_message_new_user(self, conversation_service):
        """Test adding message for new user"""
        user_id = "new_user"
        role = "user"
        content = "Hello"
        
        conversation_service.add_message(user_id, role, content)
        
        assert user_id in conversation_service.conversations
        conv = conversation_service.conversations[user_id]
        
        assert len(conv["messages"]) == 1
        assert conv["messages"][0]["role"] == role
        assert conv["messages"][0]["content"] == content
        assert isinstance(conv["messages"][0]["timestamp"], datetime)
        assert isinstance(conv["created_at"], datetime)
        assert isinstance(conv["last_activity"], datetime)
    
    def test_add_message_existing_user(self, conversation_service):
        """Test adding message for existing user"""
        user_id = "existing_user"
        
        # Add first message
        conversation_service.add_message(user_id, "user", "First message")
        
        # Add second message
        conversation_service.add_message(user_id, "assistant", "Second message")
        
        conv = conversation_service.conversations[user_id]
        assert len(conv["messages"]) == 2
        assert conv["messages"][0]["content"] == "First message"
        assert conv["messages"][1]["content"] == "Second message"
    
    def test_get_conversation_history_existing_user(self, conversation_service, sample_conversation_history):
        """Test getting conversation history for existing user"""
        user_id = "test_user"
        
        # Add sample conversation
        for msg in sample_conversation_history:
            conversation_service.add_message(user_id, msg["role"], msg["content"])
        
        history = conversation_service.get_conversation_history(user_id)
        
        assert len(history) == len(sample_conversation_history)
        for i, msg in enumerate(history):
            assert msg["role"] == sample_conversation_history[i]["role"]
            assert msg["content"] == sample_conversation_history[i]["content"]
            # Should not include timestamp in history
            assert "timestamp" not in msg
    
    def test_get_conversation_history_nonexistent_user(self, conversation_service):
        """Test getting conversation history for non-existent user"""
        history = conversation_service.get_conversation_history("nonexistent_user")
        
        assert history == []
    
    def test_message_limit_per_user(self, conversation_service):
        """Test message limit enforcement per user"""
        user_id = "heavy_user"
        max_messages = conversation_service.max_messages_per_user
        
        # Add more messages than the limit
        for i in range(max_messages + 20):
            conversation_service.add_message(user_id, "user", f"Message {i}")
        
        conv = conversation_service.conversations[user_id]
        
        # Should be trimmed to max_messages
        assert len(conv["messages"]) == max_messages
        
        # Should keep the most recent messages
        assert conv["messages"][-1]["content"] == f"Message {max_messages + 19}"
        assert conv["messages"][0]["content"] == f"Message 20"
    
    def test_get_conversation_stats_existing_user(self, conversation_service, sample_conversation_history):
        """Test getting conversation statistics for existing user"""
        user_id = "test_user"
        
        # Add sample conversation
        for msg in sample_conversation_history:
            conversation_service.add_message(user_id, msg["role"], msg["content"])
        
        stats = conversation_service.get_conversation_stats(user_id)
        
        assert stats["exists"] is True
        assert stats["message_count"] == len(sample_conversation_history)
        assert isinstance(stats["created_at"], str)  # Should be ISO format
        assert isinstance(stats["last_activity"], str)  # Should be ISO format
    
    def test_get_conversation_stats_nonexistent_user(self, conversation_service):
        """Test getting conversation statistics for non-existent user"""
        stats = conversation_service.get_conversation_stats("nonexistent_user")
        
        assert stats["exists"] is False
        assert stats["message_count"] == 0
        assert stats["created_at"] is None
        assert stats["last_activity"] is None
    
    def test_clear_conversation_existing_user(self, conversation_service):
        """Test clearing conversation for existing user"""
        user_id = "test_user"
        
        # Add some messages
        conversation_service.add_message(user_id, "user", "Hello")
        conversation_service.add_message(user_id, "assistant", "Hi")
        
        assert user_id in conversation_service.conversations
        
        # Clear conversation
        result = conversation_service.clear_conversation(user_id)
        
        assert result is True
        assert user_id not in conversation_service.conversations
    
    def test_clear_conversation_nonexistent_user(self, conversation_service):
        """Test clearing conversation for non-existent user"""
        result = conversation_service.clear_conversation("nonexistent_user")
        
        assert result is False
    
    def test_get_all_conversations_stats(self, conversation_service):
        """Test getting statistics for all conversations"""
        # Add conversations for multiple users
        conversation_service.add_message("user1", "user", "Hello from user1")
        conversation_service.add_message("user1", "assistant", "Hi user1")
        
        conversation_service.add_message("user2", "user", "Hello from user2")
        conversation_service.add_message("user2", "assistant", "Hi user2")
        conversation_service.add_message("user2", "user", "Another message")
        
        stats = conversation_service.get_all_conversations_stats()
        
        assert stats["total_users"] == 2
        assert stats["total_messages"] == 5
        assert stats["active_conversations"] == 2
    
    def test_get_all_conversations_stats_empty(self, conversation_service):
        """Test getting statistics with no conversations"""
        stats = conversation_service.get_all_conversations_stats()
        
        assert stats["total_users"] == 0
        assert stats["total_messages"] == 0
        assert stats["active_conversations"] == 0
    
    def test_global_conversation_limit(self, conversation_service):
        """Test global conversation limit enforcement"""
        # Temporarily reduce limit for testing
        original_limit = conversation_service.max_total_conversations
        conversation_service.max_total_conversations = 5
        
        try:
            # Add conversations up to the limit
            for i in range(7):  # More than the limit
                user_id = f"user_{i}"
                conversation_service.add_message(user_id, "user", f"Message from {user_id}")
            
            # Should have trimmed to limit
            assert len(conversation_service.conversations) <= 5
            
        finally:
            # Restore original limit
            conversation_service.max_total_conversations = original_limit
    
    def test_cleanup_old_conversations(self, conversation_service):
        """Test cleanup of old conversations"""
        # Add some conversations
        conversation_service.add_message("user1", "user", "Recent message")
        conversation_service.add_message("user2", "user", "Old message")
        
        # Manually set old timestamp for user2
        old_time = datetime.now() - timedelta(hours=25)  # 25 hours ago
        conversation_service.conversations["user2"]["last_activity"] = old_time
        
        # Cleanup conversations older than 24 hours
        removed_count = conversation_service.cleanup_old_conversations(max_age_hours=24)
        
        assert removed_count == 1
        assert "user1" in conversation_service.conversations
        assert "user2" not in conversation_service.conversations
    
    def test_cleanup_old_conversations_none_to_remove(self, conversation_service):
        """Test cleanup when no conversations are old enough"""
        # Add recent conversation
        conversation_service.add_message("user1", "user", "Recent message")
        
        # Try to cleanup very old conversations
        removed_count = conversation_service.cleanup_old_conversations(max_age_hours=1)
        
        assert removed_count == 0
        assert "user1" in conversation_service.conversations
    
    def test_last_activity_update(self, conversation_service):
        """Test that last_activity is updated when adding messages"""
        user_id = "test_user"
        
        # Add first message
        conversation_service.add_message(user_id, "user", "First message")
        first_activity = conversation_service.conversations[user_id]["last_activity"]
        
        # Wait a tiny bit and add second message
        import time
        time.sleep(0.01)
        
        conversation_service.add_message(user_id, "assistant", "Second message")
        second_activity = conversation_service.conversations[user_id]["last_activity"]
        
        # Last activity should be updated
        assert second_activity > first_activity
    
    def test_conversation_history_format(self, conversation_service):
        """Test that conversation history has correct format for OpenAI"""
        user_id = "test_user"
        
        conversation_service.add_message(user_id, "user", "Hello")
        conversation_service.add_message(user_id, "assistant", "Hi there!")
        
        history = conversation_service.get_conversation_history(user_id)
        
        # Should only have role and content (no timestamp, created_at, etc.)
        for msg in history:
            assert set(msg.keys()) == {"role", "content"}
            assert msg["role"] in ["user", "assistant"]
            assert isinstance(msg["content"], str)
    
    def test_manage_global_limits_called(self, conversation_service):
        """Test that global limit management is called when adding messages"""
        with pytest.MonkeyPatch().context() as m:
            # Mock the global limit management method
            mock_manage = Mock()
            m.setattr(conversation_service, "_manage_global_limits", mock_manage)
            
            conversation_service.add_message("user1", "user", "Test message")
            
            # Should have been called
            mock_manage.assert_called_once()
    
    def test_error_handling_in_add_message(self, conversation_service, caplog):
        """Test error handling in add_message method"""
        import logging
        
        # Temporarily break the conversations dict to cause an error
        original_conversations = conversation_service.conversations
        conversation_service.conversations = None
        
        with caplog.at_level(logging.ERROR):
            conversation_service.add_message("user1", "user", "Test message")
        
        # Should log error but not crash
        assert "Error adding message" in caplog.text
        
        # Restore conversations
        conversation_service.conversations = original_conversations