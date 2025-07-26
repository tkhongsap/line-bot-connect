"""
Rich Message configuration settings

This module provides configuration management for the Rich Message automation system,
including environment variable handling, validation, and default settings.
"""

import os
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from src.models.rich_message_models import RichMessageConfig, ContentCategory, ValidationError

logger = logging.getLogger(__name__)


@dataclass
class TemplateConfig:
    """Template system configuration"""
    template_directory: str = "/home/runner/workspace/templates/rich_messages/backgrounds"
    metadata_file: str = "/home/runner/workspace/templates/rich_messages/metadata.json"
    cache_templates: bool = True
    cache_duration_hours: int = 24
    max_template_size_mb: float = 5.0
    supported_formats: List[str] = field(default_factory=lambda: ["png", "jpg", "jpeg"])
    fallback_template: str = "motivation_bright_01.png"
    
    def __post_init__(self):
        """Validate template configuration"""
        if not os.path.exists(self.template_directory):
            logger.warning(f"Template directory does not exist: {self.template_directory}")
        
        if self.cache_duration_hours < 0:
            raise ValidationError("Cache duration must be non-negative")
        
        if self.max_template_size_mb <= 0:
            raise ValidationError("Max template size must be positive")


@dataclass 
class ContentGenerationConfig:
    """Content generation configuration"""
    ai_model: str = "gpt-4.1-nano"
    max_content_length: int = 2000
    max_title_length: int = 100
    content_cache_hours: int = 6
    prompt_templates_file: str = "/home/runner/workspace/src/config/content_prompts.json"
    default_language: str = "en"
    supported_languages: List[str] = field(default_factory=lambda: [
        "en", "th", "zh", "ja", "ko", "vi", "es", "fr", "de"
    ])
    content_validation_enabled: bool = True
    sentiment_analysis_enabled: bool = True
    
    def __post_init__(self):
        """Validate content generation configuration"""
        if self.max_content_length <= 0:
            raise ValidationError("Max content length must be positive")
        
        if self.max_title_length <= 0:
            raise ValidationError("Max title length must be positive")
        
        if self.default_language not in self.supported_languages:
            raise ValidationError(f"Default language must be one of: {self.supported_languages}")


@dataclass
class SchedulingConfig:
    """Scheduling and delivery configuration"""
    default_send_hour: int = 9  # 9 AM
    timezone_aware: bool = True
    default_timezone: str = "UTC"
    batch_size: int = 100
    delivery_timeout_seconds: int = 30
    max_concurrent_deliveries: int = 10
    rate_limit_per_minute: int = 1000
    rate_limit_per_hour: int = 10000
    enable_delivery_tracking: bool = True
    
    def __post_init__(self):
        """Validate scheduling configuration"""
        if not 0 <= self.default_send_hour <= 23:
            raise ValidationError("Default send hour must be between 0 and 23")
        
        if self.batch_size <= 0:
            raise ValidationError("Batch size must be positive")
        
        if self.delivery_timeout_seconds <= 0:
            raise ValidationError("Delivery timeout must be positive")


@dataclass
class AnalyticsConfig:
    """Analytics and monitoring configuration"""
    enabled: bool = True
    track_user_interactions: bool = True
    track_delivery_metrics: bool = True
    track_content_performance: bool = True
    retention_days: int = 90
    aggregate_hourly: bool = True
    aggregate_daily: bool = True
    export_format: str = "json"  # json, csv
    
    def __post_init__(self):
        """Validate analytics configuration"""
        if self.retention_days < 0:
            raise ValidationError("Retention days must be non-negative")
        
        if self.export_format not in ["json", "csv"]:
            raise ValidationError("Export format must be 'json' or 'csv'")


@dataclass
class RetryConfig:
    """Retry and error handling configuration"""
    max_retries: int = 3
    initial_delay_seconds: int = 30
    max_delay_seconds: int = 300
    backoff_multiplier: float = 2.0
    retry_on_network_error: bool = True
    retry_on_rate_limit: bool = True
    retry_on_server_error: bool = True
    dead_letter_queue_enabled: bool = True
    
    def __post_init__(self):
        """Validate retry configuration"""
        if self.max_retries < 0:
            raise ValidationError("Max retries must be non-negative")
        
        if self.initial_delay_seconds < 0:
            raise ValidationError("Initial delay must be non-negative")
        
        if self.backoff_multiplier < 1.0:
            raise ValidationError("Backoff multiplier must be >= 1.0")


