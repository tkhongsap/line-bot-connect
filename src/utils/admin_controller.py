"""
Administrative Controller for Rich Message Automation System.

This module provides administrative controls for manual triggering, monitoring,
and management of Rich Message campaigns and analytics.
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from enum import Enum
import json
import uuid

from src.utils.analytics_tracker import get_analytics_tracker
from src.utils.interaction_handler import get_interaction_handler
from src.utils.metrics_storage import get_metrics_storage
from src.utils.memory_monitor import get_memory_monitor
from src.services.rich_message_service import RichMessageService
from src.services.line_service import LineService
from src.config.settings import Settings

logger = logging.getLogger(__name__)


class CampaignStatus(Enum):
    """Rich Message campaign status"""
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class AdminPermission(Enum):
    """Administrative permission levels"""
    READ_ONLY = "read_only"
    CAMPAIGN_MANAGER = "campaign_manager"
    ANALYTICS_VIEWER = "analytics_viewer"
    SYSTEM_ADMIN = "system_admin"


@dataclass
class RichMessageCampaign:
    """Rich Message campaign configuration"""
    campaign_id: str
    name: str
    description: str
    content_title: str
    content_message: str
    
    # Scheduling
    status: CampaignStatus = CampaignStatus.DRAFT
    scheduled_time: Optional[datetime] = None
    target_audience: Optional[str] = None  # "all" or audience_id
    
    # Content settings
    image_url: Optional[str] = None
    template_id: Optional[str] = None
    content_category: str = "general"
    include_interactions: bool = True
    
    # Campaign metadata
    created_by: str = "admin"
    created_at: datetime = None
    updated_at: datetime = None
    
    # Statistics
    total_sent: int = 0
    total_delivered: int = 0
    total_opened: int = 0
    total_interactions: int = 0
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)
        if self.updated_at is None:
            self.updated_at = datetime.now(timezone.utc)


@dataclass
class SystemHealthStatus:
    """System health monitoring status"""
    overall_status: str  # healthy, warning, critical
    timestamp: datetime
    
    # Service status
    line_service_status: str
    rich_message_service_status: str
    analytics_service_status: str
    database_status: str
    
    # Performance metrics
    avg_response_time_ms: float
    memory_usage_mb: Optional[float]
    active_campaigns: int
    pending_deliveries: int
    
    # Issues and alerts
    issues: List[str]
    warnings: List[str]
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)


class AdminController:
    """
    Administrative controller for Rich Message automation system.
    
    Provides centralized management of campaigns, analytics monitoring,
    manual triggering, and system health oversight.
    """
    
    def __init__(self):
        """Initialize the AdminController."""
        self.settings = Settings()
        self.analytics_tracker = get_analytics_tracker()
        self.interaction_handler = get_interaction_handler()
        self.metrics_storage = get_metrics_storage()
        self.memory_monitor = get_memory_monitor()
        
        # Campaign storage (in-memory for now, could be database later)
        self.campaigns: Dict[str, RichMessageCampaign] = {}
        
        # Admin session tracking
        self.admin_sessions: Dict[str, Dict[str, Any]] = {}
        
        logger.info("AdminController initialized")
    
    def create_campaign(self, 
                       name: str,
                       description: str,
                       content_title: str,
                       content_message: str,
                       created_by: str = "admin",
                       **kwargs) -> Dict[str, Any]:
        """
        Create a new Rich Message campaign.
        
        Args:
            name: Campaign name
            description: Campaign description
            content_title: Message title
            content_message: Message content
            created_by: Creator identifier
            **kwargs: Additional campaign parameters
            
        Returns:
            Result dictionary with campaign information
        """
        try:
            campaign_id = f"campaign_{uuid.uuid4().hex[:8]}"
            
            campaign = RichMessageCampaign(
                campaign_id=campaign_id,
                name=name,
                description=description,
                content_title=content_title,
                content_message=content_message,
                created_by=created_by,
                **kwargs
            )
            
            self.campaigns[campaign_id] = campaign
            
            logger.info(f"Created campaign {campaign_id}: {name}")
            
            return {
                "success": True,
                "campaign_id": campaign_id,
                "campaign": asdict(campaign),
                "message": f"Campaign '{name}' created successfully"
            }
            
        except Exception as e:
            logger.error(f"Failed to create campaign: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to create campaign"
            }
    
    def update_campaign(self, 
                       campaign_id: str,
                       updates: Dict[str, Any],
                       updated_by: str = "admin") -> Dict[str, Any]:
        """
        Update an existing campaign.
        
        Args:
            campaign_id: Campaign identifier
            updates: Dictionary of fields to update
            updated_by: Updater identifier
            
        Returns:
            Result dictionary
        """
        try:
            if campaign_id not in self.campaigns:
                return {
                    "success": False,
                    "error": "Campaign not found",
                    "message": f"Campaign {campaign_id} does not exist"
                }
            
            campaign = self.campaigns[campaign_id]
            
            # Prevent updates to active campaigns
            if campaign.status == CampaignStatus.ACTIVE:
                return {
                    "success": False,
                    "error": "Cannot update active campaign",
                    "message": "Stop the campaign before making changes"
                }
            
            # Apply updates
            for field, value in updates.items():
                if hasattr(campaign, field):
                    setattr(campaign, field, value)
            
            campaign.updated_at = datetime.now(timezone.utc)
            
            logger.info(f"Updated campaign {campaign_id} by {updated_by}")
            
            return {
                "success": True,
                "campaign_id": campaign_id,
                "campaign": asdict(campaign),
                "message": "Campaign updated successfully"
            }
            
        except Exception as e:
            logger.error(f"Failed to update campaign {campaign_id}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to update campaign"
            }
    
    def schedule_campaign(self, 
                         campaign_id: str,
                         scheduled_time: datetime,
                         target_audience: str = "all") -> Dict[str, Any]:
        """
        Schedule a campaign for delivery.
        
        Args:
            campaign_id: Campaign identifier
            scheduled_time: When to send the campaign
            target_audience: Target audience ("all" or audience_id)
            
        Returns:
            Result dictionary
        """
        try:
            if campaign_id not in self.campaigns:
                return {
                    "success": False,
                    "error": "Campaign not found"
                }
            
            campaign = self.campaigns[campaign_id]
            
            # Validate scheduling
            if scheduled_time <= datetime.now(timezone.utc):
                return {
                    "success": False,
                    "error": "Scheduled time must be in the future"
                }
            
            # Update campaign
            campaign.scheduled_time = scheduled_time
            campaign.target_audience = target_audience
            campaign.status = CampaignStatus.SCHEDULED
            campaign.updated_at = datetime.now(timezone.utc)
            
            logger.info(f"Scheduled campaign {campaign_id} for {scheduled_time}")
            
            return {
                "success": True,
                "campaign_id": campaign_id,
                "scheduled_time": scheduled_time.isoformat(),
                "target_audience": target_audience,
                "message": "Campaign scheduled successfully"
            }
            
        except Exception as e:
            logger.error(f"Failed to schedule campaign {campaign_id}: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def trigger_campaign_manual(self, 
                              campaign_id: str,
                              target_audience: str = "all",
                              triggered_by: str = "admin") -> Dict[str, Any]:
        """
        Manually trigger a campaign for immediate delivery.
        
        Args:
            campaign_id: Campaign identifier
            target_audience: Target audience
            triggered_by: Who triggered the campaign
            
        Returns:
            Result dictionary with delivery status
        """
        try:
            if campaign_id not in self.campaigns:
                return {
                    "success": False,
                    "error": "Campaign not found"
                }
            
            campaign = self.campaigns[campaign_id]
            
            # Create Rich Message service
            line_service = LineService(
                self.settings,
                openai_service=None,  # Not needed for Rich Messages
                conversation_service=None
            )
            
            rich_message_service = RichMessageService(
                line_bot_api=line_service.line_bot_api
            )
            
            # Create Flex Message
            flex_message = rich_message_service.create_flex_message(
                title=campaign.content_title,
                content=campaign.content_message,
                image_url=campaign.image_url,
                content_id=campaign_id,
                include_interactions=campaign.include_interactions
            )
            
            if not flex_message:
                return {
                    "success": False,
                    "error": "Failed to create Flex Message"
                }
            
            # Broadcast message
            broadcast_result = rich_message_service.broadcast_rich_message(
                flex_message=flex_message,
                target_audience=target_audience if target_audience != "all" else None
            )
            
            if broadcast_result["success"]:
                # Update campaign status
                campaign.status = CampaignStatus.ACTIVE
                campaign.updated_at = datetime.now(timezone.utc)
                campaign.total_sent += 1  # Simplified tracking
                
                logger.info(f"Manual trigger of campaign {campaign_id} by {triggered_by}")
                
                return {
                    "success": True,
                    "campaign_id": campaign_id,
                    "broadcast_result": broadcast_result,
                    "triggered_by": triggered_by,
                    "triggered_at": datetime.now(timezone.utc).isoformat(),
                    "message": "Campaign triggered successfully"
                }
            else:
                return {
                    "success": False,
                    "error": "Broadcast failed",
                    "details": broadcast_result
                }
            
        except Exception as e:
            logger.error(f"Failed to trigger campaign {campaign_id}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to trigger campaign"
            }
    
    def pause_campaign(self, campaign_id: str, paused_by: str = "admin") -> Dict[str, Any]:
        """
        Pause an active campaign.
        
        Args:
            campaign_id: Campaign identifier
            paused_by: Who paused the campaign
            
        Returns:
            Result dictionary
        """
        try:
            if campaign_id not in self.campaigns:
                return {
                    "success": False,
                    "error": "Campaign not found"
                }
            
            campaign = self.campaigns[campaign_id]
            
            if campaign.status not in [CampaignStatus.ACTIVE, CampaignStatus.SCHEDULED]:
                return {
                    "success": False,
                    "error": f"Cannot pause campaign with status: {campaign.status.value}"
                }
            
            campaign.status = CampaignStatus.PAUSED
            campaign.updated_at = datetime.now(timezone.utc)
            
            logger.info(f"Paused campaign {campaign_id} by {paused_by}")
            
            return {
                "success": True,
                "campaign_id": campaign_id,
                "paused_by": paused_by,
                "paused_at": datetime.now(timezone.utc).isoformat(),
                "message": "Campaign paused successfully"
            }
            
        except Exception as e:
            logger.error(f"Failed to pause campaign {campaign_id}: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_campaign_list(self, 
                         status_filter: Optional[CampaignStatus] = None,
                         limit: Optional[int] = None) -> Dict[str, Any]:
        """
        Get list of campaigns with optional filtering.
        
        Args:
            status_filter: Filter by campaign status
            limit: Maximum number of campaigns to return
            
        Returns:
            List of campaigns
        """
        try:
            campaigns = list(self.campaigns.values())
            
            # Apply status filter
            if status_filter:
                campaigns = [c for c in campaigns if c.status == status_filter]
            
            # Sort by creation date (newest first)
            campaigns.sort(key=lambda x: x.created_at, reverse=True)
            
            # Apply limit
            if limit:
                campaigns = campaigns[:limit]
            
            # Convert to dictionaries
            campaign_list = [asdict(campaign) for campaign in campaigns]
            
            return {
                "success": True,
                "campaigns": campaign_list,
                "total_count": len(self.campaigns),
                "filtered_count": len(campaign_list)
            }
            
        except Exception as e:
            logger.error(f"Failed to get campaign list: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "campaigns": []
            }
    
    def get_campaign_details(self, campaign_id: str) -> Dict[str, Any]:
        """
        Get detailed information about a specific campaign.
        
        Args:
            campaign_id: Campaign identifier
            
        Returns:
            Campaign details with analytics
        """
        try:
            if campaign_id not in self.campaigns:
                return {
                    "success": False,
                    "error": "Campaign not found"
                }
            
            campaign = self.campaigns[campaign_id]
            
            # Get interaction statistics for this campaign
            interaction_stats = self.interaction_handler.get_content_stats(campaign_id)
            
            # Get analytics data
            content_metrics = self.analytics_tracker.get_content_metrics(
                campaign.content_category, campaign_id
            )
            
            return {
                "success": True,
                "campaign": asdict(campaign),
                "interaction_stats": asdict(interaction_stats) if interaction_stats else None,
                "content_metrics": asdict(content_metrics) if content_metrics else None,
                "last_updated": campaign.updated_at.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get campaign details for {campaign_id}: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_analytics_dashboard(self, days: int = 7) -> Dict[str, Any]:
        """
        Get comprehensive analytics dashboard data.
        
        Args:
            days: Number of days to include in analytics
            
        Returns:
            Dashboard data with metrics and charts
        """
        try:
            # Get system metrics
            system_metrics = self.analytics_tracker.calculate_system_metrics()
            
            # Get persistent metrics summary
            persistent_summary = self.analytics_tracker.get_persistent_metrics_summary(days)
            
            # Get engagement summary from interaction handler
            interaction_summary = self.interaction_handler.get_engagement_analytics_summary()
            
            # Get top performing campaigns
            top_campaigns = []
            for campaign in sorted(
                self.campaigns.values(),
                key=lambda x: x.total_interactions,
                reverse=True
            )[:5]:
                top_campaigns.append({
                    "campaign_id": campaign.campaign_id,
                    "name": campaign.name,
                    "total_interactions": campaign.total_interactions,
                    "total_sent": campaign.total_sent,
                    "interaction_rate": (
                        campaign.total_interactions / campaign.total_sent
                        if campaign.total_sent > 0 else 0
                    )
                })
            
            # Get storage statistics
            storage_stats = self.metrics_storage.get_storage_statistics()
            
            return {
                "success": True,
                "dashboard_data": {
                    "period_days": days,
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "system_metrics": asdict(system_metrics),
                    "persistent_metrics": persistent_summary,
                    "interaction_summary": interaction_summary,
                    "top_campaigns": top_campaigns,
                    "campaign_summary": {
                        "total_campaigns": len(self.campaigns),
                        "active_campaigns": len([
                            c for c in self.campaigns.values()
                            if c.status == CampaignStatus.ACTIVE
                        ]),
                        "scheduled_campaigns": len([
                            c for c in self.campaigns.values()
                            if c.status == CampaignStatus.SCHEDULED
                        ])
                    },
                    "storage_stats": storage_stats
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to generate analytics dashboard: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "dashboard_data": {}
            }
    
    def check_system_health(self) -> SystemHealthStatus:
        """
        Perform comprehensive system health check.
        
        Returns:
            SystemHealthStatus object
        """
        try:
            issues = []
            warnings = []
            
            # Check LINE service
            line_status = "healthy"
            try:
                line_service = LineService(self.settings, None, None)
                # Simple test - if initialization works, service is likely healthy
            except Exception as e:
                line_status = "critical"
                issues.append(f"LINE service error: {str(e)}")
            
            # Check Rich Message service
            rich_message_status = "healthy"
            try:
                rich_message_service = RichMessageService(None)
            except Exception as e:
                rich_message_status = "warning"
                warnings.append(f"Rich Message service warning: {str(e)}")
            
            # Check analytics service
            analytics_status = "healthy"
            try:
                system_metrics = self.analytics_tracker.calculate_system_metrics()
                if system_metrics.overall_open_rate < 0.1:  # Less than 10% open rate
                    analytics_status = "warning"
                    warnings.append("Low overall open rate detected")
            except Exception as e:
                analytics_status = "critical"
                issues.append(f"Analytics service error: {str(e)}")
            
            # Check database
            database_status = "healthy"
            try:
                storage_stats = self.metrics_storage.get_storage_statistics()
                if "error" in storage_stats:
                    database_status = "critical"
                    issues.append("Database connection failed")
            except Exception as e:
                database_status = "critical"
                issues.append(f"Database error: {str(e)}")
            
            # Check memory usage
            memory_usage_mb = None
            try:
                memory_stats = self.memory_monitor.get_memory_stats()
                memory_usage_mb = memory_stats.process_memory / (1024 * 1024)
                
                # Add memory-related warnings
                if memory_stats.memory_percent >= 90:
                    issues.append(f"Critical memory usage: {memory_stats.memory_percent:.1f}%")
                elif memory_stats.memory_percent >= 70:
                    warnings.append(f"High memory usage: {memory_stats.memory_percent:.1f}%")
                
                # Check for active memory alerts
                active_alerts = self.memory_monitor.get_active_alerts()
                for alert in active_alerts:
                    if not alert.acknowledged:
                        if alert.level.value in ['critical', 'emergency']:
                            issues.append(f"Memory alert: {alert.title}")
                        else:
                            warnings.append(f"Memory alert: {alert.title}")
                            
            except Exception as e:
                warnings.append(f"Memory monitoring error: {str(e)}")
            
            # Calculate overall status
            if issues:
                overall_status = "critical"
            elif warnings:
                overall_status = "warning"
            else:
                overall_status = "healthy"
            
            # Calculate performance metrics
            avg_response_time = 150.0  # Placeholder - could be calculated from metrics
            active_campaigns = len([
                c for c in self.campaigns.values()
                if c.status == CampaignStatus.ACTIVE
            ])
            
            health_status = SystemHealthStatus(
                overall_status=overall_status,
                timestamp=datetime.now(timezone.utc),
                line_service_status=line_status,
                rich_message_service_status=rich_message_status,
                analytics_service_status=analytics_status,
                database_status=database_status,
                avg_response_time_ms=avg_response_time,
                memory_usage_mb=memory_usage_mb,
                active_campaigns=active_campaigns,
                pending_deliveries=0,  # Could implement delivery queue monitoring
                issues=issues,
                warnings=warnings
            )
            
            logger.info(f"System health check completed: {overall_status}")
            return health_status
            
        except Exception as e:
            logger.error(f"System health check failed: {str(e)}")
            return SystemHealthStatus(
                overall_status="critical",
                timestamp=datetime.now(timezone.utc),
                line_service_status="unknown",
                rich_message_service_status="unknown",
                analytics_service_status="unknown",
                database_status="unknown",
                avg_response_time_ms=0.0,
                active_campaigns=0,
                pending_deliveries=0,
                issues=[f"Health check failed: {str(e)}"],
                warnings=[]
            )
    
    def cleanup_old_data(self, days_to_keep: int = 30) -> Dict[str, Any]:
        """
        Clean up old data across all systems.
        
        Args:
            days_to_keep: Number of days of data to retain
            
        Returns:
            Cleanup results
        """
        try:
            results = {}
            
            # Cleanup analytics interactions
            analytics_removed = self.analytics_tracker.cleanup_old_interactions(days_to_keep)
            results["analytics_interactions_removed"] = analytics_removed
            
            # Cleanup interaction handler data
            interaction_removed = self.interaction_handler.cleanup_old_interactions(days_to_keep)
            results["interaction_records_removed"] = interaction_removed
            
            # Cleanup persistent storage
            storage_removed = self.metrics_storage.cleanup_old_metrics(days_to_keep)
            results["storage_metrics_removed"] = storage_removed
            
            # Cleanup old completed campaigns (optional)
            old_campaigns = [
                c for c in self.campaigns.values()
                if c.status == CampaignStatus.COMPLETED and
                c.updated_at < datetime.now(timezone.utc) - timedelta(days=days_to_keep)
            ]
            
            for campaign in old_campaigns:
                del self.campaigns[campaign.campaign_id]
            
            results["old_campaigns_removed"] = len(old_campaigns)
            
            logger.info(f"Cleanup completed: {results}")
            
            return {
                "success": True,
                "cleanup_results": results,
                "days_kept": days_to_keep,
                "cleanup_timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Cleanup failed: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }


# Global admin controller instance
_admin_controller = None

def get_admin_controller() -> AdminController:
    """Get global admin controller instance."""
    global _admin_controller
    if _admin_controller is None:
        _admin_controller = AdminController()
    return _admin_controller