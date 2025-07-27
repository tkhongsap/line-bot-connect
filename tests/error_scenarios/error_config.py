"""
Error scenario configuration and utilities for comprehensive error testing.

This module provides configuration for various error scenarios, utilities for
simulating failures, and validation criteria for error handling.
"""

from dataclasses import dataclass
from typing import Dict, List, Any, Optional, Callable, Union
from enum import Enum
import time
import random


class ErrorType(Enum):
    """Types of errors to simulate in testing"""
    NETWORK_ERROR = "network_error"
    API_ERROR = "api_error"
    AUTHENTICATION_ERROR = "authentication_error"
    RATE_LIMIT_ERROR = "rate_limit_error"
    SERVICE_UNAVAILABLE = "service_unavailable"
    TIMEOUT_ERROR = "timeout_error"
    DATA_CORRUPTION = "data_corruption"
    MEMORY_ERROR = "memory_error"
    DISK_ERROR = "disk_error"
    CONFIGURATION_ERROR = "configuration_error"
    VALIDATION_ERROR = "validation_error"
    BUSINESS_LOGIC_ERROR = "business_logic_error"


class ErrorSeverity(Enum):
    """Severity levels for error scenarios"""
    LOW = "low"          # System continues with minor degradation
    MEDIUM = "medium"    # Some features unavailable, core functions work
    HIGH = "high"        # Significant functionality impacted
    CRITICAL = "critical"  # System-wide failure, major components down


@dataclass
class ErrorScenario:
    """Configuration for a specific error scenario"""
    name: str
    error_type: ErrorType
    severity: ErrorSeverity
    description: str
    
    # Error simulation parameters
    failure_rate: float = 0.0  # 0.0 to 1.0 (probability of failure)
    duration_seconds: Optional[float] = None  # How long error persists
    recovery_time_seconds: Optional[float] = None  # Time to recover
    
    # Validation criteria
    expected_fallback: bool = True  # Should fallback mechanisms activate
    max_recovery_time: float = 30.0  # Maximum time for system recovery
    min_success_rate: float = 0.0  # Minimum success rate during error
    
    # Error details
    error_message: str = "Simulated error for testing"
    error_code: Optional[str] = None
    http_status_code: Optional[int] = None
    
    # Metadata
    tags: List[str] = None
    prerequisites: List[str] = None  # Other scenarios that must pass first
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if self.prerequisites is None:
            self.prerequisites = []


