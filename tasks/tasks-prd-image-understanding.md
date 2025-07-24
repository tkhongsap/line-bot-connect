# Tasks: Image Understanding for LINE Bot

## Relevant Files

- `src/services/line_service.py` - Main LINE Bot service that needs to handle ImageMessage events alongside TextMessage
- `src/services/openai_service.py` - Azure OpenAI service that needs vision capabilities for GPT-4.1-nano
- `src/services/conversation_service.py` - Conversation history service that needs to track image message context
- `src/utils/image_utils.py` - New utility module for image download, processing, and cleanup functions
- `src/config/settings.py` - Configuration settings (may need image processing limits/configs)
- `app.py` - Main Flask application (may need endpoint updates for image handling)
- `tests/test_line_service.py` - Unit tests for LINE service image handling (to be created)
- `tests/test_openai_service.py` - Unit tests for OpenAI vision integration (to be created)
- `tests/test_image_utils.py` - Unit tests for image utilities (to be created)

### Notes

- Tests should be created in a `tests/` directory to validate image processing functionality
- Image files will be temporarily stored and cleaned up after processing
- Error handling should maintain bilingual support (English/Thai) consistent with existing implementation
- Use existing logging patterns for image processing events

## Tasks

- [x] 1.0 LINE Bot Image Message Handler Integration
  - [x] 1.1 Import ImageMessage from linebot.models in line_service.py
  - [x] 1.2 Add ImageMessage event handler registration alongside existing TextMessage handler
  - [x] 1.3 Implement _handle_image_message method to process incoming image events
  - [x] 1.4 Add logging for image message receipt with user privacy protection (truncated user IDs)
  - [x] 1.5 Handle cases where images are sent with accompanying text messages
  - [x] 1.6 Implement fallback behavior when image processing fails (graceful degradation to text-only response)

- [ ] 2.0 Image Download and Processing Pipeline
  - [ ] 2.1 Create src/utils/image_utils.py module with image processing utilities
  - [ ] 2.2 Implement download_image_from_line function using LINE Bot API message content endpoint
  - [ ] 2.3 Add image format validation (JPG, PNG, GIF) and size limit checking
  - [ ] 2.4 Create temporary file management with automatic cleanup using tempfile module
  - [ ] 2.5 Implement image-to-base64 encoding for GPT-4.1-nano vision API compatibility
  - [ ] 2.6 Add proper error handling for network failures during image download
  - [ ] 2.7 Implement image preprocessing if needed (resize for API limits, format conversion)

- [ ] 3.0 GPT-4.1-nano Vision Integration
  - [ ] 3.1 Research and implement vision message format for Azure OpenAI GPT-4.1-nano
  - [ ] 3.2 Extend get_response method in openai_service.py to accept image data parameter
  - [ ] 3.3 Create vision-enabled message structure combining text and image for API calls
  - [ ] 3.4 Update both streaming and standard response methods to handle vision requests
  - [ ] 3.5 Implement proper token usage tracking for vision API calls (different pricing)
  - [ ] 3.6 Add vision-specific error handling and fallback to text-only processing
  - [ ] 3.7 Test vision API integration with sample images to ensure proper formatting

- [ ] 4.0 Conversation Context Enhancement
  - [ ] 4.1 Update conversation_service.py to handle image message types in history
  - [ ] 4.2 Implement image reference storage in conversation context (metadata, not actual image data)
  - [ ] 4.3 Enable follow-up questions about previously sent images within same conversation
  - [ ] 4.4 Update conversation history format to include image message indicators
  - [ ] 4.5 Implement conversation context limit management with image messages included
  - [ ] 4.6 Add support for mixed conversation flows (text + images + follow-up questions)

- [ ] 5.0 Error Handling and User Experience
  - [ ] 5.1 Create bilingual error messages for unsupported image formats (English/Thai)
  - [ ] 5.2 Implement graceful handling of image download failures with user-friendly messages
  - [ ] 5.3 Add error handling for Azure OpenAI vision API failures with fallback options
  - [ ] 5.4 Create user feedback for image processing status (processing, completed, failed)
  - [ ] 5.5 Implement timeout handling for slow image processing (10-second target)
  - [ ] 5.6 Add logging for all error conditions with proper context for debugging
  - [ ] 5.7 Test error scenarios: large images, corrupted files, network issues, API failures