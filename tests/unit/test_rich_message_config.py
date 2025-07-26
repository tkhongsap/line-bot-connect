"""
Unit tests for Rich Message configuration
"""

import pytest
import os
import tempfile
from unittest.mock import patch, mock_open
from src.config.rich_message_config import (
    RichMessageSystemConfig, TemplateConfig, ContentGenerationConfig,
    SchedulingConfig, AnalyticsConfig, RetryConfig,
    get_rich_message_config, reload_rich_message_config
)
from src.models.rich_message_models import ValidationError, ContentCategory


class TestTemplateConfig:
    """Test TemplateConfig"""
    
    def test_template_config_creation(self):
        """Test valid template config creation"""
        config = TemplateConfig(
            template_directory="/test/templates",
            metadata_file="/test/metadata.json",
            cache_templates=True,
            cache_duration_hours=12
        )
        
        assert config.template_directory == "/test/templates"
        assert config.metadata_file == "/test/metadata.json"
        assert config.cache_templates is True
        assert config.cache_duration_hours == 12
    
    def test_template_config_negative_cache_duration(self):
        """Test template config with negative cache duration"""
        with pytest.raises(ValidationError, match="Cache duration must be non-negative"):
            TemplateConfig(cache_duration_hours=-1)
    
    def test_template_config_zero_max_size(self):
        """Test template config with zero max size"""
        with pytest.raises(ValidationError, match="Max template size must be positive"):
            TemplateConfig(max_template_size_mb=0)


class TestContentGenerationConfig:
    """Test ContentGenerationConfig"""
    
    def test_content_generation_config_creation(self):
        """Test valid content generation config creation"""
        config = ContentGenerationConfig(
            ai_model="gpt-4",
            max_content_length=1500,
            max_title_length=80,
            default_language="th"
        )
        
        assert config.ai_model == "gpt-4"
        assert config.max_content_length == 1500
        assert config.max_title_length == 80
        assert config.default_language == "th"
    
    def test_content_generation_config_negative_content_length(self):
        """Test config with negative content length"""
        with pytest.raises(ValidationError, match="Max content length must be positive"):
            ContentGenerationConfig(max_content_length=-100)
    
    def test_content_generation_config_invalid_default_language(self):
        """Test config with invalid default language"""
        with pytest.raises(ValidationError, match="Default language must be one of"):
            ContentGenerationConfig(default_language="invalid_lang")


class TestSchedulingConfig:
    """Test SchedulingConfig"""
    
    def test_scheduling_config_creation(self):
        """Test valid scheduling config creation"""
        config = SchedulingConfig(
            default_send_hour=14,
            timezone_aware=False,
            batch_size=50,
            delivery_timeout_seconds=45
        )
        
        assert config.default_send_hour == 14
        assert config.timezone_aware is False
        assert config.batch_size == 50
        assert config.delivery_timeout_seconds == 45
    
    def test_scheduling_config_invalid_send_hour(self):
        """Test config with invalid send hour"""
        with pytest.raises(ValidationError, match="Default send hour must be between 0 and 23"):
            SchedulingConfig(default_send_hour=25)
    
    def test_scheduling_config_negative_batch_size(self):
        """Test config with negative batch size"""
        with pytest.raises(ValidationError, match="Batch size must be positive"):
            SchedulingConfig(batch_size=-10)
    
    def test_scheduling_config_negative_timeout(self):
        """Test config with negative timeout"""
        with pytest.raises(ValidationError, match="Delivery timeout must be positive"):
            SchedulingConfig(delivery_timeout_seconds=-5)


class TestAnalyticsConfig:
    """Test AnalyticsConfig"""
    
    def test_analytics_config_creation(self):
        """Test valid analytics config creation"""
        config = AnalyticsConfig(
            enabled=False,
            retention_days=30,
            export_format="csv"
        )
        
        assert config.enabled is False
        assert config.retention_days == 30
        assert config.export_format == "csv"
    
    def test_analytics_config_negative_retention(self):
        """Test config with negative retention days"""
        with pytest.raises(ValidationError, match="Retention days must be non-negative"):
            AnalyticsConfig(retention_days=-1)
    
    def test_analytics_config_invalid_export_format(self):
        """Test config with invalid export format"""
        with pytest.raises(ValidationError, match="Export format must be"):
            AnalyticsConfig(export_format="xml")


