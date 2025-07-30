"""
Centralized Configuration System for LINE Bot Application

This module provides a unified configuration management system using Pydantic
for validation, type checking, and environment variable loading. It consolidates
all configuration settings from various parts of the application.
"""

import os
import logging
from typing import List, Dict, Any, Optional, Union
from enum import Enum
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class Environment(str, Enum):
    """Application environment types"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"


class LogLevel(str, Enum):
    """Logging level options"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class ContentCategory(str, Enum):
    """Rich Message content categories"""
    MOTIVATION = "motivation"
    INSPIRATION = "inspiration"
    WELLNESS = "wellness"
    PRODUCTIVITY = "productivity"
    NATURE = "nature"
    EDUCATIONAL = "educational"
    GENERAL = "general"


class LineConfig(BaseModel):
    """LINE Bot configuration"""
    channel_access_token: SecretStr = Field(..., description="LINE Bot channel access token")
    channel_secret: SecretStr = Field(..., description="LINE Bot channel secret for webhook verification")
    channel_id: Optional[str] = Field(None, description="LINE Bot channel ID")
    
    @field_validator('channel_access_token', 'channel_secret')
    @classmethod
    def validate_required_secrets(cls, v):
        if not v:
            raise ValueError("Required LINE configuration missing")
        return v
    
    model_config = ConfigDict(frozen=True)


class AzureOpenAIConfig(BaseModel):
    """Azure OpenAI configuration"""
    api_key: SecretStr = Field(..., description="Azure OpenAI API key")
    endpoint: str = Field(
        default="https://thaibev-azure-subscription-ai-foundry.cognitiveservices.azure.com",
        description="Azure OpenAI endpoint URL"
    )
    api_version: str = Field(
        default="2025-01-01-preview",
        description="Azure OpenAI API version"
    )
    deployment_name: str = Field(
        default="gpt-4.1-nano",
        description="Azure OpenAI deployment name"
    )
    
    @field_validator('endpoint')
    @classmethod
    def validate_endpoint(cls, v):
        if not v.startswith(('http://', 'https://')):
            raise ValueError("Endpoint must be a valid HTTP(S) URL")
        return v.rstrip('/')
    
    @field_validator('api_key')
    @classmethod
    def validate_api_key(cls, v):
        if not v:
            raise ValueError("Azure OpenAI API key is required")
        return v
    
    model_config = ConfigDict(frozen=True)


class ConversationConfig(BaseModel):
    """Conversation management configuration"""
    max_messages_per_user: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Maximum messages to store per user conversation"
    )
    max_total_conversations: int = Field(
        default=1000,
        ge=1,
        le=10000,
        description="Maximum total conversations to maintain"
    )
    storage_backend: str = Field(
        default="memory",
        pattern="^(memory|redis)$",
        description="Storage backend for conversations"
    )
    redis_url: Optional[str] = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL if using Redis backend"
    )
    conversation_ttl_hours: int = Field(
        default=72,
        ge=1,
        le=720,
        description="Conversation TTL in hours"
    )
    
    @model_validator(mode='after')
    def validate_redis_config(self):
        if self.storage_backend == 'redis' and not self.redis_url:
            raise ValueError("Redis URL required when using Redis backend")
        return self
    
    model_config = ConfigDict(frozen=True)


