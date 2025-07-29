# LINE Bot with Azure OpenAI Integration

## Project Overview
A sophisticated LINE webhook service leveraging Azure OpenAI for intelligent, multilingual chatbot interactions. Provides advanced conversational AI capabilities with seamless web search, image understanding, file processing, and dynamic language support.

**Current Status**: ✅ Active and Running with File Support
- **Platform**: Replit (Python 3.11)
- **Port**: 5000 (Flask + Gunicorn)
- **Main Technologies**: Azure OpenAI (GPT-4.1-nano), Flask, LINE Bot SDK
- **Latest Feature**: Comprehensive file type support for document analysis

## Recent Changes
- **2025-07-29**: Implemented comprehensive file type support
  - Added FileMessage handler for processing all OpenAI-compatible file types
  - Support for PDF, DOC, XLS, PPT, code files, and more (20+ formats)
  - Enhanced FileProcessor with 20MB size limit and comprehensive error handling
  - Complete test coverage with 1,978+ lines of new code
  - Updated documentation and deployment checklist
- **Previous**: Fixed critical HTTP/2 dependency issue by installing h2 package
- **Current State**: All core services operational with full file processing capabilities

## Project Architecture

### Core Services
- **OpenAI Service** (`src/services/openai_service.py`): Azure OpenAI integration with HTTP/2 connection pooling and file processing
- **LINE Service** (`src/services/line_service.py`): LINE Bot API integration with webhook handling for text, image, and file messages
- **Conversation Service** (`src/services/conversation_service.py`): Message context management with file metadata tracking
- **Rich Message Service** (`src/services/rich_message_service.py`): Automated rich content delivery
- **File Processor** (`src/utils/file_utils.py`): Comprehensive file handling with 20+ format support

### Key Features
1. **Conversational AI Flow**: LINE webhook → message processing → Azure OpenAI → response delivery
2. **File Processing**: Upload and analyze documents, spreadsheets, presentations, and code files
3. **Rich Message Automation**: Scheduled AI-generated motivational content with dynamic templates
4. **Multilingual Support**: 9 languages (English, Thai, Chinese, Japanese, Korean, Vietnamese, Spanish, French, German)
5. **Image Understanding**: GPT-4 vision API for image analysis
6. **Web Search Integration**: Real-time information retrieval
7. **Connection Pooling**: Optimized HTTP connections for all external APIs

### File Support Capabilities
- **Documents**: PDF, DOC, DOCX, TXT, RTF, MD
- **Spreadsheets**: XLS, XLSX, CSV, TSV
- **Presentations**: PPT, PPTX
- **Code Files**: PY, JS, HTML, CSS, JSON, XML, SQL
- **Data Files**: JSON, XML, YAML, LOG
- **Size Limit**: 20MB maximum with comprehensive validation
- **Error Handling**: Bilingual error messages (Thai/English)

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

## Testing Infrastructure
- **Framework**: pytest with comprehensive coverage
- **Test Coverage**: 1,978+ lines of new tests for file processing
- **Test Types**: Unit, integration, and performance tests including file processing pipeline
- **Coverage Target**: 80+ % maintained with full file support testing
- **Mock Strategy**: Heavy use of mocks to avoid real API calls during testing

## User Preferences
- Language: English
- Focus: Debugging and maintaining production-ready code
- Approach: Comprehensive problem-solving with detailed explanations