class RichMessageSystemConfig:
    """Complete Rich Message system configuration"""
    
    def __init__(self):
        """Initialize configuration from environment variables"""
        self.load_configuration()
    
    def load_configuration(self):
        """Load configuration from environment variables and defaults"""
        try:
            # Core Rich Message config
            self.rich_message = RichMessageConfig.from_env()
            
            # Template configuration
            self.template = TemplateConfig(
                template_directory=os.environ.get(
                    'RICH_MESSAGE_TEMPLATE_DIR', 
                    '/home/runner/workspace/templates/rich_messages/backgrounds'
                ),
                metadata_file=os.environ.get(
                    'RICH_MESSAGE_METADATA_FILE',
                    '/home/runner/workspace/templates/rich_messages/metadata.json'
                ),
                cache_templates=os.environ.get('RICH_MESSAGE_CACHE_TEMPLATES', 'true').lower() == 'true',
                cache_duration_hours=int(os.environ.get('RICH_MESSAGE_TEMPLATE_CACHE_HOURS', '24')),
                max_template_size_mb=float(os.environ.get('RICH_MESSAGE_MAX_TEMPLATE_SIZE_MB', '5.0')),
                fallback_template=os.environ.get('RICH_MESSAGE_FALLBACK_TEMPLATE', 'motivation_bright_01.png')
            )
            
            # Content generation configuration
            self.content_generation = ContentGenerationConfig(
                ai_model=os.environ.get('RICH_MESSAGE_AI_MODEL', 'gpt-4.1-nano'),
                max_content_length=int(os.environ.get('RICH_MESSAGE_MAX_CONTENT_LENGTH', '2000')),
                max_title_length=int(os.environ.get('RICH_MESSAGE_MAX_TITLE_LENGTH', '100')),
                content_cache_hours=int(os.environ.get('RICH_MESSAGE_CONTENT_CACHE_HOURS', '6')),
                default_language=os.environ.get('RICH_MESSAGE_DEFAULT_LANGUAGE', 'en'),
                content_validation_enabled=os.environ.get('RICH_MESSAGE_CONTENT_VALIDATION', 'true').lower() == 'true',
                sentiment_analysis_enabled=os.environ.get('RICH_MESSAGE_SENTIMENT_ANALYSIS', 'true').lower() == 'true'
            )
            
            # Scheduling configuration
            self.scheduling = SchedulingConfig(
                default_send_hour=int(os.environ.get('RICH_MESSAGE_DEFAULT_SEND_HOUR', '9')),
                timezone_aware=os.environ.get('RICH_MESSAGE_TIMEZONE_AWARE', 'true').lower() == 'true',
                default_timezone=os.environ.get('RICH_MESSAGE_DEFAULT_TIMEZONE', 'UTC'),
                batch_size=int(os.environ.get('RICH_MESSAGE_BATCH_SIZE', '100')),
                delivery_timeout_seconds=int(os.environ.get('RICH_MESSAGE_DELIVERY_TIMEOUT', '30')),
                max_concurrent_deliveries=int(os.environ.get('RICH_MESSAGE_MAX_CONCURRENT', '10')),
                rate_limit_per_minute=int(os.environ.get('RICH_MESSAGE_RATE_LIMIT_MINUTE', '1000')),
                rate_limit_per_hour=int(os.environ.get('RICH_MESSAGE_RATE_LIMIT_HOUR', '10000'))
            )
            
            # Analytics configuration
            self.analytics = AnalyticsConfig(
                enabled=os.environ.get('RICH_MESSAGE_ANALYTICS_ENABLED', 'true').lower() == 'true',
                track_user_interactions=os.environ.get('RICH_MESSAGE_TRACK_INTERACTIONS', 'true').lower() == 'true',
                track_delivery_metrics=os.environ.get('RICH_MESSAGE_TRACK_DELIVERY', 'true').lower() == 'true',
                track_content_performance=os.environ.get('RICH_MESSAGE_TRACK_PERFORMANCE', 'true').lower() == 'true',
                retention_days=int(os.environ.get('RICH_MESSAGE_RETENTION_DAYS', '90')),
                export_format=os.environ.get('RICH_MESSAGE_EXPORT_FORMAT', 'json')
            )
            
            # Retry configuration
            self.retry = RetryConfig(
                max_retries=int(os.environ.get('RICH_MESSAGE_MAX_RETRIES', '3')),
                initial_delay_seconds=int(os.environ.get('RICH_MESSAGE_INITIAL_DELAY', '30')),
                max_delay_seconds=int(os.environ.get('RICH_MESSAGE_MAX_DELAY', '300')),
                backoff_multiplier=float(os.environ.get('RICH_MESSAGE_BACKOFF_MULTIPLIER', '2.0')),
                retry_on_network_error=os.environ.get('RICH_MESSAGE_RETRY_NETWORK', 'true').lower() == 'true',
                retry_on_rate_limit=os.environ.get('RICH_MESSAGE_RETRY_RATE_LIMIT', 'true').lower() == 'true',
                retry_on_server_error=os.environ.get('RICH_MESSAGE_RETRY_SERVER_ERROR', 'true').lower() == 'true',
                dead_letter_queue_enabled=os.environ.get('RICH_MESSAGE_DLQ_ENABLED', 'true').lower() == 'true'
            )
            
            logger.info("Rich Message system configuration loaded successfully")
            
        except Exception as e:
            logger.error(f"Error loading Rich Message configuration: {str(e)}")
            raise
    
    def validate_configuration(self) -> bool:
        """Validate the complete configuration"""
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
        """Get list of enabled content categories"""
        return self.rich_message.enabled_categories
    
    def is_category_enabled(self, category: ContentCategory) -> bool:
        """Check if a content category is enabled"""
        return category in self.rich_message.enabled_categories
    
    def get_template_path(self, filename: str) -> str:
        """Get full path to a template file"""
        return os.path.join(self.template.template_directory, filename)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary for debugging/logging"""
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
_config_instance: Optional[RichMessageSystemConfig] = None


def get_rich_message_config() -> RichMessageSystemConfig:
    """Get the global Rich Message configuration instance"""
    global _config_instance
    if _config_instance is None:
        _config_instance = RichMessageSystemConfig()
        
        # Validate configuration on first load
        if not _config_instance.validate_configuration():
            logger.warning("Rich Message configuration validation failed")
    
    return _config_instance


def reload_rich_message_config() -> RichMessageSystemConfig:
    """Reload the configuration from environment variables"""
    global _config_instance
    _config_instance = None
    return get_rich_message_config()