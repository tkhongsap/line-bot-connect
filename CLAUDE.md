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

# Run single test file
uv run pytest tests/unit/test_openai_service.py -v

# Run specific test
uv run pytest tests/unit/test_openai_service.py::TestOpenAIService::test_web_search_rate_limiting -v
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
  - `AZURE_OPENAI_API_KEY`: Azure OpenAI service authentication key
  - `AZURE_OPENAI_ENDPOINT`: Azure cognitive services endpoint URL
  - `AZURE_OPENAI_DEPLOYMENT_NAME`: Model deployment identifier (e.g., gpt-4.1-mini)
- Optional environment variables:
  - `DEBUG`: Enable debug mode (default: False)
  - `LOG_LEVEL`: Logging verbosity (default: INFO)
  - `MAX_MESSAGES_PER_USER`: Conversation history limit (default: 100)
  - `MAX_TOTAL_CONVERSATIONS`: Total conversation limit (default: 1000)

## Architecture Overview

This is a Flask-based LINE Bot application that integrates Azure OpenAI for conversational AI capabilities. The architecture follows a service-oriented pattern with clear separation of concerns:

### Core Services Layer
- **LineService** (`src/services/line_service.py`): Handles LINE Bot SDK integration, webhook verification, message processing, and supports both text and image messages
- **OpenAIService** (`src/services/openai_service.py`): Manages Azure OpenAI API communication with GPT-4.1-mini model, conversation context, web search capabilities, and multimodal (text + vision) processing
- **ConversationService** (`src/services/conversation_service.py`): Maintains in-memory conversation history per user with automatic trimming (supports up to 100 messages per user)
- **ImageProcessor** (`src/utils/image_utils.py`): Handles image download from LINE content API, format validation, base64 conversion for GPT-4 vision API, and automatic cleanup

### Application Structure
- **Entry Points**: `app.py` (main Flask application) and `main.py` (alternative entry point)
- **Configuration**: `src/config/settings.py` handles environment variables and validation
- **Utilities**: `src/utils/logger.py` for centralized logging
- **Web Interface**: Templates and static files for dashboard monitoring

### Multimodal Data Flow Pattern
1. LINE webhook → LineService (signature verification)
2. Message type detection (text/image) → Appropriate processing path
3. For images: ImageProcessor downloads → converts to base64 → GPT-4 vision API
4. For text: Direct processing → ConversationService (context management)
5. AI response generation → OpenAIService (Azure OpenAI integration with optional web search)
6. Response delivery → LINE Bot API

### Key Design Decisions
- **In-memory storage**: Conversation history stored in memory for MVP demo purposes (not production-ready for scaling)
- **Conversation limits**: 100 messages per user, 1000 total conversations to prevent memory overflow
- **Streaming responses**: GPT-4.1-mini integration supports streaming for better user experience
- **Multilingual support**: Comprehensive language handling for English, Thai, Chinese, Japanese, Korean, Vietnamese, Spanish, French, and German with cultural sensitivity and automatic language detection and matching
- **Web search integration**: OpenAI's built-in web search tool for real-time information (news, weather, stocks)
- **Rate limiting**: 10 web searches per user per hour to prevent abuse
- **Search caching**: 15-minute cache for search results to improve performance
- **Multimodal capabilities**: Native image understanding using GPT-4.1-mini's vision features
- **Context-aware image processing**: Images processed with conversation context for better understanding

## Service Dependencies

### External APIs
- **LINE Messaging API**: Requires official LINE Bot account and channel setup
- **Azure OpenAI**: Configured for GPT-4.1-mini deployment with specific endpoint settings

### Python Dependencies
Key packages defined in `pyproject.toml`:
- `flask` + `gunicorn`: Web framework and WSGI server
- `line-bot-sdk`: Official LINE Bot SDK for Python
- `openai`: Azure OpenAI Python client
- `python-dotenv`: Environment variable management
- `pillow`: Image processing for vision capabilities
- `requests`: HTTP client for image downloads
- `pytest`: Testing framework with coverage reporting
- `flask-sqlalchemy` + `psycopg2-binary`: Database ORM and PostgreSQL adapter (installed but not yet implemented)

## Current Features

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
- **Vision API Integration**: GPT-4.1-mini processes images with accompanying text
- **Format Support**: JPEG, PNG, GIF, WEBP formats with automatic validation
- **Size Optimization**: Images resized and compressed for optimal API performance
- **Context Awareness**: Images processed with conversation history for better understanding
- **Automatic Cleanup**: Temporary files cleaned up after processing

### Enhanced Conversation Memory
- **Extended History**: 100 messages per conversation for better context retention
- **Message Type Tracking**: Tracks text, image, and mixed message types
- **Automatic Cleanup**: Old conversations removed when limits are reached

### Usage Examples
- "What's the latest news about Thailand?" → Gets current news with sources
- "What's Tesla's stock price today?" → Provides real-time market data
- "What's the weather in Bangkok?" → Returns current weather conditions
- Send image + "What do you see?" → Detailed image analysis with context
- Language switching: Works seamlessly across all 9 supported languages (English, Thai, Chinese, Japanese, Korean, Vietnamese, Spanish, French, German) with appropriate cultural context

## Testing Infrastructure

The codebase includes comprehensive testing with `pytest`:

### Test Structure
- **Unit Tests**: Individual components tested in isolation with mocks
- **Integration Tests**: Component interactions and HTTP endpoints
- **Coverage Requirements**: Minimum 80% coverage enforced
- **Test Markers**: `unit`, `integration`, `slow`, `mock`, `line_api`, `openai_api`

### Test Execution
- **Comprehensive Test Runner**: `scripts/run_tests.sh` with multiple execution modes
- **Coverage Reporting**: HTML and terminal coverage reports
- **Mock-Heavy Approach**: No real API calls during testing
- **Detailed Documentation**: See `README_TESTING.md` for complete testing guide

## Development Notes

### Current Limitations
- Conversation storage is in-memory only (lost on restart)
- Single-instance deployment required for session continuity
- No database persistence layer implemented
- Web search limited to OpenAI's built-in tool (no external search APIs)
- Image processing limited to 5MB files and 2048px dimensions

### Monitoring Endpoints
- `/`: Dashboard with user statistics and service status
- `/health`: Health check endpoint returning service status
- `/conversations`: Conversation statistics for monitoring
- `/webhook`: LINE Bot webhook endpoint (POST) and verification (GET)

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

## Deployment Configuration (Replit)
- **Platform**: Replit with autoscale deployment enabled
- **Runtime**: Python 3.11 + Node.js 20 modules
- **System packages**: OpenSSL, PostgreSQL
- **Port mapping**: Internal port 5000 → External port 80
- **Entry points**: `app.py` (default) or `main.py` (Replit deployment)

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