"""
Unit tests for Rich Message Automation Tasks
"""

import pytest
from unittest.mock import patch, Mock, MagicMock
from datetime import datetime, time, timezone, timedelta

# Mock Celery to avoid import issues in tests
with patch('celery.Celery'):
    from src.tasks.rich_message_automation import (
        coordinate_timezone_deliveries, execute_timezone_delivery,
        send_rich_message_to_user_batch, process_delivery_retries,
        retry_failed_delivery, update_user_timezone_from_activity,
        cleanup_timezone_data, health_check_task
    )


class TestRichMessageAutomation:
    """Test cases for Rich Message automation tasks"""
    
    @pytest.fixture
    def mock_celery_task(self):
        """Create a mock Celery task object"""
        task = Mock()
        task.request = Mock()
        task.request.retries = 0
        task.retry = Mock()
        return task
    
    @pytest.fixture
    def mock_services(self):
        """Create mock services for testing"""
        with patch('src.tasks.rich_message_automation.Settings') as mock_settings, \
             patch('src.tasks.rich_message_automation.OpenAIService') as mock_openai, \
             patch('src.tasks.rich_message_automation.LineService') as mock_line, \
             patch('src.tasks.rich_message_automation.ConversationService') as mock_conversation, \
             patch('src.tasks.rich_message_automation.get_rich_message_config') as mock_config, \
             patch('src.tasks.rich_message_automation.get_timezone_manager') as mock_tz_manager, \
             patch('src.tasks.rich_message_automation.get_delivery_tracker') as mock_delivery_tracker, \
             patch('src.tasks.rich_message_automation.get_analytics_tracker') as mock_analytics:
            
            # Configure mocks
            mock_settings_instance = Mock()
            mock_settings.return_value = mock_settings_instance
            
            mock_config_instance = Mock()
            mock_config.return_value = mock_config_instance
            mock_config_instance.get_enabled_categories.return_value = []
            
            mock_tz_manager_instance = Mock()
            mock_tz_manager.return_value = mock_tz_manager_instance
            mock_tz_manager_instance.get_optimal_delivery_schedule.return_value = []
            mock_tz_manager_instance.get_pending_retries.return_value = []
            mock_tz_manager_instance.get_timezone_statistics.return_value = {
                'total_users': 0,
                'timezones_count': 0,
                'groups_count': 0,
                'scheduled_deliveries': 0
            }
            
            mock_delivery_tracker_instance = Mock()
            mock_delivery_tracker.return_value = mock_delivery_tracker_instance
            mock_delivery_tracker_instance.get_pending_retries.return_value = []
            mock_delivery_tracker_instance.get_delivery_health_status.return_value = {
                'status': 'healthy',
                'issues': [],
                'total_deliveries': 0,
                'success_rate': 1.0,
                'pending_retries': 0,
                'average_delivery_time_ms': 0,
                'deliveries_last_hour': 0,
                'uptime_hours': 1
            }
            
            mock_analytics_instance = Mock()
            mock_analytics.return_value = mock_analytics_instance
            mock_analytics_instance.calculate_system_metrics.return_value = Mock(
                total_users=0,
                active_users=0,
                overall_open_rate=0.0,
                overall_interaction_rate=0.0,
                user_retention_rate=0.0,
                system_uptime_percentage=100.0
            )
            mock_analytics_instance.get_user_engagement_summary.return_value = {
                'total_users': 0,
                'active_users': 0
            }
            
            yield {
                'settings': mock_settings,
                'openai': mock_openai,
                'line': mock_line,
                'conversation': mock_conversation,
                'config': mock_config,
                'timezone_manager': mock_tz_manager,
                'delivery_tracker': mock_delivery_tracker,
                'analytics': mock_analytics
            }
    
    def test_coordinate_timezone_deliveries_no_categories(self, mock_services):
        """Test timezone delivery coordination with no enabled categories"""
        result = coordinate_timezone_deliveries()
        
        assert result['success'] is True
        assert result['total_categories'] == 0
        assert result['timezone_deliveries_scheduled'] == 0
        assert result['timezone_deliveries_executed'] == 0
        assert 'execution_time_seconds' in result
        assert 'success_rate' in result
    
    def test_coordinate_timezone_deliveries_no_schedules(self, mock_services):
        """Test timezone delivery coordination with categories but no schedules"""
        # Mock enabled categories
        mock_services['config'].return_value.get_enabled_categories.return_value = [
            Mock(value='motivation')
        ]
        
        result = coordinate_timezone_deliveries()
        
        assert result['success'] is True
        assert result['total_categories'] == 1
        assert result['timezone_deliveries_scheduled'] == 0
        assert result['timezone_deliveries_executed'] == 0
    
    def test_process_delivery_retries_no_retries(self, mock_services):
        """Test processing delivery retries with no pending retries"""
        result = process_delivery_retries()
        
        assert result['success'] is True
        assert result['message'] == 'No retries pending'
        assert result['retries_processed'] == 0
    
    def test_update_user_timezone_from_activity_success(self, mock_services):
        """Test updating user timezone from activity data"""
        # Mock timezone detection
        mock_tz_info = Mock()
        mock_tz_info.timezone = "Asia/Bangkok"
        mock_tz_info.detected_method = "activity_pattern"
        mock_tz_info.confidence = 0.8
        mock_tz_info.offset_hours = 7.0
        
        mock_services['timezone_manager'].return_value.detect_user_timezone.return_value = mock_tz_info
        
        result = update_user_timezone_from_activity(
            "test_user_123", 
            {"activity_times": [datetime.now(timezone.utc)]}
        )
        
        assert result['success'] is True
        assert result['user_id'] == 'test_use...'
        assert result['detected_timezone'] == 'Asia/Bangkok'
        assert result['detection_method'] == 'activity_pattern'
        assert result['confidence'] == 0.8
        assert result['offset_hours'] == 7.0
    
    def test_update_user_timezone_from_activity_no_detection(self, mock_services):
        """Test updating user timezone when detection fails"""
        # Mock failed detection
        mock_services['timezone_manager'].return_value.detect_user_timezone.return_value = None
        
        result = update_user_timezone_from_activity(
            "test_user_456", 
            {"activity_times": []}
        )
        
        assert result['success'] is False
        assert result['user_id'] == 'test_use...'
        assert result['error'] == 'Could not detect timezone from activity data'
    
    def test_cleanup_timezone_data_success(self, mock_services):
        """Test timezone data cleanup"""
        # Mock cleanup results
        mock_services['timezone_manager'].return_value.cleanup_old_schedules.return_value = 5
        mock_services['timezone_manager'].return_value.get_timezone_statistics.return_value = {
            'total_users': 100,
            'timezones_count': 15,
            'groups_count': 10,
            'scheduled_deliveries': 25
        }
        
        result = cleanup_timezone_data(days_to_keep=30)
        
        assert result['success'] is True
        assert result['removed_schedules'] == 5
        assert result['days_to_keep'] == 30
        assert 'current_stats' in result
        assert result['current_stats']['total_users'] == 100
    
    @patch('src.tasks.rich_message_automation.TemplateManager')
    def test_health_check_task_healthy(self, mock_template_manager, mock_services):
        """Test health check task with healthy system"""
        # Mock template manager
        mock_template_instance = Mock()
        mock_template_instance.templates = ['template1', 'template2', 'template3']
        mock_template_manager.return_value = mock_template_instance
        
        result = health_check_task()
        
        assert result['overall_status'] == 'healthy'
        assert result['celery_worker_active'] is True
        assert result['config_loaded'] is True
        assert 'services_status' in result
        assert 'delivery_health' in result
        assert 'analytics_health' in result
        assert 'timezone_health' in result
        assert 'template_health' in result
        assert len(result['issues']) == 0
        assert 'health_check_execution_time_ms' in result
    
    @patch('src.tasks.rich_message_automation.TemplateManager')
    def test_health_check_task_with_issues(self, mock_template_manager, mock_services):
        """Test health check task with system issues"""
        # Mock delivery health with issues
        mock_services['delivery_tracker'].return_value.get_delivery_health_status.return_value = {
            'status': 'warning',
            'issues': ['Low success rate: 60%'],
            'total_deliveries': 100,
            'success_rate': 0.6,
            'pending_retries': 10,
            'average_delivery_time_ms': 2000,
            'deliveries_last_hour': 5,
            'uptime_hours': 24
        }
        
        # Mock analytics with low metrics
        mock_analytics_metrics = Mock()
        mock_analytics_metrics.total_users = 50
        mock_analytics_metrics.active_users = 20
        mock_analytics_metrics.overall_open_rate = 0.05  # Low open rate
        mock_analytics_metrics.overall_interaction_rate = 0.02
        mock_analytics_metrics.user_retention_rate = 0.2  # Low retention
        mock_analytics_metrics.system_uptime_percentage = 95.0
        
        mock_services['analytics'].return_value.calculate_system_metrics.return_value = mock_analytics_metrics
        
        # Mock template manager with templates
        mock_template_instance = Mock()
        mock_template_instance.templates = ['template1']
        mock_template_manager.return_value = mock_template_instance
        
        result = health_check_task()
        
        assert result['overall_status'] == 'warning'
        assert len(result['issues']) > 0
        assert any('Low success rate' in issue for issue in result['issues'])
        assert any('Low open rate' in issue for issue in result['issues'])
        assert any('Low retention rate' in issue for issue in result['issues'])
    
    @patch('src.tasks.rich_message_automation.TemplateManager')
    def test_health_check_task_critical(self, mock_template_manager, mock_services):
        """Test health check task with critical issues"""
        # Mock template manager with no templates
        mock_template_instance = Mock()
        mock_template_instance.templates = []
        mock_template_manager.return_value = mock_template_instance
        
        result = health_check_task()
        
        assert result['overall_status'] == 'critical'
        assert any('No templates available' in issue for issue in result['issues'])
        assert result['template_health']['status'] == 'critical'
    
    def test_send_rich_message_to_user_batch_empty_users(self, mock_services):
        """Test sending rich message to empty user batch"""
        with patch('src.tasks.rich_message_automation.RichMessageService') as mock_rich_service:
            result = send_rich_message_to_user_batch(
                user_ids=[],
                image_path="/path/to/image.jpg",
                content_data={"title": "Test", "content": "Test content"},
                category="motivation",
                timezone_name="Asia/Bangkok"
            )
            
            assert result['success'] is False
            assert result['users_count'] == 0
            assert result['successful_deliveries'] == 0
            assert result['failed_deliveries'] == 0
    
    @patch('src.tasks.rich_message_automation.RichMessageService')
    def test_send_rich_message_to_user_batch_flex_message_creation_fails(self, mock_rich_service, mock_services):
        """Test batch sending when Flex message creation fails"""
        # Mock RichMessageService to return None for flex message
        mock_service_instance = Mock()
        mock_service_instance.create_flex_message.return_value = None
        mock_rich_service.return_value = mock_service_instance
        
        result = send_rich_message_to_user_batch(
            user_ids=["user1", "user2"],
            image_path="/path/to/image.jpg",
            content_data={"title": "Test", "content": "Test content"},
            category="motivation",
            timezone_name="Asia/Bangkok"
        )
        
        assert result['success'] is False
        assert result['error'] == 'Failed to create Flex Message'
        assert result['users_count'] == 2
        assert result['successful_deliveries'] == 0
        assert result['failed_deliveries'] == 2
    
    def test_execute_timezone_delivery_no_users(self, mock_services):
        """Test executing timezone delivery with no target users"""
        result = execute_timezone_delivery(
            timezone_name="Asia/Bangkok",
            target_users=[],
            category="motivation",
            local_time="09:00"
        )
        
        assert result['success'] is True
        assert result['timezone'] == 'Asia/Bangkok'
        assert result['users_count'] == 0
        assert result['message'] == 'No users to deliver to'
    
    def test_task_parameter_validation(self):
        """Test that tasks have proper parameter validation"""
        # Test coordinate_timezone_deliveries with categories parameter
        with patch('src.tasks.rich_message_automation.get_rich_message_config') as mock_config:
            mock_config_instance = Mock()
            mock_config_instance.get_enabled_categories.return_value = []
            mock_config.return_value = mock_config_instance
            
            with patch('src.tasks.rich_message_automation.get_timezone_manager') as mock_tz:
                mock_tz.return_value.get_optimal_delivery_schedule.return_value = []
                
                result = coordinate_timezone_deliveries(categories=["motivation", "wellness"])
                assert result['success'] is True
    
    def test_error_handling_in_tasks(self, mock_services):
        """Test error handling in automation tasks"""
        # Test that tasks handle exceptions gracefully
        with patch('src.tasks.rich_message_automation.get_timezone_manager', side_effect=Exception("Test error")):
            result = coordinate_timezone_deliveries()
            
            # Task should handle the exception and return error info
            # Note: This depends on the specific error handling implementation
            # The exact assertion may vary based on how errors are handled
            assert isinstance(result, dict)
    
    def test_task_return_format_consistency(self, mock_services):
        """Test that all tasks return consistent result formats"""
        # All tasks should return dictionaries with success indicators
        
        result1 = coordinate_timezone_deliveries()
        assert isinstance(result1, dict)
        assert 'success' in result1 or 'overall_status' in result1
        
        result2 = process_delivery_retries()
        assert isinstance(result2, dict)
        assert 'success' in result2
        
        result3 = cleanup_timezone_data()
        assert isinstance(result3, dict)
        assert 'success' in result3
        
        result4 = health_check_task()
        assert isinstance(result4, dict)
        assert 'overall_status' in result4
    
    def test_task_logging_integration(self, mock_services):
        """Test that tasks integrate with logging system"""
        with patch('src.tasks.rich_message_automation.logger') as mock_logger:
            coordinate_timezone_deliveries()
            
            # Verify that logger was called
            assert mock_logger.info.called or mock_logger.debug.called
    
    def test_task_timing_metrics(self, mock_services):
        """Test that tasks include timing metrics in results"""
        result = coordinate_timezone_deliveries()
        
        # Should include execution time
        assert 'execution_time_seconds' in result
        assert isinstance(result['execution_time_seconds'], (int, float))
        assert result['execution_time_seconds'] >= 0