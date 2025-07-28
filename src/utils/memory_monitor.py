"""
Memory Monitoring Utility with Configurable Thresholds

This module provides comprehensive memory monitoring capabilities with configurable
thresholds, alerts, and automatic cleanup triggers for the LINE Bot application.
"""

import psutil
import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass
from enum import Enum
import gc
import os
import sys
import json

logger = logging.getLogger(__name__)


class MemoryAlertLevel(Enum):
    """Memory alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


@dataclass
class MemoryStats:
    """Memory usage statistics"""
    total_memory: int
    available_memory: int
    used_memory: int
    memory_percent: float
    swap_total: int
    swap_used: int
    swap_percent: float
    process_memory: int
    process_memory_percent: float
    timestamp: datetime


@dataclass
class MemoryThreshold:
    """Memory threshold configuration"""
    level: MemoryAlertLevel
    memory_percent: float
    swap_percent: float
    process_memory_mb: Optional[int] = None
    callback: Optional[Callable] = None
    description: str = ""


@dataclass
class MemoryAlert:
    """Memory alert notification"""
    alert_id: str
    level: MemoryAlertLevel
    title: str
    message: str
    memory_stats: MemoryStats
    threshold: MemoryThreshold
    timestamp: datetime
    acknowledged: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert alert to dictionary for serialization."""
        return {
            'alert_id': self.alert_id,
            'level': self.level.value,
            'title': self.title,
            'message': self.message,
            'memory_percent': self.memory_stats.memory_percent,
            'swap_percent': self.memory_stats.swap_percent,
            'process_memory_mb': self.memory_stats.process_memory / (1024**2),
            'threshold_percent': self.threshold.memory_percent,
            'threshold_description': self.threshold.description,
            'timestamp': self.timestamp.isoformat(),
            'acknowledged': self.acknowledged
        }