class RichMessageConfig(BaseModel):
    """Rich Message automation configuration"""
    enabled: bool = Field(
        default=False,
        description="Enable Rich Message automation system"
    )
    enabled_categories: List[ContentCategory] = Field(
        default_factory=lambda: [ContentCategory.MOTIVATION],
        description="Enabled content categories"
    )
    default_send_hour: int = Field(
        default=9,
        ge=0,
        le=23,
        description="Default hour to send messages (24-hour format)"
    )
    timezone_aware: bool = Field(
        default=True,
        description="Enable timezone-aware scheduling"
    )
    default_timezone: str = Field(
        default="UTC",
        description="Default timezone for scheduling"
    )
    analytics_enabled: bool = Field(
        default=True,
        description="Enable Rich Message analytics tracking"
    )
    template_cache_hours: int = Field(
        default=24,
        ge=0,
        le=168,
        description="Template cache duration in hours"
    )
    content_cache_hours: int = Field(
        default=6,
        ge=0,
        le=48,
        description="Content cache duration in hours"
    )
    max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Maximum retry attempts for failed deliveries"
    )
    batch_size: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Batch size for message delivery"
    )
    rate_limit_per_minute: int = Field(
        default=1000,
        ge=1,
        le=10000,
        description="Rate limit per minute for message delivery"
    )
    rate_limit_per_hour: int = Field(
        default=10000,
        ge=1,
        le=100000,
        description="Rate limit per hour for message delivery"
    )
    
    @field_validator('enabled_categories')
    @classmethod
    def validate_categories(cls, v):
        if not v:
            return [ContentCategory.MOTIVATION]
        return v
    
    @model_validator(mode='after')
    def validate_rate_limits(self):
        if self.rate_limit_per_hour < self.rate_limit_per_minute * 60:
            logger.warning(
                f"Hourly rate limit ({self.rate_limit_per_hour}) may be inconsistent with "
                f"per-minute limit ({self.rate_limit_per_minute} * 60 = {self.rate_limit_per_minute * 60})"
            )
        return self
    
    model_config = ConfigDict(frozen=True)


class TemplateConfig(BaseModel):
    """Template system configuration"""
    template_directory: Path = Field(
        default=Path("/home/runner/workspace/templates/rich_messages/backgrounds"),
        description="Directory containing template images"
    )
    metadata_file: Path = Field(
        default=Path("/home/runner/workspace/templates/rich_messages/metadata.json"),
        description="Template metadata JSON file path"
    )
    cache_templates: bool = Field(
        default=True,
        description="Enable template caching"
    )
    max_template_size_mb: float = Field(
        default=5.0,
        gt=0,
        le=50.0,
        description="Maximum template file size in MB"
    )
    supported_formats: List[str] = Field(
        default_factory=lambda: ["png", "jpg", "jpeg"],
        description="Supported image formats"
    )
    fallback_template: str = Field(
        default="motivation_bright_01.png",
        description="Fallback template filename"
    )
    
    @field_validator('template_directory', 'metadata_file')
    @classmethod
    def validate_paths(cls, v):
        if not isinstance(v, Path):
            v = Path(v)
        return v
    
    model_config = ConfigDict(frozen=True)


class CeleryConfig(BaseModel):
    """Celery task queue configuration"""
    broker_url: str = Field(
        default="redis://localhost:6379/0",
        description="Celery broker URL"
    )
    result_backend: str = Field(
        default="redis://localhost:6379/0",
        description="Celery result backend URL"
    )
    task_time_limit: int = Field(
        default=300,
        ge=10,
        le=3600,
        description="Task time limit in seconds"
    )
    task_soft_time_limit: int = Field(
        default=240,
        ge=10,
        le=3600,
        description="Task soft time limit in seconds"
    )
    worker_max_tasks_per_child: int = Field(
        default=1000,
        ge=1,
        le=10000,
        description="Maximum tasks per worker child"
    )
    
    @model_validator(mode='after')
    def validate_time_limits(self):
        if self.task_soft_time_limit >= self.task_time_limit:
            raise ValueError("Soft time limit must be less than hard time limit")
        return self
    
    model_config = ConfigDict(frozen=True)


class ApplicationConfig(BaseModel):
    """General application configuration"""
    environment: Environment = Field(
        default=Environment.DEVELOPMENT,
        description="Application environment"
    )
    debug: bool = Field(
        default=True,
        description="Enable debug mode"
    )
    log_level: LogLevel = Field(
        default=LogLevel.INFO,
        description="Application log level"
    )
    session_secret: SecretStr = Field(
        default_factory=lambda: SecretStr(os.urandom(24).hex()),
        description="Flask session secret key"
    )
    host: str = Field(
        default="0.0.0.0",
        description="Application host"
    )
    port: int = Field(
        default=5000,
        ge=1,
        le=65535,
        description="Application port"
    )
    workers: int = Field(
        default=4,
        ge=1,
        le=16,
        description="Number of worker processes"
    )
    
    @field_validator('debug')
    @classmethod
    def validate_debug_mode(cls, v, info):
        if info.data.get('environment') == Environment.PRODUCTION and v:
            logger.warning("Debug mode enabled in production environment")
        return v
    
    model_config = ConfigDict(frozen=True)


