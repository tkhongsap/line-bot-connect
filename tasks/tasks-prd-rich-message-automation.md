# Rich Message Automation System - Task List

## Relevant Files

- `src/services/rich_message_service.py` - Core service for Rich Message automation, template management, and content generation coordination
- `src/services/rich_message_service.test.py` - Unit tests for RichMessageService
- `src/utils/template_manager.py` - Utility for managing Canva templates, metadata, and template selection algorithms
- `src/utils/template_manager.test.py` - Unit tests for template management utilities
- `src/utils/content_generator.py` - Content generation pipeline with themed content and Azure OpenAI integration
- `src/utils/content_generator.test.py` - Unit tests for content generation system
- `src/utils/image_composer.py` - Image composition utility for text overlay on Canva templates using PIL
- `src/utils/image_composer.test.py` - Unit tests for image composition functionality
- `src/tasks/rich_message_automation.py` - Celery tasks for scheduled Rich Message generation and delivery
- `src/tasks/rich_message_automation.test.py` - Unit tests for automation tasks
- `src/services/line_service.py` - Extension of existing LineService to support Rich Message API calls
- `src/services/openai_service.py` - Extension of existing OpenAIService for themed content generation
- `src/utils/timezone_manager.py` - Timezone detection and management for global user delivery
- `src/utils/timezone_manager.test.py` - Unit tests for timezone management
- `src/utils/analytics_tracker.py` - User engagement and delivery metrics tracking system
- `src/utils/analytics_tracker.test.py` - Unit tests for analytics tracking
- `templates/rich_messages/metadata.json` - Template metadata configuration file
- `templates/rich_messages/backgrounds/` - Directory for Canva-exported template backgrounds
- `static/fonts/` - Font files for text overlay on templates
- `src/config/rich_message_config.py` - Configuration settings for Rich Message system
- `tests/integration/test_rich_message_flow.py` - End-to-end integration tests for Rich Message automation

### Notes

- Unit tests should be placed alongside the code files they are testing
- Use `./scripts/run_tests.sh all` to run the complete test suite
- Integration tests verify the full Rich Message generation and delivery pipeline
- Template files are stored outside `/src` to separate code from content assets

## Tasks

- [ ] 0.0 Template Design & Preparation (Manual Phase)
  - [ ] 0.1 Create Canva template designs for different themes (morning energy, evening calm, productivity, wellness, general motivation)
  - [ ] 0.2 Export templates at LINE specifications (2500×1686px, PNG/JPEG, max 1MB)
  - [ ] 0.3 Test text positioning areas and readability across different templates
  - [ ] 0.4 Create template metadata file with positioning coordinates and theme classifications
  - [ ] 0.5 Organize exported templates in `/templates/rich_messages/backgrounds/` directory
  - [ ] 0.6 Validate template compatibility with mobile LINE app display

- [ ] 1.0 Rich Message Infrastructure Setup
  - [ ] 1.1 Create RichMessageService class with LINE Rich Message API integration
  - [ ] 1.2 Extend LineService to support Rich Message creation and delivery
  - [ ] 1.3 Implement Rich Message data models and validation
  - [ ] 1.4 Add Rich Message configuration settings and environment variables
  - [ ] 1.5 Create unit tests for RichMessageService core functionality

- [ ] 2.0 Template & Content Management System
  - [ ] 2.1 Implement TemplateManager for loading and managing Canva templates
  - [ ] 2.2 Create ContentGenerator with Azure OpenAI integration for themed content
  - [ ] 2.3 Build ImageComposer for text overlay on templates using PIL
  - [ ] 2.4 Implement template selection algorithms based on content mood and theme
  - [ ] 2.5 Add content validation and appropriateness filtering
  - [ ] 2.6 Create comprehensive unit tests for all template and content management components

- [ ] 3.0 Automated Scheduling System
  - [ ] 3.1 Create Celery tasks for daily Rich Message generation and delivery
  - [ ] 3.2 Implement timezone-aware scheduling with user timezone detection
  - [ ] 3.3 Build delivery coordination system for multiple timezones
  - [ ] 3.4 Add retry logic and error handling for failed deliveries
  - [ ] 3.5 Implement delivery tracking and success rate monitoring
  - [ ] 3.6 Create unit tests for all scheduling and delivery components

- [ ] 4.0 User Interaction & Analytics
  - [ ] 4.1 Implement Rich Message interaction buttons (Share, Save, Like/React)
  - [ ] 4.2 Create analytics tracking system for user engagement metrics
  - [ ] 4.3 Build user interaction handling and response tracking
  - [ ] 4.4 Add engagement metrics collection and storage
  - [ ] 4.5 Implement administrative controls for manual triggering and monitoring
  - [ ] 4.6 Create unit tests for interaction handling and analytics tracking

- [ ] 5.0 Testing & Deployment
  - [ ] 5.1 Create integration tests for complete Rich Message generation pipeline
  - [ ] 5.2 Build end-to-end tests for template loading, content generation, and delivery
  - [ ] 5.3 Implement performance testing for image generation and delivery times
  - [ ] 5.4 Add error scenario testing and fallback mechanism validation
  - [ ] 5.5 Create deployment scripts and production environment setup
  - [ ] 5.6 Validate system meets all PRD success metrics and requirements