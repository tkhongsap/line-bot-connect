# Tasks: Azure OpenAI API Fix for Replit Development

Based on PRD: `tasks/prd-azure-openai-api-fix-replit.md`

## Relevant Files

- `src/config/centralized_config.py` - Add new Azure OpenAI configuration options for API detection and preferences
- `src/config/config_adapters.py` - Update adapter to expose new configuration options
- `src/config/validation.py` - Add validation rules for new configuration options
- `src/services/openai_service.py` - Enhance existing service with improved capability detection and routing
- `src/utils/azure_api_detector.py` - New: API capability detection and caching utility
- `src/utils/capability_cache.py` - New: File-based capability caching with TTL management
- `src/utils/api_router.py` - New: Intelligent API routing logic based on capabilities
- `src/exceptions/azure_openai_exceptions.py` - New: Structured error types for Azure OpenAI
- `src/routes/admin_routes.py` - Add health check endpoints for API status monitoring
- `data/api_capabilities.json` - New: Capability cache storage file
- `tests/unit/test_azure_api_detector.py` - Unit tests for API detector
- `tests/unit/test_capability_cache.py` - Unit tests for capability cache
- `tests/unit/test_api_router.py` - Unit tests for API router
- `tests/integration/test_openai_service_enhanced.py` - Integration tests for enhanced OpenAI service
- `tests/unit/test_azure_openai_exceptions.py` - Unit tests for new exception types

### Notes

- Unit tests should be placed in `tests/unit/` directory following existing project patterns
- Integration tests should be placed in `tests/integration/` directory
- Use `pytest` to run tests following existing project testing framework
- File-based caching uses `data/` directory which already exists in the project structure

## Tasks

- [x] 1.0 Enhanced Configuration Management
  - [x] 1.1 Add new fields to `AzureOpenAIConfig` model: `prefer_responses_api`, `force_chat_completions`, `capability_cache_ttl`, `enable_startup_validation`
  - [x] 1.2 Update `config_adapters.py` to expose new configuration options with backward compatibility
  - [x] 1.3 Add validation rules in `validation.py` for new configuration fields and logical combinations
  - [x] 1.4 Update environment variable loading in `centralized_config.py` `from_env` method for new options
  - [x] 1.5 Add configuration validation method to detect conflicting settings (e.g., prefer_responses_api + force_chat_completions)

- [x] 2.0 API Capability Detection System
  - [x] 2.1 Create `azure_api_detector.py` with `AzureOpenAICapabilityDetector` class for endpoint testing
  - [x] 2.2 Implement `detect_capabilities()` method to test Responses API, Chat Completions, and Models endpoints
  - [x] 2.3 Create `capability_cache.py` with JSON file-based caching, TTL management, and in-memory fallback
  - [x] 2.4 Add `_test_responses_api()`, `_test_chat_completions()`, and `_test_models_endpoint()` methods with proper error handling
  - [x] 2.5 Implement startup validation in detector with configurable timeout and retry logic
  - [x] 2.6 Add cache invalidation and refresh mechanisms with background updates

- [x] 3.0 Intelligent API Routing Logic
  - [x] 3.1 Create `api_router.py` with `APIRouter` class that makes routing decisions based on capabilities
  - [x] 3.2 Enhance `openai_service.py` to integrate capability detection and intelligent routing on initialization
  - [x] 3.3 Update `_should_use_responses_api()` method to use capability detection instead of basic circuit breaker
  - [x] 3.4 Implement preference override logic to respect force_chat_completions and prefer_responses_api settings
  - [x] 3.5 Add performance monitoring for routing decisions to ensure <50ms overhead target
  - [x] 3.6 Update circuit breaker logic to permanently cache 404 errors and avoid repeated failed attempts

- [x] 4.0 Health Monitoring & Error Handling
  - [x] 4.1 Create `azure_openai_exceptions.py` with structured error types: `FeatureNotEnabledError`, `DeploymentNotFoundError`, `AuthenticationFailedError`
  - [x] 4.2 Add `/health/azure-openai` endpoint in `admin_routes.py` that exposes current API capabilities and status
  - [x] 4.3 Enhance error logging in `openai_service.py` with structured logging and correlation IDs for troubleshooting
  - [x] 4.4 Update error handling to classify errors properly and provide actionable error messages
  - [x] 4.5 Add metrics collection for API usage distribution (Responses vs Chat Completions) and error rates
  - [x] 4.6 Implement graceful degradation messaging that clearly indicates which API is being used

- [ ] 5.0 Integration & Testing
  - [ ] 5.1 Create unit tests for `azure_api_detector.py` with mocked Azure OpenAI responses for various scenarios
  - [ ] 5.2 Create unit tests for `capability_cache.py` testing TTL behavior, file operations, and in-memory fallback
  - [ ] 5.3 Create unit tests for `api_router.py` testing routing decisions based on different capability combinations
  - [ ] 5.4 Create integration tests for enhanced `openai_service.py` testing full capability detection and routing flow
  - [ ] 5.5 Add performance tests to validate routing overhead stays under 50ms target
  - [ ] 5.6 Create error scenario tests simulating network failures, invalid configs, and Azure API changes
  - [ ] 5.7 Update project documentation and deployment checklist with new configuration options and validation steps