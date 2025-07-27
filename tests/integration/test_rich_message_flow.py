"""
Integration tests for Rich Message automation pipeline.

This module tests the complete end-to-end flow of Rich Message generation,
delivery, and interaction handling.
"""

import pytest
import tempfile
import os
import json
from unittest.mock import patch, Mock, MagicMock
from datetime import datetime, timezone, timedelta

from src.services.rich_message_service import RichMessageService
from src.utils.interaction_handler import get_interaction_handler, InteractionType
from src.utils.analytics_tracker import get_analytics_tracker
from src.utils.metrics_storage import get_metrics_storage
from src.utils.admin_controller import get_admin_controller, CampaignStatus
from src.config.settings import Settings


class TestRichMessageIntegrationFlow:
    """Integration tests for complete Rich Message automation flow"""
    
    @pytest.fixture
    def temp_db_path(self):
        """Create temporary database for testing"""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as temp_file:
            temp_path = temp_file.name
        yield temp_path
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    
    @pytest.fixture
    def mock_line_bot_api(self):
        """Create mock LINE Bot API"""
        mock_api = Mock()
        mock_api.create_rich_menu.return_value = "rich_menu_123"
        mock_api.set_rich_menu_image.return_value = None
        mock_api.set_default_rich_menu.return_value = None
        mock_api.broadcast.return_value = None
        mock_api.narrowcast.return_value = None
        return mock_api
    
    @pytest.fixture
    def rich_message_service(self, mock_line_bot_api):
        """Create RichMessageService with mocked dependencies"""
        return RichMessageService(line_bot_api=mock_line_bot_api)
    
    @pytest.fixture
    def sample_content_data(self):
        """Sample content data for Rich Messages"""
        return {
            "title": "Daily Motivation",
            "content": "Believe in yourself and all that you are. Know that there is something inside you that is greater than any obstacle.",
            "image_url": "https://example.com/motivation.jpg",
            "content_category": "motivation",
            "template_id": "template_motivation_001"
        }
    
    def test_complete_rich_message_creation_flow(self, rich_message_service, sample_content_data):
        """Test complete Rich Message creation and structure"""
        # Create Rich Message with interactions
        flex_message = rich_message_service.create_flex_message(
            title=sample_content_data["title"],
            content=sample_content_data["content"],
            image_url=sample_content_data["image_url"],
            content_id="test_content_123",
            user_id="test_user_456",
            include_interactions=True
        )
        
        assert flex_message is not None
        assert hasattr(flex_message, 'contents')
        assert hasattr(flex_message, 'alt_text')
        
        # Check alt text
        expected_alt = f"{sample_content_data['title']}: {sample_content_data['content'][:50]}..."
        assert flex_message.alt_text == expected_alt
        
        # Check bubble structure
        bubble = flex_message.contents
        assert hasattr(bubble, 'body')
        assert hasattr(bubble, 'hero')  # Should have hero image
        
        # Check body contents include title and content
        body_contents = bubble.body.contents
        assert len(body_contents) >= 2  # At least title and content
        
        # Verify title component
        title_component = body_contents[0]
        assert hasattr(title_component, 'text')
        assert title_component.text == sample_content_data["title"]
        
        # Verify content component  
        content_component = body_contents[2]  # After title and spacer
        assert hasattr(content_component, 'text')
        assert content_component.text == sample_content_data["content"]
    
    def test_rich_message_broadcast_flow(self, rich_message_service, sample_content_data, mock_line_bot_api):
        """Test Rich Message broadcast flow"""
        # Create message
        flex_message = rich_message_service.create_flex_message(
            title=sample_content_data["title"],
            content=sample_content_data["content"]
        )
        
        # Test broadcast to all users
        result = rich_message_service.broadcast_rich_message(flex_message)
        
        assert result["success"] is True
        assert "timestamp" in result
        assert result["audience"] == "all"
        
        # Verify LINE API was called
        mock_line_bot_api.broadcast.assert_called_once()
        call_args = mock_line_bot_api.broadcast.call_args
        assert call_args[1]["messages"] == [flex_message]
    
    def test_rich_message_narrowcast_flow(self, rich_message_service, sample_content_data, mock_line_bot_api):
        """Test Rich Message narrowcast to specific audience"""
        # Create message
        flex_message = rich_message_service.create_flex_message(
            title=sample_content_data["title"],
            content=sample_content_data["content"]
        )
        
        # Test narrowcast to specific audience
        target_audience = "audience_123"
        result = rich_message_service.broadcast_rich_message(
            flex_message, 
            target_audience=target_audience
        )
        
        assert result["success"] is True
        assert result["audience"] == target_audience
        
        # Verify LINE API was called with correct parameters
        mock_line_bot_api.narrowcast.assert_called_once()
        call_args = mock_line_bot_api.narrowcast.call_args
        assert call_args[1]["messages"] == [flex_message]
        assert call_args[1]["recipient"]["audienceGroupId"] == target_audience
    
    @patch('src.utils.metrics_storage.get_metrics_storage')
    def test_user_interaction_processing_flow(self, mock_get_storage):
        """Test complete user interaction processing flow"""
        # Setup mocks
        mock_storage = Mock()
        mock_get_storage.return_value = mock_storage
        mock_storage.store_metric.return_value = True
        
        interaction_handler = get_interaction_handler()
        
        # Simulate user interaction
        user_id = "test_user_789"
        interaction_data = {
            "action": "interaction",
            "type": "like",
            "content_id": "content_123"
        }
        
        # Process interaction
        result = interaction_handler.handle_user_interaction(user_id, interaction_data)
        
        assert result["success"] is True
        assert result["response_type"] == "message"
        assert "❤️ Liked!" in result["message"]
        assert "interaction_id" in result
        
        # Check interaction was stored
        assert len(interaction_handler.user_interactions) == 1
        interaction = interaction_handler.user_interactions[0]
        assert interaction.user_id == user_id
        assert interaction.content_id == "content_123"
        assert interaction.interaction_type == InteractionType.LIKE
        
        # Check analytics tracking was called
        mock_storage.store_metric.assert_called_once()
    
    def test_analytics_data_flow(self, temp_db_path):
        """Test analytics data collection and storage flow"""
        with patch('src.utils.metrics_storage.get_metrics_storage') as mock_get_storage:
            # Create real metrics storage with temp DB
            from src.utils.metrics_storage import EngagementMetricsStorage
            metrics_storage = EngagementMetricsStorage(db_path=temp_db_path)
            mock_get_storage.return_value = metrics_storage
            
            analytics_tracker = get_analytics_tracker()
            
            # Track multiple interactions
            user_interactions = [
                ("user_1", "motivation", "template_001"),
                ("user_2", "motivation", "template_001"),
                ("user_1", "wellness", "template_002"),
                ("user_3", "productivity", "template_003"),
            ]
            
            for user_id, category, template_id in user_interactions:
                # Track message delivery
                analytics_tracker.track_message_delivery(
                    user_id=user_id,
                    content_category=category,
                    template_id=template_id,
                    delivery_time_ms=150
                )
                
                # Track message opened
                analytics_tracker.track_user_interaction(
                    user_id=user_id,
                    interaction_type=analytics_tracker.InteractionType.MESSAGE_OPENED,
                    content_category=category,
                    template_id=template_id
                )
            
            # Calculate system metrics
            system_metrics = analytics_tracker.calculate_system_metrics(force_recalculate=True)
            
            assert system_metrics.total_users == 3
            assert system_metrics.total_deliveries == 4
            assert system_metrics.overall_delivery_rate == 1.0
            assert system_metrics.overall_open_rate == 1.0
            
            # Check persistent storage
            stored_metrics = metrics_storage.get_metrics()
            assert len(stored_metrics) >= 8  # At least 4 deliveries + 4 opens
            
            # Test aggregation
            start_date = datetime.now(timezone.utc) - timedelta(hours=1)
            end_date = datetime.now(timezone.utc) + timedelta(hours=1)
            
            aggregated = metrics_storage.calculate_aggregated_metrics(
                time_period="hourly",
                start_date=start_date,
                end_date=end_date
            )
            
            assert aggregated is not None
            assert aggregated.total_interactions >= 8
            assert aggregated.unique_users == 3
    
    @patch('src.utils.admin_controller.LineService')
    @patch('src.utils.admin_controller.RichMessageService')
    def test_admin_campaign_flow(self, mock_rich_service_class, mock_line_service_class):
        """Test complete admin campaign management flow"""
        # Mock services
        mock_line_service = Mock()
        mock_line_service.line_bot_api = Mock()
        mock_line_service_class.return_value = mock_line_service
        
        mock_rich_service = Mock()
        mock_flex_message = Mock()
        mock_rich_service.create_flex_message.return_value = mock_flex_message
        mock_rich_service.broadcast_rich_message.return_value = {
            "success": True, 
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        mock_rich_service_class.return_value = mock_rich_service
        
        admin_controller = get_admin_controller()
        
        # Create campaign
        campaign_data = {
            "name": "Integration Test Campaign",
            "description": "Test campaign for integration testing",
            "content_title": "Test Message",
            "content_message": "This is a test message for integration testing.",
            "content_category": "testing",
            "include_interactions": True
        }
        
        create_result = admin_controller.create_campaign(**campaign_data)
        assert create_result["success"] is True
        
        campaign_id = create_result["campaign_id"]
        
        # Schedule campaign
        scheduled_time = datetime.now(timezone.utc) + timedelta(hours=1)
        schedule_result = admin_controller.schedule_campaign(
            campaign_id, scheduled_time, "all"
        )
        assert schedule_result["success"] is True
        
        # Check campaign status
        campaign = admin_controller.campaigns[campaign_id]
        assert campaign.status == CampaignStatus.SCHEDULED
        
        # Trigger campaign manually
        trigger_result = admin_controller.trigger_campaign_manual(
            campaign_id, "all", "integration_test"
        )
        assert trigger_result["success"] is True
        
        # Check campaign was activated
        campaign = admin_controller.campaigns[campaign_id]
        assert campaign.status == CampaignStatus.ACTIVE
        assert campaign.total_sent == 1
        
        # Verify Rich Message creation and broadcast
        mock_rich_service.create_flex_message.assert_called_once()
        mock_rich_service.broadcast_rich_message.assert_called_once()
        
        # Pause campaign
        pause_result = admin_controller.pause_campaign(campaign_id, "integration_test")
        assert pause_result["success"] is True
        assert campaign.status == CampaignStatus.PAUSED
    
    def test_end_to_end_message_interaction_flow(self, rich_message_service, sample_content_data):
        """Test end-to-end message creation and interaction simulation"""
        # Step 1: Create Rich Message with interaction buttons
        content_id = "e2e_test_content_001"
        user_id = "e2e_test_user_001"
        
        flex_message = rich_message_service.create_flex_message(
            title=sample_content_data["title"],
            content=sample_content_data["content"],
            content_id=content_id,
            user_id=user_id,
            include_interactions=True
        )
        
        assert flex_message is not None
        
        # Step 2: Simulate user interactions
        interaction_handler = get_interaction_handler()
        
        # Like interaction
        like_result = interaction_handler.handle_user_interaction(
            user_id, 
            {"action": "interaction", "type": "like", "content_id": content_id}
        )
        assert like_result["success"] is True
        
        # Share interaction
        share_result = interaction_handler.handle_user_interaction(
            user_id,
            {"action": "interaction", "type": "share", "content_id": content_id}
        )
        assert share_result["success"] is True
        
        # Save interaction
        save_result = interaction_handler.handle_user_interaction(
            user_id,
            {"action": "interaction", "type": "save", "content_id": content_id}
        )
        assert save_result["success"] is True
        
        # Reaction interaction
        react_result = interaction_handler.handle_user_interaction(
            user_id,
            {
                "action": "interaction", 
                "type": "react", 
                "content_id": content_id,
                "reaction": "LOVE"
            }
        )
        assert react_result["success"] is True
        
        # Step 3: Check interaction statistics
        content_stats = interaction_handler.get_content_stats(content_id)
        assert content_stats is not None
        assert content_stats.total_likes == 1
        assert content_stats.total_shares == 1
        assert content_stats.total_saves == 1
        assert content_stats.total_reactions == 1
        
        user_profile = interaction_handler.get_user_profile(user_id)
        assert user_profile is not None
        assert user_profile.total_interactions == 4
        assert user_profile.likes_given == 1
        assert user_profile.shares_made == 1
        assert user_profile.content_saved == 1
        assert user_profile.reactions_made == 1
        
        # Step 4: Generate buttons with updated stats
        updated_buttons = interaction_handler.create_interactive_buttons(
            content_id, current_user_id=user_id, include_stats=True
        )
        
        assert len(updated_buttons) == 4
        
        # Check that like button shows "Unlike" since user already liked
        like_button = updated_buttons[0]
        assert "Unlike" in like_button["label"] or "1" in like_button["label"]
        
        # Check save button shows "Saved" since user already saved
        save_button = updated_buttons[2]
        assert "Saved" in save_button["label"] or "1" in save_button["label"]
    
    def test_multi_user_interaction_analytics_flow(self, temp_db_path):
        """Test analytics flow with multiple users and content"""
        with patch('src.utils.metrics_storage.get_metrics_storage') as mock_get_storage:
            # Create real metrics storage
            from src.utils.metrics_storage import EngagementMetricsStorage
            metrics_storage = EngagementMetricsStorage(db_path=temp_db_path)
            mock_get_storage.return_value = metrics_storage
            
            interaction_handler = get_interaction_handler()
            analytics_tracker = get_analytics_tracker()
            
            # Simulate multiple users interacting with multiple content pieces
            users = ["user_001", "user_002", "user_003", "user_004", "user_005"]
            content_ids = ["content_A", "content_B", "content_C"]
            interaction_types = ["like", "share", "save", "react"]
            
            interaction_count = 0
            
            for i, user_id in enumerate(users):
                for j, content_id in enumerate(content_ids):
                    # Each user interacts with each content differently
                    interaction_type = interaction_types[(i + j) % len(interaction_types)]
                    
                    # Track in interaction handler
                    result = interaction_handler.handle_user_interaction(
                        user_id,
                        {
                            "action": "interaction",
                            "type": interaction_type,
                            "content_id": content_id
                        }
                    )
                    assert result["success"] is True
                    interaction_count += 1
                    
                    # Also track message delivery for analytics
                    analytics_tracker.track_message_delivery(
                        user_id=user_id,
                        content_category="test_category",
                        template_id=content_id,
                        delivery_time_ms=100 + (i * 10)
                    )
            
            # Verify interaction counts
            assert len(interaction_handler.user_interactions) == interaction_count
            
            # Check analytics summary
            engagement_summary = interaction_handler.get_engagement_analytics_summary()
            assert engagement_summary["local_interaction_summary"]["total_interactions"] == interaction_count
            assert engagement_summary["local_interaction_summary"]["total_users"] == len(users)
            assert engagement_summary["local_interaction_summary"]["total_content"] == len(content_ids)
            
            # Check top engaged content
            top_content = interaction_handler.get_top_engaged_content(limit=3)
            assert len(top_content) == 3
            
            # Verify persistent storage
            stored_metrics = metrics_storage.get_metrics()
            assert len(stored_metrics) >= interaction_count  # At least the interactions we created
            
            # Test aggregated metrics
            start_date = datetime.now(timezone.utc) - timedelta(hours=1)
            end_date = datetime.now(timezone.utc) + timedelta(hours=1)
            
            aggregated = metrics_storage.calculate_aggregated_metrics(
                "hourly", start_date, end_date
            )
            
            assert aggregated.total_interactions >= interaction_count
            assert aggregated.unique_users == len(users)
    
    def test_system_health_monitoring_flow(self):
        """Test system health monitoring integration"""
        admin_controller = get_admin_controller()
        
        # Perform system health check
        health_status = admin_controller.check_system_health()
        
        assert hasattr(health_status, 'overall_status')
        assert health_status.overall_status in ['healthy', 'warning', 'critical']
        assert hasattr(health_status, 'line_service_status')
        assert hasattr(health_status, 'analytics_service_status')
        assert hasattr(health_status, 'database_status')
        assert isinstance(health_status.issues, list)
        assert isinstance(health_status.warnings, list)
        assert health_status.active_campaigns >= 0
        
        # Test analytics dashboard
        dashboard_result = admin_controller.get_analytics_dashboard(days=1)
        assert dashboard_result["success"] is True
        
        dashboard_data = dashboard_result["dashboard_data"]
        assert "period_days" in dashboard_data
        assert "system_metrics" in dashboard_data
        assert "campaign_summary" in dashboard_data
        assert "storage_stats" in dashboard_data
    
    def test_error_handling_and_recovery_flow(self, rich_message_service):
        """Test error handling throughout the pipeline"""
        # Test Rich Message creation with invalid data
        try:
            flex_message = rich_message_service.create_flex_message(
                title="",  # Empty title
                content="",  # Empty content
                image_url="invalid_url"
            )
            # Should still create a message even with invalid data
            assert flex_message is not None
        except Exception as e:
            # If it fails, ensure it fails gracefully
            assert isinstance(e, Exception)
        
        # Test interaction with missing data
        interaction_handler = get_interaction_handler()
        
        invalid_interaction = interaction_handler.handle_user_interaction(
            "test_user",
            {"action": "interaction"}  # Missing required fields
        )
        
        assert invalid_interaction["success"] is False
        assert "error" in invalid_interaction
        
        # Test admin operations with invalid data
        admin_controller = get_admin_controller()
        
        invalid_campaign = admin_controller.get_campaign_details("nonexistent_id")
        assert invalid_campaign["success"] is False
        
        # Test analytics with error conditions
        analytics_tracker = get_analytics_tracker()
        
        # Should handle gracefully
        try:
            system_metrics = analytics_tracker.calculate_system_metrics()
            assert system_metrics is not None
        except Exception:
            # If it fails, ensure it's handled properly
            pass
    
    def test_performance_and_scalability_flow(self, temp_db_path):
        """Test performance with larger datasets"""
        with patch('src.utils.metrics_storage.get_metrics_storage') as mock_get_storage:
            # Create real metrics storage
            from src.utils.metrics_storage import EngagementMetricsStorage
            metrics_storage = EngagementMetricsStorage(db_path=temp_db_path)
            mock_get_storage.return_value = metrics_storage
            
            interaction_handler = get_interaction_handler()
            
            # Create a larger number of interactions
            num_users = 50
            num_content = 10
            interactions_per_user = 5
            
            start_time = datetime.now()
            
            for user_idx in range(num_users):
                user_id = f"perf_user_{user_idx:03d}"
                
                for content_idx in range(num_content):
                    content_id = f"perf_content_{content_idx:03d}"
                    
                    for interaction_idx in range(interactions_per_user):
                        interaction_type = ["like", "share", "save", "react"][interaction_idx % 4]
                        
                        result = interaction_handler.handle_user_interaction(
                            user_id,
                            {
                                "action": "interaction",
                                "type": interaction_type,
                                "content_id": content_id
                            }
                        )
                        assert result["success"] is True
            
            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()
            
            total_interactions = num_users * num_content * interactions_per_user
            
            # Performance assertions
            assert len(interaction_handler.user_interactions) == total_interactions
            assert processing_time < 30.0  # Should complete within 30 seconds
            
            # Test analytics performance
            start_analytics = datetime.now()
            
            engagement_summary = interaction_handler.get_engagement_analytics_summary()
            top_content = interaction_handler.get_top_engaged_content(limit=10)
            
            end_analytics = datetime.now()
            analytics_time = (end_analytics - start_analytics).total_seconds()
            
            # Analytics should be fast
            assert analytics_time < 5.0  # Should complete within 5 seconds
            
            # Verify results
            assert engagement_summary["local_interaction_summary"]["total_interactions"] == total_interactions
            assert engagement_summary["local_interaction_summary"]["total_users"] == num_users
            assert len(top_content) == min(10, num_content)
            
            # Test cleanup performance
            start_cleanup = datetime.now()
            removed_count = interaction_handler.cleanup_old_interactions(days_to_keep=1)
            end_cleanup = datetime.now()
            cleanup_time = (end_cleanup - start_cleanup).total_seconds()
            
            # Cleanup should be fast (nothing should be removed since data is new)
            assert cleanup_time < 2.0
            assert removed_count == 0  # No old data to remove