class TestRetryConfig:
    """Test RetryConfig"""
    
    def test_retry_config_creation(self):
        """Test valid retry config creation"""
        config = RetryConfig(
            max_retries=5,
            initial_delay_seconds=60,
            backoff_multiplier=1.5
        )
        
        assert config.max_retries == 5
        assert config.initial_delay_seconds == 60
        assert config.backoff_multiplier == 1.5
    
    def test_retry_config_negative_max_retries(self):
        """Test config with negative max retries"""
        with pytest.raises(ValidationError, match="Max retries must be non-negative"):
            RetryConfig(max_retries=-1)
    
    def test_retry_config_negative_delay(self):
        """Test config with negative initial delay"""
        with pytest.raises(ValidationError, match="Initial delay must be non-negative"):
            RetryConfig(initial_delay_seconds=-10)
    
    def test_retry_config_invalid_backoff_multiplier(self):
        """Test config with invalid backoff multiplier"""
        with pytest.raises(ValidationError, match="Backoff multiplier must be >= 1.0"):
            RetryConfig(backoff_multiplier=0.5)


class TestRichMessageSystemConfig:
    """Test RichMessageSystemConfig"""
    
    def test_system_config_creation(self):
        """Test system config creation with default values"""
        with patch('os.path.exists', return_value=True):
            config = RichMessageSystemConfig()
            
            assert hasattr(config, 'rich_message')
            assert hasattr(config, 'template')
            assert hasattr(config, 'content_generation')
            assert hasattr(config, 'scheduling')
            assert hasattr(config, 'analytics')
            assert hasattr(config, 'retry')
    
    def test_system_config_with_env_vars(self):
        """Test system config with environment variables"""
        env_vars = {
            'RICH_MESSAGE_DEFAULT_SEND_HOUR': '10',
            'RICH_MESSAGE_MAX_RETRIES': '5',
            'RICH_MESSAGE_BATCH_SIZE': '200',
            'RICH_MESSAGE_ANALYTICS_ENABLED': 'false',
            'RICH_MESSAGE_AI_MODEL': 'gpt-3.5-turbo'
        }
        
        with patch.dict(os.environ, env_vars), \
             patch('os.path.exists', return_value=True):
            config = RichMessageSystemConfig()
            
            assert config.scheduling.default_send_hour == 10
            assert config.retry.max_retries == 5
            assert config.scheduling.batch_size == 200
            assert config.analytics.enabled is False
            assert config.content_generation.ai_model == 'gpt-3.5-turbo'
    
    def test_system_config_validation_success(self):
        """Test successful system config validation"""
        with tempfile.TemporaryDirectory() as temp_dir:
            template_dir = os.path.join(temp_dir, "templates")
            metadata_file = os.path.join(temp_dir, "metadata.json")
            
            os.makedirs(template_dir)
            with open(metadata_file, 'w') as f:
                f.write('{"test": "metadata"}')
            
            env_vars = {
                'RICH_MESSAGE_TEMPLATE_DIR': template_dir,
                'RICH_MESSAGE_METADATA_FILE': metadata_file
            }
            
            with patch.dict(os.environ, env_vars):
                config = RichMessageSystemConfig()
                assert config.validate_configuration() is True
    
    def test_system_config_validation_missing_template_dir(self):
        """Test config validation with missing template directory"""
        env_vars = {
            'RICH_MESSAGE_TEMPLATE_DIR': '/nonexistent/templates',
            'RICH_MESSAGE_METADATA_FILE': '/nonexistent/metadata.json'
        }
        
        with patch.dict(os.environ, env_vars):
            config = RichMessageSystemConfig()
            assert config.validate_configuration() is False
    
    def test_system_config_get_enabled_categories(self):
        """Test getting enabled categories"""
        with patch('os.path.exists', return_value=True):
            config = RichMessageSystemConfig()
            categories = config.get_enabled_categories()
            
            assert isinstance(categories, list)
            assert all(isinstance(cat, ContentCategory) for cat in categories)
    
    def test_system_config_is_category_enabled(self):
        """Test checking if category is enabled"""
        with patch('os.path.exists', return_value=True):
            config = RichMessageSystemConfig()
            
            # All categories should be enabled by default
            assert config.is_category_enabled(ContentCategory.MOTIVATION) is True
            assert config.is_category_enabled(ContentCategory.WELLNESS) is True
    
    def test_system_config_get_template_path(self):
        """Test getting template path"""
        with patch('os.path.exists', return_value=True):
            config = RichMessageSystemConfig()
            path = config.get_template_path("test_template.png")
            
            assert path.endswith("test_template.png")
            assert config.template.template_directory in path
    
    def test_system_config_to_dict(self):
        """Test converting system config to dictionary"""
        with patch('os.path.exists', return_value=True):
            config = RichMessageSystemConfig()
            config_dict = config.to_dict()
            
            assert isinstance(config_dict, dict)
            assert "rich_message" in config_dict
            assert "template" in config_dict
            assert "content_generation" in config_dict
            assert "scheduling" in config_dict
            assert "analytics" in config_dict
            assert "retry" in config_dict


