#!/usr/bin/env python3
"""
Test Inspiration Sticker Template

This script tests the playful inspiration_sticker_01.png template with
cheerful, youth-oriented content that matches its fun theme.

Usage:
python test_sticker_template.py                    # Safe mock test
python test_sticker_template.py --send             # Actually send message
python test_sticker_template.py --user U123...     # Test with specific user ID
"""

import sys
import os
import random
from datetime import datetime

# Add src to path
sys.path.append('/home/runner/workspace/src')

# Configuration - set your LINE User ID here
YOUR_USER_ID = "YOUR_LINE_USER_ID_HERE"

def test_sticker_template(user_id=None, send_mode=False):
    """Test the inspiration sticker template with playful content"""
    
    target_user = user_id or YOUR_USER_ID
    
    print("🎉 TESTING INSPIRATION STICKER TEMPLATE")
    print("=" * 45)
    print(f"📱 Target: {target_user}")
    print(f"📤 Mode: {'LIVE' if send_mode else 'MOCK'}")
    print("🎨 Template: inspiration_sticker_01.png (Playful & Fun)")
    print()
    
    # Validate User ID
    if target_user == "YOUR_LINE_USER_ID_HERE":
        print("❌ Please set YOUR_USER_ID in this script or use --user option")
        print("   Get your User ID: python get_my_user_id.py")
        return False
    
    if not target_user.startswith('U') or len(target_user) != 33:
        print(f"❌ Invalid User ID format: {target_user}")
        print("   Expected: U + 32 characters")
        return False
    
    try:
        # Import services
        from src.services.rich_message_service import RichMessageService
        from src.services.line_service import LineService
        from src.services.openai_service import OpenAIService
        from src.services.conversation_service import ConversationService
        from src.config.settings import Settings
        from unittest.mock import Mock
        
        print("✅ Services imported")
        
        # Initialize services in correct order
        settings = Settings()
        
        if send_mode:
            print("🔴 Real services (will send!)")
            conversation_service = ConversationService()
            openai_service = OpenAIService(settings, conversation_service)
            line_service = LineService(settings, openai_service, conversation_service)
            line_bot_api = line_service.line_bot_api
        else:
            print("🟡 Mock services (safe)")
            line_bot_api = Mock()
            line_bot_api.push_message = Mock()
        
        rich_service = RichMessageService(line_bot_api=line_bot_api)
        print("✅ Services ready")
        
        # Check template
        template_path = "/home/runner/workspace/templates/rich_messages/backgrounds/inspiration_sticker_01.png"
        
        if not os.path.exists(template_path):
            print(f"❌ Template not found: {template_path}")
            return False
        
        file_size = os.path.getsize(template_path)
        print(f"✅ Template found: inspiration_sticker_01.png ({file_size:,} bytes)")
        
        # Create playful, cheerful content matching the sticker theme
        cheerful_quotes = [
            "Life is like a sticker collection - colorful, fun, and full of surprises!",
            "Stick to your dreams and make them sparkle! ✨",
            "Every day is a fresh page waiting for your colorful story!",
            "Be the reason someone smiles today - you're amazing!",
            "Collect moments, not things - and make them all bright!",
            "Your potential is like glitter - it spreads everywhere you go!",
            "Dream big, shine bright, and stick to what makes you happy!",
            "Life's too short for boring days - add some color to everything!"
        ]
        
        fun_tips = [
            "Start your day with a smile and see how it changes everything!",
            "Find three things today that make you laugh out loud!",
            "Send a random compliment to someone - spread the joy!",
            "Dance to your favorite song, even if no one's watching!",
            "Try something new today, no matter how small!",
            "Take a photo of something beautiful you notice today!"
        ]
        
        # Random selection for variety
        selected_quote = random.choice(cheerful_quotes)
        selected_tip = random.choice(fun_tips)
        
        content = {
            "title": "🌈 Daily Fun Boost!",
            "content": f'"{selected_quote}"\n\n💡 Fun Challenge: {selected_tip}\n\nMake today colorful and amazing! 🎉',
            "template_path": template_path
        }
        
        print("✅ Cheerful content created:")
        print(f"   📝 Title: {content['title']}")
        print(f"   💭 Quote: {selected_quote[:50]}...")
        print(f"   🎯 Tip: {selected_tip[:50]}...")
        
        # Create Rich Message with fun interactions
        flex_message = rich_service.create_flex_message(
            title=content["title"],
            content=content["content"],
            image_path=content["template_path"],
            content_id=f"sticker_test_{int(datetime.now().timestamp())}",
            user_id=target_user,
            include_interactions=True
        )
        
        if not flex_message:
            print("❌ Failed to create Rich Message")
            return False
        
        print("✅ Playful Rich Message created with interactive buttons!")
        
        # Send the message
        if send_mode:
            print("🔴 SENDING...")
            line_bot_api.push_message(target_user, flex_message)
            print("🎉 Message sent! Check your LINE app!")
        else:
            print("🟡 Mock send successful")
            line_bot_api.push_message(target_user, flex_message)
        
        print()
        print("📊 Summary:")
        print(f"   👤 Recipient: {target_user}")
        print(f"   🎨 Template: inspiration_sticker_01.png")
        print(f"   🎭 Theme: Playful & Cheerful")
        print(f"   📱 Interactive: Like, Share, Save, React buttons")
        print(f"   📤 Status: {'Sent' if send_mode else 'Mock'}")
        print()
        print("🎮 What to test:")
        print("   💝 Tap Like to show appreciation")
        print("   📤 Tap Share to spread the positivity")  
        print("   💾 Tap Save to keep the inspiration")
        print("   😊 Tap React to add your emoji response")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Parse arguments and run test"""
    
    user_id = None
    send_mode = False
    
    # Parse simple arguments
    for arg in sys.argv[1:]:
        if arg == "--send":
            send_mode = True
        elif arg.startswith("--user"):
            if "=" in arg:
                user_id = arg.split("=", 1)[1]
            else:
                # Next argument should be user ID
                try:
                    idx = sys.argv.index(arg)
                    if idx + 1 < len(sys.argv):
                        user_id = sys.argv[idx + 1]
                except (ValueError, IndexError):
                    pass
        elif arg.startswith("U") and len(arg) == 33:
            user_id = arg
        elif arg in ["--help", "-h"]:
            print("Inspiration Sticker Template Test")
            print()
            print("This template is perfect for:")
            print("- Cheerful morning messages")
            print("- Youth motivation")  
            print("- Fun daily challenges")
            print("- Playful inspiration")
            print()
            print("Usage:")
            print("  python test_sticker_template.py                    # Safe mock test")
            print("  python test_sticker_template.py --send             # Actually send")
            print("  python test_sticker_template.py --user U123...     # Specific user")
            print()
            print("Get your User ID: python get_my_user_id.py")
            return
    
    # Confirm live sending
    if send_mode:
        print("⚠️  LIVE SEND MODE - Message will be sent!")
        try:
            confirm = input("Continue? (y/N): ").strip().lower()
            if confirm not in ['y', 'yes']:
                print("❌ Cancelled")
                return
        except KeyboardInterrupt:
            print("\n❌ Cancelled")
            return
    
    # Run test
    success = test_sticker_template(user_id, send_mode)
    
    print()
    if success:
        print("🎉 Sticker template test completed successfully!")
        if send_mode:
            print("📱 Check your LINE app for the colorful message!")
        else:
            print("🔧 Add --send to actually send the message")
    else:
        print("❌ Test failed")

if __name__ == "__main__":
    main()