# Predefined error scenarios for comprehensive testing
ERROR_SCENARIOS = {
    # Network and connectivity errors
    "network_timeout": ErrorScenario(
        name="Network Timeout",
        error_type=ErrorType.TIMEOUT_ERROR,
        severity=ErrorSeverity.MEDIUM,
        description="Network requests time out due to slow connectivity",
        failure_rate=1.0,
        duration_seconds=5.0,
        recovery_time_seconds=2.0,
        expected_fallback=True,
        max_recovery_time=10.0,
        min_success_rate=0.0,
        error_message="Request timed out after 30 seconds",
        tags=["network", "timeout", "connectivity"]
    ),
    
    "connection_refused": ErrorScenario(
        name="Connection Refused",
        error_type=ErrorType.NETWORK_ERROR,
        severity=ErrorSeverity.HIGH,
        description="Cannot establish connection to external services",
        failure_rate=1.0,
        duration_seconds=10.0,
        recovery_time_seconds=5.0,
        expected_fallback=True,
        max_recovery_time=15.0,
        error_message="Connection refused by server",
        tags=["network", "connection", "external_service"]
    ),
    
    # API and service errors
    "line_api_rate_limit": ErrorScenario(
        name="LINE API Rate Limit",
        error_type=ErrorType.RATE_LIMIT_ERROR,
        severity=ErrorSeverity.MEDIUM,
        description="LINE API rate limiting is triggered",
        failure_rate=1.0,
        duration_seconds=60.0,
        recovery_time_seconds=10.0,
        expected_fallback=True,
        max_recovery_time=70.0,
        min_success_rate=0.0,
        error_message="Rate limit exceeded. Retry after 60 seconds",
        error_code="RATE_LIMIT_EXCEEDED",
        http_status_code=429,
        tags=["line_api", "rate_limit", "external_service"]
    ),
    
    "line_api_authentication": ErrorScenario(
        name="LINE API Authentication Error",
        error_type=ErrorType.AUTHENTICATION_ERROR,
        severity=ErrorSeverity.CRITICAL,
        description="LINE API authentication fails",
        failure_rate=1.0,
        expected_fallback=False,  # No fallback for auth errors
        error_message="Invalid channel access token",
        error_code="INVALID_TOKEN",
        http_status_code=401,
        tags=["line_api", "authentication", "security"]
    ),
    
    "line_api_service_unavailable": ErrorScenario(
        name="LINE API Service Unavailable",
        error_type=ErrorType.SERVICE_UNAVAILABLE,
        severity=ErrorSeverity.HIGH,
        description="LINE API service is temporarily unavailable",
        failure_rate=1.0,
        duration_seconds=30.0,
        recovery_time_seconds=15.0,
        expected_fallback=True,
        max_recovery_time=45.0,
        error_message="Service temporarily unavailable",
        http_status_code=503,
        tags=["line_api", "service_unavailable", "external_service"]
    ),
    
    "openai_api_quota_exceeded": ErrorScenario(
        name="OpenAI API Quota Exceeded",
        error_type=ErrorType.API_ERROR,
        severity=ErrorSeverity.HIGH,
        description="OpenAI API quota is exceeded",
        failure_rate=1.0,
        expected_fallback=True,
        error_message="You have exceeded your API quota",
        error_code="QUOTA_EXCEEDED",
        http_status_code=429,
        tags=["openai_api", "quota", "external_service"]
    ),
    
    # Data and storage errors
    "database_connection_failure": ErrorScenario(
        name="Database Connection Failure",
        error_type=ErrorType.NETWORK_ERROR,
        severity=ErrorSeverity.HIGH,
        description="Cannot connect to database for metrics storage",
        failure_rate=1.0,
        duration_seconds=20.0,
        recovery_time_seconds=10.0,
        expected_fallback=True,
        max_recovery_time=30.0,
        min_success_rate=0.8,  # Core functions should still work
        error_message="Database connection failed",
        tags=["database", "storage", "persistence"]
    ),
    
    "data_corruption": ErrorScenario(
        name="Data Corruption",
        error_type=ErrorType.DATA_CORRUPTION,
        severity=ErrorSeverity.MEDIUM,
        description="Template or configuration data is corrupted",
        failure_rate=0.5,  # Intermittent corruption
        expected_fallback=True,
        error_message="Data corruption detected in template file",
        tags=["data", "corruption", "templates"]
    ),
    
    "disk_space_full": ErrorScenario(
        name="Disk Space Full",
        error_type=ErrorType.DISK_ERROR,
        severity=ErrorSeverity.HIGH,
        description="Disk space is full, cannot write files",
        failure_rate=1.0,
        expected_fallback=True,
        error_message="No space left on device",
        tags=["disk", "storage", "filesystem"]
    ),
    
    # Memory and resource errors
    "memory_exhaustion": ErrorScenario(
        name="Memory Exhaustion",
        error_type=ErrorType.MEMORY_ERROR,
        severity=ErrorSeverity.CRITICAL,
        description="System runs out of available memory",
        failure_rate=0.8,
        expected_fallback=True,
        min_success_rate=0.2,  # Some operations might still work
        error_message="Out of memory",
        tags=["memory", "resources", "performance"]
    ),
    
    # Configuration and validation errors
    "invalid_configuration": ErrorScenario(
        name="Invalid Configuration",
        error_type=ErrorType.CONFIGURATION_ERROR,
        severity=ErrorSeverity.MEDIUM,
        description="Configuration file contains invalid settings",
        failure_rate=1.0,
        expected_fallback=True,
        error_message="Invalid configuration parameter",
        tags=["configuration", "validation", "setup"]
    ),
    
    "template_validation_failure": ErrorScenario(
        name="Template Validation Failure",
        error_type=ErrorType.VALIDATION_ERROR,
        severity=ErrorSeverity.MEDIUM,
        description="Template fails validation checks",
        failure_rate=0.3,  # Some templates fail validation
        expected_fallback=True,
        error_message="Template validation failed: missing required fields",
        tags=["templates", "validation", "content"]
    ),
    
    # Business logic errors
    "content_generation_failure": ErrorScenario(
        name="Content Generation Failure",
        error_type=ErrorType.BUSINESS_LOGIC_ERROR,
        severity=ErrorSeverity.MEDIUM,
        description="AI content generation fails",
        failure_rate=0.2,  # Occasional failures
        expected_fallback=True,
        min_success_rate=0.8,
        error_message="Content generation service failed",
        tags=["content", "generation", "ai", "business_logic"]
    ),
    
    "image_composition_failure": ErrorScenario(
        name="Image Composition Failure",
        error_type=ErrorType.BUSINESS_LOGIC_ERROR,
        severity=ErrorSeverity.MEDIUM,
        description="Image composition process fails",
        failure_rate=0.1,  # Rare failures
        expected_fallback=True,
        min_success_rate=0.9,
        error_message="Image composition failed",
        tags=["images", "composition", "graphics", "business_logic"]
    ),
    
    # Cascade failure scenario
    "cascade_failure": ErrorScenario(
        name="Cascade Failure",
        error_type=ErrorType.SERVICE_UNAVAILABLE,
        severity=ErrorSeverity.CRITICAL,
        description="Multiple interconnected systems fail simultaneously",
        failure_rate=1.0,
        duration_seconds=45.0,
        recovery_time_seconds=30.0,
        expected_fallback=True,
        max_recovery_time=75.0,
        min_success_rate=0.1,  # Minimal functionality
        error_message="Multiple system components unavailable",
        prerequisites=["database_connection_failure", "line_api_service_unavailable"],
        tags=["cascade", "multiple_failure", "critical", "resilience"]
    )
}


