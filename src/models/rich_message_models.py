"""
Data models for Rich Message automation system

This module defines the data structures used throughout the Rich Message
automation system including content models, templates, and validation.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from enum import Enum
import json
import logging

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Custom exception for validation errors"""
    pass


class ContentCategory(Enum):
    """Content category enumeration"""
    MOTIVATION = "motivation"
    INSPIRATION = "inspiration" 
    WELLNESS = "wellness"
    PRODUCTIVITY = "productivity"
    NATURE = "nature"
    EDUCATIONAL = "educational"
    GENERAL = "general"


class ContentTheme(Enum):
    """Content theme enumeration"""
    MORNING_ENERGY = "morning_energy"
    EVENING_CALM = "evening_calm"
    WEEKLY_GOALS = "weekly_goals"
    DAILY_TIPS = "daily_tips"
    SEASONAL = "seasonal"
    SPECIAL_EVENTS = "special_events"


class DeliveryStatus(Enum):
    """Delivery status enumeration"""
    PENDING = "pending"
    PROCESSING = "processing"
    SENT = "sent"
    FAILED = "failed"
    RETRYING = "retrying"


@dataclass
class TextArea:
    """Text area positioning for template overlay"""
    x: int
    y: int
    width: int
    height: int
    max_chars: Optional[int] = None
    font_size: Optional[int] = None
    font_color: Optional[str] = None
    alignment: str = "left"
    
    def __post_init__(self):
        """Validate text area parameters"""
        if self.x < 0 or self.y < 0:
            raise ValidationError("Text area coordinates must be non-negative")
        if self.width <= 0 or self.height <= 0:
            raise ValidationError("Text area dimensions must be positive")
        if self.alignment not in ["left", "center", "right"]:
            raise ValidationError("Text alignment must be 'left', 'center', or 'right'")


@dataclass
class RichMessageTemplate:
    """Rich Message template configuration"""
    template_id: str
    filename: str
    category: ContentCategory
    theme: ContentTheme
    mood: str
    energy_level: str
    text_areas: Dict[str, TextArea]
    best_for: List[str] = field(default_factory=list)
    time_of_day: List[str] = field(default_factory=list)
    content_types: List[str] = field(default_factory=list)
    dimensions: Tuple[int, int] = (2500, 1686)
    file_size_mb: Optional[float] = None
    created_at: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self):
        """Validate template configuration"""
        if not self.template_id or not self.filename:
            raise ValidationError("Template ID and filename are required")
        
        if not isinstance(self.category, ContentCategory):
            raise ValidationError("Category must be a ContentCategory enum")
            
        if not isinstance(self.theme, ContentTheme):
            raise ValidationError("Theme must be a ContentTheme enum")
        
        # Validate dimensions for LINE Rich Menu
        if self.dimensions not in [(2500, 1686), (2500, 843)]:
            raise ValidationError("Template dimensions must be 2500x1686 or 2500x843 pixels")
        
        # Validate text areas
        for area_name, area in self.text_areas.items():
            if not isinstance(area, TextArea):
                raise ValidationError(f"Text area '{area_name}' must be a TextArea instance")
    
    @classmethod
    def from_metadata(cls, template_id: str, metadata: Dict[str, Any]) -> 'RichMessageTemplate':
        """Create template from metadata dictionary"""
        try:
            # Parse text areas
            text_areas = {}
            for area_name, area_data in metadata.get('text_areas', {}).items():
                text_areas[area_name] = TextArea(**area_data)
            
            return cls(
                template_id=template_id,
                filename=metadata['filename'],
                category=ContentCategory(metadata['theme']),
                theme=ContentTheme(metadata.get('content_theme', 'daily_tips')),
                mood=metadata['mood'],
                energy_level=metadata['energy_level'],
                text_areas=text_areas,
                best_for=metadata.get('best_for', []),
                time_of_day=metadata.get('time_of_day', []),
                content_types=metadata.get('content_type', [])
            )
        except (KeyError, ValueError, TypeError) as e:
            raise ValidationError(f"Invalid template metadata: {str(e)}")
    
    def is_suitable_for_time(self, hour: int) -> bool:
        """Check if template is suitable for given hour"""
        time_mappings = {
            "morning": range(6, 12),
            "afternoon": range(12, 17),
            "evening": range(17, 22),
            "night": range(22, 24)
        }
        
        for time_period in self.time_of_day:
            if time_period in time_mappings and hour in time_mappings[time_period]:
                return True
        return False
    
    def matches_energy_level(self, desired_energy: str) -> bool:
        """Check if template matches desired energy level"""
        energy_hierarchy = {
            "very_low": 1,
            "low": 2,
            "medium": 3,
            "high": 4,
            "very_high": 5
        }
        
        template_level = energy_hierarchy.get(self.energy_level, 3)
        desired_level = energy_hierarchy.get(desired_energy, 3)
        
        # Allow templates within 1 level of desired energy
        return abs(template_level - desired_level) <= 1


