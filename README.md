# LINE Bot Connect

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Flask](https://img.shields.io/badge/flask-3.1+-green.svg)](https://flask.palletsprojects.com/)
[![Tests](https://img.shields.io/badge/tests-80%25%20coverage-brightgreen.svg)](./README_TESTING.md)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

A sophisticated Flask-based LINE Bot application powered by Azure OpenAI, featuring conversational AI and automated Rich Message delivery with advanced content generation capabilities.

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Environment Configuration](#environment-configuration)
- [Development](#development)
- [Testing](#testing)
- [Deployment](#deployment)
- [API Endpoints](#api-endpoints)
- [Usage Examples](#usage-examples)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)

## Features

### 🤖 Conversational AI
- **Multi-modal Intelligence**: GPT-4.1-nano with text, image, and file processing
- **Multilingual Support**: Native support for 9 languages with cultural sensitivity
- **Web Search Integration**: Real-time information retrieval for news, weather, stocks
- **File Processing**: Support for 20+ formats including documents, spreadsheets, code files
- **Image Understanding**: Advanced vision capabilities with HEIC/HEIF support
- **Conversation Memory**: Extended 100-message history with intelligent cleanup

### 🎨 Rich Message Automation
- **AI-Generated Content**: Daily motivational messages with Bourdain persona
- **Template Library**: 50+ categorized background templates (motivation, wellness, productivity)
- **Dynamic Composition**: Real-time text overlay on template backgrounds
- **Smart Scheduling**: Timezone-aware delivery with Celery automation
- **Interactive Elements**: Conversation triggers and engagement tracking
- **Analytics Dashboard**: Comprehensive delivery metrics and user engagement

### 🔧 Technical Capabilities
- **Hybrid Storage**: Seamless Redis/in-memory fallback with circuit breaker
- **Connection Pooling**: Advanced HTTP/2 pooling for optimal performance
- **Background Processing**: Celery + Redis for async task handling
- **Rate Limiting**: Sophisticated per-user and per-endpoint controls
- **Memory Management**: Automatic cleanup with pressure monitoring
- **Health Monitoring**: Real-time service health and performance metrics

## Architecture

### Service-Oriented Design
- **LineService**: LINE Bot SDK integration with optimized connection pooling
- **OpenAIService**: Hybrid Azure OpenAI with Responses API + Chat Completions fallback
- **ConversationService**: Unified conversation management with hybrid storage
- **RichMessageService**: Advanced Rich Message system with 4-tier content fallback
- **Admin Interface**: Comprehensive dashboard for campaign management and analytics

### Data Flow
1. **Conversational AI**: LINE webhook → message processing → AI response → delivery
2. **Rich Messages**: Scheduled automation → content generation → template selection → delivery
3. **Background Tasks**: Celery processing for image handling, automation, and analytics

### Storage Architecture
- **Conversations**: Redis (primary) + in-memory (fallback)
- **Analytics**: PostgreSQL with comprehensive schema
- **Caching**: Multi-tier LRU → Redis → memory hierarchy
- **Assets**: File system for Rich Message templates and backgrounds

## Quick Start

### Prerequisites
- Python 3.11+
- Redis (optional, will fallback to in-memory)
- PostgreSQL (optional, for analytics)

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd line-bot-connect
   ```

2. **Install dependencies using uv (recommended)**
   ```bash
   # Install uv if not already installed
   curl -LsSf https://astral.sh/uv/install.sh | sh
   
   # Install dependencies
   uv sync
   ```

   **Alternative with pip**
   ```bash
   pip install -e .
   ```

3. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your credentials (see Environment Configuration below)
   ```

4. **Run the application**
   ```bash
   # Development mode
   python app.py
   
   # Production mode with Gunicorn
   gunicorn -w 4 -b 0.0.0.0:5000 app:app
   ```

5. **Verify installation**
   - Visit `http://localhost:5000` for dashboard
   - Check `http://localhost:5000/health` for service status

## Environment Configuration

### Required Variables
```bash
# LINE Bot Configuration
LINE_CHANNEL_ACCESS_TOKEN=your_line_channel_access_token
LINE_CHANNEL_SECRET=your_line_channel_secret
LINE_CHANNEL_ID=your_line_channel_id

# Azure OpenAI Configuration
AZURE_OPENAI_API_KEY=your_azure_openai_api_key
AZURE_OPENAI_ENDPOINT=https://your-endpoint.openai.azure.com
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4.1-nano

# Flask Configuration
SESSION_SECRET=your_secure_session_secret
```

### Optional Configuration
```bash
# Application Environment
DEBUG=false
LOG_LEVEL=INFO
APP_ENV=production

# Conversation Limits
MAX_MESSAGES_PER_USER=100
MAX_TOTAL_CONVERSATIONS=1000

# Rate Limiting
RATE_LIMIT_PER_MINUTE=200
RATE_LIMIT_PER_HOUR=1000

# Redis Configuration (optional)
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/1

# Database Configuration (optional)
DATABASE_URL=postgresql://user:password@localhost/linebot
```

### Environment Setup
You can copy `.env.example` to `.env` and update the values:
```bash
cp .env.example .env
```

## Development

### Development Commands
```bash
# Run in development mode
python app.py

# Run with Gunicorn (production-like)
gunicorn --bind 0.0.0.0:5000 --reload main:app

# Install development dependencies
uv sync --group dev
```

### Code Quality
```bash
# Run linting checks
./scripts/run_tests.sh lint

# Run all tests
./scripts/run_tests.sh all

# Run with coverage
./scripts/run_tests.sh coverage
```

## Testing

### Comprehensive Test Suite
- **Coverage**: 80% minimum coverage requirement
- **Test Files**: 49 test files across multiple categories
- **Test Organization**: Unit (37 files), Integration (7 files), Performance, Error scenarios

### Test Commands
```bash
# Install test dependencies
./scripts/run_tests.sh install

# Run all tests
./scripts/run_tests.sh all

# Run specific test categories
./scripts/run_tests.sh unit
./scripts/run_tests.sh integration
./scripts/run_tests.sh marker openai_api

# Advanced test options
./scripts/run_tests.sh coverage    # With coverage report
./scripts/run_tests.sh quick       # Skip slow tests
./scripts/run_tests.sh parallel    # Run in parallel
./scripts/run_tests.sh file tests/unit/test_openai_service.py  # Specific file

# Maintenance commands
./scripts/run_tests.sh clean       # Clean test artifacts
./scripts/run_tests.sh stats       # Show test statistics
```

### Alternative Commands
```bash
# Using Makefile
make test      # Run all tests
make coverage  # Run with coverage
make lint      # Run linting
make clean     # Clean artifacts

# Direct pytest commands
uv run pytest tests/unit/test_openai_service.py -v
```

For detailed testing information, see [README_TESTING.md](README_TESTING.md).

## Deployment

### Replit Deployment (Recommended)
Automatic deployment with autoscale support:

1. **Configure environment variables** in Replit Secrets
2. **Deploy**: Push changes to trigger automatic redeployment
3. **Verify**: Check deployment logs and health endpoint

### Docker Deployment
```bash
# Local Docker
docker build -t line-bot-connect .
docker run -p 5000:5000 --env-file .env line-bot-connect

# Production with Docker Compose
cd deployment
docker-compose up -d

# Include full stack (Redis, PostgreSQL, monitoring)
docker-compose -f docker-compose.yml up -d
```

### Local Development
```bash
# Standard development setup
python app.py

# With Redis for full functionality
docker run -d -p 6379:6379 redis:7-alpine
python app.py
```

For comprehensive deployment instructions, see [DEPLOYMENT.md](DEPLOYMENT.md).

## API Endpoints

### Main Application
- `GET /` - Dashboard with statistics and service status
- `POST /webhook` - LINE Bot webhook endpoint
- `GET /webhook` - Webhook verification endpoint
- `GET /health` - Health check with service status
- `GET /conversations` - Conversation statistics
- `GET /memory` - Memory usage and alerts
- `GET /connection-pools` - Connection pool metrics

### Admin Interface
- `GET /admin/` - Main admin dashboard
- `GET /admin/campaigns` - Campaign management
- `GET /admin/analytics` - Analytics dashboard
- `GET /admin/system/health` - System health monitoring

### Static Assets
- `GET /static/backgrounds/<filename>` - Rich Message template backgrounds

### Health Monitoring
```bash
# Check overall health
curl http://localhost:5000/health

# Check memory status
curl http://localhost:5000/memory

# Check connection pools
curl http://localhost:5000/connection-pools
```

## Usage Examples

### Conversational AI Examples
```
User: "What's the latest news about Thailand?"
Bot: [Returns current news with sources via web search]

User: "What's Tesla's stock price today?"
Bot: [Provides real-time market data]

User: [Sends image] "What do you see?"
Bot: [Detailed image analysis with conversation context]

User: "สวัสดี" (Thai greeting)
Bot: [Responds in Thai with cultural appropriateness]
```

### Rich Message Automation
- **Daily 9 AM** motivational messages with AI-generated content
- **Template selection** based on content mood and time of day
- **Interactive buttons** for user engagement tracking
- **Analytics tracking** for delivery success and user interactions

### File Processing
- **Documents**: PDF, DOCX, TXT files with content extraction
- **Spreadsheets**: Excel, CSV with data analysis
- **Code Files**: Python, JavaScript, etc. with syntax understanding
- **Images**: JPEG, PNG, HEIC with vision analysis

## Troubleshooting

### Common Issues

**Connection Errors**
```bash
# Check Redis connection
redis-cli ping

# Verify environment variables
python -c "import os; print(os.environ.get('AZURE_OPENAI_API_KEY', 'Not set'))"
```

**Memory Issues**
- Monitor `/memory` endpoint for usage statistics
- Check logs for memory pressure warnings
- Adjust `MAX_MESSAGES_PER_USER` if needed

**Rate Limiting**
- Check rate limit headers in responses
- Monitor `/health` endpoint for rate limit status
- Adjust rate limits in environment configuration

**Rich Message Issues**
- Verify LINE channel ID is set correctly
- Check background image URLs are accessible
- Review admin dashboard for delivery failures

### Performance Optimization
- Enable Redis for better conversation storage
- Use PostgreSQL for analytics persistence
- Configure connection pooling settings
- Monitor connection pool metrics at `/connection-pools`

### Debugging
```bash
# Enable debug logging
export DEBUG=true
export LOG_LEVEL=DEBUG

# Run with verbose logging
python app.py

# Check specific service logs
grep "OpenAIService" app.log
grep "RichMessageService" app.log
```

## Contributing

### Development Workflow
1. **Fork** the repository
2. **Create** a feature branch
3. **Implement** changes with tests
4. **Run** test suite: `./scripts/run_tests.sh all`
5. **Ensure** 80% test coverage
6. **Submit** pull request

### Code Standards
- **Testing**: All new features must include tests
- **Coverage**: Maintain 80% minimum coverage
- **Documentation**: Update CLAUDE.md for architectural changes
- **Linting**: Code must pass linting checks

### Architecture Guidelines
- Follow service-oriented patterns
- Implement error handling with circuit breakers
- Add connection pooling for external APIs
- Include comprehensive logging and monitoring

---

## Documentation Links
- [Comprehensive Testing Guide](README_TESTING.md)
- [Deployment Instructions](DEPLOYMENT.md)
- [Development Documentation](CLAUDE.md)
- [File Processing Support](docs/FILE_SUPPORT.md)
- [Deployment Checklist](docs/DEPLOYMENT_CHECKLIST.md)

## License
This project is licensed under the MIT License - see the LICENSE file for details.