class ErrorSimulator:
    """Utility class for simulating various error conditions"""
    
    def __init__(self):
        self.active_scenarios: Dict[str, ErrorScenario] = {}
        self.scenario_start_times: Dict[str, float] = {}
        
    def activate_scenario(self, scenario_name: str) -> bool:
        """Activate an error scenario"""
        if scenario_name not in ERROR_SCENARIOS:
            return False
            
        scenario = ERROR_SCENARIOS[scenario_name]
        self.active_scenarios[scenario_name] = scenario
        self.scenario_start_times[scenario_name] = time.time()
        
        return True
    
    def deactivate_scenario(self, scenario_name: str) -> bool:
        """Deactivate an error scenario"""
        if scenario_name in self.active_scenarios:
            del self.active_scenarios[scenario_name]
            del self.scenario_start_times[scenario_name]
            return True
        return False
    
    def should_fail(self, scenario_name: str) -> bool:
        """Check if an operation should fail based on active scenarios"""
        if scenario_name not in self.active_scenarios:
            return False
            
        scenario = self.active_scenarios[scenario_name]
        
        # Check if scenario has expired
        if scenario.duration_seconds is not None:
            elapsed = time.time() - self.scenario_start_times[scenario_name]
            if elapsed > scenario.duration_seconds:
                self.deactivate_scenario(scenario_name)
                return False
        
        # Check failure rate probability
        return random.random() < scenario.failure_rate
    
    def get_error_details(self, scenario_name: str) -> Dict[str, Any]:
        """Get error details for a scenario"""
        if scenario_name not in self.active_scenarios:
            return {}
            
        scenario = self.active_scenarios[scenario_name]
        return {
            "error_message": scenario.error_message,
            "error_code": scenario.error_code,
            "http_status_code": scenario.http_status_code,
            "error_type": scenario.error_type.value,
            "severity": scenario.severity.value
        }
    
    def get_active_scenarios(self) -> List[str]:
        """Get list of currently active error scenarios"""
        return list(self.active_scenarios.keys())
    
    def clear_all_scenarios(self):
        """Clear all active error scenarios"""
        self.active_scenarios.clear()
        self.scenario_start_times.clear()


