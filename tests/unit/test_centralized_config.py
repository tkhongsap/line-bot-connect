"""
Unit tests for centralized configuration system
"""

import os
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from src.config.centralized_config import (
    CentralizedConfig,
    get_config,
    reload_config,
    get_settings_summary,
    Environment,
    LogLevel,
    ContentCategory,
    LineConfig,
    AzureOpenAIConfig,
    ConversationConfig,
    RichMessageConfig,
    TemplateConfig,
    CeleryConfig,
    ApplicationConfig,
    RateLimitConfig
)


class TestLineConfig:
    """Test LINE configuration"""
    
    def test_valid_line_config(self):
        """Test creating valid LINE config"""
        config = LineConfig(
            channel_access_token="test_token",
            channel_secret="test_secret",
            channel_id="test_id"
        )
        assert config.channel_access_token.get_secret_value() == "test_token"
        assert config.channel_secret.get_secret_value() == "test_secret"
        assert config.channel_id == "test_id"
    
    def test_missing_required_fields(self):
        """Test LINE config validation with missing fields"""
        with pytest.raises(ValueError):
            LineConfig(
                channel_access_token="",
                channel_secret="test_secret"
            )
    
    def test_config_is_frozen(self):
        """Test that LINE config is immutable"""
        config = LineConfig(
            channel_access_token="test_token",
            channel_secret="test_secret"
        )
        with pytest.raises(ValueError, match="Instance is frozen"):
            config.channel_access_token = "new_token"


class TestAzureOpenAIConfig:
    """Test Azure OpenAI configuration"""
    
    def test_valid_azure_config(self):
        """Test creating valid Azure OpenAI config"""
        config = AzureOpenAIConfig(
            api_key="test_key",
            endpoint="https://example.cognitiveservices.azure.com",
            api_version="2025-01-01-preview",
            deployment_name="gpt-4"
        )
        assert config.api_key.get_secret_value() == "test_key"
        assert config.endpoint == "https://example.cognitiveservices.azure.com"
        assert config.api_version == "2025-01-01-preview"
        assert config.deployment_name == "gpt-4"
    
    def test_endpoint_validation(self):
        """Test endpoint URL validation"""
        # Valid endpoints
        config = AzureOpenAIConfig(
            api_key="key",
            endpoint="https://example.com/"
        )
        assert config.endpoint == "https://example.com"  # Trailing slash removed
        
        # Invalid endpoint
        with pytest.raises(ValueError, match="must be a valid HTTP"):
            AzureOpenAIConfig(
                api_key="key",
                endpoint="not-a-url"
            )
    
    def test_missing_api_key(self):
        """Test Azure config with missing API key"""
        with pytest.raises(ValueError):
            AzureOpenAIConfig(api_key="")


class TestConversationConfig:
    """Test conversation configuration"""
    
    def test_default_conversation_config(self):
        """Test conversation config with defaults"""
        config = ConversationConfig()
        assert config.max_messages_per_user == 100
        assert config.max_total_conversations == 1000
        assert config.storage_backend == "memory"
        assert config.redis_url == "redis://localhost:6379/0"
        assert config.conversation_ttl_hours == 72
    
    def test_conversation_limits_validation(self):
        """Test conversation limit validations"""
        # Valid limits
        config = ConversationConfig(
            max_messages_per_user=500,
            max_total_conversations=5000
        )
        assert config.max_messages_per_user == 500
        assert config.max_total_conversations == 5000
        
        # Invalid limits
        with pytest.raises(ValueError):
            ConversationConfig(max_messages_per_user=0)
        
        with pytest.raises(ValueError):
            ConversationConfig(max_messages_per_user=1001)
    
    def test_redis_backend_validation(self):
        """Test Redis backend configuration validation"""
        # Valid Redis config
        config = ConversationConfig(
            storage_backend="redis",
            redis_url="redis://localhost:6379/1"
        )
        assert config.storage_backend == "redis"
        assert config.redis_url == "redis://localhost:6379/1"
        
        # Invalid backend
        with pytest.raises(ValueError):
            ConversationConfig(storage_backend="invalid")


