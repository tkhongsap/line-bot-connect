"""
Unit tests for OpenAI service
"""
import pytest
from unittest.mock import Mock, patch, call
from src.services.openai_service import OpenAIService


@pytest.mark.unit
@pytest.mark.openai_api
class TestOpenAIService:
    """Test OpenAI service functionality"""
    
    def test_init(self, mock_settings, conversation_service):
        """Test OpenAI service initialization"""
        with patch('src.services.openai_service.AzureOpenAI') as mock_client:
            service = OpenAIService(mock_settings, conversation_service)
            
            assert service.settings == mock_settings
            assert service.conversation_service == conversation_service
            
            # Verify Azure OpenAI client initialization
            mock_client.assert_called_once_with(
                api_key=mock_settings.AZURE_OPENAI_API_KEY,
                api_version=mock_settings.AZURE_OPENAI_API_VERSION,
                azure_endpoint=mock_settings.AZURE_OPENAI_ENDPOINT
            )
    
    def test_get_response_standard_success(self, openai_service, sample_openai_response):
        """Test successful standard (non-streaming) response"""
        user_id = "test_user"
        user_message = "Hello"
        
        # Mock the OpenAI client response
        openai_service.client.chat.completions.create.return_value = sample_openai_response
        
        result = openai_service.get_response(user_id, user_message, use_streaming=False)
        
        assert result['success'] is True
        assert result['message'] == "Hello! How can I help you today?"
        assert result['tokens_used'] == 50
        assert result['streaming'] is False
        
        # Verify message was added to conversation
        conversation = openai_service.conversation_service.get_conversation_history(user_id)
        assert len(conversation) == 2  # User message + AI response
        assert conversation[0]['role'] == 'user'
        assert conversation[0]['content'] == user_message
        assert conversation[1]['role'] == 'assistant'
        assert conversation[1]['content'] == "Hello! How can I help you today?"
    
    def test_get_response_streaming_success(self, openai_service, sample_openai_streaming_response):
        """Test successful streaming response"""
        user_id = "test_user"
        user_message = "Hello"
        
        # Mock the streaming response
        openai_service.client.chat.completions.create.return_value = iter(sample_openai_streaming_response)
        
        result = openai_service.get_response(user_id, user_message, use_streaming=True)
        
        assert result['success'] is True
        assert result['message'] == "Hello! How can I help you today?"
        assert result['tokens_used'] == 50
        assert result['streaming'] is True
        assert 'chunks_received' in result
        assert 'chunks_sent' in result
    
    def test_get_response_with_conversation_history(self, openai_service, sample_conversation_history, sample_openai_response):
        """Test response generation with existing conversation history"""
        user_id = "test_user"
        user_message = "Continue our chat"
        
        # Add existing conversation history
        for msg in sample_conversation_history:
            openai_service.conversation_service.add_message(user_id, msg['role'], msg['content'])
        
        openai_service.client.chat.completions.create.return_value = sample_openai_response
        
        result = openai_service.get_response(user_id, user_message, use_streaming=False)
        
        assert result['success'] is True
        
        # Verify the API was called with conversation history
        call_args = openai_service.client.chat.completions.create.call_args
        messages = call_args[1]['messages']
        
        # Should include system prompt + conversation history + new message
        assert len(messages) >= 6  # System + 4 history + new message
        assert messages[0]['role'] == 'system'
        assert messages[-1]['role'] == 'user'
        assert messages[-1]['content'] == user_message
    
    def test_get_response_conversation_limit(self, openai_service, large_conversation_history, sample_openai_response):
        """Test conversation history limiting to prevent token overflow"""
        user_id = "test_user"
        user_message = "New message"
        
        # Add large conversation history
        for msg in large_conversation_history:
            openai_service.conversation_service.add_message(user_id, msg['role'], msg['content'])
        
        openai_service.client.chat.completions.create.return_value = sample_openai_response
        
        result = openai_service.get_response(user_id, user_message, use_streaming=False)
        
        assert result['success'] is True
        
        # Verify only recent messages are sent to API (last 20 messages = 10 exchanges)
        call_args = openai_service.client.chat.completions.create.call_args
        messages = call_args[1]['messages']
        
        # System prompt + up to 20 recent messages + current message
        assert len(messages) <= 22
    
    def test_get_response_api_error(self, openai_service):
        """Test handling of OpenAI API errors"""
        user_id = "test_user"
        user_message = "Hello"
        
        # Mock API error
        openai_service.client.chat.completions.create.side_effect = Exception("API Error")
        
        result = openai_service.get_response(user_id, user_message, use_streaming=False)
        
        assert result['success'] is False
        assert result['error'] == "API Error"
        assert result['message'] is None
    
    def test_streaming_fallback_to_standard(self, openai_service, sample_openai_response):
        """Test streaming request falling back to standard on error"""
        user_id = "test_user"
        user_message = "Hello"
        
        # Mock streaming to fail, standard to succeed
        def side_effect(*args, **kwargs):
            if kwargs.get('stream', False):
                raise Exception("Streaming failed")
            return sample_openai_response
        
        openai_service.client.chat.completions.create.side_effect = side_effect
        
        result = openai_service.get_response(user_id, user_message, use_streaming=True)
        
        assert result['success'] is True
        assert result['streaming'] is False
        assert result['message'] == "Hello! How can I help you today?"
    
    def test_should_send_chunk_logic(self, openai_service):
        """Test streaming chunk sending logic"""
        # Test short text - should not send
        assert openai_service._should_send_chunk("Short text", 5) is False
        
        # Test long text with sentence boundary - should send
        long_text_with_sentence = "This is a longer text that has enough characters and ends with a sentence. And continues here."
        assert openai_service._should_send_chunk(long_text_with_sentence, 10) is True
        
        # Test very long text - should send regardless
        very_long_text = "x" * 500
        assert openai_service._should_send_chunk(very_long_text, 10) is True
        
        # Test accumulated chunks - should send
        medium_text = "x" * 150
        assert openai_service._should_send_chunk(medium_text, 30) is True
    
    def test_test_connection_success(self, openai_service, sample_openai_response):
        """Test successful connection test"""
        openai_service.client.chat.completions.create.return_value = sample_openai_response
        
        result = openai_service.test_connection()
        
        assert result['success'] is True
        assert result['message'] == "Hello! How can I help you today?"
        assert result['tokens_used'] == 50
    
    def test_test_connection_failure(self, openai_service):
        """Test connection test failure"""
        openai_service.client.chat.completions.create.side_effect = Exception("Connection failed")
        
        result = openai_service.test_connection()
        
        assert result['success'] is False
        assert result['error'] == "Connection failed"
    
    def test_system_prompt_content(self, openai_service):
        """Test that system prompt contains expected elements"""
        system_prompt = openai_service.system_prompt
        
        # Check for key characteristics mentioned in the prompt
        assert "Anthony Bourdain" in system_prompt
        assert "conversationalist" in system_prompt
        assert "English and Thai" in system_prompt
        assert "LINE messaging" in system_prompt
        assert "authenticity" in system_prompt
    
    def test_message_preparation(self, openai_service, sample_openai_response):
        """Test proper message formatting for OpenAI API"""
        user_id = "test_user"
        user_message = "Test message"
        
        openai_service.client.chat.completions.create.return_value = sample_openai_response
        
        openai_service.get_response(user_id, user_message, use_streaming=False)
        
        # Verify message structure
        call_args = openai_service.client.chat.completions.create.call_args
        messages = call_args[1]['messages']
        
        # Check system message
        assert messages[0]['role'] == 'system'
        assert len(messages[0]['content']) > 0
        
        # Check user message
        assert messages[-1]['role'] == 'user'
        assert messages[-1]['content'] == user_message
        
        # Check API parameters
        assert call_args[1]['model'] == "gpt-4.1-mini" 
        assert call_args[1]['max_tokens'] == 800
        assert call_args[1]['temperature'] == 0.7
        assert call_args[1]['stream'] is False