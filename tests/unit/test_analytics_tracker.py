"""
Unit tests for AnalyticsTracker
"""

import pytest
from unittest.mock import patch, Mock
from datetime import datetime, timedelta, timezone

from src.utils.analytics_tracker import (
    AnalyticsTracker, UserInteraction, UserEngagementMetrics, ContentPerformanceMetrics,
    SystemPerformanceMetrics, InteractionType, ContentRating, get_analytics_tracker
)


class TestAnalyticsTracker:
    """Test cases for AnalyticsTracker"""
    
    @pytest.fixture
    def analytics_tracker(self):
        """Create an AnalyticsTracker instance"""
        return AnalyticsTracker()
    
    @pytest.fixture
    def sample_interaction(self):
        """Create a sample user interaction"""
        return UserInteraction(
            interaction_id="interaction_001",
            user_id="user_123",
            timestamp=datetime.now(timezone.utc),
            interaction_type=InteractionType.MESSAGE_RECEIVED,
            content_category="motivation",
            template_id="template_001",
            additional_data={"delivery_time_ms": 1500},
            response_time_ms=1500,
            timezone="Asia/Bangkok",
            local_time="09:00:00"
        )
    
    def test_initialization(self, analytics_tracker):
        """Test AnalyticsTracker initialization"""
        assert isinstance(analytics_tracker.user_interactions, list)
        assert isinstance(analytics_tracker.user_metrics, dict)
        assert isinstance(analytics_tracker.content_metrics, dict)
        assert len(analytics_tracker.user_interactions) == 0
        assert len(analytics_tracker.user_metrics) == 0
        assert len(analytics_tracker.content_metrics) == 0
        assert analytics_tracker.interaction_retention_days == 30
        assert analytics_tracker.metrics_cache_minutes == 5
    
    def test_track_user_interaction_basic(self, analytics_tracker):
        """Test tracking basic user interaction"""
        interaction_id = analytics_tracker.track_user_interaction(
            user_id="user_456",
            interaction_type=InteractionType.MESSAGE_OPENED,
            content_category="wellness",
            template_id="template_002",
            timezone_name="Europe/London",
            response_time_ms=800
        )
        
        assert interaction_id is not None
        assert interaction_id.startswith("interaction_user_456_")
        
        # Check interaction was stored
        assert len(analytics_tracker.user_interactions) == 1
        interaction = analytics_tracker.user_interactions[0]
        
        assert interaction.interaction_id == interaction_id
        assert interaction.user_id == "user_456"
        assert interaction.interaction_type == InteractionType.MESSAGE_OPENED
        assert interaction.content_category == "wellness"
        assert interaction.template_id == "template_002"
        assert interaction.response_time_ms == 800
        assert interaction.timezone == "Europe/London"
        assert interaction.local_time is not None  # Should be calculated
        
        # Check user metrics were created
        assert "user_456" in analytics_tracker.user_metrics
        user_metrics = analytics_tracker.user_metrics["user_456"]
        assert user_metrics.total_interactions == 1
        assert user_metrics.total_messages_opened == 1
        
        # Check content metrics were created
        content_key = "wellness:template_002"
        assert content_key in analytics_tracker.content_metrics
        content_metrics = analytics_tracker.content_metrics[content_key]
        assert content_metrics.total_opened == 1
    
    def test_track_user_interaction_without_template(self, analytics_tracker):
        """Test tracking interaction without template ID"""
        interaction_id = analytics_tracker.track_user_interaction(
            user_id="user_789",
            interaction_type=InteractionType.BUTTON_CLICKED,
            content_category="productivity"
        )
        
        assert interaction_id is not None
        
        # Check content metrics use category only
        assert "productivity" in analytics_tracker.content_metrics
        content_metrics = analytics_tracker.content_metrics["productivity"]
        assert content_metrics.content_category == "productivity"
        assert content_metrics.template_id is None
        assert content_metrics.total_interactions == 1
    
    def test_track_message_delivery(self, analytics_tracker):
        """Test tracking message delivery"""
        analytics_tracker.track_message_delivery(
            user_id="user_delivery",
            content_category="motivation",
            template_id="template_003",
            delivery_time_ms=2000,
            timezone_name="Asia/Tokyo"
        )
        
        assert len(analytics_tracker.user_interactions) == 1
        interaction = analytics_tracker.user_interactions[0]
        
        assert interaction.interaction_type == InteractionType.MESSAGE_RECEIVED
        assert interaction.additional_data["delivery_time_ms"] == 2000
        assert interaction.response_time_ms == 2000
        
        # Check user metrics
        user_metrics = analytics_tracker.user_metrics["user_delivery"]
        assert user_metrics.total_messages_received == 1
        
        # Check content metrics
        content_metrics = analytics_tracker.content_metrics["motivation:template_003"]
        assert content_metrics.total_sent == 1
        assert content_metrics.total_delivered == 1
        assert content_metrics.average_delivery_time_ms == 2000
    
    def test_track_content_rating(self, analytics_tracker):
        """Test tracking content rating"""
        analytics_tracker.track_content_rating(
            user_id="user_rating",
            content_category="wellness",
            rating=ContentRating.EXCELLENT,
            template_id="template_004",
            feedback_text="Great content!"
        )
        
        assert len(analytics_tracker.user_interactions) == 1
        interaction = analytics_tracker.user_interactions[0]
        
        assert interaction.interaction_type == InteractionType.FEEDBACK_PROVIDED
        assert interaction.additional_data["rating"] == "excellent"
        assert interaction.additional_data["feedback_text"] == "Great content!"
        
        # Check user metrics
        user_metrics = analytics_tracker.user_metrics["user_rating"]
        assert user_metrics.total_feedback_count == 1
        assert user_metrics.average_content_rating == 5.0
        assert "wellness" in user_metrics.content_ratings
        assert ContentRating.EXCELLENT in user_metrics.content_ratings["wellness"]
        
        # Check content metrics
        content_metrics = analytics_tracker.content_metrics["wellness:template_004"]
        assert content_metrics.total_ratings == 1
        assert content_metrics.average_rating == 5.0
        assert content_metrics.rating_distribution["excellent"] == 1
    
    def test_update_user_metrics_multiple_interactions(self, analytics_tracker):
        """Test user metrics updates with multiple interactions"""
        user_id = "user_multi"
        
        # First interaction: message received
        analytics_tracker.track_user_interaction(
            user_id, InteractionType.MESSAGE_RECEIVED, "motivation",
            response_time_ms=1000
        )
        
        # Second interaction: message opened
        analytics_tracker.track_user_interaction(
            user_id, InteractionType.MESSAGE_OPENED, "motivation",
            response_time_ms=500
        )
        
        # Third interaction: button clicked
        analytics_tracker.track_user_interaction(
            user_id, InteractionType.BUTTON_CLICKED, "motivation",
            response_time_ms=200
        )
        
        user_metrics = analytics_tracker.user_metrics[user_id]
        
        assert user_metrics.total_interactions == 3
        assert user_metrics.total_messages_received == 1
        assert user_metrics.total_messages_opened == 1
        
        # Check engagement rates
        assert user_metrics.open_rate == 1.0  # 1 opened / 1 received
        assert user_metrics.interaction_rate == 3.0  # 3 interactions / 1 received
        
        # Check average response time
        expected_avg = (1000 + 500 + 200) / 3
        assert user_metrics.average_response_time_ms == expected_avg
        assert user_metrics.fastest_response_time_ms == 200
    
    def test_update_content_metrics_performance_rates(self, analytics_tracker):
        """Test content metrics performance rate calculations"""
        category = "productivity"
        template_id = "template_perf"
        
        # Track delivery
        analytics_tracker.track_message_delivery(
            "user1", category, template_id, 1000
        )
        analytics_tracker.track_message_delivery(
            "user2", category, template_id, 1500
        )
        
        # Track opens
        analytics_tracker.track_user_interaction(
            "user1", InteractionType.MESSAGE_OPENED, category, template_id
        )
        
        # Track interactions
        analytics_tracker.track_user_interaction(
            "user1", InteractionType.BUTTON_CLICKED, category, template_id
        )
        
        content_key = f"{category}:{template_id}"
        content_metrics = analytics_tracker.content_metrics[content_key]
        
        assert content_metrics.total_sent == 2
        assert content_metrics.total_delivered == 2
        assert content_metrics.total_opened == 1
        assert content_metrics.total_interactions == 1
        
        # Check rates
        assert content_metrics.delivery_rate == 1.0  # 2 delivered / 2 sent
        assert content_metrics.open_rate == 0.5  # 1 opened / 2 delivered
        assert content_metrics.interaction_rate == 0.5  # 1 interaction / 2 delivered
        
        # Check average delivery time
        assert content_metrics.average_delivery_time_ms == 1250  # (1000 + 1500) / 2
    
    def test_update_content_metrics_time_based_performance(self, analytics_tracker):
        """Test content metrics time-based performance tracking"""
        category = "wellness"
        
        # Create interaction at specific hour and day
        with patch('src.utils.analytics_tracker.datetime') as mock_datetime:
            test_time = datetime(2024, 1, 15, 14, 30, 0, tzinfo=timezone.utc)  # Monday 2 PM
            mock_datetime.now.return_value = test_time
            
            analytics_tracker.track_user_interaction(
                "user_time", InteractionType.MESSAGE_RECEIVED, category
            )
        
        content_metrics = analytics_tracker.content_metrics[category]
        
        # Check hourly performance
        assert 14 in content_metrics.performance_by_hour
        hour_perf = content_metrics.performance_by_hour[14]
        assert hour_perf['total_sent'] == 1
        
        # Check daily performance
        assert 'Monday' in content_metrics.performance_by_day
        day_perf = content_metrics.performance_by_day['Monday']
        assert day_perf['total_sent'] == 1
    
    def test_get_user_metrics_exists(self, analytics_tracker):
        """Test getting user metrics for existing user"""
        user_id = "user_exists"
        analytics_tracker.track_user_interaction(
            user_id, InteractionType.MESSAGE_RECEIVED, "motivation"
        )
        
        metrics = analytics_tracker.get_user_metrics(user_id)
        assert metrics is not None
        assert metrics.user_id == user_id
        assert metrics.total_interactions == 1
    
    def test_get_user_metrics_not_exists(self, analytics_tracker):
        """Test getting user metrics for non-existent user"""
        metrics = analytics_tracker.get_user_metrics("nonexistent_user")
        assert metrics is None
    
    def test_get_content_metrics_with_template(self, analytics_tracker):
        """Test getting content metrics with template ID"""
        category = "motivation"
        template_id = "template_test"
        
        analytics_tracker.track_user_interaction(
            "user_content", InteractionType.MESSAGE_RECEIVED, category, template_id
        )
        
        metrics = analytics_tracker.get_content_metrics(category, template_id)
        assert metrics is not None
        assert metrics.content_category == category
        assert metrics.template_id == template_id
    
    def test_get_content_metrics_without_template(self, analytics_tracker):
        """Test getting content metrics without template ID"""
        category = "wellness"
        
        analytics_tracker.track_user_interaction(
            "user_content2", InteractionType.MESSAGE_RECEIVED, category
        )
        
        metrics = analytics_tracker.get_content_metrics(category)
        assert metrics is not None
        assert metrics.content_category == category
        assert metrics.template_id is None
    
    def test_get_content_metrics_not_exists(self, analytics_tracker):
        """Test getting content metrics for non-existent content"""
        metrics = analytics_tracker.get_content_metrics("nonexistent_category")
        assert metrics is None
    
    def test_calculate_system_metrics_empty(self, analytics_tracker):
        """Test calculating system metrics with no data"""
        metrics = analytics_tracker.calculate_system_metrics(force_recalculate=True)
        
        assert isinstance(metrics, SystemPerformanceMetrics)
        assert metrics.total_users == 0
        assert metrics.active_users == 0
        assert metrics.total_deliveries == 0
        assert metrics.overall_delivery_rate == 0.0
        assert metrics.overall_open_rate == 0.0
        assert metrics.overall_interaction_rate == 0.0
    
    def test_calculate_system_metrics_with_data(self, analytics_tracker):
        """Test calculating system metrics with sample data"""
        # Create sample interactions
        analytics_tracker.track_message_delivery("user1", "motivation", delivery_time_ms=1000)
        analytics_tracker.track_message_delivery("user2", "wellness", delivery_time_ms=1500)
        
        analytics_tracker.track_user_interaction("user1", InteractionType.MESSAGE_OPENED, "motivation")
        analytics_tracker.track_user_interaction("user1", InteractionType.BUTTON_CLICKED, "motivation")
        
        metrics = analytics_tracker.calculate_system_metrics(force_recalculate=True)
        
        assert metrics.total_users == 2
        assert metrics.active_users == 2
        assert metrics.total_deliveries == 2
        assert metrics.successful_deliveries == 2
        assert metrics.total_interactions == 4  # 2 deliveries + 1 open + 1 click
        
        assert metrics.overall_delivery_rate == 1.0  # 2 successful / 2 total
        assert metrics.overall_open_rate == 0.5  # 1 open / 2 delivered
        assert metrics.overall_interaction_rate == 0.5  # 1 interaction / 2 delivered
        
        assert metrics.average_delivery_time_ms == 1250  # (1000 + 1500) / 2
        assert metrics.user_retention_rate == 1.0  # 2 active / 2 total
    
    def test_calculate_system_metrics_cached(self, analytics_tracker):
        """Test system metrics caching"""
        # First calculation
        metrics1 = analytics_tracker.calculate_system_metrics()
        
        # Add new interaction
        analytics_tracker.track_user_interaction(
            "new_user", InteractionType.MESSAGE_RECEIVED, "motivation"
        )
        
        # Second calculation without force (should be cached)
        metrics2 = analytics_tracker.calculate_system_metrics()
        
        # Should be same object (cached)
        assert metrics1 is metrics2
        
        # Force recalculation
        metrics3 = analytics_tracker.calculate_system_metrics(force_recalculate=True)
        
        # Should be different (new calculation)
        assert metrics3 is not metrics2
        assert metrics3.total_users == 1  # Should include new user
    
    def test_get_top_performing_content(self, analytics_tracker):
        """Test getting top performing content"""
        # Create content with different performance
        analytics_tracker.track_message_delivery("user1", "motivation", "template1")
        analytics_tracker.track_user_interaction("user1", InteractionType.MESSAGE_OPENED, "motivation", "template1")
        analytics_tracker.track_user_interaction("user1", InteractionType.BUTTON_CLICKED, "motivation", "template1")
        
        analytics_tracker.track_message_delivery("user2", "wellness", "template2")
        analytics_tracker.track_user_interaction("user2", InteractionType.MESSAGE_OPENED, "wellness", "template2")
        
        analytics_tracker.track_message_delivery("user3", "productivity", "template3")
        
        top_content = analytics_tracker.get_top_performing_content(limit=2)
        
        assert len(top_content) == 2
        assert isinstance(top_content, list)
        
        # Should be sorted by interaction rate (highest first)
        first_content_key, first_metrics = top_content[0]
        second_content_key, second_metrics = top_content[1]
        
        assert first_metrics.interaction_rate >= second_metrics.interaction_rate
    
    def test_get_user_engagement_summary_empty(self, analytics_tracker):
        """Test user engagement summary with no data"""
        summary = analytics_tracker.get_user_engagement_summary()
        
        assert summary['total_users'] == 0
        assert summary['active_users'] == 0
        assert summary['engagement_summary'] == 'No active users'
    
    def test_get_user_engagement_summary_with_data(self, analytics_tracker):
        """Test user engagement summary with sample data"""
        # Create users with different engagement levels
        
        # High engagement user
        for i in range(10):
            analytics_tracker.track_user_interaction(
                "user_high", InteractionType.MESSAGE_RECEIVED, "motivation"
            )
            analytics_tracker.track_user_interaction(
                "user_high", InteractionType.MESSAGE_OPENED, "motivation"
            )
            analytics_tracker.track_user_interaction(
                "user_high", InteractionType.BUTTON_CLICKED, "motivation"
            )
        
        # Medium engagement user
        for i in range(8):
            analytics_tracker.track_user_interaction(
                "user_medium", InteractionType.MESSAGE_RECEIVED, "wellness"
            )
            if i < 3:  # Some opens
                analytics_tracker.track_user_interaction(
                    "user_medium", InteractionType.MESSAGE_OPENED, "wellness"
                )
        
        # Low engagement user
        for i in range(6):
            analytics_tracker.track_user_interaction(
                "user_low", InteractionType.MESSAGE_RECEIVED, "productivity"
            )
        
        summary = analytics_tracker.get_user_engagement_summary(min_interactions=5)
        
        assert summary['total_users'] == 3
        assert summary['active_users'] == 3
        assert 0 < summary['average_open_rate'] <= 1
        assert 0 < summary['average_interaction_rate']
        assert len(summary['popular_categories']) > 0
        
        # Check engagement distribution
        engagement_dist = summary['engagement_distribution']
        assert 'high_engagement' in engagement_dist
        assert 'medium_engagement' in engagement_dist
        assert 'low_engagement' in engagement_dist
    
    def test_cleanup_old_interactions(self, analytics_tracker):
        """Test cleaning up old interaction records"""
        # Create old and new interactions
        old_time = datetime.now(timezone.utc) - timedelta(days=35)
        new_time = datetime.now(timezone.utc)
        
        # Add old interaction
        old_interaction = UserInteraction(
            interaction_id="old_interaction",
            user_id="user_old",
            timestamp=old_time,
            interaction_type=InteractionType.MESSAGE_RECEIVED,
            content_category="motivation"
        )
        analytics_tracker.user_interactions.append(old_interaction)
        
        # Add new interaction
        analytics_tracker.track_user_interaction(
            "user_new", InteractionType.MESSAGE_RECEIVED, "wellness"
        )
        
        initial_count = len(analytics_tracker.user_interactions)
        removed_count = analytics_tracker.cleanup_old_interactions(days_to_keep=30)
        
        assert removed_count == 1
        assert len(analytics_tracker.user_interactions) == initial_count - 1
        
        # Check that old interaction was removed
        remaining_ids = [i.interaction_id for i in analytics_tracker.user_interactions]
        assert "old_interaction" not in remaining_ids
    
    def test_export_analytics_data(self, analytics_tracker):
        """Test exporting analytics data"""
        # Create sample data
        analytics_tracker.track_message_delivery("user1", "motivation", "template1", 1000)
        analytics_tracker.track_user_interaction("user1", InteractionType.MESSAGE_OPENED, "motivation", "template1")
        analytics_tracker.track_content_rating("user1", "motivation", ContentRating.GOOD, "template1")
        
        # Export data
        export_data = analytics_tracker.export_analytics_data()
        
        assert 'export_metadata' in export_data
        assert 'interactions' in export_data
        assert 'user_metrics' in export_data
        assert 'content_metrics' in export_data
        assert 'system_metrics' in export_data
        
        # Check metadata
        metadata = export_data['export_metadata']
        assert 'start_date' in metadata
        assert 'end_date' in metadata
        assert 'total_interactions' in metadata
        assert 'export_timestamp' in metadata
        
        # Check data content
        assert len(export_data['interactions']) == 3  # delivery + open + rating
        assert len(export_data['user_metrics']) == 1
        assert len(export_data['content_metrics']) == 1
        
        # Check anonymization
        interactions = export_data['interactions']
        user_metrics = export_data['user_metrics']
        
        for interaction in interactions:
            assert interaction['user_id'].endswith('...')  # Anonymized
            assert len(interaction['user_id']) == 11  # 8 chars + "..."
        
        for user_metric in user_metrics:
            assert user_metric['user_id'].endswith('...')
    
    def test_export_analytics_data_date_range(self, analytics_tracker):
        """Test exporting analytics data with date range"""
        # Create interactions at different times
        old_time = datetime.now(timezone.utc) - timedelta(days=10)
        recent_time = datetime.now(timezone.utc) - timedelta(days=5)
        
        # Old interaction (outside range)
        old_interaction = UserInteraction(
            interaction_id="old_interaction",
            user_id="user_old",
            timestamp=old_time,
            interaction_type=InteractionType.MESSAGE_RECEIVED,
            content_category="motivation"
        )
        analytics_tracker.user_interactions.append(old_interaction)
        
        # Recent interaction (within range)
        recent_interaction = UserInteraction(
            interaction_id="recent_interaction",
            user_id="user_recent",
            timestamp=recent_time,
            interaction_type=InteractionType.MESSAGE_RECEIVED,
            content_category="wellness"
        )
        analytics_tracker.user_interactions.append(recent_interaction)
        
        # Export with date range
        start_date = datetime.now(timezone.utc) - timedelta(days=7)
        end_date = datetime.now(timezone.utc)
        
        export_data = analytics_tracker.export_analytics_data(start_date, end_date)
        
        # Should only include recent interaction
        assert len(export_data['interactions']) == 1
        assert export_data['interactions'][0]['interaction_id'] == 'recent_interaction'
    
    def test_user_interaction_creation(self):
        """Test UserInteraction dataclass creation"""
        timestamp = datetime.now(timezone.utc)
        
        interaction = UserInteraction(
            interaction_id="test_interaction",
            user_id="test_user",
            timestamp=timestamp,
            interaction_type=InteractionType.BUTTON_CLICKED,
            content_category="productivity",
            template_id="template_test",
            additional_data={"button_type": "share"},
            response_time_ms=300,
            timezone="America/New_York",
            local_time="14:30:00"
        )
        
        assert interaction.interaction_id == "test_interaction"
        assert interaction.user_id == "test_user"
        assert interaction.timestamp == timestamp
        assert interaction.interaction_type == InteractionType.BUTTON_CLICKED
        assert interaction.content_category == "productivity"
        assert interaction.template_id == "template_test"
        assert interaction.additional_data == {"button_type": "share"}
        assert interaction.response_time_ms == 300
        assert interaction.timezone == "America/New_York"
        assert interaction.local_time == "14:30:00"
    
    def test_user_engagement_metrics_creation(self):
        """Test UserEngagementMetrics dataclass creation"""
        first_interaction = datetime.now(timezone.utc) - timedelta(days=10)
        last_interaction = datetime.now(timezone.utc)
        
        metrics = UserEngagementMetrics(
            user_id="test_user",
            total_messages_received=50,
            total_messages_opened=35,
            total_interactions=120,
            open_rate=0.7,
            interaction_rate=2.4,
            preferred_categories=["motivation", "wellness"],
            preferred_times=["09:00", "18:00"],
            first_interaction=first_interaction,
            last_interaction=last_interaction,
            days_active=10,
            average_response_time_ms=1200.5,
            fastest_response_time_ms=150,
            total_feedback_count=5,
            average_content_rating=4.2
        )
        
        assert metrics.user_id == "test_user"
        assert metrics.total_messages_received == 50
        assert metrics.total_messages_opened == 35
        assert metrics.total_interactions == 120
        assert metrics.open_rate == 0.7
        assert metrics.interaction_rate == 2.4
        assert metrics.preferred_categories == ["motivation", "wellness"]
        assert metrics.preferred_times == ["09:00", "18:00"]
        assert metrics.first_interaction == first_interaction
        assert metrics.last_interaction == last_interaction
        assert metrics.days_active == 10
        assert metrics.average_response_time_ms == 1200.5
        assert metrics.fastest_response_time_ms == 150
        assert metrics.total_feedback_count == 5
        assert metrics.average_content_rating == 4.2
    
    def test_interaction_type_enum(self):
        """Test InteractionType enum values"""
        assert InteractionType.MESSAGE_RECEIVED.value == "message_received"
        assert InteractionType.MESSAGE_OPENED.value == "message_opened"
        assert InteractionType.BUTTON_CLICKED.value == "button_clicked"
        assert InteractionType.CONTENT_SHARED.value == "content_shared"
        assert InteractionType.CONTENT_SAVED.value == "content_saved"
        assert InteractionType.FEEDBACK_PROVIDED.value == "feedback_provided"
        assert InteractionType.PREFERENCE_UPDATED.value == "preference_updated"
    
    def test_content_rating_enum(self):
        """Test ContentRating enum values"""
        assert ContentRating.EXCELLENT.value == "excellent"
        assert ContentRating.GOOD.value == "good"
        assert ContentRating.AVERAGE.value == "average"
        assert ContentRating.POOR.value == "poor"
        assert ContentRating.TERRIBLE.value == "terrible"
    
    def test_get_analytics_tracker_singleton(self):
        """Test global analytics tracker singleton"""
        tracker1 = get_analytics_tracker()
        tracker2 = get_analytics_tracker()
        
        assert tracker1 is tracker2
        assert isinstance(tracker1, AnalyticsTracker)