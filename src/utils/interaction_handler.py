"""
Interaction Handler for Rich Message user interactions.

This module handles user interactions with Rich Messages including likes, shares,
saves, and other engagement actions. It provides comprehensive tracking and
response management for user engagement.
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
import json
import uuid

from linebot.models import (
    PostbackAction, URIAction, MessageAction, QuickReply, QuickReplyButton,
    FlexSendMessage, BubbleContainer, BoxComponent, ButtonComponent,
    TextComponent, IconComponent
)

from src.utils.analytics_tracker import (
    get_analytics_tracker, InteractionType as AnalyticsInteractionType
)

logger = logging.getLogger(__name__)


class InteractionType(Enum):
    """Types of user interactions with Rich Messages"""
    LIKE = "like"
    UNLIKE = "unlike"
    SHARE = "share"
    SAVE = "save"
    UNSAVE = "unsave"
    REACT = "react"
    COMMENT = "comment"
    REPORT = "report"
    FEEDBACK = "feedback"
    BOOKMARK = "bookmark"
    UNBOOKMARK = "unbookmark"


class ReactionType(Enum):
    """Types of reactions users can make"""
    LOVE = "❤️"
    THUMBS_UP = "👍"
    CLAP = "👏"
    FIRE = "🔥"
    STAR = "⭐"
    MIND_BLOWN = "🤯"
    LAUGH = "😂"
    THINKING = "🤔"


@dataclass
class UserInteractionRecord:
    """Record of a user interaction with Rich Message content"""
    interaction_id: str
    user_id: str
    content_id: str  # Rich Message content identifier
    interaction_type: InteractionType
    timestamp: datetime
    
    # Optional interaction data
    reaction_type: Optional[ReactionType] = None
    comment_text: Optional[str] = None
    share_platform: Optional[str] = None
    feedback_rating: Optional[int] = None  # 1-5 scale
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ContentInteractionStats:
    """Interaction statistics for a specific piece of content"""
    content_id: str
    total_likes: int = 0
    total_shares: int = 0
    total_saves: int = 0
    total_reactions: int = 0
    total_comments: int = 0
    
    # Reaction breakdown
    reaction_counts: Dict[str, int] = field(default_factory=dict)
    
    # Engagement metrics
    engagement_rate: float = 0.0
    like_rate: float = 0.0
    share_rate: float = 0.0
    save_rate: float = 0.0
    
    # Time-based metrics
    first_interaction: Optional[datetime] = None
    last_interaction: Optional[datetime] = None
    peak_engagement_time: Optional[datetime] = None


@dataclass
class UserEngagementProfile:
    """User's engagement profile and preferences"""
    user_id: str
    total_interactions: int = 0
    favorite_content_categories: List[str] = field(default_factory=list)
    preferred_reaction_types: List[ReactionType] = field(default_factory=list)
    
    # Interaction behavior
    likes_given: int = 0
    shares_made: int = 0
    content_saved: int = 0
    reactions_made: int = 0
    comments_posted: int = 0
    
    # Engagement patterns
    most_active_hours: List[int] = field(default_factory=list)
    engagement_streak: int = 0
    last_interaction: Optional[datetime] = None
    
    # Preferences
    notification_preferences: Dict[str, bool] = field(default_factory=lambda: {
        'likes_on_content': True,
        'shares_of_content': True,
        'new_content_alerts': True,
        'weekly_summary': True
    })


