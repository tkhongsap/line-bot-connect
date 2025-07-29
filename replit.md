# LINE Bot with Azure OpenAI Integration

## Project Overview
A sophisticated LINE webhook service leveraging Azure OpenAI for intelligent, multilingual chatbot interactions. Provides advanced conversational AI capabilities with seamless web search, image understanding, and dynamic language support.

**Current Status**: ✅ Active and Running
- **Platform**: Replit (Python 3.11)
- **Port**: 5000 (Flask + Gunicorn)
- **Main Technologies**: Azure OpenAI (GPT-4.1-mini), Flask, LINE Bot SDK

## Recent Changes
- **2025-07-29**: Fixed critical HTTP/2 dependency issue by installing h2 package
  - App was failing to start due to missing h2 package for httpx HTTP/2 support
  - Installed h2 and httpx[http2] packages to resolve OpenAI service initialization
  - Application now starts successfully with all services active
- **Current State**: All core services (OpenAI, LINE, Conversation) are operational
- **Redis Status**: Using in-memory fallback (Redis not available in current environment)

## Project Architecture

### Core Services
- **OpenAI Service** (`src/services/openai_service.py`): Azure OpenAI integration with HTTP/2 connection pooling
- **LINE Service** (`src/services/line_service.py`): LINE Bot API integration with webhook handling
- **Conversation Service** (`src/services/conversation_service.py`): Message context management
- **Rich Message Service** (`src/services/rich_message_service.py`): Automated rich content delivery

### Key Features
1. **Conversational AI Flow**: LINE webhook → message processing → Azure OpenAI → response delivery
2. **Rich Message Automation**: Scheduled AI-generated motivational content with dynamic templates
3. **Multilingual Support**: 9 languages (English, Thai, Chinese, Japanese, Korean, Vietnamese, Spanish, French, German)
4. **Image Understanding**: GPT-4 vision API for image analysis
5. **Web Search Integration**: Real-time information retrieval
6. **Connection Pooling**: Optimized HTTP connections for all external APIs

### Entry Points
- **Main App**: `app.py` (Flask application with all service initialization)
- **Deployment**: `main.py` (Replit deployment entry point)
- **Configuration**: `src/config/settings.py` (environment variable management)

## Environment Setup
Required environment variables (set in Replit Secrets):
- `LINE_CHANNEL_ACCESS_TOKEN`: LINE Bot API access token
- `LINE_CHANNEL_SECRET`: LINE webhook signature verification key
- `AZURE_OPENAI_API_KEY`: Azure OpenAI service authentication key
- `AZURE_OPENAI_ENDPOINT`: Azure cognitive services endpoint URL
- `AZURE_OPENAI_DEPLOYMENT_NAME`: Model deployment identifier
- `SESSION_SECRET`: Flask session secret (auto-generated in development)

## Current Issues & Notes
- **Redis Unavailable**: App gracefully falls back to in-memory storage for conversations
- **LSP Diagnostics**: 108 type-related warnings in OpenAI service (non-critical, app functions normally)
- **Health Status**: All services report healthy via `/health` endpoint

## User Preferences
- Language: English
- Focus: Debugging and maintaining production-ready code
- Approach: Comprehensive problem-solving with detailed explanations

## Testing Infrastructure
- **Framework**: pytest with comprehensive coverage
- **Test Types**: Unit, integration, and performance tests
- **Coverage Target**: 80% minimum
- **Mock Strategy**: Heavy use of mocks to avoid real API calls during testing