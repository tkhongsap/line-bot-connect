# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common Development Commands

### Running the Application
```bash
# Development mode
python app.py

# Production mode with gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app

# Replit deployment (alternative entry point)
gunicorn --bind 0.0.0.0:5000 main:app
```

### Testing
```bash
# Install test dependencies and run all tests
./scripts/run_tests.sh install
./scripts/run_tests.sh all

# Run with coverage (minimum 80% required)
./scripts/run_tests.sh coverage

# Run specific test categories
./scripts/run_tests.sh unit
./scripts/run_tests.sh integration
./scripts/run_tests.sh marker openai_api

# Advanced test commands
./scripts/run_tests.sh quick      # Skip slow tests
./scripts/run_tests.sh slow       # Run slow tests only
./scripts/run_tests.sh parallel   # Run tests in parallel (requires pytest-xdist)
./scripts/run_tests.sh file <path>  # Run specific test file
./scripts/run_tests.sh marker <name>  # Run tests with specific marker
./scripts/run_tests.sh stats      # Show test statistics
./scripts/run_tests.sh clean      # Clean test artifacts

# Run single test file
uv run pytest tests/unit/test_openai_service.py -v

# Run specific test
uv run pytest tests/unit/test_openai_service.py::TestOpenAIService::test_web_search_rate_limiting -v

# Alternative commands via Makefile
make test      # Run all tests
make coverage  # Run tests with coverage
make lint      # Run linting checks
make clean     # Clean test artifacts
```

### Dependency Management
```bash
# Install dependencies using uv (recommended)
uv sync

# Add new dependencies
uv add package_name

# Check dependency lock file
cat uv.lock
```

### Environment Setup
- Required environment variables must be set in Replit Secrets or `.env` file:
  - `LINE_CHANNEL_ACCESS_TOKEN`: LINE Bot API access token
  - `LINE_CHANNEL_SECRET`: LINE webhook signature verification key
  - `LINE_CHANNEL_ID`: LINE Bot channel ID for Rich Message delivery
  - `AZURE_OPENAI_API_KEY`: Azure OpenAI service authentication key
  - `AZURE_OPENAI_ENDPOINT`: Azure cognitive services endpoint URL
  - `AZURE_OPENAI_DEPLOYMENT_NAME`: Model deployment identifier (e.g., gpt-4.1-nano)
  - `SESSION_SECRET`: Flask session secret (auto-generated in development)