@dataclass
class RichMessageContent:
    """Rich Message content data"""
    content_id: str
    title: str
    content: str
    category: ContentCategory
    theme: ContentTheme
    template_id: str
    generated_at: datetime = field(default_factory=datetime.now)
    ai_prompt_used: Optional[str] = None
    content_length: int = field(init=False)
    language: str = "en"
    sentiment: Optional[str] = None
    keywords: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Validate and process content"""
        if not self.content_id or not self.title or not self.content:
            raise ValidationError("Content ID, title, and content are required")
        
        if not isinstance(self.category, ContentCategory):
            raise ValidationError("Category must be a ContentCategory enum")
            
        if not isinstance(self.theme, ContentTheme):
            raise ValidationError("Theme must be a ContentTheme enum")
        
        # Calculate content length
        self.content_length = len(self.content)
        
        # Validate content length for Rich Messages
        if self.content_length > 2000:  # Reasonable limit for Rich Message display
            raise ValidationError("Content is too long for Rich Message display")
        
        if len(self.title) > 100:
            raise ValidationError("Title is too long (max 100 characters)")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "content_id": self.content_id,
            "title": self.title,
            "content": self.content,
            "category": self.category.value,
            "theme": self.theme.value,
            "template_id": self.template_id,
            "generated_at": self.generated_at.isoformat(),
            "ai_prompt_used": self.ai_prompt_used,
            "content_length": self.content_length,
            "language": self.language,
            "sentiment": self.sentiment,
            "keywords": self.keywords
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RichMessageContent':
        """Create from dictionary"""
        try:
            return cls(
                content_id=data['content_id'],
                title=data['title'],
                content=data['content'],
                category=ContentCategory(data['category']),
                theme=ContentTheme(data['theme']),
                template_id=data['template_id'],
                generated_at=datetime.fromisoformat(data['generated_at']),
                ai_prompt_used=data.get('ai_prompt_used'),
                language=data.get('language', 'en'),
                sentiment=data.get('sentiment'),
                keywords=data.get('keywords', [])
            )
        except (KeyError, ValueError, TypeError) as e:
            raise ValidationError(f"Invalid content data: {str(e)}")


@dataclass
class UserInteraction:
    """User interaction with Rich Messages"""
    interaction_id: str
    user_id: str
    content_id: str
    action: str  # view, share, save, like, react
    timestamp: datetime = field(default_factory=datetime.now)
    additional_data: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate interaction data"""
        if not self.interaction_id or not self.user_id or not self.content_id:
            raise ValidationError("Interaction ID, user ID, and content ID are required")
        
        valid_actions = ["view", "share", "save", "like", "react", "click", "postback"]
        if self.action not in valid_actions:
            raise ValidationError(f"Action must be one of: {', '.join(valid_actions)}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            "interaction_id": self.interaction_id,
            "user_id": self.user_id,
            "content_id": self.content_id,
            "action": self.action,
            "timestamp": self.timestamp.isoformat(),
            "additional_data": self.additional_data
        }


