# Azure OpenAI Intelligent Routing Guide

## Overview

This document provides comprehensive guidance on the intelligent Azure OpenAI API routing system implemented to eliminate 404 errors and provide seamless fallback between Responses API and Chat Completions API.

## Architecture

### Core Components

1. **AzureOpenAICapabilityDetector** (`src/utils/azure_api_detector.py`)
   - Detects API capabilities through lightweight test calls
   - Classifies errors into structured exception types
   - Provides deployment region detection

2. **CapabilityCache** (`src/utils/capability_cache.py`)
   - File-based caching with TTL management (default: 5 minutes)
   - In-memory fallback for performance
   - Automatic cache invalidation and refresh

3. **APIRouter** (`src/utils/api_router.py`)
   - Makes intelligent routing decisions based on cached capabilities
   - Respects configuration preferences
   - Performance monitoring with <50ms overhead target

4. **Enhanced OpenAI Service** (`src/services/openai_service.py`)
   - Integrated intelligent routing
   - Structured error handling with correlation IDs
   - Comprehensive metrics collection

## Configuration Options

### Environment Variables

```bash
# Core Azure OpenAI settings (existing)
AZURE_OPENAI_API_KEY=your-api-key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
AZURE_OPENAI_DEPLOYMENT_NAME=your-deployment
AZURE_OPENAI_API_VERSION=2024-02-15-preview

# New intelligent routing settings (optional)
AZURE_OPENAI_PREFER_RESPONSES_API=true        # Default: true
AZURE_OPENAI_FORCE_CHAT_COMPLETIONS=false    # Default: false
AZURE_OPENAI_CAPABILITY_CACHE_TTL=300        # Default: 300 seconds
AZURE_OPENAI_ENABLE_STARTUP_VALIDATION=true  # Default: true
```

### Centralized Configuration

The system uses centralized configuration from `src/config/centralized_config.py`:

```python
azure_openai:
  prefer_responses_api: true
  force_chat_completions: false
  capability_cache_ttl: 300
  enable_startup_validation: true
  routing_performance_threshold_ms: 50
```

## API Routing Logic

### Decision Flow

1. **Configuration Override Check**
   - If `force_chat_completions=true`, use Chat Completions API
   - Continue to capability detection if not overridden

2. **Capability Cache Lookup**
   - Check cached capabilities with TTL validation
   - Return cached decision if valid
   - Proceed to capability detection if cache miss/expired

3. **Intelligent Routing Decision**
   - Use Responses API if available and preferred
   - Fall back to Chat Completions API if Responses API unavailable
   - Default to Chat Completions for safety on errors

### Performance Targets

- **Routing Decision Overhead**: <50ms (typically <25ms with cache hits)
- **Cache File Access**: <10ms
- **Memory Usage**: <1MB additional overhead

## Error Handling

### Structured Exception Types

1. **FeatureNotEnabledError**
   - Responses API not enabled in deployment
   - Automatic fallback to Chat Completions

2. **DeploymentNotFoundError**
   - Deployment name incorrect or deleted
   - Cached permanently to avoid repeated failures

3. **AuthenticationFailedError**
   - Invalid API key or insufficient permissions
   - Requires user intervention

4. **QuotaExceededError**
   - Rate limits or quota exceeded
   - Temporary degradation with retry logic

5. **APICapabilityError**
   - General capability detection issues
   - Graceful degradation to Chat Completions

### Error Classification

All OpenAI API errors are automatically classified and wrapped with:
- Correlation ID for tracking
- Structured error information
- Fallback availability indication
- Actionable error messages

## Monitoring and Health Checks

### Health Monitoring Endpoint

Access real-time system health at `/admin/health/azure-openai`:

```json
{
  "status": "healthy|degraded|unhealthy",
  "timestamp": "2025-08-03T12:00:00Z",
  "api_capabilities": {
    "responses_api": true,
    "chat_completions": true,
    "responses_api_error": null
  },
  "performance_metrics": {
    "total_requests": 1000,
    "success_rate": 0.98,
    "average_response_time_ms": 275.5
  },
  "connection_info": {
    "active_connections": 8,
    "total_pools": 2
  },
  "cache_info": {
    "last_updated": "2025-08-03T11:55:00Z",
    "ttl_seconds": 300,
    "cache_hit_rate": 0.95
  },
  "deployment_info": {
    "region": "eastus",
    "api_version": "2024-02-15-preview"
  }
}
```

### Metrics Collection

The system collects comprehensive metrics:

