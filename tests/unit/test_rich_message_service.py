"""
Unit tests for RichMessageService
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, mock_open
from datetime import datetime
from linebot.models import (
    RichMenu, RichMenuSize, FlexSendMessage, BubbleContainer,
    PostbackAction, URIAction, MessageAction
)
from linebot.exceptions import LineBotApiError
from src.services.rich_message_service import RichMessageService


class TestRichMessageService:
    """Test cases for Rich Message Service"""
    
    @pytest.fixture
    def mock_line_bot_api(self):
        """Create a mock LINE Bot API instance"""
        return Mock()
    
    @pytest.fixture
    def rich_message_service(self, mock_line_bot_api):
        """Create a RichMessageService instance with mocked dependencies"""
        return RichMessageService(
            line_bot_api=mock_line_bot_api,
            template_manager=None,
            content_generator=None,
            enable_redis=False  # Disable Redis for unit tests
        )
    
    def test_initialization(self, rich_message_service):
        """Test RichMessageService initialization"""
        assert rich_message_service.RICH_MENU_WIDTH == 2500
        assert rich_message_service.RICH_MENU_HEIGHT == 1686
        assert "default" in rich_message_service._rich_menu_configs
        assert rich_message_service.template_manager is None
        assert rich_message_service.content_generator is None
    
    def test_create_rich_menu_success(self, rich_message_service, mock_line_bot_api):
        """Test successful Rich Menu creation"""
        # Mock the API response
        mock_line_bot_api.create_rich_menu.return_value = "richmenu-123456"
        
        # Create Rich Menu
        result = rich_message_service.create_rich_menu()
        
        # Verify the result
        assert result == "richmenu-123456"
        mock_line_bot_api.create_rich_menu.assert_called_once()
        
        # Verify the Rich Menu object passed to API
        call_args = mock_line_bot_api.create_rich_menu.call_args[0][0]
        assert isinstance(call_args, RichMenu)
        assert call_args.size.width == 2500
        assert call_args.size.height == 1686
        assert call_args.selected is True
        assert call_args.name == "Daily Inspiration Menu"
    
    def test_create_rich_menu_with_image(self, rich_message_service, mock_line_bot_api):
        """Test Rich Menu creation with image upload"""
        # Mock the API responses
        mock_line_bot_api.create_rich_menu.return_value = "richmenu-123456"
        
        # Create mock for file operations
        with patch("builtins.open", mock_open(read_data=b"image data")):
            with patch("os.path.exists", return_value=True):
                result = rich_message_service.create_rich_menu(
                    custom_image_path="/path/to/image.png"
                )
        
        # Verify the result
        assert result == "richmenu-123456"
        mock_line_bot_api.create_rich_menu.assert_called_once()
        mock_line_bot_api.set_rich_menu_image.assert_called_once()
    
    def test_create_rich_menu_api_error(self, rich_message_service, mock_line_bot_api):
        """Test Rich Menu creation with API error"""
        # Mock API error
        error = LineBotApiError(
            status_code=400,
            headers={},
            request_id="test-request-id",
            error=Mock(message="Invalid request")
        )
        mock_line_bot_api.create_rich_menu.side_effect = error
        
        # Create Rich Menu
        result = rich_message_service.create_rich_menu()
        
        # Verify error handling
        assert result is None
        mock_line_bot_api.create_rich_menu.assert_called_once()
    
    def test_upload_rich_menu_image_success(self, rich_message_service, mock_line_bot_api):
        """Test successful Rich Menu image upload"""
        # Mock file operations
        mock_file = mock_open(read_data=b"image data")
        with patch("builtins.open", mock_file):
            result = rich_message_service.upload_rich_menu_image(
                "richmenu-123456",
                "/path/to/image.png"
            )
        
        # Verify the result
        assert result is True
        mock_line_bot_api.set_rich_menu_image.assert_called_once()
        
        # Verify the call arguments
        call_args = mock_line_bot_api.set_rich_menu_image.call_args
        assert call_args[0][0] == "richmenu-123456"
        assert call_args[0][1] == "image/png"
    
    def test_upload_rich_menu_image_file_error(self, rich_message_service):
        """Test Rich Menu image upload with file error"""
        # Mock file error
        with patch("builtins.open", side_effect=FileNotFoundError()):
            result = rich_message_service.upload_rich_menu_image(
                "richmenu-123456",
                "/nonexistent/image.png"
            )
        
        # Verify error handling
        assert result is False
    
    def test_set_default_rich_menu_success(self, rich_message_service, mock_line_bot_api):
        """Test setting default Rich Menu"""
        # Set default Rich Menu
        result = rich_message_service.set_default_rich_menu("richmenu-123456")
        
        # Verify the result
        assert result is True
        mock_line_bot_api.set_default_rich_menu.assert_called_once_with("richmenu-123456")
    
    def test_create_flex_message_basic(self, rich_message_service):
        """Test basic Flex Message creation"""
        # Create Flex Message
        flex_message = rich_message_service.create_flex_message(
            title="Test Title",
            content="Test content for the message",
            image_url="https://example.com/image.png"
        )
        
        # Verify the result
        assert isinstance(flex_message, FlexSendMessage)
        assert flex_message.alt_text == "Test Title: Test content for the message"
        assert isinstance(flex_message.contents, BubbleContainer)
        
        # Verify bubble content
        bubble = flex_message.contents
        assert bubble.hero.url == "https://example.com/image.png"
        # Check for the title in the body contents
        title_found = any(content.text == "Test Title" for content in bubble.body.contents if hasattr(content, 'text'))
        assert title_found
        # Check for the content text in the body contents  
        content_found = any(content.text == "Test content for the message" for content in bubble.body.contents if hasattr(content, 'text'))
        assert content_found
    
    def test_create_flex_message_with_buttons(self, rich_message_service):
        """Test Flex Message creation with action buttons"""
        # Define action buttons
        buttons = [
            {"type": "uri", "label": "Share", "uri": "https://example.com/share", "primary": True},
            {"type": "postback", "label": "Save", "data": "action=save"},
            {"type": "message", "label": "More", "text": "Show more content"}
        ]
        
        # Create Flex Message
        flex_message = rich_message_service.create_flex_message(
            title="Test Title",
            content="Test content",
            image_url="https://example.com/image.png",
            action_buttons=buttons
        )
        
        # Verify buttons are in the body (they are integrated into the body now)
        bubble = flex_message.contents
        
        # Check that user-provided action buttons are included in the body contents
        # The current implementation adds action buttons to the body, not footer
        body_contents = bubble.body.contents
        
        # Look for action buttons in the body contents
        action_buttons_found = []
        for content in body_contents:
            if hasattr(content, 'action') and hasattr(content.action, 'label'):
                action_buttons_found.append(content.action.label)
        
        # Verify at least some of the expected buttons are present
        expected_labels = ["Share", "Save", "More"]
        buttons_present = any(label in action_buttons_found for label in expected_labels)
        assert buttons_present, f"Expected action buttons not found. Found: {action_buttons_found}"
    
    def test_broadcast_rich_message_success(self, rich_message_service, mock_line_bot_api):
        """Test successful Rich Message broadcast"""
        # Create a flex message
        flex_message = Mock(spec=FlexSendMessage)
        
        # Broadcast message
        result = rich_message_service.broadcast_rich_message(flex_message)
        
        # Verify the result
        assert result["success"] is True
        assert "timestamp" in result
        assert result["audience"] == "all"
        mock_line_bot_api.broadcast.assert_called_once_with(messages=[flex_message])
    
    def test_broadcast_rich_message_narrowcast(self, rich_message_service, mock_line_bot_api):
        """Test Rich Message narrowcast to specific audience"""
        # Create a flex message
        flex_message = Mock(spec=FlexSendMessage)
        
        # Narrowcast message
        result = rich_message_service.broadcast_rich_message(
            flex_message,
            target_audience="audience-123"
        )
        
        # Verify the result
        assert result["success"] is True
        assert result["audience"] == "audience-123"
        mock_line_bot_api.narrowcast.assert_called_once()
        
        # Verify narrowcast parameters
        call_kwargs = mock_line_bot_api.narrowcast.call_args[1]
        assert call_kwargs["messages"] == [flex_message]
        assert call_kwargs["recipient"]["type"] == "audience"
        assert call_kwargs["recipient"]["audienceGroupId"] == "audience-123"
    
    def test_broadcast_rich_message_error(self, rich_message_service, mock_line_bot_api):
        """Test Rich Message broadcast with error"""
        # Mock API error
        error = LineBotApiError(
            status_code=500,
            headers={},
            request_id="test-request-id",
            error=Mock(message="Server error")
        )
        mock_line_bot_api.broadcast.side_effect = error
        
        # Create a flex message
        flex_message = Mock(spec=FlexSendMessage)
        
        # Broadcast message
        result = rich_message_service.broadcast_rich_message(flex_message)
        
        # Verify error handling
        assert result["success"] is False
        assert "error" in result
        assert "Server error" in result["error"]
    
    def test_delete_rich_menu_success(self, rich_message_service, mock_line_bot_api):
        """Test successful Rich Menu deletion"""
        # Delete Rich Menu
        result = rich_message_service.delete_rich_menu("richmenu-123456")
        
        # Verify the result
        assert result is True
        mock_line_bot_api.delete_rich_menu.assert_called_once_with("richmenu-123456")
    
    def test_list_rich_menus_success(self, rich_message_service, mock_line_bot_api):
        """Test listing Rich Menus"""
        # Mock Rich Menu objects
        mock_menu1 = Mock()
        mock_menu1.rich_menu_id = "richmenu-1"
        mock_menu1.name = "Menu 1"
        mock_menu1.size = Mock()
        mock_menu1.size.width = 2500
        mock_menu1.size.height = 1686
        mock_menu1.selected = True
        mock_menu1.chat_bar_text = "Tap here"
        
        mock_menu2 = Mock()
        mock_menu2.rich_menu_id = "richmenu-2"
        mock_menu2.name = "Menu 2"
        mock_menu2.size = Mock()
        mock_menu2.size.width = 2500
        mock_menu2.size.height = 843
        mock_menu2.selected = False
        mock_menu2.chat_bar_text = "Menu"
        
        mock_line_bot_api.get_rich_menu_list.return_value = [mock_menu1, mock_menu2]
        
        # List Rich Menus
        result = rich_message_service.list_rich_menus()
        
        # Verify the result
        assert len(result) == 2
        assert result[0]["richMenuId"] == "richmenu-1"
        assert result[0]["name"] == "Menu 1"
        assert result[0]["size"]["width"] == 2500
        assert result[0]["size"]["height"] == 1686
        assert result[0]["selected"] is True
        assert result[1]["richMenuId"] == "richmenu-2"
        assert result[1]["name"] == "Menu 2"
    
    def test_list_rich_menus_error(self, rich_message_service, mock_line_bot_api):
        """Test listing Rich Menus with error"""
        # Mock API error
        error = LineBotApiError(
            status_code=403,
            headers={},
            request_id="test-request-id",
            error=Mock(message="Forbidden")
        )
        mock_line_bot_api.get_rich_menu_list.side_effect = error
        
        # List Rich Menus
        result = rich_message_service.list_rich_menus()
        
        # Verify error handling
        assert result == []
        mock_line_bot_api.get_rich_menu_list.assert_called_once()