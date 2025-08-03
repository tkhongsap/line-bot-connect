"""
Centralized exception hierarchy for LINE Bot application.

This module provides a comprehensive exception hierarchy for structured error handling
across all services and components of the LINE Bot application.
"""

import uuid
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum


class ErrorSeverity(Enum):
    """Error severity levels for classification and alerting."""
    LOW = "low"
    MEDIUM = "medium" 
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Categories for different types of errors."""
    API_ERROR = "api_error"
    VALIDATION_ERROR = "validation_error"
    AUTHENTICATION_ERROR = "authentication_error"
    AUTHORIZATION_ERROR = "authorization_error"
    RATE_LIMIT_ERROR = "rate_limit_error"
    NETWORK_ERROR = "network_error"
    SERVICE_ERROR = "service_error"
    DATA_ERROR = "data_error"
    CONFIGURATION_ERROR = "configuration_error"
    RESOURCE_ERROR = "resource_error"


class BaseBotException(Exception):
    """
    Base exception class for all LINE Bot application errors.
    
    Provides structured error handling with correlation IDs, context tracking,
    and severity classification for better monitoring and debugging.
    """
    
    def __init__(
        self,
        message: str,
        correlation_id: Optional[str] = None,
        category: ErrorCategory = ErrorCategory.SERVICE_ERROR,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        context: Optional[Dict[str, Any]] = None,
        original_exception: Optional[Exception] = None,
        user_message: Optional[str] = None,
        retry_after: Optional[int] = None
    ):
        """
        Initialize base exception with comprehensive error context.
        
        Args:
            message: Technical error message for logging
            correlation_id: Unique identifier for error tracking
            category: Error category for classification
            severity: Error severity level for alerting
            context: Additional context data
            original_exception: Original exception that caused this error
            user_message: User-friendly error message
            retry_after: Seconds to wait before retry (for transient errors)
        """
        super().__init__(message)
        
        self.message = message
        self.correlation_id = correlation_id or str(uuid.uuid4())
        self.category = category
        self.severity = severity
        self.context = context or {}
        self.original_exception = original_exception
        self.user_message = user_message or "An error occurred. Please try again."
        self.retry_after = retry_after
        self.timestamp = datetime.utcnow()
        
        # Add original exception details to context
        if original_exception:
            self.context['original_error'] = {
                'type': type(original_exception).__name__,
                'message': str(original_exception),
                'args': original_exception.args if hasattr(original_exception, 'args') else []
            }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for logging and monitoring."""
        return {
            'error_type': self.__class__.__name__,
            'message': self.message,
            'correlation_id': self.correlation_id,
            'category': self.category.value,
            'severity': self.severity.value,
            'context': self.context,
            'user_message': self.user_message,
            'retry_after': self.retry_after,
            'timestamp': self.timestamp.isoformat(),
            'original_exception': str(self.original_exception) if self.original_exception else None
        }
    
    def log_error(self, logger: logging.Logger, extra_context: Optional[Dict[str, Any]] = None):
        """Log error with structured format and correlation ID."""
        context = self.context.copy()
        if extra_context:
            context.update(extra_context)
        
        log_data = {
            'correlation_id': self.correlation_id,
            'error_category': self.category.value,
            'error_severity': self.severity.value,
            'context': context
        }
        
        if self.severity == ErrorSeverity.CRITICAL:
            logger.critical(f"CRITICAL ERROR: {self.message}", extra=log_data)
        elif self.severity == ErrorSeverity.HIGH:
            logger.error(f"HIGH SEVERITY: {self.message}", extra=log_data)
        elif self.severity == ErrorSeverity.MEDIUM:
            logger.warning(f"MEDIUM SEVERITY: {self.message}", extra=log_data)
        else:
            logger.info(f"LOW SEVERITY: {self.message}", extra=log_data)


# API-related exceptions
class APIException(BaseBotException):
    """Base exception for external API errors."""
    
    def __init__(self, message: str, api_name: str, status_code: Optional[int] = None, **kwargs):
        super().__init__(
            message=message,
            category=ErrorCategory.API_ERROR,
            **kwargs
        )
        self.api_name = api_name
        self.status_code = status_code
        self.context.update({
            'api_name': api_name,
            'status_code': status_code
        })


class LineAPIException(APIException):
    """LINE Bot API specific errors."""
    
    def __init__(self, message: str, status_code: Optional[int] = None, **kwargs):
        super().__init__(
            message=message,
            api_name="LINE_API",
            status_code=status_code,
            severity=ErrorSeverity.HIGH,
            **kwargs
        )


class OpenAIAPIException(APIException):
    """Azure OpenAI API specific errors."""
    
    def __init__(self, message: str, status_code: Optional[int] = None, **kwargs):
        super().__init__(
            message=message,
            api_name="AZURE_OPENAI",
            status_code=status_code,
            severity=ErrorSeverity.HIGH,
            **kwargs
        )