- **API Usage Distribution**: Responses API vs Chat Completions usage
- **Routing Performance**: Decision times and cache hit rates
- **Error Rates**: Success/failure rates by API type
- **Response Times**: Average response times by endpoint

## Troubleshooting

### Common Issues

1. **404 Errors from Responses API**
   - **Symptom**: Persistent 404s despite valid configuration
   - **Solution**: System automatically detects and caches 404s, falling back to Chat Completions
   - **Verification**: Check `/admin/health/azure-openai` for capability status

2. **Slow Routing Decisions**
   - **Symptom**: Routing overhead >50ms
   - **Causes**: Cache file corruption, disk I/O issues
   - **Solution**: Clear cache file in `data/api_capabilities.json`

3. **Authentication Errors**
   - **Symptom**: `AuthenticationFailedError` exceptions
   - **Solution**: Verify API key and endpoint configuration
   - **Check**: Ensure key has proper permissions for deployment

4. **Cache Issues**
   - **Symptom**: Repeated capability detection calls
   - **Solution**: Check file permissions on `data/` directory
   - **Fallback**: System uses in-memory cache if file access fails

### Debug Information

Enable debug logging for detailed routing information:

```python
import logging
logging.getLogger('src.utils.api_router').setLevel(logging.DEBUG)
logging.getLogger('src.services.openai_service').setLevel(logging.DEBUG)
```

### Performance Analysis

Monitor routing performance:

```bash
# Check routing metrics
curl http://localhost:5000/admin/health/azure-openai | jq '.performance_metrics'

# Analyze log patterns
grep -E "(routing_time_ms|performance_threshold)" app.log
```

## Best Practices

### Development

1. **Always Use Correlation IDs**
   ```python
   result = await openai_service.process_message_async(
       user_id="user-123",
       message="Hello",
       correlation_id="request-456"
   )
   ```

2. **Handle Structured Exceptions**
   ```python
   try:
       result = await openai_service.process_message_async(...)
   except AuthenticationFailedError as e:
       logger.error(f"Auth failed: {e} (correlation: {e.correlation_id})")
   except APICapabilityError as e:
       logger.warning(f"API issue: {e}, fallback available: {e.fallback_available}")
   ```

3. **Monitor Performance**
   - Check routing overhead regularly
   - Alert on >50ms routing times
   - Monitor cache hit rates

### Production Deployment

1. **Cache File Permissions**
   ```bash
   # Ensure cache directory is writable
   mkdir -p data/
   chmod 755 data/
   ```

2. **Health Check Integration**
   ```bash
   # Add to deployment health checks
   curl -f http://localhost:5000/admin/health/azure-openai
   ```

3. **Log Monitoring**
   ```bash
   # Monitor for routing issues
   tail -f app.log | grep -E "(routing|degradation|fallback)"
   ```

## API Compatibility

### Backwards Compatibility

The intelligent routing system maintains full backwards compatibility:

- Existing code continues working without changes
- Same response formats and error handling
- No breaking changes to public APIs

### Migration Path

No migration is required - the system automatically:
1. Detects existing deployment capabilities
2. Caches results for performance
3. Routes requests intelligently
4. Falls back gracefully on errors

## Testing

### Unit Tests

```bash
# Run capability detection tests
python -m pytest tests/unit/test_azure_api_detector.py -v

# Run routing logic tests  
python -m pytest tests/unit/test_api_router.py -v

# Run cache functionality tests
python -m pytest tests/unit/test_capability_cache.py -v
```

### Integration Tests

```bash
# Run full integration tests
python -m pytest tests/integration/test_openai_service_integration.py -v

# Run health monitoring tests
python -m pytest tests/integration/test_health_monitoring.py -v
```

### Performance Tests

```bash
# Validate <50ms routing overhead
python -m pytest tests/performance/test_routing_performance.py -v
```

### Error Scenario Tests

```bash
# Test error handling and recovery
python -m pytest tests/error_scenarios/test_azure_openai_error_scenarios.py -v
```

## Support

For issues related to the intelligent routing system:

1. **Check Health Endpoint**: `/admin/health/azure-openai`
2. **Review Logs**: Look for correlation IDs and structured error messages
3. **Validate Configuration**: Ensure all required environment variables are set
4. **Clear Cache**: Delete `data/api_capabilities.json` if routing seems stuck
5. **Test Manually**: Use the health endpoint to trigger capability detection

The system is designed to be self-healing and will automatically recover from most issues through its intelligent fallback mechanisms.