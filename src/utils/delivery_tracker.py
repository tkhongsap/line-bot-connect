"""
Delivery Tracking and Error Handling for Rich Message automation.

This module provides comprehensive delivery tracking, retry logic, error handling,
and success rate monitoring for Rich Message deliveries.
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
import json

logger = logging.getLogger(__name__)


class DeliveryStatus(Enum):
    """Delivery status types"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRYING = "retrying"
    PERMANENTLY_FAILED = "permanently_failed"


class ErrorType(Enum):
    """Error classification types"""
    NETWORK_ERROR = "network_error"
    RATE_LIMIT = "rate_limit"
    INVALID_USER = "invalid_user"
    CONTENT_ERROR = "content_error"
    TEMPLATE_ERROR = "template_error"
    GENERATION_ERROR = "generation_error"
    PERMISSION_ERROR = "permission_error"
    TIMEOUT_ERROR = "timeout_error"
    SYSTEM_ERROR = "system_error"
    UNKNOWN_ERROR = "unknown_error"


@dataclass
class DeliveryAttempt:
    """Individual delivery attempt record"""
    attempt_id: str
    attempt_number: int
    timestamp: datetime
    status: DeliveryStatus
    error_type: Optional[ErrorType] = None
    error_message: Optional[str] = None
    response_time_ms: Optional[int] = None
    retry_after_seconds: Optional[int] = None


@dataclass
class DeliveryRecord:
    """Complete delivery record with tracking and retry history"""
    delivery_id: str
    user_id: str
    content_category: str
    timezone: str
    scheduled_time: datetime
    created_at: datetime
    status: DeliveryStatus
    
    # Delivery tracking
    attempts: List[DeliveryAttempt] = field(default_factory=list)
    total_attempts: int = 0
    last_attempt_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    
    # Error handling
    current_error_type: Optional[ErrorType] = None
    current_error_message: Optional[str] = None
    retry_count: int = 0
    next_retry_at: Optional[datetime] = None
    permanent_failure: bool = False
    
    # Content metadata
    template_id: Optional[str] = None
    image_path: Optional[str] = None
    content_title: Optional[str] = None
    
    # Performance tracking
    generation_time_ms: Optional[int] = None
    delivery_time_ms: Optional[int] = None
    total_processing_time_ms: Optional[int] = None


@dataclass
class RetryPolicy:
    """Retry policy configuration"""
    max_retries: int = 3
    initial_delay_seconds: int = 30
    max_delay_seconds: int = 3600  # 1 hour
    backoff_multiplier: float = 2.0
    exponential_backoff: bool = True
    
    # Error-specific retry settings
    retry_on_errors: List[ErrorType] = field(default_factory=lambda: [
        ErrorType.NETWORK_ERROR,
        ErrorType.RATE_LIMIT,
        ErrorType.TIMEOUT_ERROR,
        ErrorType.SYSTEM_ERROR
    ])
    
    no_retry_errors: List[ErrorType] = field(default_factory=lambda: [
        ErrorType.INVALID_USER,
        ErrorType.PERMISSION_ERROR,
        ErrorType.CONTENT_ERROR
    ])


@dataclass
class DeliveryStats:
    """Delivery statistics and metrics"""
    total_deliveries: int = 0
    successful_deliveries: int = 0
    failed_deliveries: int = 0
    pending_deliveries: int = 0
    retrying_deliveries: int = 0
    
    success_rate: float = 0.0
    average_delivery_time_ms: float = 0.0
    average_retry_count: float = 0.0
    
    # Error breakdown
    error_breakdown: Dict[str, int] = field(default_factory=dict)
    
    # Timezone breakdown
    timezone_stats: Dict[str, Dict[str, int]] = field(default_factory=dict)
    
    # Time-based metrics
    deliveries_last_hour: int = 0
    deliveries_last_24h: int = 0
    current_delivery_rate: float = 0.0


