# Rich Message Automation LINE Bot

## Overview

This repository contains a comprehensive LINE Bot application with Rich Message automation capabilities. The system integrates Azure OpenAI (GPT-4.1-nano) for conversational AI with an automated Rich Message delivery system that generates daily inspirational content in Anthony Bourdain's authentic voice.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Backend Architecture
- **Framework**: Flask web application with modular service architecture
- **Language**: Python 3.x with type hints and modern patterns
- **Design Pattern**: Service-oriented architecture with clear separation of concerns
- **Background Processing**: Celery with Redis for asynchronous task execution
- **Session Management**: Flask sessions with secure secret handling

### Frontend Architecture
- **Web Interface**: Server-side rendered templates using Jinja2
- **Styling**: Bootstrap with custom CSS for responsive design
- **Admin Dashboard**: Comprehensive analytics and campaign management interface
- **Mobile Support**: LINE Bot optimized for mobile messaging

### Data Storage Solutions
- **Primary Storage**: In-memory conversation management with Redis fallback
- **Cache Layer**: Redis for conversation history, template cache, and content cache
- **File Storage**: Local filesystem for templates and generated images
- **Analytics**: SQLite-based metrics storage with aggregation capabilities

### Authentication and Authorization
- **LINE Bot Verification**: HMAC-SHA256 webhook signature validation
- **Azure OpenAI**: API key-based authentication with fallback client support
- **Admin Interface**: Token-based authentication (demo implementation)
- **Security Headers**: Comprehensive CSP, HSTS, and security middleware

## Key Components

### Core Services
1. **LineService**: Handles LINE Bot API integration, webhook processing, and message routing
2. **OpenAIService**: Manages Azure OpenAI integration with Responses API and Chat Completions fallback
3. **ConversationService**: Manages conversation history with memory optimization and Redis persistence
4. **RichMessageService**: Automated Rich Message generation, template management, and delivery coordination

### Rich Message Automation System
1. **TemplateManager**: Canva template loading, caching, and intelligent selection
2. **ContentGenerator**: AI-powered content generation using Anthony Bourdain persona
3. **ImageComposer**: PIL-based image composition with text overlay and styling
4. **DeliveryTracker**: Comprehensive delivery monitoring with retry logic and error handling

### Supporting Utilities
1. **PromptManager**: Structured prompt engineering for consistent AI personality
2. **TimezoneManager**: Global timezone detection and delivery scheduling
3. **AnalyticsTracker**: Engagement metrics collection and success rate monitoring
4. **SecurityUtils**: Webhook verification, CORS handling, and security headers

## Data Flow

### Message Processing Flow
1. LINE webhook receives user message
2. Signature verification and payload validation
3. Message routing based on type (text, image, postback)
4. Conversation context retrieval from storage
5. AI response generation via Azure OpenAI
6. Response formatting and delivery via LINE API
7. Conversation history update and analytics tracking

### Rich Message Automation Flow
1. Celery scheduled tasks trigger content generation
2. Template selection based on time, mood, and user preferences
3. AI content generation using Bourdain persona prompts
4. Image composition with text overlay and styling
5. Delivery coordination across global timezones
6. User interaction tracking and engagement analytics
7. Success rate monitoring and performance optimization

## External Dependencies

### Primary APIs
- **LINE Messaging API**: Core bot functionality, webhook handling, and Rich Message delivery
- **Azure OpenAI API**: GPT-4.1-nano model with Responses API for conversation continuity
- **Redis**: Session storage, caching, and Celery message broker

### Development Dependencies
- **Flask**: Web framework with extensive middleware
- **Celery**: Background task processing and scheduling
- **PIL/Pillow**: Image processing with format support extensions
- **pytest**: Comprehensive testing framework with 614 tests
- **uv**: Modern Python dependency management

### Optional Integrations
- **pillow-heif**: HEIC/HEIF image format support for Samsung devices
- **pillow-avif**: AVIF image format support for modern Android
- **pillow-jxl**: JPEG XL support for cutting-edge formats

## Deployment Strategy

### Local Development
- Direct Python execution with auto-reload
- In-memory storage for rapid iteration
- Debug mode with comprehensive logging
- Hot-reload for template and static assets

### Production Deployment
- **Container**: Docker with multi-stage builds
- **Web Server**: Gunicorn with multiple workers
- **Reverse Proxy**: Nginx for static assets and load balancing
- **Process Management**: Celery workers with Redis coordination
- **Monitoring**: Prometheus metrics with health check endpoints

### Scaling Considerations
- Horizontal scaling via Docker Compose
- Redis cluster for high-availability caching
- Load balancing for webhook processing
- Background task distribution across worker nodes
- Database migration path from SQLite to PostgreSQL for production analytics

The system is designed for gradual scaling from development to production with clear migration paths for each component. The modular architecture allows independent scaling of conversation processing, Rich Message generation, and delivery coordination.