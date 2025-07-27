"""
Rich Message Service for LINE Bot automation

This service handles the creation, management, and delivery of Rich Messages
with automated content generation and template-based graphics.
"""

import json
import logging
import os
from typing import Dict, List, Optional, Any
from datetime import datetime
from linebot.models import (
    RichMenu, RichMenuSize, RichMenuArea, RichMenuBounds,
    PostbackAction, URIAction, MessageAction,
    FlexSendMessage, BubbleContainer, ImageComponent,
    BoxComponent, TextComponent, ButtonComponent
)
from linebot.exceptions import LineBotApiError

logger = logging.getLogger(__name__)


class RichMessageService:
    """Service for managing Rich Message automation and delivery"""
    
    def __init__(self, line_bot_api, template_manager=None, content_generator=None, base_url=None):
        """
        Initialize Rich Message Service
        
        Args:
            line_bot_api: LINE Bot API instance for sending messages
            template_manager: Template management utility (optional, will be implemented later)
            content_generator: Content generation utility (optional, will be implemented later)
            base_url: Base URL for generating image links (optional)
        """
        self.line_bot_api = line_bot_api
        self.template_manager = template_manager
        self.content_generator = content_generator
        self.base_url = base_url
        
        # Rich Menu dimensions for LINE
        self.RICH_MENU_WIDTH = 2500
        self.RICH_MENU_HEIGHT = 1686
        
        # Initialize Rich Menu configurations
        self._rich_menu_configs = self._load_rich_menu_configs()
        
        logger.info("RichMessageService initialized")
    
    def _get_base_url(self) -> str:
        """Get the base URL for generating image links"""
        if self.base_url:
            return self.base_url.rstrip('/')
        
        try:
            from flask import request
            if hasattr(request, 'host_url'):
                return request.host_url.rstrip('/')
        except:
            pass
        
        # Fallback to environment variable or default
        return os.environ.get('BASE_URL', 'https://line-bot-connect.replit.app')
    
    def _load_rich_menu_configs(self) -> Dict[str, Any]:
        """Load Rich Menu configuration templates"""
        return {
            "default": {
                "size": RichMenuSize(width=self.RICH_MENU_WIDTH, height=self.RICH_MENU_HEIGHT),
                "selected": True,
                "name": "Daily Inspiration Menu",
                "chatBarText": "Tap for menu",
                "areas": [
                    # Full image tap area for main content interaction
                    RichMenuArea(
                        bounds=RichMenuBounds(x=0, y=0, width=self.RICH_MENU_WIDTH, height=self.RICH_MENU_HEIGHT),
                        action=PostbackAction(
                            label="View Content",
                            data="action=view_content&menu=daily_inspiration"
                        )
                    )
                ]
            }
        }
    
    def create_rich_menu(self, menu_type: str = "default", custom_image_path: Optional[str] = None) -> Optional[str]:
        """
        Create a new Rich Menu with specified configuration
        
        Args:
            menu_type: Type of menu configuration to use
            custom_image_path: Optional custom image path for the menu
            
        Returns:
            Rich Menu ID if successful, None otherwise
        """
        try:
            # Get menu configuration
            config = self._rich_menu_configs.get(menu_type, self._rich_menu_configs["default"])
            
            # Create Rich Menu object
            rich_menu = RichMenu(
                size=config["size"],
                selected=config["selected"],
                name=config["name"],
                chat_bar_text=config["chatBarText"],
                areas=config["areas"]
            )
            
            # Create the Rich Menu
            rich_menu_id = self.line_bot_api.create_rich_menu(rich_menu)
            logger.info(f"Created Rich Menu with ID: {rich_menu_id}")
            
            # Upload image if provided
            if custom_image_path and os.path.exists(custom_image_path):
                self.upload_rich_menu_image(rich_menu_id, custom_image_path)
            
            return rich_menu_id
            
        except LineBotApiError as e:
            logger.error(f"Failed to create Rich Menu: {e.status_code} - {e.error.message}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error creating Rich Menu: {str(e)}")
            return None
    
    def upload_rich_menu_image(self, rich_menu_id: str, image_path: str) -> bool:
        """
        Upload an image to a Rich Menu
        
        Args:
            rich_menu_id: ID of the Rich Menu
            image_path: Path to the image file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with open(image_path, 'rb') as f:
                self.line_bot_api.set_rich_menu_image(rich_menu_id, 'image/png', f)
            
            logger.info(f"Uploaded image to Rich Menu {rich_menu_id}")
            return True
            
        except LineBotApiError as e:
            logger.error(f"Failed to upload Rich Menu image: {e.status_code} - {e.error.message}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error uploading Rich Menu image: {str(e)}")
            return False
    
    def set_default_rich_menu(self, rich_menu_id: str) -> bool:
        """
        Set a Rich Menu as the default for all users
        
        Args:
            rich_menu_id: ID of the Rich Menu to set as default
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.line_bot_api.set_default_rich_menu(rich_menu_id)
            logger.info(f"Set Rich Menu {rich_menu_id} as default")
            return True
            
        except LineBotApiError as e:
            logger.error(f"Failed to set default Rich Menu: {e.status_code} - {e.error.message}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error setting default Rich Menu: {str(e)}")
            return False
    
    def create_flex_message(self, 
                          title: str, 
                          content: str, 
                          image_url: Optional[str] = None,
                          image_path: Optional[str] = None,
                          content_id: Optional[str] = None,
                          user_id: Optional[str] = None,
                          action_buttons: Optional[List[Dict[str, str]]] = None,
                          include_interactions: bool = True) -> FlexSendMessage:
        """
        Create a Flex Message for rich content display with interactive features.
        
        Args:
            title: Message title
            content: Message content text
            image_url: URL of the header image (optional)
            image_path: Local path to image (optional, for upload)
            content_id: Unique identifier for this content (for interactions)
            user_id: Current user ID (for personalized interactions)
            action_buttons: Optional list of custom action buttons
            include_interactions: Whether to include interaction buttons
            
        Returns:
            FlexSendMessage object
        """
        from src.utils.interaction_handler import get_interaction_handler
        import uuid
        
        # Generate content ID if not provided
        if not content_id:
            content_id = str(uuid.uuid4())
        
        # Prepare image component
        hero_component = None
        if image_url:
            hero_component = ImageComponent(
                url=image_url,
                size="full",
                aspect_ratio="20:13",
                aspect_mode="cover"
            )
        elif image_path:
            # Convert local image path to public URL using our static route
            try:
                # Extract filename from path
                filename = os.path.basename(image_path)
                
                # Generate public URL using the static route we added
                base_url = self._get_base_url()
                public_image_url = f"{base_url}/static/backgrounds/{filename}"
                
                hero_component = ImageComponent(
                    url=public_image_url,
                    size="full",
                    aspect_ratio="20:13", 
                    aspect_mode="cover"
                )
                logger.info(f"Generated image URL for {filename}: {public_image_url}")
                
            except Exception as e:
                logger.error(f"Failed to generate image URL for {image_path}: {str(e)}")
                hero_component = None
        
        # Create body content
        body_contents = [
            TextComponent(
                text=title,
                weight="bold",
                size="xl",
                wrap=True,
                color="#333333"
            ),
            TextComponent(text=" ", size="xs"),  # Spacer replacement
            TextComponent(
                text=content,
                size="md",
                wrap=True,
                color="#666666"
            )
        ]
        
        # Add interaction buttons if enabled
        if include_interactions and content_id:
            try:
                interaction_handler = get_interaction_handler()
                interactive_buttons = interaction_handler.create_interactive_buttons(
                    content_id=content_id,
                    current_user_id=user_id,
                    include_stats=True
                )
                
                if interactive_buttons:
                    body_contents.append(TextComponent(text=" ", size="sm"))  # Spacer replacement
                    
                    # Create button components in rows of 2
                    button_rows = []
                    for i in range(0, len(interactive_buttons), 2):
                        row_buttons = interactive_buttons[i:i+2]
                        
                        button_components = []
                        for button in row_buttons:
                            if button.get("type") == "uri":
                                action = URIAction(label=button["label"], uri=button["uri"])
                            elif button.get("type") == "postback":
                                action = PostbackAction(label=button["label"], data=button["data"])
                            else:
                                action = MessageAction(label=button["label"], text=button.get("text", button["label"]))
                            
                            button_components.append(
                                ButtonComponent(
                                    action=action,
                                    style=button.get("style", "secondary"),
                                    height="sm",
                                    flex=1
                                )
                            )
                        
                        # Create horizontal box for button row
                        button_row = BoxComponent(
                            layout="horizontal",
                            contents=button_components,
                            spacing="sm"
                        )
                        button_rows.append(button_row)
                    
                    # Add button rows to body
                    for row in button_rows:
                        body_contents.append(row)
                        if row != button_rows[-1]:  # Add spacing between rows
                            body_contents.append(TextComponent(text=" ", size="xs"))  # Spacer replacement
                            
            except Exception as e:
                logger.error(f"Failed to create interactive buttons: {str(e)}")
        
        # Add custom action buttons if provided
        if action_buttons:
            if not (include_interactions and content_id):  # Only add spacer if no interaction buttons
                body_contents.append(TextComponent(text=" ", size="sm"))  # Spacer replacement
            
            custom_button_components = []
            for button in action_buttons:
                if button.get("type") == "uri":
                    action = URIAction(label=button["label"], uri=button["uri"])
                elif button.get("type") == "postback":
                    action = PostbackAction(label=button["label"], data=button["data"])
                else:
                    action = MessageAction(label=button["label"], text=button.get("text", button["label"]))
                
                custom_button_components.append(
                    ButtonComponent(
                        action=action,
                        style="primary" if button.get("primary") else "secondary",
                        height="sm"
                    )
                )
            
            # Add custom buttons
            for button in custom_button_components:
                body_contents.append(TextComponent(text=" ", size="xs"))  # Spacer replacement
                body_contents.append(button)
        
        # Create bubble container
        bubble_kwargs = {
            "body": BoxComponent(
                layout="vertical",
                contents=body_contents,
                spacing="none",
                margin="lg"
            )
        }
        
        # Add hero image if available
        if hero_component:
            bubble_kwargs["hero"] = hero_component
        
        bubble = BubbleContainer(**bubble_kwargs)
        
        return FlexSendMessage(
            alt_text=f"{title}: {content[:50]}..." if len(content) > 50 else f"{title}: {content}",
            contents=bubble
        )
    
    def broadcast_rich_message(self, 
                             flex_message: FlexSendMessage,
                             target_audience: Optional[str] = None) -> Dict[str, Any]:
        """
        Broadcast a Rich Message to users
        
        Args:
            flex_message: The Flex Message to broadcast
            target_audience: Optional audience ID for targeted broadcasting
            
        Returns:
            Result dictionary with success status and details
        """
        try:
            if target_audience:
                # Narrowcast to specific audience
                self.line_bot_api.narrowcast(
                    messages=[flex_message],
                    recipient={"type": "audience", "audienceGroupId": target_audience}
                )
                logger.info(f"Narrowcast Rich Message to audience {target_audience}")
            else:
                # Broadcast to all users
                self.line_bot_api.broadcast(messages=[flex_message])
                logger.info("Broadcast Rich Message to all users")
            
            return {
                "success": True,
                "timestamp": datetime.now().isoformat(),
                "audience": target_audience or "all"
            }
            
        except LineBotApiError as e:
            error_msg = f"Failed to broadcast Rich Message: {e.status_code} - {e.error.message}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            error_msg = f"Unexpected error broadcasting Rich Message: {str(e)}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "timestamp": datetime.now().isoformat()
            }
    
    def delete_rich_menu(self, rich_menu_id: str) -> bool:
        """
        Delete a Rich Menu
        
        Args:
            rich_menu_id: ID of the Rich Menu to delete
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.line_bot_api.delete_rich_menu(rich_menu_id)
            logger.info(f"Deleted Rich Menu {rich_menu_id}")
            return True
            
        except LineBotApiError as e:
            logger.error(f"Failed to delete Rich Menu: {e.status_code} - {e.error.message}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error deleting Rich Menu: {str(e)}")
            return False
    
    def list_rich_menus(self) -> List[Dict[str, Any]]:
        """
        List all Rich Menus
        
        Returns:
            List of Rich Menu information dictionaries
        """
        try:
            rich_menus = self.line_bot_api.get_rich_menu_list()
            menu_list = []
            
            for menu in rich_menus:
                menu_list.append({
                    "richMenuId": menu.rich_menu_id,
                    "name": menu.name,
                    "size": {
                        "width": menu.size.width,
                        "height": menu.size.height
                    },
                    "selected": menu.selected,
                    "chatBarText": menu.chat_bar_text
                })
            
            logger.info(f"Listed {len(menu_list)} Rich Menus")
            return menu_list
            
        except LineBotApiError as e:
            logger.error(f"Failed to list Rich Menus: {e.status_code} - {e.error.message}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error listing Rich Menus: {str(e)}")
            return []