class DeliveryTracker:
    """
    Comprehensive delivery tracking and error handling system.
    
    Manages delivery records, retry logic, error classification,
    and success rate monitoring for Rich Message automation.
    """
    
    def __init__(self, retry_policy: Optional[RetryPolicy] = None):
        """
        Initialize the DeliveryTracker.
        
        Args:
            retry_policy: Optional custom retry policy
        """
        self.retry_policy = retry_policy or RetryPolicy()
        self.delivery_records: Dict[str, DeliveryRecord] = {}
        self.pending_retries: List[str] = []  # List of delivery IDs pending retry
        
        # Performance tracking
        self.start_time = datetime.now(timezone.utc)
        self.last_stats_calculation = datetime.now(timezone.utc)
        self.cached_stats: Optional[DeliveryStats] = None
        
        logger.info("DeliveryTracker initialized with retry policy", extra={
            'max_retries': self.retry_policy.max_retries,
            'initial_delay': self.retry_policy.initial_delay_seconds,
            'max_delay': self.retry_policy.max_delay_seconds
        })
    
    def create_delivery_record(self, user_id: str, content_category: str,
                             timezone_name: str, scheduled_time: datetime,
                             template_id: Optional[str] = None,
                             content_title: Optional[str] = None) -> DeliveryRecord:
        """
        Create a new delivery record.
        
        Args:
            user_id: User identifier
            content_category: Content category
            timezone_name: Target timezone
            scheduled_time: Scheduled delivery time
            template_id: Optional template identifier
            content_title: Optional content title
            
        Returns:
            New DeliveryRecord instance
        """
        delivery_id = f"delivery_{user_id}_{content_category}_{int(scheduled_time.timestamp())}"
        
        record = DeliveryRecord(
            delivery_id=delivery_id,
            user_id=user_id,
            content_category=content_category,
            timezone=timezone_name,
            scheduled_time=scheduled_time,
            created_at=datetime.now(timezone.utc),
            status=DeliveryStatus.PENDING,
            template_id=template_id,
            content_title=content_title
        )
        
        self.delivery_records[delivery_id] = record
        
        logger.debug(f"Created delivery record {delivery_id} for user {user_id[:8]}...")
        
        return record
    
    def start_delivery_attempt(self, delivery_id: str) -> Optional[str]:
        """
        Start a new delivery attempt.
        
        Args:
            delivery_id: Delivery record identifier
            
        Returns:
            Attempt ID if successful, None if delivery not found
        """
        if delivery_id not in self.delivery_records:
            logger.warning(f"Delivery record not found: {delivery_id}")
            return None
        
        record = self.delivery_records[delivery_id]
        
        # Check if delivery is eligible for attempt
        if record.permanent_failure:
            logger.warning(f"Delivery {delivery_id} marked as permanently failed")
            return None
        
        attempt_id = f"{delivery_id}_attempt_{record.total_attempts + 1}"
        
        attempt = DeliveryAttempt(
            attempt_id=attempt_id,
            attempt_number=record.total_attempts + 1,
            timestamp=datetime.now(timezone.utc),
            status=DeliveryStatus.IN_PROGRESS
        )
        
        record.attempts.append(attempt)
        record.total_attempts += 1
        record.last_attempt_at = attempt.timestamp
        record.status = DeliveryStatus.IN_PROGRESS
        
        logger.info(f"Started delivery attempt {attempt.attempt_number} for {delivery_id}")
        
        return attempt_id
    
    def record_delivery_success(self, delivery_id: str, attempt_id: str,
                              response_time_ms: int = 0) -> bool:
        """
        Record successful delivery.
        
        Args:
            delivery_id: Delivery record identifier
            attempt_id: Attempt identifier
            response_time_ms: Response time in milliseconds
            
        Returns:
            True if recorded successfully
        """
        if delivery_id not in self.delivery_records:
            return False
        
        record = self.delivery_records[delivery_id]
        
        # Find and update the attempt
        attempt = self._find_attempt(record, attempt_id)
        if not attempt:
            return False
        
        attempt.status = DeliveryStatus.DELIVERED
        attempt.response_time_ms = response_time_ms
        
        # Update delivery record
        record.status = DeliveryStatus.DELIVERED
        record.delivered_at = datetime.now(timezone.utc)
        record.delivery_time_ms = response_time_ms
        
        # Calculate total processing time
        if record.created_at and record.delivered_at:
            total_time = (record.delivered_at - record.created_at).total_seconds() * 1000
            record.total_processing_time_ms = int(total_time)
        
        # Remove from pending retries if present
        if delivery_id in self.pending_retries:
            self.pending_retries.remove(delivery_id)
        
        logger.info(f"Delivery {delivery_id} completed successfully in {response_time_ms}ms")
        
        return True
    
    def record_delivery_failure(self, delivery_id: str, attempt_id: str,
                              error_message: str, error_type: Optional[ErrorType] = None,
                              response_time_ms: int = 0) -> bool:
        """
        Record delivery failure and determine retry strategy.
        
        Args:
            delivery_id: Delivery record identifier
            attempt_id: Attempt identifier
            error_message: Error description
            error_type: Classification of error
            response_time_ms: Response time in milliseconds
            
        Returns:
            True if recorded successfully
        """
        if delivery_id not in self.delivery_records:
            return False
        
        record = self.delivery_records[delivery_id]
        
        # Find and update the attempt
        attempt = self._find_attempt(record, attempt_id)
        if not attempt:
            return False
        
        # Classify error if not provided
        if error_type is None:
            error_type = self._classify_error(error_message)
        
        attempt.status = DeliveryStatus.FAILED
        attempt.error_type = error_type
        attempt.error_message = error_message
        attempt.response_time_ms = response_time_ms
        
        # Update delivery record
        record.current_error_type = error_type
        record.current_error_message = error_message
        record.retry_count += 1
        
        # Determine if retry is possible
        should_retry = self._should_retry(record, error_type)
        
        if should_retry:
            # Schedule retry
            retry_delay = self._calculate_retry_delay(record.retry_count)
            record.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=retry_delay)
            record.status = DeliveryStatus.RETRYING
            
            # Add to pending retries
            if delivery_id not in self.pending_retries:
                self.pending_retries.append(delivery_id)
            
            attempt.retry_after_seconds = retry_delay
            
            logger.warning(f"Delivery {delivery_id} failed (attempt {record.retry_count}): {error_message}. "
                          f"Retry scheduled in {retry_delay}s")
        else:
            # Mark as permanently failed
            record.status = DeliveryStatus.PERMANENTLY_FAILED
            record.permanent_failure = True
            
            # Remove from pending retries
            if delivery_id in self.pending_retries:
                self.pending_retries.remove(delivery_id)
            
            logger.error(f"Delivery {delivery_id} permanently failed after {record.retry_count} attempts: {error_message}")
        
        return True
    
    def _find_attempt(self, record: DeliveryRecord, attempt_id: str) -> Optional[DeliveryAttempt]:
        """Find delivery attempt by ID."""
        return next((a for a in record.attempts if a.attempt_id == attempt_id), None)
    
    def _classify_error(self, error_message: str) -> ErrorType:
        """Classify error based on error message."""
        error_lower = error_message.lower()
        
        # Network-related errors
        if any(term in error_lower for term in ['connection', 'network', 'dns', 'socket']):
            return ErrorType.NETWORK_ERROR
        
        # Rate limiting
        if any(term in error_lower for term in ['rate limit', 'too many requests', '429']):
            return ErrorType.RATE_LIMIT
        
        # Invalid user/permission errors
        if any(term in error_lower for term in ['invalid user', 'user not found', 'forbidden', '403', '404']):
            return ErrorType.INVALID_USER
        
        # Permission errors
        if any(term in error_lower for term in ['permission', 'unauthorized', '401']):
            return ErrorType.PERMISSION_ERROR
        
        # Timeout errors
        if any(term in error_lower for term in ['timeout', 'timed out']):
            return ErrorType.TIMEOUT_ERROR
        
        # Content/template errors
        if any(term in error_lower for term in ['template', 'content', 'image', 'invalid format']):
            return ErrorType.CONTENT_ERROR
        
        # System errors
        if any(term in error_lower for term in ['system error', 'internal error', '500', '502', '503']):
            return ErrorType.SYSTEM_ERROR
        
        return ErrorType.UNKNOWN_ERROR
    
    def _should_retry(self, record: DeliveryRecord, error_type: ErrorType) -> bool:
        """Determine if delivery should be retried."""
        # Check if already exceeded max retries
        if record.retry_count >= self.retry_policy.max_retries:
            return False
        
        # Check if error type is retryable
        if error_type in self.retry_policy.no_retry_errors:
            return False
        
        # Check if error type is in retry list
        if error_type not in self.retry_policy.retry_on_errors:
            return False
        
        return True
    
    def _calculate_retry_delay(self, retry_count: int) -> int:
        """Calculate retry delay based on retry count and policy."""
        if self.retry_policy.exponential_backoff:
            delay = self.retry_policy.initial_delay_seconds * (self.retry_policy.backoff_multiplier ** (retry_count - 1))
        else:
            delay = self.retry_policy.initial_delay_seconds
        
        # Cap at maximum delay
        delay = min(delay, self.retry_policy.max_delay_seconds)
        
        return int(delay)
    
    def get_pending_retries(self, check_time: Optional[datetime] = None) -> List[str]:
        """
        Get delivery IDs that are ready for retry.
        
        Args:
            check_time: Time to check against (defaults to now)
            
        Returns:
            List of delivery IDs ready for retry
        """
        if check_time is None:
            check_time = datetime.now(timezone.utc)
        
        ready_retries = []
        
        for delivery_id in self.pending_retries:
            if delivery_id not in self.delivery_records:
                continue
            
            record = self.delivery_records[delivery_id]
            
            # Check if retry time has arrived
            if record.next_retry_at and record.next_retry_at <= check_time:
                ready_retries.append(delivery_id)
        
        return ready_retries
    
    def get_delivery_record(self, delivery_id: str) -> Optional[DeliveryRecord]:
        """Get delivery record by ID."""
        return self.delivery_records.get(delivery_id)
    
    def get_user_deliveries(self, user_id: str, 
                          status_filter: Optional[DeliveryStatus] = None) -> List[DeliveryRecord]:
        """
        Get delivery records for a specific user.
        
        Args:
            user_id: User identifier
            status_filter: Optional status filter
            
        Returns:
            List of delivery records for the user
        """
        user_deliveries = [
            record for record in self.delivery_records.values()
            if record.user_id == user_id
        ]
        
        if status_filter:
            user_deliveries = [
                record for record in user_deliveries
                if record.status == status_filter
            ]
        
        return user_deliveries
    
    def calculate_delivery_stats(self, force_recalculate: bool = False) -> DeliveryStats:
        """
        Calculate comprehensive delivery statistics.
        
        Args:
            force_recalculate: Force recalculation even if cached
            
        Returns:
            DeliveryStats object with current statistics
        """
        now = datetime.now(timezone.utc)
        
        # Use cached stats if recent (within 5 minutes) and not forced
        if (not force_recalculate and 
            self.cached_stats and 
            (now - self.last_stats_calculation).total_seconds() < 300):
            return self.cached_stats
        
        stats = DeliveryStats()
        
        # Count deliveries by status
        status_counts = {}
        error_counts = {}
        timezone_counts = {}
        
        total_delivery_time = 0
        successful_with_time = 0
        total_retries = 0
        
        # Time-based counters
        hour_ago = now - timedelta(hours=1)
        day_ago = now - timedelta(hours=24)
        deliveries_last_hour = 0
        deliveries_last_24h = 0
        
        for record in self.delivery_records.values():
            stats.total_deliveries += 1
            
            # Status counting
            status = record.status.value
            status_counts[status] = status_counts.get(status, 0) + 1
            
            # Error breakdown
            if record.current_error_type:
                error_type = record.current_error_type.value
                error_counts[error_type] = error_counts.get(error_type, 0) + 1
            
            # Timezone breakdown
            tz = record.timezone
            if tz not in timezone_counts:
                timezone_counts[tz] = {'total': 0, 'successful': 0, 'failed': 0}
            timezone_counts[tz]['total'] += 1
            
            if record.status == DeliveryStatus.DELIVERED:
                timezone_counts[tz]['successful'] += 1
                
                # Performance metrics
                if record.delivery_time_ms:
                    total_delivery_time += record.delivery_time_ms
                    successful_with_time += 1
            elif record.status == DeliveryStatus.PERMANENTLY_FAILED:
                timezone_counts[tz]['failed'] += 1
            
            # Retry counting
            total_retries += record.retry_count
            
            # Time-based metrics
            if record.created_at:
                if record.created_at >= hour_ago:
                    deliveries_last_hour += 1
                if record.created_at >= day_ago:
                    deliveries_last_24h += 1
        
        # Set status counts
        stats.successful_deliveries = status_counts.get('delivered', 0)
        stats.failed_deliveries = status_counts.get('permanently_failed', 0)
        stats.pending_deliveries = status_counts.get('pending', 0)
        stats.retrying_deliveries = status_counts.get('retrying', 0)
        
        # Calculate rates and averages
        if stats.total_deliveries > 0:
            stats.success_rate = stats.successful_deliveries / stats.total_deliveries
            stats.average_retry_count = total_retries / stats.total_deliveries
        
        if successful_with_time > 0:
            stats.average_delivery_time_ms = total_delivery_time / successful_with_time
        
        # Set breakdowns
        stats.error_breakdown = error_counts
        stats.timezone_stats = timezone_counts
        
        # Time-based metrics
        stats.deliveries_last_hour = deliveries_last_hour
        stats.deliveries_last_24h = deliveries_last_24h
        
        # Calculate current delivery rate (deliveries per hour)
        uptime_hours = (now - self.start_time).total_seconds() / 3600
        if uptime_hours > 0:
            stats.current_delivery_rate = stats.total_deliveries / uptime_hours
        
        # Cache the results
        self.cached_stats = stats
        self.last_stats_calculation = now
        
        logger.debug(f"Calculated delivery stats: {stats.total_deliveries} total, "
                    f"{stats.success_rate:.2%} success rate")
        
        return stats
    
    def cleanup_old_records(self, days_to_keep: int = 7) -> int:
        """
        Clean up old delivery records.
        
        Args:
            days_to_keep: Keep records newer than this many days
            
        Returns:
            Number of records removed
        """
        cutoff_time = datetime.now(timezone.utc) - timedelta(days=days_to_keep)
        
        # Find records to remove (only remove completed deliveries)
        to_remove = []
        for delivery_id, record in self.delivery_records.items():
            if (record.created_at < cutoff_time and 
                record.status in [DeliveryStatus.DELIVERED, DeliveryStatus.PERMANENTLY_FAILED]):
                to_remove.append(delivery_id)
        
        # Remove records
        for delivery_id in to_remove:
            del self.delivery_records[delivery_id]
            
            # Also remove from pending retries
            if delivery_id in self.pending_retries:
                self.pending_retries.remove(delivery_id)
        
        if to_remove:
            logger.info(f"Cleaned up {len(to_remove)} old delivery records")
            # Force stats recalculation
            self.cached_stats = None
        
        return len(to_remove)
    
    def get_delivery_health_status(self) -> Dict[str, Any]:
        """
        Get overall delivery system health status.
        
        Returns:
            Dictionary with health metrics
        """
        stats = self.calculate_delivery_stats()
        
        # Determine health status
        health_status = "healthy"
        issues = []
        
        # Check success rate
        if stats.success_rate < 0.5:
            health_status = "critical"
            issues.append(f"Low success rate: {stats.success_rate:.1%}")
        elif stats.success_rate < 0.8:
            health_status = "warning"
            issues.append(f"Moderate success rate: {stats.success_rate:.1%}")
        
        # Check pending retries
        pending_retries = len(self.pending_retries)
        if pending_retries > 100:
            health_status = "critical"
            issues.append(f"High pending retries: {pending_retries}")
        elif pending_retries > 50:
            if health_status == "healthy":
                health_status = "warning"
            issues.append(f"Elevated pending retries: {pending_retries}")
        
        # Check average delivery time
        if stats.average_delivery_time_ms > 10000:  # 10 seconds
            if health_status == "healthy":
                health_status = "warning"
            issues.append(f"Slow delivery times: {stats.average_delivery_time_ms:.0f}ms")
        
        return {
            "status": health_status,
            "issues": issues,
            "total_deliveries": stats.total_deliveries,
            "success_rate": stats.success_rate,
            "pending_retries": pending_retries,
            "average_delivery_time_ms": stats.average_delivery_time_ms,
            "deliveries_last_hour": stats.deliveries_last_hour,
            "uptime_hours": (datetime.now(timezone.utc) - self.start_time).total_seconds() / 3600
        }


# Global delivery tracker instance
_delivery_tracker = None

def get_delivery_tracker() -> DeliveryTracker:
    """Get global delivery tracker instance."""
    global _delivery_tracker
    if _delivery_tracker is None:
        _delivery_tracker = DeliveryTracker()
    return _delivery_tracker