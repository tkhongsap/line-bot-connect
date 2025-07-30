"""
Configuration Hot-Reloading System

This module provides hot-reloading capabilities for the centralized configuration
system, allowing configuration changes to be applied without restarting the application.
"""

import os
import json
import logging
import threading
import time
from pathlib import Path
from typing import Dict, Any, Optional, Callable, List
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from datetime import datetime

from src.config.centralized_config import get_config, reload_config

logger = logging.getLogger(__name__)


class ConfigurationChangeHandler(FileSystemEventHandler):
    """Handler for configuration file changes."""
    
    def __init__(self, reload_callback: Callable[[], None], config_files: List[str]):
        """
        Initialize the handler.
        
        Args:
            reload_callback: Function to call when configuration changes
            config_files: List of configuration files to watch
        """
        self.reload_callback = reload_callback
        self.config_files = set(config_files)
        self.last_reload = datetime.now()
        self.reload_cooldown = 2.0  # Seconds to wait between reloads
        super().__init__()
    
    def on_modified(self, event):
        """Handle file modification events."""
        if event.is_directory:
            return
        
        # Check if the modified file is one we're watching
        if os.path.basename(event.src_path) in self.config_files:
            current_time = datetime.now()
            time_since_last = (current_time - self.last_reload).total_seconds()
            
            # Debounce rapid changes
            if time_since_last < self.reload_cooldown:
                logger.debug(f"Ignoring config change due to cooldown: {event.src_path}")
                return
            
            logger.info(f"Configuration file changed: {event.src_path}")
            self.last_reload = current_time
            
            try:
                self.reload_callback()
                logger.info("Configuration reloaded successfully")
            except Exception as e:
                logger.error(f"Failed to reload configuration: {e}")


class ConfigurationHotReloader:
    """
    Manages hot-reloading of configuration files.
    
    This class monitors configuration files for changes and automatically
    reloads the configuration when changes are detected.
    """
    
    def __init__(self):
        """Initialize the hot reloader."""
        self.observer: Optional[Observer] = None
        self.is_running = False
        self.config_files = ['.env', 'config.json', 'settings.json']
        self.watch_directories = ['.', 'src/config']
        self.reload_callbacks: List[Callable[[], None]] = []
        self.change_log: List[Dict[str, Any]] = []
        self.max_log_entries = 100
        self._lock = threading.Lock()
    
    def add_reload_callback(self, callback: Callable[[], None]) -> None:
        """
        Add a callback to be called when configuration is reloaded.
        
        Args:
            callback: Function to call on configuration reload
        """
        with self._lock:
            self.reload_callbacks.append(callback)
    
    def remove_reload_callback(self, callback: Callable[[], None]) -> None:
        """
        Remove a reload callback.
        
        Args:
            callback: Function to remove from callbacks
        """
        with self._lock:
            if callback in self.reload_callbacks:
                self.reload_callbacks.remove(callback)
    
    def _reload_configuration(self) -> None:
        """Reload the configuration and notify callbacks."""
        try:
            # Reload the centralized configuration
            old_config = get_config()
            new_config = reload_config()
            
            # Log the change
            change_entry = {
                'timestamp': datetime.now().isoformat(),
                'event': 'configuration_reloaded',
                'success': True,
                'config_version': new_config.config_version if new_config else 'unknown'
            }
            
            with self._lock:
                self.change_log.append(change_entry)
                if len(self.change_log) > self.max_log_entries:
                    self.change_log.pop(0)
                
                # Notify all callbacks
                for callback in self.reload_callbacks:
                    try:
                        callback()
                    except Exception as e:
                        logger.error(f"Error in reload callback: {e}")
            
            logger.info(f"Configuration reloaded successfully (version: {new_config.config_version})")
            
        except Exception as e:
            logger.error(f"Failed to reload configuration: {e}")
            
            # Log the failure
            change_entry = {
                'timestamp': datetime.now().isoformat(),
                'event': 'configuration_reload_failed',
                'success': False,
                'error': str(e)
            }
            
            with self._lock:
                self.change_log.append(change_entry)
                if len(self.change_log) > self.max_log_entries:
                    self.change_log.pop(0)
    
    def start(self) -> None:
        """Start monitoring configuration files for changes."""
        if self.is_running:
            logger.warning("Hot reloader is already running")
            return
        
        try:
            self.observer = Observer()
            handler = ConfigurationChangeHandler(
                self._reload_configuration,
                self.config_files
            )
            
            # Watch each directory
            for directory in self.watch_directories:
                if os.path.exists(directory):
                    self.observer.schedule(handler, directory, recursive=False)
                    logger.info(f"Watching directory for config changes: {directory}")
            
            self.observer.start()
            self.is_running = True
            logger.info("Configuration hot reloader started")
            
        except Exception as e:
            logger.error(f"Failed to start configuration hot reloader: {e}")
            self.stop()
    
    def stop(self) -> None:
        """Stop monitoring configuration files."""
        if not self.is_running:
            return
        
        try:
            if self.observer:
                self.observer.stop()
                self.observer.join(timeout=5.0)
                self.observer = None
            
            self.is_running = False
            logger.info("Configuration hot reloader stopped")
            
        except Exception as e:
            logger.error(f"Error stopping configuration hot reloader: {e}")
    
    def is_active(self) -> bool:
        """Check if the hot reloader is currently active."""
        return self.is_running and self.observer is not None
    
    def get_change_log(self) -> List[Dict[str, Any]]:
        """Get the configuration change log."""
        with self._lock:
            return self.change_log.copy()
    
    def clear_change_log(self) -> None:
        """Clear the configuration change log."""
        with self._lock:
            self.change_log.clear()
    
    def add_watch_file(self, filename: str) -> None:
        """
        Add a file to watch for changes.
        
        Args:
            filename: Name of the file to watch
        """
        if filename not in self.config_files:
            self.config_files.append(filename)
            logger.info(f"Added file to watch list: {filename}")
    
    def remove_watch_file(self, filename: str) -> None:
        """
        Remove a file from the watch list.
        
        Args:
            filename: Name of the file to stop watching
        """
        if filename in self.config_files:
            self.config_files.remove(filename)
            logger.info(f"Removed file from watch list: {filename}")
    
    def trigger_reload(self) -> None:
        """Manually trigger a configuration reload."""
        logger.info("Manual configuration reload triggered")
        self._reload_configuration()
    
    def get_status(self) -> Dict[str, Any]:
        """Get the current status of the hot reloader."""
        return {
            'is_running': self.is_running,
            'is_active': self.is_active(),
            'watched_files': self.config_files.copy(),
            'watched_directories': self.watch_directories.copy(),
            'change_log_entries': len(self.change_log),
            'callbacks_registered': len(self.reload_callbacks)
        }