class TestRichMessageConfig:
    """Test Rich Message configuration"""
    
    def test_default_rich_message_config(self):
        """Test Rich Message config with defaults"""
        config = RichMessageConfig()
        assert config.enabled is False
        assert config.enabled_categories == [ContentCategory.MOTIVATION]
        assert config.default_send_hour == 9
        assert config.timezone_aware is True
        assert config.analytics_enabled is True
        assert config.max_retries == 3
        assert config.batch_size == 100
    
    def test_send_hour_validation(self):
        """Test send hour validation"""
        # Valid hours
        for hour in [0, 12, 23]:
            config = RichMessageConfig(default_send_hour=hour)
            assert config.default_send_hour == hour
        
        # Invalid hours
        with pytest.raises(ValueError):
            RichMessageConfig(default_send_hour=-1)
        
        with pytest.raises(ValueError):
            RichMessageConfig(default_send_hour=24)
    
    def test_rate_limit_validation(self):
        """Test rate limit validation"""
        config = RichMessageConfig(
            rate_limit_per_minute=100,
            rate_limit_per_hour=5000
        )
        assert config.rate_limit_per_minute == 100
        assert config.rate_limit_per_hour == 5000
    
    def test_empty_categories_default(self):
        """Test that empty categories default to motivation"""
        config = RichMessageConfig(enabled_categories=[])
        assert config.enabled_categories == [ContentCategory.MOTIVATION]


class TestTemplateConfig:
    """Test template configuration"""
    
    def test_default_template_config(self):
        """Test template config with defaults"""
        config = TemplateConfig()
        assert config.template_directory == Path("/home/runner/workspace/templates/rich_messages/backgrounds")
        assert config.metadata_file == Path("/home/runner/workspace/templates/rich_messages/metadata.json")
        assert config.cache_templates is True
        assert config.max_template_size_mb == 5.0
        assert config.supported_formats == ["png", "jpg", "jpeg"]
        assert config.fallback_template == "motivation_bright_01.png"
    
    def test_path_validation(self):
        """Test path type conversion"""
        config = TemplateConfig(
            template_directory="/custom/path",
            metadata_file="/custom/metadata.json"
        )
        assert isinstance(config.template_directory, Path)
        assert isinstance(config.metadata_file, Path)
        assert str(config.template_directory) == "/custom/path"
        assert str(config.metadata_file) == "/custom/metadata.json"
    
    def test_size_validation(self):
        """Test template size validation"""
        # Valid size
        config = TemplateConfig(max_template_size_mb=10.0)
        assert config.max_template_size_mb == 10.0
        
        # Invalid sizes
        with pytest.raises(ValueError):
            TemplateConfig(max_template_size_mb=0)
        
        with pytest.raises(ValueError):
            TemplateConfig(max_template_size_mb=51)


class TestCeleryConfig:
    """Test Celery configuration"""
    
    def test_default_celery_config(self):
        """Test Celery config with defaults"""
        config = CeleryConfig()
        assert config.broker_url == "redis://localhost:6379/0"
        assert config.result_backend == "redis://localhost:6379/0"
        assert config.task_time_limit == 300
        assert config.task_soft_time_limit == 240
        assert config.worker_max_tasks_per_child == 1000
    
    def test_time_limit_validation(self):
        """Test time limit validation"""
        # Valid time limits
        config = CeleryConfig(
            task_soft_time_limit=100,
            task_time_limit=200
        )
        assert config.task_soft_time_limit == 100
        assert config.task_time_limit == 200
        
        # Invalid: soft limit >= hard limit
        with pytest.raises(ValueError, match="Soft time limit must be less than hard time limit"):
            CeleryConfig(
                task_soft_time_limit=300,
                task_time_limit=300
            )


