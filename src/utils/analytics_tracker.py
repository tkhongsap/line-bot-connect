"""
Analytics Tracking and Success Rate Monitoring for Rich Message automation.

This module provides comprehensive analytics tracking, user engagement metrics,
and success rate monitoring for the Rich Message automation system.
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
import json
import uuid

from src.utils.metrics_storage import get_metrics_storage, EngagementMetric

logger = logging.getLogger(__name__)


class InteractionType(Enum):
    """User interaction types"""
    MESSAGE_RECEIVED = "message_received"
    MESSAGE_OPENED = "message_opened"
    BUTTON_CLICKED = "button_clicked"
    CONTENT_SHARED = "content_shared"
    CONTENT_SAVED = "content_saved"
    FEEDBACK_PROVIDED = "feedback_provided"
    PREFERENCE_UPDATED = "preference_updated"


class ContentRating(Enum):
    """Content rating values"""
    EXCELLENT = "excellent"
    GOOD = "good"
    AVERAGE = "average"
    POOR = "poor"
    TERRIBLE = "terrible"


@dataclass
class UserInteraction:
    """Individual user interaction record"""
    interaction_id: str
    user_id: str
    timestamp: datetime
    interaction_type: InteractionType
    content_category: str
    template_id: Optional[str] = None
    
    # Interaction details
    additional_data: Dict[str, Any] = field(default_factory=dict)
    response_time_ms: Optional[int] = None
    
    # Location context
    timezone: Optional[str] = None
    local_time: Optional[str] = None


@dataclass
class UserEngagementMetrics:
    """User engagement metrics"""
    user_id: str
    total_messages_received: int = 0
    total_messages_opened: int = 0
    total_interactions: int = 0
    
    # Engagement rates
    open_rate: float = 0.0
    interaction_rate: float = 0.0
    
    # Content preferences
    preferred_categories: List[str] = field(default_factory=list)
    preferred_times: List[str] = field(default_factory=list)
    content_ratings: Dict[str, List[ContentRating]] = field(default_factory=dict)
    
    # Temporal data
    first_interaction: Optional[datetime] = None
    last_interaction: Optional[datetime] = None
    days_active: int = 0
    
    # Response patterns
    average_response_time_ms: float = 0.0
    fastest_response_time_ms: Optional[int] = None
    
    # Feedback
    total_feedback_count: int = 0
    average_content_rating: Optional[float] = None


@dataclass
class ContentPerformanceMetrics:
    """Content performance metrics"""
    content_category: str
    template_id: Optional[str] = None
    
    # Delivery metrics
    total_sent: int = 0
    total_delivered: int = 0
    total_opened: int = 0
    total_interactions: int = 0
    
    # Performance rates
    delivery_rate: float = 0.0
    open_rate: float = 0.0
    interaction_rate: float = 0.0
    
    # Timing metrics
    average_delivery_time_ms: float = 0.0
    average_response_time_ms: float = 0.0
    
    # Feedback
    total_ratings: int = 0
    average_rating: float = 0.0
    rating_distribution: Dict[str, int] = field(default_factory=dict)
    
    # Time-based performance
    performance_by_hour: Dict[int, Dict[str, float]] = field(default_factory=dict)
    performance_by_day: Dict[str, Dict[str, float]] = field(default_factory=dict)


@dataclass
class SystemPerformanceMetrics:
    """Overall system performance metrics"""
    # Time period
    start_time: datetime
    end_time: datetime
    
    # Overall metrics
    total_users: int = 0
    active_users: int = 0
    total_deliveries: int = 0
    successful_deliveries: int = 0
    total_interactions: int = 0
    
    # System rates
    overall_delivery_rate: float = 0.0
    overall_open_rate: float = 0.0
    overall_interaction_rate: float = 0.0
    user_retention_rate: float = 0.0
    
    # Performance metrics
    average_delivery_time_ms: float = 0.0
    average_processing_time_ms: float = 0.0
    system_uptime_percentage: float = 0.0
    
    # Category breakdown
    category_performance: Dict[str, ContentPerformanceMetrics] = field(default_factory=dict)
    
    # Timezone breakdown
    timezone_performance: Dict[str, Dict[str, float]] = field(default_factory=dict)
    
    # Trends
    daily_trends: Dict[str, Dict[str, float]] = field(default_factory=dict)
    hourly_trends: Dict[int, Dict[str, float]] = field(default_factory=dict)


class AnalyticsTracker:
    """
    Comprehensive analytics tracking and monitoring system.
    
    Tracks user interactions, engagement metrics, content performance,
    and overall system health for Rich Message automation.
    """
    
    def __init__(self):
        """Initialize the AnalyticsTracker."""
        self.user_interactions: List[UserInteraction] = []
        self.user_metrics: Dict[str, UserEngagementMetrics] = {}
        self.content_metrics: Dict[str, ContentPerformanceMetrics] = {}
        
        # Performance tracking
        self.start_time = datetime.now(timezone.utc)
        self.last_metrics_calculation = datetime.now(timezone.utc)
        self.cached_system_metrics: Optional[SystemPerformanceMetrics] = None
        
        # Configuration
        self.interaction_retention_days = 30  # Keep interactions for 30 days
        self.metrics_cache_minutes = 5  # Cache system metrics for 5 minutes
        
        # Persistent storage
        self.metrics_storage = get_metrics_storage()
        
        logger.info("AnalyticsTracker initialized with persistent storage")
    
    def track_user_interaction(self, user_id: str, interaction_type: InteractionType,
                              content_category: str, template_id: Optional[str] = None,
                              timezone_name: Optional[str] = None,
                              additional_data: Optional[Dict[str, Any]] = None,
                              response_time_ms: Optional[int] = None) -> str:
        """
        Track a user interaction.
        
        Args:
            user_id: User identifier
            interaction_type: Type of interaction
            content_category: Content category
            template_id: Optional template identifier
            timezone_name: User's timezone
            additional_data: Additional interaction data
            response_time_ms: Response time in milliseconds
            
        Returns:
            Interaction ID
        """
        timestamp = datetime.now(timezone.utc)
        interaction_id = f"interaction_{user_id}_{int(timestamp.timestamp())}"
        
        # Create local time string if timezone provided
        local_time = None
        if timezone_name:
            try:
                from zoneinfo import ZoneInfo
                local_dt = timestamp.astimezone(ZoneInfo(timezone_name))
                local_time = local_dt.strftime("%H:%M:%S")
            except Exception:
                pass
        
        interaction = UserInteraction(
            interaction_id=interaction_id,
            user_id=user_id,
            timestamp=timestamp,
            interaction_type=interaction_type,
            content_category=content_category,
            template_id=template_id,
            additional_data=additional_data or {},
            response_time_ms=response_time_ms,
            timezone=timezone_name,
            local_time=local_time
        )
        
        self.user_interactions.append(interaction)
        
        # Update user metrics
        self._update_user_metrics(user_id, interaction)
        
        # Update content metrics
        self._update_content_metrics(content_category, template_id, interaction)
        
        # Store to persistent storage
        self._store_interaction_persistently(interaction)
        
        logger.debug(f"Tracked {interaction_type.value} interaction for user {user_id[:8]}...")
        
        return interaction_id
    
    def track_message_delivery(self, user_id: str, content_category: str,
                             template_id: Optional[str] = None,
                             delivery_time_ms: Optional[int] = None,
                             timezone_name: Optional[str] = None) -> None:
        """
        Track message delivery.
        
        Args:
            user_id: User identifier
            content_category: Content category
            template_id: Template identifier
            delivery_time_ms: Delivery time in milliseconds
            timezone_name: User's timezone
        """
        self.track_user_interaction(
            user_id=user_id,
            interaction_type=InteractionType.MESSAGE_RECEIVED,
            content_category=content_category,
            template_id=template_id,
            timezone_name=timezone_name,
            additional_data={'delivery_time_ms': delivery_time_ms},
            response_time_ms=delivery_time_ms
        )
    
    def track_content_rating(self, user_id: str, content_category: str,
                           rating: ContentRating, template_id: Optional[str] = None,
                           feedback_text: Optional[str] = None) -> None:
        """
        Track content rating and feedback.
        
        Args:
            user_id: User identifier
            content_category: Content category
            rating: Content rating
            template_id: Template identifier
            feedback_text: Optional feedback text
        """
        additional_data = {'rating': rating.value}
        if feedback_text:
            additional_data['feedback_text'] = feedback_text
        
        self.track_user_interaction(
            user_id=user_id,
            interaction_type=InteractionType.FEEDBACK_PROVIDED,
            content_category=content_category,
            template_id=template_id,
            additional_data=additional_data
        )
    
    def _update_user_metrics(self, user_id: str, interaction: UserInteraction) -> None:
        """Update user engagement metrics."""
        if user_id not in self.user_metrics:
            self.user_metrics[user_id] = UserEngagementMetrics(user_id=user_id)
        
        metrics = self.user_metrics[user_id]
        
        # Update interaction counts
        metrics.total_interactions += 1
        
        if interaction.interaction_type == InteractionType.MESSAGE_RECEIVED:
            metrics.total_messages_received += 1
        elif interaction.interaction_type == InteractionType.MESSAGE_OPENED:
            metrics.total_messages_opened += 1
        
        # Update timing
        if metrics.first_interaction is None:
            metrics.first_interaction = interaction.timestamp
        metrics.last_interaction = interaction.timestamp
        
        # Update response time
        if interaction.response_time_ms:
            if metrics.average_response_time_ms == 0:
                metrics.average_response_time_ms = interaction.response_time_ms
            else:
                # Running average
                total_interactions = metrics.total_interactions
                metrics.average_response_time_ms = (
                    (metrics.average_response_time_ms * (total_interactions - 1) + 
                     interaction.response_time_ms) / total_interactions
                )
            
            if (metrics.fastest_response_time_ms is None or 
                interaction.response_time_ms < metrics.fastest_response_time_ms):
                metrics.fastest_response_time_ms = interaction.response_time_ms
        
        # Update content preferences
        if interaction.content_category not in metrics.preferred_categories:
            metrics.preferred_categories.append(interaction.content_category)
        
        # Update time preferences
        if interaction.local_time and interaction.local_time not in metrics.preferred_times:
            metrics.preferred_times.append(interaction.local_time)
        
        # Handle ratings
        if interaction.interaction_type == InteractionType.FEEDBACK_PROVIDED:
            rating_data = interaction.additional_data.get('rating')
            if rating_data:
                category = interaction.content_category
                if category not in metrics.content_ratings:
                    metrics.content_ratings[category] = []
                
                try:
                    rating = ContentRating(rating_data)
                    metrics.content_ratings[category].append(rating)
                    metrics.total_feedback_count += 1
                    
                    # Calculate average rating
                    all_ratings = []
                    for cat_ratings in metrics.content_ratings.values():
                        all_ratings.extend(cat_ratings)
                    
                    if all_ratings:
                        rating_values = {
                            ContentRating.EXCELLENT: 5,
                            ContentRating.GOOD: 4,
                            ContentRating.AVERAGE: 3,
                            ContentRating.POOR: 2,
                            ContentRating.TERRIBLE: 1
                        }
                        total_score = sum(rating_values[r] for r in all_ratings)
                        metrics.average_content_rating = total_score / len(all_ratings)
                except ValueError:
                    pass
        
        # Calculate engagement rates
        if metrics.total_messages_received > 0:
            metrics.open_rate = metrics.total_messages_opened / metrics.total_messages_received
            metrics.interaction_rate = metrics.total_interactions / metrics.total_messages_received
        
        # Calculate days active
        if metrics.first_interaction and metrics.last_interaction:
            days_diff = (metrics.last_interaction - metrics.first_interaction).days
            metrics.days_active = max(1, days_diff)
    
    def _update_content_metrics(self, content_category: str, template_id: Optional[str],
                               interaction: UserInteraction) -> None:
        """Update content performance metrics."""
        # Use category as key, or category+template if template specified
        metrics_key = content_category
        if template_id:
            metrics_key = f"{content_category}:{template_id}"
        
        if metrics_key not in self.content_metrics:
            self.content_metrics[metrics_key] = ContentPerformanceMetrics(
                content_category=content_category,
                template_id=template_id
            )
        
        metrics = self.content_metrics[metrics_key]
        
        # Update counts based on interaction type
        if interaction.interaction_type == InteractionType.MESSAGE_RECEIVED:
            metrics.total_sent += 1
            metrics.total_delivered += 1  # Assume delivered if received
            
            # Update delivery time
            delivery_time = interaction.additional_data.get('delivery_time_ms')
            if delivery_time:
                if metrics.average_delivery_time_ms == 0:
                    metrics.average_delivery_time_ms = delivery_time
                else:
                    # Running average
                    metrics.average_delivery_time_ms = (
                        (metrics.average_delivery_time_ms * (metrics.total_delivered - 1) + 
                         delivery_time) / metrics.total_delivered
                    )
        
        elif interaction.interaction_type == InteractionType.MESSAGE_OPENED:
            metrics.total_opened += 1
        
        elif interaction.interaction_type in [
            InteractionType.BUTTON_CLICKED,
            InteractionType.CONTENT_SHARED,
            InteractionType.CONTENT_SAVED
        ]:
            metrics.total_interactions += 1
        
        elif interaction.interaction_type == InteractionType.FEEDBACK_PROVIDED:
            rating_data = interaction.additional_data.get('rating')
            if rating_data:
                try:
                    rating = ContentRating(rating_data)
                    metrics.total_ratings += 1
                    
                    # Update rating distribution
                    rating_value = rating.value
                    metrics.rating_distribution[rating_value] = (
                        metrics.rating_distribution.get(rating_value, 0) + 1
                    )
                    
                    # Calculate average rating
                    rating_values = {
                        ContentRating.EXCELLENT: 5,
                        ContentRating.GOOD: 4,
                        ContentRating.AVERAGE: 3,
                        ContentRating.POOR: 2,
                        ContentRating.TERRIBLE: 1
                    }
                    total_score = sum(
                        rating_values[ContentRating(r)] * count 
                        for r, count in metrics.rating_distribution.items()
                    )
                    metrics.average_rating = total_score / metrics.total_ratings
                except ValueError:
                    pass
        
        # Update response time
        if interaction.response_time_ms:
            if metrics.average_response_time_ms == 0:
                metrics.average_response_time_ms = interaction.response_time_ms
            else:
                total_interactions = (metrics.total_opened + metrics.total_interactions + 
                                    metrics.total_ratings)
                if total_interactions > 0:
                    metrics.average_response_time_ms = (
                        (metrics.average_response_time_ms * (total_interactions - 1) + 
                         interaction.response_time_ms) / total_interactions
                    )
        
        # Calculate performance rates
        if metrics.total_sent > 0:
            metrics.delivery_rate = metrics.total_delivered / metrics.total_sent
        
        if metrics.total_delivered > 0:
            metrics.open_rate = metrics.total_opened / metrics.total_delivered
            metrics.interaction_rate = metrics.total_interactions / metrics.total_delivered
        
        # Update time-based performance
        hour = interaction.timestamp.hour
        day_name = interaction.timestamp.strftime('%A')
        
        # Initialize hour performance if not exists
        if hour not in metrics.performance_by_hour:
            metrics.performance_by_hour[hour] = {
                'total_sent': 0, 'total_opened': 0, 'total_interactions': 0
            }
        
        # Initialize day performance if not exists
        if day_name not in metrics.performance_by_day:
            metrics.performance_by_day[day_name] = {
                'total_sent': 0, 'total_opened': 0, 'total_interactions': 0
            }
        
        # Update hour and day performance
        if interaction.interaction_type == InteractionType.MESSAGE_RECEIVED:
            metrics.performance_by_hour[hour]['total_sent'] += 1
            metrics.performance_by_day[day_name]['total_sent'] += 1
        elif interaction.interaction_type == InteractionType.MESSAGE_OPENED:
            metrics.performance_by_hour[hour]['total_opened'] += 1
            metrics.performance_by_day[day_name]['total_opened'] += 1
        elif interaction.interaction_type in [
            InteractionType.BUTTON_CLICKED,
            InteractionType.CONTENT_SHARED,
            InteractionType.CONTENT_SAVED
        ]:
            metrics.performance_by_hour[hour]['total_interactions'] += 1
            metrics.performance_by_day[day_name]['total_interactions'] += 1
    
    def get_user_metrics(self, user_id: str) -> Optional[UserEngagementMetrics]:
        """Get metrics for a specific user."""
        return self.user_metrics.get(user_id)
    
    def get_content_metrics(self, content_category: str, 
                          template_id: Optional[str] = None) -> Optional[ContentPerformanceMetrics]:
        """Get metrics for specific content."""
        metrics_key = content_category
        if template_id:
            metrics_key = f"{content_category}:{template_id}"
        return self.content_metrics.get(metrics_key)
    
    def calculate_system_metrics(self, force_recalculate: bool = False) -> SystemPerformanceMetrics:
        """
        Calculate comprehensive system performance metrics.
        
        Args:
            force_recalculate: Force recalculation even if cached
            
        Returns:
            SystemPerformanceMetrics object
        """
        now = datetime.now(timezone.utc)
        
        # Use cached metrics if recent and not forced
        if (not force_recalculate and 
            self.cached_system_metrics and 
            (now - self.last_metrics_calculation).total_seconds() < self.metrics_cache_minutes * 60):
            return self.cached_system_metrics
        
        # Calculate time period (last 24 hours or since start)
        start_time = max(self.start_time, now - timedelta(hours=24))
        end_time = now
        
        metrics = SystemPerformanceMetrics(
            start_time=start_time,
            end_time=end_time
        )
        
        # Calculate user metrics
        metrics.total_users = len(self.user_metrics)
        
        # Count active users (interacted in last 24 hours)
        active_users = set()
        total_deliveries = 0
        successful_deliveries = 0
        total_interactions = 0
        total_delivery_time = 0
        delivery_count = 0
        total_response_time = 0
        response_count = 0
        
        # Analyze interactions within time period
        for interaction in self.user_interactions:
            if start_time <= interaction.timestamp <= end_time:
                active_users.add(interaction.user_id)
                total_interactions += 1
                
                if interaction.interaction_type == InteractionType.MESSAGE_RECEIVED:
                    total_deliveries += 1
                    successful_deliveries += 1  # Assume successful if received
                    
                    delivery_time = interaction.additional_data.get('delivery_time_ms')
                    if delivery_time:
                        total_delivery_time += delivery_time
                        delivery_count += 1
                
                if interaction.response_time_ms:
                    total_response_time += interaction.response_time_ms
                    response_count += 1
        
        metrics.active_users = len(active_users)
        metrics.total_deliveries = total_deliveries
        metrics.successful_deliveries = successful_deliveries
        metrics.total_interactions = total_interactions
        
        # Calculate rates
        if total_deliveries > 0:
            metrics.overall_delivery_rate = successful_deliveries / total_deliveries
            
            # Count opened messages
            opened_count = sum(1 for i in self.user_interactions 
                             if (start_time <= i.timestamp <= end_time and 
                                 i.interaction_type == InteractionType.MESSAGE_OPENED))
            metrics.overall_open_rate = opened_count / successful_deliveries
            
            # Count interactive messages
            interactive_count = sum(1 for i in self.user_interactions 
                                  if (start_time <= i.timestamp <= end_time and 
                                      i.interaction_type in [
                                          InteractionType.BUTTON_CLICKED,
                                          InteractionType.CONTENT_SHARED,
                                          InteractionType.CONTENT_SAVED
                                      ]))
            metrics.overall_interaction_rate = interactive_count / successful_deliveries
        
        # Calculate retention rate (users active in both periods)
        if metrics.total_users > 0:
            # Simple retention: active users / total users
            metrics.user_retention_rate = metrics.active_users / metrics.total_users
        
        # Calculate average times
        if delivery_count > 0:
            metrics.average_delivery_time_ms = total_delivery_time / delivery_count
        
        if response_count > 0:
            metrics.average_processing_time_ms = total_response_time / response_count
        
        # Calculate uptime percentage (simplified - based on expected vs actual interactions)
        uptime_hours = (end_time - start_time).total_seconds() / 3600
        expected_interactions_per_hour = max(1, metrics.total_users * 0.1)  # Assume 10% interaction rate per hour
        expected_total = expected_interactions_per_hour * uptime_hours
        if expected_total > 0:
            metrics.system_uptime_percentage = min(100.0, (total_interactions / expected_total) * 100)
        else:
            metrics.system_uptime_percentage = 100.0
        
        # Aggregate category performance
        for content_key, content_metrics in self.content_metrics.items():
            category = content_metrics.content_category
            if category not in metrics.category_performance:
                metrics.category_performance[category] = ContentPerformanceMetrics(
                    content_category=category
                )
            
            cat_metrics = metrics.category_performance[category]
            cat_metrics.total_sent += content_metrics.total_sent
            cat_metrics.total_delivered += content_metrics.total_delivered
            cat_metrics.total_opened += content_metrics.total_opened
            cat_metrics.total_interactions += content_metrics.total_interactions
            
            # Recalculate rates for aggregated data
            if cat_metrics.total_sent > 0:
                cat_metrics.delivery_rate = cat_metrics.total_delivered / cat_metrics.total_sent
            if cat_metrics.total_delivered > 0:
                cat_metrics.open_rate = cat_metrics.total_opened / cat_metrics.total_delivered
                cat_metrics.interaction_rate = cat_metrics.total_interactions / cat_metrics.total_delivered
        
        # Calculate timezone performance
        timezone_stats = {}
        for interaction in self.user_interactions:
            if (start_time <= interaction.timestamp <= end_time and 
                interaction.timezone):
                tz = interaction.timezone
                if tz not in timezone_stats:
                    timezone_stats[tz] = {'total': 0, 'opened': 0, 'interactions': 0}
                
                timezone_stats[tz]['total'] += 1
                if interaction.interaction_type == InteractionType.MESSAGE_OPENED:
                    timezone_stats[tz]['opened'] += 1
                elif interaction.interaction_type in [
                    InteractionType.BUTTON_CLICKED,
                    InteractionType.CONTENT_SHARED,
                    InteractionType.CONTENT_SAVED
                ]:
                    timezone_stats[tz]['interactions'] += 1
        
        # Convert to performance metrics
        for tz, stats in timezone_stats.items():
            metrics.timezone_performance[tz] = {
                'total_messages': stats['total'],
                'open_rate': stats['opened'] / max(1, stats['total']),
                'interaction_rate': stats['interactions'] / max(1, stats['total'])
            }
        
        # Calculate daily and hourly trends
        daily_stats = {}
        hourly_stats = {}
        
        for interaction in self.user_interactions:
            if start_time <= interaction.timestamp <= end_time:
                # Daily trends
                day_key = interaction.timestamp.strftime('%Y-%m-%d')
                if day_key not in daily_stats:
                    daily_stats[day_key] = {'total': 0, 'opened': 0, 'interactions': 0}
                
                daily_stats[day_key]['total'] += 1
                if interaction.interaction_type == InteractionType.MESSAGE_OPENED:
                    daily_stats[day_key]['opened'] += 1
                elif interaction.interaction_type in [
                    InteractionType.BUTTON_CLICKED,
                    InteractionType.CONTENT_SHARED,
                    InteractionType.CONTENT_SAVED
                ]:
                    daily_stats[day_key]['interactions'] += 1
                
                # Hourly trends
                hour = interaction.timestamp.hour
                if hour not in hourly_stats:
                    hourly_stats[hour] = {'total': 0, 'opened': 0, 'interactions': 0}
                
                hourly_stats[hour]['total'] += 1
                if interaction.interaction_type == InteractionType.MESSAGE_OPENED:
                    hourly_stats[hour]['opened'] += 1
                elif interaction.interaction_type in [
                    InteractionType.BUTTON_CLICKED,
                    InteractionType.CONTENT_SHARED,
                    InteractionType.CONTENT_SAVED
                ]:
                    hourly_stats[hour]['interactions'] += 1
        
        # Convert to trend metrics
        for day, stats in daily_stats.items():
            metrics.daily_trends[day] = {
                'total_messages': stats['total'],
                'open_rate': stats['opened'] / max(1, stats['total']),
                'interaction_rate': stats['interactions'] / max(1, stats['total'])
            }
        
        for hour, stats in hourly_stats.items():
            metrics.hourly_trends[hour] = {
                'total_messages': stats['total'],
                'open_rate': stats['opened'] / max(1, stats['total']),
                'interaction_rate': stats['interactions'] / max(1, stats['total'])
            }
        
        # Cache the results
        self.cached_system_metrics = metrics
        self.last_metrics_calculation = now
        
        logger.debug(f"Calculated system metrics: {metrics.total_users} users, "
                    f"{metrics.overall_delivery_rate:.2%} delivery rate")
        
        return metrics
    
    def get_top_performing_content(self, limit: int = 10) -> List[Tuple[str, ContentPerformanceMetrics]]:
        """
        Get top performing content by interaction rate.
        
        Args:
            limit: Maximum number of results
            
        Returns:
            List of (content_key, metrics) tuples sorted by performance
        """
        content_list = list(self.content_metrics.items())
        
        # Sort by interaction rate, then by open rate
        content_list.sort(
            key=lambda x: (x[1].interaction_rate, x[1].open_rate, x[1].total_interactions),
            reverse=True
        )
        
        return content_list[:limit]
    
    def get_user_engagement_summary(self, min_interactions: int = 5) -> Dict[str, Any]:
        """
        Get user engagement summary statistics.
        
        Args:
            min_interactions: Minimum interactions to be considered active
            
        Returns:
            Dictionary with engagement summary
        """
        active_users = [
            metrics for metrics in self.user_metrics.values()
            if metrics.total_interactions >= min_interactions
        ]
        
        if not active_users:
            return {
                'total_users': len(self.user_metrics),
                'active_users': 0,
                'engagement_summary': 'No active users'
            }
        
        # Calculate averages for active users
        avg_open_rate = sum(u.open_rate for u in active_users) / len(active_users)
        avg_interaction_rate = sum(u.interaction_rate for u in active_users) / len(active_users)
        avg_response_time = sum(u.average_response_time_ms for u in active_users) / len(active_users)
        
        # Find most popular categories
        category_counts = {}
        for user in active_users:
            for category in user.preferred_categories:
                category_counts[category] = category_counts.get(category, 0) + 1
        
        popular_categories = sorted(category_counts.items(), key=lambda x: x[1], reverse=True)
        
        return {
            'total_users': len(self.user_metrics),
            'active_users': len(active_users),
            'average_open_rate': avg_open_rate,
            'average_interaction_rate': avg_interaction_rate,
            'average_response_time_ms': avg_response_time,
            'popular_categories': popular_categories[:5],
            'engagement_distribution': {
                'high_engagement': len([u for u in active_users if u.interaction_rate > 0.5]),
                'medium_engagement': len([u for u in active_users if 0.2 <= u.interaction_rate <= 0.5]),
                'low_engagement': len([u for u in active_users if u.interaction_rate < 0.2])
            }
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
            # Force metrics recalculation
            self.cached_system_metrics = None
        
        return removed_count
    
    def export_analytics_data(self, start_date: Optional[datetime] = None,
                            end_date: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Export analytics data for external analysis.
        
        Args:
            start_date: Start date for export (optional)
            end_date: End date for export (optional)
            
        Returns:
            Dictionary with analytics data
        """
        if start_date is None:
            start_date = datetime.now(timezone.utc) - timedelta(days=30)
        if end_date is None:
            end_date = datetime.now(timezone.utc)
        
        # Filter interactions by date range
        filtered_interactions = [
            interaction for interaction in self.user_interactions
            if start_date <= interaction.timestamp <= end_date
        ]
        
        # Convert to serializable format
        interactions_data = []
        for interaction in filtered_interactions:
            interactions_data.append({
                'interaction_id': interaction.interaction_id,
                'user_id': interaction.user_id[:8] + "...",  # Anonymize
                'timestamp': interaction.timestamp.isoformat(),
                'interaction_type': interaction.interaction_type.value,
                'content_category': interaction.content_category,
                'template_id': interaction.template_id,
                'timezone': interaction.timezone,
                'local_time': interaction.local_time,
                'response_time_ms': interaction.response_time_ms,
                'additional_data': interaction.additional_data
            })
        
        # Export user metrics (anonymized)
        user_metrics_data = []
        for user_id, metrics in self.user_metrics.items():
            user_metrics_data.append({
                'user_id': user_id[:8] + "...",
                'total_messages_received': metrics.total_messages_received,
                'total_messages_opened': metrics.total_messages_opened,
                'total_interactions': metrics.total_interactions,
                'open_rate': metrics.open_rate,
                'interaction_rate': metrics.interaction_rate,
                'preferred_categories': metrics.preferred_categories,
                'average_response_time_ms': metrics.average_response_time_ms,
                'days_active': metrics.days_active,
                'total_feedback_count': metrics.total_feedback_count,
                'average_content_rating': metrics.average_content_rating
            })
        
        # Export content metrics
        content_metrics_data = []
        for content_key, metrics in self.content_metrics.items():
            content_metrics_data.append({
                'content_key': content_key,
                'content_category': metrics.content_category,
                'template_id': metrics.template_id,
                'total_sent': metrics.total_sent,
                'total_delivered': metrics.total_delivered,
                'total_opened': metrics.total_opened,
                'total_interactions': metrics.total_interactions,
                'delivery_rate': metrics.delivery_rate,
                'open_rate': metrics.open_rate,
                'interaction_rate': metrics.interaction_rate,
                'average_delivery_time_ms': metrics.average_delivery_time_ms,
                'average_response_time_ms': metrics.average_response_time_ms,
                'average_rating': metrics.average_rating,
                'rating_distribution': metrics.rating_distribution
            })
        
        return {
            'export_metadata': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'total_interactions': len(filtered_interactions),
                'total_users': len(self.user_metrics),
                'total_content_items': len(self.content_metrics),
                'export_timestamp': datetime.now(timezone.utc).isoformat()
            },
            'interactions': interactions_data,
            'user_metrics': user_metrics_data,
            'content_metrics': content_metrics_data,
            'system_metrics': self.calculate_system_metrics(force_recalculate=True).__dict__
        }
    
    def _store_interaction_persistently(self, interaction: UserInteraction) -> None:
        """Store interaction to persistent storage."""
        try:
            # Convert UserInteraction to EngagementMetric
            engagement_metric = EngagementMetric(
                metric_id=interaction.interaction_id,
                user_id=interaction.user_id,
                content_id=interaction.template_id or f"{interaction.content_category}_content",
                interaction_type=interaction.interaction_type.value,
                timestamp=interaction.timestamp,
                response_time_ms=interaction.response_time_ms,
                content_category=interaction.content_category,
                template_id=interaction.template_id,
                user_timezone=interaction.timezone,
                platform="line_bot",
                metadata=interaction.additional_data or {}
            )
            
            # Store to persistent storage
            success = self.metrics_storage.store_metric(engagement_metric)
            if not success:
                logger.warning(f"Failed to store interaction {interaction.interaction_id} persistently")
                
        except Exception as e:
            logger.error(f"Error storing interaction persistently: {str(e)}")
    
    def get_persistent_metrics_summary(self, days: int = 7) -> Dict[str, Any]:
        """Get metrics summary from persistent storage."""
        try:
            end_date = datetime.now(timezone.utc)
            start_date = end_date - timedelta(days=days)
            
            # Get aggregated metrics from storage
            aggregated = self.metrics_storage.calculate_aggregated_metrics(
                time_period="daily",
                start_date=start_date,
                end_date=end_date
            )
            
            # Get storage statistics
            storage_stats = self.metrics_storage.get_storage_statistics()
            
            if aggregated:
                return {
                    "period_days": days,
                    "period_start": start_date.isoformat(),
                    "period_end": end_date.isoformat(),
                    "total_interactions": aggregated.total_interactions,
                    "unique_users": aggregated.unique_users,
                    "engagement_rates": {
                        "like_rate": aggregated.like_rate,
                        "share_rate": aggregated.share_rate,
                        "save_rate": aggregated.save_rate,
                        "reaction_rate": aggregated.reaction_rate
                    },
                    "performance_metrics": {
                        "avg_response_time_ms": aggregated.avg_response_time_ms,
                        "avg_engagement_score": aggregated.avg_engagement_score
                    },
                    "top_content": {
                        "categories": aggregated.top_content_categories,
                        "templates": aggregated.top_templates
                    },
                    "user_segments": {
                        "high_engagement": aggregated.high_engagement_users,
                        "medium_engagement": aggregated.medium_engagement_users,
                        "low_engagement": aggregated.low_engagement_users
                    },
                    "storage_info": storage_stats
                }
            else:
                return {
                    "period_days": days,
                    "total_interactions": 0,
                    "message": "No metrics data available for the specified period",
                    "storage_info": storage_stats
                }
                
        except Exception as e:
            logger.error(f"Error getting persistent metrics summary: {str(e)}")
            return {
                "error": str(e),
                "period_days": days
            }


# Global analytics tracker instance
_analytics_tracker = None

def get_analytics_tracker() -> AnalyticsTracker:
    """Get global analytics tracker instance."""
    global _analytics_tracker
    if _analytics_tracker is None:
        _analytics_tracker = AnalyticsTracker()
    return _analytics_tracker