"""
Unit tests for Rich Message data models
"""

import pytest
from datetime import datetime
from src.models.rich_message_models import (
    RichMessageContent, RichMessageTemplate, RichMessageConfig,
    ContentCategory, ContentTheme, UserInteraction, DeliveryRecord,
    DeliveryStatus, TextArea, ValidationError
)


class TestTextArea:
    """Test TextArea data model"""
    
    def test_text_area_creation(self):
        """Test valid TextArea creation"""
        area = TextArea(x=100, y=200, width=300, height=150)
        assert area.x == 100
        assert area.y == 200
        assert area.width == 300
        assert area.height == 150
        assert area.alignment == "left"  # default
    
    def test_text_area_with_options(self):
        """Test TextArea with optional parameters"""
        area = TextArea(
            x=100, y=200, width=300, height=150,
            max_chars=100, font_size=14, font_color="#000000",
            alignment="center"
        )
        assert area.max_chars == 100
        assert area.font_size == 14
        assert area.font_color == "#000000"
        assert area.alignment == "center"
    
    def test_text_area_negative_coordinates(self):
        """Test TextArea with negative coordinates"""
        with pytest.raises(ValidationError, match="coordinates must be non-negative"):
            TextArea(x=-10, y=200, width=300, height=150)
    
    def test_text_area_zero_dimensions(self):
        """Test TextArea with zero dimensions"""
        with pytest.raises(ValidationError, match="dimensions must be positive"):
            TextArea(x=100, y=200, width=0, height=150)
    
    def test_text_area_invalid_alignment(self):
        """Test TextArea with invalid alignment"""
        with pytest.raises(ValidationError, match="alignment must be"):
            TextArea(x=100, y=200, width=300, height=150, alignment="invalid")


class TestRichMessageTemplate:
    """Test RichMessageTemplate data model"""
    
    def test_template_creation(self):
        """Test valid template creation"""
        text_areas = {
            "primary": TextArea(x=100, y=200, width=300, height=150),
            "secondary": TextArea(x=200, y=400, width=200, height=100)
        }
        
        template = RichMessageTemplate(
            template_id="test_template",
            filename="test.png",
            category=ContentCategory.MOTIVATION,
            theme=ContentTheme.MORNING_ENERGY,
            mood="energetic",
            energy_level="high",
            text_areas=text_areas
        )
        
        assert template.template_id == "test_template"
        assert template.filename == "test.png"
        assert template.category == ContentCategory.MOTIVATION
        assert template.theme == ContentTheme.MORNING_ENERGY
        assert template.mood == "energetic"
        assert template.energy_level == "high"
        assert len(template.text_areas) == 2
    
    def test_template_missing_required_fields(self):
        """Test template creation with missing required fields"""
        with pytest.raises(ValidationError, match="Template ID and filename are required"):
            RichMessageTemplate(
                template_id="",
                filename="test.png",
                category=ContentCategory.MOTIVATION,
                theme=ContentTheme.MORNING_ENERGY,
                mood="energetic",
                energy_level="high",
                text_areas={}
            )
    
    def test_template_invalid_category(self):
        """Test template with invalid category"""
        with pytest.raises(ValidationError, match="Category must be a ContentCategory enum"):
            RichMessageTemplate(
                template_id="test_template",
                filename="test.png",
                category="invalid_category",
                theme=ContentTheme.MORNING_ENERGY,
                mood="energetic",
                energy_level="high",
                text_areas={}
            )
    
    def test_template_invalid_dimensions(self):
        """Test template with invalid dimensions"""
        with pytest.raises(ValidationError, match="Template dimensions must be"):
            RichMessageTemplate(
                template_id="test_template",
                filename="test.png",
                category=ContentCategory.MOTIVATION,
                theme=ContentTheme.MORNING_ENERGY,
                mood="energetic",
                energy_level="high",
                text_areas={},
                dimensions=(1000, 1000)  # Invalid dimensions
            )
    
    def test_template_from_metadata(self):
        """Test template creation from metadata"""
        metadata = {
            "filename": "motivation_bright_01.png",
            "theme": "motivation",
            "mood": "bright",
            "energy_level": "high",
            "text_areas": {
                "primary": {"x": 100, "y": 200, "width": 300, "height": 150},
                "secondary": {"x": 200, "y": 400, "width": 200, "height": 100}
            },
            "best_for": ["morning_motivation", "energy_boost"],
            "time_of_day": ["morning"],
            "content_type": ["motivational_quotes"]
        }
        
        template = RichMessageTemplate.from_metadata("test_template", metadata)
        
        assert template.template_id == "test_template"
        assert template.filename == "motivation_bright_01.png"
        assert template.category == ContentCategory.MOTIVATION
        assert template.mood == "bright"
        assert len(template.text_areas) == 2
    
    def test_template_is_suitable_for_time(self):
        """Test template time suitability check"""
        template = RichMessageTemplate(
            template_id="test_template",
            filename="test.png",
            category=ContentCategory.MOTIVATION,
            theme=ContentTheme.MORNING_ENERGY,
            mood="energetic",
            energy_level="high",
            text_areas={},
            time_of_day=["morning"]
        )
        
        assert template.is_suitable_for_time(9) is True  # Morning
        assert template.is_suitable_for_time(15) is False  # Afternoon
    
    def test_template_matches_energy_level(self):
        """Test template energy level matching"""
        template = RichMessageTemplate(
            template_id="test_template",
            filename="test.png",
            category=ContentCategory.MOTIVATION,
            theme=ContentTheme.MORNING_ENERGY,
            mood="energetic",
            energy_level="high",
            text_areas={}
        )
        
        assert template.matches_energy_level("high") is True
        assert template.matches_energy_level("medium") is True  # Within 1 level
        assert template.matches_energy_level("very_low") is False


