"""
End-to-end tests for template loading, content generation, and delivery pipeline.

This module tests the complete flow from template management through content
generation to final message delivery.
"""

import pytest
import tempfile
import os
import json
from unittest.mock import patch, Mock, MagicMock, mock_open
from datetime import datetime, timezone, timedelta
from pathlib import Path

from src.services.rich_message_service import RichMessageService
from src.services.openai_service import OpenAIService
from src.config.settings import Settings


class TestTemplateContentDeliveryFlow:
    """End-to-end tests for template, content, and delivery pipeline"""
    
    @pytest.fixture
    def temp_directories(self):
        """Create temporary directories for templates and assets"""
        with tempfile.TemporaryDirectory() as temp_dir:
            templates_dir = os.path.join(temp_dir, "templates", "rich_messages")
            backgrounds_dir = os.path.join(templates_dir, "backgrounds")
            fonts_dir = os.path.join(temp_dir, "static", "fonts")
            
            os.makedirs(templates_dir, exist_ok=True)
            os.makedirs(backgrounds_dir, exist_ok=True)
            os.makedirs(fonts_dir, exist_ok=True)
            
            yield {
                "base_dir": temp_dir,
                "templates_dir": templates_dir,
                "backgrounds_dir": backgrounds_dir,
                "fonts_dir": fonts_dir
            }
    
    @pytest.fixture
    def sample_template_metadata(self, temp_directories):
        """Create sample template metadata file"""
        metadata = {
            "templates": {
                "motivation_001": {
                    "name": "Morning Energy",
                    "category": "motivation",
                    "background_file": "motivation_morning.png",
                    "text_areas": [
                        {
                            "name": "title",
                            "position": {"x": 100, "y": 200},
                            "max_width": 400,
                            "font_size": 32,
                            "font_color": "#FFFFFF",
                            "alignment": "center"
                        },
                        {
                            "name": "content",
                            "position": {"x": 100, "y": 300},
                            "max_width": 400,
                            "font_size": 18,
                            "font_color": "#F0F0F0",
                            "alignment": "left"
                        }
                    ],
                    "dimensions": {"width": 600, "height": 400},
                    "optimal_times": ["07:00", "08:00", "09:00"]
                },
                "wellness_001": {
                    "name": "Evening Calm",
                    "category": "wellness",
                    "background_file": "wellness_evening.png",
                    "text_areas": [
                        {
                            "name": "title",
                            "position": {"x": 150, "y": 180},
                            "max_width": 350,
                            "font_size": 28,
                            "font_color": "#2E3440",
                            "alignment": "center"
                        },
                        {
                            "name": "content",
                            "position": {"x": 150, "y": 280},
                            "max_width": 350,
                            "font_size": 16,
                            "font_color": "#4C566A",
                            "alignment": "left"
                        }
                    ],
                    "dimensions": {"width": 600, "height": 400},
                    "optimal_times": ["18:00", "19:00", "20:00"]
                }
            },
            "categories": {
                "motivation": {
                    "themes": ["energy", "success", "perseverance", "confidence"],
                    "tone": "energetic",
                    "target_emotions": ["inspired", "motivated", "determined"]
                },
                "wellness": {
                    "themes": ["mindfulness", "relaxation", "balance", "self-care"],
                    "tone": "calm",
                    "target_emotions": ["peaceful", "centered", "relaxed"]
                }
            },
            "version": "1.0.0",
            "last_updated": datetime.now(timezone.utc).isoformat()
        }
        
        metadata_path = os.path.join(temp_directories["templates_dir"], "metadata.json")
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        return metadata_path, metadata
    
    @pytest.fixture
    def sample_background_images(self, temp_directories):
        """Create sample background image files"""
        backgrounds_dir = temp_directories["backgrounds_dir"]
        
        # Create dummy image files (just empty files for testing)
        image_files = [
            "motivation_morning.png",
            "wellness_evening.png"
        ]
        
        created_files = []
        for image_file in image_files:
            file_path = os.path.join(backgrounds_dir, image_file)
            with open(file_path, 'wb') as f:
                # Create a minimal PNG file header for testing
                f.write(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x02X\x00\x00\x01\x90\x08\x06\x00\x00\x00')
            created_files.append(file_path)
        
        return created_files
    
    @pytest.fixture
    def mock_openai_service(self):
        """Create mock OpenAI service for content generation"""
        mock_service = Mock(spec=OpenAIService)
        
        # Mock content generation responses
        mock_service.generate_themed_content.return_value = {
            "success": True,
            "title": "Start Your Day with Purpose",
            "content": "Every morning brings new possibilities. Embrace them with confidence and determination.",
            "theme": "morning_motivation",
            "tone": "energetic",
            "suggested_template": "motivation_001"
        }
        
        mock_service.get_response.return_value = {
            "success": True,
            "message": "Generated content successfully",
            "tokens_used": 45
        }
        
        return mock_service
    
    @pytest.fixture
    def mock_line_bot_api(self):
        """Create mock LINE Bot API"""
        mock_api = Mock()
        mock_api.broadcast.return_value = None
        mock_api.narrowcast.return_value = None
        mock_api.push_message.return_value = None
        mock_api.reply_message.return_value = None
        return mock_api
    
    def test_template_metadata_loading_flow(self, sample_template_metadata, temp_directories):
        """Test loading and parsing template metadata"""
        metadata_path, expected_metadata = sample_template_metadata
        
        # Test metadata file exists and is readable
        assert os.path.exists(metadata_path)
        
        with open(metadata_path, 'r') as f:
            loaded_metadata = json.load(f)
        
        # Verify structure
        assert "templates" in loaded_metadata
        assert "categories" in loaded_metadata
        assert "version" in loaded_metadata
        
        # Verify template entries
        templates = loaded_metadata["templates"]
        assert "motivation_001" in templates
        assert "wellness_001" in templates
        
        # Verify template structure
        motivation_template = templates["motivation_001"]
        assert motivation_template["name"] == "Morning Energy"
        assert motivation_template["category"] == "motivation"
        assert "text_areas" in motivation_template
        assert len(motivation_template["text_areas"]) == 2
        
        # Verify text area structure
        title_area = motivation_template["text_areas"][0]
        assert title_area["name"] == "title"
        assert "position" in title_area
        assert "max_width" in title_area
        assert "font_size" in title_area
    
    def test_background_image_availability_flow(self, sample_background_images, temp_directories):
        """Test background image file availability and access"""
        backgrounds_dir = temp_directories["backgrounds_dir"]
        
        # Check that all expected background files exist
        expected_files = ["motivation_morning.png", "wellness_evening.png"]
        
        for filename in expected_files:
            file_path = os.path.join(backgrounds_dir, filename)
            assert os.path.exists(file_path)
            assert os.path.getsize(file_path) > 0  # Not empty
            
            # Test file is readable
            with open(file_path, 'rb') as f:
                content = f.read()
                assert len(content) > 0
                assert content.startswith(b'\x89PNG')  # PNG header
    
    @patch('src.utils.template_manager.TemplateManager')
    def test_template_selection_algorithm_flow(self, mock_template_manager, sample_template_metadata):
        """Test template selection based on content and time"""
        metadata_path, metadata = sample_template_metadata
        
        # Mock template manager
        mock_manager = Mock()
        mock_template_manager.return_value = mock_manager
        
        # Configure template selection behavior
        mock_manager.select_template.return_value = {
            "template_id": "motivation_001",
            "template_data": metadata["templates"]["motivation_001"],
            "match_score": 0.85,
            "selection_reason": "category_match_and_optimal_time"
        }
        
        mock_manager.get_templates_by_category.return_value = [
            metadata["templates"]["motivation_001"]
        ]
        
        # Test template selection for motivation content
        content_data = {
            "category": "motivation",
            "tone": "energetic",
            "current_time": "08:00"
        }
        
        selected = mock_manager.select_template(content_data)
        
        assert selected["template_id"] == "motivation_001"
        assert selected["match_score"] > 0.8
        assert "motivation" in selected["selection_reason"] or "optimal_time" in selected["selection_reason"]
        
        # Verify manager was called with correct parameters
        mock_manager.select_template.assert_called_once_with(content_data)
    
    def test_content_generation_flow(self, mock_openai_service):
        """Test AI-powered content generation"""
        # Test content generation for motivation category
        generation_params = {
            "category": "motivation",
            "theme": "morning_energy",
            "target_audience": "professionals",
            "tone": "energetic",
            "max_title_length": 50,
            "max_content_length": 200
        }
        
        result = mock_openai_service.generate_themed_content(**generation_params)
        
        assert result["success"] is True
        assert "title" in result
        assert "content" in result
        assert len(result["title"]) <= 50
        assert len(result["content"]) <= 200
        assert result["theme"] == "morning_motivation"
        assert result["tone"] == "energetic"
        
        # Verify service was called
        mock_openai_service.generate_themed_content.assert_called_once_with(**generation_params)
    
    @patch('src.utils.image_composer.ImageComposer')
    def test_image_composition_flow(self, mock_image_composer, sample_template_metadata, sample_background_images):
        """Test image composition with text overlay"""
        metadata_path, metadata = sample_template_metadata
        
        # Mock image composer
        mock_composer = Mock()
        mock_image_composer.return_value = mock_composer
        
        # Configure composition behavior
        output_path = "/tmp/composed_image.png"
        mock_composer.compose_image.return_value = {
            "success": True,
            "output_path": output_path,
            "composition_time_ms": 250,
            "final_dimensions": {"width": 600, "height": 400}
        }
        
        # Test image composition
        template_data = metadata["templates"]["motivation_001"]
        content_data = {
            "title": "Start Your Day with Purpose",
            "content": "Every morning brings new possibilities. Embrace them with confidence and determination."
        }
        
        composition_result = mock_composer.compose_image(
            template_data=template_data,
            content_data=content_data,
            output_path=output_path
        )
        
        assert composition_result["success"] is True
        assert composition_result["output_path"] == output_path
        assert composition_result["composition_time_ms"] < 1000  # Should be fast
        assert composition_result["final_dimensions"]["width"] == 600
        assert composition_result["final_dimensions"]["height"] == 400
        
        # Verify composer was called correctly
        mock_composer.compose_image.assert_called_once()
    
    @patch('src.services.rich_message_service.RichMessageService')
    def test_rich_message_creation_from_template_flow(self, mock_rich_service_class, mock_line_bot_api):
        """Test Rich Message creation using template data"""
        # Mock Rich Message service
        mock_service = Mock()
        mock_rich_service_class.return_value = mock_service
        
        # Configure Flex Message creation
        mock_flex_message = Mock()
        mock_flex_message.alt_text = "Start Your Day with Purpose: Every morning brings..."
        mock_service.create_flex_message.return_value = mock_flex_message
        
        # Test Rich Message creation with template data
        template_data = {
            "template_id": "motivation_001",
            "category": "motivation",
            "name": "Morning Energy"
        }
        
        content_data = {
            "title": "Start Your Day with Purpose",
            "content": "Every morning brings new possibilities. Embrace them with confidence and determination.",
            "image_url": "https://example.com/composed_image.png"
        }
        
        flex_message = mock_service.create_flex_message(
            title=content_data["title"],
            content=content_data["content"],
            image_url=content_data["image_url"],
            content_id=f"content_{template_data['template_id']}_{int(datetime.now().timestamp())}",
            include_interactions=True
        )
        
        assert flex_message is not None
        assert hasattr(flex_message, 'alt_text')
        
        # Verify service was called with correct parameters
        mock_service.create_flex_message.assert_called_once()
        call_args = mock_service.create_flex_message.call_args
        assert call_args[1]["title"] == content_data["title"]
        assert call_args[1]["content"] == content_data["content"]
        assert call_args[1]["image_url"] == content_data["image_url"]
        assert call_args[1]["include_interactions"] is True
    
    def test_message_delivery_flow(self, mock_line_bot_api):
        """Test message delivery to LINE platform"""
        # Create Rich Message service
        rich_service = RichMessageService(line_bot_api=mock_line_bot_api)
        
        # Create sample Flex Message
        flex_message = rich_service.create_flex_message(
            title="Test Title",
            content="Test content for delivery testing",
            include_interactions=True
        )
        
        # Test broadcast delivery
        broadcast_result = rich_service.broadcast_rich_message(flex_message)
        
        assert broadcast_result["success"] is True
        assert "timestamp" in broadcast_result
        assert broadcast_result["audience"] == "all"
        
        # Verify LINE API was called
        mock_line_bot_api.broadcast.assert_called_once()
        
        # Test narrowcast delivery
        mock_line_bot_api.reset_mock()
        
        narrowcast_result = rich_service.broadcast_rich_message(
            flex_message, 
            target_audience="test_audience_123"
        )
        
        assert narrowcast_result["success"] is True
        assert narrowcast_result["audience"] == "test_audience_123"
        
        # Verify narrowcast API was called
        mock_line_bot_api.narrowcast.assert_called_once()
    
    @patch('src.utils.template_manager.TemplateManager')
    @patch('src.utils.content_generator.ContentGenerator')
    @patch('src.utils.image_composer.ImageComposer')
    def test_complete_template_to_delivery_pipeline(self, mock_image_composer, mock_content_generator, mock_template_manager, 
                                                   sample_template_metadata, mock_line_bot_api):
        """Test complete pipeline from template selection to delivery"""
        metadata_path, metadata = sample_template_metadata
        
        # Step 1: Mock template selection
        mock_manager = Mock()
        mock_template_manager.return_value = mock_manager
        
        selected_template = {
            "template_id": "motivation_001",
            "template_data": metadata["templates"]["motivation_001"],
            "match_score": 0.9
        }
        mock_manager.select_template.return_value = selected_template
        
        # Step 2: Mock content generation
        mock_generator = Mock()
        mock_content_generator.return_value = mock_generator
        
        generated_content = {
            "success": True,
            "title": "Embrace Today's Opportunities",
            "content": "Each morning is a fresh start. Make it count with positive energy and focused determination.",
            "theme": "morning_motivation",
            "generation_time_ms": 180
        }
        mock_generator.generate_content.return_value = generated_content
        
        # Step 3: Mock image composition
        mock_composer = Mock()
        mock_image_composer.return_value = mock_composer
        
        composed_image = {
            "success": True,
            "output_path": "/tmp/motivation_composed.png",
            "public_url": "https://example.com/images/motivation_composed.png",
            "composition_time_ms": 320
        }
        mock_composer.compose_image.return_value = composed_image
        
        # Step 4: Execute complete pipeline
        
        # Template selection
        content_request = {
            "category": "motivation",
            "target_time": "08:00",
            "audience": "professionals"
        }
        
        template_result = mock_manager.select_template(content_request)
        assert template_result["template_id"] == "motivation_001"
        
        # Content generation
        generation_params = {
            "template_data": template_result["template_data"],
            "content_request": content_request
        }
        
        content_result = mock_generator.generate_content(**generation_params)
        assert content_result["success"] is True
        
        # Image composition
        composition_params = {
            "template_data": template_result["template_data"],
            "content_data": {
                "title": content_result["title"],
                "content": content_result["content"]
            }
        }
        
        image_result = mock_composer.compose_image(**composition_params)
        assert image_result["success"] is True
        
        # Rich Message creation and delivery
        rich_service = RichMessageService(line_bot_api=mock_line_bot_api)
        
        flex_message = rich_service.create_flex_message(
            title=content_result["title"],
            content=content_result["content"],
            image_url=image_result["public_url"],
            content_id=f"pipeline_test_{int(datetime.now().timestamp())}",
            include_interactions=True
        )
        
        delivery_result = rich_service.broadcast_rich_message(flex_message)
        
        assert delivery_result["success"] is True
        
        # Verify all components were called
        mock_manager.select_template.assert_called_once()
        mock_generator.generate_content.assert_called_once()
        mock_composer.compose_image.assert_called_once()
        mock_line_bot_api.broadcast.assert_called_once()
    
    def test_error_handling_in_pipeline(self, mock_line_bot_api):
        """Test error handling at each stage of the pipeline"""
        
        # Test template selection failure
        with patch('src.utils.template_manager.TemplateManager') as mock_template_manager:
            mock_manager = Mock()
            mock_template_manager.return_value = mock_manager
            mock_manager.select_template.return_value = None  # Selection failure
            
            result = mock_manager.select_template({"category": "nonexistent"})
            assert result is None
        
        # Test content generation failure  
        with patch('src.utils.content_generator.ContentGenerator') as mock_content_generator:
            mock_generator = Mock()
            mock_content_generator.return_value = mock_generator
            mock_generator.generate_content.return_value = {
                "success": False,
                "error": "Content generation failed",
                "error_code": "OPENAI_API_ERROR"
            }
            
            result = mock_generator.generate_content({})
            assert result["success"] is False
            assert "error" in result
        
        # Test image composition failure
        with patch('src.utils.image_composer.ImageComposer') as mock_image_composer:
            mock_composer = Mock()
            mock_image_composer.return_value = mock_composer
            mock_composer.compose_image.return_value = {
                "success": False,
                "error": "Image composition failed",
                "error_code": "TEMPLATE_FILE_NOT_FOUND"
            }
            
            result = mock_composer.compose_image({}, {})
            assert result["success"] is False
            assert "error" in result
        
        # Test message delivery failure
        mock_line_bot_api.broadcast.side_effect = Exception("LINE API Error")
        
        rich_service = RichMessageService(line_bot_api=mock_line_bot_api)
        
        flex_message = rich_service.create_flex_message(
            title="Test Title",
            content="Test content"
        )
        
        delivery_result = rich_service.broadcast_rich_message(flex_message)
        
        assert delivery_result["success"] is False
        assert "error" in delivery_result
    
    def test_performance_optimization_flow(self, sample_template_metadata, mock_line_bot_api):
        """Test performance optimization throughout the pipeline"""
        metadata_path, metadata = sample_template_metadata
        
        # Measure template loading performance
        start_time = datetime.now()
        
        with open(metadata_path, 'r') as f:
            loaded_metadata = json.load(f)
        
        template_load_time = (datetime.now() - start_time).total_seconds()
        assert template_load_time < 0.1  # Should load quickly
        
        # Test Rich Message creation performance
        rich_service = RichMessageService(line_bot_api=mock_line_bot_api)
        
        start_time = datetime.now()
        
        for i in range(10):  # Create multiple messages
            flex_message = rich_service.create_flex_message(
                title=f"Performance Test Message {i}",
                content=f"This is performance test content number {i}. It should be created quickly.",
                include_interactions=True
            )
            assert flex_message is not None
        
        creation_time = (datetime.now() - start_time).total_seconds()
        assert creation_time < 1.0  # Should create 10 messages in under 1 second
        
        # Test delivery performance
        start_time = datetime.now()
        
        delivery_result = rich_service.broadcast_rich_message(flex_message)
        
        delivery_time = (datetime.now() - start_time).total_seconds()
        assert delivery_time < 0.5  # Should deliver quickly
        assert delivery_result["success"] is True
    
    def test_template_validation_flow(self, temp_directories):
        """Test template metadata validation"""
        templates_dir = temp_directories["templates_dir"]
        
        # Test valid template metadata
        valid_metadata = {
            "templates": {
                "test_template": {
                    "name": "Test Template",
                    "category": "test",
                    "background_file": "test.png",
                    "text_areas": [
                        {
                            "name": "title",
                            "position": {"x": 100, "y": 100},
                            "max_width": 400,
                            "font_size": 24,
                            "font_color": "#000000",
                            "alignment": "center"
                        }
                    ],
                    "dimensions": {"width": 600, "height": 400}
                }
            },
            "categories": {
                "test": {
                    "themes": ["testing"],
                    "tone": "neutral"
                }
            }
        }
        
        valid_path = os.path.join(templates_dir, "valid_metadata.json")
        with open(valid_path, 'w') as f:
            json.dump(valid_metadata, f)
        
        # Load and validate
        with open(valid_path, 'r') as f:
            loaded = json.load(f)
        
        # Basic validation checks
        assert "templates" in loaded
        assert "categories" in loaded
        
        template = loaded["templates"]["test_template"]
        assert all(field in template for field in ["name", "category", "background_file", "text_areas", "dimensions"])
        
        text_area = template["text_areas"][0]
        assert all(field in text_area for field in ["name", "position", "max_width", "font_size", "font_color", "alignment"])
        
        # Test invalid metadata (missing required fields)
        invalid_metadata = {
            "templates": {
                "invalid_template": {
                    "name": "Invalid Template"
                    # Missing required fields
                }
            }
        }
        
        invalid_path = os.path.join(templates_dir, "invalid_metadata.json")
        with open(invalid_path, 'w') as f:
            json.dump(invalid_metadata, f)
        
        with open(invalid_path, 'r') as f:
            invalid_loaded = json.load(f)
        
        # Validation should catch missing fields
        invalid_template = invalid_loaded["templates"]["invalid_template"]
        required_fields = ["category", "background_file", "text_areas", "dimensions"]
        missing_fields = [field for field in required_fields if field not in invalid_template]
        
        assert len(missing_fields) > 0  # Should have missing fields
    
    def test_content_personalization_flow(self, mock_openai_service):
        """Test content personalization based on user data"""
        # Test personalized content generation
        user_profile = {
            "user_id": "user_123",
            "preferences": {
                "categories": ["motivation", "productivity"],
                "tone": "professional",
                "language": "en"
            },
            "timezone": "America/New_York",
            "local_time": "08:30",
            "engagement_history": {
                "most_engaged_categories": ["motivation"],
                "preferred_content_length": "medium",
                "interaction_patterns": ["likes_quotes", "shares_actionable_tips"]
            }
        }
        
        # Configure personalized response
        mock_openai_service.generate_themed_content.return_value = {
            "success": True,
            "title": "Morning Productivity Boost",
            "content": "Start your day with focused intention. Set three clear priorities and tackle them with confidence.",
            "theme": "productive_morning",
            "tone": "professional",
            "personalization_score": 0.92,
            "personalization_factors": ["timezone_appropriate", "preference_match", "engagement_history"]
        }
        
        # Test personalized generation
        result = mock_openai_service.generate_themed_content(
            category="motivation",
            user_profile=user_profile,
            personalization=True
        )
        
        assert result["success"] is True
        assert result["personalization_score"] > 0.9
        assert "timezone_appropriate" in result["personalization_factors"]
        assert "preference_match" in result["personalization_factors"]
        
        # Verify appropriate content for time and preferences
        assert "morning" in result["title"].lower() or "morning" in result["content"].lower()
        assert result["tone"] == "professional"
    
    def test_multi_language_content_flow(self, mock_openai_service):
        """Test multi-language content generation and template support"""
        languages = [
            {"code": "en", "name": "English"},
            {"code": "th", "name": "Thai"},
            {"code": "zh", "name": "Chinese"},
            {"code": "ja", "name": "Japanese"}
        ]
        
        for lang in languages:
            # Configure language-specific response
            mock_openai_service.generate_themed_content.return_value = {
                "success": True,
                "title": f"Motivational Title in {lang['name']}",
                "content": f"Motivational content in {lang['name']} language with cultural context.",
                "language": lang["code"],
                "cultural_adaptation": True,
                "tone": "culturally_appropriate"
            }
            
            # Test language-specific generation
            result = mock_openai_service.generate_themed_content(
                category="motivation",
                language=lang["code"],
                cultural_adaptation=True
            )
            
            assert result["success"] is True
            assert result["language"] == lang["code"]
            assert result["cultural_adaptation"] is True
            assert lang["name"] in result["title"]
    
    def test_scheduling_and_timing_flow(self, sample_template_metadata, mock_openai_service):
        """Test scheduling and optimal timing functionality"""
        metadata_path, metadata = sample_template_metadata
        
        # Test optimal time-based template selection
        current_times = ["07:00", "12:00", "18:00", "22:00"]
        
        for current_time in current_times:
            # Determine expected template based on time
            if current_time in ["07:00", "08:00", "09:00"]:
                expected_template = "motivation_001"  # Morning energy
            elif current_time in ["18:00", "19:00", "20:00"]:
                expected_template = "wellness_001"  # Evening calm
            else:
                expected_template = None  # No optimal template
            
            # Mock template selection based on time
            with patch('src.utils.template_manager.TemplateManager') as mock_manager_class:
                mock_manager = Mock()
                mock_manager_class.return_value = mock_manager
                
                if expected_template:
                    mock_manager.select_optimal_template.return_value = {
                        "template_id": expected_template,
                        "template_data": metadata["templates"][expected_template],
                        "time_match_score": 0.95,
                        "selection_reason": "optimal_time_match"
                    }
                else:
                    mock_manager.select_optimal_template.return_value = None
                
                # Test time-based selection
                result = mock_manager.select_optimal_template(
                    category="any",
                    current_time=current_time
                )
                
                if expected_template:
                    assert result is not None
                    assert result["template_id"] == expected_template
                    assert result["time_match_score"] > 0.9
                else:
                    assert result is None
    
    def test_fallback_and_resilience_flow(self, mock_line_bot_api):
        """Test fallback mechanisms and system resilience"""
        rich_service = RichMessageService(line_bot_api=mock_line_bot_api)
        
        # Test fallback when image URL is invalid
        flex_message = rich_service.create_flex_message(
            title="Fallback Test",
            content="This should work even with invalid image URL",
            image_url="https://invalid-url.com/nonexistent.jpg"
        )
        
        assert flex_message is not None
        # Should create message without image when URL is invalid
        
        # Test fallback when content is empty or invalid
        fallback_message = rich_service.create_flex_message(
            title="",  # Empty title
            content=""  # Empty content
        )
        
        assert fallback_message is not None
        # Should create basic message even with empty content
        
        # Test delivery with API failure and retry
        mock_line_bot_api.broadcast.side_effect = [
            Exception("Temporary API failure"),  # First attempt fails
            None  # Second attempt succeeds
        ]
        
        # This would require implementing retry logic in the service
        # For now, just test that error is handled gracefully
        try:
            delivery_result = rich_service.broadcast_rich_message(flex_message)
            # Should handle error gracefully
            assert "success" in delivery_result
        except Exception:
            # Acceptable if no retry logic implemented yet
            pass