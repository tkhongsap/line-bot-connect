"""
Unit tests for ImageComposer
"""

import pytest
import os
import tempfile
from unittest.mock import Mock, patch, MagicMock
from PIL import Image, ImageFont
from datetime import datetime

from src.utils.image_composer import ImageComposer, FontConfig, TextStyle, CompositionResult
from src.models.rich_message_models import RichMessageTemplate, TextArea, ContentCategory
from src.utils.content_generator import GeneratedContent


class TestImageComposer:
    """Test cases for ImageComposer"""
    
    @pytest.fixture
    def mock_config(self):
        """Create a mock configuration"""
        config = Mock()
        config.content_generation = Mock()
        config.content_generation.content_cache_hours = 6
        return config
    
    @pytest.fixture
    def sample_template(self):
        """Create a sample template"""
        return RichMessageTemplate(
            template_id="test_template",
            category=ContentCategory.MOTIVATION,
            filename="test_template.png",
            theme="morning_energy",
            mood="energetic",
            preferred_times=["08:00", "09:00"],
            energy_level="high",
            text_areas=[
                TextArea(
                    x=100,
                    y=200,
                    width=300,
                    height=100,
                    alignment="center"
                ),
                TextArea(
                    x=50,
                    y=350,
                    width=400,
                    height=150,
                    alignment="center"
                )
            ],
            tags=["morning", "motivation"]
        )
    
    @pytest.fixture
    def sample_content(self):
        """Create sample generated content"""
        return GeneratedContent(
            title="Start Your Day Strong",
            content="Every morning brings new opportunities to achieve greatness. Take the first step today!",
            language="en",
            category=ContentCategory.MOTIVATION,
            theme=None,
            metadata={},
            generation_time=datetime.now()
        )
    
    @pytest.fixture
    def image_composer(self, mock_config):
        """Create an ImageComposer instance with mocked dependencies"""
        with patch('src.utils.image_composer.get_rich_message_config', return_value=mock_config), \
             patch('os.makedirs'):
            
            composer = ImageComposer(config=mock_config)
            return composer
    
    @pytest.fixture
    def mock_image(self):
        """Create a mock PIL Image"""
        img = Mock(spec=Image.Image)
        img.size = (2500, 1686)
        img.mode = 'RGB'
        img.convert.return_value = img
        img.copy.return_value = img
        img.save = Mock()
        return img
    
    def test_initialization(self, image_composer, mock_config):
        """Test ImageComposer initialization"""
        assert image_composer.config == mock_config
        assert image_composer.font_cache == {}
        assert isinstance(image_composer.default_fonts, dict)
        assert image_composer.output_dir == "/tmp/rich_messages"
    
    def test_load_default_fonts(self, image_composer):
        """Test default font loading"""
        fonts = image_composer._load_default_fonts()
        
        assert isinstance(fonts, dict)
        # Should have at least a default font or empty dict
        assert len(fonts) >= 0
    
    def test_get_font_with_valid_path(self, image_composer):
        """Test font loading with valid path"""
        font_config = FontConfig(
            font_path="/non/existent/font.ttf",  # Will fallback
            size=24
        )
        
        with patch('PIL.ImageFont.truetype') as mock_truetype, \
             patch('PIL.ImageFont.load_default') as mock_default:
            
            mock_default.return_value = Mock()
            
            # Should fallback to default when path doesn't exist
            font = image_composer._get_font(font_config)
            assert font is not None
    
    def test_get_font_caching(self, image_composer):
        """Test font caching functionality"""
        font_config = FontConfig(font_path="", size=24)
        
        with patch('PIL.ImageFont.load_default') as mock_default:
            mock_font = Mock()
            mock_default.return_value = mock_font
            
            # First call should cache
            font1 = image_composer._get_font(font_config)
            assert len(image_composer.font_cache) == 1
            
            # Second call should use cache
            font2 = image_composer._get_font(font_config)
            assert font1 is font2
    
    def test_select_font_for_language_english(self, image_composer):
        """Test font selection for English"""
        font_config = image_composer._select_font_for_language("en", size=36)
        
        assert font_config.size == 36
        assert font_config.color == (255, 255, 255, 255)
        assert font_config.stroke_width == 2
    
    def test_select_font_for_language_thai(self, image_composer):
        """Test font selection for Thai"""
        font_config = image_composer._select_font_for_language("th", size=32, bold=True)
        
        assert font_config.size == 32
        # Should attempt to use Thai-specific font
        assert isinstance(font_config.font_path, str)
    
    def test_wrap_text_simple(self, image_composer):
        """Test simple text wrapping"""
        mock_font = Mock()
        mock_font.getbbox.return_value = (0, 0, 100, 20)  # width=100, height=20
        
        text = "Hello world test"
        max_width = 150
        
        lines = image_composer._wrap_text(text, mock_font, max_width)
        
        assert isinstance(lines, list)
        assert len(lines) >= 1
    
    def test_wrap_text_long_text(self, image_composer):
        """Test text wrapping with long text"""
        mock_font = Mock()
        # Mock font to return different widths for different text lengths
        def mock_getbbox(text):
            return (0, 0, len(text) * 10, 20)
        mock_font.getbbox.side_effect = mock_getbbox
        
        text = "This is a very long text that should definitely be wrapped across multiple lines"
        max_width = 200  # Should force wrapping
        
        lines = image_composer._wrap_text(text, mock_font, max_width)
        
        assert len(lines) > 1  # Should wrap to multiple lines
    
    def test_calculate_text_size(self, image_composer):
        """Test text size calculation"""
        mock_font = Mock()
        mock_font.getbbox.return_value = (0, 0, 200, 30)
        
        with patch.object(image_composer, '_wrap_text', return_value=["Line 1", "Line 2"]):
            width, height = image_composer._calculate_text_size("Test text", mock_font, 300)
            
            assert width > 0
            assert height > 0
    
    def test_calculate_text_position_center(self, image_composer):
        """Test text position calculation for center alignment"""
        text_area = TextArea(x=100, y=200, width=300, height=100, alignment="center")
        text_size = (150, 50)
        
        x, y = image_composer._calculate_text_position(
            text_area, text_size, "center", "center"
        )
        
        # Should be centered in the area
        assert x == 175  # 100 + (300-150)/2
        assert y == 225  # 200 + (100-50)/2
    
    def test_calculate_text_position_left_top(self, image_composer):
        """Test text position calculation for left-top alignment"""
        text_area = TextArea(x=100, y=200, width=300, height=100, alignment="left")
        text_size = (150, 50)
        
        x, y = image_composer._calculate_text_position(
            text_area, text_size, "left", "top"
        )
        
        assert x == 100  # Left edge
        assert y == 200  # Top edge
    
    def test_draw_text_with_style(self, image_composer):
        """Test drawing text with styling"""
        mock_draw = Mock()
        mock_font = Mock()
        mock_font.getbbox.return_value = (0, 0, 100, 20)
        
        font_config = FontConfig(font_path="", size=24)
        text_style = TextStyle(
            font_config=font_config,
            alignment="center",
            word_wrap=True,
            shadow=True
        )
        
        text_area = TextArea(x=100, y=200, width=300, height=100)
        
        with patch.object(image_composer, '_get_font', return_value=mock_font), \
             patch.object(image_composer, '_wrap_text', return_value=["Test line"]):
            
            image_composer._draw_text_with_style(
                mock_draw, "Test text", (100, 200), text_style, text_area
            )
            
            # Should call draw.text at least twice (shadow + main text)
            assert mock_draw.text.call_count >= 2
    
    def test_enhance_image_quality(self, image_composer):
        """Test image quality enhancement"""
        mock_image = Mock()
        mock_enhancer = Mock()
        mock_enhancer.enhance.return_value = mock_image
        
        with patch('PIL.ImageEnhance.Sharpness', return_value=mock_enhancer), \
             patch('PIL.ImageEnhance.Contrast', return_value=mock_enhancer):
            
            result = image_composer._enhance_image_quality(mock_image)
            
            assert result == mock_image
            assert mock_enhancer.enhance.call_count == 2  # Sharpness + Contrast
    
    def test_compose_image_success(self, image_composer, sample_template, sample_content, mock_image):
        """Test successful image composition"""
        template_path = "/test/template.png"
        
        with patch('PIL.Image.open', return_value=mock_image), \
             patch('PIL.ImageDraw.Draw') as mock_draw_class, \
             patch.object(image_composer, '_enhance_image_quality', return_value=mock_image), \
             patch('os.path.exists', return_value=True), \
             patch('os.makedirs'), \
             patch('builtins.open', create=True):
            
            mock_draw = Mock()
            mock_draw_class.return_value = mock_draw
            
            result = image_composer.compose_image(
                sample_template,
                sample_content,
                template_image_path=template_path
            )
            
            assert result.success is True
            assert result.image_path is not None
            assert result.image_size == (2500, 1686)
            assert result.metadata is not None
    
    def test_compose_image_template_not_found(self, image_composer, sample_template, sample_content):
        """Test image composition with missing template"""
        template_path = "/non/existent/template.png"
        
        with patch('os.path.exists', return_value=False):
            result = image_composer.compose_image(
                sample_template,
                sample_content,
                template_image_path=template_path
            )
            
            assert result.success is False
            assert "not found" in result.error_message.lower()
    
    def test_compose_image_no_text_areas(self, image_composer, sample_content, mock_image):
        """Test image composition with template having no text areas"""
        template = RichMessageTemplate(
            template_id="no_text_areas",
            category=ContentCategory.MOTIVATION,
            filename="test.png",
            theme="test",
            mood="test",
            preferred_times=[],
            energy_level="medium",
            text_areas=[],  # No text areas
            tags=[]
        )
        
        template_path = "/test/template.png"
        
        with patch('PIL.Image.open', return_value=mock_image), \
             patch('PIL.ImageDraw.Draw') as mock_draw_class, \
             patch.object(image_composer, '_enhance_image_quality', return_value=mock_image), \
             patch('os.path.exists', return_value=True), \
             patch('os.makedirs'), \
             patch('builtins.open', create=True):
            
            mock_draw = Mock()
            mock_draw_class.return_value = mock_draw
            
            result = image_composer.compose_image(
                template,
                sample_content,
                template_image_path=template_path
            )
            
            # Should still succeed by creating default text area
            assert result.success is True
    
    def test_create_rich_message_image_success(self, image_composer, sample_template, sample_content):
        """Test creating Rich Message image"""
        template_path = "/test/template.png"
        output_path = "/test/output.jpg"
        
        with patch.object(image_composer, 'compose_image') as mock_compose:
            mock_compose.return_value = CompositionResult(
                success=True,
                image_path=output_path
            )
            
            result_path = image_composer.create_rich_message_image(
                sample_template,
                sample_content,
                template_path
            )
            
            assert result_path == output_path
    
    def test_create_rich_message_image_failure(self, image_composer, sample_template, sample_content):
        """Test creating Rich Message image with failure"""
        template_path = "/test/template.png"
        
        with patch.object(image_composer, 'compose_image') as mock_compose:
            mock_compose.return_value = CompositionResult(
                success=False,
                error_message="Test error"
            )
            
            result_path = image_composer.create_rich_message_image(
                sample_template,
                sample_content,
                template_path
            )
            
            assert result_path is None
    
    def test_get_image_as_base64_success(self, image_composer):
        """Test converting image to base64"""
        test_data = b"fake image data"
        
        with patch('builtins.open', create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = test_data
            
            result = image_composer.get_image_as_base64("/test/image.jpg")
            
            assert result is not None
            assert isinstance(result, str)
    
    def test_get_image_as_base64_file_error(self, image_composer):
        """Test converting image to base64 with file error"""
        with patch('builtins.open', side_effect=FileNotFoundError()):
            result = image_composer.get_image_as_base64("/non/existent/image.jpg")
            
            assert result is None
    
    def test_validate_image_for_line_success(self, image_composer, mock_image):
        """Test image validation for LINE requirements"""
        image_path = "/test/image.jpg"
        
        with patch('os.path.exists', return_value=True), \
             patch('os.path.getsize', return_value=500000), \
             patch('PIL.Image.open', return_value=mock_image):
            
            mock_image.size = (2500, 1686)  # Optimal size
            mock_image.format = 'JPEG'
            mock_image.__enter__ = Mock(return_value=mock_image)
            mock_image.__exit__ = Mock(return_value=None)
            
            result = image_composer.validate_image_for_line(image_path)
            
            assert result["valid"] is True
            assert len(result["issues"]) == 0
    
    def test_validate_image_for_line_too_large(self, image_composer, mock_image):
        """Test image validation with oversized file"""
        image_path = "/test/large_image.jpg"
        
        with patch('os.path.exists', return_value=True), \
             patch('os.path.getsize', return_value=2000000), \
             patch('PIL.Image.open', return_value=mock_image):
            
            mock_image.size = (2500, 1686)
            mock_image.format = 'JPEG'
            mock_image.__enter__ = Mock(return_value=mock_image)
            mock_image.__exit__ = Mock(return_value=None)
            
            result = image_composer.validate_image_for_line(image_path)
            
            assert result["valid"] is False
            assert any("size too large" in issue.lower() for issue in result["issues"])
    
    def test_validate_image_for_line_wrong_dimensions(self, image_composer, mock_image):
        """Test image validation with wrong dimensions"""
        image_path = "/test/wrong_size.jpg"
        
        with patch('os.path.exists', return_value=True), \
             patch('os.path.getsize', return_value=500000), \
             patch('PIL.Image.open', return_value=mock_image):
            
            mock_image.size = (1000, 800)  # Wrong dimensions
            mock_image.format = 'JPEG'
            mock_image.__enter__ = Mock(return_value=mock_image)
            mock_image.__exit__ = Mock(return_value=None)
            
            result = image_composer.validate_image_for_line(image_path)
            
            assert any("dimensions" in issue.lower() for issue in result["issues"])
    
    def test_validate_image_for_line_file_not_found(self, image_composer):
        """Test image validation with missing file"""
        with patch('os.path.exists', return_value=False):
            result = image_composer.validate_image_for_line("/non/existent.jpg")
            
            assert result["valid"] is False
            assert any("not found" in issue.lower() for issue in result["issues"])
    
    def test_clear_font_cache(self, image_composer):
        """Test font cache clearing"""
        # Add something to cache
        image_composer.font_cache["test"] = Mock()
        assert len(image_composer.font_cache) > 0
        
        image_composer.clear_font_cache()
        assert len(image_composer.font_cache) == 0
    
    def test_get_composition_stats(self, image_composer):
        """Test composition statistics"""
        stats = image_composer.get_composition_stats()
        
        assert "cached_fonts" in stats
        assert "available_fonts" in stats
        assert "output_directory" in stats
        assert "font_types" in stats
        
        assert stats["output_directory"] == "/tmp/rich_messages"
        assert isinstance(stats["font_types"], list)
    
    def test_font_config_creation(self):
        """Test FontConfig creation"""
        font_config = FontConfig(
            font_path="/test/font.ttf",
            size=24,
            color=(255, 0, 0, 255),
            stroke_width=2
        )
        
        assert font_config.font_path == "/test/font.ttf"
        assert font_config.size == 24
        assert font_config.color == (255, 0, 0, 255)
        assert font_config.stroke_width == 2
    
    def test_text_style_creation(self):
        """Test TextStyle creation"""
        font_config = FontConfig(font_path="", size=24)
        text_style = TextStyle(
            font_config=font_config,
            alignment="center",
            shadow=True
        )
        
        assert text_style.font_config == font_config
        assert text_style.alignment == "center"
        assert text_style.shadow is True
        assert text_style.line_spacing == 1.2  # Default value
    
    def test_composition_result_creation(self):
        """Test CompositionResult creation"""
        result = CompositionResult(
            success=True,
            image_path="/test/output.jpg",
            image_size=(2500, 1686)
        )
        
        assert result.success is True
        assert result.image_path == "/test/output.jpg"
        assert result.image_size == (2500, 1686)
        assert result.error_message is None