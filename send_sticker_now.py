#!/usr/bin/env python3
"""
Direct Send Inspiration Sticker Template

This script sends the playful inspiration sticker template directly
to your LINE account without interactive prompts.
"""

import sys
import os
import random
from datetime import datetime

# Add src to path
sys.path.append('/home/runner/workspace/src')

def send_sticker_message(user_id):
    """Send inspiration sticker message directly"""
    
    print("🎉 SENDING INSPIRATION STICKER MESSAGE")
    print("=" * 40)
    print(f"📱 Target: {user_id}")
    print("🎨 Template: inspiration_sticker_01.png")
    print()
    
    try:
        # Import services
        from src.services.rich_message_service import RichMessageService
        from src.services.line_service import LineService
        from src.services.openai_service import OpenAIService
        from src.services.conversation_service import ConversationService
        from src.config.settings import Settings
        
        print("✅ Services imported")
        
        # Initialize services
        settings = Settings()
        conversation_service = ConversationService()
        openai_service = OpenAIService(settings, conversation_service)
        line_service = LineService(settings, openai_service, conversation_service)
        line_bot_api = line_service.line_bot_api
        
        rich_service = RichMessageService(line_bot_api=line_bot_api)
        print("✅ Services ready")
        
        # Template path
        template_path = "/home/runner/workspace/templates/rich_messages/backgrounds/inspiration_sticker_01.png"
        
        if not os.path.exists(template_path):
            print(f"❌ Template not found: {template_path}")
            return False
        
        print("✅ Template found")
        
        # Create cheerful content
        cheerful_quotes = [
            "Life is like a sticker collection - colorful, fun, and full of surprises!",
            "Stick to your dreams and make them sparkle! ✨",
            "Every day is a fresh page waiting for your colorful story!",
            "Be the reason someone smiles today - you're amazing!",
            "Collect moments, not things - and make them all bright!"
        ]
        
        fun_tips = [
            "Start your day with a smile and see how it changes everything!",
            "Find three things today that make you laugh out loud!",
            "Send a random compliment to someone - spread the joy!",
            "Try something new today, no matter how small!"
        ]
        
        selected_quote = random.choice(cheerful_quotes)
        selected_tip = random.choice(fun_tips)
        
        content = {
            "title": "🌈 Daily Fun Boost!",
            "content": f'"{selected_quote}"\n\n💡 Fun Challenge: {selected_tip}\n\nMake today colorful and amazing! 🎉',
            "template_path": template_path
        }
        
        print("✅ Cheerful content created")
        
        # Create Rich Message
        flex_message = rich_service.create_flex_message(
            title=content["title"],
            content=content["content"],
            image_path=content["template_path"],
            content_id=f"sticker_direct_{int(datetime.now().timestamp())}",
            user_id=user_id,
            include_interactions=True
        )
        
        if not flex_message:
            print("❌ Failed to create Rich Message")
            return False
        
        print("✅ Rich Message created")
        
        # Send the message
        print("🔴 SENDING...")
        line_bot_api.push_message(user_id, flex_message)
        print("🎉 Message sent successfully!")
        
        print()
        print("📊 Message Details:")
        print(f"   👤 Sent to: {user_id}")
        print(f"   🎨 Template: inspiration_sticker_01.png")
        print(f"   🎭 Theme: Playful & Cheerful")
        print(f"   📱 Interactive: Like, Share, Save, React buttons")
        print(f"   🕒 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        print("📱 CHECK YOUR LINE APP!")
        print("   🎨 Look for the colorful sticker-themed message")
        print("   🔘 Try the interactive buttons:")
        print("      💝 Like - Show appreciation")
        print("      📤 Share - Spread positivity")  
        print("      💾 Save - Keep the inspiration")
        print("      😊 React - Add emoji response")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    # User ID (keeping confidential as requested)
    user_id = "U595491d702720bc7c90d50618324cac3"
    
    success = send_sticker_message(user_id)
    
    print()
    if success:
        print("🎉 STICKER MESSAGE SENT SUCCESSFULLY!")
        print("📱 Check your LINE app for the cheerful message!")
    else:
        print("❌ Send failed")