class InteractionHandler:
    """
    Comprehensive handler for Rich Message user interactions.
    
    Manages user engagement actions, tracks interaction statistics,
    and provides engagement analytics and response generation.
    """
    
    def __init__(self):
        """Initialize the InteractionHandler."""
        self.user_interactions: List[UserInteractionRecord] = []
        self.content_stats: Dict[str, ContentInteractionStats] = {}
        self.user_profiles: Dict[str, UserEngagementProfile] = {}
        
        # Configuration
        self.interaction_retention_days = 90  # Keep interactions for 90 days
        self.max_interactions_per_user_per_day = 100
        
        # Analytics integration
        self.analytics_tracker = get_analytics_tracker()
        
        logger.info("InteractionHandler initialized with analytics tracking")
    
    def create_interactive_buttons(self, content_id: str, 
                                 current_user_id: Optional[str] = None,
                                 include_stats: bool = False) -> List[Dict[str, Any]]:
        """
        Create interactive button configurations for Rich Messages.
        
        Args:
            content_id: Identifier for the content
            current_user_id: Current user ID for personalized buttons
            include_stats: Whether to include interaction statistics
            
        Returns:
            List of button configurations for Flex Message
        """
        buttons = []
        
        # Get current stats for this content
        stats = self.content_stats.get(content_id, ContentInteractionStats(content_id))
        
        # Check user's current interactions with this content
        user_liked = False
        user_saved = False
        if current_user_id:
            user_interactions = [
                i for i in self.user_interactions 
                if i.user_id == current_user_id and i.content_id == content_id
            ]
            user_liked = any(i.interaction_type == InteractionType.LIKE for i in user_interactions)
            user_saved = any(i.interaction_type == InteractionType.SAVE for i in user_interactions)
        
        # Like/Unlike button
        like_label = f"❤️ {stats.total_likes}" if include_stats else ("💔 Unlike" if user_liked else "❤️ Like")
        like_action = InteractionType.UNLIKE.value if user_liked else InteractionType.LIKE.value
        
        buttons.append({
            "type": "postback",
            "label": like_label,
            "data": json.dumps({
                "action": "interaction",
                "type": like_action,
                "content_id": content_id
            }),
            "style": "primary" if user_liked else "secondary"
        })
        
        # Share button
        share_label = f"📤 {stats.total_shares}" if include_stats else "📤 Share"
        buttons.append({
            "type": "postback",
            "label": share_label,
            "data": json.dumps({
                "action": "interaction",
                "type": InteractionType.SHARE.value,
                "content_id": content_id
            }),
            "style": "secondary"
        })
        
        # Save/Unsave button
        save_label = f"🔖 {stats.total_saves}" if include_stats else ("📌 Saved" if user_saved else "🔖 Save")
        save_action = InteractionType.UNSAVE.value if user_saved else InteractionType.SAVE.value
        
        buttons.append({
            "type": "postback",
            "label": save_label,
            "data": json.dumps({
                "action": "interaction",
                "type": save_action,
                "content_id": content_id
            }),
            "style": "primary" if user_saved else "secondary"
        })
        
        # React button (opens reaction menu)
        react_label = f"😊 {stats.total_reactions}" if include_stats else "😊 React"
        buttons.append({
            "type": "postback",
            "label": react_label,
            "data": json.dumps({
                "action": "show_reactions",
                "content_id": content_id
            }),
            "style": "secondary"
        })
        
        return buttons
    
    def create_reaction_quick_reply(self, content_id: str) -> QuickReply:
        """
        Create quick reply buttons for reactions.
        
        Args:
            content_id: Content identifier
            
        Returns:
            QuickReply object with reaction options
        """
        items = []
        
        for reaction in ReactionType:
            items.append(
                QuickReplyButton(
                    action=PostbackAction(
                        label=f"{reaction.value}",
                        data=json.dumps({
                            "action": "interaction",
                            "type": InteractionType.REACT.value,
                            "content_id": content_id,
                            "reaction": reaction.name
                        })
                    )
                )
            )
        
        return QuickReply(items=items)
    
    def create_share_options_flex(self, content_id: str, content_title: str) -> FlexSendMessage:
        """
        Create Flex Message with sharing options.
        
        Args:
            content_id: Content identifier
            content_title: Title of content being shared
            
        Returns:
            FlexSendMessage with sharing options
        """
        # Share options
        share_buttons = [
            {
                "type": "postback",
                "label": "📱 Share to LINE",
                "data": json.dumps({
                    "action": "share_platform",
                    "platform": "line",
                    "content_id": content_id
                })
            },
            {
                "type": "postback", 
                "label": "📋 Copy Link",
                "data": json.dumps({
                    "action": "share_platform",
                    "platform": "copy",
                    "content_id": content_id
                })
            },
            {
                "type": "postback",
                "label": "✉️ Send via Email",
                "data": json.dumps({
                    "action": "share_platform",
                    "platform": "email",
                    "content_id": content_id
                })
            }
        ]
        
        # Create button components
        button_components = []
        for button in share_buttons:
            button_components.append(
                ButtonComponent(
                    action=PostbackAction(
                        label=button["label"],
                        data=button["data"]
                    ),
                    style="secondary",
                    height="sm"
                )
            )
        
        # Create bubble
        bubble = BubbleContainer(
            body=BoxComponent(
                layout="vertical",
                contents=[
                    TextComponent(
                        text="Share this content",
                        weight="bold",
                        size="lg",
                        color="#333333"
                    ),
                    TextComponent(
                        text=f'"{content_title}"',
                        size="sm",
                        color="#666666",
                        wrap=True,
                        margin="md"
                    ),
                    TextComponent(text=" ", size="sm")  # Spacer replacement
                ] + button_components,
                spacing="sm",
                margin="lg"
            )
        )
        
        return FlexSendMessage(alt_text="Share options", contents=bubble)
    
    def handle_user_interaction(self, user_id: str, interaction_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle a user interaction with Rich Message content.
        
        Args:
            user_id: User identifier
            interaction_data: Parsed interaction data from postback
            
        Returns:
            Dictionary with response data and actions
        """
        try:
            action = interaction_data.get("action")
            content_id = interaction_data.get("content_id")
            interaction_type_str = interaction_data.get("type")
            
            if not all([action, content_id]):
                return {
                    "success": False,
                    "error": "Missing required interaction data",
                    "response_type": "error"
                }
            
            # Handle different action types
            if action == "interaction":
                return self._handle_content_interaction(
                    user_id, content_id, interaction_type_str, interaction_data
                )
            elif action == "show_reactions":
                return self._handle_show_reactions(content_id)
            elif action == "share_platform":
                return self._handle_share_platform(
                    user_id, content_id, interaction_data.get("platform")
                )
            else:
                return {
                    "success": False,
                    "error": f"Unknown action: {action}",
                    "response_type": "error"
                }
                
        except Exception as e:
            logger.error(f"Error handling user interaction: {str(e)}")
            return {
                "success": False,
                "error": "Failed to process interaction",
                "response_type": "error"
            }
    
    def _handle_content_interaction(self, user_id: str, content_id: str, 
                                  interaction_type_str: str, 
                                  interaction_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle content interaction (like, save, react, etc.)"""
        try:
            interaction_type = InteractionType(interaction_type_str)
        except ValueError:
            return {
                "success": False,
                "error": f"Invalid interaction type: {interaction_type_str}",
                "response_type": "error"
            }
        
        # Create interaction record
        interaction_record = UserInteractionRecord(
            interaction_id=str(uuid.uuid4()),
            user_id=user_id,
            content_id=content_id,
            interaction_type=interaction_type,
            timestamp=datetime.now(timezone.utc)
        )
        
        # Handle specific interaction types
        response_message = ""
        
        if interaction_type == InteractionType.LIKE:
            # Remove any existing unlike, add like
            self._remove_user_interaction(user_id, content_id, InteractionType.UNLIKE)
            response_message = "❤️ Liked! Thanks for your feedback."
            
        elif interaction_type == InteractionType.UNLIKE:
            # Remove any existing like, add unlike
            self._remove_user_interaction(user_id, content_id, InteractionType.LIKE)
            response_message = "💔 Unliked. We'll improve our content."
            
        elif interaction_type == InteractionType.SAVE:
            # Remove any existing unsave, add save
            self._remove_user_interaction(user_id, content_id, InteractionType.UNSAVE)
            response_message = "🔖 Saved to your collection!"
            
        elif interaction_type == InteractionType.UNSAVE:
            # Remove any existing save, add unsave
            self._remove_user_interaction(user_id, content_id, InteractionType.SAVE)
            response_message = "📌 Removed from your collection."
            
        elif interaction_type == InteractionType.SHARE:
            response_message = "📤 Thanks for sharing!"
            
        elif interaction_type == InteractionType.REACT:
            reaction_name = interaction_data.get("reaction")
            if reaction_name:
                try:
                    reaction_type = ReactionType[reaction_name]
                    interaction_record.reaction_type = reaction_type
                    response_message = f"{reaction_type.value} Thanks for your reaction!"
                except KeyError:
                    response_message = "😊 Thanks for your reaction!"
            else:
                response_message = "😊 Thanks for your reaction!"
        
        # Store interaction
        self.user_interactions.append(interaction_record)
        
        # Update statistics
        self._update_content_stats(content_id, interaction_type, interaction_record)
        self._update_user_profile(user_id, interaction_type, interaction_record)
        
        # Track analytics
        self._track_analytics_interaction(user_id, interaction_type, content_id, interaction_data)
        
        logger.info(f"Processed {interaction_type.value} interaction for user {user_id[:8]}... on content {content_id}")
        
        return {
            "success": True,
            "response_type": "message",
            "message": response_message,
            "interaction_id": interaction_record.interaction_id,
            "updated_stats": self.get_content_stats(content_id)
        }
    
    def _handle_show_reactions(self, content_id: str) -> Dict[str, Any]:
        """Handle request to show reaction options"""
        return {
            "success": True,
            "response_type": "quick_reply",
            "quick_reply": self.create_reaction_quick_reply(content_id),
            "message": "How did this content make you feel?"
        }
    
    def _handle_share_platform(self, user_id: str, content_id: str, platform: str) -> Dict[str, Any]:
        """Handle platform-specific sharing"""
        # Record the share interaction
        interaction_record = UserInteractionRecord(
            interaction_id=str(uuid.uuid4()),
            user_id=user_id,
            content_id=content_id,
            interaction_type=InteractionType.SHARE,
            timestamp=datetime.now(timezone.utc),
            share_platform=platform
        )
        
        self.user_interactions.append(interaction_record)
        self._update_content_stats(content_id, InteractionType.SHARE, interaction_record)
        self._update_user_profile(user_id, InteractionType.SHARE, interaction_record)
        
        # Platform-specific responses
        if platform == "line":
            return {
                "success": True,
                "response_type": "message",
                "message": "📱 Content shared to LINE! Your friends will love this."
            }
        elif platform == "copy":
            return {
                "success": True,
                "response_type": "message", 
                "message": "📋 Link copied! You can paste it anywhere."
            }
        elif platform == "email":
            return {
                "success": True,
                "response_type": "message",
                "message": "✉️ Email template ready! Check your email app."
            }
        else:
            return {
                "success": True,
                "response_type": "message",
                "message": "📤 Content shared successfully!"
            }
    
    def _remove_user_interaction(self, user_id: str, content_id: str, 
                                interaction_type: InteractionType) -> None:
        """Remove existing interaction of specific type for user and content"""
        self.user_interactions = [
            i for i in self.user_interactions
            if not (i.user_id == user_id and 
                   i.content_id == content_id and 
                   i.interaction_type == interaction_type)
        ]
    
    def _update_content_stats(self, content_id: str, interaction_type: InteractionType,
                            interaction_record: UserInteractionRecord) -> None:
        """Update content interaction statistics"""
        if content_id not in self.content_stats:
            self.content_stats[content_id] = ContentInteractionStats(content_id)
        
        stats = self.content_stats[content_id]
        
        # Update timestamp tracking
        if stats.first_interaction is None:
            stats.first_interaction = interaction_record.timestamp
        stats.last_interaction = interaction_record.timestamp
        
        # Update interaction counts
        if interaction_type == InteractionType.LIKE:
            stats.total_likes += 1
        elif interaction_type == InteractionType.UNLIKE:
            stats.total_likes = max(0, stats.total_likes - 1)
        elif interaction_type == InteractionType.SAVE:
            stats.total_saves += 1
        elif interaction_type == InteractionType.UNSAVE:
            stats.total_saves = max(0, stats.total_saves - 1)
        elif interaction_type == InteractionType.SHARE:
            stats.total_shares += 1
        elif interaction_type == InteractionType.REACT:
            stats.total_reactions += 1
            
            # Update reaction breakdown
            if interaction_record.reaction_type:
                reaction_name = interaction_record.reaction_type.name
                stats.reaction_counts[reaction_name] = stats.reaction_counts.get(reaction_name, 0) + 1
        elif interaction_type == InteractionType.COMMENT:
            stats.total_comments += 1
        
        # Recalculate engagement metrics (simplified)
        total_views = max(1, stats.total_likes + stats.total_shares + stats.total_saves + 50)  # Estimate views
        stats.engagement_rate = (stats.total_likes + stats.total_shares + stats.total_saves + stats.total_reactions) / total_views
        stats.like_rate = stats.total_likes / total_views
        stats.share_rate = stats.total_shares / total_views
        stats.save_rate = stats.total_saves / total_views
    
    def _update_user_profile(self, user_id: str, interaction_type: InteractionType,
                           interaction_record: UserInteractionRecord) -> None:
        """Update user engagement profile"""
        if user_id not in self.user_profiles:
            self.user_profiles[user_id] = UserEngagementProfile(user_id)
        
        profile = self.user_profiles[user_id]
        profile.total_interactions += 1
        profile.last_interaction = interaction_record.timestamp
        
        # Update interaction counts
        if interaction_type == InteractionType.LIKE:
            profile.likes_given += 1
        elif interaction_type == InteractionType.SHARE:
            profile.shares_made += 1
        elif interaction_type == InteractionType.SAVE:
            profile.content_saved += 1
        elif interaction_type == InteractionType.REACT:
            profile.reactions_made += 1
            
            # Track preferred reactions
            if interaction_record.reaction_type:
                if interaction_record.reaction_type not in profile.preferred_reaction_types:
                    profile.preferred_reaction_types.append(interaction_record.reaction_type)
        elif interaction_type == InteractionType.COMMENT:
            profile.comments_posted += 1
        
        # Update activity hour tracking
        hour = interaction_record.timestamp.hour
        if hour not in profile.most_active_hours:
            profile.most_active_hours.append(hour)
        
        # Update engagement streak (simplified)
        if profile.last_interaction:
            time_diff = interaction_record.timestamp - profile.last_interaction
            if time_diff.days <= 1:
                profile.engagement_streak += 1
            else:
                profile.engagement_streak = 1
    
    def get_content_stats(self, content_id: str) -> Optional[ContentInteractionStats]:
        """Get interaction statistics for specific content"""
        return self.content_stats.get(content_id)
    
    def get_user_profile(self, user_id: str) -> Optional[UserEngagementProfile]:
        """Get engagement profile for specific user"""
        return self.user_profiles.get(user_id)
    
    def get_top_engaged_content(self, limit: int = 10) -> List[Tuple[str, ContentInteractionStats]]:
        """
        Get top engaged content by engagement rate.
        
        Args:
            limit: Maximum number of results
            
        Returns:
            List of (content_id, stats) tuples sorted by engagement
        """
        content_list = list(self.content_stats.items())
        content_list.sort(key=lambda x: x[1].engagement_rate, reverse=True)
        return content_list[:limit]
    
    def get_user_saved_content(self, user_id: str) -> List[str]:
        """Get list of content IDs saved by user"""
        saved_content = []
        for interaction in self.user_interactions:
            if (interaction.user_id == user_id and 
                interaction.interaction_type == InteractionType.SAVE):
                if interaction.content_id not in saved_content:
                    saved_content.append(interaction.content_id)
        
        # Remove unsaved content
        for interaction in self.user_interactions:
            if (interaction.user_id == user_id and 
                interaction.interaction_type == InteractionType.UNSAVE):
                if interaction.content_id in saved_content:
                    saved_content.remove(interaction.content_id)
        
        return saved_content
    
    def get_engagement_summary(self) -> Dict[str, Any]:
        """Get overall engagement summary statistics"""
        if not self.user_interactions:
            return {
                "total_interactions": 0,
                "total_users": 0,
                "total_content": 0,
                "top_interaction_types": {},
                "engagement_summary": "No interactions recorded"
            }
        
        # Count interaction types
        interaction_counts = {}
        users = set()
        content_ids = set()
        
        for interaction in self.user_interactions:
            interaction_type = interaction.interaction_type.value
            interaction_counts[interaction_type] = interaction_counts.get(interaction_type, 0) + 1
            users.add(interaction.user_id)
            content_ids.add(interaction.content_id)
        
        # Calculate averages
        total_interactions = len(self.user_interactions)
        avg_interactions_per_user = total_interactions / len(users) if users else 0
        avg_interactions_per_content = total_interactions / len(content_ids) if content_ids else 0
        
        return {
            "total_interactions": total_interactions,
            "total_users": len(users),
            "total_content": len(content_ids),
            "interaction_type_counts": interaction_counts,
            "average_interactions_per_user": avg_interactions_per_user,
            "average_interactions_per_content": avg_interactions_per_content,
            "most_popular_interaction": max(interaction_counts.items(), key=lambda x: x[1])[0] if interaction_counts else None
        }
    
    def cleanup_old_interactions(self, days_to_keep: Optional[int] = None) -> int:
        """
        Clean up old interaction records.
        
        Args:
            days_to_keep: Days to keep (defaults to instance setting)
            
        Returns:
            Number of interactions removed
        """
        if days_to_keep is None:
            days_to_keep = self.interaction_retention_days
        
        cutoff_time = datetime.now(timezone.utc) - timedelta(days=days_to_keep)
        
        old_count = len(self.user_interactions)
        self.user_interactions = [
            interaction for interaction in self.user_interactions
            if interaction.timestamp >= cutoff_time
        ]
        
        removed_count = old_count - len(self.user_interactions)
        
        if removed_count > 0:
            logger.info(f"Cleaned up {removed_count} old interaction records")
        
        return removed_count
    
    def _track_analytics_interaction(self, user_id: str, interaction_type: InteractionType, 
                                   content_id: str, interaction_data: Dict[str, Any]) -> None:
        """Track interaction with analytics system."""
        try:
            # Map interaction types to analytics interaction types
            analytics_type_mapping = {
                InteractionType.LIKE: AnalyticsInteractionType.BUTTON_CLICKED,
                InteractionType.UNLIKE: AnalyticsInteractionType.BUTTON_CLICKED,
                InteractionType.SHARE: AnalyticsInteractionType.CONTENT_SHARED,
                InteractionType.SAVE: AnalyticsInteractionType.CONTENT_SAVED,
                InteractionType.UNSAVE: AnalyticsInteractionType.BUTTON_CLICKED,
                InteractionType.REACT: AnalyticsInteractionType.BUTTON_CLICKED,
                InteractionType.COMMENT: AnalyticsInteractionType.FEEDBACK_PROVIDED,
                InteractionType.FEEDBACK: AnalyticsInteractionType.FEEDBACK_PROVIDED,
            }
            
            analytics_type = analytics_type_mapping.get(interaction_type, AnalyticsInteractionType.BUTTON_CLICKED)
            
            # Extract content category from content_id if available
            content_category = "rich_message"  # Default category
            
            # Track the interaction
            self.analytics_tracker.track_user_interaction(
                user_id=user_id,
                interaction_type=analytics_type,
                content_category=content_category,
                template_id=content_id,
                additional_data={
                    "interaction_subtype": interaction_type.value,
                    "reaction_type": interaction_data.get("reaction"),
                    "platform": interaction_data.get("platform"),
                    "original_data": interaction_data
                }
            )
            
            logger.debug(f"Tracked analytics for {interaction_type.value} interaction")
            
        except Exception as e:
            logger.error(f"Failed to track analytics interaction: {str(e)}")
    
    def get_engagement_analytics_summary(self) -> Dict[str, Any]:
        """Get comprehensive engagement analytics summary."""
        try:
            # Get analytics summary
            analytics_summary = self.analytics_tracker.get_user_engagement_summary()
            
            # Get top performing content from analytics
            top_content = self.analytics_tracker.get_top_performing_content(limit=5)
            
            # Get system metrics
            system_metrics = self.analytics_tracker.calculate_system_metrics()
            
            # Combine with local interaction stats
            local_summary = self.get_engagement_summary()
            
            return {
                "analytics_summary": analytics_summary,
                "top_performing_content": [
                    {
                        "content_key": content_key,
                        "open_rate": metrics.open_rate,
                        "interaction_rate": metrics.interaction_rate,
                        "total_interactions": metrics.total_interactions
                    } for content_key, metrics in top_content
                ],
                "system_metrics": {
                    "total_users": system_metrics.total_users,
                    "active_users": system_metrics.active_users,
                    "overall_open_rate": system_metrics.overall_open_rate,
                    "overall_interaction_rate": system_metrics.overall_interaction_rate,
                    "user_retention_rate": system_metrics.user_retention_rate
                },
                "local_interaction_summary": local_summary,
                "combined_metrics": {
                    "total_rich_message_interactions": local_summary.get("total_interactions", 0),
                    "most_popular_interaction_type": local_summary.get("most_popular_interaction"),
                    "engagement_trend": "stable"  # This could be calculated based on time series data
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to generate engagement analytics summary: {str(e)}")
            return {
                "error": "Failed to generate analytics summary",
                "local_interaction_summary": self.get_engagement_summary()
            }


# Global interaction handler instance
_interaction_handler = None

def get_interaction_handler() -> InteractionHandler:
    """Get global interaction handler instance."""
    global _interaction_handler
    if _interaction_handler is None:
        _interaction_handler = InteractionHandler()
    return _interaction_handler