#!/usr/bin/env python3
"""
Send Rich Message with Different Template

This test sends Rich Messages with different templates to showcase variety.
"""

import sys
import os
from datetime import datetime

# Add src to path
sys.path.append('/home/runner/workspace/src')

def send_variety_rich_message():
    """Send Rich Messages with different templates"""
    
    print("🎨 SENDING VARIETY RICH MESSAGE TEST")
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
            base_url='https://line-bot-connect-tkhongsap.replit.app'
        )
        
        # Test with a different template this time
        template_options = [
            ("wellness_nature_spirits.png", "🌿 Mindful Monday", "Take a moment to breathe deeply and connect with nature. Even a few minutes of mindfulness can transform your entire day. Find peace in the present moment! 🧘‍♀️✨"),
            ("motivation_abstract_geometric.png", "🎯 Focus Power", "Success happens when preparation meets opportunity. Stay focused on your goals, eliminate distractions, and take consistent action. You've got this! 💪"),
            ("inspiration_creative_minimal.png", "✨ Creative Flow", "Innovation comes from thinking differently. Let your creativity flow freely today and explore new possibilities. Your unique perspective is your superpower! 🎨")
        ]
        
        # Use a different template than the coffee one
        template_name, title, content = template_options[0]  # Nature/wellness theme
        template_path = f"/home/runner/workspace/templates/rich_messages/backgrounds/{template_name}"
        
        if not os.path.exists(template_path):
            print(f"❌ Template not found: {template_path}")
            return False
        
        file_size = os.path.getsize(template_path)
        print(f"✅ Using template: {template_name} ({file_size:,} bytes)")
        print(f"📋 Title: {title}")
        print(f"💼 Content: {content[:60]}...")
        
        # Create Rich Message
        flex_message = rich_service.create_flex_message(
            title=title,
            content=content,
            image_path=template_path,
            content_id=f"variety_test_{int(datetime.now().timestamp())}",
            user_id="U595491d702720bc7c90d50618324cac3",
            include_interactions=True
        )
        
        print("✅ Rich Message created with nature/wellness theme")
        
        # Verify the structure
        flex_dict = flex_message.as_json_dict()
        bubble = flex_dict.get('contents', {})
        hero = bubble.get('hero', {})
        
        if hero and hero.get('url'):
            print(f"✅ Background image URL: {hero['url']}")
        
        # Send the message
        print("📤 Sending wellness-themed Rich Message...")
        line_service.line_bot_api.push_message("U595491d702720bc7c90d50618324cac3", flex_message)
        print("🎉 Wellness Rich Message sent successfully!")
        
        print("\n📱 CHECK YOUR LINE APP FOR:")
        print("   🌿 Nature/wellness background image")
        print("   🧘‍♀️ Mindfulness-focused content")
        print("   🔘 Interactive engagement buttons")
        print("   ✨ Different visual theme from coffee template")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed: {str(e)}")
        return False

if __name__ == "__main__":
    send_variety_rich_message()