- Optional environment variables:
  - `DEBUG`: Enable debug mode (default: False)
  - `LOG_LEVEL`: Logging verbosity (default: INFO)
  - `MAX_MESSAGES_PER_USER`: Conversation history limit (default: 100)
  - `MAX_TOTAL_CONVERSATIONS`: Total conversation limit (default: 1000)
  - `CELERY_BROKER_URL`: Redis URL for Celery task queue (default: redis://localhost:6379/0)
  - `CELERY_RESULT_BACKEND`: Redis URL for Celery results (default: redis://localhost:6379/0)
  - `REDIS_URL`: Redis connection URL for conversation storage (default: redis://localhost:6379/0)
  - `APP_ENV`: Application environment (development/staging/production)
  - `RATE_LIMIT_PER_MINUTE`: API rate limit per minute (default: 200)
  - `RATE_LIMIT_PER_HOUR`: API rate limit per hour (default: 1000)

## Architecture Overview

This is a Flask-based LINE Bot application with two major capabilities: conversational AI and automated Rich Message delivery. The architecture follows a service-oriented pattern with clear separation of concerns and background task processing.

### Core Services Layer
- **LineService** (`src/services/line_service.py`): Advanced LINE Bot SDK integration with optimized connection pooling, webhook verification, enhanced file processing (20+ formats), postback handling with JSON/legacy format support, and connection health monitoring
- **OpenAIService** (`src/services/openai_service.py`): Hybrid Azure OpenAI integration with dual API support (Responses API + Chat Completions), advanced connection pooling, circuit breaker pattern, response caching, file upload support, and health monitoring
- **ConversationService** (`src/services/conversation_service.py`): Unified conversation management with hybrid storage (Redis/in-memory), thread-safe operations, memory monitoring with cleanup callbacks, response ID tracking for API continuity, and circuit breaker for Redis health
- **ConversationFactory** (`src/services/conversation_factory.py`): Factory pattern implementation with automatic fallback logic and health check validation
- **RedisConversationService** (`src/services/redis_conversation_service.py`): Redis-based persistent storage with connection pooling, TTL management, and structured metadata storage
- **RichMessageService** (`src/services/rich_message_service.py`): Advanced Rich Message system with 4-tier content generation fallback, smart template selection, multi-level caching (LRU→Redis→memory), rate limiting, interactive conversation triggers, and mood-based template matching
- **ImageProcessor** (`src/utils/image_utils.py`): Handles image download from LINE content API, format validation, base64 conversion for GPT-4 vision API, and automatic cleanup
- **FileProcessor** (`src/utils/file_utils.py`): Handles general file download, type detection, validation, and processing with support for 20+ file formats including documents, spreadsheets, code files, and data formats
- **ConnectionPoolManager** (`src/utils/connection_pool.py`): Advanced HTTP connection pooling for all external APIs with health monitoring and retry logic

### Rich Message Automation System
- **ContentGenerator** (`src/utils/content_generator.py`): AI-powered content generation with Bourdain persona for daily motivational messages
- **TemplateManager** (`src/utils/template_manager.py`): Manages template library with 50+ categorized backgrounds (motivation, wellness, productivity, inspiration)
- **ImageComposer** (`src/utils/image_composer.py`): Dynamically composes text overlays on template backgrounds using PIL
- **TemplateSelector** (`src/utils/template_selector.py`): Context-aware template selection with mood scoring, time-based matching, and weighted algorithms
- **Celery Automation** (`src/tasks/rich_message_automation.py`): Advanced task scheduling with timezone support, batch processing, and health monitoring
- **Analytics & Tracking** (`src/utils/analytics_tracker.py`, `src/utils/delivery_tracker.py`): Comprehensive delivery analytics and error tracking
- **AsyncPipeline** (`src/utils/async_rich_message_pipeline.py`): Asynchronous processing pipeline with priority queues and concurrent task execution
- **ContentEnhancer** (`src/utils/content_enhancer.py`): Content quality optimization and validation
- **PromptManager** (`src/utils/prompt_manager.py`): AI prompt template management system

### Application Structure
- **Entry Points**: `app.py` (main Flask application with full initialization) and `main.py` (alternative entry point for Replit)
- **Configuration**: 
  - `src/config/settings.py`: Legacy configuration loader
  - `src/config/centralized_config.py`: Modern Pydantic-based configuration with hot-reload
  - `src/config/rich_message_config.py`: Rich Message specific configuration
  - `src/config/config_schema.json`: JSON Schema validation
  - `src/config/content_prompts.json`: AI content generation prompts
- **Admin Interface**: `src/routes/admin_routes.py` provides comprehensive Rich Message management dashboard with campaign management, analytics, and system health monitoring
- **Background Processing**: Celery + Redis for automated task processing including Rich Message generation, image processing, and webhook handling
- **Web Interface**: Templates and static files for dashboard monitoring and Rich Message asset serving
- **Database Models**: `src/models/analytics_models.py` provides complete PostgreSQL schema for analytics and tracking

### Data Flow Patterns

#### Conversational AI Flow
1. LINE webhook → LineService (signature verification)
2. Message type detection (text/image) → Appropriate processing path
3. For images: ImageProcessor downloads → converts to base64 → GPT-4 vision API
4. For text: Direct processing → ConversationService (context management)
5. AI response generation → OpenAIService (Azure OpenAI integration with optional web search)
6. Response delivery → LINE Bot API

#### Rich Message Automation Flow
1. Celery scheduler triggers daily automation task
2. ContentGenerator creates AI-powered motivational content
3. TemplateSelector chooses appropriate background based on content mood and time
4. ImageComposer overlays text on selected template background
5. RichMessageService formats as LINE Flex Message with interactive elements
6. Delivery to configured user groups via LINE Bot API
7. Analytics tracking for delivery success/failure and user interactions

### Key Design Decisions
- **Hybrid storage architecture**: Seamless fallback between Redis and in-memory storage with circuit breaker patterns
- **Advanced connection management**: Comprehensive connection pooling with health monitoring across all services
- **Conversation limits**: 100 messages per user, 1000 total conversations with memory-aware cleanup strategies
- **Background processing**: Celery + Redis for automated task processing with timezone support and batch operations
- **Template-driven design**: 50+ categorized background templates with context-aware selection algorithms
- **Multi-tier content generation**: 4-level fallback system (AI → Constrained AI → Premium fallback → Emergency)
- **Comprehensive caching strategy**: LRU → Redis → in-memory hierarchy with intelligent eviction
- **AI content generation**: Azure OpenAI with Bourdain persona generates personalized motivational content
- **Dual API support**: Automatic fallback between OpenAI Responses API and Chat Completions
- **Streaming responses**: GPT-4.1-nano integration supports streaming for better user experience
- **Multilingual support**: Comprehensive language handling for English, Thai, Chinese, Japanese, Korean, Vietnamese, Spanish, French, and German with cultural sensitivity and automatic language detection and matching
- **Web search integration**: OpenAI's built-in web search tool for real-time information (news, weather, stocks)
- **Advanced rate limiting**: Sophisticated rate limiting with cooldown periods, daily limits, and per-endpoint controls
- **Search caching**: 15-minute cache for search results to improve performance
- **Multimodal capabilities**: Native image understanding using GPT-4.1-nano's vision features
- **Context-aware processing**: Images and content processed with full conversation context
- **Interactive conversation system**: AI-powered conversation triggers from Rich Message interactions
- **Production database**: Full PostgreSQL implementation with analytics and metrics tracking

## Service Dependencies

### External APIs
- **LINE Messaging API**: Requires official LINE Bot account and channel setup
- **Azure OpenAI**: Configured for GPT-4.1-nano deployment with specific endpoint settings

### Python Dependencies
Key packages defined in `pyproject.toml`:
- `flask` + `gunicorn`: Web framework and WSGI server
- `line-bot-sdk`: Official LINE Bot SDK for Python
- `openai`: Azure OpenAI Python client  
- `python-dotenv`: Environment variable management
- `pillow`: Image processing for vision capabilities and Rich Message composition
- `requests` + `urllib3`: HTTP clients with connection pooling
- `pytest` + extensions: Comprehensive testing framework with coverage, async support, and mocking
- `flask-sqlalchemy` + `psycopg2-binary`: Database ORM and PostgreSQL adapter with full implementation
- `celery` + `redis`: Background task processing for Rich Message automation
- `flask-limiter`: Rate limiting for API endpoints
- `flask-caching`: Response caching for improved performance
- `aiohttp` + `aiofiles`: Async HTTP and file operations
- `pydantic`: Modern configuration management with validation
- `jsonschema`: Configuration schema validation
- `python-multipart`: File upload handling
- `chardet`: Character encoding detection for file processing
- `pypdf`: PDF file processing support

## Current Features

### Rich Message Automation System
- **AI-Generated Content**: Daily motivational messages with Bourdain persona using 4-tier fallback system
- **Template Library**: 50+ categorized background templates (motivation, wellness, productivity, inspiration)
- **Dynamic Composition**: Real-time text overlay on template backgrounds using PIL with smart positioning
- **Context-Aware Selection**: Advanced template selection with mood scoring, time-based matching, and weighted algorithms
- **Scheduled Delivery**: Celery-based automation with timezone support and batch processing
- **Interactive Elements**: Rich Messages with conversation triggers and AI-powered response generation
- **Analytics Dashboard**: Full PostgreSQL-backed analytics with delivery tracking, engagement metrics, and system health
- **Multi-category Support**: Motivation, wellness, productivity, and inspiration themes with subcategories
- **Template Management**: Hot-swappable templates with JSON metadata and validation
- **Performance Optimization**: Async processing pipeline with priority queues and concurrent execution
- **Caching Strategy**: Multi-tier caching (LRU → Redis → memory) for optimal performance
- **Rate Limiting**: Sophisticated controls with daily limits and cooldown periods

### Multilingual Support
- **Comprehensive Language Coverage**: Supports 9 major languages with native-speaker-level responses
- **Cultural Sensitivity**: Adapts communication style to match cultural norms and formality levels
- **Language Detection**: Automatically detects user's language and responds accordingly
- **Regional Variations**: Handles Traditional/Simplified Chinese and regional communication patterns
- **Hierarchical Communication**: Respects formal/informal distinctions in East Asian languages

### Web Search Integration
- **Intelligent Search**: Bot automatically determines when web search is needed for current information
- **Real-time Data**: Supports queries about news, weather, stock prices, and recent events
- **Rate Limiting**: 10 searches per user per hour to prevent API abuse
- **Caching**: 15-minute cache for search results to improve response times
- **Language Matching**: Responses automatically match the user's input language across 9 supported languages with cultural context awareness

### Image Understanding Capabilities
- **Vision API Integration**: GPT-4.1-nano processes images with accompanying text
- **Format Support**: JPEG, PNG, GIF, WEBP formats with automatic validation
- **Size Optimization**: Images resized and compressed for optimal API performance
- **Context Awareness**: Images processed with conversation history for better understanding
- **Automatic Cleanup**: Temporary files cleaned up after processing

### Enhanced Conversation Memory
- **Extended History**: 100 messages per conversation for better context retention
- **Hybrid Storage**: Seamless fallback between Redis and in-memory with health monitoring
- **Thread-Safe Operations**: Re-entrant locks for concurrent access protection
- **Memory Monitoring**: Integration with cleanup callbacks for different severity levels
- **Response ID Tracking**: Maintains continuity for OpenAI Responses API
- **Message Type Tracking**: Tracks text, image, file, and mixed message types
- **Automatic Cleanup**: Memory-aware cleanup with light, aggressive, and emergency strategies
- **Circuit Breaker**: Automatic Redis health detection with TTL-based caching

### Usage Examples
#### Conversational AI
- "What's the latest news about Thailand?" → Gets current news with sources
- "What's Tesla's stock price today?" → Provides real-time market data
- "What's the weather in Bangkok?" → Returns current weather conditions
- Send image + "What do you see?" → Detailed image analysis with context
- Language switching: Works seamlessly across all 9 supported languages (English, Thai, Chinese, Japanese, Korean, Vietnamese, Spanish, French, German) with appropriate cultural context

#### Rich Message Automation
- Daily 9 AM motivational messages with AI-generated content
- Template backgrounds automatically selected based on content mood
- Interactive buttons for user engagement tracking
- Admin dashboard for monitoring delivery analytics and managing templates

## Testing Infrastructure

The codebase includes comprehensive testing with `pytest`:

### Test Structure  
- **Comprehensive Test Suite**: 60+ test files across multiple categories
- **Unit Tests**: 32 files testing individual components in isolation
- **Integration Tests**: 7 files testing component interactions and workflows
- **Performance Tests**: Load testing and benchmarking capabilities
- **Error Scenarios**: Dedicated error handling and resilience testing
- **Coverage Requirements**: Minimum 80% coverage enforced
- **Test Markers**: `unit`, `integration`, `slow`, `mock`, `line_api`, `openai_api`, `performance`, `error_scenario`, `asyncio`
- **Test Organization**: 
  - `tests/unit/`: Core component tests
  - `tests/integration/`: End-to-end workflows
  - `tests/performance/`: Load and performance testing
  - `tests/validation/`: PRD compliance validation
  - `tests/error_scenarios/`: Error handling tests
  - `tests/fixtures/`: Shared test data and fixtures

### Test Execution
- **Comprehensive Test Runner**: `scripts/run_tests.sh` with multiple execution modes
- **Coverage Reporting**: HTML and terminal coverage reports
- **Mock-Heavy Approach**: No real API calls during testing
- **Detailed Documentation**: See `README_TESTING.md` for complete testing guide

## Development Notes

### Current Limitations
- **Web search**: Limited to OpenAI's built-in tool (no external search APIs)
- **Image processing**: Limited to 5MB files and 2048px dimensions for conversation images
- **Rich Message templates**: Fixed template library (50+ templates), no dynamic template generation
- **Celery dependency**: Rich Message automation requires Redis for background task processing
- **Database migrations**: PostgreSQL schema implemented but migration system not yet in place
- **Real-time updates**: No WebSocket support for live updates
- **Template editor**: No GUI for creating new Rich Message templates

### Monitoring Endpoints

#### Main Application Endpoints
- `/`: Dashboard with user statistics and service status
- `/health`: Health check endpoint with detailed service status
- `/conversations`: Conversation statistics for monitoring
- `/memory`: Memory usage statistics and alerts
- `/connection-pools`: Connection pool health metrics
- `/webhook`: LINE Bot webhook endpoint (POST) and verification (GET)
- `/static/backgrounds/<filename>`: Serves Rich Message template backgrounds

#### Admin Interface Endpoints
- `/admin/`: Main admin dashboard
- `/admin/campaigns`: Campaign management interface
- `/admin/campaigns/create`: Create new Rich Message campaigns
- `/admin/campaigns/<id>`: Individual campaign details
- `/admin/analytics`: Analytics dashboard with engagement metrics
- `/admin/system/health`: System health monitoring

#### Admin API Endpoints
- `/admin/api/campaigns`: Campaign CRUD operations
- `/admin/api/analytics/dashboard`: Analytics data API
- `/admin/api/system/health`: System health API
- `/admin/api/system/cleanup`: Data cleanup operations

### Logging Configuration
- Structured logging with configurable levels via `LOG_LEVEL` environment variable
- User privacy protection (truncated user IDs in logs)
- Webhook event tracking for debugging
- Image processing logging with metadata

## Security Considerations
- LINE webhook signature verification implemented in LineService
- Environment variable validation prevents missing credentials
- No sensitive data logged or exposed in dashboard
- Image download timeout protection (10 seconds)
- Temporary file cleanup prevents disk space issues

## Deployment Configuration

### Replit Deployment
- **Platform**: Replit with autoscale deployment enabled
- **Runtime**: Python 3.11 + Node.js 20 modules
- **System packages**: OpenSSL, PostgreSQL
- **Port mapping**: Internal port 5000 → External port 80
- **Entry points**: `app.py` (default) or `main.py` (Replit deployment)
- **Configuration**: `.replit` file with workflow definitions

### Docker Deployment
- **Dockerfile**: Basic container with Python 3.12 slim and Gunicorn
- **Docker Compose**: Full production stack in `deployment/docker-compose.yml`
  - Application container with health checks
  - Redis for caching and Celery backend
  - PostgreSQL for analytics persistence
  - Nginx reverse proxy with SSL termination
  - Monitoring stack: Prometheus, Grafana, Fluentd
  - Volume management and network isolation

### Production Configuration
- **Database**: PostgreSQL schema in `deployment/scripts/init-db.sql`
- **Environment**: Multiple environment support (development/staging/production)
- **Monitoring**: Comprehensive monitoring with Prometheus metrics
- **Logging**: Centralized logging with Fluentd
- **Security**: SSL/TLS termination, security headers, rate limiting

## Task Management and Development Workflow

### Task List Protocol
When working on tasks tracked in markdown files:
1. **Work one sub-task at a time** - Do not start the next sub-task until user approval
2. **Completion sequence**:
   - Mark sub-task as completed `[x]` when finished
   - When all subtasks under a parent are complete: run tests → stage changes → clean up → commit → mark parent complete
   - Use conventional commit format with `-m` flags for multiline messages
3. **Always update task lists** and maintain "Relevant Files" sections
4. **Stop after each sub-task** and wait for user go-ahead

### Development Best Practices
- Always run tests before committing: `./scripts/run_tests.sh all`
- Maintain test coverage above 80%
- Use conventional commit format for clear history
- Update CLAUDE.md when adding new features or changing architecture
- Document new environment variables and configuration options

## Advanced Features and Architecture

### Connection Pool Management
- **Optimized LINE Bot API**: Custom connection pooling with HTTP/2 support
- **OpenAI Connection Pooling**: Advanced pooling for both Responses API and Chat Completions
- **Health Monitoring**: Connection health checks with automatic recovery
- **Performance Metrics**: Real-time connection pool statistics at `/connection-pools`

### Caching Architecture
- **Multi-tier Caching**: LRU → Redis → In-memory hierarchy
- **Cache Types**: Response caching, content caching, template caching
- **TTL Management**: Intelligent TTL based on content type
- **Cache Warming**: Preload frequently used data

### Memory Management
- **Memory Monitoring**: Real-time memory usage tracking with alerts
- **Cleanup Strategies**: Light (70%), Aggressive (85%), Emergency (95%) thresholds
- **Memory-aware Operations**: Automatic conversation cleanup based on memory pressure
- **Statistics Endpoint**: Detailed memory statistics at `/memory`

### Error Handling and Resilience
- **Circuit Breaker Pattern**: Automatic API failure detection and recovery
- **Retry Logic**: Exponential backoff with jitter for all external APIs
- **Fallback Mechanisms**: Multiple fallback levels for critical operations
- **Correlation IDs**: Request tracking across all services

### File Processing Capabilities
- **Supported Formats**: 20+ file types including documents, spreadsheets, code, and data files
- **Async Processing**: Non-blocking file operations with progress tracking
- **Content Extraction**: Intelligent content extraction based on file type
- **Security Validation**: File type validation and malware scanning

### Background Task Processing
- **Task Types**: Rich Message generation, image processing, webhook handling, cleanup tasks
- **Priority Queues**: Task prioritization based on importance
- **Batch Processing**: Efficient batch operations for bulk tasks
- **Task Monitoring**: Real-time task status and performance metrics

### Database Architecture
- **Analytics Schema**: Comprehensive PostgreSQL schema for metrics and tracking
- **Indexing Strategy**: Optimized indexes for query performance
- **Data Aggregation**: Pre-aggregated analytics for dashboard performance
- **Retention Policies**: Automatic data cleanup based on age

### Performance Optimizations
- **Async Operations**: Extensive use of asyncio for I/O operations
- **Connection Reuse**: HTTP connection pooling across all services
- **Response Streaming**: Stream large responses to reduce memory usage
- **Lazy Loading**: Load resources only when needed

### Security Features
- **Webhook Verification**: LINE signature validation for all webhooks
- **Rate Limiting**: Multiple rate limit strategies (per-user, per-IP, per-endpoint)
- **Input Validation**: Comprehensive validation for all user inputs
- **Secret Management**: Secure handling of API keys and secrets

### Configuration Management
- **Hot Reload**: Configuration changes without restart
- **Schema Validation**: JSON Schema validation for all configurations
- **Environment Adapters**: Seamless switching between environments
- **Version Control**: Configuration versioning and rollback support