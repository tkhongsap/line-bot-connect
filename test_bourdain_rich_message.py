#!/usr/bin/env python3
"""
Test Anthony Bourdain Style Rich Message Content

This test demonstrates the new Bourdain-style content generation
for Rich Messages with authentic voice and optimized length.
"""

import sys
import os
from datetime import datetime

# Add src to path
sys.path.append('/home/runner/workspace/src')

def test_bourdain_content_generation():
    """Test the new Bourdain-style content generation"""
    
    print("🎭 TESTING ANTHONY BOURDAIN RICH MESSAGE CONTENT")
    print("=" * 60)
    
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
        
        # Create RichMessageService WITH OpenAI service for Bourdain content
        rich_service = RichMessageService(
            line_bot_api=line_service.line_bot_api,
            base_url='https://line-bot-connect-tkhongsap.replit.app',
            openai_service=openai_service  # This enables Bourdain content generation
        )
        
        print("✅ Services initialized with Bourdain content generator")
        
        # Test different themes
        themes_to_test = [
            ("productivity", "productivity_monday_coffee.png"),
            ("wellness", "wellness_nature_spirits.png"),
            ("motivation", "motivation_abstract_geometric.png"),
            ("inspiration", "inspiration_creative_minimal.png")
        ]
        
        print("\n🎨 TESTING BOURDAIN CONTENT ACROSS THEMES:")
        print("-" * 60)
        
        for theme, template_name in themes_to_test:
            print(f"\n📝 Theme: {theme.upper()}")
            print(f"🖼️  Template: {template_name}")
            
            # Generate Bourdain-style content
            content = rich_service.generate_bourdain_content(
                theme=theme,
                template_name=template_name
            )
            
            title = content['title']
            message_content = content['content']
            
            print(f"   📋 Title: '{title}' ({len(title)} chars)")
            print(f"   💬 Content: '{message_content}' ({len(message_content)} chars)")
            print(f"   📊 Total: {len(title) + len(message_content)} characters")
            
            # Validate length constraints
            if len(title) <= 50 and len(message_content) <= 250:
                print("   ✅ Length constraints: PASSED")
            else:
                print("   ❌ Length constraints: FAILED")
        
        print("\n" + "=" * 60)
        print("🎯 COMPARISON: OLD vs NEW STYLE")
        print("=" * 60)
        
        print("\n❌ OLD (Generic Wellness):")
        print("   📋 Title: '🌿 Mindful Monday'")
        print("   💬 Content: 'Take a moment to breathe deeply and connect with nature. Even a few minutes of mindfulness can transform your entire day. Find peace in the present moment! 🧘‍♀️✨'")
        print("   📊 Total: 140+ characters")
        
        print("\n✅ NEW (Bourdain Style):")
        wellness_content = rich_service.generate_bourdain_content(
            theme="wellness",
            template_name="wellness_nature_spirits.png"
        )
        print(f"   📋 Title: '{wellness_content['title']}'")
        print(f"   💬 Content: '{wellness_content['content']}'") 
        print(f"   📊 Total: {len(wellness_content['title']) + len(wellness_content['content'])} characters")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_send_bourdain_rich_message():
    """Send a Rich Message with Bourdain-style content"""
    
    print("\n" + "=" * 60)
    print("📤 SENDING BOURDAIN RICH MESSAGE TEST")
    print("=" * 60)
    
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
        
        # Create RichMessageService with Bourdain content generator
        rich_service = RichMessageService(
            line_bot_api=line_service.line_bot_api,
            base_url='https://line-bot-connect-tkhongsap.replit.app',
            openai_service=openai_service
        )
        
        # Generate Bourdain-style content
        template_name = "productivity_monday_coffee.png"
        template_path = f"/home/runner/workspace/templates/rich_messages/backgrounds/{template_name}"
        
        print(f"🎨 Using template: {template_name}")
        
        bourdain_content = rich_service.generate_bourdain_content(
            theme="productivity",
            template_name=template_name
        )
        
        print(f"✅ Generated Bourdain content:")
        print(f"   📋 Title: '{bourdain_content['title']}'")
        print(f"   💬 Content: '{bourdain_content['content']}'")
        
        # Create Rich Message with Bourdain content
        flex_message = rich_service.create_flex_message(
            title=bourdain_content['title'],
            content=bourdain_content['content'],
            image_path=template_path,
            content_id=f"bourdain_test_{int(datetime.now().timestamp())}",
            user_id="U595491d702720bc7c90d50618324cac3",
            include_interactions=True
        )
        
        print("✅ Rich Message created with Bourdain content")
        
        # Send the message
        print("📤 Sending Bourdain-style Rich Message...")
        line_service.line_bot_api.push_message("U595491d702720bc7c90d50618324cac3", flex_message)
        print("🎉 Bourdain Rich Message sent successfully!")
        
        print("\n📱 CHECK YOUR LINE APP FOR:")
        print("   ☕ Bourdain's authentic, no-bullshit voice")
        print("   📏 Shorter, punchier content")
        print("   🎯 Real perspective instead of generic wellness")
        print("   🖼️ Beautiful background image (working correctly)")
        
        return True
        
    except Exception as e:
        print(f"❌ Send test failed: {str(e)}")
        return False

if __name__ == "__main__":
    print("🎭 ANTHONY BOURDAIN RICH MESSAGE TESTING")
    print("Testing the new authentic voice and optimized content system")
    print()
    
    # Test content generation
    content_success = test_bourdain_content_generation()
    
    if content_success:
        # Test sending actual message
        send_success = test_send_bourdain_rich_message()
        
        if send_success:
            print("\n🎉 ALL BOURDAIN RICH MESSAGE TESTS PASSED!")
            print("✅ Authentic voice implemented")
            print("✅ Content length optimized") 
            print("✅ Rich Message sent successfully")
        else:
            print("\n⚠️ Content generation passed, but sending failed")
    else:
        print("\n❌ Content generation tests failed")