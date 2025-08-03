# PRD: Azure OpenAI API Fix for Replit Development

## Document Information
- **Document Type**: Product Requirements Document (PRD) for Replit
- **Project**: LINE Bot Azure OpenAI API Enhancement
- **Version**: 1.0
- **Date**: 2025-08-03
- **Target Platform**: Replit (Python Flask)
- **Status**: Ready for Development

## 1. Introduction/Overview

Fix the recurring 404 "Resource not found" errors in our LINE Bot's Azure OpenAI integration by implementing intelligent API capability detection and seamless fallback mechanisms. The current implementation attempts to use the Azure OpenAI Responses API but fails when the feature flag isn't enabled, creating unnecessary error logs and potential service instability.

**Goal**: Eliminate Azure OpenAI API 404 errors while maintaining full conversational functionality through intelligent API routing and robust error handling.

## 2. Goals

1. **Eliminate 404 Errors**: Stop all unnecessary Responses API calls when endpoint is unavailable
2. **Intelligent Routing**: Automatically detect and route to available Azure OpenAI APIs
3. **Seamless Operation**: Maintain current user experience with zero downtime
4. **Operational Excellence**: Reduce error log noise and improve monitoring clarity
5. **Future-Proofing**: Handle Azure OpenAI feature flag changes gracefully

## 3. User Stories

1. **As a LINE Bot user**, I want my messages processed reliably without service interruptions caused by API errors
2. **As a developer**, I want clear visibility into which Azure OpenAI APIs are available and being used
3. **As a system administrator**, I want reduced error logs and cleaner monitoring dashboards
4. **As a LINE Bot user**, I want the same conversational quality regardless of which Azure OpenAI API is used behind the scenes
5. **As a developer**, I want the system to automatically adapt to Azure OpenAI feature availability changes

## 4. Functional Requirements

1. **API Capability Detection**: System must detect Azure OpenAI API availability on startup and cache results
2. **Intelligent API Routing**: System must automatically route requests to available APIs (Responses API preferred, Chat Completions fallback)
3. **Error Classification**: System must distinguish between temporary failures and permanent feature unavailability
4. **Graceful Fallback**: System must seamlessly switch to Chat Completions API when Responses API returns 404
5. **Configuration Management**: System must support manual API preference overrides via environment variables
6. **Caching Mechanism**: System must cache API capability detection results with configurable TTL
7. **Enhanced Logging**: System must provide clear, actionable error messages without sensitive data exposure
8. **Health Monitoring**: System must expose API status through health check endpoints
9. **Circuit Breaker**: System must prevent repeated calls to known unavailable endpoints
10. **Performance Maintenance**: API detection must not impact response times for user interactions

## 5. Replit Deployment Specifications

### Platform Type
- **Type**: Flask Web Application (webhook service enhancement)
- **Current Setup**: Existing LINE Bot webhook service
- **Modification Scope**: Internal service enhancements only

### Port Configuration
- **Port**: 5000 (existing Flask setup)
- **Binding**: 0.0.0.0:5000 (already configured)
- **Protocol**: HTTP/HTTPS webhook endpoint

### Workflow Command
```bash
gunicorn --bind 0.0.0.0:5000 --reuse-port --reload main:app
```
*(No changes to existing workflow)*

### Dependencies
**New packages to add**:
```txt
aiofiles>=0.8.0  # For async file operations
```
**Existing packages** (already installed):
- flask
- httpx
- openai
- psycopg2-binary
- python-dotenv

### Environment Variables
**New variables needed**:
```env
# API Detection Configuration
AZURE_OPENAI_PREFER_RESPONSES_API=true
AZURE_OPENAI_CAPABILITY_CACHE_TTL=300
AZURE_OPENAI_ENABLE_STARTUP_VALIDATION=true

# Debug/Override Options
AZURE_OPENAI_FORCE_CHAT_COMPLETIONS=false
AZURE_OPENAI_DEBUG_API_DETECTION=false
```