class RateLimitException(BaseBotException):
    """Rate limiting errors with retry information."""
    
    def __init__(self, message: str, retry_after: int, service: str, **kwargs):
        super().__init__(
            message=message,
            category=ErrorCategory.RATE_LIMIT_ERROR,
            severity=ErrorSeverity.MEDIUM,
            retry_after=retry_after,
            user_message="Service temporarily unavailable. Please try again later.",
            **kwargs
        )
        self.service = service
        self.context.update({
            'service': service,
            'retry_after': retry_after
        })


# Network and connectivity exceptions
class NetworkException(BaseBotException):
    """Network connectivity and timeout errors."""
    
    def __init__(self, message: str, operation: str, **kwargs):
        super().__init__(
            message=message,
            category=ErrorCategory.NETWORK_ERROR,
            severity=ErrorSeverity.MEDIUM,
            user_message="Network connection issue. Please try again.",
            **kwargs
        )
        self.operation = operation
        self.context.update({'operation': operation})


class TimeoutException(NetworkException):
    """Request timeout errors."""
    
    def __init__(self, message: str, operation: str, timeout_seconds: float, **kwargs):
        super().__init__(
            message=message,
            operation=operation,
            **kwargs
        )
        self.timeout_seconds = timeout_seconds
        self.context.update({'timeout_seconds': timeout_seconds})


# Validation and data exceptions
class ValidationException(BaseBotException):
    """Input validation and data format errors."""
    
    def __init__(self, message: str, field: str, value: Any = None, **kwargs):
        super().__init__(
            message=message,
            category=ErrorCategory.VALIDATION_ERROR,
            severity=ErrorSeverity.LOW,
            user_message="Invalid input provided. Please check your data and try again.",
            **kwargs
        )
        self.field = field
        self.value = value
        self.context.update({
            'field': field,
            'value': str(value) if value is not None else None
        })


class DataProcessingException(BaseBotException):
    """Data processing and transformation errors."""
    
    def __init__(self, message: str, operation: str, data_type: str, **kwargs):
        super().__init__(
            message=message,
            category=ErrorCategory.DATA_ERROR,
            severity=ErrorSeverity.MEDIUM,
            **kwargs
        )
        self.operation = operation
        self.data_type = data_type
        self.context.update({
            'operation': operation,
            'data_type': data_type
        })


# Service-specific exceptions
class ConversationServiceException(BaseBotException):
    """Conversation service errors."""
    
    def __init__(self, message: str, user_id: Optional[str] = None, **kwargs):
        super().__init__(
            message=message,
            category=ErrorCategory.SERVICE_ERROR,
            **kwargs
        )
        self.user_id = user_id
        if user_id:
            # Truncate user ID for privacy in logs
            self.context.update({'user_id': f"{user_id[:8]}..."})


class RichMessageServiceException(BaseBotException):
    """Rich Message service errors."""
    
    def __init__(self, message: str, template_id: Optional[str] = None, **kwargs):
        super().__init__(
            message=message,
            category=ErrorCategory.SERVICE_ERROR,
            **kwargs
        )
        self.template_id = template_id
        if template_id:
            self.context.update({'template_id': template_id})


class ImageProcessingException(BaseBotException):
    """Image processing and manipulation errors."""
    
    def __init__(self, message: str, image_type: Optional[str] = None, **kwargs):
        super().__init__(
            message=message,
            category=ErrorCategory.DATA_ERROR,
            severity=ErrorSeverity.MEDIUM,
            **kwargs
        )
        self.image_type = image_type
        if image_type:
            self.context.update({'image_type': image_type})


# Resource and infrastructure exceptions
class RedisConnectionException(BaseBotException):
    """Redis connection and operation errors."""
    
    def __init__(self, message: str, operation: str, **kwargs):
        super().__init__(
            message=message,
            category=ErrorCategory.RESOURCE_ERROR,
            severity=ErrorSeverity.HIGH,
            **kwargs
        )
        self.operation = operation
        self.context.update({'operation': operation})


class MemoryException(BaseBotException):
    """Memory usage and resource exhaustion errors."""
    
    def __init__(self, message: str, current_usage: Optional[float] = None, **kwargs):
        super().__init__(
            message=message,
            category=ErrorCategory.RESOURCE_ERROR,
            severity=ErrorSeverity.HIGH,
            **kwargs
        )
        self.current_usage = current_usage
        if current_usage:
            self.context.update({'memory_usage_percent': current_usage})


class ConfigurationException(BaseBotException):
    """Configuration and environment errors."""
    
    def __init__(self, message: str, config_key: str, **kwargs):
        super().__init__(
            message=message,
            category=ErrorCategory.CONFIGURATION_ERROR,
            severity=ErrorSeverity.CRITICAL,
            **kwargs
        )
        self.config_key = config_key
        self.context.update({'config_key': config_key})


