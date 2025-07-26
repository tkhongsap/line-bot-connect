"""
Unit tests for TemplateManager
"""

import pytest
import os
import json
import tempfile
from unittest.mock import Mock, patch, mock_open
from datetime import datetime, time
from PIL import Image

from src.utils.template_manager import TemplateManager, TemplateCache
from src.models.rich_message_models import RichMessageTemplate, ContentCategory, TextArea


class TestTemplateManager:
    """Test cases for TemplateManager"""
    
    @pytest.fixture
    def mock_config(self):
        """Create a mock configuration"""
        config = Mock()
        config.template = Mock()
        config.template.template_directory = "/test/templates"
        config.template.metadata_file = "/test/metadata.json"
        config.template.cache_templates = True
        config.template.cache_duration_hours = 24
        config.template.max_template_size_mb = 5.0
        return config
    
    @pytest.fixture
    def sample_metadata(self):
        """Create sample template metadata"""
        return {
            "motivation_morning_1": {
                "filename": "motivation_morning_1.png",
                "category": "motivation",
                "theme": "morning_energy",
                "mood": "energetic",
                "preferred_times": ["06:00", "07:00", "08:00", "09:00"],
                "energy_level": "high",
                "text_areas": [
                    {
                        "x": 100,
                        "y": 200,
                        "width": 300,
                        "height": 100,
                        "alignment": "center"
                    }
                ],
                "tags": ["morning", "motivation", "energy"]
            },
            "wellness_calm_1": {
                "filename": "wellness_calm_1.png", 
                "category": "wellness",
                "theme": "mindfulness",
                "mood": "calm",
                "preferred_times": ["18:00", "19:00", "20:00", "21:00"],
                "energy_level": "low",
                "text_areas": [
                    {
                        "x": 50,
                        "y": 300,
                        "width": 400,
                        "height": 150,
                        "alignment": "left"
                    }
                ],
                "tags": ["evening", "wellness", "calm"]
            }
        }
    
    @pytest.fixture
    def template_manager(self, mock_config):
        """Create a TemplateManager instance with mocked dependencies"""
        with patch('src.utils.template_manager.get_rich_message_config', return_value=mock_config), \
             patch('os.path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data='{}')) as mock_file:
            
            manager = TemplateManager(config=mock_config)
            return manager
    
    def test_initialization(self, template_manager, mock_config):
        """Test TemplateManager initialization"""
        assert template_manager.config == mock_config
        assert template_manager.template_cache == {}
        assert template_manager.metadata_cache is not None
    
    def test_load_metadata_success(self, mock_config, sample_metadata):
        """Test successful metadata loading"""
        metadata_json = json.dumps(sample_metadata)
        
        with patch('src.utils.template_manager.get_rich_message_config', return_value=mock_config), \
             patch('os.path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=metadata_json)):
            
            manager = TemplateManager(config=mock_config)
            
            assert manager.metadata_cache == sample_metadata
            assert manager.metadata_loaded_at is not None
    
    def test_load_metadata_file_not_found(self, mock_config):
        """Test metadata loading when file doesn't exist"""
        with patch('src.utils.template_manager.get_rich_message_config', return_value=mock_config), \
             patch('os.path.exists', return_value=False):
            
            manager = TemplateManager(config=mock_config)
            
            assert manager.metadata_cache == {}
            assert manager.metadata_loaded_at is None
    
    def test_load_metadata_json_error(self, mock_config):
        """Test metadata loading with invalid JSON"""
        with patch('src.utils.template_manager.get_rich_message_config', return_value=mock_config), \
             patch('os.path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data='invalid json')):
            
            manager = TemplateManager(config=mock_config)
            
            assert manager.metadata_cache == {}
    
    def test_validate_template_file_success(self, template_manager):
        """Test successful template file validation"""
        # Mock a valid image file
        mock_image = Mock()
        mock_image.size = (2500, 1686)
        
        with patch('os.path.exists', return_value=True), \
             patch('os.path.getsize', return_value=1024*1024), \
             patch('PIL.Image.open', return_value=mock_image) as mock_open_img:
            
            mock_open_img.return_value.__enter__ = Mock(return_value=mock_image)
            mock_open_img.return_value.__exit__ = Mock(return_value=None)
            
            is_valid, size = template_manager._validate_template_file("/test/image.png")
            
            assert is_valid is True
            assert size == (2500, 1686)
    
    def test_validate_template_file_too_large(self, template_manager):
        """Test template file validation with oversized file"""
        with patch('os.path.exists', return_value=True), \
             patch('os.path.getsize', return_value=10*1024*1024):  # 10MB > 5MB limit
            
            is_valid, size = template_manager._validate_template_file("/test/large.png")
            
            assert is_valid is False
            assert size is None
    
    def test_validate_template_file_not_found(self, template_manager):
        """Test template file validation with missing file"""
        with patch('os.path.exists', return_value=False):
            
            is_valid, size = template_manager._validate_template_file("/test/missing.png")
            
            assert is_valid is False
            assert size is None
    
    def test_load_template_success(self, mock_config, sample_metadata):
        """Test successful template loading"""
        metadata_json = json.dumps(sample_metadata)
        
        # Mock a valid image
        mock_image = Mock()
        mock_image.size = (2500, 1686)
        
        with patch('src.utils.template_manager.get_rich_message_config', return_value=mock_config), \
             patch('os.path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=metadata_json)), \
             patch('os.path.getsize', return_value=1024*1024), \
             patch('PIL.Image.open', return_value=mock_image) as mock_open_img:
            
            mock_open_img.return_value.__enter__ = Mock(return_value=mock_image)
            mock_open_img.return_value.__exit__ = Mock(return_value=None)
            
            manager = TemplateManager(config=mock_config)
            template = manager.load_template("motivation_morning_1")
            
            assert template is not None
            assert template.template_id == "motivation_morning_1"
            assert template.category == ContentCategory.MOTIVATION
    
    def test_load_template_not_found(self, template_manager):
        """Test loading non-existent template"""
        template = template_manager.load_template("nonexistent_template")
        assert template is None
    
    def test_get_available_templates(self, mock_config, sample_metadata):
        """Test getting list of available templates"""
        metadata_json = json.dumps(sample_metadata)
        
        with patch('src.utils.template_manager.get_rich_message_config', return_value=mock_config), \
             patch('os.path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=metadata_json)):
            
            manager = TemplateManager(config=mock_config)
            templates = manager.get_available_templates()
            
            assert len(templates) == 2
            assert "motivation_morning_1" in templates
            assert "wellness_calm_1" in templates
    
    def test_get_templates_by_category(self, mock_config, sample_metadata):
        """Test filtering templates by category"""
        metadata_json = json.dumps(sample_metadata)
        
        # Mock valid images
        mock_image = Mock()
        mock_image.size = (2500, 1686)
        
        with patch('src.utils.template_manager.get_rich_message_config', return_value=mock_config), \
             patch('os.path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=metadata_json)), \
             patch('os.path.getsize', return_value=1024*1024), \
             patch('PIL.Image.open', return_value=mock_image) as mock_open_img:
            
            mock_open_img.return_value.__enter__ = Mock(return_value=mock_image)
            mock_open_img.return_value.__exit__ = Mock(return_value=None)
            
            manager = TemplateManager(config=mock_config)
            motivation_templates = manager.get_templates_by_category(ContentCategory.MOTIVATION)
            wellness_templates = manager.get_templates_by_category(ContentCategory.WELLNESS)
            
            assert len(motivation_templates) == 1
            assert len(wellness_templates) == 1
            assert motivation_templates[0].template_id == "motivation_morning_1"
            assert wellness_templates[0].template_id == "wellness_calm_1"
    
    def test_select_template_for_time_morning(self, mock_config, sample_metadata):
        """Test template selection for morning time"""
        metadata_json = json.dumps(sample_metadata)
        
        # Mock valid images
        mock_image = Mock()
        mock_image.size = (2500, 1686)
        
        with patch('src.utils.template_manager.get_rich_message_config', return_value=mock_config), \
             patch('os.path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=metadata_json)), \
             patch('os.path.getsize', return_value=1024*1024), \
             patch('PIL.Image.open', return_value=mock_image) as mock_open_img:
            
            mock_open_img.return_value.__enter__ = Mock(return_value=mock_image)
            mock_open_img.return_value.__exit__ = Mock(return_value=None)
            
            manager = TemplateManager(config=mock_config)
            
            # Test morning time (8:00 AM)
            morning_time = time(8, 0)
            template = manager.select_template_for_time(
                ContentCategory.MOTIVATION, 
                morning_time, 
                "high"
            )
            
            assert template is not None
            assert template.template_id == "motivation_morning_1"
    
    def test_select_template_for_time_evening(self, mock_config, sample_metadata):
        """Test template selection for evening time"""
        metadata_json = json.dumps(sample_metadata)
        
        # Mock valid images
        mock_image = Mock()
        mock_image.size = (2500, 1686)
        
        with patch('src.utils.template_manager.get_rich_message_config', return_value=mock_config), \
             patch('os.path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=metadata_json)), \
             patch('os.path.getsize', return_value=1024*1024), \
             patch('PIL.Image.open', return_value=mock_image) as mock_open_img:
            
            mock_open_img.return_value.__enter__ = Mock(return_value=mock_image)
            mock_open_img.return_value.__exit__ = Mock(return_value=None)
            
            manager = TemplateManager(config=mock_config)
            
            # Test evening time (7:00 PM)
            evening_time = time(19, 0)
            template = manager.select_template_for_time(
                ContentCategory.WELLNESS, 
                evening_time, 
                "low"
            )
            
            assert template is not None
            assert template.template_id == "wellness_calm_1"
    
    def test_select_template_no_category_match(self, template_manager):
        """Test template selection with no matching category"""
        template = template_manager.select_template_for_time(ContentCategory.PRODUCTIVITY)
        assert template is None
    
    def test_get_template_file_path(self, mock_config, sample_metadata):
        """Test getting template file path"""
        metadata_json = json.dumps(sample_metadata)
        
        # Mock valid images
        mock_image = Mock()
        mock_image.size = (2500, 1686)
        
        with patch('src.utils.template_manager.get_rich_message_config', return_value=mock_config), \
             patch('os.path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=metadata_json)), \
             patch('os.path.getsize', return_value=1024*1024), \
             patch('PIL.Image.open', return_value=mock_image) as mock_open_img:
            
            mock_open_img.return_value.__enter__ = Mock(return_value=mock_image)
            mock_open_img.return_value.__exit__ = Mock(return_value=None)
            
            manager = TemplateManager(config=mock_config)
            file_path = manager.get_template_file_path("motivation_morning_1")
            
            assert file_path == "/test/templates/motivation_morning_1.png"
    
    def test_template_caching(self, mock_config, sample_metadata):
        """Test template caching functionality"""
        metadata_json = json.dumps(sample_metadata)
        
        # Mock valid images
        mock_image = Mock()
        mock_image.size = (2500, 1686)
        
        with patch('src.utils.template_manager.get_rich_message_config', return_value=mock_config), \
             patch('os.path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=metadata_json)), \
             patch('os.path.getsize', return_value=1024*1024), \
             patch('PIL.Image.open', return_value=mock_image) as mock_open_img:
            
            mock_open_img.return_value.__enter__ = Mock(return_value=mock_image)
            mock_open_img.return_value.__exit__ = Mock(return_value=None)
            
            manager = TemplateManager(config=mock_config)
            
            # First load should cache the template
            template1 = manager.load_template("motivation_morning_1")
            assert len(manager.template_cache) == 1
            
            # Second load should use cache
            template2 = manager.load_template("motivation_morning_1")
            assert template1 is template2  # Should be same object from cache
    
    def test_cache_disabled(self, mock_config, sample_metadata):
        """Test behavior when caching is disabled"""
        mock_config.template.cache_templates = False
        metadata_json = json.dumps(sample_metadata)
        
        # Mock valid images
        mock_image = Mock()
        mock_image.size = (2500, 1686)
        
        with patch('src.utils.template_manager.get_rich_message_config', return_value=mock_config), \
             patch('os.path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=metadata_json)), \
             patch('os.path.getsize', return_value=1024*1024), \
             patch('PIL.Image.open', return_value=mock_image) as mock_open_img:
            
            mock_open_img.return_value.__enter__ = Mock(return_value=mock_image)
            mock_open_img.return_value.__exit__ = Mock(return_value=None)
            
            manager = TemplateManager(config=mock_config)
            
            # Load template with caching disabled
            template = manager.load_template("motivation_morning_1")
            assert template is not None
            assert len(manager.template_cache) == 0  # Should not cache
    
    def test_clear_cache(self, template_manager):
        """Test cache clearing"""
        # Add something to cache manually
        template_manager.template_cache["test"] = Mock()
        template_manager.metadata_cache = {"test": "data"}
        template_manager.metadata_loaded_at = datetime.now()
        
        template_manager.clear_cache()
        
        assert len(template_manager.template_cache) == 0
        assert template_manager.metadata_cache is None
        assert template_manager.metadata_loaded_at is None
    
    def test_get_cache_stats(self, template_manager):
        """Test cache statistics"""
        stats = template_manager.get_cache_stats()
        
        assert "cached_templates" in stats
        assert "metadata_loaded" in stats
        assert "metadata_age_hours" in stats
        assert "cache_enabled" in stats
        
        assert stats["cached_templates"] == 0
        assert stats["cache_enabled"] is True
    
    def test_validate_all_templates(self, mock_config, sample_metadata):
        """Test validation of all templates"""
        metadata_json = json.dumps(sample_metadata)
        
        # Mock valid images
        mock_image = Mock()
        mock_image.size = (2500, 1686)
        
        with patch('src.utils.template_manager.get_rich_message_config', return_value=mock_config), \
             patch('os.path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=metadata_json)), \
             patch('os.path.getsize', return_value=1024*1024), \
             patch('PIL.Image.open', return_value=mock_image) as mock_open_img:
            
            mock_open_img.return_value.__enter__ = Mock(return_value=mock_image)
            mock_open_img.return_value.__exit__ = Mock(return_value=None)
            
            manager = TemplateManager(config=mock_config)
            validation_results = manager.validate_all_templates()
            
            assert len(validation_results) == 2
            assert validation_results["motivation_morning_1"] is True
            assert validation_results["wellness_calm_1"] is True
    
    def test_file_hash_calculation(self, template_manager):
        """Test file hash calculation"""
        test_content = b"test file content"
        
        with patch('builtins.open', mock_open(read_data=test_content)):
            file_hash = template_manager._get_file_hash("/test/file.png")
            
            # Verify hash is calculated
            assert len(file_hash) == 64  # SHA256 hash length
            assert file_hash != ""
    
    def test_should_reload_metadata(self, template_manager):
        """Test metadata reload logic"""
        # Initially should reload (no metadata loaded)
        assert template_manager._should_reload_metadata() is True
        
        # After setting loaded time, should not reload immediately
        template_manager.metadata_loaded_at = datetime.now()
        assert template_manager._should_reload_metadata() is False