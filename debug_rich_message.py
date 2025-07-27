#!/usr/bin/env python3
"""
Debug Rich Message Creation

This script adds detailed logging to understand why the background image
is not being included in the hero component.
"""

import sys
import os
import logging
from datetime import datetime

# Add src to path
sys.path.append('/home/runner/workspace/src')

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

def debug_rich_message_creation():
    """Debug the Rich Message creation process"""
    
    print("🐛 DEBUGGING RICH MESSAGE CREATION")
    print("=" * 50)
    
    try:
        from src.services.rich_message_service import RichMessageService
        from src.services.line_service import LineService
        from src.services.openai_service import OpenAIService
        from src.services.conversation_service import ConversationService
        from src.config.settings import Settings
        
        # Initialize services
        settings = Settings()
        conversation_service = ConversationService()
        openai_service = OpenAIService(settings, conversation_service)
        line_service = LineService(settings, openai_service, conversation_service)
        
        rich_service = RichMessageService(
            line_bot_api=line_service.line_bot_api,
            base_url='https://line-bot-connect.replit.app'
        )
        
        # Test template
        template_name = "productivity_monday_coffee.png"
        template_path = f"/home/runner/workspace/templates/rich_messages/backgrounds/{template_name}"
        
        print(f"🖼️ Template path: {template_path}")
        print(f"🔍 File exists: {os.path.exists(template_path)}")
        
        if os.path.exists(template_path):
            file_size = os.path.getsize(template_path)
            print(f"📏 File size: {file_size:,} bytes")
        
        # Test base URL generation
        base_url = rich_service._get_base_url()
        print(f"🌐 Base URL: {base_url}")
        
        # Manually test the image URL generation logic
        filename = os.path.basename(template_path)
        public_image_url = f"{base_url}/static/backgrounds/{filename}"
        print(f"🔗 Generated URL: {public_image_url}")
        
        # Test content
        title = "🚀 Debug Test"
        content = "Testing background image functionality with detailed debugging."
        
        print(f"📋 Title: {title}")
        print(f"💼 Content: {content}")
        
        # Create Rich Message with detailed logging
        print("\n🎨 Creating Rich Message...")
        print("Parameters:")
        print(f"  - title: {title}")
        print(f"  - content: {content}")
        print(f"  - image_path: {template_path}")
        print(f"  - content_id: debug_test")
        print(f"  - user_id: debug_user")
        print(f"  - include_interactions: True")
        
        # Get the module logger
        import src.services.rich_message_service as rms_module
        module_logger = logging.getLogger('src.services.rich_message_service')
        
        # Add a custom handler for debugging
        class DebugHandler(logging.Handler):
            def emit(self, record):
                print(f"🔍 LOG [{record.levelname}]: {record.getMessage()}")
        
        debug_handler = DebugHandler()
        module_logger.addHandler(debug_handler)
        module_logger.setLevel(logging.DEBUG)
        
        flex_message = rich_service.create_flex_message(
            title=title,
            content=content,
            image_path=template_path,
            content_id="debug_test",
            user_id="debug_user",
            include_interactions=True
        )
        
        print("✅ Rich Message created")
        
        # Inspect the result
        flex_dict = flex_message.as_json_dict()
        bubble = flex_dict.get('contents', {})
        hero = bubble.get('hero', {})
        
        print(f"\n🔍 Flex Message Structure:")
        print(f"  - Alt text: {flex_dict.get('altText', 'Not set')}")
        print(f"  - Bubble type: {bubble.get('type', 'Not set')}")
        print(f"  - Hero present: {'Yes' if hero else 'No'}")
        
        if hero:
            print(f"  - Hero URL: {hero.get('url', 'Not set')}")
            print(f"  - Hero size: {hero.get('size', 'Not set')}")
            print(f"  - Hero aspect ratio: {hero.get('aspectRatio', 'Not set')}")
        else:
            print("  - No hero component found")
        
        body = bubble.get('body', {})
        contents = body.get('contents', [])
        print(f"  - Body contents count: {len(contents)}")
        
        # Print first few contents for debugging
        for i, content_item in enumerate(contents[:3]):
            print(f"    [{i}] Type: {content_item.get('type', 'Unknown')}")
            if content_item.get('type') == 'text':
                text = content_item.get('text', '')[:30]
                print(f"        Text: {text}...")
        
        return flex_message
        
    except Exception as e:
        print(f"❌ Debug failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    debug_rich_message_creation()