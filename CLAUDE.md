# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common Development Commands

### Running the Application
```bash
# Development mode
python app.py

# Production mode with gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
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

## Architecture Overview

This is a Flask-based LINE Bot application that integrates Azure OpenAI for conversational AI capabilities. The architecture follows a service-oriented pattern with clear separation of concerns:

### Core Services Layer
- **LineService** (`src/services/line_service.py`): Handles LINE Bot SDK integration, webhook verification, and message processing
- **OpenAIService** (`src/services/openai_service.py`): Manages Azure OpenAI API communication with GPT-4.1 model and conversation context
- **ConversationService** (`src/services/conversation_service.py`): Maintains in-memory conversation history per user with automatic trimming

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
- **Bilingual support**: Built-in English/Thai language handling

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

## Development Notes

### Current Limitations
- Conversation storage is in-memory only (lost on restart)
- Single-instance deployment required for session continuity
- No database persistence layer implemented

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