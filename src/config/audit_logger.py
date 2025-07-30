"""
Configuration Audit Logging and Change Tracking

This module provides comprehensive audit logging for configuration changes,
tracking who made changes, when they were made, and what was changed.
"""

import os
import json
import logging
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum

from src.config.centralized_config import CentralizedConfig, get_config

logger = logging.getLogger(__name__)


class AuditEventType(str, Enum):
    """Types of configuration audit events"""
    CONFIG_LOADED = "config_loaded"
    CONFIG_RELOADED = "config_reloaded"
    CONFIG_VALIDATED = "config_validated"
    CONFIG_CHANGED = "config_changed"
    CONFIG_ROLLBACK = "config_rollback"
    CONFIG_EXPORT = "config_export"
    CONFIG_IMPORT = "config_import"
    VALIDATION_FAILED = "validation_failed"
    ACCESS_GRANTED = "access_granted"
    ACCESS_DENIED = "access_denied"
    SCHEMA_VIOLATION = "schema_violation"


class AuditLevel(str, Enum):
    """Audit log levels"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ConfigurationChange:
    """Represents a configuration change"""
    field_path: str
    old_value: Any
    new_value: Any
    change_type: str  # added, modified, removed
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'field_path': self.field_path,
            'old_value': str(self.old_value) if self.old_value is not None else None,
            'new_value': str(self.new_value) if self.new_value is not None else None,
            'change_type': self.change_type
        }


@dataclass
class AuditEvent:
    """Represents a configuration audit event"""
    event_id: str
    timestamp: datetime
    event_type: AuditEventType
    level: AuditLevel
    user_id: str
    session_id: str
    ip_address: str
    user_agent: str
    message: str
    config_version: str
    changes: List[ConfigurationChange]
    metadata: Dict[str, Any]
    source_file: str = ""
    line_number: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'event_id': self.event_id,
            'timestamp': self.timestamp.isoformat(),
            'event_type': self.event_type.value,
            'level': self.level.value,
            'user_id': self.user_id,
            'session_id': self.session_id,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'message': self.message,
            'config_version': self.config_version,
            'changes': [change.to_dict() for change in self.changes],
            'metadata': self.metadata,
            'source_file': self.source_file,
            'line_number': self.line_number
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AuditEvent':
        """Create from dictionary"""
        changes = [
            ConfigurationChange(
                field_path=change['field_path'],
                old_value=change['old_value'],
                new_value=change['new_value'],
                change_type=change['change_type']
            )
            for change in data.get('changes', [])
        ]
        
        return cls(
            event_id=data['event_id'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            event_type=AuditEventType(data['event_type']),
            level=AuditLevel(data['level']),
            user_id=data['user_id'],
            session_id=data['session_id'],
            ip_address=data['ip_address'],
            user_agent=data['user_agent'],
            message=data['message'],
            config_version=data['config_version'],
            changes=changes,
            metadata=data.get('metadata', {}),
            source_file=data.get('source_file', ''),
            line_number=data.get('line_number', 0)
        )


class ConfigurationAuditLogger:
    """
    Configuration audit logger with comprehensive change tracking.
    
    This class provides detailed audit logging for all configuration-related
    activities, including changes, access, validation, and administrative actions.
    """
    
    def __init__(self, log_dir: str = "config_audit_logs"):
        """
        Initialize the configuration audit logger.
        
        Args:
            log_dir: Directory to store audit logs
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
        self.current_log_file = self.log_dir / f"config_audit_{datetime.now().strftime('%Y%m%d')}.jsonl"
        self.retention_days = 365  # Keep logs for 1 year
        self.max_log_size_mb = 100  # Rotate logs at 100MB
        self.enable_console_logging = True
        self.enable_syslog = False
        
        # Current configuration state for change detection
        self.current_config_hash: Optional[str] = None
        self.current_config_dict: Optional[Dict[str, Any]] = None
        
        # Session tracking
        self.current_session_id = self._generate_session_id()
        
        # Initialize logging
        self._setup_logging()
    
    def _setup_logging(self) -> None:
        """Set up audit logging configuration"""
        # Create audit logger
        self.audit_logger = logging.getLogger("config_audit")
        self.audit_logger.setLevel(logging.DEBUG)
        
        # File handler for audit logs
        file_handler = logging.FileHandler(self.current_log_file)
        file_handler.setLevel(logging.DEBUG)
        
        # JSON formatter for structured logging
        formatter = logging.Formatter('%(message)s')
        file_handler.setFormatter(formatter)
        
        if not self.audit_logger.handlers:
            self.audit_logger.addHandler(file_handler)
        
        # Console logging if enabled
        if self.enable_console_logging:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            console_formatter = logging.Formatter(
                '[AUDIT] %(asctime)s - %(levelname)s - %(message)s'
            )
            console_handler.setFormatter(console_formatter)
            if console_handler not in self.audit_logger.handlers:
                self.audit_logger.addHandler(console_handler)
    
    def _generate_session_id(self) -> str:
        """Generate a unique session ID"""
        import uuid
        return str(uuid.uuid4())[:8]
    
    def _generate_event_id(self) -> str:
        """Generate a unique event ID"""
        import uuid
        return str(uuid.uuid4())
    
    def _calculate_config_hash(self, config_dict: Dict[str, Any]) -> str:
        """Calculate hash of configuration for change detection"""
        # Remove sensitive data for hashing
        sanitized_config = self._sanitize_config_for_logging(config_dict)
        config_str = json.dumps(sanitized_config, sort_keys=True)
        return hashlib.sha256(config_str.encode()).hexdigest()[:16]
    
    def _sanitize_config_for_logging(self, config_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Remove sensitive data from configuration for logging"""
        sanitized = config_dict.copy()
        
        # Remove or mask sensitive fields
        sensitive_fields = [
            'channel_access_token', 'channel_secret', 'api_key', 'session_secret'
        ]
        
        def mask_sensitive(obj, path=""):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    current_path = f"{path}.{key}" if path else key
                    if any(sensitive in key.lower() for sensitive in sensitive_fields):
                        obj[key] = "***MASKED***"
                    else:
                        mask_sensitive(value, current_path)
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    mask_sensitive(item, f"{path}[{i}]")
        
        mask_sensitive(sanitized)
        return sanitized
    
    def _detect_changes(
        self,
        old_config: Dict[str, Any],
        new_config: Dict[str, Any],
        path: str = ""
    ) -> List[ConfigurationChange]:
        """Detect changes between two configuration dictionaries"""
        changes = []
        
        # Get all keys from both configs
        all_keys = set(old_config.keys()) | set(new_config.keys())
        
        for key in all_keys:
            current_path = f"{path}.{key}" if path else key
            
            if key not in old_config:
                # New field added
                changes.append(ConfigurationChange(
                    field_path=current_path,
                    old_value=None,
                    new_value=new_config[key],
                    change_type="added"
                ))
            elif key not in new_config:
                # Field removed
                changes.append(ConfigurationChange(
                    field_path=current_path,
                    old_value=old_config[key],
                    new_value=None,
                    change_type="removed"
                ))
            elif old_config[key] != new_config[key]:
                # Field modified
                if isinstance(old_config[key], dict) and isinstance(new_config[key], dict):
                    # Recursively check nested dictionaries
                    nested_changes = self._detect_changes(
                        old_config[key],
                        new_config[key],
                        current_path
                    )
                    changes.extend(nested_changes)
                else:
                    changes.append(ConfigurationChange(
                        field_path=current_path,
                        old_value=old_config[key],
                        new_value=new_config[key],
                        change_type="modified"
                    ))
        
        return changes
    
    def _get_caller_info(self) -> tuple:
        """Get information about the caller"""
        import inspect
        
        # Get the calling frame (skip this method and the log method)
        frame = inspect.currentframe()
        try:
            # Go up the stack to find the actual caller
            for _ in range(3):
                frame = frame.f_back
                if frame is None:
                    break
            
            if frame:
                filename = frame.f_code.co_filename
                line_number = frame.f_lineno
                return filename, line_number
            else:
                return "", 0
        finally:
            del frame
    
    def log_event(
        self,
        event_type: AuditEventType,
        level: AuditLevel,
        message: str,
        user_id: str = "system",
        changes: List[ConfigurationChange] = None,
        metadata: Dict[str, Any] = None,
        ip_address: str = "127.0.0.1",
        user_agent: str = "system"
    ) -> str:
        """
        Log a configuration audit event.
        
        Args:
            event_type: Type of audit event
            level: Audit level
            message: Human-readable message
            user_id: ID of user performing action
            changes: List of configuration changes
            metadata: Additional metadata
            ip_address: IP address of requester
            user_agent: User agent string
            
        Returns:
            str: Event ID of logged event
        """
        if changes is None:
            changes = []
        if metadata is None:
            metadata = {}
        
        # Get caller information
        source_file, line_number = self._get_caller_info()
        
        # Get current config version
        try:
            config = get_config()
            config_version = config.config_version
        except Exception:
            config_version = "unknown"
        
        # Create audit event
        event = AuditEvent(
            event_id=self._generate_event_id(),
            timestamp=datetime.now(),
            event_type=event_type,
            level=level,
            user_id=user_id,
            session_id=self.current_session_id,
            ip_address=ip_address,
            user_agent=user_agent,
            message=message,
            config_version=config_version,
            changes=changes,
            metadata=metadata,
            source_file=source_file,
            line_number=line_number
        )
        
        # Log the event
        self._write_audit_log(event)
        
        # Check if log rotation is needed
        self._check_log_rotation()
        
        return event.event_id
    
    def _write_audit_log(self, event: AuditEvent) -> None:
        """Write audit event to log file"""
        try:
            # Write as JSON Lines format
            log_line = json.dumps(event.to_dict(), default=str)
            
            with open(self.current_log_file, 'a') as f:
                f.write(log_line + '\n')
            
            # Also log to Python logger
            log_level = {
                AuditLevel.DEBUG: logging.DEBUG,
                AuditLevel.INFO: logging.INFO,
                AuditLevel.WARNING: logging.WARNING,
                AuditLevel.ERROR: logging.ERROR,
                AuditLevel.CRITICAL: logging.CRITICAL
            }.get(event.level, logging.INFO)
            
            self.audit_logger.log(log_level, f"{event.event_type.value}: {event.message}")
            
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")
    
    def _check_log_rotation(self) -> None:
        """Check if log rotation is needed"""
        try:
            if self.current_log_file.exists():
                size_mb = self.current_log_file.stat().st_size / (1024 * 1024)
                if size_mb > self.max_log_size_mb:
                    self._rotate_log()
        except Exception as e:
            logger.error(f"Error checking log rotation: {e}")
    
    def _rotate_log(self) -> None:
        """Rotate the current log file"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            rotated_name = f"config_audit_{timestamp}.jsonl"
            rotated_path = self.log_dir / rotated_name
            
            self.current_log_file.rename(rotated_path)
            
            # Create new log file
            today = datetime.now().strftime('%Y%m%d')
            self.current_log_file = self.log_dir / f"config_audit_{today}.jsonl"
            
            # Update file handler
            self._setup_logging()
            
            logger.info(f"Rotated audit log to {rotated_name}")
            
        except Exception as e:
            logger.error(f"Failed to rotate audit log: {e}")
    
    def log_config_loaded(self, config: CentralizedConfig, user_id: str = "system") -> str:
        """Log configuration loading event"""
        config_dict = self._sanitize_config_for_logging(config.to_dict())
        self.current_config_dict = config_dict
        self.current_config_hash = self._calculate_config_hash(config_dict)
        
        return self.log_event(
            event_type=AuditEventType.CONFIG_LOADED,
            level=AuditLevel.INFO,
            message=f"Configuration loaded (version: {config.config_version})",
            user_id=user_id,
            metadata={
                'config_hash': self.current_config_hash,
                'environment': config.application.environment.value
            }
        )
    
    def log_config_reloaded(self, old_config: CentralizedConfig, new_config: CentralizedConfig, user_id: str = "system") -> str:
        """Log configuration reload event with change detection"""
        old_dict = self._sanitize_config_for_logging(old_config.to_dict())
        new_dict = self._sanitize_config_for_logging(new_config.to_dict())
        
        changes = self._detect_changes(old_dict, new_dict)
        
        self.current_config_dict = new_dict
        self.current_config_hash = self._calculate_config_hash(new_dict)
        
        return self.log_event(
            event_type=AuditEventType.CONFIG_RELOADED,
            level=AuditLevel.INFO,
            message=f"Configuration reloaded ({len(changes)} changes detected)",
            user_id=user_id,
            changes=changes,
            metadata={
                'old_version': old_config.config_version,
                'new_version': new_config.config_version,
                'old_hash': self._calculate_config_hash(old_dict),
                'new_hash': self.current_config_hash
            }
        )
    
    def log_validation_result(self, is_valid: bool, issues: List, user_id: str = "system") -> str:
        """Log configuration validation result"""
        if is_valid:
            return self.log_event(
                event_type=AuditEventType.CONFIG_VALIDATED,
                level=AuditLevel.INFO,
                message="Configuration validation passed",
                user_id=user_id,
                metadata={'issues_count': len(issues)}
            )
        else:
            return self.log_event(
                event_type=AuditEventType.VALIDATION_FAILED,
                level=AuditLevel.ERROR,
                message=f"Configuration validation failed ({len(issues)} issues)",
                user_id=user_id,
                metadata={
                    'issues_count': len(issues),
                    'issues': [str(issue) for issue in issues[:10]]  # Limit to first 10
                }
            )
    
    def log_access_attempt(self, user_id: str, action: str, granted: bool, reason: str = "", ip_address: str = "127.0.0.1") -> str:
        """Log configuration access attempt"""
        event_type = AuditEventType.ACCESS_GRANTED if granted else AuditEventType.ACCESS_DENIED
        level = AuditLevel.INFO if granted else AuditLevel.WARNING
        
        return self.log_event(
            event_type=event_type,
            level=level,
            message=f"Configuration access {'granted' if granted else 'denied'} for action: {action}",
            user_id=user_id,
            ip_address=ip_address,
            metadata={
                'action': action,
                'granted': granted,
                'reason': reason
            }
        )
    
    def log_rollback(self, target_version: str, user_id: str = "system") -> str:
        """Log configuration rollback event"""
        return self.log_event(
            event_type=AuditEventType.CONFIG_ROLLBACK,
            level=AuditLevel.WARNING,
            message=f"Configuration rolled back to version: {target_version}",
            user_id=user_id,
            metadata={'target_version': target_version}
        )
    
    def search_audit_logs(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        event_types: List[AuditEventType] = None,
        user_id: str = None,
        limit: int = 100
    ) -> List[AuditEvent]:
        """
        Search audit logs with filters.
        
        Args:
            start_date: Start date for search
            end_date: End date for search
            event_types: List of event types to filter
            user_id: User ID to filter
            limit: Maximum number of results
            
        Returns:
            List of matching audit events
        """
        events = []
        
        # Get all log files in date range
        log_files = list(self.log_dir.glob("config_audit_*.jsonl"))
        log_files.sort(reverse=True)  # Most recent first
        
        for log_file in log_files:
            if len(events) >= limit:
                break
            
            try:
                with open(log_file, 'r') as f:
                    for line in f:
                        if len(events) >= limit:
                            break
                        
                        try:
                            event_data = json.loads(line.strip())
                            event = AuditEvent.from_dict(event_data)
                            
                            # Apply filters
                            if start_date and event.timestamp < start_date:
                                continue
                            if end_date and event.timestamp > end_date:
                                continue
                            if event_types and event.event_type not in event_types:
                                continue
                            if user_id and event.user_id != user_id:
                                continue
                            
                            events.append(event)
                            
                        except (json.JSONDecodeError, KeyError) as e:
                            logger.warning(f"Skipping invalid audit log line: {e}")
                            continue
                            
            except Exception as e:
                logger.error(f"Error reading audit log file {log_file}: {e}")
                continue
        
        return events[:limit]
    
    def get_audit_statistics(self) -> Dict[str, Any]:
        """Get audit log statistics"""
        try:
            log_files = list(self.log_dir.glob("config_audit_*.jsonl"))
            
            stats = {
                'total_log_files': len(log_files),
                'total_events': 0,
                'events_by_type': {},
                'events_by_user': {},
                'date_range': {'start': None, 'end': None},
                'total_size_mb': 0
            }
            
            for log_file in log_files:
                file_size = log_file.stat().st_size
                stats['total_size_mb'] += file_size / (1024 * 1024)
                
                with open(log_file, 'r') as f:
                    for line in f:
                        try:
                            event_data = json.loads(line.strip())
                            stats['total_events'] += 1
                            
                            # Count by event type
                            event_type = event_data.get('event_type', 'unknown')
                            stats['events_by_type'][event_type] = stats['events_by_type'].get(event_type, 0) + 1
                            
                            # Count by user
                            user_id = event_data.get('user_id', 'unknown')
                            stats['events_by_user'][user_id] = stats['events_by_user'].get(user_id, 0) + 1
                            
                            # Track date range
                            timestamp = datetime.fromisoformat(event_data['timestamp'])
                            if stats['date_range']['start'] is None or timestamp < stats['date_range']['start']:
                                stats['date_range']['start'] = timestamp
                            if stats['date_range']['end'] is None or timestamp > stats['date_range']['end']:
                                stats['date_range']['end'] = timestamp
                                
                        except (json.JSONDecodeError, KeyError):
                            continue
            
            # Convert datetime objects to ISO strings for JSON serialization
            if stats['date_range']['start']:
                stats['date_range']['start'] = stats['date_range']['start'].isoformat()
            if stats['date_range']['end']:
                stats['date_range']['end'] = stats['date_range']['end'].isoformat()
            
            stats['total_size_mb'] = round(stats['total_size_mb'], 2)
            
            return stats
            
        except Exception as e:
            logger.error(f"Error calculating audit statistics: {e}")
            return {'error': str(e)}
    
    def cleanup_old_logs(self) -> int:
        """Clean up old audit logs based on retention policy"""
        cutoff_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        cutoff_date = cutoff_date.replace(day=cutoff_date.day - self.retention_days)
        
        deleted_count = 0
        log_files = list(self.log_dir.glob("config_audit_*.jsonl"))
        
        for log_file in log_files:
            try:
                # Extract date from filename
                filename = log_file.stem
                if filename.startswith("config_audit_"):
                    date_part = filename.replace("config_audit_", "").split("_")[0]
                    file_date = datetime.strptime(date_part, "%Y%m%d")
                    
                    if file_date < cutoff_date:
                        log_file.unlink()
                        deleted_count += 1
                        logger.info(f"Deleted old audit log: {log_file.name}")
                        
            except (ValueError, OSError) as e:
                logger.warning(f"Could not process audit log file {log_file}: {e}")
                continue
        
        return deleted_count


# Global audit logger instance
_audit_logger: Optional[ConfigurationAuditLogger] = None


def get_audit_logger() -> ConfigurationAuditLogger:
    """Get the global configuration audit logger"""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = ConfigurationAuditLogger()
    return _audit_logger


def log_config_event(
    event_type: AuditEventType,
    message: str,
    user_id: str = "system",
    level: AuditLevel = AuditLevel.INFO,
    **kwargs
) -> str:
    """Log a configuration audit event"""
    audit_logger = get_audit_logger()
    return audit_logger.log_event(event_type, level, message, user_id, **kwargs)


def log_config_access(user_id: str, action: str, granted: bool, reason: str = "") -> str:
    """Log configuration access attempt"""
    audit_logger = get_audit_logger()
    return audit_logger.log_access_attempt(user_id, action, granted, reason)


def search_config_audit_logs(**kwargs) -> List[AuditEvent]:
    """Search configuration audit logs"""
    audit_logger = get_audit_logger()
    return audit_logger.search_audit_logs(**kwargs)