class RateLimitConfig(BaseModel):
    """Rate limiting configuration"""
    enabled: bool = Field(
        default=True,
        description="Enable rate limiting"
    )
    default_limits: List[str] = Field(
        default_factory=lambda: ["200 per day", "50 per hour"],
        description="Default rate limits"
    )
    storage_uri: str = Field(
        default="memory://",
        description="Rate limit storage URI"
    )
    webhook_limit: str = Field(
        default="100 per minute",
        description="Webhook endpoint rate limit"
    )
    api_limit: str = Field(
        default="60 per minute",
        description="API endpoint rate limit"
    )
    
    model_config = ConfigDict(frozen=True)


class CentralizedConfig(BaseSettings):
    """
    Centralized configuration for the LINE Bot application.
    
    This class consolidates all configuration settings and provides
    validation, type checking, and environment variable loading.
    """
    
    # Configuration version for migration support
    config_version: str = Field(
        default="1.0.0",
        description="Configuration schema version"
    )
    
    # Sub-configurations
    line: LineConfig
    azure_openai: AzureOpenAIConfig
    conversation: ConversationConfig = Field(default_factory=ConversationConfig)
    rich_message: RichMessageConfig = Field(default_factory=RichMessageConfig)
    template: TemplateConfig = Field(default_factory=TemplateConfig)
    celery: CeleryConfig = Field(default_factory=CeleryConfig)
    application: ApplicationConfig = Field(default_factory=ApplicationConfig)
    rate_limit: RateLimitConfig = Field(default_factory=RateLimitConfig)
    
    # Additional configurations
    web_search_enabled: bool = Field(
        default=True,
        description="Enable web search functionality"
    )
    web_search_rate_limit: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Web search rate limit per user per hour"
    )
    web_search_cache_minutes: int = Field(
        default=15,
        ge=0,
        le=60,
        description="Web search result cache duration in minutes"
    )
    
    multimodal_enabled: bool = Field(
        default=True,
        description="Enable image understanding capabilities"
    )
    max_image_size_mb: float = Field(
        default=5.0,
        gt=0,
        le=20.0,
        description="Maximum image size in MB"
    )
    max_image_dimension: int = Field(
        default=2048,
        ge=512,
        le=4096,
        description="Maximum image dimension in pixels"
    )
    
    supported_languages: List[str] = Field(
        default_factory=lambda: ["en", "th", "zh", "ja", "ko", "vi", "es", "fr", "de"],
        description="Supported languages for multilingual responses"
    )
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore"
    )
    
    @classmethod
    def from_env(cls) -> "CentralizedConfig":
        """
        Create configuration from environment variables.
        
        This method provides backward compatibility with the existing
        environment variable names while using Pydantic's validation.
        """
        # Map existing environment variables to new structure
        line_config = LineConfig(
            channel_access_token=os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", ""),
            channel_secret=os.environ.get("LINE_CHANNEL_SECRET", ""),
            channel_id=os.environ.get("LINE_CHANNEL_ID")
        )
        
        azure_config = AzureOpenAIConfig(
            api_key=os.environ.get("AZURE_OPENAI_API_KEY", ""),
            endpoint=os.environ.get(
                "AZURE_OPENAI_ENDPOINT",
                "https://thaibev-azure-subscription-ai-foundry.cognitiveservices.azure.com"
            ),
            api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2025-01-01-preview"),
            deployment_name=os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4.1-nano")
        )
        
        conversation_config = ConversationConfig(
            max_messages_per_user=int(os.environ.get("MAX_MESSAGES_PER_USER", "100")),
            max_total_conversations=int(os.environ.get("MAX_TOTAL_CONVERSATIONS", "1000")),
            storage_backend=os.environ.get("CONVERSATION_STORAGE_BACKEND", "memory"),
            redis_url=os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        )
        
        rich_message_config = RichMessageConfig(
            enabled=os.environ.get("RICH_MESSAGE_ENABLED", "false").lower() == "true",
            default_send_hour=int(os.environ.get("RICH_MESSAGE_DEFAULT_SEND_HOUR", "9")),
            timezone_aware=os.environ.get("RICH_MESSAGE_TIMEZONE_AWARE", "true").lower() == "true",
            analytics_enabled=os.environ.get("RICH_MESSAGE_ANALYTICS_ENABLED", "true").lower() == "true",
            template_cache_hours=int(os.environ.get("RICH_MESSAGE_TEMPLATE_CACHE_HOURS", "24")),
            content_cache_hours=int(os.environ.get("RICH_MESSAGE_CONTENT_CACHE_HOURS", "6")),
            max_retries=int(os.environ.get("RICH_MESSAGE_MAX_RETRIES", "3")),
            batch_size=int(os.environ.get("RICH_MESSAGE_BATCH_SIZE", "100")),
            rate_limit_per_minute=int(os.environ.get("RICH_MESSAGE_RATE_LIMIT_MINUTE", "1000")),
            rate_limit_per_hour=int(os.environ.get("RICH_MESSAGE_RATE_LIMIT_HOUR", "10000"))
        )
        
        template_config = TemplateConfig(
            template_directory=os.environ.get(
                "RICH_MESSAGE_TEMPLATE_DIR",
                "/home/runner/workspace/templates/rich_messages/backgrounds"
            ),
            metadata_file=os.environ.get(
                "RICH_MESSAGE_METADATA_FILE",
                "/home/runner/workspace/templates/rich_messages/metadata.json"
            ),
            cache_templates=os.environ.get("RICH_MESSAGE_CACHE_TEMPLATES", "true").lower() == "true",
            max_template_size_mb=float(os.environ.get("RICH_MESSAGE_MAX_TEMPLATE_SIZE_MB", "5.0")),
            fallback_template=os.environ.get("RICH_MESSAGE_FALLBACK_TEMPLATE", "motivation_bright_01.png")
        )
        
        celery_config = CeleryConfig(
            broker_url=os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0"),
            result_backend=os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
        )
        
        app_config = ApplicationConfig(
            environment=Environment(os.environ.get("ENVIRONMENT", "development")),
            debug=os.environ.get("DEBUG", "true").lower() == "true",
            log_level=LogLevel(os.environ.get("LOG_LEVEL", "INFO")),
            session_secret=os.environ.get("SESSION_SECRET", os.urandom(24).hex())
        )
        
        return cls(
            line=line_config,
            azure_openai=azure_config,
            conversation=conversation_config,
            rich_message=rich_message_config,
            template=template_config,
            celery=celery_config,
            application=app_config
        )
    
    def validate_configuration(self) -> bool:
        """
        Validate the complete configuration.
        
        Returns:
            bool: True if configuration is valid
        """
        try:
            # Template directory validation
            if self.rich_message.enabled:
                # For testing environments, templates might not exist
                if not self.template.template_directory.exists():
                    logger.warning(f"Template directory not found: {self.template.template_directory}")
                    if self.application.environment not in (Environment.TESTING, Environment.DEVELOPMENT):
                        return False
                
                if not self.template.metadata_file.exists():
                    logger.warning(f"Template metadata file not found: {self.template.metadata_file}")
                    if self.application.environment not in (Environment.TESTING, Environment.DEVELOPMENT):
                        return False
            
            # Ensure Celery is configured if Rich Messages are enabled
            if self.rich_message.enabled and not self.celery.broker_url:
                logger.error("Celery broker URL required when Rich Messages are enabled")
                return False
            
            logger.info("Configuration validation passed")
            return True
            
        except Exception as e:
            logger.error(f"Configuration validation failed: {str(e)}")
            return False
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get a summary of configuration without sensitive values.
        
        Returns:
            Dict containing non-sensitive configuration summary
        """
        return {
            "config_version": self.config_version,
            "environment": self.application.environment.value,
            "debug_mode": self.application.debug,
            "log_level": self.application.log_level.value,
            "azure_endpoint": self.azure_openai.endpoint,
            "api_version": self.azure_openai.api_version,
            "deployment_name": self.azure_openai.deployment_name,
            "max_messages_per_user": self.conversation.max_messages_per_user,
            "max_total_conversations": self.conversation.max_total_conversations,
            "conversation_storage": self.conversation.storage_backend,
            "rich_message_enabled": self.rich_message.enabled,
            "rich_message_categories": [cat.value for cat in self.rich_message.enabled_categories],
            "web_search_enabled": self.web_search_enabled,
            "multimodal_enabled": self.multimodal_enabled,
            "supported_languages": self.supported_languages,
            "rate_limiting_enabled": self.rate_limit.enabled
        }
    
    def to_dict(self, include_secrets: bool = False) -> Dict[str, Any]:
        """
        Convert configuration to dictionary.
        
        Args:
            include_secrets: Include sensitive values (default: False)
            
        Returns:
            Dictionary representation of configuration
        """
        # Get base dictionary
        data = self.model_dump(mode='json')
        
        if include_secrets:
            # Replace masked secrets with actual values
            if hasattr(self.line.channel_access_token, 'get_secret_value'):
                data['line']['channel_access_token'] = self.line.channel_access_token.get_secret_value()
            if hasattr(self.line.channel_secret, 'get_secret_value'):
                data['line']['channel_secret'] = self.line.channel_secret.get_secret_value()
            if hasattr(self.azure_openai.api_key, 'get_secret_value'):
                data['azure_openai']['api_key'] = self.azure_openai.api_key.get_secret_value()
            if hasattr(self.application.session_secret, 'get_secret_value'):
                data['application']['session_secret'] = self.application.session_secret.get_secret_value()
        else:
            # Mask sensitive values
            if 'line' in data:
                data['line']['channel_access_token'] = "***"
                data['line']['channel_secret'] = "***"
            if 'azure_openai' in data:
                data['azure_openai']['api_key'] = "***"
            if 'application' in data:
                data['application']['session_secret'] = "***"
        
        return data
    
    @property
    def is_production(self) -> bool:
        """Check if running in production environment"""
        return self.application.environment == Environment.PRODUCTION
    
    @property
    def is_development(self) -> bool:
        """Check if running in development environment"""
        return self.application.environment == Environment.DEVELOPMENT


# Global configuration instance
_config_instance: Optional[CentralizedConfig] = None


def get_config() -> CentralizedConfig:
    """
    Get the global configuration instance.
    
    Returns:
        CentralizedConfig: The configuration instance
    """
    global _config_instance
    if _config_instance is None:
        _config_instance = CentralizedConfig.from_env()
        
        # Validate configuration on first load
        if not _config_instance.validate_configuration():
            logger.warning("Configuration validation failed")
    
    return _config_instance


def reload_config() -> CentralizedConfig:
    """
    Reload configuration from environment variables.
    
    This function creates a new configuration instance from the current
    environment variables, useful for hot-reloading configuration changes.
    
    Returns:
        CentralizedConfig: The reloaded configuration instance
    """
    global _config_instance
    
    # Clear any cached environment variables
    load_dotenv(override=True)
    
    # Store old configuration for comparison
    old_config = _config_instance
    old_version = old_config.config_version if old_config else "unknown"
    
    # Create new configuration instance
    try:
        new_config = CentralizedConfig.from_env()
        
        # Validate the new configuration
        if not new_config.validate_configuration():
            logger.error("New configuration validation failed, keeping old configuration")
            return old_config if old_config else new_config
        
        # Replace global instance
        _config_instance = new_config
        
        logger.info(f"Configuration reloaded successfully (old: {old_version}, new: {new_config.config_version})")
        return _config_instance
        
    except Exception as e:
        logger.error(f"Failed to reload configuration: {e}")
        if old_config:
            logger.info("Keeping previous configuration due to reload failure")
            return old_config
        raise


def reset_config() -> None:
    """
    Reset the global configuration instance.
    
    This forces the next call to get_config() to create a new instance.
    Useful for testing and configuration management.
    """
    global _config_instance
    _config_instance = None
    logger.info("Configuration instance reset")


def get_settings_summary() -> Dict[str, Any]:
    """
    Get configuration summary for backward compatibility.
    
    Returns:
        Dict containing configuration summary
    """
    config = get_config()
    return config.get_summary()


# Backward compatibility exports
__all__ = [
    "CentralizedConfig",
    "get_config",
    "reload_config",
    "reset_config",
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