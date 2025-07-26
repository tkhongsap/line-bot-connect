"""
Timezone Management and User Timezone Detection for Rich Message automation.

This module provides timezone-aware scheduling capabilities, user timezone detection,
and delivery time coordination for global Rich Message distribution.
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
import json
import re

logger = logging.getLogger(__name__)


@dataclass
class UserTimezoneInfo:
    """User timezone information"""
    user_id: str
    timezone: str  # IANA timezone identifier (e.g., "Asia/Bangkok")
    offset_hours: float  # UTC offset in hours
    detected_method: str  # How timezone was detected
    confidence: float  # Confidence level (0.0 to 1.0)
    last_updated: datetime
    preferred_delivery_time: Optional[time] = None
    country_code: Optional[str] = None
    city: Optional[str] = None


@dataclass
class DeliverySchedule:
    """Delivery schedule for a specific timezone"""
    timezone: str
    delivery_time_utc: datetime
    local_delivery_time: time
    target_users: List[str]
    content_category: str
    priority: int = 1  # 1 = highest priority


@dataclass
class TimezoneGroup:
    """Group of users sharing the same timezone for batch delivery"""
    timezone: str
    offset_hours: float
    user_count: int
    users: List[str] = field(default_factory=list)
    next_delivery_utc: Optional[datetime] = None
    preferred_local_time: time = time(9, 0)  # Default 9:00 AM local


class TimezoneManager:
    """
    Comprehensive timezone management system for Rich Message automation.
    
    Handles user timezone detection, delivery scheduling coordination,
    and timezone-aware message distribution.
    """
    
    def __init__(self):
        """Initialize the TimezoneManager."""
        self.user_timezones: Dict[str, UserTimezoneInfo] = {}
        self.timezone_groups: Dict[str, TimezoneGroup] = {}
        self.delivery_schedules: List[DeliverySchedule] = []
        
        # Load timezone data and initialize detection patterns
        self._load_timezone_data()
        self._init_detection_patterns()
        
        # Default delivery preferences
        self.default_delivery_hour = 9  # 9:00 AM local time
        self.delivery_window_hours = 2  # Allow 2-hour window around preferred time
        self.max_timezone_groups = 50  # Limit number of timezone groups for performance
    
    def _load_timezone_data(self) -> None:
        """Load timezone mapping data and common patterns."""
        # Common timezone mappings for major regions
        self.timezone_mappings = {
            # Asia-Pacific
            "th": "Asia/Bangkok",
            "thailand": "Asia/Bangkok",
            "bangkok": "Asia/Bangkok",
            "jp": "Asia/Tokyo",
            "japan": "Asia/Tokyo",
            "tokyo": "Asia/Tokyo",
            "kr": "Asia/Seoul",
            "korea": "Asia/Seoul",
            "seoul": "Asia/Seoul",
            "cn": "Asia/Shanghai",
            "china": "Asia/Shanghai",
            "shanghai": "Asia/Shanghai",
            "beijing": "Asia/Shanghai",
            "sg": "Asia/Singapore",
            "singapore": "Asia/Singapore",
            "hk": "Asia/Hong_Kong",
            "hong kong": "Asia/Hong_Kong",
            "tw": "Asia/Taipei",
            "taiwan": "Asia/Taipei",
            "taipei": "Asia/Taipei",
            "my": "Asia/Kuala_Lumpur",
            "malaysia": "Asia/Kuala_Lumpur",
            "kuala lumpur": "Asia/Kuala_Lumpur",
            "id": "Asia/Jakarta",
            "indonesia": "Asia/Jakarta",
            "jakarta": "Asia/Jakarta",
            "ph": "Asia/Manila",
            "philippines": "Asia/Manila",
            "manila": "Asia/Manila",
            "vn": "Asia/Ho_Chi_Minh",
            "vietnam": "Asia/Ho_Chi_Minh",
            "ho chi minh": "Asia/Ho_Chi_Minh",
            "saigon": "Asia/Ho_Chi_Minh",
            "in": "Asia/Kolkata",
            "india": "Asia/Kolkata",
            "mumbai": "Asia/Kolkata",
            "delhi": "Asia/Kolkata",
            "kolkata": "Asia/Kolkata",
            "au": "Australia/Sydney",
            "australia": "Australia/Sydney",
            "sydney": "Australia/Sydney",
            "melbourne": "Australia/Melbourne",
            
            # Europe
            "gb": "Europe/London",
            "uk": "Europe/London",
            "london": "Europe/London",
            "fr": "Europe/Paris",
            "france": "Europe/Paris",
            "paris": "Europe/Paris",
            "de": "Europe/Berlin",
            "germany": "Europe/Berlin",
            "berlin": "Europe/Berlin",
            "it": "Europe/Rome",
            "italy": "Europe/Rome",
            "rome": "Europe/Rome",
            "es": "Europe/Madrid",
            "spain": "Europe/Madrid",
            "madrid": "Europe/Madrid",
            "nl": "Europe/Amsterdam",
            "netherlands": "Europe/Amsterdam",
            "amsterdam": "Europe/Amsterdam",
            "ru": "Europe/Moscow",
            "russia": "Europe/Moscow",
            "moscow": "Europe/Moscow",
            
            # Americas
            "us": "America/New_York",
            "usa": "America/New_York",
            "new york": "America/New_York",
            "los angeles": "America/Los_Angeles",
            "chicago": "America/Chicago",
            "denver": "America/Denver",
            "ca": "America/Toronto",
            "canada": "America/Toronto",
            "toronto": "America/Toronto",
            "vancouver": "America/Vancouver",
            "br": "America/Sao_Paulo",
            "brazil": "America/Sao_Paulo",
            "sao paulo": "America/Sao_Paulo",
            "mx": "America/Mexico_City",
            "mexico": "America/Mexico_City",
            "mexico city": "America/Mexico_City",
            
            # Middle East & Africa
            "ae": "Asia/Dubai",
            "uae": "Asia/Dubai",
            "dubai": "Asia/Dubai",
            "sa": "Asia/Riyadh",
            "saudi arabia": "Asia/Riyadh",
            "riyadh": "Asia/Riyadh",
            "eg": "Africa/Cairo",
            "egypt": "Africa/Cairo",
            "cairo": "Africa/Cairo",
            "za": "Africa/Johannesburg",
            "south africa": "Africa/Johannesburg",
            "johannesburg": "Africa/Johannesburg",
        }
        
        # UTC offset mappings for common timezones
        self.utc_offsets = {
            "Asia/Bangkok": 7.0,
            "Asia/Tokyo": 9.0,
            "Asia/Seoul": 9.0,
            "Asia/Shanghai": 8.0,
            "Asia/Singapore": 8.0,
            "Asia/Hong_Kong": 8.0,
            "Asia/Taipei": 8.0,
            "Asia/Kuala_Lumpur": 8.0,
            "Asia/Jakarta": 7.0,
            "Asia/Manila": 8.0,
            "Asia/Ho_Chi_Minh": 7.0,
            "Asia/Kolkata": 5.5,
            "Australia/Sydney": 11.0,  # AEDT, varies with DST
            "Australia/Melbourne": 11.0,
            "Europe/London": 0.0,  # GMT, varies with DST
            "Europe/Paris": 1.0,  # CET, varies with DST
            "Europe/Berlin": 1.0,
            "Europe/Rome": 1.0,
            "Europe/Madrid": 1.0,
            "Europe/Amsterdam": 1.0,
            "Europe/Moscow": 3.0,
            "America/New_York": -5.0,  # EST, varies with DST
            "America/Los_Angeles": -8.0,  # PST, varies with DST
            "America/Chicago": -6.0,  # CST, varies with DST
            "America/Denver": -7.0,  # MST, varies with DST
            "America/Toronto": -5.0,
            "America/Vancouver": -8.0,
            "America/Sao_Paulo": -3.0,
            "America/Mexico_City": -6.0,
            "Asia/Dubai": 4.0,
            "Asia/Riyadh": 3.0,
            "Africa/Cairo": 2.0,
            "Africa/Johannesburg": 2.0,
        }
    
    def _init_detection_patterns(self) -> None:
        """Initialize patterns for timezone detection from user data."""
        # Patterns for extracting timezone info from user messages or profile data
        self.timezone_patterns = [
            # Direct timezone mentions
            r'\b(utc|gmt)([+-]\d{1,2})\b',
            r'\b(gmt|utc)\s*([+-]\d{1,2}(?::\d{2})?)\b',
            
            # Time zone abbreviations
            r'\b(pst|pdt|est|edt|cst|cdt|mst|mdt|jst|kst|ist|cet|bst|aest|aedt)\b',
            
            # Location mentions
            r'\b(live in|from|located in|based in|living in)\s+([a-z\s]+)',
            r'\b(timezone|time zone):\s*([a-z/_]+)',
            
            # Time format patterns (12/24 hour indicators)
            r'\b(\d{1,2}):(\d{2})\s*(am|pm)\b',
            r'\b(\d{1,2}):(\d{2})\s*(?:local|my time)\b',
        ]
        
        # Common timezone abbreviations mapping
        self.timezone_abbreviations = {
            "pst": "America/Los_Angeles",
            "pdt": "America/Los_Angeles",
            "est": "America/New_York",
            "edt": "America/New_York",
            "cst": "America/Chicago",
            "cdt": "America/Chicago",
            "mst": "America/Denver",
            "mdt": "America/Denver",
            "jst": "Asia/Tokyo",
            "kst": "Asia/Seoul",
            "ist": "Asia/Kolkata",
            "cet": "Europe/Paris",
            "bst": "Europe/London",
            "aest": "Australia/Sydney",
            "aedt": "Australia/Sydney",
        }
    
    def detect_user_timezone(self, user_id: str, user_data: Dict[str, Any]) -> Optional[UserTimezoneInfo]:
        """
        Detect user timezone from available data.
        
        Args:
            user_id: User identifier
            user_data: Dictionary containing user profile data, messages, etc.
            
        Returns:
            UserTimezoneInfo if timezone detected, None otherwise
        """
        detection_methods = []
        candidate_timezones = []
        
        # Method 1: Direct timezone information from profile
        if "timezone" in user_data and user_data["timezone"]:
            tz_str = str(user_data["timezone"]).lower()
            if tz_str in self.timezone_mappings:
                candidate_timezones.append((
                    self.timezone_mappings[tz_str],
                    "profile_direct",
                    0.95
                ))
        
        # Method 2: Location information
        location_fields = ["location", "country", "city", "region"]
        for field in location_fields:
            if field in user_data and user_data[field]:
                location = str(user_data[field]).lower().strip()
                if location in self.timezone_mappings:
                    candidate_timezones.append((
                        self.timezone_mappings[location],
                        f"location_{field}",
                        0.8
                    ))
        
        # Method 3: Language-based inference
        if "language" in user_data and user_data["language"]:
            lang = str(user_data["language"]).lower()
            if lang in self.timezone_mappings:
                candidate_timezones.append((
                    self.timezone_mappings[lang],
                    "language_inference",
                    0.6
                ))
        
        # Method 4: Message content analysis
        if "recent_messages" in user_data:
            tz_from_messages = self._analyze_message_patterns(user_data["recent_messages"])
            if tz_from_messages:
                candidate_timezones.extend([
                    (tz, "message_analysis", conf) for tz, conf in tz_from_messages
                ])
        
        # Method 5: Activity pattern analysis
        if "activity_times" in user_data:
            tz_from_activity = self._analyze_activity_patterns(user_data["activity_times"])
            if tz_from_activity:
                candidate_timezones.append((
                    tz_from_activity,
                    "activity_pattern",
                    0.7
                ))
        
        # Select best candidate
        if not candidate_timezones:
            logger.info(f"No timezone detected for user {user_id[:8]}...")
            return None
        
        # Sort by confidence and select best
        candidate_timezones.sort(key=lambda x: x[2], reverse=True)
        best_timezone, method, confidence = candidate_timezones[0]
        
        # Get UTC offset
        offset_hours = self._get_timezone_offset(best_timezone)
        
        # Create timezone info
        timezone_info = UserTimezoneInfo(
            user_id=user_id,
            timezone=best_timezone,
            offset_hours=offset_hours,
            detected_method=method,
            confidence=confidence,
            last_updated=datetime.now(timezone.utc),
            country_code=user_data.get("country_code"),
            city=user_data.get("city")
        )
        
        # Store timezone info
        self.user_timezones[user_id] = timezone_info
        
        logger.info(f"Detected timezone {best_timezone} for user {user_id[:8]}... "
                   f"(method: {method}, confidence: {confidence:.2f})")
        
        return timezone_info
    
    def _analyze_message_patterns(self, messages: List[str]) -> List[Tuple[str, float]]:
        """Analyze message patterns to infer timezone."""
        candidates = []
        
        for message in messages:
            message_lower = message.lower()
            
            # Look for timezone patterns
            for pattern in self.timezone_patterns:
                matches = re.findall(pattern, message_lower)
                if matches:
                    # Process matches based on pattern type
                    for match in matches:
                        if isinstance(match, tuple):
                            # Extract timezone from complex patterns
                            tz_candidate = self._extract_timezone_from_match(match)
                            if tz_candidate:
                                candidates.append((tz_candidate, 0.8))
                        else:
                            # Simple string match
                            if match in self.timezone_abbreviations:
                                candidates.append((self.timezone_abbreviations[match], 0.7))
        
        return candidates
    
    def _extract_timezone_from_match(self, match: tuple) -> Optional[str]:
        """Extract timezone from regex match tuple."""
        if len(match) >= 2:
            # Handle UTC offset patterns like "GMT+7" or "UTC-5"
            base, offset = match[0], match[1]
            if base.lower() in ["utc", "gmt"]:
                try:
                    offset_hours = float(offset.replace(":", "."))
                    # Find closest timezone by offset
                    return self._find_timezone_by_offset(offset_hours)
                except ValueError:
                    pass
        
        return None
    
    def _find_timezone_by_offset(self, target_offset: float) -> Optional[str]:
        """Find timezone by UTC offset."""
        best_match = None
        min_diff = float('inf')
        
        for tz_name, offset in self.utc_offsets.items():
            diff = abs(offset - target_offset)
            if diff < min_diff:
                min_diff = diff
                best_match = tz_name
        
        # Only return if offset is close (within 1 hour)
        return best_match if min_diff <= 1.0 else None
    
    def _analyze_activity_patterns(self, activity_times: List[datetime]) -> Optional[str]:
        """Analyze user activity patterns to infer timezone."""
        if len(activity_times) < 5:
            return None
        
        # Calculate typical activity hours in UTC
        utc_hours = [dt.hour for dt in activity_times if isinstance(dt, datetime)]
        if not utc_hours:
            return None
        
        # Find peak activity hours
        hour_counts = {}
        for hour in utc_hours:
            hour_counts[hour] = hour_counts.get(hour, 0) + 1
        
        # Most common activity hours
        peak_hours = sorted(hour_counts.keys(), key=hour_counts.get, reverse=True)[:3]
        avg_peak_hour = sum(peak_hours) / len(peak_hours)
        
        # Assume typical active hours are 9-21 local time (avg 15)
        # Calculate offset needed to shift UTC to local peak
        target_local_hour = 15  # 3 PM average
        estimated_offset = (target_local_hour - avg_peak_hour) % 24
        if estimated_offset > 12:
            estimated_offset -= 24
        
        return self._find_timezone_by_offset(estimated_offset)
    
    def _get_timezone_offset(self, timezone_name: str) -> float:
        """Get UTC offset for timezone."""
        if timezone_name in self.utc_offsets:
            return self.utc_offsets[timezone_name]
        
        # Try to calculate offset using zoneinfo
        try:
            tz = ZoneInfo(timezone_name)
            now = datetime.now(tz)
            offset_seconds = now.utcoffset().total_seconds()
            return offset_seconds / 3600  # Convert to hours
        except Exception as e:
            logger.warning(f"Could not determine offset for {timezone_name}: {e}")
            return 0.0
    
    def schedule_delivery_for_timezone(self, timezone_name: str, 
                                     local_delivery_time: time,
                                     content_category: str,
                                     target_users: Optional[List[str]] = None) -> DeliverySchedule:
        """
        Schedule delivery for a specific timezone.
        
        Args:
            timezone_name: IANA timezone identifier
            local_delivery_time: Desired delivery time in local timezone
            content_category: Content category to deliver
            target_users: Specific users to target (None for all users in timezone)
            
        Returns:
            DeliverySchedule object
        """
        # Get users in this timezone if not specified
        if target_users is None:
            target_users = self.get_users_in_timezone(timezone_name)
        
        # Calculate UTC delivery time
        try:
            tz = ZoneInfo(timezone_name)
            
            # Create local datetime for today
            today = datetime.now(tz).date()
            local_datetime = datetime.combine(today, local_delivery_time, tz)
            
            # Convert to UTC
            delivery_time_utc = local_datetime.astimezone(timezone.utc)
            
            # If the time has already passed today, schedule for tomorrow
            if delivery_time_utc <= datetime.now(timezone.utc):
                local_datetime = datetime.combine(
                    today + timedelta(days=1), 
                    local_delivery_time, 
                    tz
                )
                delivery_time_utc = local_datetime.astimezone(timezone.utc)
            
        except Exception as e:
            logger.error(f"Error calculating delivery time for {timezone_name}: {e}")
            # Fallback to simple offset calculation
            offset_hours = self._get_timezone_offset(timezone_name)
            utc_hour = (local_delivery_time.hour - offset_hours) % 24
            delivery_time_utc = datetime.now(timezone.utc).replace(
                hour=utc_hour,
                minute=local_delivery_time.minute,
                second=0,
                microsecond=0
            )
        
        # Create delivery schedule
        schedule = DeliverySchedule(
            timezone=timezone_name,
            delivery_time_utc=delivery_time_utc,
            local_delivery_time=local_delivery_time,
            target_users=target_users,
            content_category=content_category,
            priority=1
        )
        
        self.delivery_schedules.append(schedule)
        
        logger.info(f"Scheduled delivery for {timezone_name} at {local_delivery_time} local "
                   f"(UTC: {delivery_time_utc}), {len(target_users)} users")
        
        return schedule
    
    def get_users_in_timezone(self, timezone_name: str) -> List[str]:
        """Get list of users in a specific timezone."""
        return [
            user_id for user_id, info in self.user_timezones.items()
            if info.timezone == timezone_name
        ]
    
    def get_upcoming_deliveries(self, hours_ahead: int = 24) -> List[DeliverySchedule]:
        """
        Get upcoming deliveries within specified time window.
        
        Args:
            hours_ahead: Look ahead this many hours
            
        Returns:
            List of upcoming delivery schedules
        """
        now = datetime.now(timezone.utc)
        cutoff = now + timedelta(hours=hours_ahead)
        
        upcoming = [
            schedule for schedule in self.delivery_schedules
            if now <= schedule.delivery_time_utc <= cutoff
        ]
        
        # Sort by delivery time
        upcoming.sort(key=lambda x: x.delivery_time_utc)
        
        return upcoming
    
    def get_next_delivery_time_for_user(self, user_id: str, 
                                       preferred_local_hour: int = 9) -> Optional[datetime]:
        """
        Get next delivery time for a specific user.
        
        Args:
            user_id: User identifier
            preferred_local_hour: Preferred delivery hour in user's local time
            
        Returns:
            Next delivery time in UTC, or None if user timezone unknown
        """
        if user_id not in self.user_timezones:
            return None
        
        user_tz_info = self.user_timezones[user_id]
        local_time = time(preferred_local_hour, 0)
        
        try:
            tz = ZoneInfo(user_tz_info.timezone)
            today = datetime.now(tz).date()
            local_datetime = datetime.combine(today, local_time, tz)
            delivery_utc = local_datetime.astimezone(timezone.utc)
            
            # If time has passed, schedule for tomorrow
            if delivery_utc <= datetime.now(timezone.utc):
                tomorrow = today + timedelta(days=1)
                local_datetime = datetime.combine(tomorrow, local_time, tz)
                delivery_utc = local_datetime.astimezone(timezone.utc)
            
            return delivery_utc
            
        except Exception as e:
            logger.error(f"Error calculating next delivery for user {user_id[:8]}...: {e}")
            return None
    
    def create_timezone_groups(self) -> Dict[str, TimezoneGroup]:
        """
        Create timezone groups for efficient batch delivery.
        
        Returns:
            Dictionary mapping timezone names to TimezoneGroup objects
        """
        self.timezone_groups.clear()
        
        # Group users by timezone
        timezone_user_map = {}
        for user_id, tz_info in self.user_timezones.items():
            tz_name = tz_info.timezone
            if tz_name not in timezone_user_map:
                timezone_user_map[tz_name] = []
            timezone_user_map[tz_name].append(user_id)
        
        # Create timezone groups
        for tz_name, users in timezone_user_map.items():
            if len(users) == 0:
                continue
                
            offset_hours = self._get_timezone_offset(tz_name)
            
            group = TimezoneGroup(
                timezone=tz_name,
                offset_hours=offset_hours,
                user_count=len(users),
                users=users,
                preferred_local_time=time(self.default_delivery_hour, 0)
            )
            
            # Calculate next delivery time
            group.next_delivery_utc = self.get_next_delivery_time_for_user(
                users[0], self.default_delivery_hour
            )
            
            self.timezone_groups[tz_name] = group
        
        logger.info(f"Created {len(self.timezone_groups)} timezone groups covering "
                   f"{sum(g.user_count for g in self.timezone_groups.values())} users")
        
        return self.timezone_groups
    
    def get_optimal_delivery_schedule(self, content_category: str) -> List[DeliverySchedule]:
        """
        Generate optimal delivery schedule for all timezone groups.
        
        Args:
            content_category: Content category to schedule
            
        Returns:
            List of optimized delivery schedules
        """
        if not self.timezone_groups:
            self.create_timezone_groups()
        
        schedules = []
        
        for tz_name, group in self.timezone_groups.items():
            if group.user_count == 0:
                continue
            
            schedule = self.schedule_delivery_for_timezone(
                timezone_name=tz_name,
                local_delivery_time=group.preferred_local_time,
                content_category=content_category,
                target_users=group.users
            )
            
            schedules.append(schedule)
        
        # Sort by delivery time for efficient execution
        schedules.sort(key=lambda x: x.delivery_time_utc)
        
        return schedules
    
    def update_user_timezone(self, user_id: str, timezone_name: str, 
                           method: str = "manual_update") -> bool:
        """
        Manually update user timezone.
        
        Args:
            user_id: User identifier
            timezone_name: IANA timezone identifier
            method: Method used for update
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Validate timezone
            tz = ZoneInfo(timezone_name)
            offset_hours = self._get_timezone_offset(timezone_name)
            
            # Update or create timezone info
            if user_id in self.user_timezones:
                tz_info = self.user_timezones[user_id]
                tz_info.timezone = timezone_name
                tz_info.offset_hours = offset_hours
                tz_info.detected_method = method
                tz_info.confidence = 1.0  # Manual updates have high confidence
                tz_info.last_updated = datetime.now(timezone.utc)
            else:
                tz_info = UserTimezoneInfo(
                    user_id=user_id,
                    timezone=timezone_name,
                    offset_hours=offset_hours,
                    detected_method=method,
                    confidence=1.0,
                    last_updated=datetime.now(timezone.utc)
                )
                self.user_timezones[user_id] = tz_info
            
            logger.info(f"Updated timezone for user {user_id[:8]}... to {timezone_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update timezone for user {user_id[:8]}...: {e}")
            return False
    
    def get_timezone_statistics(self) -> Dict[str, Any]:
        """
        Get timezone distribution statistics.
        
        Returns:
            Dictionary with timezone statistics
        """
        if not self.user_timezones:
            return {
                "total_users": 0,
                "timezones_count": 0,
                "timezone_distribution": {},
                "detection_methods": {},
                "coverage_regions": {}
            }
        
        # Count timezone distribution
        tz_distribution = {}
        method_distribution = {}
        region_distribution = {}
        
        for tz_info in self.user_timezones.values():
            # Timezone distribution
            tz_name = tz_info.timezone
            tz_distribution[tz_name] = tz_distribution.get(tz_name, 0) + 1
            
            # Detection method distribution
            method = tz_info.detected_method
            method_distribution[method] = method_distribution.get(method, 0) + 1
            
            # Region distribution
            region = tz_name.split('/')[0] if '/' in tz_name else 'Unknown'
            region_distribution[region] = region_distribution.get(region, 0) + 1
        
        return {
            "total_users": len(self.user_timezones),
            "timezones_count": len(tz_distribution),
            "timezone_distribution": dict(sorted(tz_distribution.items(), 
                                               key=lambda x: x[1], reverse=True)),
            "detection_methods": method_distribution,
            "coverage_regions": region_distribution,
            "groups_count": len(self.timezone_groups),
            "scheduled_deliveries": len(self.delivery_schedules)
        }
    
    def cleanup_old_schedules(self, hours_past: int = 24) -> int:
        """
        Clean up old delivery schedules.
        
        Args:
            hours_past: Remove schedules older than this many hours
            
        Returns:
            Number of schedules removed
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_past)
        
        old_count = len(self.delivery_schedules)
        self.delivery_schedules = [
            schedule for schedule in self.delivery_schedules
            if schedule.delivery_time_utc >= cutoff
        ]
        
        removed_count = old_count - len(self.delivery_schedules)
        
        if removed_count > 0:
            logger.info(f"Cleaned up {removed_count} old delivery schedules")
        
        return removed_count


# Global timezone manager instance
_timezone_manager = None

def get_timezone_manager() -> TimezoneManager:
    """Get global timezone manager instance."""
    global _timezone_manager
    if _timezone_manager is None:
        _timezone_manager = TimezoneManager()
    return _timezone_manager