**Existing variables** (no changes needed):
- AZURE_OPENAI_API_KEY
- AZURE_OPENAI_ENDPOINT  
- AZURE_OPENAI_DEPLOYMENT_NAME

## 6. Database & Storage Requirements

### Database Type
- **Primary**: File-based JSON storage for lightweight caching
- **Location**: `data/api_capabilities.json`
- **Backup**: In-memory fallback for file access failures

### Schema Design
```json
{
  "last_updated": "2025-08-03T10:00:00Z",
  "ttl_seconds": 300,
  "capabilities": {
    "responses_api_available": true,
    "chat_completions_available": true,
    "models_endpoint_available": true,
    "deployment_accessible": true
  },
  "detection_history": [
    {
      "timestamp": "2025-08-03T10:00:00Z",
      "responses_api": true,
      "chat_completions": true
    }
  ]
}
```

### Data Migration
- **No existing data impact**: New feature with isolated storage
- **File creation**: Auto-create capability cache file on first run
- **Graceful degradation**: Continue operation if file storage unavailable

### Backup/Recovery
- **In-memory cache**: Primary operation continues if file unavailable
- **Auto-recovery**: Re-detect capabilities if cache corrupted
- **No critical data**: Cache loss only triggers re-detection

## 7. Performance Requirements

### Response Time Targets
- **API Routing Decision**: <50ms (real-time routing)
- **Capability Detection**: <500ms on startup
- **Cache Operations**: <10ms for reads
- **User Message Processing**: Maintain current <2s target

### Resource Constraints
- **Memory**: <5MB additional for capability caching
- **CPU**: <1% additional overhead for routing logic
- **Storage**: <1MB for capability cache and logs
- **Network**: Minimal additional calls (startup detection only)

### Scalability Needs
- **Current Load**: Support existing LINE Bot usage patterns
- **Growth**: No impact on horizontal scaling
- **Efficiency**: Reduce unnecessary API calls by 100%

### Monitoring
- **Health Endpoint**: `/health/azure-openai` for API status
- **Metrics**: Track API usage distribution and error rates
- **Logging**: Enhanced structured logging for troubleshooting

## 8. External Integrations

### APIs Required
- **Azure OpenAI Responses API**: Primary preference (when available)
- **Azure OpenAI Chat Completions API**: Reliable fallback
- **Azure OpenAI Models API**: For capability detection

### Authentication
- **Existing**: Continue using current AZURE_OPENAI_API_KEY
- **No changes**: Maintain current authentication patterns
- **Security**: No additional credentials needed

### Rate Limits
- **Detection calls**: Minimal impact (startup + TTL refresh)
- **User calls**: No change to existing rate limit handling
- **Fallback**: Seamless transition maintains rate limit budgets

### Error Handling
- **Network timeouts**: 10-second timeout for detection calls
- **Authentication errors**: Fail fast with clear error messages
- **Service unavailable**: Graceful degradation to available APIs
- **Invalid responses**: Log and retry with exponential backoff

## 9. Security & Configuration

### Secrets Management
- **Existing secrets**: No changes to current API key management
- **New configuration**: Environment variables for behavior control
- **No exposure**: Capability detection doesn't require additional secrets

### Access Control
- **Current access**: Maintain existing LINE webhook access patterns
- **Admin endpoints**: Health checks accessible for monitoring
- **No authentication changes**: Internal routing logic only

### Data Privacy
- **No user data**: Capability detection uses technical endpoints only
- **Logging**: Exclude API keys and user content from detection logs
- **Cache data**: Only technical capability flags stored

### CORS/Headers
- **No changes**: Existing webhook configuration sufficient
- **Health endpoints**: Standard JSON response headers
- **Security headers**: Maintain current security posture

## 10. Non-Goals (Out of Scope)

