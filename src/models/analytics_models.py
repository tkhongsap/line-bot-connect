"""
PostgreSQL Analytics Models

This module defines SQLAlchemy models for Rich Message analytics and tracking
data, providing a robust PostgreSQL-based persistence layer for analytics.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from enum import Enum as PyEnum
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, Text, JSON,
    ForeignKey, Index, UniqueConstraint, CheckConstraint
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, ENUM
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, Session
from sqlalchemy.sql import func

Base = declarative_base()


# Enums for PostgreSQL
class ContentCategoryEnum(PyEnum):
    """Content category enumeration"""
    MOTIVATION = "motivation"
    INSPIRATION = "inspiration"
    WELLNESS = "wellness"
    PRODUCTIVITY = "productivity"
    NATURE = "nature"
    EDUCATIONAL = "educational"
    GENERAL = "general"


class DeliveryStatusEnum(PyEnum):
    """Message delivery status enumeration"""
    PENDING = "pending"
    PROCESSING = "processing"
    SENT = "sent"
    FAILED = "failed"
    RETRYING = "retrying"


class InteractionTypeEnum(PyEnum):
    """User interaction type enumeration"""
    VIEW = "view"
    CLICK = "click"
    SHARE = "share"
    REPLY = "reply"
    POSTBACK = "postback"
    FOLLOW = "follow"
    UNFOLLOW = "unfollow"


class TemplateModel(Base):
    """
    Rich Message template metadata model.
    
    Stores information about available templates including metadata,
    usage statistics, and performance metrics.
    """
    __tablename__ = 'templates'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template_id = Column(String(100), unique=True, nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    category = Column(ENUM(ContentCategoryEnum), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    
    # Template properties
    width = Column(Integer)
    height = Column(Integer)
    file_size_bytes = Column(Integer)
    format = Column(String(10))  # png, jpg, etc.
    
    # Text overlay configuration
    text_areas = Column(JSONB)  # JSON array of text area definitions
    font_config = Column(JSONB)  # Font configuration
    color_scheme = Column(JSONB)  # Color scheme information
    
    # Usage and performance metrics
    usage_count = Column(Integer, default=0, nullable=False)
    success_rate = Column(Float, default=0.0)  # 0.0 to 1.0
    avg_engagement_score = Column(Float, default=0.0)
    last_used_at = Column(DateTime(timezone=True))
    
    # Metadata
    tags = Column(JSONB)  # Array of tags
    metadata = Column(JSONB)  # Additional metadata
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    contents = relationship("ContentModel", back_populates="template")
    deliveries = relationship("DeliveryModel", back_populates="template")

    # Indexes
    __table_args__ = (
        Index('idx_templates_category_active', 'category', 'is_active'),
        Index('idx_templates_usage_count', 'usage_count'),
        Index('idx_templates_success_rate', 'success_rate'),
        Index('idx_templates_created_at', 'created_at'),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API serialization"""
        return {
            'id': str(self.id),
            'template_id': self.template_id,
            'filename': self.filename,
            'category': self.category.value if self.category else None,
            'name': self.name,
            'description': self.description,
            'width': self.width,
            'height': self.height,
            'file_size_bytes': self.file_size_bytes,
            'format': self.format,
            'text_areas': self.text_areas,
            'font_config': self.font_config,
            'color_scheme': self.color_scheme,
            'usage_count': self.usage_count,
            'success_rate': self.success_rate,
            'avg_engagement_score': self.avg_engagement_score,
            'last_used_at': self.last_used_at.isoformat() if self.last_used_at else None,
            'tags': self.tags,
            'metadata': self.metadata,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class ContentModel(Base):
    """
    Rich Message content model.
    
    Stores generated content including AI-generated text, metadata,
    and performance tracking.
    """
    __tablename__ = 'contents'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    content_id = Column(String(100), unique=True, nullable=False, index=True)
    template_id = Column(UUID(as_uuid=True), ForeignKey('templates.id'), nullable=False)
    
    # Content data
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=False)
    language = Column(String(5), default='en', nullable=False)
    category = Column(ENUM(ContentCategoryEnum), nullable=False, index=True)
    
    # Content generation metadata
    ai_model = Column(String(100))  # Model used for generation
    generation_prompt = Column(Text)  # Prompt used
    generation_metadata = Column(JSONB)  # Additional generation metadata
    
    # Content properties
    word_count = Column(Integer)
    sentiment_score = Column(Float)  # -1.0 to 1.0
    readability_score = Column(Float)
    topic_tags = Column(JSONB)  # Array of topic tags
    
    # Performance metrics
    usage_count = Column(Integer, default=0, nullable=False)
    engagement_score = Column(Float, default=0.0)
    avg_interaction_rate = Column(Float, default=0.0)
    
    # Status and lifecycle
    is_approved = Column(Boolean, default=True, nullable=False)
    is_archived = Column(Boolean, default=False, nullable=False)
    archived_reason = Column(String(500))
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False)
    approved_at = Column(DateTime(timezone=True))
    archived_at = Column(DateTime(timezone=True))

    # Relationships
    template = relationship("TemplateModel", back_populates="contents")
    deliveries = relationship("DeliveryModel", back_populates="content")
    interactions = relationship("InteractionModel", back_populates="content")

    # Indexes
    __table_args__ = (
        Index('idx_contents_category_approved', 'category', 'is_approved'),
        Index('idx_contents_language', 'language'),
        Index('idx_contents_created_at', 'created_at'),
        Index('idx_contents_usage_count', 'usage_count'),
        Index('idx_contents_engagement_score', 'engagement_score'),
        CheckConstraint('sentiment_score >= -1.0 AND sentiment_score <= 1.0', name='check_sentiment_range'),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API serialization"""
        return {
            'id': str(self.id),
            'content_id': self.content_id,
            'template_id': str(self.template_id),
            'title': self.title,
            'content': self.content,
            'language': self.language,
            'category': self.category.value if self.category else None,
            'ai_model': self.ai_model,
            'generation_prompt': self.generation_prompt,
            'generation_metadata': self.generation_metadata,
            'word_count': self.word_count,
            'sentiment_score': self.sentiment_score,
            'readability_score': self.readability_score,
            'topic_tags': self.topic_tags,
            'usage_count': self.usage_count,
            'engagement_score': self.engagement_score,
            'avg_interaction_rate': self.avg_interaction_rate,
            'is_approved': self.is_approved,
            'is_archived': self.is_archived,
            'archived_reason': self.archived_reason,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'approved_at': self.approved_at.isoformat() if self.approved_at else None,
            'archived_at': self.archived_at.isoformat() if self.archived_at else None
        }


class DeliveryModel(Base):
    """
    Message delivery tracking model.
    
    Tracks individual Rich Message deliveries including status,
    timing, and delivery metadata.
    """
    __tablename__ = 'deliveries'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    delivery_id = Column(String(100), unique=True, nullable=False, index=True)
    content_id = Column(UUID(as_uuid=True), ForeignKey('contents.id'), nullable=False)
    template_id = Column(UUID(as_uuid=True), ForeignKey('templates.id'), nullable=False)
    
    # Delivery target
    user_id = Column(String(100), nullable=False, index=True)
    channel_id = Column(String(100))
    group_id = Column(String(100))
    
    # Delivery status and timing
    status = Column(ENUM(DeliveryStatusEnum), default=DeliveryStatusEnum.PENDING, nullable=False, index=True)
    scheduled_at = Column(DateTime(timezone=True), nullable=False)
    sent_at = Column(DateTime(timezone=True))
    delivered_at = Column(DateTime(timezone=True))
    failed_at = Column(DateTime(timezone=True))
    
    # Retry tracking
    retry_count = Column(Integer, default=0, nullable=False)
    max_retries = Column(Integer, default=3, nullable=False)
    next_retry_at = Column(DateTime(timezone=True))
    
    # Delivery metadata
    message_id = Column(String(200))  # LINE message ID
    delivery_metadata = Column(JSONB)  # Additional delivery data
    error_message = Column(Text)
    error_code = Column(String(50))
    
    # Performance tracking
    processing_time_ms = Column(Integer)  # Time to process and send
    delivery_time_ms = Column(Integer)  # Time to deliver
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    content = relationship("ContentModel", back_populates="deliveries")
    template = relationship("TemplateModel", back_populates="deliveries")
    interactions = relationship("InteractionModel", back_populates="delivery")

    # Indexes
    __table_args__ = (
        Index('idx_deliveries_user_id', 'user_id'),
        Index('idx_deliveries_status', 'status'),
        Index('idx_deliveries_scheduled_at', 'scheduled_at'),
        Index('idx_deliveries_sent_at', 'sent_at'),
        Index('idx_deliveries_created_at', 'created_at'),
        Index('idx_deliveries_retry_count', 'retry_count'),
        Index('idx_deliveries_user_status', 'user_id', 'status'),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API serialization"""
        return {
            'id': str(self.id),
            'delivery_id': self.delivery_id,
            'content_id': str(self.content_id),
            'template_id': str(self.template_id),
            'user_id': self.user_id,
            'channel_id': self.channel_id,
            'group_id': self.group_id,
            'status': self.status.value if self.status else None,
            'scheduled_at': self.scheduled_at.isoformat() if self.scheduled_at else None,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'delivered_at': self.delivered_at.isoformat() if self.delivered_at else None,
            'failed_at': self.failed_at.isoformat() if self.failed_at else None,
            'retry_count': self.retry_count,
            'max_retries': self.max_retries,
            'next_retry_at': self.next_retry_at.isoformat() if self.next_retry_at else None,
            'message_id': self.message_id,
            'delivery_metadata': self.delivery_metadata,
            'error_message': self.error_message,
            'error_code': self.error_code,
            'processing_time_ms': self.processing_time_ms,
            'delivery_time_ms': self.delivery_time_ms,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class InteractionModel(Base):
    """
    User interaction tracking model.
    
    Tracks user interactions with Rich Messages including clicks,
    shares, replies, and other engagement metrics.
    """
    __tablename__ = 'interactions'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    interaction_id = Column(String(100), unique=True, nullable=False, index=True)
    delivery_id = Column(UUID(as_uuid=True), ForeignKey('deliveries.id'), nullable=False)
    content_id = Column(UUID(as_uuid=True), ForeignKey('contents.id'), nullable=False)
    
    # Interaction details
    user_id = Column(String(100), nullable=False, index=True)
    interaction_type = Column(ENUM(InteractionTypeEnum), nullable=False, index=True)
    interaction_data = Column(JSONB)  # Type-specific interaction data
    
    # Context information
    timestamp = Column(DateTime(timezone=True), default=func.now(), nullable=False, index=True)
    session_id = Column(String(100))
    device_type = Column(String(50))
    user_agent = Column(Text)
    ip_address = Column(String(45))  # IPv6 compatible
    location_data = Column(JSONB)  # Geographic data if available
    
    # Engagement metrics
    engagement_score = Column(Float, default=1.0)  # Weighted score based on interaction type
    time_to_interact_seconds = Column(Integer)  # Time from delivery to interaction
    interaction_duration_ms = Column(Integer)  # Duration of interaction
    
    # Additional metadata
    metadata = Column(JSONB)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)

    # Relationships
    delivery = relationship("DeliveryModel", back_populates="interactions")
    content = relationship("ContentModel", back_populates="interactions")

    # Indexes
    __table_args__ = (
        Index('idx_interactions_user_id', 'user_id'),
        Index('idx_interactions_type', 'interaction_type'),
        Index('idx_interactions_timestamp', 'timestamp'),
        Index('idx_interactions_user_timestamp', 'user_id', 'timestamp'),
        Index('idx_interactions_content_type', 'content_id', 'interaction_type'),
        Index('idx_interactions_engagement_score', 'engagement_score'),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API serialization"""
        return {
            'id': str(self.id),
            'interaction_id': self.interaction_id,
            'delivery_id': str(self.delivery_id),
            'content_id': str(self.content_id),
            'user_id': self.user_id,
            'interaction_type': self.interaction_type.value if self.interaction_type else None,
            'interaction_data': self.interaction_data,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'session_id': self.session_id,
            'device_type': self.device_type,
            'user_agent': self.user_agent,
            'ip_address': self.ip_address,
            'location_data': self.location_data,
            'engagement_score': self.engagement_score,
            'time_to_interact_seconds': self.time_to_interact_seconds,
            'interaction_duration_ms': self.interaction_duration_ms,
            'metadata': self.metadata,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class AnalyticsAggregateModel(Base):
    """
    Pre-aggregated analytics data model.
    
    Stores pre-computed analytics aggregations for faster reporting
    and dashboard queries.
    """
    __tablename__ = 'analytics_aggregates'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Aggregation metadata
    aggregate_type = Column(String(50), nullable=False, index=True)  # hourly, daily, weekly, monthly
    dimension = Column(String(100), nullable=False, index=True)  # template, content, user, category
    dimension_value = Column(String(200), nullable=False)  # Actual dimension value
    date = Column(DateTime(timezone=True), nullable=False, index=True)
    
    # Delivery metrics
    deliveries_sent = Column(Integer, default=0, nullable=False)
    deliveries_failed = Column(Integer, default=0, nullable=False)
    unique_recipients = Column(Integer, default=0, nullable=False)
    
    # Interaction metrics
    total_interactions = Column(Integer, default=0, nullable=False)
    unique_interactors = Column(Integer, default=0, nullable=False)
    interactions_by_type = Column(JSONB)  # Count by interaction type
    
    # Engagement metrics
    engagement_rate = Column(Float, default=0.0)
    avg_engagement_score = Column(Float, default=0.0)
    avg_time_to_interact = Column(Float, default=0.0)  # seconds
    
    # Performance metrics
    avg_processing_time_ms = Column(Float, default=0.0)
    avg_delivery_time_ms = Column(Float, default=0.0)
    success_rate = Column(Float, default=0.0)
    
    # Additional metrics
    custom_metrics = Column(JSONB)  # Extensible custom metrics
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False)

    # Indexes
    __table_args__ = (
        Index('idx_aggregates_type_dimension', 'aggregate_type', 'dimension'),
        Index('idx_aggregates_date', 'date'),
        Index('idx_aggregates_dimension_value', 'dimension_value'),
        Index('idx_aggregates_type_date', 'aggregate_type', 'date'),
        UniqueConstraint('aggregate_type', 'dimension', 'dimension_value', 'date', name='uq_aggregate_key'),
        CheckConstraint('engagement_rate >= 0.0 AND engagement_rate <= 1.0', name='check_engagement_rate_range'),
        CheckConstraint('success_rate >= 0.0 AND success_rate <= 1.0', name='check_success_rate_range'),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API serialization"""
        return {
            'id': str(self.id),
            'aggregate_type': self.aggregate_type,
            'dimension': self.dimension,
            'dimension_value': self.dimension_value,
            'date': self.date.isoformat() if self.date else None,
            'deliveries_sent': self.deliveries_sent,
            'deliveries_failed': self.deliveries_failed,
            'unique_recipients': self.unique_recipients,
            'total_interactions': self.total_interactions,
            'unique_interactors': self.unique_interactors,
            'interactions_by_type': self.interactions_by_type,
            'engagement_rate': self.engagement_rate,
            'avg_engagement_score': self.avg_engagement_score,
            'avg_time_to_interact': self.avg_time_to_interact,
            'avg_processing_time_ms': self.avg_processing_time_ms,
            'avg_delivery_time_ms': self.avg_delivery_time_ms,
            'success_rate': self.success_rate,
            'custom_metrics': self.custom_metrics,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class SystemMetricsModel(Base):
    """
    System-level metrics and health tracking model.
    
    Tracks overall system performance, health indicators,
    and operational metrics.
    """
    __tablename__ = 'system_metrics'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Metric metadata
    metric_name = Column(String(100), nullable=False, index=True)
    metric_type = Column(String(50), nullable=False)  # counter, gauge, histogram
    timestamp = Column(DateTime(timezone=True), default=func.now(), nullable=False, index=True)
    
    # Metric values
    value = Column(Float, nullable=False)
    unit = Column(String(50))
    tags = Column(JSONB)  # Key-value tags for filtering/grouping
    
    # Additional data
    metadata = Column(JSONB)
    
    # Indexes
    __table_args__ = (
        Index('idx_system_metrics_name_timestamp', 'metric_name', 'timestamp'),
        Index('idx_system_metrics_type', 'metric_type'),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API serialization"""
        return {
            'id': str(self.id),
            'metric_name': self.metric_name,
            'metric_type': self.metric_type,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'value': self.value,
            'unit': self.unit,
            'tags': self.tags,
            'metadata': self.metadata
        }


# Model registry for easy access
ANALYTICS_MODELS = {
    'template': TemplateModel,
    'content': ContentModel,
    'delivery': DeliveryModel,
    'interaction': InteractionModel,
    'analytics_aggregate': AnalyticsAggregateModel,
    'system_metrics': SystemMetricsModel
}


def get_model_by_name(name: str) -> Base:
    """Get model class by name"""
    return ANALYTICS_MODELS.get(name)


def get_all_models() -> List[Base]:
    """Get all analytics model classes"""
    return list(ANALYTICS_MODELS.values())