# Authentication and authorization exceptions
class AuthenticationException(BaseBotException):
    """Authentication and credential errors."""
    
    def __init__(self, message: str, service: str, **kwargs):
        super().__init__(
            message=message,
            category=ErrorCategory.AUTHENTICATION_ERROR,
            severity=ErrorSeverity.HIGH,
            user_message="Authentication failed. Please check your credentials.",
            **kwargs
        )
        self.service = service
        self.context.update({'service': service})


class AuthorizationException(BaseBotException):
    """Authorization and permission errors."""
    
    def __init__(self, message: str, resource: str, action: str, **kwargs):
        super().__init__(
            message=message,
            category=ErrorCategory.AUTHORIZATION_ERROR,
            severity=ErrorSeverity.MEDIUM,
            user_message="Access denied. You don't have permission for this operation.",
            **kwargs
        )
        self.resource = resource
        self.action = action
        self.context.update({
            'resource': resource,
            'action': action
        })


# Utility functions for error handling
def create_correlation_id() -> str:
    """Generate a unique correlation ID for error tracking."""
    return str(uuid.uuid4())


def log_exception(
    logger: logging.Logger,
    exception: Exception,
    correlation_id: Optional[str] = None,
    extra_context: Optional[Dict[str, Any]] = None,
    user_id: Optional[str] = None
):
    """
    Log any exception with structured format and correlation tracking.
    
    Args:
        logger: Logger instance to use
        exception: Exception to log
        correlation_id: Optional correlation ID for tracking
        extra_context: Additional context data
        user_id: User ID associated with the error (will be truncated for privacy)
    """
    correlation_id = correlation_id or create_correlation_id()
    
    context = extra_context or {}
    if user_id:
        context['user_id'] = f"{user_id[:8]}..."
    
    if isinstance(exception, BaseBotException):
        exception.log_error(logger, context)
    else:
        # Handle non-custom exceptions
        log_data = {
            'correlation_id': correlation_id,
            'error_type': type(exception).__name__,
            'context': context
        }
        
        logger.error(f"Unhandled exception: {str(exception)}", extra=log_data, exc_info=True)


def wrap_api_exception(
    original_exception: Exception,
    api_name: str,
    operation: str,
    correlation_id: Optional[str] = None
) -> APIException:
    """
    Wrap external API exceptions with structured error handling.
    
    Args:
        original_exception: The original exception from the API
        api_name: Name of the API service
        operation: Operation that was being performed
        correlation_id: Optional correlation ID for tracking
    
    Returns:
        APIException with structured error information
    """
    status_code = None
    if hasattr(original_exception, 'status_code'):
        status_code = original_exception.status_code
    elif hasattr(original_exception, 'response') and original_exception.response:
        status_code = original_exception.response.status_code
    
    message = f"{api_name} API error during {operation}: {str(original_exception)}"
    
    if api_name.lower() == 'line':
        return LineAPIException(
            message=message,
            status_code=status_code,
            correlation_id=correlation_id,
            original_exception=original_exception,
            context={'operation': operation}
        )
    elif api_name.lower() in ('openai', 'azure_openai'):
        return OpenAIAPIException(
            message=message,
            status_code=status_code,
            correlation_id=correlation_id,
            original_exception=original_exception,
            context={'operation': operation}
        )
    else:
        return APIException(
            message=message,
            api_name=api_name,
            status_code=status_code,
            correlation_id=correlation_id,
            original_exception=original_exception,
            context={'operation': operation}
        )


# Export all exception classes and utilities
__all__ = [
    # Enums
    'ErrorSeverity',
    'ErrorCategory',
    
    # Base exceptions
    'BaseBotException',
    
    # API exceptions
    'APIException',
    'LineAPIException', 
    'OpenAIAPIException',
    'RateLimitException',
    
    # Network exceptions
    'NetworkException',
    'TimeoutException',
    
    # Validation exceptions
    'ValidationException',
    'DataProcessingException',
    
    # Service exceptions
    'ConversationServiceException',
    'RichMessageServiceException',
    'ImageProcessingException',
    
    # Resource exceptions
    'RedisConnectionException',
    'MemoryException',
    'ConfigurationException',
    
    # Auth exceptions
    'AuthenticationException',
    'AuthorizationException',
    
    # Utility functions
    'create_correlation_id',
    'log_exception',
    'wrap_api_exception'
]


# Import Azure OpenAI specific exceptions
try:
    from .azure_openai_exceptions import (
        AzureOpenAIException,
        FeatureNotEnabledError,
        DeploymentNotFoundError,
        AuthenticationFailedError,
        QuotaExceededError,
        APICapabilityError,
        create_azure_openai_exception
    )
    
    # Add to exports
    __all__.extend([
        'AzureOpenAIException',
        'FeatureNotEnabledError', 
        'DeploymentNotFoundError',
        'AuthenticationFailedError',
        'QuotaExceededError',
        'APICapabilityError',
        'create_azure_openai_exception'
    ])
except ImportError:
    # Handle case where azure_openai_exceptions module is not available
    pass