@dataclass
class DeliveryRecord:
    """Rich Message delivery record"""
    delivery_id: str
    content_id: str
    template_id: str
    status: DeliveryStatus
    scheduled_time: datetime
    delivered_time: Optional[datetime] = None
    target_audience: Optional[str] = None
    user_count: Optional[int] = None
    success_count: Optional[int] = None
    failure_count: Optional[int] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self):
        """Validate delivery record"""
        if not self.delivery_id or not self.content_id:
            raise ValidationError("Delivery ID and content ID are required")
        
        if not isinstance(self.status, DeliveryStatus):
            raise ValidationError("Status must be a DeliveryStatus enum")
    
    def mark_as_sent(self, success_count: int, failure_count: int = 0):
        """Mark delivery as sent with success/failure counts"""
        self.status = DeliveryStatus.SENT
        self.delivered_time = datetime.now()
        self.success_count = success_count
        self.failure_count = failure_count
    
    def mark_as_failed(self, error_message: str):
        """Mark delivery as failed with error message"""
        self.status = DeliveryStatus.FAILED
        self.error_message = error_message
    
    def mark_for_retry(self):
        """Mark delivery for retry"""
        self.status = DeliveryStatus.RETRYING
        self.retry_count += 1
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            "delivery_id": self.delivery_id,
            "content_id": self.content_id,
            "template_id": self.template_id,
            "status": self.status.value,
            "scheduled_time": self.scheduled_time.isoformat(),
            "delivered_time": self.delivered_time.isoformat() if self.delivered_time else None,
            "target_audience": self.target_audience,
            "user_count": self.user_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "created_at": self.created_at.isoformat()
        }


@dataclass
class RichMessageConfig:
    """Configuration for Rich Message system"""
    daily_send_hour: int = 9  # Default send time: 9 AM
    max_retries: int = 3
    retry_delay_minutes: int = 30
    template_cache_duration_hours: int = 24
    content_cache_duration_hours: int = 6
    default_language: str = "en"
    fallback_template: str = "motivation_bright_01"
    enabled_categories: List[ContentCategory] = field(default_factory=lambda: list(ContentCategory))
    timezone_aware: bool = True
    analytics_enabled: bool = True
    
    def __post_init__(self):
        """Validate configuration"""
        if not 0 <= self.daily_send_hour <= 23:
            raise ValidationError("Daily send hour must be between 0 and 23")
        
        if self.max_retries < 0:
            raise ValidationError("Max retries must be non-negative")
        
        if self.retry_delay_minutes < 0:
            raise ValidationError("Retry delay must be non-negative")
        
        if not self.enabled_categories:
            self.enabled_categories = list(ContentCategory)
    
    @classmethod
    def from_env(cls, **overrides) -> 'RichMessageConfig':
        """Create configuration from environment variables with overrides"""
        import os
        
        config = cls(
            daily_send_hour=int(os.environ.get('RICH_MESSAGE_SEND_HOUR', '9')),
            max_retries=int(os.environ.get('RICH_MESSAGE_MAX_RETRIES', '3')),
            retry_delay_minutes=int(os.environ.get('RICH_MESSAGE_RETRY_DELAY', '30')),
            template_cache_duration_hours=int(os.environ.get('RICH_MESSAGE_TEMPLATE_CACHE', '24')),
            content_cache_duration_hours=int(os.environ.get('RICH_MESSAGE_CONTENT_CACHE', '6')),
            default_language=os.environ.get('RICH_MESSAGE_DEFAULT_LANGUAGE', 'en'),
            fallback_template=os.environ.get('RICH_MESSAGE_FALLBACK_TEMPLATE', 'motivation_bright_01'),
            timezone_aware=os.environ.get('RICH_MESSAGE_TIMEZONE_AWARE', 'true').lower() == 'true',
            analytics_enabled=os.environ.get('RICH_MESSAGE_ANALYTICS', 'true').lower() == 'true'
        )
        
        # Apply overrides
        for key, value in overrides.items():
            if hasattr(config, key):
                setattr(config, key, value)
        
        return config
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "daily_send_hour": self.daily_send_hour,
            "max_retries": self.max_retries,
            "retry_delay_minutes": self.retry_delay_minutes,
            "template_cache_duration_hours": self.template_cache_duration_hours,
            "content_cache_duration_hours": self.content_cache_duration_hours,
            "default_language": self.default_language,
            "fallback_template": self.fallback_template,
            "enabled_categories": [cat.value for cat in self.enabled_categories],
            "timezone_aware": self.timezone_aware,
            "analytics_enabled": self.analytics_enabled
        }