class TestApplicationConfig:
    """Test application configuration"""
    
    def test_default_app_config(self):
        """Test application config with defaults"""
        config = ApplicationConfig()
        assert config.environment == Environment.DEVELOPMENT
        assert config.debug is True
        assert config.log_level == LogLevel.INFO
        assert config.host == "0.0.0.0"
        assert config.port == 5000
        assert config.workers == 4
    
    def test_environment_validation(self):
        """Test environment validation"""
        for env in Environment:
            config = ApplicationConfig(environment=env)
            assert config.environment == env
    
    def test_debug_warning_in_production(self, caplog):
        """Test warning when debug is enabled in production"""
        config = ApplicationConfig(
            environment=Environment.PRODUCTION,
            debug=True
        )
        assert "Debug mode enabled in production environment" in caplog.text
    
    def test_port_validation(self):
        """Test port number validation"""
        # Valid ports
        config = ApplicationConfig(port=8080)
        assert config.port == 8080
        
        # Invalid ports
        with pytest.raises(ValueError):
            ApplicationConfig(port=0)
        
        with pytest.raises(ValueError):
            ApplicationConfig(port=65536)


class TestCentralizedConfig:
    """Test centralized configuration"""
    
    @pytest.fixture
    def mock_env(self):
        """Mock environment variables"""
        env_vars = {
            "LINE_CHANNEL_ACCESS_TOKEN": "mock_line_token",
            "LINE_CHANNEL_SECRET": "mock_line_secret",
            "LINE_CHANNEL_ID": "mock_line_id",
            "AZURE_OPENAI_API_KEY": "mock_azure_key",
            "AZURE_OPENAI_ENDPOINT": "https://mock.cognitiveservices.azure.com",
            "AZURE_OPENAI_API_VERSION": "2025-01-01-preview",
            "AZURE_OPENAI_DEPLOYMENT_NAME": "gpt-4-mock",
            "DEBUG": "false",
            "LOG_LEVEL": "WARNING",
            "ENVIRONMENT": "staging",
            "MAX_MESSAGES_PER_USER": "200",
            "MAX_TOTAL_CONVERSATIONS": "2000",
            "RICH_MESSAGE_ENABLED": "true",
            "RICH_MESSAGE_DEFAULT_SEND_HOUR": "10",
            "RICH_MESSAGE_BATCH_SIZE": "50"
        }
        with patch.dict(os.environ, env_vars, clear=True):
            yield env_vars
    
    def test_from_env(self, mock_env):
        """Test creating config from environment variables"""
        config = CentralizedConfig.from_env()
        
        # LINE config
        assert config.line.channel_access_token.get_secret_value() == "mock_line_token"
        assert config.line.channel_secret.get_secret_value() == "mock_line_secret"
        assert config.line.channel_id == "mock_line_id"
        
        # Azure config
        assert config.azure_openai.api_key.get_secret_value() == "mock_azure_key"
        assert config.azure_openai.endpoint == "https://mock.cognitiveservices.azure.com"
        assert config.azure_openai.deployment_name == "gpt-4-mock"
        
        # Application config
        assert config.application.environment == Environment.STAGING
        assert config.application.debug is False
        assert config.application.log_level == LogLevel.WARNING
        
        # Conversation config
        assert config.conversation.max_messages_per_user == 200
        assert config.conversation.max_total_conversations == 2000
        
        # Rich Message config
        assert config.rich_message.enabled is True
        assert config.rich_message.default_send_hour == 10
        assert config.rich_message.batch_size == 50
    
    def test_config_summary(self, mock_env):
        """Test configuration summary"""
        config = CentralizedConfig.from_env()
        summary = config.get_summary()
        
        assert summary["environment"] == "staging"
        assert summary["debug_mode"] is False
        assert summary["log_level"] == "WARNING"
        assert summary["deployment_name"] == "gpt-4-mock"
        assert summary["max_messages_per_user"] == 200
        assert summary["rich_message_enabled"] is True
        assert "channel_access_token" not in str(summary)  # No secrets
    
    def test_to_dict(self, mock_env):
        """Test converting config to dictionary"""
        config = CentralizedConfig.from_env()
        
        # Without secrets
        data = config.to_dict(include_secrets=False)
        assert data["line"]["channel_access_token"] == "***"
        assert data["line"]["channel_secret"] == "***"
        assert data["azure_openai"]["api_key"] == "***"
        
        # With secrets
        data = config.to_dict(include_secrets=True)
        assert data["line"]["channel_access_token"] == "mock_line_token"
        assert data["line"]["channel_secret"] == "mock_line_secret"
        assert data["azure_openai"]["api_key"] == "mock_azure_key"
    
    def test_validation_with_template_paths(self, mock_env, tmp_path):
        """Test configuration validation with template paths"""
        # Create temporary directories and files
        template_dir = tmp_path / "templates"
        template_dir.mkdir()
        metadata_file = tmp_path / "metadata.json"
        metadata_file.write_text("{}")
        
        with patch.dict(os.environ, {
            **mock_env,
            "RICH_MESSAGE_TEMPLATE_DIR": str(template_dir),
            "RICH_MESSAGE_METADATA_FILE": str(metadata_file)
        }):
            config = CentralizedConfig.from_env()
            assert config.validate_configuration() is True
    
    def test_validation_with_missing_paths(self, mock_env):
        """Test configuration validation with missing paths"""
        config = CentralizedConfig.from_env()
        # Since we're in staging environment with Rich Message enabled and paths don't exist
        # it should return True because paths are only required in production
        assert config.validate_configuration() is True
    
    def test_environment_properties(self, mock_env):
        """Test environment helper properties"""
        # Development
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            config = CentralizedConfig.from_env()
            assert config.is_development is True
            assert config.is_production is False
        
        # Production
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            config = CentralizedConfig.from_env()
            assert config.is_development is False
            assert config.is_production is True