1. **User Interface Changes**: No changes to LINE Bot user experience
2. **New Features**: No additional AI capabilities or conversation features
3. **Database Migration**: No changes to existing conversation storage
4. **Authentication Changes**: No modifications to current security model
5. **Performance Optimization**: No general performance improvements outside API routing
6. **Monitoring Dashboard**: No new admin UI (health endpoints only)
7. **API Key Rotation**: No changes to current credential management
8. **Multi-tenant Support**: No support for multiple Azure OpenAI endpoints

## 11. Replit Development Considerations

### File Structure
```
src/
├── services/
│   ├── openai_service.py          # Enhanced with capability detection
│   └── azure_api_detector.py      # New: API capability detection
├── utils/
│   ├── api_router.py              # New: Intelligent API routing
│   └── capability_cache.py        # New: File-based caching
├── config/
│   └── settings.py                # Enhanced with new config options
└── exceptions/
    └── azure_openai_exceptions.py # New: Structured error types

data/
└── api_capabilities.json          # New: Capability cache file
```

### Replit Features Used
- **File Storage**: JSON-based capability caching
- **Environment Variables**: Configuration management
- **Health Checks**: Built-in monitoring endpoints
- **Logging**: Enhanced structured logging

### Testing Strategy
- **Unit Tests**: Mock Azure OpenAI responses for different scenarios
- **Integration Tests**: Test with real Azure endpoints in development
- **Error Simulation**: Test fallback mechanisms with network failures
- **Performance Tests**: Validate routing overhead is minimal

### Debugging
- **Structured Logging**: Clear API routing decisions and errors
- **Debug Mode**: Optional verbose logging for troubleshooting
- **Health Endpoints**: Real-time API status visibility
- **Error Classification**: Distinct error types for different failure modes

## 12. Success Metrics

### Technical Metrics
- **Error Reduction**: 100% elimination of Azure OpenAI 404 errors
- **Response Time**: <50ms overhead for API routing decisions
- **Uptime**: Maintain 99.9% service availability during API changes
- **Cache Hit Rate**: >95% cache hits for capability queries

### Business Metrics
- **User Experience**: Zero user-facing errors from API issues
- **Operational Efficiency**: 90% reduction in error log volume
- **Developer Productivity**: Clear API status visibility
- **System Reliability**: Graceful handling of Azure feature flag changes

### Monitoring Dashboards
- **API Usage Distribution**: Percentage using Responses vs Chat Completions
- **Error Rate Trends**: Track remaining error patterns
- **Performance Impact**: Monitor routing overhead
- **Capability Detection**: Track Azure feature availability over time

## 13. Deployment Checklist

- [ ] **Dependencies installed**: Verify aiofiles package availability
- [ ] **Environment variables configured**: Set API detection preferences
- [ ] **File permissions**: Ensure data/ directory is writable
- [ ] **Azure API access tested**: Validate current credentials work
- [ ] **Capability detection working**: Test startup validation
- [ ] **Fallback mechanisms tested**: Simulate API unavailability
- [ ] **Health check endpoint**: Verify `/health/azure-openai` responds
- [ ] **Error handling tested**: Test various failure scenarios
- [ ] **Performance validated**: Confirm routing overhead <50ms
- [ ] **Logging configured**: Verify structured error logging
- [ ] **Cache functionality**: Test capability cache read/write
- [ ] **Circuit breaker working**: Test repeated failure handling
- [ ] **Ready for Replit deployment**: All components integration tested

## 14. Open Questions

1. **Cache TTL Optimization**: Should capability cache TTL be dynamic based on Azure API stability patterns?
2. **Monitoring Integration**: Should we add Prometheus metrics for detailed API usage tracking?
3. **Recovery Strategies**: Should we implement automatic retry for capability detection failures?
4. **Configuration Hot-reloading**: Should API preferences be updateable without service restart?
5. **Error Notification**: Should persistent API unavailability trigger external alerts?

---

**Next Steps**: Begin implementation with Phase 1 (API capability detection) following the existing codebase patterns and Replit deployment workflows.