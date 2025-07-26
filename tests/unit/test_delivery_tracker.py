"""
Unit tests for DeliveryTracker
"""

import pytest
from unittest.mock import patch, Mock
from datetime import datetime, timedelta, timezone

from src.utils.delivery_tracker import (
    DeliveryTracker, DeliveryRecord, DeliveryAttempt, RetryPolicy,
    DeliveryStats, DeliveryStatus, ErrorType, get_delivery_tracker
)


class TestDeliveryTracker:
    """Test cases for DeliveryTracker"""
    
    @pytest.fixture
    def delivery_tracker(self):
        """Create a DeliveryTracker instance"""
        return DeliveryTracker()
    
    @pytest.fixture
    def custom_retry_policy(self):
        """Create a custom retry policy for testing"""
        return RetryPolicy(
            max_retries=2,
            initial_delay_seconds=10,
            max_delay_seconds=300,
            backoff_multiplier=1.5,
            exponential_backoff=True
        )
    
    @pytest.fixture
    def sample_delivery_record(self, delivery_tracker):
        """Create a sample delivery record"""
        return delivery_tracker.create_delivery_record(
            user_id="test_user_123",
            content_category="motivation",
            timezone_name="Asia/Bangkok",
            scheduled_time=datetime.now(timezone.utc),
            template_id="template_001",
            content_title="Daily Motivation"
        )
    
    def test_initialization_default_policy(self, delivery_tracker):
        """Test DeliveryTracker initialization with default retry policy"""
        assert isinstance(delivery_tracker.retry_policy, RetryPolicy)
        assert delivery_tracker.retry_policy.max_retries == 3
        assert delivery_tracker.retry_policy.initial_delay_seconds == 30
        assert isinstance(delivery_tracker.delivery_records, dict)
        assert isinstance(delivery_tracker.pending_retries, list)
        assert len(delivery_tracker.delivery_records) == 0
        assert len(delivery_tracker.pending_retries) == 0
    
    def test_initialization_custom_policy(self, custom_retry_policy):
        """Test DeliveryTracker initialization with custom retry policy"""
        tracker = DeliveryTracker(retry_policy=custom_retry_policy)
        assert tracker.retry_policy == custom_retry_policy
        assert tracker.retry_policy.max_retries == 2
        assert tracker.retry_policy.initial_delay_seconds == 10
    
    def test_create_delivery_record(self, delivery_tracker):
        """Test creating a delivery record"""
        scheduled_time = datetime.now(timezone.utc)
        
        record = delivery_tracker.create_delivery_record(
            user_id="user_456",
            content_category="wellness",
            timezone_name="Europe/London",
            scheduled_time=scheduled_time,
            template_id="template_002",
            content_title="Wellness Tips"
        )
        
        assert isinstance(record, DeliveryRecord)
        assert record.user_id == "user_456"
        assert record.content_category == "wellness"
        assert record.timezone == "Europe/London"
        assert record.scheduled_time == scheduled_time
        assert record.template_id == "template_002"
        assert record.content_title == "Wellness Tips"
        assert record.status == DeliveryStatus.PENDING
        assert record.total_attempts == 0
        assert record.retry_count == 0
        assert not record.permanent_failure
        
        # Check that record is stored
        assert record.delivery_id in delivery_tracker.delivery_records
        assert delivery_tracker.delivery_records[record.delivery_id] == record
    
    def test_start_delivery_attempt_success(self, delivery_tracker, sample_delivery_record):
        """Test starting a delivery attempt successfully"""
        delivery_id = sample_delivery_record.delivery_id
        
        attempt_id = delivery_tracker.start_delivery_attempt(delivery_id)
        
        assert attempt_id is not None
        assert attempt_id.startswith(f"{delivery_id}_attempt_")
        
        # Check record state
        record = delivery_tracker.delivery_records[delivery_id]
        assert record.total_attempts == 1
        assert record.status == DeliveryStatus.IN_PROGRESS
        assert record.last_attempt_at is not None
        assert len(record.attempts) == 1
        
        # Check attempt
        attempt = record.attempts[0]
        assert attempt.attempt_id == attempt_id
        assert attempt.attempt_number == 1
        assert attempt.status == DeliveryStatus.IN_PROGRESS
    
    def test_start_delivery_attempt_nonexistent(self, delivery_tracker):
        """Test starting delivery attempt for nonexistent record"""
        attempt_id = delivery_tracker.start_delivery_attempt("nonexistent_id")
        assert attempt_id is None
    
    def test_start_delivery_attempt_permanently_failed(self, delivery_tracker, sample_delivery_record):
        """Test starting delivery attempt for permanently failed record"""
        delivery_id = sample_delivery_record.delivery_id
        
        # Mark as permanently failed
        record = delivery_tracker.delivery_records[delivery_id]
        record.permanent_failure = True
        
        attempt_id = delivery_tracker.start_delivery_attempt(delivery_id)
        assert attempt_id is None
    
    def test_record_delivery_success(self, delivery_tracker, sample_delivery_record):
        """Test recording successful delivery"""
        delivery_id = sample_delivery_record.delivery_id
        attempt_id = delivery_tracker.start_delivery_attempt(delivery_id)
        
        success = delivery_tracker.record_delivery_success(
            delivery_id, attempt_id, response_time_ms=1500
        )
        
        assert success is True
        
        # Check record state
        record = delivery_tracker.delivery_records[delivery_id]
        assert record.status == DeliveryStatus.DELIVERED
        assert record.delivered_at is not None
        assert record.delivery_time_ms == 1500
        assert record.total_processing_time_ms is not None
        
        # Check attempt
        attempt = record.attempts[0]
        assert attempt.status == DeliveryStatus.DELIVERED
        assert attempt.response_time_ms == 1500
        
        # Should not be in pending retries
        assert delivery_id not in delivery_tracker.pending_retries
    
    def test_record_delivery_success_nonexistent(self, delivery_tracker):
        """Test recording success for nonexistent delivery"""
        success = delivery_tracker.record_delivery_success(
            "nonexistent_id", "nonexistent_attempt", 1000
        )
        assert success is False
    
    def test_record_delivery_failure_retryable(self, delivery_tracker, sample_delivery_record):
        """Test recording delivery failure with retry"""
        delivery_id = sample_delivery_record.delivery_id
        attempt_id = delivery_tracker.start_delivery_attempt(delivery_id)
        
        success = delivery_tracker.record_delivery_failure(
            delivery_id, attempt_id, "Network timeout", ErrorType.TIMEOUT_ERROR, 5000
        )
        
        assert success is True
        
        # Check record state
        record = delivery_tracker.delivery_records[delivery_id]
        assert record.status == DeliveryStatus.RETRYING
        assert record.current_error_type == ErrorType.TIMEOUT_ERROR
        assert record.current_error_message == "Network timeout"
        assert record.retry_count == 1
        assert record.next_retry_at is not None
        assert not record.permanent_failure
        
        # Check attempt
        attempt = record.attempts[0]
        assert attempt.status == DeliveryStatus.FAILED
        assert attempt.error_type == ErrorType.TIMEOUT_ERROR
        assert attempt.error_message == "Network timeout"
        assert attempt.response_time_ms == 5000
        assert attempt.retry_after_seconds is not None
        
        # Should be in pending retries
        assert delivery_id in delivery_tracker.pending_retries
    
    def test_record_delivery_failure_non_retryable(self, delivery_tracker, sample_delivery_record):
        """Test recording delivery failure with no retry"""
        delivery_id = sample_delivery_record.delivery_id
        attempt_id = delivery_tracker.start_delivery_attempt(delivery_id)
        
        success = delivery_tracker.record_delivery_failure(
            delivery_id, attempt_id, "User not found", ErrorType.INVALID_USER, 200
        )
        
        assert success is True
        
        # Check record state
        record = delivery_tracker.delivery_records[delivery_id]
        assert record.status == DeliveryStatus.PERMANENTLY_FAILED
        assert record.permanent_failure is True
        
        # Should not be in pending retries
        assert delivery_id not in delivery_tracker.pending_retries
    
    def test_record_delivery_failure_max_retries_exceeded(self, delivery_tracker, sample_delivery_record):
        """Test recording failure when max retries exceeded"""
        delivery_id = sample_delivery_record.delivery_id
        record = delivery_tracker.delivery_records[delivery_id]
        
        # Simulate max retries exceeded
        record.retry_count = delivery_tracker.retry_policy.max_retries
        
        attempt_id = delivery_tracker.start_delivery_attempt(delivery_id)
        success = delivery_tracker.record_delivery_failure(
            delivery_id, attempt_id, "Network error", ErrorType.NETWORK_ERROR, 3000
        )
        
        assert success is True
        
        # Should be permanently failed
        record = delivery_tracker.delivery_records[delivery_id]
        assert record.status == DeliveryStatus.PERMANENTLY_FAILED
        assert record.permanent_failure is True
        assert delivery_id not in delivery_tracker.pending_retries
    
    def test_classify_error_network(self, delivery_tracker):
        """Test error classification for network errors"""
        error_type = delivery_tracker._classify_error("Connection timeout occurred")
        assert error_type == ErrorType.NETWORK_ERROR
        
        error_type = delivery_tracker._classify_error("DNS resolution failed")
        assert error_type == ErrorType.NETWORK_ERROR
    
    def test_classify_error_rate_limit(self, delivery_tracker):
        """Test error classification for rate limiting"""
        error_type = delivery_tracker._classify_error("Rate limit exceeded")
        assert error_type == ErrorType.RATE_LIMIT
        
        error_type = delivery_tracker._classify_error("HTTP 429 Too Many Requests")
        assert error_type == ErrorType.RATE_LIMIT
    
    def test_classify_error_invalid_user(self, delivery_tracker):
        """Test error classification for invalid user"""
        error_type = delivery_tracker._classify_error("User not found")
        assert error_type == ErrorType.INVALID_USER
        
        error_type = delivery_tracker._classify_error("HTTP 404 Not Found")
        assert error_type == ErrorType.INVALID_USER
    
    def test_classify_error_timeout(self, delivery_tracker):
        """Test error classification for timeout"""
        error_type = delivery_tracker._classify_error("Request timed out")
        assert error_type == ErrorType.TIMEOUT_ERROR
        
        error_type = delivery_tracker._classify_error("Connection timeout")
        assert error_type == ErrorType.TIMEOUT_ERROR
    
    def test_classify_error_unknown(self, delivery_tracker):
        """Test error classification for unknown errors"""
        error_type = delivery_tracker._classify_error("Some random error message")
        assert error_type == ErrorType.UNKNOWN_ERROR
    
    def test_should_retry_retryable_error(self, delivery_tracker, sample_delivery_record):
        """Test retry decision for retryable error"""
        record = delivery_tracker.delivery_records[sample_delivery_record.delivery_id]
        record.retry_count = 1  # Below max retries
        
        should_retry = delivery_tracker._should_retry(record, ErrorType.NETWORK_ERROR)
        assert should_retry is True
    
    def test_should_retry_non_retryable_error(self, delivery_tracker, sample_delivery_record):
        """Test retry decision for non-retryable error"""
        record = delivery_tracker.delivery_records[sample_delivery_record.delivery_id]
        record.retry_count = 1
        
        should_retry = delivery_tracker._should_retry(record, ErrorType.INVALID_USER)
        assert should_retry is False
    
    def test_should_retry_max_retries_exceeded(self, delivery_tracker, sample_delivery_record):
        """Test retry decision when max retries exceeded"""
        record = delivery_tracker.delivery_records[sample_delivery_record.delivery_id]
        record.retry_count = delivery_tracker.retry_policy.max_retries + 1
        
        should_retry = delivery_tracker._should_retry(record, ErrorType.NETWORK_ERROR)
        assert should_retry is False
    
    def test_calculate_retry_delay_exponential(self, delivery_tracker):
        """Test retry delay calculation with exponential backoff"""
        # First retry
        delay = delivery_tracker._calculate_retry_delay(1)
        assert delay == 30  # initial_delay_seconds
        
        # Second retry
        delay = delivery_tracker._calculate_retry_delay(2)
        assert delay == 60  # 30 * 2.0
        
        # Third retry
        delay = delivery_tracker._calculate_retry_delay(3)
        assert delay == 120  # 30 * 2.0^2
    
    def test_calculate_retry_delay_max_cap(self, delivery_tracker):
        """Test retry delay calculation with max cap"""
        # Very high retry count should be capped
        delay = delivery_tracker._calculate_retry_delay(10)
        assert delay == delivery_tracker.retry_policy.max_delay_seconds
    
    def test_calculate_retry_delay_linear(self):
        """Test retry delay calculation with linear backoff"""
        policy = RetryPolicy(
            initial_delay_seconds=20,
            exponential_backoff=False
        )
        tracker = DeliveryTracker(retry_policy=policy)
        
        # All retries should have same delay
        delay1 = tracker._calculate_retry_delay(1)
        delay2 = tracker._calculate_retry_delay(2)
        delay3 = tracker._calculate_retry_delay(3)
        
        assert delay1 == delay2 == delay3 == 20
    
    def test_get_pending_retries_empty(self, delivery_tracker):
        """Test getting pending retries when none are ready"""
        ready_retries = delivery_tracker.get_pending_retries()
        assert ready_retries == []
    
    def test_get_pending_retries_with_ready(self, delivery_tracker, sample_delivery_record):
        """Test getting pending retries with ready deliveries"""
        delivery_id = sample_delivery_record.delivery_id
        attempt_id = delivery_tracker.start_delivery_attempt(delivery_id)
        
        # Record failure to trigger retry
        delivery_tracker.record_delivery_failure(
            delivery_id, attempt_id, "Network error", ErrorType.NETWORK_ERROR
        )
        
        # Set next_retry_at to past time to make it ready
        record = delivery_tracker.delivery_records[delivery_id]
        record.next_retry_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        
        ready_retries = delivery_tracker.get_pending_retries()
        assert delivery_id in ready_retries
    
    def test_get_pending_retries_not_ready(self, delivery_tracker, sample_delivery_record):
        """Test getting pending retries with not-ready deliveries"""
        delivery_id = sample_delivery_record.delivery_id
        attempt_id = delivery_tracker.start_delivery_attempt(delivery_id)
        
        # Record failure to trigger retry
        delivery_tracker.record_delivery_failure(
            delivery_id, attempt_id, "Network error", ErrorType.NETWORK_ERROR
        )
        
        # next_retry_at should be in future by default
        ready_retries = delivery_tracker.get_pending_retries()
        assert delivery_id not in ready_retries
    
    def test_get_delivery_record_exists(self, delivery_tracker, sample_delivery_record):
        """Test getting existing delivery record"""
        delivery_id = sample_delivery_record.delivery_id
        record = delivery_tracker.get_delivery_record(delivery_id)
        
        assert record is not None
        assert record == sample_delivery_record
    
    def test_get_delivery_record_not_exists(self, delivery_tracker):
        """Test getting non-existent delivery record"""
        record = delivery_tracker.get_delivery_record("nonexistent_id")
        assert record is None
    
    def test_get_user_deliveries(self, delivery_tracker):
        """Test getting deliveries for specific user"""
        # Create multiple delivery records
        user_id = "test_user"
        scheduled_time = datetime.now(timezone.utc)
        
        record1 = delivery_tracker.create_delivery_record(
            user_id, "motivation", "Asia/Bangkok", scheduled_time
        )
        record2 = delivery_tracker.create_delivery_record(
            user_id, "wellness", "Asia/Bangkok", scheduled_time
        )
        record3 = delivery_tracker.create_delivery_record(
            "other_user", "motivation", "Asia/Bangkok", scheduled_time
        )
        
        # Get deliveries for test_user
        user_deliveries = delivery_tracker.get_user_deliveries(user_id)
        
        assert len(user_deliveries) == 2
        assert record1 in user_deliveries
        assert record2 in user_deliveries
        assert record3 not in user_deliveries
    
    def test_get_user_deliveries_with_status_filter(self, delivery_tracker):
        """Test getting user deliveries with status filter"""
        user_id = "test_user"
        scheduled_time = datetime.now(timezone.utc)
        
        record1 = delivery_tracker.create_delivery_record(
            user_id, "motivation", "Asia/Bangkok", scheduled_time
        )
        record2 = delivery_tracker.create_delivery_record(
            user_id, "wellness", "Asia/Bangkok", scheduled_time
        )
        
        # Change status of one record
        record2.status = DeliveryStatus.DELIVERED
        
        # Filter by status
        pending_deliveries = delivery_tracker.get_user_deliveries(
            user_id, DeliveryStatus.PENDING
        )
        delivered_deliveries = delivery_tracker.get_user_deliveries(
            user_id, DeliveryStatus.DELIVERED
        )
        
        assert len(pending_deliveries) == 1
        assert record1 in pending_deliveries
        
        assert len(delivered_deliveries) == 1
        assert record2 in delivered_deliveries
    
    def test_calculate_delivery_stats_empty(self, delivery_tracker):
        """Test calculating delivery stats with no data"""
        stats = delivery_tracker.calculate_delivery_stats()
        
        assert isinstance(stats, DeliveryStats)
        assert stats.total_deliveries == 0
        assert stats.successful_deliveries == 0
        assert stats.failed_deliveries == 0
        assert stats.success_rate == 0.0
        assert stats.average_delivery_time_ms == 0.0
    
    def test_calculate_delivery_stats_with_data(self, delivery_tracker):
        """Test calculating delivery stats with sample data"""
        # Create some delivery records
        user_id = "test_user"
        scheduled_time = datetime.now(timezone.utc)
        
        # Successful delivery
        record1 = delivery_tracker.create_delivery_record(
            user_id, "motivation", "Asia/Bangkok", scheduled_time
        )
        attempt1 = delivery_tracker.start_delivery_attempt(record1.delivery_id)
        delivery_tracker.record_delivery_success(record1.delivery_id, attempt1, 1000)
        
        # Failed delivery
        record2 = delivery_tracker.create_delivery_record(
            user_id, "wellness", "Asia/Bangkok", scheduled_time
        )
        attempt2 = delivery_tracker.start_delivery_attempt(record2.delivery_id)
        delivery_tracker.record_delivery_failure(
            record2.delivery_id, attempt2, "User not found", ErrorType.INVALID_USER
        )
        
        # Pending delivery
        record3 = delivery_tracker.create_delivery_record(
            user_id, "productivity", "Asia/Bangkok", scheduled_time
        )
        
        stats = delivery_tracker.calculate_delivery_stats()
        
        assert stats.total_deliveries == 3
        assert stats.successful_deliveries == 1
        assert stats.failed_deliveries == 1
        assert stats.pending_deliveries == 1
        assert stats.success_rate == 1/3
        assert stats.average_delivery_time_ms == 1000.0
    
    def test_cleanup_old_records(self, delivery_tracker):
        """Test cleaning up old delivery records"""
        # Create old and new records
        old_time = datetime.now(timezone.utc) - timedelta(days=10)
        new_time = datetime.now(timezone.utc)
        
        # Old completed record (should be removed)
        old_record = delivery_tracker.create_delivery_record(
            "user1", "motivation", "Asia/Bangkok", old_time
        )
        old_record.created_at = old_time
        old_record.status = DeliveryStatus.DELIVERED
        
        # New record (should be kept)
        new_record = delivery_tracker.create_delivery_record(
            "user2", "wellness", "Asia/Bangkok", new_time
        )
        
        # Old pending record (should be kept even if old)
        old_pending_record = delivery_tracker.create_delivery_record(
            "user3", "productivity", "Asia/Bangkok", old_time
        )
        old_pending_record.created_at = old_time
        old_pending_record.status = DeliveryStatus.PENDING
        
        initial_count = len(delivery_tracker.delivery_records)
        removed_count = delivery_tracker.cleanup_old_records(days_to_keep=7)
        
        assert removed_count == 1
        assert len(delivery_tracker.delivery_records) == initial_count - 1
        assert old_record.delivery_id not in delivery_tracker.delivery_records
        assert new_record.delivery_id in delivery_tracker.delivery_records
        assert old_pending_record.delivery_id in delivery_tracker.delivery_records
    
    def test_get_delivery_health_status_healthy(self, delivery_tracker):
        """Test getting health status when system is healthy"""
        # Create some successful deliveries
        user_id = "test_user"
        scheduled_time = datetime.now(timezone.utc)
        
        for i in range(10):
            record = delivery_tracker.create_delivery_record(
                f"{user_id}_{i}", "motivation", "Asia/Bangkok", scheduled_time
            )
            attempt = delivery_tracker.start_delivery_attempt(record.delivery_id)
            delivery_tracker.record_delivery_success(record.delivery_id, attempt, 1000)
        
        health = delivery_tracker.get_delivery_health_status()
        
        assert health['status'] == 'healthy'
        assert health['total_deliveries'] == 10
        assert health['success_rate'] == 1.0
        assert health['pending_retries'] == 0
        assert len(health['issues']) == 0
    
    def test_get_delivery_health_status_warning(self, delivery_tracker):
        """Test getting health status with warning conditions"""
        user_id = "test_user"
        scheduled_time = datetime.now(timezone.utc)
        
        # Create deliveries with low success rate
        for i in range(10):
            record = delivery_tracker.create_delivery_record(
                f"{user_id}_{i}", "motivation", "Asia/Bangkok", scheduled_time
            )
            attempt = delivery_tracker.start_delivery_attempt(record.delivery_id)
            
            if i < 6:  # 60% success rate
                delivery_tracker.record_delivery_success(record.delivery_id, attempt, 1000)
            else:
                delivery_tracker.record_delivery_failure(
                    record.delivery_id, attempt, "Network error", ErrorType.NETWORK_ERROR
                )
        
        health = delivery_tracker.get_delivery_health_status()
        
        assert health['status'] == 'warning'
        assert 0.5 <= health['success_rate'] < 0.8
        assert len(health['issues']) > 0
    
    def test_get_delivery_health_status_critical(self, delivery_tracker):
        """Test getting health status with critical conditions"""
        user_id = "test_user"
        scheduled_time = datetime.now(timezone.utc)
        
        # Create deliveries with very low success rate
        for i in range(10):
            record = delivery_tracker.create_delivery_record(
                f"{user_id}_{i}", "motivation", "Asia/Bangkok", scheduled_time
            )
            attempt = delivery_tracker.start_delivery_attempt(record.delivery_id)
            
            if i < 3:  # 30% success rate
                delivery_tracker.record_delivery_success(record.delivery_id, attempt, 1000)
            else:
                delivery_tracker.record_delivery_failure(
                    record.delivery_id, attempt, "Network error", ErrorType.NETWORK_ERROR
                )
        
        health = delivery_tracker.get_delivery_health_status()
        
        assert health['status'] == 'critical'
        assert health['success_rate'] < 0.5
        assert len(health['issues']) > 0
    
    def test_delivery_record_creation(self):
        """Test DeliveryRecord dataclass creation"""
        scheduled_time = datetime.now(timezone.utc)
        created_time = datetime.now(timezone.utc)
        
        record = DeliveryRecord(
            delivery_id="test_delivery_123",
            user_id="user_456",
            content_category="motivation",
            timezone="Asia/Bangkok",
            scheduled_time=scheduled_time,
            created_at=created_time,
            status=DeliveryStatus.PENDING,
            template_id="template_001",
            content_title="Test Content"
        )
        
        assert record.delivery_id == "test_delivery_123"
        assert record.user_id == "user_456"
        assert record.content_category == "motivation"
        assert record.timezone == "Asia/Bangkok"
        assert record.scheduled_time == scheduled_time
        assert record.created_at == created_time
        assert record.status == DeliveryStatus.PENDING
        assert record.template_id == "template_001"
        assert record.content_title == "Test Content"
        assert record.total_attempts == 0
        assert record.retry_count == 0
        assert not record.permanent_failure
        assert len(record.attempts) == 0
    
    def test_delivery_attempt_creation(self):
        """Test DeliveryAttempt dataclass creation"""
        timestamp = datetime.now(timezone.utc)
        
        attempt = DeliveryAttempt(
            attempt_id="attempt_001",
            attempt_number=1,
            timestamp=timestamp,
            status=DeliveryStatus.IN_PROGRESS,
            error_type=ErrorType.NETWORK_ERROR,
            error_message="Connection timeout",
            response_time_ms=5000,
            retry_after_seconds=60
        )
        
        assert attempt.attempt_id == "attempt_001"
        assert attempt.attempt_number == 1
        assert attempt.timestamp == timestamp
        assert attempt.status == DeliveryStatus.IN_PROGRESS
        assert attempt.error_type == ErrorType.NETWORK_ERROR
        assert attempt.error_message == "Connection timeout"
        assert attempt.response_time_ms == 5000
        assert attempt.retry_after_seconds == 60
    
    def test_retry_policy_creation(self):
        """Test RetryPolicy dataclass creation"""
        policy = RetryPolicy(
            max_retries=5,
            initial_delay_seconds=15,
            max_delay_seconds=1800,
            backoff_multiplier=3.0,
            exponential_backoff=False
        )
        
        assert policy.max_retries == 5
        assert policy.initial_delay_seconds == 15
        assert policy.max_delay_seconds == 1800
        assert policy.backoff_multiplier == 3.0
        assert policy.exponential_backoff is False
        assert ErrorType.NETWORK_ERROR in policy.retry_on_errors
        assert ErrorType.INVALID_USER in policy.no_retry_errors
    
    def test_delivery_stats_creation(self):
        """Test DeliveryStats dataclass creation"""
        stats = DeliveryStats(
            total_deliveries=100,
            successful_deliveries=85,
            failed_deliveries=10,
            pending_deliveries=5,
            success_rate=0.85,
            average_delivery_time_ms=1250.5
        )
        
        assert stats.total_deliveries == 100
        assert stats.successful_deliveries == 85
        assert stats.failed_deliveries == 10
        assert stats.pending_deliveries == 5
        assert stats.success_rate == 0.85
        assert stats.average_delivery_time_ms == 1250.5
    
    def test_delivery_status_enum(self):
        """Test DeliveryStatus enum values"""
        assert DeliveryStatus.PENDING.value == "pending"
        assert DeliveryStatus.IN_PROGRESS.value == "in_progress"
        assert DeliveryStatus.DELIVERED.value == "delivered"
        assert DeliveryStatus.FAILED.value == "failed"
        assert DeliveryStatus.RETRYING.value == "retrying"
        assert DeliveryStatus.PERMANENTLY_FAILED.value == "permanently_failed"
    
    def test_error_type_enum(self):
        """Test ErrorType enum values"""
        assert ErrorType.NETWORK_ERROR.value == "network_error"
        assert ErrorType.RATE_LIMIT.value == "rate_limit"
        assert ErrorType.INVALID_USER.value == "invalid_user"
        assert ErrorType.CONTENT_ERROR.value == "content_error"
        assert ErrorType.TIMEOUT_ERROR.value == "timeout_error"
        assert ErrorType.SYSTEM_ERROR.value == "system_error"
        assert ErrorType.UNKNOWN_ERROR.value == "unknown_error"
    
    def test_get_delivery_tracker_singleton(self):
        """Test global delivery tracker singleton"""
        tracker1 = get_delivery_tracker()
        tracker2 = get_delivery_tracker()
        
        assert tracker1 is tracker2
        assert isinstance(tracker1, DeliveryTracker)