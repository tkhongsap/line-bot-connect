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
        
        # Verify only recent messages are sent to API (last 100 messages)
        call_args = openai_service.client.chat.completions.create.call_args
        messages = call_args[1]['messages']
        
        # System prompt + up to 100 recent messages + current message
        assert len(messages) <= 102
    
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
        
        # Test long text with sentence boundary and newline - should send
        long_text_with_sentence = "x" * 150 + "This is a longer text that ends with a sentence.\nAnd continues here."
        assert openai_service._should_send_chunk(long_text_with_sentence, 10) is True
        
        # Test very long text - should send regardless
        very_long_text = "x" * 500
        assert openai_service._should_send_chunk(very_long_text, 10) is True
        
        # Test accumulated chunks at boundary - should send
        medium_text = "x" * 100
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
        assert "conversationalist" in system_prompt
        assert "English and Thai" in system_prompt
        assert "web search" in system_prompt.lower()
        assert "authentic" in system_prompt
    
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
    
    def test_web_search_rate_limiting(self, openai_service):
        """Test web search rate limiting functionality"""
        user_id = "test_user"
        
        # User should be able to search initially
        assert openai_service._can_user_search(user_id) is True
        
        # Simulate reaching the rate limit (10 searches per hour)
        for i in range(10):
            openai_service._increment_search_count(user_id)
        
        # User should be rate limited now
        assert openai_service._can_user_search(user_id) is False
        
        # Check that rate limit data is stored correctly
        assert user_id in openai_service.search_rate_limits
        assert openai_service.search_rate_limits[user_id]["count"] == 10
    
    def test_web_search_cache_functionality(self, openai_service):
        """Test web search result caching"""
        query = "What's the weather today?"
        cache_key = openai_service._get_cache_key(query)
        
        # Cache should be empty initially
        assert cache_key not in openai_service.search_cache
        
        # Simulate adding to cache
        import time
        openai_service.search_cache[cache_key] = {
            "result": "It's sunny today",
            "timestamp": time.time()
        }
        
        # Should find cached result
        assert cache_key in openai_service.search_cache
        
        # Test cache cleanup
        # Add expired entry
        expired_key = "expired_query"
        openai_service.search_cache[expired_key] = {
            "result": "Old result",
            "timestamp": time.time() - (16 * 60)  # 16 minutes ago (expired)
        }
        
        openai_service._cleanup_search_cache()
        
        # Expired entry should be removed
        assert expired_key not in openai_service.search_cache
        # Current entry should remain
        assert cache_key in openai_service.search_cache
    
    def test_web_search_tool_integration(self, openai_service, sample_openai_response):
        """Test that web search tool is included when user is within limits"""
        user_id = "test_user"
        user_message = "What's the latest news?"
        
        # Mock the OpenAI client response
        openai_service.client.chat.completions.create.return_value = sample_openai_response
        
        result = openai_service.get_response(user_id, user_message, use_streaming=False)
        
        assert result['success'] is True
        
        # Verify the API was called with web search tools
        call_args = openai_service.client.chat.completions.create.call_args
        tools = call_args[1].get('tools')
        
        # Should include web search tool
        assert tools is not None
        assert len(tools) == 1
        assert tools[0]["type"] == "web_search"
        
        # Verify search count was incremented
        assert user_id in openai_service.search_rate_limits
        assert openai_service.search_rate_limits[user_id]["count"] == 1
    
    def test_web_search_rate_limit_prevents_tool_usage(self, openai_service, sample_openai_response):
        """Test that web search tool is not included when user exceeds rate limit"""
        user_id = "test_user"
        user_message = "What's the latest news?"
        
        # Exhaust the rate limit
        for i in range(10):
            openai_service._increment_search_count(user_id)
        
        # Mock the OpenAI client response
        openai_service.client.chat.completions.create.return_value = sample_openai_response
        
        result = openai_service.get_response(user_id, user_message, use_streaming=False)
        
        assert result['success'] is True
        
        # Verify the API was called without web search tools
        call_args = openai_service.client.chat.completions.create.call_args
        tools = call_args[1].get('tools')
        
        # Should not include web search tool due to rate limiting
        assert tools is None
    
    def test_system_prompt_includes_web_search_instructions(self, openai_service):
        """Test that system prompt includes web search and language matching instructions"""
        system_prompt = openai_service.system_prompt
        
        # Check for web search instructions
        assert "web search" in system_prompt.lower()
        assert "current events" in system_prompt.lower()
        assert "real-time information" in system_prompt.lower()
        
        # Check for language matching instructions
        assert "EXACT same language" in system_prompt
        assert "respond in Thai" in system_prompt
        assert "respond in English" in system_prompt
        
        # Check for rate about sources
        assert "sources" in system_prompt.lower()
    
    def test_conversation_history_extended_limit(self, openai_service, sample_openai_response):
        """Test that conversation history supports up to 100 messages"""
        user_id = "test_user"
        
        # Add 50 exchanges (100 messages total) to conversation history
        for i in range(50):
            openai_service.conversation_service.add_message(user_id, "user", f"User message {i}")
            openai_service.conversation_service.add_message(user_id, "assistant", f"Assistant response {i}")
        
        # Mock the OpenAI client response
        openai_service.client.chat.completions.create.return_value = sample_openai_response
        
        result = openai_service.get_response(user_id, "Test message", use_streaming=False)
        
        assert result['success'] is True
        
        # Verify that all 100 messages were included in the API call
        call_args = openai_service.client.chat.completions.create.call_args
        messages = call_args[1]['messages']
        
        # Should include: system prompt + 100 conversation messages + current message = 102 total
        assert len(messages) == 102
        assert messages[0]['role'] == 'system'
        assert messages[-1]['role'] == 'user'
        assert messages[-1]['content'] == "Test message"