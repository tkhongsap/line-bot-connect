"""
Structured exception types for Azure OpenAI API integration.

These exceptions provide detailed error information and enable proper error handling
for different types of Azure OpenAI API failures.
"""

from typing import Optional, Dict, Any
from ..exceptions import BaseBotException


class AzureOpenAIException(BaseBotException):
    """Base exception for Azure OpenAI API related errors"""
    
    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        status_code: Optional[int] = None,
        correlation_id: Optional[str] = None,
        api_endpoint: Optional[str] = None,
        deployment_name: Optional[str] = None,
        original_exception: Optional[Exception] = None,
        **kwargs
    ):
        super().__init__(message, correlation_id=correlation_id, **kwargs)
        self.error_code = error_code
        self.status_code = status_code
        self.api_endpoint = api_endpoint
        self.deployment_name = deployment_name
        self.original_exception = original_exception
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for logging and monitoring"""
        base_dict = super().to_dict()
        base_dict.update({
            'error_code': self.error_code,
            'status_code': self.status_code,
            'api_endpoint': self.api_endpoint,
            'deployment_name': self.deployment_name,
            'exception_type': 'AzureOpenAIException'
        })
        return base_dict


class FeatureNotEnabledError(AzureOpenAIException):
    """
    Raised when attempting to use an Azure OpenAI feature that is not enabled
    for the current deployment or subscription.
    
    This typically happens with:
    - Responses API not available in the deployment region
    - Specific model features not enabled
    - Beta features not accessible
    """
    
    def __init__(
        self,
        feature_name: str,
        deployment_name: Optional[str] = None,
        suggested_alternative: Optional[str] = None,
        **kwargs
    ):
        message = f"Feature '{feature_name}' is not enabled for this Azure OpenAI deployment"
        if deployment_name:
            message += f" (deployment: {deployment_name})"
        if suggested_alternative:
            message += f". Consider using: {suggested_alternative}"
            
        super().__init__(
            message=message,
            error_code="FEATURE_NOT_ENABLED",
            deployment_name=deployment_name,
            **kwargs
        )
        self.feature_name = feature_name
        self.suggested_alternative = suggested_alternative
    
    def to_dict(self) -> Dict[str, Any]:
        base_dict = super().to_dict()
        base_dict.update({
            'feature_name': self.feature_name,
            'suggested_alternative': self.suggested_alternative,
            'exception_type': 'FeatureNotEnabledError'
        })
        return base_dict


class DeploymentNotFoundError(AzureOpenAIException):
    """
    Raised when the specified Azure OpenAI deployment cannot be found.
    
    This can happen when:
    - Deployment name is incorrect
    - Deployment was deleted or renamed
    - Access permissions are insufficient
    """
    
    def __init__(
        self,
        deployment_name: str,
        endpoint: Optional[str] = None,
        available_deployments: Optional[list] = None,
        **kwargs
    ):
        message = f"Azure OpenAI deployment '{deployment_name}' not found"
        if endpoint:
            message += f" at endpoint {endpoint}"
        if available_deployments:
            message += f". Available deployments: {', '.join(available_deployments)}"
            
        super().__init__(
            message=message,
            error_code="DEPLOYMENT_NOT_FOUND",
            status_code=404,
            deployment_name=deployment_name,
            api_endpoint=endpoint,
            **kwargs
        )
        self.available_deployments = available_deployments or []
    
    def to_dict(self) -> Dict[str, Any]:
        base_dict = super().to_dict()
        base_dict.update({
            'available_deployments': self.available_deployments,
            'exception_type': 'DeploymentNotFoundError'
        })
        return base_dict


class AuthenticationFailedError(AzureOpenAIException):
    """
    Raised when Azure OpenAI API authentication fails.
    
    This can happen when:
    - API key is invalid or expired
    - API key doesn't have required permissions
    - Azure subscription is not active
    """
    
    def __init__(
        self,
        auth_method: str = "api_key",
        endpoint: Optional[str] = None,
        **kwargs
    ):
        message = f"Azure OpenAI authentication failed using {auth_method}"
        if endpoint:
            message += f" for endpoint {endpoint}"
        message += ". Please check your API key and permissions."
            
        super().__init__(
            message=message,
            error_code="AUTHENTICATION_FAILED",
            status_code=401,
            api_endpoint=endpoint,
            **kwargs
        )
        self.auth_method = auth_method
    
    def to_dict(self) -> Dict[str, Any]:
        base_dict = super().to_dict()
        base_dict.update({
            'auth_method': self.auth_method,
            'exception_type': 'AuthenticationFailedError'
        })
        return base_dict


class QuotaExceededError(AzureOpenAIException):
    """
    Raised when Azure OpenAI API quota limits are exceeded.
    
    This can happen with:
    - Token quota exceeded
    - Request rate limits
    - Monthly usage limits
    """
    
    def __init__(
        self,
        quota_type: str,
        current_usage: Optional[int] = None,
        quota_limit: Optional[int] = None,
        reset_time: Optional[str] = None,
        **kwargs
    ):
        message = f"Azure OpenAI {quota_type} quota exceeded"
        if current_usage and quota_limit:
            message += f" ({current_usage}/{quota_limit})"
        if reset_time:
            message += f". Quota resets at: {reset_time}"
            
        super().__init__(
            message=message,
            error_code="QUOTA_EXCEEDED",
            status_code=429,
            **kwargs
        )
        self.quota_type = quota_type
        self.current_usage = current_usage
        self.quota_limit = quota_limit
        self.reset_time = reset_time
    
    def to_dict(self) -> Dict[str, Any]:
        base_dict = super().to_dict()
        base_dict.update({
            'quota_type': self.quota_type,
            'current_usage': self.current_usage,
            'quota_limit': self.quota_limit,
            'reset_time': self.reset_time,
            'exception_type': 'QuotaExceededError'
        })
        return base_dict


class APICapabilityError(AzureOpenAIException):
    """
    Raised when there are issues with API capability detection or routing.
    
    This can happen when:
    - Capability detection fails
    - API routing cannot determine available endpoints
    - Cache corruption or unavailability
    """
    
    def __init__(
        self,
        capability_issue: str,
        fallback_available: bool = False,
        **kwargs
    ):
        message = f"Azure OpenAI capability error: {capability_issue}"
        if fallback_available:
            message += " (fallback method available)"
            
        super().__init__(
            message=message,
            error_code="CAPABILITY_ERROR",
            **kwargs
        )
        self.capability_issue = capability_issue
        self.fallback_available = fallback_available
    
    def to_dict(self) -> Dict[str, Any]:
        base_dict = super().to_dict()
        base_dict.update({
            'capability_issue': self.capability_issue,
            'fallback_available': self.fallback_available,
            'exception_type': 'APICapabilityError'
        })
        return base_dict


def create_azure_openai_exception(
    error: Exception,
    correlation_id: Optional[str] = None,
    deployment_name: Optional[str] = None,
    endpoint: Optional[str] = None
) -> AzureOpenAIException:
    """
    Factory function to create appropriate Azure OpenAI exception based on error details.
    
    Args:
        error: Original exception
        correlation_id: Request correlation ID for tracking
        deployment_name: Azure OpenAI deployment name
        endpoint: API endpoint URL
        
    Returns:
        Appropriate Azure OpenAI exception type
    """
    error_str = str(error).lower()
    
    # Check for specific error patterns
    if 'authentication' in error_str or 'unauthorized' in error_str:
        return AuthenticationFailedError(
            endpoint=endpoint,
            correlation_id=correlation_id,
            original_exception=error
        )
    elif 'deployment' in error_str and 'not found' in error_str:
        return DeploymentNotFoundError(
            deployment_name=deployment_name or "unknown",
            endpoint=endpoint,
            correlation_id=correlation_id,
            original_exception=error
        )
    elif 'feature not enabled' in error_str or 'not available' in error_str:
        feature_name = "unknown"
        suggested_alternative = None
        
        if 'responses' in error_str:
            feature_name = "Responses API"
            suggested_alternative = "Chat Completions API"
        
        return FeatureNotEnabledError(
            feature_name=feature_name,
            deployment_name=deployment_name,
            suggested_alternative=suggested_alternative,
            correlation_id=correlation_id,
            original_exception=error
        )
    elif 'quota' in error_str or 'rate limit' in error_str or 'too many requests' in error_str:
        quota_type = "requests"
        if 'token' in error_str:
            quota_type = "tokens"
            
        return QuotaExceededError(
            quota_type=quota_type,
            correlation_id=correlation_id,
            original_exception=error
        )
    else:
        # Generic Azure OpenAI exception
        status_code = getattr(error, 'status_code', None)
        return AzureOpenAIException(
            message=str(error),
            status_code=status_code,
            deployment_name=deployment_name,
            api_endpoint=endpoint,
            correlation_id=correlation_id,
            original_exception=error
        )