class TestRichMessageContent:
    """Test RichMessageContent data model"""
    
    def test_content_creation(self):
        """Test valid content creation"""
        content = RichMessageContent(
            content_id="content_123",
            title="Test Title",
            content="This is test content for Rich Message.",
            category=ContentCategory.MOTIVATION,
            theme=ContentTheme.DAILY_TIPS,
            template_id="template_123"
        )
        
        assert content.content_id == "content_123"
        assert content.title == "Test Title"
        assert content.content == "This is test content for Rich Message."
        assert content.category == ContentCategory.MOTIVATION
        assert content.theme == ContentTheme.DAILY_TIPS
        assert content.template_id == "template_123"
        assert content.content_length == len("This is test content for Rich Message.")
    
    def test_content_missing_required_fields(self):
        """Test content creation with missing required fields"""
        with pytest.raises(ValidationError, match="Content ID, title, and content are required"):
            RichMessageContent(
                content_id="",
                title="Test Title",
                content="Test content",
                category=ContentCategory.MOTIVATION,
                theme=ContentTheme.DAILY_TIPS,
                template_id="template_123"
            )
    
    def test_content_too_long(self):
        """Test content that is too long"""
        long_content = "x" * 2001  # Exceeds 2000 character limit
        
        with pytest.raises(ValidationError, match="Content is too long"):
            RichMessageContent(
                content_id="content_123",
                title="Test Title",
                content=long_content,
                category=ContentCategory.MOTIVATION,
                theme=ContentTheme.DAILY_TIPS,
                template_id="template_123"
            )
    
    def test_content_title_too_long(self):
        """Test content with title too long"""
        long_title = "x" * 101  # Exceeds 100 character limit
        
        with pytest.raises(ValidationError, match="Title is too long"):
            RichMessageContent(
                content_id="content_123",
                title=long_title,
                content="Test content",
                category=ContentCategory.MOTIVATION,
                theme=ContentTheme.DAILY_TIPS,
                template_id="template_123"
            )
    
    def test_content_to_dict(self):
        """Test content serialization to dictionary"""
        content = RichMessageContent(
            content_id="content_123",
            title="Test Title",
            content="Test content",
            category=ContentCategory.MOTIVATION,
            theme=ContentTheme.DAILY_TIPS,
            template_id="template_123",
            language="en",
            sentiment="positive",
            keywords=["motivation", "inspiration"]
        )
        
        content_dict = content.to_dict()
        
        assert content_dict["content_id"] == "content_123"
        assert content_dict["title"] == "Test Title"
        assert content_dict["category"] == "motivation"
        assert content_dict["theme"] == "daily_tips"
        assert content_dict["language"] == "en"
        assert content_dict["sentiment"] == "positive"
        assert content_dict["keywords"] == ["motivation", "inspiration"]
    
    def test_content_from_dict(self):
        """Test content creation from dictionary"""
        content_dict = {
            "content_id": "content_123",
            "title": "Test Title",
            "content": "Test content",
            "category": "motivation",
            "theme": "daily_tips",
            "template_id": "template_123",
            "generated_at": datetime.now().isoformat(),
            "language": "en",
            "sentiment": "positive",
            "keywords": ["motivation", "inspiration"]
        }
        
        content = RichMessageContent.from_dict(content_dict)
        
        assert content.content_id == "content_123"
        assert content.title == "Test Title"
        assert content.category == ContentCategory.MOTIVATION
        assert content.theme == ContentTheme.DAILY_TIPS


