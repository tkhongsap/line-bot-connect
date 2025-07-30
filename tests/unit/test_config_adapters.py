"""
Unit tests for configuration adapters.

This module tests the backward-compatible configuration adapters that maintain
the same API as the original configuration classes while using the centralized
configuration system internally.
"""

import os
import pytest
from unittest.mock import patch, MagicMock
from src.config.config_adapters import (
    Settings,
    get_settings,
    RichMessageSystemConfig,
    get_rich_message_config,
    reload_rich_message_config
)


class TestSettingsAdapter:
    """Test the Settings backward-compatible adapter."""
    
    def setup_method(self):
        """Set up test environment."""
        # Clear any cached instances
        import src.config.config_adapters
        src.config.config_adapters._settings_instance = None
        
        # Mock environment variables
        self.env_vars = {
            'LINE_CHANNEL_ACCESS_TOKEN': 'test_line_token',
            'LINE_CHANNEL_SECRET': 'test_line_secret',
            'LINE_CHANNEL_ID': 'test_channel_id',
            'AZURE_OPENAI_API_KEY': 'test_azure_key',
            'AZURE_OPENAI_ENDPOINT': 'https://test.openai.azure.com',
            'AZURE_OPENAI_DEPLOYMENT_NAME': 'gpt-4-test',
            'DEBUG': 'true',
            'LOG_LEVEL': 'DEBUG',
            'MAX_MESSAGES_PER_USER': '50',
            'MAX_TOTAL_CONVERSATIONS': '500'
        }
    
    @patch.dict(os.environ, {
        'LINE__CHANNEL_ACCESS_TOKEN': 'test_line_token',
        'LINE__CHANNEL_SECRET': 'test_line_secret',
        'AZURE_OPENAI__API_KEY': 'test_azure_key',
        'AZURE_OPENAI__ENDPOINT': 'https://test.openai.azure.com',
        'AZURE_OPENAI__DEPLOYMENT_NAME': 'gpt-4-test'
    })
    def test_settings_initialization(self):
        """Test that Settings initializes correctly with centralized config."""
        settings = Settings()
        
        # Test LINE Bot configuration
        assert settings.LINE_CHANNEL_ACCESS_TOKEN == 'test_line_token'
        assert settings.LINE_CHANNEL_SECRET == 'test_line_secret'
        
        # Test Azure OpenAI configuration
        assert settings.AZURE_OPENAI_API_KEY == 'test_azure_key'
        assert settings.AZURE_OPENAI_ENDPOINT == 'https://test.openai.azure.com'
        assert settings.AZURE_OPENAI_DEPLOYMENT_NAME == 'gpt-4-test'
        
        # Test application configuration
        assert isinstance(settings.DEBUG, bool)
        assert isinstance(settings.LOG_LEVEL, str)
        
        # Test conversation limits
        assert isinstance(settings.MAX_MESSAGES_PER_USER, int)
        assert isinstance(settings.MAX_TOTAL_CONVERSATIONS, int)
    
    @patch.dict(os.environ, {
        'LINE__CHANNEL_ACCESS_TOKEN': 'test_line_token',
        'LINE__CHANNEL_SECRET': 'test_line_secret',
        'AZURE_OPENAI__API_KEY': 'test_azure_key',
        'AZURE_OPENAI__ENDPOINT': 'https://test.openai.azure.com',
        'AZURE_OPENAI__DEPLOYMENT_NAME': 'gpt-4-test'
    })
    def test_settings_get_summary(self):
        """Test Settings get_summary method returns expected format."""
        settings = Settings()
        summary = settings.get_summary()
        
        # Check required keys exist
        required_keys = [
            'debug_mode', 'log_level', 'azure_endpoint', 'api_version',
            'deployment_name', 'max_messages_per_user', 'max_total_conversations',
            'line_channel_configured', 'azure_openai_configured', 'api_type',
            'rich_message_enabled'
        ]
        
        for key in required_keys:
            assert key in summary
        
        # Check sensitive values are not exposed
        assert 'LINE_CHANNEL_ACCESS_TOKEN' not in str(summary)
        assert 'AZURE_OPENAI_API_KEY' not in str(summary)
        
        # Check boolean flags
        assert isinstance(summary['line_channel_configured'], bool)
        assert isinstance(summary['azure_openai_configured'], bool)
        assert summary['line_channel_configured'] is True
        assert summary['azure_openai_configured'] is True
    
    def test_settings_validation_missing_required(self):
        """Test that Settings raises ValueError for missing required variables."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError) as exc_info:
                Settings()
            
            assert "Missing required environment variables" in str(exc_info.value)
            assert "LINE_CHANNEL_ACCESS_TOKEN" in str(exc_info.value)
            assert "AZURE_OPENAI_API_KEY" in str(exc_info.value)
    
    @patch.dict(os.environ, {
        'LINE__CHANNEL_ACCESS_TOKEN': 'test_line_token',
        'LINE__CHANNEL_SECRET': 'test_line_secret',
        'AZURE_OPENAI__API_KEY': 'test_azure_key',
        'AZURE_OPENAI__ENDPOINT': 'https://test.openai.azure.com',
        'AZURE_OPENAI__DEPLOYMENT_NAME': 'gpt-4-test'
    })
    def test_get_settings_singleton(self):
        """Test that get_settings returns the same instance."""
        settings1 = get_settings()
        settings2 = get_settings()
        
        assert settings1 is settings2
        assert isinstance(settings1, Settings)


class TestRichMessageSystemConfigAdapter:
    """Test the RichMessageSystemConfig backward-compatible adapter."""
    
    def setup_method(self):
        """Set up test environment."""
        # Clear any cached instances
        import src.config.config_adapters
        import src.config.centralized_config
        src.config.config_adapters._rich_config_instance = None
        src.config.centralized_config._config_instance = None
        
        # Mock template directory and metadata file
        self.template_dir = "/tmp/test_templates"
        self.metadata_file = "/tmp/test_metadata.json"
        
        # Create mock files
        os.makedirs(self.template_dir, exist_ok=True)
        with open(self.metadata_file, 'w') as f:
            f.write('{"templates": []}')
    
    def teardown_method(self):
        """Clean up test environment."""
        # Clean up mock files
        if os.path.exists(self.metadata_file):
            os.remove(self.metadata_file)
        if os.path.exists(self.template_dir):
            os.rmdir(self.template_dir)
    
    @patch.dict(os.environ, {
        'LINE__CHANNEL_ACCESS_TOKEN': 'test_token',
        'LINE__CHANNEL_SECRET': 'test_secret',
        'AZURE_OPENAI__API_KEY': 'test_key',
        'AZURE_OPENAI__ENDPOINT': 'https://test.openai.azure.com',
        'AZURE_OPENAI__DEPLOYMENT_NAME': 'gpt-4-test',
        'TEMPLATE__TEMPLATE_DIRECTORY': '/tmp/test_templates',
        'TEMPLATE__METADATA_FILE': '/tmp/test_metadata.json'
    })
    def test_rich_message_config_initialization(self):
        """Test RichMessageSystemConfig initializes correctly."""
        config = RichMessageSystemConfig()
        
        # Test that all configuration sections exist
        assert hasattr(config, 'rich_message')
        assert hasattr(config, 'template')
        assert hasattr(config, 'content_generation')
        assert hasattr(config, 'scheduling')
        assert hasattr(config, 'analytics')
        assert hasattr(config, 'retry')
        
        # Test template configuration
        assert config.template.template_directory == '/tmp/test_templates'
        assert config.template.metadata_file == '/tmp/test_metadata.json'
        assert isinstance(config.template.cache_templates, bool)
        assert isinstance(config.template.cache_duration_hours, int)
        
        # Test scheduling configuration
        assert 0 <= config.scheduling.default_send_hour <= 23
        assert isinstance(config.scheduling.timezone_aware, bool)
        assert config.scheduling.batch_size > 0
    
    @patch.dict(os.environ, {
        'LINE__CHANNEL_ACCESS_TOKEN': 'test_token',
        'LINE__CHANNEL_SECRET': 'test_secret',
        'AZURE_OPENAI__API_KEY': 'test_key',
        'AZURE_OPENAI__ENDPOINT': 'https://test.openai.azure.com',
        'AZURE_OPENAI__DEPLOYMENT_NAME': 'gpt-4-test',
        'TEMPLATE__TEMPLATE_DIRECTORY': '/tmp/test_templates',
        'TEMPLATE__METADATA_FILE': '/tmp/test_metadata.json'
    })
    def test_rich_message_config_validation(self):
        """Test configuration validation."""
        config = RichMessageSystemConfig()
        
        # Should pass validation with mock files
        assert config.validate_configuration() is True
    
    @patch.dict(os.environ, {
        'LINE__CHANNEL_ACCESS_TOKEN': 'test_token',
        'LINE__CHANNEL_SECRET': 'test_secret',
        'AZURE_OPENAI__API_KEY': 'test_key',
        'AZURE_OPENAI__ENDPOINT': 'https://test.openai.azure.com',
        'AZURE_OPENAI__DEPLOYMENT_NAME': 'gpt-4-test',
        'TEMPLATE__TEMPLATE_DIRECTORY': '/nonexistent/path',
        'TEMPLATE__METADATA_FILE': '/nonexistent/metadata.json'
    })
    def test_rich_message_config_validation_failure(self):
        """Test configuration validation with missing files."""
        config = RichMessageSystemConfig()
        
        # Should fail validation with nonexistent files
        assert config.validate_configuration() is False
    
    @patch.dict(os.environ, {
        'LINE__CHANNEL_ACCESS_TOKEN': 'test_token',
        'LINE__CHANNEL_SECRET': 'test_secret',
        'AZURE_OPENAI__API_KEY': 'test_key',
        'AZURE_OPENAI__ENDPOINT': 'https://test.openai.azure.com',
        'AZURE_OPENAI__DEPLOYMENT_NAME': 'gpt-4-test',
        'TEMPLATE__TEMPLATE_DIRECTORY': '/tmp/test_templates',
        'TEMPLATE__METADATA_FILE': '/tmp/test_metadata.json'
    })
    def test_rich_message_config_methods(self):
        """Test RichMessageSystemConfig utility methods."""
        config = RichMessageSystemConfig()
        
        # Test get_template_path
        template_path = config.get_template_path('test_template.png')
        expected_path = os.path.join(config.template.template_directory, 'test_template.png')
        assert template_path == expected_path
        
        # Test to_dict
        config_dict = config.to_dict()
        assert isinstance(config_dict, dict)
        assert 'rich_message' in config_dict
        assert 'template' in config_dict
        assert 'content_generation' in config_dict
        assert 'scheduling' in config_dict
        assert 'analytics' in config_dict
        assert 'retry' in config_dict
        
        # Test get_enabled_categories
        categories = config.get_enabled_categories()
        assert isinstance(categories, list)
    
    @patch.dict(os.environ, {
        'LINE__CHANNEL_ACCESS_TOKEN': 'test_token',
        'LINE__CHANNEL_SECRET': 'test_secret',
        'AZURE_OPENAI__API_KEY': 'test_key',
        'AZURE_OPENAI__ENDPOINT': 'https://test.openai.azure.com',
        'AZURE_OPENAI__DEPLOYMENT_NAME': 'gpt-4-test',
        'TEMPLATE__TEMPLATE_DIRECTORY': '/tmp/test_templates',
        'TEMPLATE__METADATA_FILE': '/tmp/test_metadata.json'
    })
    def test_get_rich_message_config_singleton(self):
        """Test that get_rich_message_config returns the same instance."""
        config1 = get_rich_message_config()
        config2 = get_rich_message_config()
        
        assert config1 is config2
        assert isinstance(config1, RichMessageSystemConfig)
    
    @patch.dict(os.environ, {
        'LINE__CHANNEL_ACCESS_TOKEN': 'test_token',
        'LINE__CHANNEL_SECRET': 'test_secret',
        'AZURE_OPENAI__API_KEY': 'test_key',
        'AZURE_OPENAI__ENDPOINT': 'https://test.openai.azure.com',
        'AZURE_OPENAI__DEPLOYMENT_NAME': 'gpt-4-test',
        'TEMPLATE__TEMPLATE_DIRECTORY': '/tmp/test_templates',
        'TEMPLATE__METADATA_FILE': '/tmp/test_metadata.json'
    })
    def test_reload_rich_message_config(self):
        """Test configuration reload functionality."""
        config1 = get_rich_message_config()
        config2 = reload_rich_message_config()
        
        # Should be different instances after reload
        assert config1 is not config2
        assert isinstance(config2, RichMessageSystemConfig)


class TestConfigurationDataClasses:
    """Test the configuration dataclasses validation."""
    
    def test_template_config_validation(self):
        """Test TemplateConfig validation."""
        from src.config.config_adapters import TemplateConfig
        
        # Valid configuration
        config = TemplateConfig(
            template_directory="/tmp/test",
            metadata_file="/tmp/metadata.json",
            cache_templates=True,
            cache_duration_hours=24,
            max_template_size_mb=5.0,
            supported_formats=["png", "jpg"],
            fallback_template="default.png"
        )
        assert config.cache_duration_hours == 24
        
        # Invalid cache duration
        with pytest.raises(ValueError):
            TemplateConfig(
                template_directory="/tmp/test",
                metadata_file="/tmp/metadata.json",
                cache_templates=True,
                cache_duration_hours=-1,
                max_template_size_mb=5.0,
                supported_formats=["png", "jpg"],
                fallback_template="default.png"
            )
    
    def test_content_generation_config_validation(self):
        """Test ContentGenerationConfig validation."""
        from src.config.config_adapters import ContentGenerationConfig
        
        # Valid configuration
        config = ContentGenerationConfig(
            ai_model="gpt-4",
            max_content_length=2000,
            max_title_length=100,
            content_cache_hours=6,
            prompt_templates_file="/tmp/prompts.json",
            default_language="en",
            supported_languages=["en", "th", "ja"],
            content_validation_enabled=True,
            sentiment_analysis_enabled=True
        )
        assert config.max_content_length == 2000
        
        # Invalid content length
        with pytest.raises(ValueError):
            ContentGenerationConfig(
                ai_model="gpt-4",
                max_content_length=0,
                max_title_length=100,
                content_cache_hours=6,
                prompt_templates_file="/tmp/prompts.json",
                default_language="en",
                supported_languages=["en", "th", "ja"],
                content_validation_enabled=True,
                sentiment_analysis_enabled=True
            )
    
    def test_scheduling_config_validation(self):
        """Test SchedulingConfig validation."""
        from src.config.config_adapters import SchedulingConfig
        
        # Valid configuration
        config = SchedulingConfig(
            default_send_hour=9,
            timezone_aware=True,
            default_timezone="UTC",
            batch_size=100,
            delivery_timeout_seconds=30,
            max_concurrent_deliveries=10,
            rate_limit_per_minute=1000,
            rate_limit_per_hour=10000,
            enable_delivery_tracking=True
        )
        assert config.default_send_hour == 9
        
        # Invalid send hour
        with pytest.raises(ValueError):
            SchedulingConfig(
                default_send_hour=25,
                timezone_aware=True,
                default_timezone="UTC",
                batch_size=100,
                delivery_timeout_seconds=30,
                max_concurrent_deliveries=10,
                rate_limit_per_minute=1000,
                rate_limit_per_hour=10000,
                enable_delivery_tracking=True
            )
    
    def test_analytics_config_validation(self):
        """Test AnalyticsConfig validation."""
        from src.config.config_adapters import AnalyticsConfig
        
        # Valid configuration
        config = AnalyticsConfig(
            enabled=True,
            track_user_interactions=True,
            track_delivery_metrics=True,
            track_content_performance=True,
            retention_days=90,
            aggregate_hourly=True,
            aggregate_daily=True,
            export_format="json"
        )
        assert config.retention_days == 90
        
        # Invalid export format
        with pytest.raises(ValueError):
            AnalyticsConfig(
                enabled=True,
                track_user_interactions=True,
                track_delivery_metrics=True,
                track_content_performance=True,
                retention_days=90,
                aggregate_hourly=True,
                aggregate_daily=True,
                export_format="xml"
            )
    
    def test_retry_config_validation(self):
        """Test RetryConfig validation."""
        from src.config.config_adapters import RetryConfig
        
        # Valid configuration
        config = RetryConfig(
            max_retries=3,
            initial_delay_seconds=30,
            max_delay_seconds=300,
            backoff_multiplier=2.0,
            retry_on_network_error=True,
            retry_on_rate_limit=True,
            retry_on_server_error=True,
            dead_letter_queue_enabled=True
        )
        assert config.max_retries == 3
        
        # Invalid max retries
        with pytest.raises(ValueError):
            RetryConfig(
                max_retries=-1,
                initial_delay_seconds=30,
                max_delay_seconds=300,
                backoff_multiplier=2.0,
                retry_on_network_error=True,
                retry_on_rate_limit=True,
                retry_on_server_error=True,
                dead_letter_queue_enabled=True
            )