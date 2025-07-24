"""
Pytest configuration and shared fixtures for LINE Bot tests
"""
import pytest
import os
from unittest.mock import Mock, patch
from src.config.settings import Settings
from src.services.conversation_service import ConversationService
from src.services.openai_service import OpenAIService
from src.services.line_service import LineService


@pytest.fixture
def mock_settings():
    """Mock settings for testing"""
    settings = Mock(spec=Settings)
    settings.LINE_CHANNEL_ACCESS_TOKEN = "test_channel_access_token"
    settings.LINE_CHANNEL_SECRET = "test_channel_secret"
    settings.AZURE_OPENAI_API_KEY = "test_openai_key"
    settings.AZURE_OPENAI_ENDPOINT = "https://test.openai.azure.com"
    settings.AZURE_OPENAI_API_VERSION = "2025-01-01-preview"
    settings.AZURE_OPENAI_DEPLOYMENT_NAME = "gpt-4.1-mini"
    settings.DEBUG = True
    settings.LOG_LEVEL = "DEBUG"
    settings.MAX_MESSAGES_PER_USER = 100
    settings.MAX_TOTAL_CONVERSATIONS = 1000
    return settings


@pytest.fixture
def conversation_service():
    """Create a fresh ConversationService instance for testing"""
    return ConversationService()


@pytest.fixture
def mock_openai_client():
    """Mock Azure OpenAI client"""
    with patch('src.services.openai_service.AzureOpenAI') as mock_client:
        mock_instance = Mock()
        mock_client.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def openai_service(mock_settings, conversation_service, mock_openai_client):
    """Create OpenAIService with mocked dependencies"""
    return OpenAIService(mock_settings, conversation_service)


@pytest.fixture
def mock_line_bot_api():
    """Mock LINE Bot API"""
    with patch('src.services.line_service.LineBotApi') as mock_api:
        mock_instance = Mock()
        mock_api.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_webhook_handler():
    """Mock LINE webhook handler"""
    with patch('src.services.line_service.WebhookHandler') as mock_handler:
        mock_instance = Mock()
        mock_handler.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def line_service(mock_settings, openai_service, conversation_service, mock_line_bot_api, mock_webhook_handler):
    """Create LineService with mocked dependencies"""
    return LineService(mock_settings, openai_service, conversation_service)


@pytest.fixture
def sample_line_message_event():
    """Sample LINE message event for testing"""
    event = Mock()
    event.source.user_id = "test_user_123"
    event.message.text = "Hello, bot!"
    event.message.id = "msg_123"
    event.reply_token = "reply_token_123"
    return event


@pytest.fixture
def sample_openai_response():
    """Sample OpenAI API response"""
    response = Mock()
    response.choices = [Mock()]
    response.choices[0].message.content = "Hello! How can I help you today?"
    response.usage.total_tokens = 50
    return response


@pytest.fixture
def sample_openai_streaming_response():
    """Sample OpenAI streaming response"""
    chunks = []
    
    # Create sample streaming chunks
    chunk1 = Mock()
    chunk1.choices = [Mock()]
    chunk1.choices[0].delta.content = "Hello! "
    chunk1.usage = None
    chunks.append(chunk1)
    
    chunk2 = Mock()
    chunk2.choices = [Mock()]
    chunk2.choices[0].delta.content = "How can I help you today?"
    chunk2.usage = None
    chunks.append(chunk2)
    
    final_chunk = Mock()
    final_chunk.choices = [Mock()]
    final_chunk.choices[0].delta.content = None
    final_chunk.usage = Mock()
    final_chunk.usage.total_tokens = 50
    chunks.append(final_chunk)
    
    return chunks


@pytest.fixture
def clean_environment():
    """Clean environment variables for testing"""
    original_env = os.environ.copy()
    
    # Clear LINE Bot related environment variables
    env_vars_to_clear = [
        'LINE_CHANNEL_ACCESS_TOKEN',
        'LINE_CHANNEL_SECRET', 
        'AZURE_OPENAI_API_KEY',
        'AZURE_OPENAI_ENDPOINT',
        'AZURE_OPENAI_DEPLOYMENT_NAME'
    ]
    
    for var in env_vars_to_clear:
        if var in os.environ:
            del os.environ[var]
    
    yield
    
    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture(autouse=True)
def no_requests(monkeypatch):
    """Disable HTTP requests during tests"""
    def mock_request(*args, **kwargs):
        raise RuntimeError("HTTP requests are not allowed in tests. Use responses or httpx mock instead.")
    
    monkeypatch.setattr("requests.request", mock_request)
    monkeypatch.setattr("httpx.request", mock_request)


# Test data fixtures
@pytest.fixture
def sample_conversation_history():
    """Sample conversation history data"""
    return [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there! How can I help you?"},
        {"role": "user", "content": "What's the weather like?"},
        {"role": "assistant", "content": "I don't have access to current weather data, but I'd be happy to help with other questions!"}
    ]


@pytest.fixture
def large_conversation_history():
    """Large conversation history for testing limits"""
    history = []
    for i in range(150):  # More than the 100 message limit
        history.append({"role": "user", "content": f"Message {i}"})
        history.append({"role": "assistant", "content": f"Response {i}"})
    return history