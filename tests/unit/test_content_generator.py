"""
Unit tests for ContentGenerator
"""

import pytest
import json
from unittest.mock import Mock, patch, mock_open
from datetime import datetime, time

from src.utils.content_generator import ContentGenerator, ContentRequest, GeneratedContent
from src.models.rich_message_models import ContentCategory, ContentTheme


class TestContentGenerator:
    """Test cases for ContentGenerator"""
    
    @pytest.fixture
    def mock_config(self):
        """Create a mock configuration"""
        config = Mock()
        config.content_generation = Mock()
        config.content_generation.ai_model = "gpt-4.1-nano"
        config.content_generation.max_title_length = 100
        config.content_generation.max_content_length = 1000
        config.content_generation.content_cache_hours = 6
        config.content_generation.default_language = "en"
        return config
    
    @pytest.fixture
    def mock_openai_service(self):
        """Create a mock OpenAI service"""
        service = Mock()
        service.get_response.return_value = {
            'success': True,
            'message': '{"title": "Start Your Day Strong", "content": "Every morning brings new opportunities to achieve greatness. Take the first step today!"}',
            'tokens_used': 45
        }
        return service
    
    @pytest.fixture
    def sample_prompts(self):
        """Create sample content prompts"""
        return {
            "content_prompts": {
                "motivation": {
                    "morning_energy": {
                        "system_prompt": "You are a motivational speaker creating inspiring content.",
                        "user_prompts": [
                            "Create a powerful morning motivation message.",
                            "Write an energizing message about taking action today."
                        ],
                        "style_guidelines": "Use action-oriented language, positive reinforcement."
                    }
                },
                "wellness": {
                    "mindfulness": {
                        "system_prompt": "You are a mindfulness teacher helping people find peace.",
                        "user_prompts": [
                            "Write about the power of taking mindful pauses.",
                            "Create content about finding calm in busy schedules."
                        ],
                        "style_guidelines": "Use calm, soothing language."
                    }
                }
            },
            "prompt_modifiers": {
                "length": {
                    "short": "Keep the message under 150 characters.",
                    "medium": "Create a message between 150-500 characters.",
                    "long": "Develop a comprehensive message up to 1000 characters."
                },
                "tone": {
                    "energetic": "Use dynamic, action-oriented language.",
                    "calm": "Use peaceful, soothing language.",
                    "professional": "Use clear, authoritative language.",
                    "friendly": "Use warm, conversational language."
                },
                "language_specific": {
                    "en": "Use clear, direct English with motivational vocabulary.",
                    "th": "Incorporate Thai cultural values of respect and mindfulness."
                }
            },
            "content_validation": {
                "required_elements": ["positive_tone", "actionable_insight"],
                "avoid": ["negative_language", "controversial_topics"]
            }
        }
    
    @pytest.fixture
    def content_generator(self, mock_openai_service, mock_config, sample_prompts):
        """Create a ContentGenerator instance with mocked dependencies"""
        prompts_json = json.dumps(sample_prompts)
        
        with patch('src.utils.content_generator.get_rich_message_config', return_value=mock_config), \
             patch('builtins.open', mock_open(read_data=prompts_json)):
            
            generator = ContentGenerator(openai_service=mock_openai_service, config=mock_config)
            return generator
    
    def test_initialization(self, content_generator, mock_config, mock_openai_service):
        """Test ContentGenerator initialization"""
        assert content_generator.config == mock_config
        assert content_generator.openai_service == mock_openai_service
        assert content_generator.content_cache == {}
        assert content_generator.content_prompts is not None
    
    def test_load_content_prompts_success(self, mock_config, mock_openai_service, sample_prompts):
        """Test successful content prompts loading"""
        prompts_json = json.dumps(sample_prompts)
        
        with patch('src.utils.content_generator.get_rich_message_config', return_value=mock_config), \
             patch('builtins.open', mock_open(read_data=prompts_json)):
            
            generator = ContentGenerator(openai_service=mock_openai_service, config=mock_config)
            
            assert generator.content_prompts == sample_prompts
    
    def test_load_content_prompts_file_error(self, mock_config, mock_openai_service):
        """Test content prompts loading with file error"""
        with patch('src.utils.content_generator.get_rich_message_config', return_value=mock_config), \
             patch('builtins.open', side_effect=FileNotFoundError()):
            
            generator = ContentGenerator(openai_service=mock_openai_service, config=mock_config)
            
            # Should have fallback prompts
            assert "content_prompts" in generator.content_prompts
    
    def test_cache_key_generation(self, content_generator):
        """Test cache key generation"""
        request = ContentRequest(
            category=ContentCategory.MOTIVATION,
            theme=ContentTheme.MORNING_ENERGY,
            length="medium",
            tone="energetic",
            language="en",
            energy_level="high"
        )
        
        cache_key = content_generator._get_cache_key(request)
        
        assert isinstance(cache_key, str)
        assert len(cache_key) == 32  # MD5 hash length
    
    def test_select_prompt_template_specific_theme(self, content_generator):
        """Test selecting prompt template for specific theme"""
        request = ContentRequest(
            category=ContentCategory.MOTIVATION,
            theme=ContentTheme.MORNING_ENERGY
        )
        
        template = content_generator._select_prompt_template(request)
        
        assert "system_prompt" in template
        assert "motivational speaker" in template["system_prompt"].lower()
    
    def test_select_prompt_template_fallback(self, content_generator):
        """Test prompt template selection with fallback"""
        request = ContentRequest(
            category=ContentCategory.PRODUCTIVITY,  # Not in sample prompts
            theme=None
        )
        
        template = content_generator._select_prompt_template(request)
        
        assert "system_prompt" in template
        assert "user_prompts" in template
    
    def test_build_generation_prompt(self, content_generator):
        """Test building generation prompts"""
        request = ContentRequest(
            category=ContentCategory.MOTIVATION,
            theme=ContentTheme.MORNING_ENERGY,
            length="medium",
            tone="energetic",
            language="en",
            time_context=time(8, 0),
            energy_level="high"
        )
        
        template = content_generator._select_prompt_template(request)
        system_prompt, user_prompt = content_generator._build_generation_prompt(request, template)
        
        assert isinstance(system_prompt, str)
        assert isinstance(user_prompt, str)
        assert "motivational speaker" in system_prompt.lower()
        assert "morning" in user_prompt.lower()
        assert "JSON format" in user_prompt
    
    def test_validate_generated_content_success(self, content_generator):
        """Test successful content validation"""
        content_dict = {
            "title": "Start Your Day Strong",
            "content": "Every morning brings new opportunities to achieve greatness."
        }
        
        request = ContentRequest(category=ContentCategory.MOTIVATION)
        is_valid = content_generator._validate_generated_content(content_dict, request)
        
        assert is_valid is True
    
    def test_validate_generated_content_missing_fields(self, content_generator):
        """Test content validation with missing fields"""
        content_dict = {
            "title": "Start Your Day Strong"
            # Missing "content" field
        }
        
        request = ContentRequest(category=ContentCategory.MOTIVATION)
        is_valid = content_generator._validate_generated_content(content_dict, request)
        
        assert is_valid is False
    
    def test_validate_generated_content_too_long(self, content_generator):
        """Test content validation with oversized content"""
        content_dict = {
            "title": "x" * 150,  # Exceeds max_title_length of 100
            "content": "Valid content"
        }
        
        request = ContentRequest(category=ContentCategory.MOTIVATION)
        is_valid = content_generator._validate_generated_content(content_dict, request)
        
        assert is_valid is False
    
    def test_validate_generated_content_empty(self, content_generator):
        """Test content validation with empty content"""
        content_dict = {
            "title": "",
            "content": ""
        }
        
        request = ContentRequest(category=ContentCategory.MOTIVATION)
        is_valid = content_generator._validate_generated_content(content_dict, request)
        
        assert is_valid is False
    
    def test_generate_content_success(self, content_generator):
        """Test successful content generation"""
        request = ContentRequest(
            category=ContentCategory.MOTIVATION,
            theme=ContentTheme.MORNING_ENERGY,
            language="en"
        )
        
        generated_content = content_generator.generate_content(request)
        
        assert generated_content is not None
        assert isinstance(generated_content, GeneratedContent)
        assert generated_content.title == "Start Your Day Strong"
        assert "opportunities" in generated_content.content
        assert generated_content.category == ContentCategory.MOTIVATION
    
    def test_generate_content_no_openai_service(self, mock_config, sample_prompts):
        """Test content generation without OpenAI service"""
        prompts_json = json.dumps(sample_prompts)
        
        with patch('src.utils.content_generator.get_rich_message_config', return_value=mock_config), \
             patch('builtins.open', mock_open(read_data=prompts_json)):
            
            generator = ContentGenerator(openai_service=None, config=mock_config)
            
            request = ContentRequest(category=ContentCategory.MOTIVATION)
            generated_content = generator.generate_content(request)
            
            assert generated_content is None
    
    def test_generate_content_ai_failure(self, content_generator):
        """Test content generation with AI failure"""
        # Mock AI service failure
        content_generator.openai_service.get_response.return_value = {
            'success': False,
            'error': 'API timeout'
        }
        
        request = ContentRequest(category=ContentCategory.MOTIVATION)
        generated_content = content_generator.generate_content(request)
        
        assert generated_content is None
    
    def test_generate_content_invalid_json(self, content_generator):
        """Test content generation with invalid JSON response"""
        # Mock invalid JSON response
        content_generator.openai_service.get_response.return_value = {
            'success': True,
            'message': 'This is not valid JSON content',
            'tokens_used': 30
        }
        
        request = ContentRequest(category=ContentCategory.MOTIVATION)
        generated_content = content_generator.generate_content(request)
        
        # Should still work with fallback text extraction
        assert generated_content is not None
        assert generated_content.title == "This is not valid JSON content"
    
    def test_generate_content_with_json_markers(self, content_generator):
        """Test content generation with JSON code block markers"""
        # Mock response with JSON markers
        json_response = '```json\\n{"title": "Test Title", "content": "Test content"}\\n```'
        content_generator.openai_service.get_response.return_value = {
            'success': True,
            'message': json_response,
            'tokens_used': 40
        }
        
        request = ContentRequest(category=ContentCategory.MOTIVATION)
        generated_content = content_generator.generate_content(request)
        
        assert generated_content is not None
        assert generated_content.title == "Test Title"
        assert generated_content.content == "Test content"
    
    def test_generate_content_caching(self, content_generator):
        """Test content caching functionality"""
        request = ContentRequest(
            category=ContentCategory.MOTIVATION,
            language="en"
        )
        
        # First generation should cache
        content1 = content_generator.generate_content(request)
        assert len(content_generator.content_cache) == 1
        
        # Second generation should use cache
        content2 = content_generator.generate_content(request)
        assert content1 is content2  # Should be same object from cache
    
    def test_generate_content_cache_disabled(self, content_generator):
        """Test content generation with caching disabled"""
        request = ContentRequest(category=ContentCategory.MOTIVATION)
        
        # Generate with caching disabled
        content = content_generator.generate_content(request, use_cache=False)
        
        assert content is not None
        assert len(content_generator.content_cache) == 0  # Should not cache
    
    def test_generate_daily_content_morning(self, content_generator):
        """Test daily content generation for morning"""
        morning_time = time(8, 0)
        
        content = content_generator.generate_daily_content(
            ContentCategory.MOTIVATION,
            morning_time,
            "en"
        )
        
        assert content is not None
        assert content.metadata["generation_params"]["time_context"] == "08:00"
    
    def test_generate_daily_content_evening(self, content_generator):
        """Test daily content generation for evening"""
        evening_time = time(19, 0)
        
        content = content_generator.generate_daily_content(
            ContentCategory.WELLNESS,
            evening_time,
            "en"
        )
        
        assert content is not None
        assert content.metadata["generation_params"]["time_context"] == "19:00"
    
    def test_generate_daily_content_default_time(self, content_generator):
        """Test daily content generation with default time"""
        content = content_generator.generate_daily_content(ContentCategory.MOTIVATION)
        
        assert content is not None
        assert "time_context" in content.metadata["generation_params"]
    
    def test_generate_content_variations(self, content_generator):
        """Test generating multiple content variations"""
        request = ContentRequest(category=ContentCategory.MOTIVATION)
        
        variations = content_generator.generate_content_variations(request, count=3)
        
        assert len(variations) == 3
        assert all(isinstance(content, GeneratedContent) for content in variations)
        
        # Variations should be different (different custom_context)
        contexts = [v.metadata["generation_params"].get("custom_context") for v in variations]
        assert len(set(contexts)) == 3  # All different
    
    def test_clear_cache(self, content_generator):
        """Test cache clearing"""
        # Add something to cache
        request = ContentRequest(category=ContentCategory.MOTIVATION)
        content_generator.generate_content(request)
        assert len(content_generator.content_cache) > 0
        
        # Clear cache
        content_generator.clear_cache()
        assert len(content_generator.content_cache) == 0
    
    def test_get_cache_stats(self, content_generator):
        """Test cache statistics"""
        stats = content_generator.get_cache_stats()
        
        assert "cached_items" in stats
        assert "cache_enabled" in stats
        assert "total_generations" in stats
        assert stats["cache_enabled"] is True
    
    def test_validate_content_quality_excellent(self, content_generator):
        """Test content quality validation for excellent content"""
        content = GeneratedContent(
            title="Embrace Today's Possibilities",
            content="Every sunrise brings new opportunities to grow, learn, and make a positive impact. Take action today with confidence and determination.",
            language="en",
            category=ContentCategory.MOTIVATION,
            theme=ContentTheme.MORNING_ENERGY,
            metadata={},
            generation_time=datetime.now()
        )
        
        quality_result = content_generator.validate_content_quality(content)
        
        assert quality_result["quality_score"] >= 90
        assert quality_result["quality_level"] == "excellent"
        assert "content_stats" in quality_result
    
    def test_validate_content_quality_poor(self, content_generator):
        """Test content quality validation for poor content"""
        content = GeneratedContent(
            title="Hi",  # Too short
            content="Yes.",  # Too short
            language="en",
            category=ContentCategory.MOTIVATION,
            theme=ContentTheme.MORNING_ENERGY,
            metadata={},
            generation_time=datetime.now()
        )
        
        quality_result = content_generator.validate_content_quality(content)
        
        assert quality_result["quality_score"] < 75
        assert quality_result["quality_level"] == "needs_improvement"
        assert len(quality_result["issues"]) > 0
        assert len(quality_result["recommendations"]) > 0
    
    def test_cache_validity_check(self, content_generator):
        """Test cache validity checking"""
        # Create content with recent generation time
        recent_content = GeneratedContent(
            title="Test",
            content="Test content",
            language="en",
            category=ContentCategory.MOTIVATION,
            theme=None,
            metadata={},
            generation_time=datetime.now()  # Very recent
        )
        
        assert content_generator._is_cache_valid(recent_content) is True
        
        # Create content with old generation time
        old_content = GeneratedContent(
            title="Test",
            content="Test content", 
            language="en",
            category=ContentCategory.MOTIVATION,
            theme=None,
            metadata={},
            generation_time=datetime(2020, 1, 1)  # Very old
        )
        
        assert content_generator._is_cache_valid(old_content) is False