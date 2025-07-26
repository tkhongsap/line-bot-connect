#!/usr/bin/env python3
"""
Quick Rich Message Test - Simple and Working

This is a simplified version that quickly tests rich message automation.
Just set your USER_ID and run!

Usage:
python quick_rich_test.py                    # Safe mock test
python quick_rich_test.py --send             # Actually send message
python quick_rich_test.py --user U123...     # Test with specific user ID
"""

import sys
import os
import random
from datetime import datetime

# Add src to path
sys.path.append('/home/runner/workspace/src')

# Quick configuration - set your LINE User ID here
YOUR_USER_ID = "YOUR_LINE_USER_ID_HERE"

def quick_test(user_id=None, send_mode=False):
    """Quick test of rich message system"""
    
    target_user = user_id or YOUR_USER_ID
    
    print("🚀 QUICK RICH MESSAGE TEST")
    print("=" * 30)
    print(f"📱 Target: {target_user}")
    print(f"📤 Mode: {'LIVE' if send_mode else 'MOCK'}")
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
        
        # Check for Little Prince template
        template_path = "/home/runner/workspace/templates/rich_messages/backgrounds/general_motivation_inspiration_prince_01_v1.jpg"
        
        if not os.path.exists(template_path):
            print(f"⚠️  Template not found, using backup...")
            # Try backup templates
            backup_templates = [
                "/home/runner/workspace/templates/rich_messages/backgrounds/general_motivation_motivation_lion_01_v1.jpg",
                "/home/runner/workspace/templates/rich_messages/backgrounds/morning_energy_inspiration_uplifting_01_v1.jpg"
            ]
            template_path = None
            for backup in backup_templates:
                if os.path.exists(backup):
                    template_path = backup
                    break
            
            if not template_path:
                print("❌ No templates found")
                return False
        
        print(f"✅ Template: {os.path.basename(template_path)}")
        
        # Create content
        quotes = [
            "What is essential is invisible to the eye.",
            "Every day is a new beginning.",
            "Believe in yourself and magic happens.",
            "Your potential is endless."
        ]
        
        content = {
            "title": "🌟 Daily Inspiration",
            "content": f'"{random.choice(quotes)}"\n\nLet this message brighten your day! ✨',
            "template_path": template_path
        }
        
        print("✅ Content created")
        
        # Create Rich Message
        flex_message = rich_service.create_flex_message(
            title=content["title"],
            content=content["content"],
            image_path=content["template_path"],
            content_id=f"quick_test_{int(datetime.now().timestamp())}",
            user_id=target_user,
            include_interactions=True
        )
        
        if not flex_message:
            print("❌ Failed to create Rich Message")
            return False
        
        print("✅ Rich Message created")
        
        # Send
        if send_mode:
            print("🔴 SENDING...")
            line_bot_api.push_message(target_user, flex_message)
            print("✅ Message sent! Check your LINE app!")
        else:
            print("🟡 Mock send successful")
            line_bot_api.push_message(target_user, flex_message)
        
        print()
        print("📊 Summary:")
        print(f"   👤 Recipient: {target_user}")
        print(f"   🎨 Template: {os.path.basename(template_path)}")
        print(f"   📱 Interactive: Yes (Like, Share, Save, React)")
        print(f"   📤 Status: {'Sent' if send_mode else 'Mock'}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
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
            print("Quick Rich Message Test")
            print()
            print("Usage:")
            print("  python quick_rich_test.py                    # Safe mock test")
            print("  python quick_rich_test.py --send             # Actually send")
            print("  python quick_rich_test.py --user U123...     # Specific user")
            print("  python quick_rich_test.py U123... --send     # Send to user")
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
    success = quick_test(user_id, send_mode)
    
    print()
    if success:
        print("🎉 Test completed successfully!")
    else:
        print("❌ Test failed")

if __name__ == "__main__":
    main()