class TestUserInteraction:
    """Test UserInteraction data model"""
    
    def test_interaction_creation(self):
        """Test valid interaction creation"""
        interaction = UserInteraction(
            interaction_id="interaction_123",
            user_id="user_456",
            content_id="content_789",
            action="like"
        )
        
        assert interaction.interaction_id == "interaction_123"
        assert interaction.user_id == "user_456"
        assert interaction.content_id == "content_789"
        assert interaction.action == "like"
        assert isinstance(interaction.timestamp, datetime)
    
    def test_interaction_missing_required_fields(self):
        """Test interaction with missing required fields"""
        with pytest.raises(ValidationError, match="Interaction ID, user ID, and content ID are required"):
            UserInteraction(
                interaction_id="",
                user_id="user_456",
                content_id="content_789",
                action="like"
            )
    
    def test_interaction_invalid_action(self):
        """Test interaction with invalid action"""
        with pytest.raises(ValidationError, match="Action must be one of"):
            UserInteraction(
                interaction_id="interaction_123",
                user_id="user_456",
                content_id="content_789",
                action="invalid_action"
            )
    
    def test_interaction_to_dict(self):
        """Test interaction serialization"""
        interaction = UserInteraction(
            interaction_id="interaction_123",
            user_id="user_456",
            content_id="content_789",
            action="share",
            additional_data={"platform": "facebook"}
        )
        
        interaction_dict = interaction.to_dict()
        
        assert interaction_dict["interaction_id"] == "interaction_123"
        assert interaction_dict["user_id"] == "user_456"
        assert interaction_dict["content_id"] == "content_789"
        assert interaction_dict["action"] == "share"
        assert interaction_dict["additional_data"]["platform"] == "facebook"