class MemoryMonitor:
    """
    Comprehensive memory monitoring utility with configurable thresholds and alerts.
    
    Features:
    - Real-time memory usage monitoring
    - Configurable threshold-based alerts
    - Process-specific memory tracking
    - Automatic cleanup triggers
    - Memory pressure detection
    - Historical usage tracking
    - Thread-safe operations
    """
    
    def __init__(self, 
                 monitoring_interval: int = 30,
                 history_retention_hours: int = 24,
                 enable_process_monitoring: bool = True,
                 enable_system_monitoring: bool = True,
                 enable_automatic_cleanup: bool = True):
        """
        Initialize memory monitor.
        
        Args:
            monitoring_interval: Seconds between memory checks
            history_retention_hours: Hours to retain memory history
            enable_process_monitoring: Whether to monitor process-specific memory
            enable_system_monitoring: Whether to monitor system-wide memory
            enable_automatic_cleanup: Whether to trigger automatic cleanup
        """
        self.monitoring_interval = monitoring_interval
        self.history_retention_hours = history_retention_hours
        self.enable_process_monitoring = enable_process_monitoring
        self.enable_system_monitoring = enable_system_monitoring
        self.enable_automatic_cleanup = enable_automatic_cleanup
        
        # Threading and control
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.RLock()
        self._is_monitoring = False
        
        # Current process information
        self._process = psutil.Process(os.getpid())
        
        # Memory thresholds (default configuration)
        self._thresholds: List[MemoryThreshold] = []
        self._setup_default_thresholds()
        
        # Memory history and statistics
        self._memory_history: List[MemoryStats] = []
        self._alert_history: List[Dict[str, Any]] = []
        self._last_cleanup_time: Optional[datetime] = None
        
        # Cleanup callbacks
        self._cleanup_callbacks: List[Callable] = []
        
        # Alert management
        self._active_alerts: Dict[str, MemoryAlert] = {}
        self._alert_callbacks: List[Callable[[MemoryAlert], None]] = []
        self._last_alert_times: Dict[MemoryAlertLevel, datetime] = {}
        self._alert_cooldown_minutes = 5  # Prevent spam alerts
        
        # Performance tracking
        self._stats = {
            'monitoring_cycles': 0,
            'alerts_triggered': 0,
            'cleanup_operations': 0,
            'memory_pressure_events': 0,
            'last_memory_check': None,
            'average_memory_usage': 0.0,
            'peak_memory_usage': 0.0,
            'total_alerts_sent': 0,
            'alerts_acknowledged': 0
        }
        
        logger.info("MemoryMonitor initialized with default thresholds")
    
    def _setup_default_thresholds(self):
        """Setup default memory thresholds."""
        self._thresholds = [
            MemoryThreshold(
                level=MemoryAlertLevel.INFO,
                memory_percent=50.0,
                swap_percent=10.0,
                description="Memory usage is moderate"
            ),
            MemoryThreshold(
                level=MemoryAlertLevel.WARNING,
                memory_percent=70.0,
                swap_percent=25.0,
                callback=self._trigger_light_cleanup,
                description="Memory usage is high - triggering light cleanup"
            ),
            MemoryThreshold(
                level=MemoryAlertLevel.CRITICAL,
                memory_percent=90.0,
                swap_percent=50.0,
                callback=self._trigger_aggressive_cleanup,
                description="Memory usage is critical - triggering aggressive cleanup"
            ),
            MemoryThreshold(
                level=MemoryAlertLevel.EMERGENCY,
                memory_percent=95.0,
                swap_percent=75.0,
                callback=self._trigger_emergency_cleanup,
                description="Memory usage is at emergency levels"
            )
        ]
    
    def add_threshold(self, threshold: MemoryThreshold):
        """Add a custom memory threshold."""
        with self._lock:
            self._thresholds.append(threshold)
            # Sort thresholds by memory percent for efficient checking
            self._thresholds.sort(key=lambda t: t.memory_percent)
            logger.info(f"Added memory threshold: {threshold.level.value} at {threshold.memory_percent}%")
    
    def remove_threshold(self, level: MemoryAlertLevel):
        """Remove a memory threshold by level."""
        with self._lock:
            self._thresholds = [t for t in self._thresholds if t.level != level]
            logger.info(f"Removed memory threshold: {level.value}")
    
    def add_cleanup_callback(self, callback: Callable):
        """Add a callback function to be called during cleanup operations."""
        with self._lock:
            self._cleanup_callbacks.append(callback)
            logger.debug(f"Added cleanup callback: {getattr(callback, '__name__', str(callback))}")
    
    def add_alert_callback(self, callback: Callable[[MemoryAlert], None]):
        """Add a callback function to be called when memory alerts are triggered."""
        with self._lock:
            self._alert_callbacks.append(callback)
            logger.debug(f"Added alert callback: {getattr(callback, '__name__', str(callback))}")
    
    def remove_alert_callback(self, callback: Callable[[MemoryAlert], None]):
        """Remove an alert callback function."""
        with self._lock:
            if callback in self._alert_callbacks:
                self._alert_callbacks.remove(callback)
                logger.debug(f"Removed alert callback: {getattr(callback, '__name__', str(callback))}")
    
    def get_active_alerts(self) -> List[MemoryAlert]:
        """Get all currently active memory alerts."""
        with self._lock:
            return list(self._active_alerts.values())
    
    def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge a memory alert by ID."""
        with self._lock:
            if alert_id in self._active_alerts:
                self._active_alerts[alert_id].acknowledged = True
                self._stats['alerts_acknowledged'] += 1
                logger.info(f"Acknowledged memory alert: {alert_id}")
                return True
            return False
    
    def clear_acknowledged_alerts(self):
        """Clear all acknowledged alerts from active alerts."""
        with self._lock:
            cleared_count = 0
            for alert_id in list(self._active_alerts.keys()):
                if self._active_alerts[alert_id].acknowledged:
                    del self._active_alerts[alert_id]
                    cleared_count += 1
            
            if cleared_count > 0:
                logger.info(f"Cleared {cleared_count} acknowledged alerts")
    
    def set_alert_cooldown(self, minutes: int):
        """Set the cooldown period for alerts to prevent spam."""
        with self._lock:
            self._alert_cooldown_minutes = minutes
            logger.info(f"Alert cooldown set to {minutes} minutes")
    
    def start_monitoring(self):
        """Start the background memory monitoring thread."""
        with self._lock:
            if self._is_monitoring:
                logger.warning("Memory monitoring is already running")
                return
            
            self._stop_event.clear()
            self._monitor_thread = threading.Thread(
                target=self._monitor_loop,
                name="memory-monitor",
                daemon=True
            )
            self._monitor_thread.start()
            self._is_monitoring = True
            logger.info(f"Started memory monitoring (interval: {self.monitoring_interval}s)")
    
    def stop_monitoring(self):
        """Stop the background memory monitoring thread."""
        with self._lock:
            if not self._is_monitoring:
                logger.warning("Memory monitoring is not running")
                return
            
            logger.info("Stopping memory monitoring")
            self._stop_event.set()
            
            if self._monitor_thread:
                self._monitor_thread.join(timeout=5)
                if self._monitor_thread.is_alive():
                    logger.warning("Memory monitoring thread did not stop gracefully")
                
            self._is_monitoring = False
            logger.info("Memory monitoring stopped")
    
    def _monitor_loop(self):
        """Main monitoring loop that runs in the background thread."""
        while not self._stop_event.is_set():
            try:
                # Get current memory statistics
                memory_stats = self.get_memory_stats()
                
                # Add to history
                self._add_to_history(memory_stats)
                
                # Check thresholds and trigger alerts
                self._check_thresholds(memory_stats)
                
                # Clean up old history
                self._cleanup_history()
                
                # Update statistics
                with self._lock:
                    self._stats['monitoring_cycles'] += 1
                    self._stats['last_memory_check'] = memory_stats.timestamp.isoformat()
                    
                    # Update average and peak memory usage
                    if self._memory_history:
                        avg_usage = sum(stat.memory_percent for stat in self._memory_history) / len(self._memory_history)
                        self._stats['average_memory_usage'] = avg_usage
                        self._stats['peak_memory_usage'] = max(stat.memory_percent for stat in self._memory_history)
                
            except Exception as e:
                logger.error(f"Error in memory monitoring loop: {e}")
            
            # Wait for next cycle
            self._stop_event.wait(self.monitoring_interval)
    
    def get_memory_stats(self) -> MemoryStats:
        """Get current memory usage statistics."""
        try:
            # System memory
            system_memory = psutil.virtual_memory()
            swap_memory = psutil.swap_memory()
            
            # Process memory
            process_memory = 0
            process_memory_percent = 0.0
            
            if self.enable_process_monitoring:
                try:
                    process_info = self._process.memory_info()
                    process_memory = process_info.rss  # Resident Set Size
                    process_memory_percent = self._process.memory_percent()
                except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                    logger.warning(f"Cannot access process memory info: {e}")
            
            return MemoryStats(
                total_memory=system_memory.total,
                available_memory=system_memory.available,
                used_memory=system_memory.used,
                memory_percent=system_memory.percent,
                swap_total=swap_memory.total,
                swap_used=swap_memory.used,
                swap_percent=swap_memory.percent,
                process_memory=process_memory,
                process_memory_percent=process_memory_percent,
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Error getting memory statistics: {e}")
            # Return empty stats with current timestamp
            return MemoryStats(
                total_memory=0, available_memory=0, used_memory=0, memory_percent=0.0,
                swap_total=0, swap_used=0, swap_percent=0.0,
                process_memory=0, process_memory_percent=0.0,
                timestamp=datetime.now()
            )
    
    def _add_to_history(self, memory_stats: MemoryStats):
        """Add memory statistics to history."""
        with self._lock:
            self._memory_history.append(memory_stats)
            
            # Limit history size to prevent memory leaks
            max_history_size = (self.history_retention_hours * 3600) // self.monitoring_interval
            if len(self._memory_history) > max_history_size:
                self._memory_history = self._memory_history[-max_history_size:]
    
    def _cleanup_history(self):
        """Remove old entries from memory history."""
        cutoff_time = datetime.now() - timedelta(hours=self.history_retention_hours)
        
        with self._lock:
            self._memory_history = [
                stat for stat in self._memory_history 
                if stat.timestamp > cutoff_time
            ]
            
            self._alert_history = [
                alert for alert in self._alert_history
                if datetime.fromisoformat(alert['timestamp']) > cutoff_time
            ]
    
    def _check_thresholds(self, memory_stats: MemoryStats):
        """Check memory statistics against configured thresholds."""
        for threshold in reversed(self._thresholds):  # Check highest thresholds first
            if (memory_stats.memory_percent >= threshold.memory_percent or
                memory_stats.swap_percent >= threshold.swap_percent):
                
                # Check if we need to consider process memory
                process_check = True
                if threshold.process_memory_mb is not None:
                    process_memory_mb = memory_stats.process_memory / (1024 * 1024)
                    process_check = process_memory_mb >= threshold.process_memory_mb
                
                if process_check:
                    self._trigger_alert(threshold, memory_stats)
                    break  # Only trigger the highest matching threshold
    
    def _trigger_alert(self, threshold: MemoryThreshold, memory_stats: MemoryStats):
        """Trigger a memory alert and execute associated actions."""
        # Check cooldown to prevent spam alerts
        now = datetime.now()
        if threshold.level in self._last_alert_times:
            time_since_last = now - self._last_alert_times[threshold.level]
            if time_since_last.total_seconds() < (self._alert_cooldown_minutes * 60):
                return  # Still in cooldown period
        
        # Create alert notification
        alert_id = f"memory_{threshold.level.value}_{int(now.timestamp())}"
        title = f"Memory Usage Alert - {threshold.level.value.upper()}"
        message = self._format_alert_message(threshold, memory_stats)
        
        alert = MemoryAlert(
            alert_id=alert_id,
            level=threshold.level,
            title=title,
            message=message,
            memory_stats=memory_stats,
            threshold=threshold,
            timestamp=now
        )
        
        # Legacy alert info for backward compatibility
        alert_info = {
            'alert_id': alert_id,
            'level': threshold.level.value,
            'memory_percent': memory_stats.memory_percent,
            'swap_percent': memory_stats.swap_percent,
            'process_memory_mb': memory_stats.process_memory / (1024 * 1024),
            'description': threshold.description,
            'timestamp': memory_stats.timestamp.isoformat()
        }
        
        with self._lock:
            # Add to active alerts (remove any existing alert of the same level)
            existing_alert_id = None
            for aid, existing_alert in self._active_alerts.items():
                if existing_alert.level == threshold.level:
                    existing_alert_id = aid
                    break
            
            if existing_alert_id:
                del self._active_alerts[existing_alert_id]
            
            self._active_alerts[alert_id] = alert
            self._alert_history.append(alert_info)
            self._stats['alerts_triggered'] += 1
            self._stats['total_alerts_sent'] += 1
            self._last_alert_times[threshold.level] = now
        
        process_memory_mb = memory_stats.process_memory / (1024 * 1024)
        logger.warning(
            f"Memory alert [{threshold.level.value}]: {threshold.description} "
            f"(Memory: {memory_stats.memory_percent:.1f}%, "
            f"Swap: {memory_stats.swap_percent:.1f}%, "
            f"Process: {process_memory_mb:.1f}MB)"
        )
        
        # Send alert notifications
        self._send_alert_notifications(alert)
        
        # Execute threshold callback if available
        if threshold.callback:
            try:
                threshold.callback(memory_stats, alert_info)
            except Exception as e:
                logger.error(f"Error executing threshold callback: {e}")
    
    def _format_alert_message(self, threshold: MemoryThreshold, memory_stats: MemoryStats) -> str:
        """Format a human-readable alert message."""
        process_memory_mb = memory_stats.process_memory / (1024 * 1024)
        memory_gb = memory_stats.used_memory / (1024**3)
        available_gb = memory_stats.available_memory / (1024**3)
        
        return (
            f"Memory usage has reached {threshold.level.value} levels.\n"
            f"Current usage: {memory_stats.memory_percent:.1f}% "
            f"({memory_gb:.1f}GB used, {available_gb:.1f}GB available)\n"
            f"Swap usage: {memory_stats.swap_percent:.1f}%\n"
            f"Process memory: {process_memory_mb:.1f}MB\n"
            f"Threshold: {threshold.memory_percent}% ({threshold.description})\n"
            f"Time: {memory_stats.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
        )
    
    def _send_alert_notifications(self, alert: MemoryAlert):
        """Send alert notifications to registered callbacks."""
        for callback in self._alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                logger.error(f"Error in alert callback: {e}")
    
    def _trigger_light_cleanup(self, memory_stats: MemoryStats, alert_info: Dict[str, Any]):
        """Trigger light cleanup operations."""
        if not self.enable_automatic_cleanup:
            return
        
        logger.info("Triggering light memory cleanup")
        
        try:
            # Force garbage collection
            gc.collect()
            
            # Execute registered cleanup callbacks
            for callback in self._cleanup_callbacks:
                try:
                    callback("light", memory_stats)
                except Exception as e:
                    logger.error(f"Error in cleanup callback: {e}")
            
            with self._lock:
                self._stats['cleanup_operations'] += 1
                self._last_cleanup_time = datetime.now()
            
            logger.info("Light memory cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during light cleanup: {e}")
    
    def _trigger_aggressive_cleanup(self, memory_stats: MemoryStats, alert_info: Dict[str, Any]):
        """Trigger aggressive cleanup operations."""
        if not self.enable_automatic_cleanup:
            return
        
        logger.warning("Triggering aggressive memory cleanup")
        
        try:
            # First do light cleanup
            self._trigger_light_cleanup(memory_stats, alert_info)
            
            # Execute aggressive cleanup callbacks
            for callback in self._cleanup_callbacks:
                try:
                    callback("aggressive", memory_stats)
                except Exception as e:
                    logger.error(f"Error in aggressive cleanup callback: {e}")
            
            # Force multiple garbage collection cycles
            for _ in range(3):
                gc.collect()
            
            with self._lock:
                self._stats['memory_pressure_events'] += 1
            
            logger.warning("Aggressive memory cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during aggressive cleanup: {e}")
    
    def _trigger_emergency_cleanup(self, memory_stats: MemoryStats, alert_info: Dict[str, Any]):
        """Trigger emergency cleanup operations."""
        logger.critical("EMERGENCY: Memory usage at critical levels - triggering emergency cleanup")
        
        try:
            # First do aggressive cleanup
            self._trigger_aggressive_cleanup(memory_stats, alert_info)
            
            # Execute emergency cleanup callbacks
            for callback in self._cleanup_callbacks:
                try:
                    callback("emergency", memory_stats)
                except Exception as e:
                    logger.error(f"Error in emergency cleanup callback: {e}")
            
            # Clear internal history to free memory
            with self._lock:
                self._memory_history = self._memory_history[-10:]  # Keep only last 10 entries
                self._alert_history = self._alert_history[-10:]    # Keep only last 10 alerts
            
            logger.critical("Emergency memory cleanup completed")
            
        except Exception as e:
            logger.critical(f"CRITICAL ERROR during emergency cleanup: {e}")
    
    def get_memory_usage_summary(self) -> Dict[str, Any]:
        """Get a comprehensive summary of current memory usage."""
        current_stats = self.get_memory_stats()
        
        with self._lock:
            summary = {
                'current': {
                    'memory_percent': current_stats.memory_percent,
                    'memory_used_gb': current_stats.used_memory / (1024**3),
                    'memory_available_gb': current_stats.available_memory / (1024**3),
                    'memory_total_gb': current_stats.total_memory / (1024**3),
                    'swap_percent': current_stats.swap_percent,
                    'swap_used_gb': current_stats.swap_used / (1024**3),
                    'process_memory_mb': current_stats.process_memory / (1024**2),
                    'process_memory_percent': current_stats.process_memory_percent
                },
                'statistics': self._stats.copy(),
                'monitoring': {
                    'is_monitoring': self._is_monitoring,
                    'monitoring_interval': self.monitoring_interval,
                    'history_retention_hours': self.history_retention_hours,
                    'history_entries': len(self._memory_history),
                    'alert_entries': len(self._alert_history)
                },
                'thresholds': [
                    {
                        'level': t.level.value,
                        'memory_percent': t.memory_percent,
                        'swap_percent': t.swap_percent,
                        'description': t.description
                    }
                    for t in self._thresholds
                ],
                'recent_alerts': self._alert_history[-5:] if self._alert_history else [],
                'active_alerts': [alert.to_dict() for alert in self._active_alerts.values()],
                'total_active_alerts': len(self._active_alerts),
                'total_acknowledged_alerts': len([a for a in self._active_alerts.values() if a.acknowledged])
            }
        
        return summary
    
    def get_memory_history(self, hours: int = 1) -> List[Dict[str, Any]]:
        """Get memory usage history for the specified number of hours."""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        with self._lock:
            recent_history = [
                {
                    'timestamp': stat.timestamp.isoformat(),
                    'memory_percent': stat.memory_percent,
                    'swap_percent': stat.swap_percent,
                    'process_memory_mb': stat.process_memory / (1024**2)
                }
                for stat in self._memory_history
                if stat.timestamp > cutoff_time
            ]
        
        return recent_history
    
    def force_cleanup(self, level: str = "aggressive"):
        """Manually trigger cleanup operations."""
        logger.info(f"Manually triggering {level} cleanup")
        
        current_stats = self.get_memory_stats()
        alert_info = {
            'level': 'manual',
            'timestamp': datetime.now().isoformat(),
            'description': f'Manual {level} cleanup triggered'
        }
        
        if level == "light":
            self._trigger_light_cleanup(current_stats, alert_info)
        elif level == "aggressive":
            self._trigger_aggressive_cleanup(current_stats, alert_info)
        elif level == "emergency":
            self._trigger_emergency_cleanup(current_stats, alert_info)
        else:
            logger.error(f"Unknown cleanup level: {level}")
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get health status of the memory monitor."""
        current_stats = self.get_memory_stats()
        
        # Determine overall health
        health_status = "healthy"
        if current_stats.memory_percent >= 90:
            health_status = "critical"
        elif current_stats.memory_percent >= 70:
            health_status = "warning"
        elif current_stats.memory_percent >= 50:
            health_status = "moderate"
        
        return {
            'service': 'MemoryMonitor',
            'status': health_status,
            'is_monitoring': self._is_monitoring,
            'current_memory_percent': current_stats.memory_percent,
            'current_swap_percent': current_stats.swap_percent,
            'last_cleanup': self._last_cleanup_time.isoformat() if self._last_cleanup_time else None,
            'total_alerts': len(self._alert_history),
            'recent_alerts': len([a for a in self._alert_history if datetime.fromisoformat(a['timestamp']) > datetime.now() - timedelta(hours=1)]),
            'cleanup_operations': self._stats['cleanup_operations'],
            'monitoring_cycles': self._stats['monitoring_cycles']
        }


# Global memory monitor instance
_global_memory_monitor: Optional[MemoryMonitor] = None
_monitor_lock = threading.Lock()


def get_memory_monitor(**kwargs) -> MemoryMonitor:
    """Get global memory monitor instance (singleton pattern)."""
    global _global_memory_monitor
    
    with _monitor_lock:
        if _global_memory_monitor is None:
            _global_memory_monitor = MemoryMonitor(**kwargs)
        
        return _global_memory_monitor


def reset_global_monitor():
    """Reset global memory monitor (mainly for testing)."""
    global _global_memory_monitor
    
    with _monitor_lock:
        if _global_memory_monitor:
            _global_memory_monitor.stop_monitoring()
            _global_memory_monitor = None