"""
Metrics collection for Azure OpenAI API usage tracking and monitoring.

This module provides comprehensive metrics collection for API usage distribution,
error rates, performance tracking, and intelligent routing effectiveness.
"""

import time
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List
from collections import defaultdict, deque
from threading import Lock
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)


class APIType(Enum):
    """API type enumeration for metrics tracking"""
    RESPONSES_API = "responses_api"
    CHAT_COMPLETIONS = "chat_completions"
    MODELS_API = "models_api"


class MetricType(Enum):
    """Types of metrics being collected"""
    REQUEST_COUNT = "request_count"
    SUCCESS_COUNT = "success_count"
    ERROR_COUNT = "error_count"
    RESPONSE_TIME = "response_time"
    ROUTING_DECISION = "routing_decision"
    ERROR_TYPE = "error_type"


@dataclass
class APIMetrics:
    """Metrics data structure for API usage"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    avg_response_time_ms: float = 0.0
    error_rate_percent: float = 0.0
    last_request_time: Optional[str] = None
    last_error_time: Optional[str] = None
    last_error_message: Optional[str] = None


@dataclass
class RoutingMetrics:
    """Metrics for intelligent routing decisions"""
    total_routing_decisions: int = 0
    responses_api_chosen: int = 0
    chat_completions_chosen: int = 0
    fallback_decisions: int = 0
    avg_routing_time_ms: float = 0.0
    cache_hit_rate_percent: float = 0.0


@dataclass
class ErrorMetrics:
    """Detailed error tracking metrics"""
    total_errors: int = 0
    error_404_count: int = 0
    error_429_count: int = 0
    error_auth_count: int = 0
    error_timeout_count: int = 0
    error_other_count: int = 0
    recent_errors: List[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.recent_errors is None:
            self.recent_errors = []


class MetricsCollector:
    """
    Comprehensive metrics collector for Azure OpenAI API usage and routing.
    
    Provides thread-safe collection of:
    - API usage statistics (Responses vs Chat Completions)
    - Error rates and types
    - Performance metrics
    - Routing decision effectiveness
    - Cache performance
    """
    
    def __init__(self, persistence_file: str = "data/api_metrics.json", max_recent_errors: int = 50):
        self.persistence_file = Path(persistence_file)
        self.max_recent_errors = max_recent_errors
        self._lock = Lock()
        
        # Core metrics storage
        self.api_metrics: Dict[APIType, APIMetrics] = {
            api_type: APIMetrics() for api_type in APIType
        }
        self.routing_metrics = RoutingMetrics()
        self.error_metrics = ErrorMetrics(recent_errors=[])
        
        # Performance tracking
        self._response_times = defaultdict(lambda: deque(maxlen=100))  # Last 100 response times per API
        self._routing_times = deque(maxlen=100)  # Last 100 routing decision times
        self._cache_hits = deque(maxlen=100)  # Cache hit tracking
        
        # Error tracking
        self._recent_errors = deque(maxlen=self.max_recent_errors)
        
        # Initialize from persistence
        self._load_metrics()
        
        logger.info(f"Initialized MetricsCollector with persistence: {self.persistence_file}")
    
    def record_api_request(
        self,
        api_type: APIType,
        success: bool,
        response_time_ms: float,
        error_message: Optional[str] = None,
        error_code: Optional[str] = None,
        correlation_id: Optional[str] = None
    ):
        """
        Record an API request and its outcome.
        
        Args:
            api_type: Which API was used
            success: Whether the request succeeded
            response_time_ms: Response time in milliseconds
            error_message: Error message if failed
            error_code: Error code if failed
            correlation_id: Request correlation ID
        """
        with self._lock:
            metrics = self.api_metrics[api_type]
            current_time = datetime.now().isoformat()
            
            # Update basic counters
            metrics.total_requests += 1
            metrics.last_request_time = current_time
            
            if success:
                metrics.successful_requests += 1
            else:
                metrics.failed_requests += 1
                metrics.last_error_time = current_time
                metrics.last_error_message = error_message
                
                # Track detailed error metrics
                self._record_error(api_type, error_message, error_code, correlation_id)
            
            # Update response time tracking
            self._response_times[api_type].append(response_time_ms)
            self._update_avg_response_time(api_type)
            
            # Update error rate
            if metrics.total_requests > 0:
                metrics.error_rate_percent = (metrics.failed_requests / metrics.total_requests) * 100
            
            logger.debug(f"Recorded {api_type.value} request: success={success}, time={response_time_ms:.1f}ms")
    
    def record_routing_decision(
        self,
        chosen_api: APIType,
        routing_time_ms: float,
        cache_hit: bool = False,
        fallback_used: bool = False,
        reason: Optional[str] = None
    ):
        """
        Record an intelligent routing decision.
        
        Args:
            chosen_api: Which API was chosen
            routing_time_ms: Time taken to make routing decision
            cache_hit: Whether cached capabilities were used
            fallback_used: Whether fallback logic was used
            reason: Reason for the routing decision
        """
        with self._lock:
            self.routing_metrics.total_routing_decisions += 1
            
            if chosen_api == APIType.RESPONSES_API:
                self.routing_metrics.responses_api_chosen += 1
            elif chosen_api == APIType.CHAT_COMPLETIONS:
                self.routing_metrics.chat_completions_chosen += 1
            
            if fallback_used:
                self.routing_metrics.fallback_decisions += 1
            
            # Update routing time tracking
            self._routing_times.append(routing_time_ms)
            if self._routing_times:
                self.routing_metrics.avg_routing_time_ms = sum(self._routing_times) / len(self._routing_times)
            
            # Update cache hit rate
            self._cache_hits.append(cache_hit)
            if self._cache_hits:
                cache_hits = sum(1 for hit in self._cache_hits if hit)
                self.routing_metrics.cache_hit_rate_percent = (cache_hits / len(self._cache_hits)) * 100
            
            logger.debug(f"Recorded routing decision: {chosen_api.value}, time={routing_time_ms:.1f}ms, cache_hit={cache_hit}")
    
    def _record_error(
        self,
        api_type: APIType,
        error_message: Optional[str],
        error_code: Optional[str],
        correlation_id: Optional[str]
    ):
        """Record detailed error information"""
        self.error_metrics.total_errors += 1
        
        # Classify error types
        error_lower = (error_message or "").lower()
        if "404" in error_lower or "not found" in error_lower:
            self.error_metrics.error_404_count += 1
        elif "429" in error_lower or "rate limit" in error_lower:
            self.error_metrics.error_429_count += 1
        elif "auth" in error_lower or "unauthorized" in error_lower:
            self.error_metrics.error_auth_count += 1
        elif "timeout" in error_lower:
            self.error_metrics.error_timeout_count += 1
        else:
            self.error_metrics.error_other_count += 1
        
        # Store recent error details
        error_record = {
            'timestamp': datetime.now().isoformat(),
            'api_type': api_type.value,
            'error_message': error_message,
            'error_code': error_code,
            'correlation_id': correlation_id
        }
        self._recent_errors.append(error_record)
        self.error_metrics.recent_errors = list(self._recent_errors)
    
    def _update_avg_response_time(self, api_type: APIType):
        """Update average response time for an API"""
        times = self._response_times[api_type]
        if times:
            self.api_metrics[api_type].avg_response_time_ms = sum(times) / len(times)
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive metrics summary.
        
        Returns:
            Dictionary containing all metrics data
        """
        with self._lock:
            return {
                'timestamp': datetime.now().isoformat(),
                'api_metrics': {
                    api_type.value: asdict(metrics) 
                    for api_type, metrics in self.api_metrics.items()
                },
                'routing_metrics': asdict(self.routing_metrics),
                'error_metrics': asdict(self.error_metrics),
                'performance_summary': {
                    'total_requests': sum(m.total_requests for m in self.api_metrics.values()),
                    'total_errors': self.error_metrics.total_errors,
                    'overall_error_rate_percent': self._calculate_overall_error_rate(),
                    'api_distribution': self._calculate_api_distribution(),
                    'most_common_error_type': self._get_most_common_error_type()
                }
            }
    
    def get_api_usage_distribution(self) -> Dict[str, float]:
        """Get percentage distribution of API usage"""
        return self._calculate_api_distribution()
    
    def get_error_summary(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get error summary for the specified time period.
        
        Args:
            hours: Number of hours to look back
            
        Returns:
            Error summary data
        """
        with self._lock:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            
            recent_errors = [
                error for error in self._recent_errors
                if datetime.fromisoformat(error['timestamp']) > cutoff_time
            ]
            
            return {
                'time_period_hours': hours,
                'total_errors': len(recent_errors),
                'error_types': self._analyze_error_types(recent_errors),
                'errors_by_api': self._analyze_errors_by_api(recent_errors),
                'recent_errors': recent_errors[-10:] if recent_errors else []  # Last 10 errors
            }
    
    def _calculate_overall_error_rate(self) -> float:
        """Calculate overall error rate across all APIs"""
        total_requests = sum(m.total_requests for m in self.api_metrics.values())
        total_errors = sum(m.failed_requests for m in self.api_metrics.values())
        
        if total_requests == 0:
            return 0.0
        return (total_errors / total_requests) * 100
    
    def _calculate_api_distribution(self) -> Dict[str, float]:
        """Calculate percentage distribution of API usage"""
        total_requests = sum(m.total_requests for m in self.api_metrics.values())
        
        if total_requests == 0:
            return {api_type.value: 0.0 for api_type in APIType}
        
        return {
            api_type.value: (metrics.total_requests / total_requests) * 100
            for api_type, metrics in self.api_metrics.items()
        }
    
    def _get_most_common_error_type(self) -> str:
        """Get the most common error type"""
        error_counts = {
            '404_not_found': self.error_metrics.error_404_count,
            '429_rate_limit': self.error_metrics.error_429_count,
            'authentication': self.error_metrics.error_auth_count,
            'timeout': self.error_metrics.error_timeout_count,
            'other': self.error_metrics.error_other_count
        }
        
        if not any(error_counts.values()):
            return 'none'
        
        return max(error_counts.items(), key=lambda x: x[1])[0]
    
    def _analyze_error_types(self, errors: List[Dict[str, Any]]) -> Dict[str, int]:
        """Analyze error types in a list of errors"""
        error_types = defaultdict(int)
        
        for error in errors:
            error_msg = (error.get('error_message') or '').lower()
            if '404' in error_msg or 'not found' in error_msg:
                error_types['404_not_found'] += 1
            elif '429' in error_msg or 'rate limit' in error_msg:
                error_types['429_rate_limit'] += 1
            elif 'auth' in error_msg or 'unauthorized' in error_msg:
                error_types['authentication'] += 1
            elif 'timeout' in error_msg:
                error_types['timeout'] += 1
            else:
                error_types['other'] += 1
        
        return dict(error_types)
    
    def _analyze_errors_by_api(self, errors: List[Dict[str, Any]]) -> Dict[str, int]:
        """Analyze errors by API type"""
        api_errors = defaultdict(int)
        for error in errors:
            api_type = error.get('api_type', 'unknown')
            api_errors[api_type] += 1
        return dict(api_errors)
    
    def persist_metrics(self):
        """Save metrics to persistent storage"""
        try:
            metrics_data = self.get_metrics_summary()
            
            # Ensure directory exists
            self.persistence_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.persistence_file, 'w') as f:
                json.dump(metrics_data, f, indent=2)
            
            logger.debug(f"Persisted metrics to {self.persistence_file}")
            
        except Exception as e:
            logger.error(f"Failed to persist metrics: {e}")
    
    def _load_metrics(self):
        """Load metrics from persistent storage"""
        try:
            if not self.persistence_file.exists():
                logger.debug("No existing metrics file found, starting fresh")
                return
            
            with open(self.persistence_file, 'r') as f:
                data = json.load(f)
            
            # Load API metrics
            if 'api_metrics' in data:
                for api_name, metrics_data in data['api_metrics'].items():
                    try:
                        api_type = APIType(api_name)
                        self.api_metrics[api_type] = APIMetrics(**metrics_data)
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Failed to load metrics for {api_name}: {e}")
            
            # Load routing metrics
            if 'routing_metrics' in data:
                try:
                    self.routing_metrics = RoutingMetrics(**data['routing_metrics'])
                except TypeError as e:
                    logger.warning(f"Failed to load routing metrics: {e}")
            
            # Load error metrics
            if 'error_metrics' in data:
                try:
                    error_data = data['error_metrics']
                    # Ensure recent_errors is a list
                    if 'recent_errors' not in error_data:
                        error_data['recent_errors'] = []
                    self.error_metrics = ErrorMetrics(**error_data)
                    # Populate deque from loaded data
                    self._recent_errors.extend(error_data.get('recent_errors', []))
                except TypeError as e:
                    logger.warning(f"Failed to load error metrics: {e}")
            
            logger.info(f"Loaded metrics from {self.persistence_file}")
            
        except Exception as e:
            logger.error(f"Failed to load metrics from {self.persistence_file}: {e}")


# Global metrics collector instance
_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector instance"""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


def record_api_request(api_type: APIType, success: bool, response_time_ms: float, **kwargs):
    """Convenience function to record API request"""
    collector = get_metrics_collector()
    collector.record_api_request(api_type, success, response_time_ms, **kwargs)


def record_routing_decision(chosen_api: APIType, routing_time_ms: float, **kwargs):
    """Convenience function to record routing decision"""
    collector = get_metrics_collector()
    collector.record_routing_decision(chosen_api, routing_time_ms, **kwargs)


def get_metrics_summary() -> Dict[str, Any]:
    """Convenience function to get metrics summary"""
    collector = get_metrics_collector()
    return collector.get_metrics_summary()


def persist_metrics():
    """Convenience function to persist metrics"""
    collector = get_metrics_collector()
    collector.persist_metrics()