"""
Unit tests for TimezoneManager
"""

import pytest
from unittest.mock import patch, Mock
from datetime import datetime, time, timezone, timedelta
from zoneinfo import ZoneInfo

from src.utils.timezone_manager import (
    TimezoneManager, UserTimezoneInfo, DeliverySchedule, 
    TimezoneGroup, get_timezone_manager
)


class TestTimezoneManager:
    """Test cases for TimezoneManager"""
    
    @pytest.fixture
    def timezone_manager(self):
        """Create a TimezoneManager instance"""
        return TimezoneManager()
    
    @pytest.fixture
    def sample_user_data(self):
        """Create sample user data for testing"""
        return {
            "timezone": "Asia/Bangkok",
            "country": "Thailand", 
            "city": "Bangkok",
            "language": "th",
            "recent_messages": [
                "I'm in Bangkok, it's 3 PM now",
                "Good morning! It's 9 AM here in Thailand"
            ],
            "activity_times": [
                datetime(2024, 1, 1, 2, 0, 0, tzinfo=timezone.utc),  # 9 AM Bangkok
                datetime(2024, 1, 1, 5, 0, 0, tzinfo=timezone.utc),  # 12 PM Bangkok
                datetime(2024, 1, 1, 9, 0, 0, tzinfo=timezone.utc),  # 4 PM Bangkok
            ]
        }
    
    def test_initialization(self, timezone_manager):
        """Test TimezoneManager initialization"""
        assert isinstance(timezone_manager.user_timezones, dict)
        assert isinstance(timezone_manager.timezone_groups, dict)
        assert isinstance(timezone_manager.delivery_schedules, list)
        assert timezone_manager.default_delivery_hour == 9
        assert "Asia/Bangkok" in timezone_manager.timezone_mappings
        assert "Asia/Tokyo" in timezone_manager.utc_offsets
    
    def test_timezone_mappings_loaded(self, timezone_manager):
        """Test that timezone mappings are properly loaded"""
        # Check major regions are covered
        assert "th" in timezone_manager.timezone_mappings
        assert "japan" in timezone_manager.timezone_mappings
        assert "uk" in timezone_manager.timezone_mappings
        assert "us" in timezone_manager.timezone_mappings
        
        # Check mappings point to valid timezone names
        assert timezone_manager.timezone_mappings["th"] == "Asia/Bangkok"
        assert timezone_manager.timezone_mappings["japan"] == "Asia/Tokyo"
    
    def test_utc_offsets_loaded(self, timezone_manager):
        """Test that UTC offsets are properly loaded"""
        assert timezone_manager.utc_offsets["Asia/Bangkok"] == 7.0
        assert timezone_manager.utc_offsets["Asia/Tokyo"] == 9.0
        assert timezone_manager.utc_offsets["Europe/London"] == 0.0
        assert timezone_manager.utc_offsets["America/New_York"] == -5.0
    
    def test_detect_user_timezone_from_profile(self, timezone_manager, sample_user_data):
        """Test timezone detection from profile data"""
        user_id = "test_user_123"
        
        tz_info = timezone_manager.detect_user_timezone(user_id, sample_user_data)
        
        assert tz_info is not None
        assert tz_info.user_id == user_id
        assert tz_info.timezone == "Asia/Bangkok"
        assert tz_info.offset_hours == 7.0
        assert tz_info.detected_method == "profile_direct"
        assert tz_info.confidence >= 0.9
        assert user_id in timezone_manager.user_timezones
    
    def test_detect_user_timezone_from_location(self, timezone_manager):
        """Test timezone detection from location data"""
        user_data = {
            "country": "Japan",
            "city": "Tokyo"
        }
        user_id = "test_user_456"
        
        tz_info = timezone_manager.detect_user_timezone(user_id, user_data)
        
        assert tz_info is not None
        assert tz_info.timezone == "Asia/Tokyo"
        assert "location" in tz_info.detected_method
        assert tz_info.confidence >= 0.7
    
    def test_detect_user_timezone_from_language(self, timezone_manager):
        """Test timezone detection from language"""
        user_data = {
            "language": "th"
        }
        user_id = "test_user_789"
        
        tz_info = timezone_manager.detect_user_timezone(user_id, user_data)
        
        assert tz_info is not None
        assert tz_info.timezone == "Asia/Bangkok"
        assert tz_info.detected_method == "language_inference"
        assert tz_info.confidence >= 0.5
    
    def test_detect_user_timezone_no_data(self, timezone_manager):
        """Test timezone detection with no useful data"""
        user_data = {
            "name": "John Doe",
            "age": 30
        }
        user_id = "test_user_no_tz"
        
        tz_info = timezone_manager.detect_user_timezone(user_id, user_data)
        assert tz_info is None
        assert user_id not in timezone_manager.user_timezones
    
    def test_analyze_message_patterns(self, timezone_manager):
        """Test message pattern analysis for timezone detection"""
        messages = [
            "I'm in GMT+7 timezone",
            "It's 3 PM JST here",
            "Live in Bangkok, Thailand"
        ]
        
        candidates = timezone_manager._analyze_message_patterns(messages)
        
        assert len(candidates) > 0
        # Should find JST timezone
        assert any("Asia/Tokyo" in candidate[0] for candidate in candidates)
    
    def test_find_timezone_by_offset(self, timezone_manager):
        """Test finding timezone by UTC offset"""
        # Test exact match
        tz = timezone_manager._find_timezone_by_offset(7.0)
        assert tz in ["Asia/Bangkok", "Asia/Jakarta"]  # Both have +7 offset
        
        # Test close match
        tz = timezone_manager._find_timezone_by_offset(6.5)
        assert tz is not None  # Should find closest match
        
        # Test no match (very far offset)
        tz = timezone_manager._find_timezone_by_offset(15.0)
        assert tz is None
    
    def test_analyze_activity_patterns(self, timezone_manager):
        """Test activity pattern analysis"""
        # Activity times that suggest Asian timezone (peak around UTC+7/8)
        activity_times = [
            datetime(2024, 1, 1, 2, 0, 0, tzinfo=timezone.utc),  # 9-10 AM in Asia
            datetime(2024, 1, 1, 3, 0, 0, tzinfo=timezone.utc),
            datetime(2024, 1, 1, 7, 0, 0, tzinfo=timezone.utc),  # 2-3 PM in Asia
            datetime(2024, 1, 1, 8, 0, 0, tzinfo=timezone.utc),
            datetime(2024, 1, 1, 11, 0, 0, tzinfo=timezone.utc), # 6-7 PM in Asia
        ]
        
        detected_tz = timezone_manager._analyze_activity_patterns(activity_times)
        
        # Should detect Asian timezone
        if detected_tz:
            offset = timezone_manager._get_timezone_offset(detected_tz)
            assert 6.0 <= offset <= 9.0  # Asian timezone range
    
    def test_analyze_activity_patterns_insufficient_data(self, timezone_manager):
        """Test activity pattern analysis with insufficient data"""
        # Too few activity times
        activity_times = [
            datetime(2024, 1, 1, 2, 0, 0, tzinfo=timezone.utc),
            datetime(2024, 1, 1, 3, 0, 0, tzinfo=timezone.utc)
        ]
        
        detected_tz = timezone_manager._analyze_activity_patterns(activity_times)
        assert detected_tz is None
    
    @patch('src.utils.timezone_manager.ZoneInfo')
    def test_get_timezone_offset_with_zoneinfo(self, mock_zoneinfo, timezone_manager):
        """Test timezone offset calculation using zoneinfo"""
        mock_tz = Mock()
        mock_datetime = Mock()
        mock_datetime.utcoffset.return_value = timedelta(hours=7)
        
        with patch('src.utils.timezone_manager.datetime') as mock_dt:
            mock_dt.now.return_value = mock_datetime
            mock_zoneinfo.return_value = mock_tz
            
            offset = timezone_manager._get_timezone_offset("Asia/Bangkok")
            assert offset == 7.0
    
    def test_get_timezone_offset_fallback(self, timezone_manager):
        """Test timezone offset with fallback to stored values"""
        offset = timezone_manager._get_timezone_offset("Asia/Bangkok")
        assert offset == 7.0
        
        # Test unknown timezone
        offset = timezone_manager._get_timezone_offset("Unknown/Timezone")
        assert offset == 0.0
    
    def test_schedule_delivery_for_timezone(self, timezone_manager):
        """Test scheduling delivery for specific timezone"""
        # Add some users to the timezone first
        user_id = "test_user_schedule"
        timezone_manager.user_timezones[user_id] = UserTimezoneInfo(
            user_id=user_id,
            timezone="Asia/Bangkok",
            offset_hours=7.0,
            detected_method="test",
            confidence=1.0,
            last_updated=datetime.now(timezone.utc)
        )
        
        local_time = time(9, 0)  # 9 AM local
        
        schedule = timezone_manager.schedule_delivery_for_timezone(
            timezone_name="Asia/Bangkok",
            local_delivery_time=local_time,
            content_category="motivation",
            target_users=[user_id]
        )
        
        assert isinstance(schedule, DeliverySchedule)
        assert schedule.timezone == "Asia/Bangkok"
        assert schedule.local_delivery_time == local_time
        assert user_id in schedule.target_users
        assert schedule.content_category == "motivation"
        assert schedule in timezone_manager.delivery_schedules
    
    def test_get_users_in_timezone(self, timezone_manager):
        """Test getting users in specific timezone"""
        # Add test users
        users_bangkok = ["user1", "user2"]
        users_tokyo = ["user3"]
        
        for user_id in users_bangkok:
            timezone_manager.user_timezones[user_id] = UserTimezoneInfo(
                user_id=user_id,
                timezone="Asia/Bangkok",
                offset_hours=7.0,
                detected_method="test",
                confidence=1.0,
                last_updated=datetime.now(timezone.utc)
            )
        
        for user_id in users_tokyo:
            timezone_manager.user_timezones[user_id] = UserTimezoneInfo(
                user_id=user_id,
                timezone="Asia/Tokyo",
                offset_hours=9.0,
                detected_method="test",
                confidence=1.0,
                last_updated=datetime.now(timezone.utc)
            )
        
        bangkok_users = timezone_manager.get_users_in_timezone("Asia/Bangkok")
        tokyo_users = timezone_manager.get_users_in_timezone("Asia/Tokyo")
        
        assert set(bangkok_users) == set(users_bangkok)
        assert set(tokyo_users) == set(users_tokyo)
        assert timezone_manager.get_users_in_timezone("Europe/London") == []
    
    def test_get_upcoming_deliveries(self, timezone_manager):
        """Test getting upcoming deliveries"""
        now = datetime.now(timezone.utc)
        
        # Add some delivery schedules
        future_schedule = DeliverySchedule(
            timezone="Asia/Bangkok",
            delivery_time_utc=now + timedelta(hours=2),
            local_delivery_time=time(9, 0),
            target_users=["user1"],
            content_category="motivation"
        )
        
        past_schedule = DeliverySchedule(
            timezone="Asia/Tokyo",
            delivery_time_utc=now - timedelta(hours=1),
            local_delivery_time=time(9, 0),
            target_users=["user2"],
            content_category="wellness"
        )
        
        far_future_schedule = DeliverySchedule(
            timezone="Europe/London",
            delivery_time_utc=now + timedelta(hours=30),
            local_delivery_time=time(9, 0),
            target_users=["user3"],
            content_category="productivity"
        )
        
        timezone_manager.delivery_schedules = [
            future_schedule, past_schedule, far_future_schedule
        ]
        
        upcoming = timezone_manager.get_upcoming_deliveries(hours_ahead=24)
        
        assert len(upcoming) == 1
        assert upcoming[0] == future_schedule
    
    def test_get_next_delivery_time_for_user(self, timezone_manager):
        """Test getting next delivery time for user"""
        user_id = "test_user_next"
        timezone_manager.user_timezones[user_id] = UserTimezoneInfo(
            user_id=user_id,
            timezone="Asia/Bangkok",
            offset_hours=7.0,
            detected_method="test",
            confidence=1.0,
            last_updated=datetime.now(timezone.utc)
        )
        
        next_delivery = timezone_manager.get_next_delivery_time_for_user(
            user_id, preferred_local_hour=9
        )
        
        assert next_delivery is not None
        assert isinstance(next_delivery, datetime)
        assert next_delivery > datetime.now(timezone.utc)
    
    def test_get_next_delivery_time_unknown_user(self, timezone_manager):
        """Test getting next delivery time for unknown user"""
        next_delivery = timezone_manager.get_next_delivery_time_for_user(
            "unknown_user", preferred_local_hour=9
        )
        assert next_delivery is None
    
    def test_create_timezone_groups(self, timezone_manager):
        """Test creating timezone groups"""
        # Add users in different timezones
        test_users = {
            "user1": "Asia/Bangkok",
            "user2": "Asia/Bangkok", 
            "user3": "Asia/Tokyo",
            "user4": "Europe/London"
        }
        
        for user_id, tz_name in test_users.items():
            timezone_manager.user_timezones[user_id] = UserTimezoneInfo(
                user_id=user_id,
                timezone=tz_name,
                offset_hours=timezone_manager._get_timezone_offset(tz_name),
                detected_method="test",
                confidence=1.0,
                last_updated=datetime.now(timezone.utc)
            )
        
        groups = timezone_manager.create_timezone_groups()
        
        assert len(groups) == 3  # 3 different timezones
        assert "Asia/Bangkok" in groups
        assert "Asia/Tokyo" in groups
        assert "Europe/London" in groups
        
        bangkok_group = groups["Asia/Bangkok"]
        assert bangkok_group.user_count == 2
        assert set(bangkok_group.users) == {"user1", "user2"}
        assert bangkok_group.offset_hours == 7.0
    
    def test_get_optimal_delivery_schedule(self, timezone_manager):
        """Test getting optimal delivery schedule"""
        # Add test users
        test_users = {
            "user1": "Asia/Bangkok",
            "user2": "Asia/Tokyo",
            "user3": "Europe/London"
        }
        
        for user_id, tz_name in test_users.items():
            timezone_manager.user_timezones[user_id] = UserTimezoneInfo(
                user_id=user_id,
                timezone=tz_name,
                offset_hours=timezone_manager._get_timezone_offset(tz_name),
                detected_method="test",
                confidence=1.0,
                last_updated=datetime.now(timezone.utc)
            )
        
        schedules = timezone_manager.get_optimal_delivery_schedule("motivation")
        
        assert len(schedules) == 3  # One for each timezone
        assert all(isinstance(s, DeliverySchedule) for s in schedules)
        assert all(s.content_category == "motivation" for s in schedules)
        
        # Should be sorted by delivery time
        delivery_times = [s.delivery_time_utc for s in schedules]
        assert delivery_times == sorted(delivery_times)
    
    def test_update_user_timezone_new_user(self, timezone_manager):
        """Test updating timezone for new user"""
        user_id = "new_user"
        
        success = timezone_manager.update_user_timezone(
            user_id, "Asia/Tokyo", "manual_update"
        )
        
        assert success is True
        assert user_id in timezone_manager.user_timezones
        
        tz_info = timezone_manager.user_timezones[user_id]
        assert tz_info.timezone == "Asia/Tokyo"
        assert tz_info.detected_method == "manual_update"
        assert tz_info.confidence == 1.0
    
    def test_update_user_timezone_existing_user(self, timezone_manager):
        """Test updating timezone for existing user"""
        user_id = "existing_user"
        
        # Add existing user
        timezone_manager.user_timezones[user_id] = UserTimezoneInfo(
            user_id=user_id,
            timezone="Asia/Bangkok",
            offset_hours=7.0,
            detected_method="auto_detect",
            confidence=0.8,
            last_updated=datetime.now(timezone.utc)
        )
        
        success = timezone_manager.update_user_timezone(
            user_id, "Asia/Tokyo", "user_preference"
        )
        
        assert success is True
        
        tz_info = timezone_manager.user_timezones[user_id]
        assert tz_info.timezone == "Asia/Tokyo"
        assert tz_info.detected_method == "user_preference"
        assert tz_info.confidence == 1.0
    
    def test_update_user_timezone_invalid(self, timezone_manager):
        """Test updating timezone with invalid timezone"""
        user_id = "test_user"
        
        with patch('src.utils.timezone_manager.ZoneInfo', side_effect=Exception("Invalid timezone")):
            success = timezone_manager.update_user_timezone(
                user_id, "Invalid/Timezone", "manual"
            )
            assert success is False
            assert user_id not in timezone_manager.user_timezones
    
    def test_get_timezone_statistics_empty(self, timezone_manager):
        """Test timezone statistics with no users"""
        stats = timezone_manager.get_timezone_statistics()
        
        assert stats["total_users"] == 0
        assert stats["timezones_count"] == 0
        assert stats["timezone_distribution"] == {}
        assert stats["detection_methods"] == {}
        assert stats["coverage_regions"] == {}
    
    def test_get_timezone_statistics_with_users(self, timezone_manager):
        """Test timezone statistics with users"""
        # Add test users
        test_data = [
            ("user1", "Asia/Bangkok", "profile_direct"),
            ("user2", "Asia/Bangkok", "location_country"),
            ("user3", "Asia/Tokyo", "language_inference"),
            ("user4", "Europe/London", "manual_update")
        ]
        
        for user_id, tz_name, method in test_data:
            timezone_manager.user_timezones[user_id] = UserTimezoneInfo(
                user_id=user_id,
                timezone=tz_name,
                offset_hours=timezone_manager._get_timezone_offset(tz_name),
                detected_method=method,
                confidence=1.0,
                last_updated=datetime.now(timezone.utc)
            )
        
        stats = timezone_manager.get_timezone_statistics()
        
        assert stats["total_users"] == 4
        assert stats["timezones_count"] == 3
        assert stats["timezone_distribution"]["Asia/Bangkok"] == 2
        assert stats["timezone_distribution"]["Asia/Tokyo"] == 1
        assert stats["timezone_distribution"]["Europe/London"] == 1
        assert stats["detection_methods"]["profile_direct"] == 1
        assert stats["coverage_regions"]["Asia"] == 3
        assert stats["coverage_regions"]["Europe"] == 1
    
    def test_cleanup_old_schedules(self, timezone_manager):
        """Test cleaning up old delivery schedules"""
        now = datetime.now(timezone.utc)
        
        # Add schedules with different ages
        old_schedule = DeliverySchedule(
            timezone="Asia/Bangkok",
            delivery_time_utc=now - timedelta(hours=25),  # More than 24 hours old
            local_delivery_time=time(9, 0),
            target_users=["user1"],
            content_category="motivation"
        )
        
        recent_schedule = DeliverySchedule(
            timezone="Asia/Tokyo", 
            delivery_time_utc=now - timedelta(hours=1),  # Recent
            local_delivery_time=time(9, 0),
            target_users=["user2"],
            content_category="wellness"
        )
        
        future_schedule = DeliverySchedule(
            timezone="Europe/London",
            delivery_time_utc=now + timedelta(hours=2),  # Future
            local_delivery_time=time(9, 0),
            target_users=["user3"],
            content_category="productivity"
        )
        
        timezone_manager.delivery_schedules = [
            old_schedule, recent_schedule, future_schedule
        ]
        
        removed_count = timezone_manager.cleanup_old_schedules(hours_past=24)
        
        assert removed_count == 1
        assert len(timezone_manager.delivery_schedules) == 2
        assert old_schedule not in timezone_manager.delivery_schedules
        assert recent_schedule in timezone_manager.delivery_schedules
        assert future_schedule in timezone_manager.delivery_schedules
    
    def test_user_timezone_info_creation(self):
        """Test UserTimezoneInfo creation"""
        tz_info = UserTimezoneInfo(
            user_id="test_user",
            timezone="Asia/Bangkok",
            offset_hours=7.0,
            detected_method="profile_direct",
            confidence=0.95,
            last_updated=datetime.now(timezone.utc),
            preferred_delivery_time=time(9, 0),
            country_code="TH",
            city="Bangkok"
        )
        
        assert tz_info.user_id == "test_user"
        assert tz_info.timezone == "Asia/Bangkok"
        assert tz_info.offset_hours == 7.0
        assert tz_info.detected_method == "profile_direct"
        assert tz_info.confidence == 0.95
        assert tz_info.preferred_delivery_time == time(9, 0)
        assert tz_info.country_code == "TH"
        assert tz_info.city == "Bangkok"
    
    def test_delivery_schedule_creation(self):
        """Test DeliverySchedule creation"""
        delivery_time = datetime.now(timezone.utc) + timedelta(hours=1)
        
        schedule = DeliverySchedule(
            timezone="Asia/Bangkok",
            delivery_time_utc=delivery_time,
            local_delivery_time=time(9, 0),
            target_users=["user1", "user2"],
            content_category="motivation",
            priority=1
        )
        
        assert schedule.timezone == "Asia/Bangkok"
        assert schedule.delivery_time_utc == delivery_time
        assert schedule.local_delivery_time == time(9, 0)
        assert schedule.target_users == ["user1", "user2"]
        assert schedule.content_category == "motivation"
        assert schedule.priority == 1
    
    def test_timezone_group_creation(self):
        """Test TimezoneGroup creation"""
        group = TimezoneGroup(
            timezone="Asia/Bangkok",
            offset_hours=7.0,
            user_count=5,
            users=["user1", "user2", "user3", "user4", "user5"],
            preferred_local_time=time(9, 0)
        )
        
        assert group.timezone == "Asia/Bangkok"
        assert group.offset_hours == 7.0
        assert group.user_count == 5
        assert len(group.users) == 5
        assert group.preferred_local_time == time(9, 0)
    
    def test_get_timezone_manager_singleton(self):
        """Test global timezone manager singleton"""
        manager1 = get_timezone_manager()
        manager2 = get_timezone_manager()
        
        assert manager1 is manager2
        assert isinstance(manager1, TimezoneManager)