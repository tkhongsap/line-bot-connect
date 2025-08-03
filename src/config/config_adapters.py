"""
Backward-compatible configuration adapters for migrating to centralized configuration.

This module provides adapters that maintain the same API as existing configuration
classes while using the new centralized configuration system internally.
"""

import os
import logging
from typing import Dict, Any, Optional
from dotenv import load_dotenv

from src.config.centralized_config import get_config, ApplicationConfig

logger = logging.getLogger(__name__)

# Load environment variables from .env file if it exists
load_dotenv()


class Settings:
    """
    Backward-compatible adapter for the old Settings class.
    
    This class maintains the same API as src/config/settings.py while
    using the centralized configuration system internally.
    """
    
    def __init__(self):
        """Initialize the settings adapter with centralized configuration."""
        self._config = get_config()
        
        # LINE Bot Configuration
        self.LINE_CHANNEL_ACCESS_TOKEN = self._config.line.channel_access_token.get_secret_value() if self._config.line.channel_access_token else None
        self.LINE_CHANNEL_SECRET = self._config.line.channel_secret.get_secret_value() if self._config.line.channel_secret else None
        self.LINE_CHANNEL_ID = self._config.line.channel_id
        
        # Azure OpenAI Configuration
        self.AZURE_OPENAI_API_KEY = self._config.azure_openai.api_key.get_secret_value() if self._config.azure_openai.api_key else None
        self.AZURE_OPENAI_ENDPOINT = self._config.azure_openai.endpoint
        self.AZURE_OPENAI_API_VERSION = self._config.azure_openai.api_version
        self.AZURE_OPENAI_DEPLOYMENT_NAME = self._config.azure_openai.deployment_name
        
        # New Azure OpenAI capability detection settings
        self.AZURE_OPENAI_PREFER_RESPONSES_API = self._config.azure_openai.prefer_responses_api
        self.AZURE_OPENAI_FORCE_CHAT_COMPLETIONS = self._config.azure_openai.force_chat_completions
        self.AZURE_OPENAI_CAPABILITY_CACHE_TTL = self._config.azure_openai.capability_cache_ttl
        self.AZURE_OPENAI_ENABLE_STARTUP_VALIDATION = self._config.azure_openai.enable_startup_validation
        
        # Application Configuration
        self.DEBUG = self._config.application.debug
        self.LOG_LEVEL = self._config.application.log_level
        
        # Conversation limits
        self.MAX_MESSAGES_PER_USER = self._config.conversation.max_messages_per_user
        self.MAX_TOTAL_CONVERSATIONS = self._config.conversation.max_total_conversations
        
        # Rich Message Configuration
        self.RICH_MESSAGE_ENABLED = self._config.rich_message.enabled
        self.RICH_MESSAGE_DEFAULT_SEND_HOUR = self._config.rich_message.default_send_hour
        self.RICH_MESSAGE_TIMEZONE_AWARE = self._config.rich_message.timezone_aware
        self.RICH_MESSAGE_ANALYTICS_ENABLED = self._config.rich_message.analytics_enabled
        self.RICH_MESSAGE_TEMPLATE_CACHE_HOURS = self._config.rich_message.template_cache_hours
        self.RICH_MESSAGE_CONTENT_CACHE_HOURS = self._config.rich_message.content_cache_hours
        self.RICH_MESSAGE_MAX_RETRIES = self._config.rich_message.max_retries
        self.RICH_MESSAGE_BATCH_SIZE = self._config.rich_message.batch_size
        
        # Validate required settings for backward compatibility
        self._validate_settings()
    
    def _validate_settings(self):
        """Validate that all required settings are present."""
        required_settings = [
            ("LINE_CHANNEL_ACCESS_TOKEN", self.LINE_CHANNEL_ACCESS_TOKEN),
            ("LINE_CHANNEL_SECRET", self.LINE_CHANNEL_SECRET),
            ("AZURE_OPENAI_API_KEY", self.AZURE_OPENAI_API_KEY),
            ("AZURE_OPENAI_ENDPOINT", self.AZURE_OPENAI_ENDPOINT),
            ("AZURE_OPENAI_DEPLOYMENT_NAME", self.AZURE_OPENAI_DEPLOYMENT_NAME)
        ]
        
        missing_settings = []
        for setting_name, setting_value in required_settings:
            if not setting_value:
                missing_settings.append(setting_name)
        
        if missing_settings:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing_settings)}. "
                "Please check your .env file or environment configuration."
            )
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of current settings (without sensitive values)."""
        return {
            "debug_mode": self.DEBUG,
            "log_level": self.LOG_LEVEL,
            "azure_endpoint": self.AZURE_OPENAI_ENDPOINT,
            "api_version": self.AZURE_OPENAI_API_VERSION,
            "deployment_name": self.AZURE_OPENAI_DEPLOYMENT_NAME,
            "max_messages_per_user": self.MAX_MESSAGES_PER_USER,
            "max_total_conversations": self.MAX_TOTAL_CONVERSATIONS,
            "line_channel_configured": bool(self.LINE_CHANNEL_ACCESS_TOKEN),
            "azure_openai_configured": bool(self.AZURE_OPENAI_API_KEY),
            "api_type": "Azure OpenAI Responses API",
            "rich_message_enabled": self.RICH_MESSAGE_ENABLED,
            "rich_message_send_hour": self.RICH_MESSAGE_DEFAULT_SEND_HOUR,
            "rich_message_timezone_aware": self.RICH_MESSAGE_TIMEZONE_AWARE,
            "rich_message_analytics": self.RICH_MESSAGE_ANALYTICS_ENABLED,
            "rich_message_max_retries": self.RICH_MESSAGE_MAX_RETRIES,
            "rich_message_batch_size": self.RICH_MESSAGE_BATCH_SIZE
        }


# Create a singleton instance for backward compatibility
_settings_instance: Optional[Settings] = None


def get_settings() -> Settings:
    """Get the global settings instance (backward compatible)."""
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings()
    return _settings_instance


# Rich Message Configuration Adapters
from dataclasses import dataclass, field
from typing import List
from src.models.rich_message_models import ContentCategory


@dataclass
class TemplateConfig:
    """Backward-compatible adapter for TemplateConfig."""
    template_directory: str
    metadata_file: str
    cache_templates: bool
    cache_duration_hours: int
    max_template_size_mb: float
    supported_formats: List[str]
    fallback_template: str
    
    def __post_init__(self):
        """Validate template configuration for backward compatibility."""
        if self.cache_duration_hours < 0:
            raise ValueError("Cache duration must be non-negative")
        if self.max_template_size_mb <= 0:
            raise ValueError("Max template size must be positive")


@dataclass
class ContentGenerationConfig:
    """Backward-compatible adapter for ContentGenerationConfig."""
    ai_model: str
    max_content_length: int
    max_title_length: int
    content_cache_hours: int
    prompt_templates_file: str
    default_language: str
    supported_languages: List[str]
    content_validation_enabled: bool
    sentiment_analysis_enabled: bool
    
    def __post_init__(self):
        """Validate content generation configuration."""
        if self.max_content_length <= 0:
            raise ValueError("Max content length must be positive")
        if self.max_title_length <= 0:
            raise ValueError("Max title length must be positive")


@dataclass
class SchedulingConfig:
    """Backward-compatible adapter for SchedulingConfig."""
    default_send_hour: int
    timezone_aware: bool
    default_timezone: str
    batch_size: int
    delivery_timeout_seconds: int
    max_concurrent_deliveries: int
    rate_limit_per_minute: int
    rate_limit_per_hour: int
    enable_delivery_tracking: bool
    
    def __post_init__(self):
        """Validate scheduling configuration."""
        if not 0 <= self.default_send_hour <= 23:
            raise ValueError("Default send hour must be between 0 and 23")
        if self.batch_size <= 0:
            raise ValueError("Batch size must be positive")


@dataclass
class AnalyticsConfig:
    """Backward-compatible adapter for AnalyticsConfig."""
    enabled: bool
    track_user_interactions: bool
    track_delivery_metrics: bool
    track_content_performance: bool
    retention_days: int
    aggregate_hourly: bool
    aggregate_daily: bool
    export_format: str
    
    def __post_init__(self):
        """Validate analytics configuration."""
        if self.retention_days < 0:
            raise ValueError("Retention days must be non-negative")
        if self.export_format not in ["json", "csv"]:
            raise ValueError("Export format must be 'json' or 'csv'")


@dataclass
class RetryConfig:
    """Backward-compatible adapter for RetryConfig."""
    max_retries: int
    initial_delay_seconds: int
    max_delay_seconds: int
    backoff_multiplier: float
    retry_on_network_error: bool
    retry_on_rate_limit: bool
    retry_on_server_error: bool
    dead_letter_queue_enabled: bool
    
    def __post_init__(self):
        """Validate retry configuration."""
        if self.max_retries < 0:
            raise ValueError("Max retries must be non-negative")
        if self.initial_delay_seconds < 0:
            raise ValueError("Initial delay must be non-negative")


class RichMessageSystemConfig:
    """
    Backward-compatible adapter for RichMessageSystemConfig.
    
    This class maintains the same API as src/config/rich_message_config.py while
    using the centralized configuration system internally.
    """
    
    def __init__(self):
        """Initialize configuration from centralized config."""
        self.load_configuration()
    
    def load_configuration(self):
        """Load configuration from centralized configuration system."""
        config = get_config()
        
        # Core Rich Message config
        from src.models.rich_message_models import RichMessageConfig as RichMessageConfigModel
        self.rich_message = RichMessageConfigModel(
            daily_send_hour=config.rich_message.default_send_hour,
            max_retries=config.rich_message.max_retries,
            retry_delay_minutes=30,  # Default value in minutes
            template_cache_duration_hours=config.rich_message.template_cache_hours,
            content_cache_duration_hours=config.rich_message.content_cache_hours,
            default_language="en",  # Default language
            fallback_template="motivation_bright_01",  # Default fallback
            enabled_categories=[ContentCategory(cat.value) for cat in config.rich_message.enabled_categories],
            timezone_aware=config.rich_message.timezone_aware,
            analytics_enabled=config.rich_message.analytics_enabled
        )
        
        # Template configuration
        self.template = TemplateConfig(
            template_directory=str(config.template.template_directory),
            metadata_file=str(config.template.metadata_file),
            cache_templates=config.template.cache_templates,
            cache_duration_hours=config.rich_message.template_cache_hours,  # From rich_message config
            max_template_size_mb=config.template.max_template_size_mb,
            supported_formats=config.template.supported_formats,
            fallback_template=config.template.fallback_template
        )
        
        # Content generation configuration
        self.content_generation = ContentGenerationConfig(
            ai_model=config.azure_openai.deployment_name,  # Use Azure OpenAI deployment name
            max_content_length=2000,  # Default value
            max_title_length=100,  # Default value
            content_cache_hours=config.rich_message.content_cache_hours,
            prompt_templates_file="/home/runner/workspace/src/config/content_prompts.json",  # Default path
            default_language="en",  # Default language
            supported_languages=["en", "th", "zh", "ja", "ko", "vi", "es", "fr", "de"],  # Default languages
            content_validation_enabled=True,  # Default value
            sentiment_analysis_enabled=True  # Default value
        )
        
        # Scheduling configuration
        self.scheduling = SchedulingConfig(
            default_send_hour=config.rich_message.default_send_hour,
            timezone_aware=config.rich_message.timezone_aware,
            default_timezone=config.rich_message.default_timezone,
            batch_size=config.rich_message.batch_size,
            delivery_timeout_seconds=30,  # Default value
            max_concurrent_deliveries=10,  # Default value
            rate_limit_per_minute=config.rich_message.rate_limit_per_minute,
            rate_limit_per_hour=config.rich_message.rate_limit_per_hour,
            enable_delivery_tracking=True  # Default value
        )
        
        # Analytics configuration
        self.analytics = AnalyticsConfig(
            enabled=config.rich_message.analytics_enabled,
            track_user_interactions=True,  # Default value
            track_delivery_metrics=True,  # Default value
            track_content_performance=True,  # Default value
            retention_days=90,  # Default value
            aggregate_hourly=True,  # Default value
            aggregate_daily=True,  # Default value
            export_format="json"  # Default value
        )
        
        # Retry configuration
        self.retry = RetryConfig(
            max_retries=config.rich_message.max_retries,
            initial_delay_seconds=30,  # Default value
            max_delay_seconds=300,  # Default value
            backoff_multiplier=2.0,  # Default value
            retry_on_network_error=True,  # Default value
            retry_on_rate_limit=True,  # Default value
            retry_on_server_error=True,  # Default value
            dead_letter_queue_enabled=True  # Default value
        )
        
        logger.info("Rich Message system configuration loaded from centralized config")
    
    def validate_configuration(self) -> bool:
        """Validate the complete configuration."""
        try:
            # Validate template directory exists
            if not os.path.exists(self.template.template_directory):
                logger.error(f"Template directory not found: {self.template.template_directory}")
                return False
            
            # Validate metadata file exists
            if not os.path.exists(self.template.metadata_file):
                logger.error(f"Template metadata file not found: {self.template.metadata_file}")
                return False
            
            # Validate enabled categories
            if not self.rich_message.enabled_categories:
                logger.warning("No content categories enabled")
            
            # Validate rate limits
            if self.scheduling.rate_limit_per_hour < self.scheduling.rate_limit_per_minute * 60:
                logger.warning("Hourly rate limit may be inconsistent with per-minute limit")
            
            logger.info("Rich Message configuration validation passed")
            return True
            
        except Exception as e:
            logger.error(f"Configuration validation failed: {str(e)}")
            return False
    
    def get_enabled_categories(self) -> List[ContentCategory]:
        """Get list of enabled content categories."""
        return self.rich_message.enabled_categories
    
    def is_category_enabled(self, category: ContentCategory) -> bool:
        """Check if a content category is enabled."""
        return category in self.rich_message.enabled_categories
    
    def get_template_path(self, filename: str) -> str:
        """Get full path to a template file."""
        return os.path.join(self.template.template_directory, filename)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary for debugging/logging."""
        return {
            "rich_message": self.rich_message.to_dict(),
            "template": {
                "template_directory": self.template.template_directory,
                "metadata_file": self.template.metadata_file,
                "cache_templates": self.template.cache_templates,
                "cache_duration_hours": self.template.cache_duration_hours,
                "max_template_size_mb": self.template.max_template_size_mb,
                "supported_formats": self.template.supported_formats,
                "fallback_template": self.template.fallback_template
            },
            "content_generation": {
                "ai_model": self.content_generation.ai_model,
                "max_content_length": self.content_generation.max_content_length,
                "max_title_length": self.content_generation.max_title_length,
                "content_cache_hours": self.content_generation.content_cache_hours,
                "default_language": self.content_generation.default_language,
                "supported_languages": self.content_generation.supported_languages,
                "content_validation_enabled": self.content_generation.content_validation_enabled,
                "sentiment_analysis_enabled": self.content_generation.sentiment_analysis_enabled
            },
            "scheduling": {
                "default_send_hour": self.scheduling.default_send_hour,
                "timezone_aware": self.scheduling.timezone_aware,
                "default_timezone": self.scheduling.default_timezone,
                "batch_size": self.scheduling.batch_size,
                "delivery_timeout_seconds": self.scheduling.delivery_timeout_seconds,
                "max_concurrent_deliveries": self.scheduling.max_concurrent_deliveries,
                "rate_limit_per_minute": self.scheduling.rate_limit_per_minute,
                "rate_limit_per_hour": self.scheduling.rate_limit_per_hour
            },
            "analytics": {
                "enabled": self.analytics.enabled,
                "track_user_interactions": self.analytics.track_user_interactions,
                "track_delivery_metrics": self.analytics.track_delivery_metrics,
                "track_content_performance": self.analytics.track_content_performance,
                "retention_days": self.analytics.retention_days,
                "export_format": self.analytics.export_format
            },
            "retry": {
                "max_retries": self.retry.max_retries,
                "initial_delay_seconds": self.retry.initial_delay_seconds,
                "max_delay_seconds": self.retry.max_delay_seconds,
                "backoff_multiplier": self.retry.backoff_multiplier,
                "retry_on_network_error": self.retry.retry_on_network_error,
                "retry_on_rate_limit": self.retry.retry_on_rate_limit,
                "retry_on_server_error": self.retry.retry_on_server_error,
                "dead_letter_queue_enabled": self.retry.dead_letter_queue_enabled
            }
        }


# Global configuration instance
_rich_config_instance: Optional[RichMessageSystemConfig] = None


def get_rich_message_config() -> RichMessageSystemConfig:
    """Get the global Rich Message configuration instance."""
    global _rich_config_instance
    if _rich_config_instance is None:
        _rich_config_instance = RichMessageSystemConfig()
        
        # Validate configuration on first load
        if not _rich_config_instance.validate_configuration():
            logger.warning("Rich Message configuration validation failed")
    
    return _rich_config_instance


def reload_rich_message_config() -> RichMessageSystemConfig:
    """Reload the configuration from environment variables."""
    global _rich_config_instance
    _rich_config_instance = None
    return get_rich_message_config()