class TestDeliveryRecord:
    """Test DeliveryRecord data model"""
    
    def test_delivery_record_creation(self):
        """Test valid delivery record creation"""
        scheduled_time = datetime(2024, 1, 15, 9, 0, 0)
        
        record = DeliveryRecord(
            delivery_id="delivery_123",
            content_id="content_456",
            template_id="template_789",
            status=DeliveryStatus.PENDING,
            scheduled_time=scheduled_time
        )
        
        assert record.delivery_id == "delivery_123"
        assert record.content_id == "content_456"
        assert record.template_id == "template_789"
        assert record.status == DeliveryStatus.PENDING
        assert record.scheduled_time == scheduled_time
        assert record.retry_count == 0
    
    def test_delivery_record_missing_required_fields(self):
        """Test delivery record with missing required fields"""
        with pytest.raises(ValidationError, match="Delivery ID and content ID are required"):
            DeliveryRecord(
                delivery_id="",
                content_id="content_456",
                template_id="template_789",
                status=DeliveryStatus.PENDING,
                scheduled_time=datetime.now()
            )
    
    def test_delivery_record_mark_as_sent(self):
        """Test marking delivery record as sent"""
        record = DeliveryRecord(
            delivery_id="delivery_123",
            content_id="content_456",
            template_id="template_789",
            status=DeliveryStatus.PROCESSING,
            scheduled_time=datetime.now()
        )
        
        record.mark_as_sent(success_count=100, failure_count=5)
        
        assert record.status == DeliveryStatus.SENT
        assert record.success_count == 100
        assert record.failure_count == 5
        assert record.delivered_time is not None
    
    def test_delivery_record_mark_as_failed(self):
        """Test marking delivery record as failed"""
        record = DeliveryRecord(
            delivery_id="delivery_123",
            content_id="content_456",
            template_id="template_789",
            status=DeliveryStatus.PROCESSING,
            scheduled_time=datetime.now()
        )
        
        record.mark_as_failed("API rate limit exceeded")
        
        assert record.status == DeliveryStatus.FAILED
        assert record.error_message == "API rate limit exceeded"
    
    def test_delivery_record_mark_for_retry(self):
        """Test marking delivery record for retry"""
        record = DeliveryRecord(
            delivery_id="delivery_123",
            content_id="content_456",
            template_id="template_789",
            status=DeliveryStatus.FAILED,
            scheduled_time=datetime.now()
        )
        
        record.mark_for_retry()
        
        assert record.status == DeliveryStatus.RETRYING
        assert record.retry_count == 1


class TestRichMessageConfig:
    """Test RichMessageConfig data model"""
    
    def test_config_creation(self):
        """Test valid config creation"""
        config = RichMessageConfig(
            daily_send_hour=10,
            max_retries=5,
            retry_delay_minutes=45,
            default_language="en"
        )
        
        assert config.daily_send_hour == 10
        assert config.max_retries == 5
        assert config.retry_delay_minutes == 45
        assert config.default_language == "en"
        assert config.timezone_aware is True  # default
        assert config.analytics_enabled is True  # default
    
    def test_config_invalid_send_hour(self):
        """Test config with invalid send hour"""
        with pytest.raises(ValidationError, match="Daily send hour must be between 0 and 23"):
            RichMessageConfig(daily_send_hour=25)
    
    def test_config_negative_retries(self):
        """Test config with negative max retries"""
        with pytest.raises(ValidationError, match="Max retries must be non-negative"):
            RichMessageConfig(max_retries=-1)
    
    def test_config_negative_delay(self):
        """Test config with negative retry delay"""
        with pytest.raises(ValidationError, match="Retry delay must be non-negative"):
            RichMessageConfig(retry_delay_minutes=-10)
    
    def test_config_from_env(self):
        """Test config creation from environment variables"""
        import os
        
        # Mock environment variables
        env_vars = {
            'RICH_MESSAGE_SEND_HOUR': '8',
            'RICH_MESSAGE_MAX_RETRIES': '2',
            'RICH_MESSAGE_RETRY_DELAY': '15',
            'RICH_MESSAGE_DEFAULT_LANGUAGE': 'th',
            'RICH_MESSAGE_TIMEZONE_AWARE': 'false'
        }
        
        for key, value in env_vars.items():
            os.environ[key] = value
        
        try:
            config = RichMessageConfig.from_env()
            
            assert config.daily_send_hour == 8
            assert config.max_retries == 2
            assert config.retry_delay_minutes == 15
            assert config.default_language == "th"
            assert config.timezone_aware is False
        finally:
            # Clean up environment variables
            for key in env_vars:
                os.environ.pop(key, None)
    
    def test_config_to_dict(self):
        """Test config serialization"""
        config = RichMessageConfig(
            daily_send_hour=9,
            max_retries=3,
            enabled_categories=[ContentCategory.MOTIVATION, ContentCategory.WELLNESS]
        )
        
        config_dict = config.to_dict()
        
        assert config_dict["daily_send_hour"] == 9
        assert config_dict["max_retries"] == 3
        assert config_dict["enabled_categories"] == ["motivation", "wellness"]
        assert config_dict["timezone_aware"] is True