class TestGlobalConfigFunctions:
    """Test global configuration functions"""
    
    @pytest.fixture
    def reset_config(self):
        """Reset global config instance"""
        import src.config.centralized_config as config_module
        original = config_module._config_instance
        config_module._config_instance = None
        yield
        config_module._config_instance = original
    
    def test_get_config_singleton(self, reset_config):
        """Test that get_config returns singleton"""
        with patch.dict(os.environ, {
            "LINE_CHANNEL_ACCESS_TOKEN": "token",
            "LINE_CHANNEL_SECRET": "secret",
            "AZURE_OPENAI_API_KEY": "key"
        }):
            config1 = get_config()
            config2 = get_config()
            assert config1 is config2
    
    def test_reload_config(self, reset_config):
        """Test reloading configuration"""
        with patch.dict(os.environ, {
            "LINE_CHANNEL_ACCESS_TOKEN": "token1",
            "LINE_CHANNEL_SECRET": "secret",
            "AZURE_OPENAI_API_KEY": "key",
            "DEBUG": "true"
        }):
            config1 = get_config()
            assert config1.application.debug is True
            
            # Change environment
            os.environ["DEBUG"] = "false"
            config2 = reload_config()
            
            assert config2.application.debug is False
            assert config1 is not config2
    
    def test_get_settings_summary(self, reset_config):
        """Test backward compatibility function"""
        with patch.dict(os.environ, {
            "LINE_CHANNEL_ACCESS_TOKEN": "token",
            "LINE_CHANNEL_SECRET": "secret", 
            "AZURE_OPENAI_API_KEY": "key",
            "ENVIRONMENT": "production"
        }):
            summary = get_settings_summary()
            assert summary["environment"] == "production"
            assert "config_version" in summary
            assert "deployment_name" in summary


class TestBackwardCompatibility:
    """Test backward compatibility with existing code"""
    
    def test_all_exports(self):
        """Test that all expected exports are available"""
        from src.config import centralized_config
        
        expected_exports = [
            "CentralizedConfig",
            "get_config", 
            "reload_config",
            "get_settings_summary",
            "Environment",
            "LogLevel",
            "ContentCategory",
            "LineConfig",
            "AzureOpenAIConfig",
            "ConversationConfig",
            "RichMessageConfig",
            "TemplateConfig",
            "CeleryConfig",
            "ApplicationConfig",
            "RateLimitConfig"
        ]
        
        for export in expected_exports:
            assert hasattr(centralized_config, export)
    
    def test_content_category_values(self):
        """Test content category enum values match existing"""
        assert ContentCategory.MOTIVATION.value == "motivation"
        assert ContentCategory.INSPIRATION.value == "inspiration"
        assert ContentCategory.WELLNESS.value == "wellness"
        assert ContentCategory.PRODUCTIVITY.value == "productivity"