class FallbackValidator:
    """Validates that fallback mechanisms work correctly"""
    
    @staticmethod
    def validate_message_creation_fallback(message, expected_title: str = None) -> Dict[str, Any]:
        """Validate that message creation fallback works"""
        results = {
            "message_created": message is not None,
            "has_contents": False,
            "has_alt_text": False,
            "title_fallback_works": False
        }
        
        if message is not None:
            results["has_contents"] = hasattr(message, 'contents')
            results["has_alt_text"] = hasattr(message, 'alt_text')
            
            if expected_title and hasattr(message, 'alt_text'):
                results["title_fallback_works"] = expected_title in message.alt_text or len(message.alt_text) > 0
        
        return results
    
    @staticmethod
    def validate_broadcast_fallback(result: Dict[str, Any]) -> Dict[str, Any]:
        """Validate that broadcast fallback works"""
        return {
            "result_returned": result is not None,
            "has_success_field": "success" in result if result else False,
            "has_error_handling": "error" in result if result and not result.get("success", True) else True,
            "has_timestamp": "timestamp" in result if result else False
        }
    
    @staticmethod
    def validate_interaction_fallback(result: Dict[str, Any]) -> Dict[str, Any]:
        """Validate that interaction handling fallback works"""
        return {
            "result_returned": result is not None,
            "has_success_field": "success" in result if result else False,
            "has_response_type": "response_type" in result if result else False,
            "error_properly_reported": (
                result.get("success") is False and "error" in result
            ) if result else False
        }
    
    @staticmethod
    def validate_analytics_fallback(exception_raised: bool, data_stored: bool) -> Dict[str, Any]:
        """Validate that analytics fallback works"""
        return {
            "no_exception_raised": not exception_raised,
            "continues_operation": True,  # System should continue even if analytics fail
            "graceful_degradation": not exception_raised  # No crashes from analytics failures
        }


class ErrorTestUtils:
    """Utility functions for error testing"""
    
    @staticmethod
    def simulate_line_api_error(error_type: str, status_code: int = 500, message: str = "API Error") -> Exception:
        """Create a realistic LINE API error"""
        from linebot.exceptions import LineBotApiError
        from unittest.mock import Mock
        
        error_mock = Mock()
        error_mock.message = message
        
        return LineBotApiError(status_code=status_code, error=error_mock)
    
    @staticmethod
    def simulate_network_error(error_type: str = "timeout") -> Exception:
        """Create a realistic network error"""
        from requests.exceptions import Timeout, ConnectionError, RequestException
        
        if error_type == "timeout":
            return Timeout("Request timed out")
        elif error_type == "connection":
            return ConnectionError("Connection failed")
        else:
            return RequestException("Network error occurred")
    
    @staticmethod
    def create_corrupted_data(data_type: str = "json") -> str:
        """Create corrupted data for testing"""
        if data_type == "json":
            return '{"incomplete": "json", "missing": '  # Incomplete JSON
        elif data_type == "image":
            return "Not a valid image file content"
        else:
            return "Corrupted data content"
    
    @staticmethod
    def measure_recovery_time(operation: Callable, max_attempts: int = 10, delay: float = 1.0) -> Dict[str, Any]:
        """Measure how long it takes for an operation to recover from failure"""
        start_time = time.time()
        
        for attempt in range(max_attempts):
            try:
                result = operation()
                recovery_time = time.time() - start_time
                
                return {
                    "recovered": True,
                    "recovery_time_seconds": recovery_time,
                    "attempts_needed": attempt + 1,
                    "result": result
                }
            except Exception as e:
                if attempt < max_attempts - 1:
                    time.sleep(delay)
                else:
                    return {
                        "recovered": False,
                        "recovery_time_seconds": time.time() - start_time,
                        "attempts_needed": max_attempts,
                        "last_error": str(e)
                    }
        
        return {
            "recovered": False,
            "recovery_time_seconds": time.time() - start_time,
            "attempts_needed": max_attempts
        }
    
    @staticmethod
    def validate_error_response(response: Dict[str, Any], expected_fields: List[str] = None) -> bool:
        """Validate that an error response has the expected structure"""
        if expected_fields is None:
            expected_fields = ["success", "error", "timestamp"]
        
        if not isinstance(response, dict):
            return False
        
        # Check that success is False for error responses
        if response.get("success") is not False:
            return False
        
        # Check that all expected fields are present
        for field in expected_fields:
            if field not in response:
                return False
        
        return True
    
    @staticmethod
    def generate_stress_conditions() -> Dict[str, Any]:
        """Generate conditions that stress the system"""
        return {
            "high_load": {
                "concurrent_requests": 50,
                "request_rate_per_second": 100,
                "duration_seconds": 30
            },
            "memory_pressure": {
                "large_content_size": 1000000,  # 1MB content
                "batch_size": 100,
                "retain_references": True
            },
            "network_instability": {
                "packet_loss_rate": 0.1,
                "latency_variance": 0.5,
                "connection_drops": 0.05
            }
        }


# Global error simulator instance
_error_simulator = None

def get_error_simulator() -> ErrorSimulator:
    """Get global error simulator instance"""
    global _error_simulator
    if _error_simulator is None:
        _error_simulator = ErrorSimulator()
    return _error_simulator