"""
Unit tests for Rich Message Interaction Handler
"""

import pytest
from unittest.mock import patch, Mock, MagicMock
from datetime import datetime, timezone
import json

from src.utils.interaction_handler import (
    InteractionHandler, get_interaction_handler, InteractionType, ReactionType,
    UserInteractionRecord, ContentInteractionStats, UserEngagementProfile
)


class TestInteractionHandler:
    """Test cases for InteractionHandler"""
    
    @pytest.fixture
    def interaction_handler(self):
        """Create an InteractionHandler instance"""
        return InteractionHandler()
    
    @pytest.fixture
    def sample_interaction_data(self):
        """Create sample interaction data"""
        return {
            "action": "interaction",
            "type": "like",
            "content_id": "test_content_123"
        }
    
    def test_initialization(self, interaction_handler):
        """Test InteractionHandler initialization"""
        assert isinstance(interaction_handler.user_interactions, list)
        assert isinstance(interaction_handler.content_stats, dict)
        assert isinstance(interaction_handler.user_profiles, dict)
        assert len(interaction_handler.user_interactions) == 0
        assert len(interaction_handler.content_stats) == 0
        assert len(interaction_handler.user_profiles) == 0
        assert interaction_handler.interaction_retention_days == 90
        assert interaction_handler.max_interactions_per_user_per_day == 100
        assert hasattr(interaction_handler, 'analytics_tracker')
    
    def test_create_interactive_buttons_basic(self, interaction_handler):
        """Test creating interactive buttons without user context"""
        content_id = "test_content_123"
        
        buttons = interaction_handler.create_interactive_buttons(content_id)
        
        assert len(buttons) == 4  # Like, Share, Save, React
        assert all(isinstance(button, dict) for button in buttons)
        
        # Check button structure
        like_button = buttons[0]
        assert like_button["type"] == "postback"
        assert like_button["label"] == "❤️ Like"
        assert like_button["style"] == "secondary"
        
        # Check data format
        data = json.loads(like_button["data"])
        assert data["action"] == "interaction"
        assert data["type"] == "like"
        assert data["content_id"] == content_id
    
    def test_create_interactive_buttons_with_user_context(self, interaction_handler):
        """Test creating interactive buttons with user context"""
        content_id = "test_content_123"
        user_id = "user_456"
        
        # Create a user interaction (like)
        interaction_record = UserInteractionRecord(
            interaction_id="test_interaction",
            user_id=user_id,
            content_id=content_id,
            interaction_type=InteractionType.LIKE,
            timestamp=datetime.now(timezone.utc)
        )
        interaction_handler.user_interactions.append(interaction_record)
        
        buttons = interaction_handler.create_interactive_buttons(
            content_id, current_user_id=user_id
        )
        
        # Like button should show "Unlike" since user already liked
        like_button = buttons[0]
        assert like_button["label"] == "💔 Unlike"
        assert like_button["style"] == "primary"  # Active state
        
        data = json.loads(like_button["data"])
        assert data["type"] == "unlike"
    
    def test_create_interactive_buttons_with_stats(self, interaction_handler):
        """Test creating interactive buttons with statistics"""
        content_id = "test_content_123"
        
        # Create content stats
        stats = ContentInteractionStats(content_id)
        stats.total_likes = 15
        stats.total_shares = 8
        stats.total_saves = 12
        stats.total_reactions = 20
        interaction_handler.content_stats[content_id] = stats
        
        buttons = interaction_handler.create_interactive_buttons(
            content_id, include_stats=True
        )
        
        # Check that buttons include stats in labels
        like_button = buttons[0]
        assert "15" in like_button["label"]  # Like count
        
        share_button = buttons[1]
        assert "8" in share_button["label"]  # Share count
        
        save_button = buttons[2]
        assert "12" in save_button["label"]  # Save count
        
        react_button = buttons[3]
        assert "20" in react_button["label"]  # Reaction count
    
    def test_create_reaction_quick_reply(self, interaction_handler):
        """Test creating reaction quick reply"""
        content_id = "test_content_123"
        
        quick_reply = interaction_handler.create_reaction_quick_reply(content_id)
        
        assert hasattr(quick_reply, 'items')
        assert len(quick_reply.items) == len(ReactionType)
        
        # Check first reaction item
        first_item = quick_reply.items[0]
        assert hasattr(first_item, 'action')
        
        # Parse the postback data
        data = json.loads(first_item.action.data)
        assert data["action"] == "interaction"
        assert data["type"] == "react"
        assert data["content_id"] == content_id
        assert "reaction" in data
    
    @patch('src.utils.interaction_handler.get_analytics_tracker')
    def test_handle_user_interaction_like(self, mock_get_analytics, interaction_handler):
        """Test handling like interaction"""
        mock_analytics = Mock()
        mock_get_analytics.return_value = mock_analytics
        interaction_handler.analytics_tracker = mock_analytics
        
        user_id = "user_123"
        interaction_data = {
            "action": "interaction",
            "type": "like",
            "content_id": "content_456"
        }
        
        result = interaction_handler.handle_user_interaction(user_id, interaction_data)
        
        assert result["success"] is True
        assert result["response_type"] == "message"
        assert "❤️ Liked!" in result["message"]
        assert "interaction_id" in result
        assert "updated_stats" in result
        
        # Check that interaction was stored
        assert len(interaction_handler.user_interactions) == 1
        interaction = interaction_handler.user_interactions[0]
        assert interaction.user_id == user_id
        assert interaction.content_id == "content_456"
        assert interaction.interaction_type == InteractionType.LIKE
    
    @patch('src.utils.interaction_handler.get_analytics_tracker')
    def test_handle_user_interaction_unlike(self, mock_get_analytics, interaction_handler):
        """Test handling unlike interaction"""
        mock_analytics = Mock()
        mock_get_analytics.return_value = mock_analytics
        interaction_handler.analytics_tracker = mock_analytics
        
        user_id = "user_123"
        content_id = "content_456"
        
        # First create a like interaction
        like_interaction = UserInteractionRecord(
            interaction_id="like_123",
            user_id=user_id,
            content_id=content_id,
            interaction_type=InteractionType.LIKE,
            timestamp=datetime.now(timezone.utc)
        )
        interaction_handler.user_interactions.append(like_interaction)
        
        # Now unlike
        interaction_data = {
            "action": "interaction",
            "type": "unlike",
            "content_id": content_id
        }
        
        result = interaction_handler.handle_user_interaction(user_id, interaction_data)
        
        assert result["success"] is True
        assert "💔 Unliked" in result["message"]
        
        # Check that unlike interaction was added
        unlike_interactions = [
            i for i in interaction_handler.user_interactions
            if i.interaction_type == InteractionType.UNLIKE
        ]
        assert len(unlike_interactions) == 1
    
    @patch('src.utils.interaction_handler.get_analytics_tracker')
    def test_handle_user_interaction_react(self, mock_get_analytics, interaction_handler):
        """Test handling reaction interaction"""
        mock_analytics = Mock()
        mock_get_analytics.return_value = mock_analytics
        interaction_handler.analytics_tracker = mock_analytics
        
        user_id = "user_123"
        interaction_data = {
            "action": "interaction",
            "type": "react",
            "content_id": "content_456",
            "reaction": "LOVE"
        }
        
        result = interaction_handler.handle_user_interaction(user_id, interaction_data)
        
        assert result["success"] is True
        assert "❤️ Thanks for your reaction!" in result["message"]
        
        # Check interaction details
        interaction = interaction_handler.user_interactions[0]
        assert interaction.reaction_type == ReactionType.LOVE
    
    @patch('src.utils.interaction_handler.get_analytics_tracker')
    def test_handle_user_interaction_share(self, mock_get_analytics, interaction_handler):
        """Test handling share interaction"""
        mock_analytics = Mock()
        mock_get_analytics.return_value = mock_analytics
        interaction_handler.analytics_tracker = mock_analytics
        
        user_id = "user_123"
        interaction_data = {
            "action": "interaction",
            "type": "share",
            "content_id": "content_456"
        }
        
        result = interaction_handler.handle_user_interaction(user_id, interaction_data)
        
        assert result["success"] is True
        assert "📤 Thanks for sharing!" in result["message"]
        
        interaction = interaction_handler.user_interactions[0]
        assert interaction.interaction_type == InteractionType.SHARE
    
    def test_handle_user_interaction_missing_data(self, interaction_handler):
        """Test handling interaction with missing data"""
        user_id = "user_123"
        interaction_data = {
            "action": "interaction"
            # Missing type and content_id
        }
        
        result = interaction_handler.handle_user_interaction(user_id, interaction_data)
        
        assert result["success"] is False
        assert "Missing required interaction data" in result["error"]
        assert result["response_type"] == "error"
    
    def test_handle_user_interaction_invalid_type(self, interaction_handler):
        """Test handling interaction with invalid type"""
        user_id = "user_123"
        interaction_data = {
            "action": "interaction",
            "type": "invalid_type",
            "content_id": "content_456"
        }
        
        result = interaction_handler.handle_user_interaction(user_id, interaction_data)
        
        assert result["success"] is False
        assert "Invalid interaction type" in result["error"]
    
    def test_handle_show_reactions_action(self, interaction_handler):
        """Test handling show reactions action"""
        content_id = "content_123"
        
        result = interaction_handler._handle_show_reactions(content_id)
        
        assert result["success"] is True
        assert result["response_type"] == "quick_reply"
        assert "quick_reply" in result
        assert "How did this content make you feel?" in result["message"]
    
    @patch('src.utils.interaction_handler.get_analytics_tracker')
    def test_handle_share_platform_action(self, mock_get_analytics, interaction_handler):
        """Test handling platform-specific share action"""
        mock_analytics = Mock()
        mock_get_analytics.return_value = mock_analytics
        interaction_handler.analytics_tracker = mock_analytics
        
        user_id = "user_123"
        interaction_data = {
            "action": "share_platform",
            "platform": "line",
            "content_id": "content_456"
        }
        
        result = interaction_handler._handle_share_platform(user_id, "content_456", "line")
        
        assert result["success"] is True
        assert "📱 Content shared to LINE!" in result["message"]
        
        # Check that share interaction was recorded
        interaction = interaction_handler.user_interactions[0]
        assert interaction.interaction_type == InteractionType.SHARE
        assert interaction.share_platform == "line"
    
    def test_update_content_stats(self, interaction_handler):
        """Test updating content statistics"""
        content_id = "content_123"
        
        # Create interaction record
        interaction_record = UserInteractionRecord(
            interaction_id="test_interaction",
            user_id="user_456",
            content_id=content_id,
            interaction_type=InteractionType.LIKE,
            timestamp=datetime.now(timezone.utc)
        )
        
        # Update stats
        interaction_handler._update_content_stats(
            content_id, InteractionType.LIKE, interaction_record
        )
        
        # Check that stats were created and updated
        assert content_id in interaction_handler.content_stats
        stats = interaction_handler.content_stats[content_id]
        assert stats.total_likes == 1
        assert stats.first_interaction is not None
        assert stats.last_interaction is not None
    
    def test_update_user_profile(self, interaction_handler):
        """Test updating user engagement profile"""
        user_id = "user_123"
        
        # Create interaction record
        interaction_record = UserInteractionRecord(
            interaction_id="test_interaction",
            user_id=user_id,
            content_id="content_456",
            interaction_type=InteractionType.LIKE,
            timestamp=datetime.now(timezone.utc)
        )
        
        # Update profile
        interaction_handler._update_user_profile(
            user_id, InteractionType.LIKE, interaction_record
        )
        
        # Check that profile was created and updated
        assert user_id in interaction_handler.user_profiles
        profile = interaction_handler.user_profiles[user_id]
        assert profile.total_interactions == 1
        assert profile.likes_given == 1
        assert profile.last_interaction is not None
    
    def test_get_content_stats(self, interaction_handler):
        """Test getting content statistics"""
        content_id = "content_123"
        
        # Create stats
        stats = ContentInteractionStats(content_id)
        stats.total_likes = 10
        interaction_handler.content_stats[content_id] = stats
        
        retrieved_stats = interaction_handler.get_content_stats(content_id)
        
        assert retrieved_stats is not None
        assert retrieved_stats.content_id == content_id
        assert retrieved_stats.total_likes == 10
        
        # Test non-existent content
        non_existent_stats = interaction_handler.get_content_stats("non_existent")
        assert non_existent_stats is None
    
    def test_get_user_profile(self, interaction_handler):
        """Test getting user engagement profile"""
        user_id = "user_123"
        
        # Create profile
        profile = UserEngagementProfile(user_id)
        profile.total_interactions = 5
        interaction_handler.user_profiles[user_id] = profile
        
        retrieved_profile = interaction_handler.get_user_profile(user_id)
        
        assert retrieved_profile is not None
        assert retrieved_profile.user_id == user_id
        assert retrieved_profile.total_interactions == 5
        
        # Test non-existent user
        non_existent_profile = interaction_handler.get_user_profile("non_existent")
        assert non_existent_profile is None
    
    def test_get_top_engaged_content(self, interaction_handler):
        """Test getting top engaged content"""
        # Create multiple content stats
        content1 = ContentInteractionStats("content_1")
        content1.engagement_rate = 0.8
        content2 = ContentInteractionStats("content_2")
        content2.engagement_rate = 0.6
        content3 = ContentInteractionStats("content_3")
        content3.engagement_rate = 0.9
        
        interaction_handler.content_stats["content_1"] = content1
        interaction_handler.content_stats["content_2"] = content2
        interaction_handler.content_stats["content_3"] = content3
        
        top_content = interaction_handler.get_top_engaged_content(limit=2)
        
        assert len(top_content) == 2
        assert top_content[0][0] == "content_3"  # Highest engagement
        assert top_content[1][0] == "content_1"  # Second highest
        assert top_content[0][1].engagement_rate == 0.9
    
    def test_get_user_saved_content(self, interaction_handler):
        """Test getting user's saved content"""
        user_id = "user_123"
        
        # Create save interactions
        save1 = UserInteractionRecord(
            interaction_id="save_1",
            user_id=user_id,
            content_id="content_1",
            interaction_type=InteractionType.SAVE,
            timestamp=datetime.now(timezone.utc)
        )
        save2 = UserInteractionRecord(
            interaction_id="save_2",
            user_id=user_id,
            content_id="content_2",
            interaction_type=InteractionType.SAVE,
            timestamp=datetime.now(timezone.utc)
        )
        unsave1 = UserInteractionRecord(
            interaction_id="unsave_1",
            user_id=user_id,
            content_id="content_1",
            interaction_type=InteractionType.UNSAVE,
            timestamp=datetime.now(timezone.utc)
        )
        
        interaction_handler.user_interactions.extend([save1, save2, unsave1])
        
        saved_content = interaction_handler.get_user_saved_content(user_id)
        
        # Should only have content_2 (content_1 was unsaved)
        assert len(saved_content) == 1
        assert "content_2" in saved_content
        assert "content_1" not in saved_content
    
    def test_get_engagement_summary_empty(self, interaction_handler):
        """Test engagement summary with no data"""
        summary = interaction_handler.get_engagement_summary()
        
        assert summary["total_interactions"] == 0
        assert summary["total_users"] == 0
        assert summary["total_content"] == 0
        assert summary["engagement_summary"] == "No interactions recorded"
    
    def test_get_engagement_summary_with_data(self, interaction_handler):
        """Test engagement summary with sample data"""
        # Create sample interactions
        interactions = [
            UserInteractionRecord(
                interaction_id=f"interaction_{i}",
                user_id=f"user_{i % 3}",  # 3 different users
                content_id=f"content_{i % 2}",  # 2 different content pieces
                interaction_type=InteractionType.LIKE if i % 2 == 0 else InteractionType.SHARE,
                timestamp=datetime.now(timezone.utc)
            )
            for i in range(10)
        ]
        
        interaction_handler.user_interactions.extend(interactions)
        
        summary = interaction_handler.get_engagement_summary()
        
        assert summary["total_interactions"] == 10
        assert summary["total_users"] == 3
        assert summary["total_content"] == 2
        assert "interaction_type_counts" in summary
        assert summary["interaction_type_counts"]["like"] == 5
        assert summary["interaction_type_counts"]["share"] == 5
    
    def test_cleanup_old_interactions(self, interaction_handler):
        """Test cleaning up old interactions"""
        # Create old and new interactions
        old_interaction = UserInteractionRecord(
            interaction_id="old_interaction",
            user_id="user_old",
            content_id="content_old",
            interaction_type=InteractionType.LIKE,
            timestamp=datetime(2020, 1, 1, tzinfo=timezone.utc)  # Very old
        )
        
        new_interaction = UserInteractionRecord(
            interaction_id="new_interaction",
            user_id="user_new",
            content_id="content_new",
            interaction_type=InteractionType.LIKE,
            timestamp=datetime.now(timezone.utc)
        )
        
        interaction_handler.user_interactions.extend([old_interaction, new_interaction])
        
        removed_count = interaction_handler.cleanup_old_interactions(days_to_keep=30)
        
        assert removed_count == 1
        assert len(interaction_handler.user_interactions) == 1
        assert interaction_handler.user_interactions[0].interaction_id == "new_interaction"
    
    @patch('src.utils.interaction_handler.get_analytics_tracker')
    def test_get_engagement_analytics_summary(self, mock_get_analytics, interaction_handler):
        """Test getting comprehensive engagement analytics summary"""
        mock_analytics = Mock()
        mock_analytics.get_user_engagement_summary.return_value = {
            'total_users': 100,
            'active_users': 75
        }
        mock_analytics.get_top_performing_content.return_value = [
            ('content_1', Mock(open_rate=0.8, interaction_rate=0.6, total_interactions=50))
        ]
        mock_analytics.calculate_system_metrics.return_value = Mock(
            total_users=100,
            active_users=75,
            overall_open_rate=0.7,
            overall_interaction_rate=0.5,
            user_retention_rate=0.8
        )
        mock_get_analytics.return_value = mock_analytics
        interaction_handler.analytics_tracker = mock_analytics
        
        summary = interaction_handler.get_engagement_analytics_summary()
        
        assert "analytics_summary" in summary
        assert "top_performing_content" in summary
        assert "system_metrics" in summary
        assert "local_interaction_summary" in summary
        assert "combined_metrics" in summary
        
        assert summary["analytics_summary"]["total_users"] == 100
        assert len(summary["top_performing_content"]) == 1
    
    def test_interaction_type_enum(self):
        """Test InteractionType enum values"""
        assert InteractionType.LIKE.value == "like"
        assert InteractionType.UNLIKE.value == "unlike"
        assert InteractionType.SHARE.value == "share"
        assert InteractionType.SAVE.value == "save"
        assert InteractionType.UNSAVE.value == "unsave"
        assert InteractionType.REACT.value == "react"
        assert InteractionType.COMMENT.value == "comment"
        assert InteractionType.REPORT.value == "report"
        assert InteractionType.FEEDBACK.value == "feedback"
        assert InteractionType.BOOKMARK.value == "bookmark"
        assert InteractionType.UNBOOKMARK.value == "unbookmark"
    
    def test_reaction_type_enum(self):
        """Test ReactionType enum values"""
        assert ReactionType.LOVE.value == "❤️"
        assert ReactionType.THUMBS_UP.value == "👍"
        assert ReactionType.CLAP.value == "👏"
        assert ReactionType.FIRE.value == "🔥"
        assert ReactionType.STAR.value == "⭐"
        assert ReactionType.MIND_BLOWN.value == "🤯"
        assert ReactionType.LAUGH.value == "😂"
        assert ReactionType.THINKING.value == "🤔"
    
    def test_get_interaction_handler_singleton(self):
        """Test global interaction handler singleton"""
        handler1 = get_interaction_handler()
        handler2 = get_interaction_handler()
        
        assert handler1 is handler2
        assert isinstance(handler1, InteractionHandler)
    
    def test_user_interaction_record_creation(self):
        """Test UserInteractionRecord dataclass creation"""
        timestamp = datetime.now(timezone.utc)
        
        record = UserInteractionRecord(
            interaction_id="test_interaction",
            user_id="test_user",
            content_id="test_content",
            interaction_type=InteractionType.LIKE,
            timestamp=timestamp,
            reaction_type=ReactionType.LOVE,
            comment_text="Great content!",
            share_platform="line",
            feedback_rating=5,
            metadata={"key": "value"}
        )
        
        assert record.interaction_id == "test_interaction"
        assert record.user_id == "test_user"
        assert record.content_id == "test_content"
        assert record.interaction_type == InteractionType.LIKE
        assert record.timestamp == timestamp
        assert record.reaction_type == ReactionType.LOVE
        assert record.comment_text == "Great content!"
        assert record.share_platform == "line"
        assert record.feedback_rating == 5
        assert record.metadata == {"key": "value"}
    
    def test_content_interaction_stats_creation(self):
        """Test ContentInteractionStats dataclass creation"""
        stats = ContentInteractionStats(
            content_id="test_content",
            total_likes=10,
            total_shares=5,
            total_saves=8,
            total_reactions=15,
            total_comments=3,
            engagement_rate=0.7,
            like_rate=0.4,
            share_rate=0.2,
            save_rate=0.3
        )
        
        assert stats.content_id == "test_content"
        assert stats.total_likes == 10
        assert stats.total_shares == 5
        assert stats.total_saves == 8
        assert stats.total_reactions == 15
        assert stats.total_comments == 3
        assert stats.engagement_rate == 0.7
        assert stats.like_rate == 0.4
        assert stats.share_rate == 0.2
        assert stats.save_rate == 0.3
    
    def test_user_engagement_profile_creation(self):
        """Test UserEngagementProfile dataclass creation"""
        last_interaction = datetime.now(timezone.utc)
        
        profile = UserEngagementProfile(
            user_id="test_user",
            total_interactions=25,
            likes_given=10,
            shares_made=5,
            content_saved=8,
            reactions_made=12,
            comments_posted=3,
            engagement_streak=7,
            last_interaction=last_interaction
        )
        
        assert profile.user_id == "test_user"
        assert profile.total_interactions == 25
        assert profile.likes_given == 10
        assert profile.shares_made == 5
        assert profile.content_saved == 8
        assert profile.reactions_made == 12
        assert profile.comments_posted == 3
        assert profile.engagement_streak == 7
        assert profile.last_interaction == last_interaction