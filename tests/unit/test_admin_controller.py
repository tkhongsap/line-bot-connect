"""
Unit tests for Admin Controller
"""

import pytest
from unittest.mock import patch, Mock, MagicMock
from datetime import datetime, timezone, timedelta

from src.utils.admin_controller import (
    AdminController, RichMessageCampaign, SystemHealthStatus, CampaignStatus,
    AdminPermission, get_admin_controller
)


class TestAdminController:
    """Test cases for AdminController"""
    
    @pytest.fixture
    def admin_controller(self):
        """Create AdminController instance with mocked dependencies"""
        with patch('src.utils.admin_controller.Settings') as mock_settings, \
             patch('src.utils.admin_controller.get_analytics_tracker') as mock_analytics, \
             patch('src.utils.admin_controller.get_interaction_handler') as mock_interaction, \
             patch('src.utils.admin_controller.get_metrics_storage') as mock_storage:
            
            mock_settings_instance = Mock()
            mock_settings.return_value = mock_settings_instance
            
            mock_analytics_instance = Mock()
            mock_analytics.return_value = mock_analytics_instance
            
            mock_interaction_instance = Mock()
            mock_interaction.return_value = mock_interaction_instance
            
            mock_storage_instance = Mock()
            mock_storage.return_value = mock_storage_instance
            
            controller = AdminController()
            controller.settings = mock_settings_instance
            controller.analytics_tracker = mock_analytics_instance
            controller.interaction_handler = mock_interaction_instance
            controller.metrics_storage = mock_storage_instance
            
            return controller
    
    @pytest.fixture
    def sample_campaign_data(self):
        """Create sample campaign data"""
        return {
            "name": "Test Campaign",
            "description": "Test campaign description",
            "content_title": "Welcome Message",
            "content_message": "Welcome to our service!",
            "content_category": "motivation",
            "include_interactions": True
        }
    
    def test_initialization(self, admin_controller):
        """Test AdminController initialization"""
        assert isinstance(admin_controller.campaigns, dict)
        assert isinstance(admin_controller.admin_sessions, dict)
        assert len(admin_controller.campaigns) == 0
        assert len(admin_controller.admin_sessions) == 0
        assert hasattr(admin_controller, 'settings')
        assert hasattr(admin_controller, 'analytics_tracker')
        assert hasattr(admin_controller, 'interaction_handler')
        assert hasattr(admin_controller, 'metrics_storage')
    
    def test_create_campaign_success(self, admin_controller, sample_campaign_data):
        """Test successful campaign creation"""
        result = admin_controller.create_campaign(**sample_campaign_data)
        
        assert result["success"] is True
        assert "campaign_id" in result
        assert "campaign" in result
        assert result["message"] == "Campaign 'Test Campaign' created successfully"
        
        # Check campaign was stored
        campaign_id = result["campaign_id"]
        assert campaign_id in admin_controller.campaigns
        
        campaign = admin_controller.campaigns[campaign_id]
        assert campaign.name == "Test Campaign"
        assert campaign.description == "Test campaign description"
        assert campaign.content_title == "Welcome Message"
        assert campaign.content_message == "Welcome to our service!"
        assert campaign.status == CampaignStatus.DRAFT
        assert campaign.include_interactions is True
    
    def test_create_campaign_with_optional_params(self, admin_controller):
        """Test campaign creation with optional parameters"""
        campaign_data = {
            "name": "Advanced Campaign",
            "description": "Advanced campaign with all options",
            "content_title": "Advanced Message",
            "content_message": "Advanced content",
            "image_url": "https://example.com/image.jpg",
            "template_id": "template_123",
            "content_category": "wellness",
            "include_interactions": False,
            "created_by": "admin_user"
        }
        
        result = admin_controller.create_campaign(**campaign_data)
        
        assert result["success"] is True
        campaign_id = result["campaign_id"]
        campaign = admin_controller.campaigns[campaign_id]
        
        assert campaign.image_url == "https://example.com/image.jpg"
        assert campaign.template_id == "template_123"
        assert campaign.content_category == "wellness"
        assert campaign.include_interactions is False
        assert campaign.created_by == "admin_user"
    
    def test_create_campaign_missing_required_fields(self, admin_controller):
        """Test campaign creation with missing required fields"""
        incomplete_data = {
            "name": "Incomplete Campaign"
            # Missing description, content_title, content_message
        }
        
        with pytest.raises(TypeError):
            admin_controller.create_campaign(**incomplete_data)
    
    def test_update_campaign_success(self, admin_controller, sample_campaign_data):
        """Test successful campaign update"""
        # First create a campaign
        create_result = admin_controller.create_campaign(**sample_campaign_data)
        campaign_id = create_result["campaign_id"]
        
        # Update the campaign
        updates = {
            "name": "Updated Campaign Name",
            "description": "Updated description",
            "content_category": "productivity"
        }
        
        result = admin_controller.update_campaign(campaign_id, updates)
        
        assert result["success"] is True
        assert result["campaign_id"] == campaign_id
        assert result["message"] == "Campaign updated successfully"
        
        # Check updates were applied
        campaign = admin_controller.campaigns[campaign_id]
        assert campaign.name == "Updated Campaign Name"
        assert campaign.description == "Updated description"
        assert campaign.content_category == "productivity"
        assert campaign.updated_at > campaign.created_at
    
    def test_update_campaign_not_found(self, admin_controller):
        """Test updating non-existent campaign"""
        result = admin_controller.update_campaign("non_existent_id", {"name": "New Name"})
        
        assert result["success"] is False
        assert "Campaign not found" in result["error"]
    
    def test_update_active_campaign_fails(self, admin_controller, sample_campaign_data):
        """Test that updating active campaign fails"""
        # Create campaign
        create_result = admin_controller.create_campaign(**sample_campaign_data)
        campaign_id = create_result["campaign_id"]
        
        # Set campaign as active
        admin_controller.campaigns[campaign_id].status = CampaignStatus.ACTIVE
        
        # Try to update
        result = admin_controller.update_campaign(campaign_id, {"name": "New Name"})
        
        assert result["success"] is False
        assert "Cannot update active campaign" in result["error"]
    
    def test_schedule_campaign_success(self, admin_controller, sample_campaign_data):
        """Test successful campaign scheduling"""
        # Create campaign
        create_result = admin_controller.create_campaign(**sample_campaign_data)
        campaign_id = create_result["campaign_id"]
        
        # Schedule campaign
        scheduled_time = datetime.now(timezone.utc) + timedelta(hours=2)
        result = admin_controller.schedule_campaign(
            campaign_id, scheduled_time, "all"
        )
        
        assert result["success"] is True
        assert result["campaign_id"] == campaign_id
        assert result["target_audience"] == "all"
        assert "scheduled_time" in result
        
        # Check campaign status
        campaign = admin_controller.campaigns[campaign_id]
        assert campaign.status == CampaignStatus.SCHEDULED
        assert campaign.scheduled_time == scheduled_time
        assert campaign.target_audience == "all"
    
    def test_schedule_campaign_past_time_fails(self, admin_controller, sample_campaign_data):
        """Test scheduling campaign for past time fails"""
        # Create campaign
        create_result = admin_controller.create_campaign(**sample_campaign_data)
        campaign_id = create_result["campaign_id"]
        
        # Try to schedule for past time
        past_time = datetime.now(timezone.utc) - timedelta(hours=1)
        result = admin_controller.schedule_campaign(campaign_id, past_time)
        
        assert result["success"] is False
        assert "Scheduled time must be in the future" in result["error"]
    
    def test_schedule_campaign_not_found(self, admin_controller):
        """Test scheduling non-existent campaign"""
        future_time = datetime.now(timezone.utc) + timedelta(hours=1)
        result = admin_controller.schedule_campaign("non_existent", future_time)
        
        assert result["success"] is False
        assert "Campaign not found" in result["error"]
    
    @patch('src.utils.admin_controller.LineService')
    @patch('src.utils.admin_controller.RichMessageService')
    def test_trigger_campaign_manual_success(self, mock_rich_service_class, mock_line_service_class, admin_controller, sample_campaign_data):
        """Test successful manual campaign trigger"""
        # Mock services
        mock_line_service = Mock()
        mock_line_service.line_bot_api = Mock()
        mock_line_service_class.return_value = mock_line_service
        
        mock_rich_service = Mock()
        mock_flex_message = Mock()
        mock_rich_service.create_flex_message.return_value = mock_flex_message
        mock_rich_service.broadcast_rich_message.return_value = {"success": True, "timestamp": "2024-01-01T00:00:00"}
        mock_rich_service_class.return_value = mock_rich_service
        
        # Create campaign
        create_result = admin_controller.create_campaign(**sample_campaign_data)
        campaign_id = create_result["campaign_id"]
        
        # Trigger campaign
        result = admin_controller.trigger_campaign_manual(campaign_id, "all", "test_admin")
        
        assert result["success"] is True
        assert result["campaign_id"] == campaign_id
        assert result["triggered_by"] == "test_admin"
        assert "triggered_at" in result
        assert "broadcast_result" in result
        
        # Check campaign status
        campaign = admin_controller.campaigns[campaign_id]
        assert campaign.status == CampaignStatus.ACTIVE
        assert campaign.total_sent == 1
        
        # Verify services were called
        mock_rich_service.create_flex_message.assert_called_once()
        mock_rich_service.broadcast_rich_message.assert_called_once()
    
    @patch('src.utils.admin_controller.LineService')
    @patch('src.utils.admin_controller.RichMessageService')
    def test_trigger_campaign_manual_broadcast_fails(self, mock_rich_service_class, mock_line_service_class, admin_controller, sample_campaign_data):
        """Test manual campaign trigger when broadcast fails"""
        # Mock services with broadcast failure
        mock_line_service = Mock()
        mock_line_service_class.return_value = mock_line_service
        
        mock_rich_service = Mock()
        mock_flex_message = Mock()
        mock_rich_service.create_flex_message.return_value = mock_flex_message
        mock_rich_service.broadcast_rich_message.return_value = {"success": False, "error": "Broadcast failed"}
        mock_rich_service_class.return_value = mock_rich_service
        
        # Create campaign
        create_result = admin_controller.create_campaign(**sample_campaign_data)
        campaign_id = create_result["campaign_id"]
        
        # Trigger campaign
        result = admin_controller.trigger_campaign_manual(campaign_id)
        
        assert result["success"] is False
        assert result["error"] == "Broadcast failed"
        assert "details" in result
    
    def test_trigger_campaign_not_found(self, admin_controller):
        """Test triggering non-existent campaign"""
        result = admin_controller.trigger_campaign_manual("non_existent")
        
        assert result["success"] is False
        assert "Campaign not found" in result["error"]
    
    def test_pause_campaign_success(self, admin_controller, sample_campaign_data):
        """Test successful campaign pausing"""
        # Create and activate campaign
        create_result = admin_controller.create_campaign(**sample_campaign_data)
        campaign_id = create_result["campaign_id"]
        admin_controller.campaigns[campaign_id].status = CampaignStatus.ACTIVE
        
        # Pause campaign
        result = admin_controller.pause_campaign(campaign_id, "test_admin")
        
        assert result["success"] is True
        assert result["campaign_id"] == campaign_id
        assert result["paused_by"] == "test_admin"
        assert "paused_at" in result
        
        # Check campaign status
        campaign = admin_controller.campaigns[campaign_id]
        assert campaign.status == CampaignStatus.PAUSED
    
    def test_pause_campaign_invalid_status(self, admin_controller, sample_campaign_data):
        """Test pausing campaign with invalid status"""
        # Create campaign (status is DRAFT by default)
        create_result = admin_controller.create_campaign(**sample_campaign_data)
        campaign_id = create_result["campaign_id"]
        
        # Try to pause draft campaign
        result = admin_controller.pause_campaign(campaign_id)
        
        assert result["success"] is False
        assert "Cannot pause campaign with status" in result["error"]
    
    def test_get_campaign_list_no_filter(self, admin_controller):
        """Test getting campaign list without filters"""
        # Create multiple campaigns
        campaigns_data = [
            {"name": "Campaign 1", "description": "Desc 1", "content_title": "Title 1", "content_message": "Message 1"},
            {"name": "Campaign 2", "description": "Desc 2", "content_title": "Title 2", "content_message": "Message 2"},
            {"name": "Campaign 3", "description": "Desc 3", "content_title": "Title 3", "content_message": "Message 3"},
        ]
        
        for data in campaigns_data:
            admin_controller.create_campaign(**data)
        
        result = admin_controller.get_campaign_list()
        
        assert result["success"] is True
        assert len(result["campaigns"]) == 3
        assert result["total_count"] == 3
        assert result["filtered_count"] == 3
        
        # Should be sorted by creation date (newest first)
        campaigns = result["campaigns"]
        assert campaigns[0]["name"] == "Campaign 3"  # Most recent
        assert campaigns[1]["name"] == "Campaign 2"
        assert campaigns[2]["name"] == "Campaign 1"  # Oldest
    
    def test_get_campaign_list_with_status_filter(self, admin_controller, sample_campaign_data):
        """Test getting campaign list with status filter"""
        # Create campaigns with different statuses
        for i in range(3):
            create_result = admin_controller.create_campaign(
                name=f"Campaign {i}",
                description=f"Description {i}",
                content_title=f"Title {i}",
                content_message=f"Message {i}"
            )
            if i == 1:
                admin_controller.campaigns[create_result["campaign_id"]].status = CampaignStatus.ACTIVE
        
        # Filter by DRAFT status
        result = admin_controller.get_campaign_list(status_filter=CampaignStatus.DRAFT)
        
        assert result["success"] is True
        assert len(result["campaigns"]) == 2  # 2 draft campaigns
        assert all(c["status"] == "draft" for c in result["campaigns"])
    
    def test_get_campaign_list_with_limit(self, admin_controller):
        """Test getting campaign list with limit"""
        # Create 5 campaigns
        for i in range(5):
            admin_controller.create_campaign(
                name=f"Campaign {i}",
                description=f"Description {i}",
                content_title=f"Title {i}",
                content_message=f"Message {i}"
            )
        
        result = admin_controller.get_campaign_list(limit=3)
        
        assert result["success"] is True
        assert len(result["campaigns"]) == 3
        assert result["total_count"] == 5
        assert result["filtered_count"] == 3
    
    def test_get_campaign_details_success(self, admin_controller, sample_campaign_data):
        """Test getting campaign details"""
        # Create campaign
        create_result = admin_controller.create_campaign(**sample_campaign_data)
        campaign_id = create_result["campaign_id"]
        
        # Mock interaction stats
        mock_stats = Mock()
        admin_controller.interaction_handler.get_content_stats.return_value = mock_stats
        
        # Mock content metrics
        mock_metrics = Mock()
        admin_controller.analytics_tracker.get_content_metrics.return_value = mock_metrics
        
        result = admin_controller.get_campaign_details(campaign_id)
        
        assert result["success"] is True
        assert "campaign" in result
        assert result["campaign"]["campaign_id"] == campaign_id
        assert "interaction_stats" in result
        assert "content_metrics" in result
        assert "last_updated" in result
    
    def test_get_campaign_details_not_found(self, admin_controller):
        """Test getting details for non-existent campaign"""
        result = admin_controller.get_campaign_details("non_existent")
        
        assert result["success"] is False
        assert "Campaign not found" in result["error"]
    
    def test_get_analytics_dashboard(self, admin_controller):
        """Test getting analytics dashboard data"""
        # Mock analytics data
        mock_system_metrics = Mock()
        admin_controller.analytics_tracker.calculate_system_metrics.return_value = mock_system_metrics
        
        mock_persistent_summary = {"period_days": 7, "total_interactions": 100}
        admin_controller.analytics_tracker.get_persistent_metrics_summary.return_value = mock_persistent_summary
        
        mock_interaction_summary = {"total_users": 50}
        admin_controller.interaction_handler.get_engagement_analytics_summary.return_value = mock_interaction_summary
        
        mock_storage_stats = {"total_metrics": 500}
        admin_controller.metrics_storage.get_storage_statistics.return_value = mock_storage_stats
        
        # Create sample campaigns for top campaigns
        for i in range(3):
            create_result = admin_controller.create_campaign(
                name=f"Campaign {i}",
                description=f"Description {i}",
                content_title=f"Title {i}",
                content_message=f"Message {i}"
            )
            # Set different interaction counts
            admin_controller.campaigns[create_result["campaign_id"]].total_interactions = 10 - i
            admin_controller.campaigns[create_result["campaign_id"]].total_sent = 100
        
        result = admin_controller.get_analytics_dashboard(days=7)
        
        assert result["success"] is True
        assert "dashboard_data" in result
        
        dashboard = result["dashboard_data"]
        assert dashboard["period_days"] == 7
        assert "generated_at" in dashboard
        assert "system_metrics" in dashboard
        assert "persistent_metrics" in dashboard
        assert "interaction_summary" in dashboard
        assert "top_campaigns" in dashboard
        assert "campaign_summary" in dashboard
        assert "storage_stats" in dashboard
        
        # Check top campaigns are sorted by interactions
        top_campaigns = dashboard["top_campaigns"]
        assert len(top_campaigns) == 3
        assert top_campaigns[0]["name"] == "Campaign 0"  # Highest interactions (10)
    
    def test_check_system_health_healthy(self, admin_controller):
        """Test system health check with healthy system"""
        # Mock healthy analytics
        mock_system_metrics = Mock()
        mock_system_metrics.overall_open_rate = 0.5  # Above threshold
        admin_controller.analytics_tracker.calculate_system_metrics.return_value = mock_system_metrics
        
        # Mock healthy storage
        admin_controller.metrics_storage.get_storage_statistics.return_value = {"status": "ok"}
        
        health_status = admin_controller.check_system_health()
        
        assert isinstance(health_status, SystemHealthStatus)
        assert health_status.overall_status == "healthy"
        assert len(health_status.issues) == 0
        assert health_status.line_service_status == "healthy"
        assert health_status.analytics_service_status == "healthy"
        assert health_status.database_status == "healthy"
        assert health_status.active_campaigns >= 0
    
    def test_check_system_health_with_warnings(self, admin_controller):
        """Test system health check with warnings"""
        # Mock analytics with low open rate
        mock_system_metrics = Mock()
        mock_system_metrics.overall_open_rate = 0.05  # Below threshold
        admin_controller.analytics_tracker.calculate_system_metrics.return_value = mock_system_metrics
        
        # Mock healthy storage
        admin_controller.metrics_storage.get_storage_statistics.return_value = {"status": "ok"}
        
        health_status = admin_controller.check_system_health()
        
        assert health_status.overall_status == "warning"
        assert len(health_status.warnings) > 0
        assert any("Low overall open rate" in warning for warning in health_status.warnings)
    
    def test_check_system_health_critical_issues(self, admin_controller):
        """Test system health check with critical issues"""
        # Mock storage error
        admin_controller.metrics_storage.get_storage_statistics.return_value = {"error": "Connection failed"}
        
        health_status = admin_controller.check_system_health()
        
        assert health_status.overall_status == "critical"
        assert len(health_status.issues) > 0
        assert any("Database connection failed" in issue for issue in health_status.issues)
    
    def test_cleanup_old_data(self, admin_controller):
        """Test cleaning up old data"""
        # Mock cleanup results
        admin_controller.analytics_tracker.cleanup_old_interactions.return_value = 10
        admin_controller.interaction_handler.cleanup_old_interactions.return_value = 5
        admin_controller.metrics_storage.cleanup_old_metrics.return_value = 15
        
        # Create old completed campaign
        create_result = admin_controller.create_campaign(
            name="Old Campaign",
            description="Old description",
            content_title="Old title",
            content_message="Old message"
        )
        campaign_id = create_result["campaign_id"]
        campaign = admin_controller.campaigns[campaign_id]
        campaign.status = CampaignStatus.COMPLETED
        campaign.updated_at = datetime.now(timezone.utc) - timedelta(days=40)
        
        result = admin_controller.cleanup_old_data(days_to_keep=30)
        
        assert result["success"] is True
        assert "cleanup_results" in result
        
        cleanup_results = result["cleanup_results"]
        assert cleanup_results["analytics_interactions_removed"] == 10
        assert cleanup_results["interaction_records_removed"] == 5
        assert cleanup_results["storage_metrics_removed"] == 15
        assert cleanup_results["old_campaigns_removed"] == 1
        
        # Check old campaign was removed
        assert campaign_id not in admin_controller.campaigns
    
    def test_campaign_status_enum(self):
        """Test CampaignStatus enum values"""
        assert CampaignStatus.DRAFT.value == "draft"
        assert CampaignStatus.SCHEDULED.value == "scheduled"
        assert CampaignStatus.ACTIVE.value == "active"
        assert CampaignStatus.PAUSED.value == "paused"
        assert CampaignStatus.COMPLETED.value == "completed"
        assert CampaignStatus.CANCELLED.value == "cancelled"
    
    def test_admin_permission_enum(self):
        """Test AdminPermission enum values"""
        assert AdminPermission.READ_ONLY.value == "read_only"
        assert AdminPermission.CAMPAIGN_MANAGER.value == "campaign_manager"
        assert AdminPermission.ANALYTICS_VIEWER.value == "analytics_viewer"
        assert AdminPermission.SYSTEM_ADMIN.value == "system_admin"
    
    def test_rich_message_campaign_dataclass(self):
        """Test RichMessageCampaign dataclass creation"""
        now = datetime.now(timezone.utc)
        
        campaign = RichMessageCampaign(
            campaign_id="test_campaign",
            name="Test Campaign",
            description="Test description",
            content_title="Test Title",
            content_message="Test message",
            status=CampaignStatus.ACTIVE,
            scheduled_time=now + timedelta(hours=1),
            target_audience="test_audience",
            image_url="https://example.com/image.jpg",
            template_id="template_123",
            content_category="motivation",
            include_interactions=True,
            created_by="test_admin",
            total_sent=100,
            total_delivered=95,
            total_opened=80,
            total_interactions=60
        )
        
        assert campaign.campaign_id == "test_campaign"
        assert campaign.name == "Test Campaign"
        assert campaign.status == CampaignStatus.ACTIVE
        assert campaign.total_interactions == 60
        assert campaign.created_at is not None
        assert campaign.updated_at is not None
    
    def test_system_health_status_dataclass(self):
        """Test SystemHealthStatus dataclass creation"""
        timestamp = datetime.now(timezone.utc)
        
        health_status = SystemHealthStatus(
            overall_status="healthy",
            timestamp=timestamp,
            line_service_status="healthy",
            rich_message_service_status="healthy",
            analytics_service_status="healthy",
            database_status="healthy",
            avg_response_time_ms=150.5,
            memory_usage_mb=256.0,
            active_campaigns=5,
            pending_deliveries=10,
            issues=[],
            warnings=["Minor warning"]
        )
        
        assert health_status.overall_status == "healthy"
        assert health_status.timestamp == timestamp
        assert health_status.avg_response_time_ms == 150.5
        assert health_status.active_campaigns == 5
        assert len(health_status.warnings) == 1
    
    def test_get_admin_controller_singleton(self):
        """Test global admin controller singleton"""
        with patch('src.utils.admin_controller.Settings'), \
             patch('src.utils.admin_controller.get_analytics_tracker'), \
             patch('src.utils.admin_controller.get_interaction_handler'), \
             patch('src.utils.admin_controller.get_metrics_storage'):
            
            controller1 = get_admin_controller()
            controller2 = get_admin_controller()
            
            assert controller1 is controller2
            assert isinstance(controller1, AdminController)
    
    def test_error_handling_in_methods(self, admin_controller):
        """Test error handling in admin controller methods"""
        # Test create_campaign with exception
        with patch.object(admin_controller, 'campaigns', side_effect=Exception("Storage error")):
            result = admin_controller.create_campaign(
                name="Test", description="Test", content_title="Test", content_message="Test"
            )
            assert result["success"] is False
            assert "error" in result
        
        # Test get_analytics_dashboard with exception
        admin_controller.analytics_tracker.calculate_system_metrics.side_effect = Exception("Analytics error")
        result = admin_controller.get_analytics_dashboard()
        assert result["success"] is False
        assert "error" in result
        
        # Test cleanup_old_data with exception
        admin_controller.analytics_tracker.cleanup_old_interactions.side_effect = Exception("Cleanup error")
        result = admin_controller.cleanup_old_data()
        assert result["success"] is False
        assert "error" in result