# Global hot reloader instance
_hot_reloader: Optional[ConfigurationHotReloader] = None


def get_hot_reloader() -> ConfigurationHotReloader:
    """Get the global configuration hot reloader instance."""
    global _hot_reloader
    if _hot_reloader is None:
        _hot_reloader = ConfigurationHotReloader()
    return _hot_reloader


def start_hot_reload() -> None:
    """Start configuration hot reloading."""
    reloader = get_hot_reloader()
    reloader.start()


def stop_hot_reload() -> None:
    """Stop configuration hot reloading."""
    reloader = get_hot_reloader()
    reloader.stop()


def add_reload_callback(callback: Callable[[], None]) -> None:
    """Add a callback to be called when configuration is reloaded."""
    reloader = get_hot_reloader()
    reloader.add_reload_callback(callback)


def remove_reload_callback(callback: Callable[[], None]) -> None:
    """Remove a reload callback."""
    reloader = get_hot_reloader()
    reloader.remove_reload_callback(callback)


def trigger_reload() -> None:
    """Manually trigger a configuration reload."""
    reloader = get_hot_reloader()
    reloader.trigger_reload()


def get_reload_status() -> Dict[str, Any]:
    """Get the current status of configuration hot reloading."""
    reloader = get_hot_reloader()
    return reloader.get_status()


def get_change_log() -> List[Dict[str, Any]]:
    """Get the configuration change log."""
    reloader = get_hot_reloader()
    return reloader.get_change_log()


# Context manager for temporary hot reload disabling
class HotReloadPause:
    """Context manager to temporarily pause hot reloading."""
    
    def __init__(self):
        self.was_running = False
    
    def __enter__(self):
        reloader = get_hot_reloader()
        self.was_running = reloader.is_running
        if self.was_running:
            reloader.stop()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.was_running:
            reloader = get_hot_reloader()
            reloader.start()


# Decorators for automatic hot reload handling
def reload_on_config_change(func: Callable) -> Callable:
    """Decorator to automatically call a function when configuration changes."""
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        add_reload_callback(lambda: func(*args, **kwargs))
        return result
    return wrapper