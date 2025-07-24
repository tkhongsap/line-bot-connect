# Overview

This is a LINE Bot MVP application that provides conversational AI capabilities through Azure OpenAI integration. The bot maintains conversation context per user and serves as a demonstration platform for AI-powered messaging services. The application is built with Flask and designed for Azure Web App deployment.

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Backend Architecture
- **Web Framework**: Flask application with webhook endpoint for LINE messaging
- **Service Layer**: Modular service architecture with separate concerns for LINE integration, OpenAI communication, and conversation management
- **Configuration**: Environment-based configuration management with validation
- **Logging**: Centralized logging system for monitoring and debugging

## Frontend Architecture
- **Dashboard**: Simple HTML dashboard with Bootstrap styling for monitoring bot status
- **Static Assets**: CSS styling with dark theme support and responsive design
- **Real-time Updates**: Basic status display showing user count and service health

# Key Components

## Core Services
1. **LineService** (`src/services/line_service.py`)
   - Handles LINE Bot SDK integration
   - Manages webhook signature verification
   - Processes incoming messages and sends responses
   - Uses LINE Bot SDK Python for API communication

2. **OpenAIService** (`src/services/openai_service.py`)
   - Integrates with Azure OpenAI using the official Python SDK
   - Maintains conversation context using system prompts
   - Supports bilingual communication (English/Thai)
   - Implements response length optimization for LINE messaging

3. **ConversationService** (`src/services/conversation_service.py`)
   - Manages in-memory conversation history per user
   - Implements conversation limits (100 messages per user, 1000 total conversations)
   - Provides conversation context for AI responses
   - Handles automatic conversation trimming

## Configuration Management
- **Settings** (`src/config/settings.py`)
  - Environment variable management with validation
  - Support for LINE credentials and Azure OpenAI configuration
  - Development and production configuration separation

## Web Interface
- **Main Application** (`app.py`)
  - Flask application with webhook endpoint (`/webhook`)
  - Dashboard endpoint (`/`) for monitoring
  - Request signature verification and body parsing

# Data Flow

1. **Incoming Message Flow**:
   - LINE platform sends webhook to `/webhook` endpoint
   - LineService verifies signature and parses message
   - ConversationService adds user message to history
   - OpenAIService generates response using conversation context
   - Response sent back through LINE Bot API

2. **Conversation Context Flow**:
   - Each user maintains separate conversation history
   - Messages stored with timestamps and roles (user/assistant)
   - History provided to OpenAI for contextual responses
   - Automatic trimming prevents memory overflow

3. **Dashboard Monitoring**:
   - Real-time display of active users and service status
   - Bootstrap-based responsive interface
   - Service health indicators and usage statistics

# External Dependencies

## Required Services
- **LINE Messaging API**: Official account and channel credentials required
- **Azure OpenAI**: API key, endpoint, and deployment configuration needed
- **Python Dependencies**: 
  - `line-bot-sdk-python` for LINE integration
  - `openai` for Azure OpenAI communication  
  - `flask` for web framework
  - `python-dotenv` for environment management

## Environment Variables
- `LINE_CHANNEL_ACCESS_TOKEN`: LINE Bot API access token
- `LINE_CHANNEL_SECRET`: LINE webhook signature verification
- `AZURE_OPENAI_API_KEY`: Azure OpenAI service authentication
- `AZURE_OPENAI_ENDPOINT`: Azure cognitive services endpoint
- `AZURE_OPENAI_DEPLOYMENT_NAME`: Model deployment identifier

## Optional Configuration
- `DEBUG`: Development mode toggle
- `LOG_LEVEL`: Logging verbosity control
- `MAX_MESSAGES_PER_USER`: Conversation history limits
- `MAX_TOTAL_CONVERSATIONS`: Global conversation limits

# Deployment Strategy

## Target Platform
- **Primary**: Azure Web App (recommended for seamless Azure OpenAI integration)
- **Alternative**: Any Python WSGI-compatible hosting platform

## Deployment Requirements
- Python 3.8+ runtime environment
- HTTPS support (required for LINE webhook verification)
- Environment variable configuration
- Persistent process for in-memory conversation storage

## Scaling Considerations
- **Current**: In-memory storage suitable for MVP demonstrations
- **Future**: Database integration recommended for production scale
- **Session Management**: Single-instance deployment maintains conversation state
- **Performance**: Optimized for demo sessions rather than high-volume production

## Monitoring and Logging
- Structured logging with configurable levels
- Webhook event tracking for debugging
- User privacy protection in logs (truncated user IDs)
- Service health monitoring through dashboard interface