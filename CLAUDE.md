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
- **LineService** (`src/services/line_service.py`): Handles LINE Bot SDK integration, webhook verification, and message processing
- **OpenAIService** (`src/services/openai_service.py`): Manages Azure OpenAI API communication with GPT-4.1 model, conversation context, and web search capabilities
- **ConversationService** (`src/services/conversation_service.py`): Maintains in-memory conversation history per user with automatic trimming (supports up to 100 messages per user)

### Application Structure
- **Entry Points**: `app.py` (main Flask application) and `main.py` (alternative entry point)
- **Configuration**: `src/config/settings.py` handles environment variables and validation
- **Utilities**: `src/utils/logger.py` for centralized logging
- **Web Interface**: Templates and static files for dashboard monitoring

### Data Flow Pattern
1. LINE webhook → LineService (signature verification)
2. Message processing → ConversationService (context management)  
3. AI response generation → OpenAIService (Azure OpenAI integration)
4. Response delivery → LINE Bot API

### Key Design Decisions
- **In-memory storage**: Conversation history stored in memory for MVP demo purposes (not production-ready for scaling)
- **Conversation limits**: 100 messages per user, 1000 total conversations to prevent memory overflow
- **Streaming responses**: GPT-4.1 integration supports streaming for better user experience
- **Bilingual support**: Built-in English/Thai language handling with automatic language detection and matching
- **Web search integration**: OpenAI's built-in web search tool for real-time information (news, weather, stocks)
- **Rate limiting**: 10 web searches per user per hour to prevent abuse
- **Search caching**: 15-minute cache for search results to improve performance

## Service Dependencies

### External APIs
- **LINE Messaging API**: Requires official LINE Bot account and channel setup
- **Azure OpenAI**: Configured for GPT-4.1 deployment with specific endpoint settings

### Python Dependencies
Key packages defined in `pyproject.toml`:
- `flask` + `gunicorn`: Web framework and WSGI server
- `line-bot-sdk`: Official LINE Bot SDK for Python
- `openai`: Azure OpenAI Python client
- `python-dotenv`: Environment variable management
- `flask-sqlalchemy` + `psycopg2-binary`: Database ORM and PostgreSQL adapter (installed but not yet implemented)
- `email-validator`: Email validation utilities
- `werkzeug`: WSGI utilities for Flask

## New Features (Latest Update)

### Web Search Integration
- **Intelligent Search**: Bot automatically determines when web search is needed for current information
- **Real-time Data**: Supports queries about news, weather, stock prices, and recent events
- **Rate Limiting**: 10 searches per user per hour to prevent API abuse
- **Caching**: 15-minute cache for search results to improve response times
- **Language Matching**: Responses automatically match the user's input language (English/Thai)

### Enhanced Conversation Memory
- **Extended History**: Increased from 20 to 100 messages per conversation
- **Better Context**: Maintains longer conversation threads for more meaningful interactions
- **Automatic Cleanup**: Old conversations removed when limits are reached

### Usage Examples
- "What's the latest news about Thailand?" → Gets current news with sources
- "What's Tesla's stock price today?" → Provides real-time market data
- "What's the weather in Bangkok?" → Returns current weather conditions
- Language switching: Works seamlessly in both English and Thai

## Development Notes

### Current Limitations
- Conversation storage is in-memory only (lost on restart)
- Single-instance deployment required for session continuity
- No database persistence layer implemented
- Web search limited to OpenAI's built-in tool (no external search APIs)

### Monitoring Endpoints
- `/`: Dashboard with user statistics and service status
- `/health`: Health check endpoint returning service status
- `/conversations`: Conversation statistics for monitoring
- `/webhook`: LINE Bot webhook endpoint (POST) and verification (GET)

### Logging Configuration
- Structured logging with configurable levels via `LOG_LEVEL` environment variable
- User privacy protection (truncated user IDs in logs)
- Webhook event tracking for debugging

## Security Considerations
- LINE webhook signature verification implemented in LineService
- Environment variable validation prevents missing credentials
- No sensitive data logged or exposed in dashboard

## Deployment Configuration (Replit)
- **Platform**: Replit with autoscale deployment enabled
- **Runtime**: Python 3.11 + Node.js 20 modules
- **System packages**: OpenSSL, PostgreSQL
- **Port mapping**: Internal port 5000 → External port 80
- **Entry points**: `app.py` (default) or `main.py` (Replit deployment)

## Testing and Code Quality
**Note**: No testing framework or linting configuration is currently implemented. Consider adding:
- Testing framework (pytest) for unit and integration tests
- Linting tools (flake8, black, pylint) for code quality
- Pre-commit hooks for automated checks

## Task Management and Development Workflow

### Task List Protocol (from ai-docs/process-tasks.md)
When working on tasks tracked in markdown files:
1. **Work one sub-task at a time** - Do not start the next sub-task until user approval
2. **Completion sequence**:
   - Mark sub-task as completed `[x]` when finished
   - When all subtasks under a parent are complete: run tests → stage changes → clean up → commit → mark parent complete
   - Use conventional commit format with `-m` flags for multiline messages
3. **Always update task lists** and maintain "Relevant Files" sections
4. **Stop after each sub-task** and wait for user go-ahead

### Image and Document Processing
The codebase includes AI documentation for handling images and documents:
- Task breakdown and PRD files in `ai-docs/` directory
- Feature branch `feature/image-text-handling` for image understanding capabilities
- Attached assets in `attached_assets/` for screenshots and images