class TestConfigurationManagement:
    """Test global configuration management functions"""
    
    def test_get_rich_message_config(self):
        """Test getting global config instance"""
        with patch('os.path.exists', return_value=True):
            config1 = get_rich_message_config()
            config2 = get_rich_message_config()
            
            # Should return the same instance
            assert config1 is config2
    
    def test_reload_rich_message_config(self):
        """Test reloading global config instance"""
        with patch('os.path.exists', return_value=True):
            config1 = get_rich_message_config()
            config2 = reload_rich_message_config()
            
            # Should return a new instance
            assert config1 is not config2
    
    def test_config_validation_on_first_load(self):
        """Test that validation runs on first config load"""
        # Reset the global config instance to ensure a fresh load
        import src.config.rich_message_config as config_module
        config_module._config_instance = None
        
        with patch('os.path.exists', return_value=False), \
             patch('src.config.rich_message_config.logger') as mock_logger:
            
            config = get_rich_message_config()
            
            # Should log a warning about validation failure
            mock_logger.warning.assert_called_with(
                "Rich Message configuration validation failed"
            )


class TestEnvironmentVariableHandling:
    """Test environment variable handling and defaults"""
    
    def test_boolean_env_var_parsing(self):
        """Test boolean environment variable parsing"""
        test_cases = [
            ("true", True),
            ("True", True),
            ("TRUE", True),
            ("false", False),
            ("False", False),
            ("FALSE", False),
            ("invalid", False)  # Should default to False
        ]
        
        for env_value, expected in test_cases:
            env_vars = {'RICH_MESSAGE_ANALYTICS_ENABLED': env_value}
            
            with patch.dict(os.environ, env_vars), \
                 patch('os.path.exists', return_value=True):
                config = RichMessageSystemConfig()
                assert config.analytics.enabled == expected
    
    def test_integer_env_var_parsing(self):
        """Test integer environment variable parsing"""
        env_vars = {
            'RICH_MESSAGE_DEFAULT_SEND_HOUR': '15',
            'RICH_MESSAGE_MAX_RETRIES': '7',
            'RICH_MESSAGE_BATCH_SIZE': '150'
        }
        
        with patch.dict(os.environ, env_vars), \
             patch('os.path.exists', return_value=True):
            config = RichMessageSystemConfig()
            
            assert config.scheduling.default_send_hour == 15
            assert config.retry.max_retries == 7
            assert config.scheduling.batch_size == 150
    
    def test_float_env_var_parsing(self):
        """Test float environment variable parsing"""
        env_vars = {
            'RICH_MESSAGE_MAX_TEMPLATE_SIZE_MB': '7.5',
            'RICH_MESSAGE_BACKOFF_MULTIPLIER': '2.5'
        }
        
        with patch.dict(os.environ, env_vars), \
             patch('os.path.exists', return_value=True):
            config = RichMessageSystemConfig()
            
            assert config.template.max_template_size_mb == 7.5
            assert config.retry.backoff_multiplier == 2.5
    
    def test_default_values_when_env_vars_missing(self):
        """Test that default values are used when env vars are missing"""
        # Clear relevant environment variables
        env_vars_to_clear = [
            'RICH_MESSAGE_DEFAULT_SEND_HOUR',
            'RICH_MESSAGE_MAX_RETRIES',
            'RICH_MESSAGE_ANALYTICS_ENABLED'
        ]
        
        cleared_env = {var: '' for var in env_vars_to_clear}
        
        with patch.dict(os.environ, cleared_env, clear=False), \
             patch('os.path.exists', return_value=True):
            
            # Remove the variables entirely
            for var in env_vars_to_clear:
                os.environ.pop(var, None)
            
            config = RichMessageSystemConfig()
            
            # Should use default values
            assert config.scheduling.default_send_hour == 9
            assert config.retry.max_retries == 3
            assert config.analytics.enabled is True