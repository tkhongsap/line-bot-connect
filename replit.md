# Overview

This is a LINE Bot MVP application that provides conversational AI capabilities through Azure OpenAI GPT-4.1 integration. The bot maintains conversation context per user and serves as a demonstration platform for AI-powered messaging services. The application is built with Flask and deployed on Replit with both development and production webhook endpoints available.

**Status**: ✅ Live and operational with streaming responses enabled  
**Development**: https://3a0d8469-1495-4b1d-afe6-dc163885326a-00-2icgob4ardifi.worf.replit.dev/webhook  
**Production**: https://line-bot-connect-tkhongsap.replit.app/webhook  
**Azure OpenAI**: Connected and tested successfully with GPT-4.1 + streaming  
**LINE Integration**: Webhook verified and active  
**Performance**: Single complete responses using GPT-4.1-nano model with clean one-message delivery and context preservation  
**Last Updated**: July 24, 2025

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
   - Handles LINE Bot SDK integration (TextMessage and ImageMessage)
   - Manages webhook signature verification
   - Processes incoming text and image messages
   - Supports bilingual error handling for image processing
   - Uses LINE Bot SDK Python for API communication

2. **OpenAIService** (`src/services/openai_service.py`)
   - Integrates with Azure OpenAI using the official Python SDK
   - **NEW**: Uses GPT-4.1-nano's native multimodal capabilities for image understanding
   - Maintains conversation context using system prompts
   - Supports multilingual communication with automatic language matching
   - Implements response length optimization for LINE messaging
   - Handles both text-only and multimodal conversations seamlessly

3. **ConversationService** (`src/services/conversation_service.py`)
   - Manages in-memory conversation history per user
   - **NEW**: Tracks image message types alongside text messages
   - Implements conversation limits (100 messages per user, 1000 total conversations)
   - Provides conversation context for AI responses
   - Handles automatic conversation trimming

4. **ImageProcessor** (`src/utils/image_utils.py`)
   - **NEW**: Downloads images from LINE Bot content API
   - Validates image formats (JPG, PNG, GIF) and file sizes
   - Converts images to base64 for GPT-4 vision API
   - Handles temporary file management with automatic cleanup
   - Provides image metadata extraction

## Configuration Management
- **Settings** (`src/config/settings.py`)
  - Environment variable management with validation
  - Support for LINE credentials and Azure OpenAI configuration
  - Development and production configuration separation

# Recent Changes

## Dynamic Button Response System Fixed (July 27, 2025)
- ✅ **Button Response Issue Resolved**: Fixed "'str' object has no attribute 'get'" error preventing dynamic AI responses
- ✅ **Response Format Handling**: Enhanced interaction handler to properly handle both string and dictionary responses from OpenAI service
- ✅ **LSP Error Fixes**: Resolved 7 type checking errors in rich_message_service.py with proper null checking
- ✅ **Dynamic AI Generation**: All 4 button types (Tell me more, What's real here?, Been there?, Recipe?) now generate unique, contextual AI responses
- ✅ **Context-Aware Responses**: Buttons now reference both message content and visual context using Anthony Bourdain's authentic voice
- ✅ **Fallback Prevention**: Eliminated static fallback responses, ensuring all button clicks generate fresh AI content

## LineOA Rich Message System with Image Display Fixed (July 27, 2025)
- ✅ **Image Display Fixed**: Added Flask route `/static/backgrounds/` to serve template images via HTTPS URLs
- ✅ **LineOA Integration Confirmed**: Successfully tested rich message sending through LINE Official Account  
- ✅ **AI Content Generation**: Azure OpenAI GPT-4.1 generates professional content tailored to template themes
- ✅ **Template System**: 50+ beautiful templates with full image display (productivity, inspiration, motivation, nature themes)
- ✅ **Interactive Features**: Like, Share, Save, React buttons fully functional for engagement tracking
- ✅ **Professional Messaging**: Business-appropriate content generation for official account broadcasting
- ✅ **Production Ready**: Complete system with visual templates confirmed working for follower engagement and marketing campaigns

## Rich Message Automation Testing System (July 2025)
- ✅ **Rich Message Testing Scripts**: Created comprehensive testing tools for safe rich message automation
- ✅ **Template System**: 50+ beautiful templates available (Little Prince, motivation, nature, productivity themes)
- ✅ **Personal Testing**: Safe testing mode to send rich messages to yourself only (no broadcast)
- ✅ **Interactive Features**: Rich messages include Like, Share, Save, React buttons for engagement tracking
- ✅ **User ID Capture**: Automated tool to capture LINE User ID for testing
- ✅ **Multiple Test Scripts**: Quick test, advanced template selection, and user ID helper tools

## Rich Message Testing Tools Added
1. **Quick Rich Test** (`quick_rich_test.py`)
   - Simple one-command testing
   - Mock mode for safe testing
   - Live send mode for actual delivery
   
2. **Advanced Template Testing** (`send_test_rich_message.py`)
   - Interactive menu with 6+ template options
   - Theme-based content generation
   - Template preview and selection

3. **User ID Capture** (`get_my_user_id.py`)
   - Automated LINE User ID detection
   - Webhook monitoring for ID capture
   - Safe file-based ID storage

## Technical Features Added
- **Service Constructor Fixes**: Corrected API parameter issues in all test scripts
- **Template Management**: Metadata-driven template selection system
- **Interactive Buttons**: Like, Share, Save, React functionality with analytics
- **Safe Testing Architecture**: Mock mode prevents accidental broadcasting to all users

# Previous Changes (January 2024)

## Image Understanding Feature Implementation
- ✅ **ImageMessage Handler**: Added support for image messages in LINE service
- ✅ **Vision API Integration**: Extended OpenAI service with GPT-4 vision capabilities
- ✅ **Image Processing Pipeline**: Created complete image download, validation, and conversion utilities
- ✅ **Conversation Context**: Enhanced conversation service to track image messages
- ✅ **Error Handling**: Implemented bilingual error messages for image processing failures
- ✅ **Automatic Cleanup**: Added proper temporary file management for image processing

## Technical Features Added
1. **LINE Bot Image Support**
   - ImageMessage event handler registration
   - Image download from LINE content API
   - Privacy-conscious logging (truncated user IDs)

2. **GPT-4.1-nano Multimodal Integration**  
   - Base64 image encoding for API compatibility
   - Native multimodal message format for Azure OpenAI
   - Mixed conversation context (text + image references)
   - Superior image understanding compared to previous models

3. **Image Processing Utilities**
   - Format validation (JPG, PNG, GIF)
   - File size limits (10MB max)
   - Temporary file management with automatic cleanup
   - Image metadata extraction

4. **Enhanced Conversation Management**
   - Image message type tracking
   - Context preservation for follow-up questions about images
   - Improved conversation history format

## User Experience Improvements
- Seamless image sharing within existing chat interface
- Bilingual error messages for unsupported formats
- Graceful fallback when image processing fails
- Maintains conversation flow for follow-up questions about imageson

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