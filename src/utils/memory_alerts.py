"""
Memory Alert Handlers for the LINE Bot Application

This module provides alert handlers for memory usage notifications,
including logging, file storage, and potential external notifications.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

from src.utils.memory_monitor import MemoryAlert, MemoryAlertLevel

logger = logging.getLogger(__name__)


class MemoryAlertHandler:
    """
    Handles memory alerts with configurable notification methods.
    
    Provides multiple alert handling strategies:
    - Console/log notifications
    - File-based alert storage  
    - External notification hooks (future extension)
    """
    
    def __init__(self, 
                 enable_file_logging: bool = True,
                 alerts_directory: str = "logs/memory_alerts",
                 enable_console_alerts: bool = True,
                 critical_alert_file: Optional[str] = None):
        """
        Initialize memory alert handler.
        
        Args:
            enable_file_logging: Whether to save alerts to files
            alerts_directory: Directory to store alert files
            enable_console_alerts: Whether to log alerts to console
            critical_alert_file: File to store only critical/emergency alerts
        """
        self.enable_file_logging = enable_file_logging
        self.alerts_directory = Path(alerts_directory)
        self.enable_console_alerts = enable_console_alerts
        self.critical_alert_file = critical_alert_file
        
        # Create alerts directory if needed
        if self.enable_file_logging:
            self.alerts_directory.mkdir(parents=True, exist_ok=True)
            logger.info(f"Memory alerts directory created: {self.alerts_directory}")
        
        # Alert statistics
        self.alert_counts = {
            'info': 0,
            'warning': 0,
            'critical': 0,
            'emergency': 0,
            'total': 0
        }
        
        logger.info("MemoryAlertHandler initialized")
    
    def handle_alert(self, alert: MemoryAlert):
        """
        Main alert handling method - processes incoming memory alerts.
        
        Args:
            alert: MemoryAlert object to handle
        """
        try:
            # Update statistics
            self.alert_counts[alert.level.value] += 1
            self.alert_counts['total'] += 1
            
            # Handle alert based on severity
            if alert.level in [MemoryAlertLevel.CRITICAL, MemoryAlertLevel.EMERGENCY]:
                self._handle_critical_alert(alert)
            else:
                self._handle_standard_alert(alert)
            
            # Log to console if enabled
            if self.enable_console_alerts:
                self._log_console_alert(alert)
            
            # Save to file if enabled
            if self.enable_file_logging:
                self._save_alert_to_file(alert)
            
            logger.debug(f"Processed memory alert: {alert.alert_id}")
            
        except Exception as e:
            logger.error(f"Error handling memory alert {alert.alert_id}: {e}")
    
    def _handle_critical_alert(self, alert: MemoryAlert):
        """Handle critical and emergency level alerts with special attention."""
        # Log critical alert with higher severity
        logger.critical(f"CRITICAL MEMORY ALERT: {alert.title}")
        logger.critical(f"Message: {alert.message}")
        
        # Save to critical alerts file if specified
        if self.critical_alert_file:
            try:
                critical_file = Path(self.critical_alert_file)
                critical_file.parent.mkdir(parents=True, exist_ok=True)
                
                alert_data = {
                    **alert.to_dict(),
                    'handled_at': datetime.now().isoformat(),
                    'handler': 'MemoryAlertHandler'
                }
                
                # Append to critical alerts file
                with open(critical_file, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(alert_data) + '\n')
                
                logger.info(f"Critical alert saved to: {critical_file}")
                
            except Exception as e:
                logger.error(f"Error saving critical alert to file: {e}")
        
        # Future: Add external notification hooks here
        # - Email notifications
        # - Slack/Discord alerts
        # - SMS notifications
        # - Monitoring system integration
    
    def _handle_standard_alert(self, alert: MemoryAlert):
        """Handle standard warning and info level alerts."""
        if alert.level == MemoryAlertLevel.WARNING:
            logger.warning(f"MEMORY WARNING: {alert.title}")
        else:
            logger.info(f"MEMORY INFO: {alert.title}")
    
    def _log_console_alert(self, alert: MemoryAlert):
        """Log alert details to console with appropriate formatting."""
        separator = "=" * 60
        alert_lines = [
            "",
            separator,
            f"MEMORY ALERT - {alert.level.value.upper()}",
            separator,
            f"Alert ID: {alert.alert_id}",
            f"Time: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Memory Usage: {alert.memory_stats.memory_percent:.1f}%",
            f"Swap Usage: {alert.memory_stats.swap_percent:.1f}%",
            f"Process Memory: {alert.memory_stats.process_memory / (1024**2):.1f}MB",
            f"Threshold: {alert.threshold.memory_percent}%",
            "",
            "Description:",
            alert.message,
            separator,
            ""
        ]
        
        alert_text = "\n".join(alert_lines)
        
        # Log with appropriate level
        if alert.level == MemoryAlertLevel.EMERGENCY:
            logger.critical(alert_text)
        elif alert.level == MemoryAlertLevel.CRITICAL:
            logger.error(alert_text)
        elif alert.level == MemoryAlertLevel.WARNING:
            logger.warning(alert_text)
        else:
            logger.info(alert_text)
    
    def _save_alert_to_file(self, alert: MemoryAlert):
        """Save alert to a timestamped file."""
        try:
            # Create filename with timestamp and alert level
            timestamp = alert.timestamp.strftime('%Y%m%d_%H%M%S')
            filename = f"memory_alert_{alert.level.value}_{timestamp}_{alert.alert_id[-8:]}.json"
            filepath = self.alerts_directory / filename
            
            # Prepare alert data for storage
            alert_data = {
                **alert.to_dict(),
                'handled_at': datetime.now().isoformat(),
                'handler': 'MemoryAlertHandler',
                'system_info': {
                    'pid': os.getpid(),
                    'cwd': os.getcwd()
                }
            }
            
            # Save to file
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(alert_data, f, indent=2, ensure_ascii=False)
            
            logger.debug(f"Alert saved to file: {filepath}")
            
        except Exception as e:
            logger.error(f"Error saving alert to file: {e}")
    
    def get_alert_statistics(self) -> Dict[str, Any]:
        """Get statistics about handled alerts."""
        return {
            'alert_counts': self.alert_counts.copy(),
            'alerts_directory': str(self.alerts_directory) if self.enable_file_logging else None,
            'critical_alert_file': self.critical_alert_file,
            'file_logging_enabled': self.enable_file_logging,
            'console_alerts_enabled': self.enable_console_alerts
        }
    
    def clear_alert_files(self, older_than_days: int = 7):
        """Clear old alert files to prevent disk space issues."""
        if not self.enable_file_logging:
            return
        
        try:
            cutoff_time = datetime.now().timestamp() - (older_than_days * 24 * 3600)
            cleared_count = 0
            
            for alert_file in self.alerts_directory.glob("memory_alert_*.json"):
                if alert_file.stat().st_mtime < cutoff_time:
                    alert_file.unlink()
                    cleared_count += 1
            
            if cleared_count > 0:
                logger.info(f"Cleared {cleared_count} old alert files (older than {older_than_days} days)")
        
        except Exception as e:
            logger.error(f"Error clearing old alert files: {e}")


def create_default_alert_handler() -> MemoryAlertHandler:
    """Create a default memory alert handler with standard configuration."""
    return MemoryAlertHandler(
        enable_file_logging=True,
        alerts_directory="logs/memory_alerts",
        enable_console_alerts=True,
        critical_alert_file="logs/critical_memory_alerts.jsonl"
    )


def setup_memory_alerting():
    """Set up memory alerting with the global memory monitor."""
    from src.utils.memory_monitor import get_memory_monitor
    
    try:
        # Get the global memory monitor
        monitor = get_memory_monitor()
        
        # Create alert handler
        alert_handler = create_default_alert_handler()
        
        # Register the alert handler
        monitor.add_alert_callback(alert_handler.handle_alert)
        
        # Start monitoring if not already started
        if not monitor._is_monitoring:
            monitor.start_monitoring()
        
        logger.info("Memory alerting system configured successfully")
        return alert_handler
        
    except Exception as e:
        logger.error(f"Error setting up memory alerting: {e}")
        return None