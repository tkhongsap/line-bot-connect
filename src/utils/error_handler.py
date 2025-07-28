"""
Structured error handling utility with correlation IDs and context tracking.

This module provides comprehensive error handling utilities for consistent
error logging, monitoring, and alerting across the LINE Bot application.
"""

import logging
import json
import traceback
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable, Union
from collections import defaultdict, deque
from dataclasses import dataclass, asdict
from contextlib import contextmanager
from functools import wraps

from ..exceptions import (
    BaseBotException, ErrorSeverity, ErrorCategory, 
    create_correlation_id, log_exception
)


@dataclass
class ErrorMetrics:
    """Error metrics for monitoring and alerting."""
    total_errors: int = 0
    errors_by_category: Dict[str, int] = None
    errors_by_severity: Dict[str, int] = None
    error_rate_per_minute: float = 0.0
    last_error_time: Optional[datetime] = None
    
    def __post_init__(self):
        if self.errors_by_category is None:
            self.errors_by_category = defaultdict(int)
        if self.errors_by_severity is None:
            self.errors_by_severity = defaultdict(int)


class ErrorTracker:
    """
    Thread-safe error tracking and metrics collection.
    
    Tracks error patterns, rates, and provides alerting capabilities
    for production monitoring and debugging.
    """
    
    def __init__(self, max_history: int = 1000, alert_threshold: int = 10):
        """
        Initialize error tracker.
        
        Args:
            max_history: Maximum number of errors to keep in history
            alert_threshold: Number of errors per minute to trigger alerts
        """
        self.max_history = max_history
        self.alert_threshold = alert_threshold
        self._lock = threading.Lock()
        
        # Error history and metrics
        self.error_history: deque = deque(maxlen=max_history)
        self.metrics = ErrorMetrics()
        
        # Alert callbacks
        self.alert_callbacks: List[Callable[[Dict[str, Any]], None]] = []
        
        # Recent errors for rate calculation
        self.recent_errors: deque = deque()
        self.rate_window_minutes = 5
    
    def track_error(
        self,
        exception: Exception,
        correlation_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None
    ) -> str:
        """
        Track an error occurrence with metrics and alerting.
        
        Args:
            exception: The exception that occurred
            correlation_id: Optional correlation ID for tracking
            context: Additional context information
            user_id: User ID associated with the error
            
        Returns:
            str: Correlation ID for the tracked error
        """
        correlation_id = correlation_id or create_correlation_id()
        timestamp = datetime.utcnow()
        
        # Create error record
        error_record = {
            'correlation_id': correlation_id,
            'timestamp': timestamp,
            'error_type': type(exception).__name__,
            'message': str(exception),
            'context': context or {},
            'user_id': f"{user_id[:8]}..." if user_id else None,
            'traceback': traceback.format_exc() if not isinstance(exception, BaseBotException) else None
        }
        
        # Extract error details for metrics
        if isinstance(exception, BaseBotException):
            error_record.update({
                'category': exception.category.value,
                'severity': exception.severity.value,
                'user_message': exception.user_message,
                'retry_after': exception.retry_after
            })
            category = exception.category.value
            severity = exception.severity.value
        else:
            error_record.update({
                'category': ErrorCategory.SERVICE_ERROR.value,
                'severity': ErrorSeverity.MEDIUM.value
            })
            category = ErrorCategory.SERVICE_ERROR.value
            severity = ErrorSeverity.MEDIUM.value
        
        # Update metrics in thread-safe manner
        with self._lock:
            self.error_history.append(error_record)
            self.recent_errors.append(timestamp)
            
            # Update metrics
            self.metrics.total_errors += 1
            self.metrics.errors_by_category[category] += 1
            self.metrics.errors_by_severity[severity] += 1
            self.metrics.last_error_time = timestamp
            
            # Clean up old recent errors for rate calculation
            cutoff_time = timestamp - timedelta(minutes=self.rate_window_minutes)
            while self.recent_errors and self.recent_errors[0] < cutoff_time:
                self.recent_errors.popleft()
            
            # Calculate error rate
            self.metrics.error_rate_per_minute = (
                len(self.recent_errors) / self.rate_window_minutes
            )
            
            # Check alert threshold
            if self.metrics.error_rate_per_minute >= self.alert_threshold:
                self._trigger_alert(error_record)
        
        return correlation_id
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current error metrics."""
        with self._lock:
            return {
                'total_errors': self.metrics.total_errors,
                'errors_by_category': dict(self.metrics.errors_by_category),
                'errors_by_severity': dict(self.metrics.errors_by_severity),
                'error_rate_per_minute': self.metrics.error_rate_per_minute,
                'last_error_time': self.metrics.last_error_time.isoformat() if self.metrics.last_error_time else None,
                'recent_errors_count': len(self.recent_errors)
            }
    
    def get_recent_errors(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent error records."""
        with self._lock:
            errors = list(self.error_history)[-limit:]
            # Convert datetime objects to strings
            for error in errors:
                if 'timestamp' in error and isinstance(error['timestamp'], datetime):
                    error['timestamp'] = error['timestamp'].isoformat()
            return errors
    
    def add_alert_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Add callback function for error alerts."""
        self.alert_callbacks.append(callback)
    
    def _trigger_alert(self, error_record: Dict[str, Any]):
        """Trigger alert callbacks when error threshold is exceeded."""
        alert_data = {
            'alert_type': 'high_error_rate',
            'error_rate': self.metrics.error_rate_per_minute,
            'threshold': self.alert_threshold,
            'recent_error': error_record,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        for callback in self.alert_callbacks:
            try:
                callback(alert_data)
            except Exception as e:
                # Log alert callback errors but don't propagate
                logging.getLogger(__name__).error(f"Alert callback failed: {e}")


class StructuredLogger:
    """
    Enhanced logging with structured format and correlation tracking.
    
    Provides consistent logging format across all services with
    correlation IDs, context tracking, and error classification.
    """
    
    def __init__(self, name: str, error_tracker: Optional[ErrorTracker] = None):
        """
        Initialize structured logger.
        
        Args:
            name: Logger name (usually __name__)
            error_tracker: Optional error tracker for metrics
        """
        self.logger = logging.getLogger(name)
        self.error_tracker = error_tracker or error_tracker_instance
        self._context_local = threading.local()
    
    def set_context(self, **context):
        """Set logging context for current thread."""
        if not hasattr(self._context_local, 'context'):
            self._context_local.context = {}
        self._context_local.context.update(context)
    
    def clear_context(self):
        """Clear logging context for current thread."""
        self._context_local.context = {}
    
    def get_context(self) -> Dict[str, Any]:
        """Get current logging context."""
        return getattr(self._context_local, 'context', {})
    
    @contextmanager
    def context(self, **context):
        """Context manager for temporary logging context."""
        old_context = self.get_context().copy()
        self.set_context(**context)
        try:
            yield
        finally:
            self.clear_context()
            self.set_context(**old_context)
    
    def _log(
        self,
        level: int,
        message: str,
        correlation_id: Optional[str] = None,
        extra_context: Optional[Dict[str, Any]] = None,
        exception: Optional[Exception] = None
    ):
        """Internal structured logging method."""
        correlation_id = correlation_id or create_correlation_id()
        
        # Combine contexts
        context = self.get_context().copy()
        if extra_context:
            context.update(extra_context)
        
        # Create structured log record
        log_data = {
            'correlation_id': correlation_id,
            'timestamp': datetime.utcnow().isoformat(),
            'context': context
        }
        
        # Track error if exception provided
        if exception:
            self.error_tracker.track_error(
                exception=exception,
                correlation_id=correlation_id,
                context=context
            )
        
        # Log with structured format
        self.logger.log(level, message, extra=log_data, exc_info=exception is not None)
    
    def debug(self, message: str, **kwargs):
        """Log debug message with structured format."""
        self._log(logging.DEBUG, message, **kwargs)
    
    def info(self, message: str, **kwargs):
        """Log info message with structured format."""
        self._log(logging.INFO, message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning message with structured format."""
        self._log(logging.WARNING, message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """Log error message with structured format."""
        self._log(logging.ERROR, message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        """Log critical message with structured format."""
        self._log(logging.CRITICAL, message, **kwargs)
    
    def exception(self, message: str, exception: Exception, **kwargs):
        """Log exception with full context and tracking."""
        correlation_id = kwargs.get('correlation_id') or create_correlation_id()
        
        if isinstance(exception, BaseBotException):
            exception.log_error(self.logger, kwargs.get('extra_context'))
        else:
            log_exception(
                logger=self.logger,
                exception=exception,
                correlation_id=correlation_id,
                extra_context=kwargs.get('extra_context'),
                user_id=kwargs.get('user_id')
            )
        
        # Track error in metrics
        self.error_tracker.track_error(
            exception=exception,
            correlation_id=correlation_id,
            context=kwargs.get('extra_context'),
            user_id=kwargs.get('user_id')
        )


def error_handler(
    logger: Optional[StructuredLogger] = None,
    reraise: bool = True,
    default_return: Any = None,
    handle_types: Optional[tuple] = None
):
    """
    Decorator for consistent error handling across service methods.
    
    Args:
        logger: Optional structured logger instance
        reraise: Whether to reraise exceptions after logging
        default_return: Default return value if exception is caught
        handle_types: Tuple of exception types to handle (None = all)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            nonlocal logger
            if logger is None:
                logger = StructuredLogger(func.__module__)
            
            correlation_id = create_correlation_id()
            
            try:
                with logger.context(
                    function=func.__name__,
                    correlation_id=correlation_id
                ):
                    return func(*args, **kwargs)
                    
            except Exception as e:
                # Check if we should handle this exception type
                if handle_types and not isinstance(e, handle_types):
                    raise
                
                # Log the exception
                logger.exception(
                    f"Error in {func.__name__}: {str(e)}",
                    exception=e,
                    correlation_id=correlation_id,
                    extra_context={
                        'function': func.__name__,
                        'args_count': len(args),
                        'kwargs_keys': list(kwargs.keys())
                    }
                )
                
                if reraise:
                    raise
                else:
                    return default_return
        
        return wrapper
    return decorator


def retry_with_backoff(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff_factor: float = 2.0,
    handle_types: Optional[tuple] = None,
    logger: Optional[StructuredLogger] = None
):
    """
    Decorator for automatic retry with exponential backoff.
    
    Args:
        max_attempts: Maximum number of retry attempts
        base_delay: Base delay in seconds
        max_delay: Maximum delay in seconds
        backoff_factor: Multiplier for exponential backoff
        handle_types: Exception types that should trigger retry
        logger: Optional structured logger
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            nonlocal logger
            if logger is None:
                logger = StructuredLogger(func.__module__)
            
            correlation_id = create_correlation_id()
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    with logger.context(
                        function=func.__name__,
                        correlation_id=correlation_id,
                        attempt=attempt + 1
                    ):
                        return func(*args, **kwargs)
                        
                except Exception as e:
                    last_exception = e
                    
                    # Check if we should retry this exception
                    if handle_types and not isinstance(e, handle_types):
                        raise
                    
                    # Don't retry on last attempt
                    if attempt == max_attempts - 1:
                        raise
                    
                    # Calculate delay with exponential backoff
                    delay = min(base_delay * (backoff_factor ** attempt), max_delay)
                    
                    logger.warning(
                        f"Attempt {attempt + 1} failed for {func.__name__}, retrying in {delay:.2f}s",
                        correlation_id=correlation_id,
                        extra_context={
                            'function': func.__name__,
                            'attempt': attempt + 1,
                            'delay': delay,
                            'error': str(e)
                        }
                    )
                    
                    time.sleep(delay)
            
            # This should never be reached, but just in case
            if last_exception:
                raise last_exception
        
        return wrapper
    return decorator


# Global error tracker instance
error_tracker_instance = ErrorTracker()


def get_error_tracker() -> ErrorTracker:
    """Get the global error tracker instance."""
    return error_tracker_instance


def setup_error_logging(
    log_level: str = "INFO",
    log_format: Optional[str] = None,
    enable_json_logging: bool = True
):
    """
    Setup structured error logging configuration.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Custom log format string
        enable_json_logging: Whether to use JSON formatter
    """
    # Default structured format
    if log_format is None:
        if enable_json_logging:
            log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        else:
            log_format = '%(asctime)s - %(name)s - %(levelname)s - [%(correlation_id)s] - %(message)s'
    
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format=log_format,
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Add custom formatter for structured logging
    if enable_json_logging:
        class JSONFormatter(logging.Formatter):
            def format(self, record):
                log_data = {
                    'timestamp': self.formatTime(record),
                    'level': record.levelname,
                    'logger': record.name,
                    'message': record.getMessage(),
                    'module': record.module,
                    'function': record.funcName,
                    'line': record.lineno
                }
                
                # Add extra fields from structured logging
                for key, value in record.__dict__.items():
                    if key not in ('name', 'msg', 'args', 'levelname', 'levelno', 
                                 'pathname', 'filename', 'module', 'lineno', 
                                 'funcName', 'created', 'msecs', 'relativeCreated',
                                 'thread', 'threadName', 'processName', 'process',
                                 'message', 'exc_info', 'exc_text', 'stack_info'):
                        log_data[key] = value
                
                return json.dumps(log_data, default=str)
        
        # Apply JSON formatter to root logger
        root_logger = logging.getLogger()
        for handler in root_logger.handlers:
            handler.setFormatter(JSONFormatter())


# Export main classes and functions
__all__ = [
    'ErrorTracker',
    'StructuredLogger', 
    'ErrorMetrics',
    'error_handler',
    'retry_with_backoff',
    'get_error_tracker',
    'setup_error_logging',
    'error_tracker_instance'
]