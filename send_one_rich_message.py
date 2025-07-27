#!/usr/bin/env python3
"""
Send ONE Rich Message Test

Simple script to send exactly one Rich Message with confirmation.
Uses the new controlled sending system with rate limiting.
"""

import sys
import os
from datetime import datetime

# Add src to path
sys.path.append('/home/runner/workspace/src')

def send_single_rich_message():
    """Send exactly one Rich Message with all safety controls"""
    
    print("📱 SENDING ONE RICH MESSAGE")
    print("Safe, controlled single Rich Message send")
    print("=" * 50)
    
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
        
        rich_service = RichMessageService(
            line_bot_api=line_service.line_bot_api,
            base_url='https://line-bot-connect-tkhongsap.replit.app',
            openai_service=openai_service
        )
        
        print("✅ Rich Message service initialized with rate limiting")
        
        user_id = "U595491d702720bc7c90d50618324cac3"
        
        # Check current status
        send_status = rich_service.get_send_status(user_id)
        print(f"\n📊 CURRENT STATUS:")
        print(f"   Daily Count: {send_status['daily_count']}/{send_status['max_daily']}")
        print(f"   Last Send: {send_status['last_send'] or 'Never'}")
        print(f"   Can Send: {'✅ Yes' if send_status['can_send_now'] else '❌ No'}")
        
        if send_status['cooldown_remaining'] > 0:
            print(f"   ⏳ Cooldown: {send_status['cooldown_remaining']:.0f}s remaining")
            print("\n🚫 Cannot send - still in cooldown period")
            print("💡 Try again later or use --bypass-limit flag for testing")
            return False
        
        # Create smart Rich Message
        print(f"\n🎨 Creating Rich Message...")
        
        smart_message = rich_service.create_smart_rich_message(
            theme="motivation",
            user_context="afternoon energy",
            user_id=user_id,
            force_ai_generation=True
        )
        
        if not smart_message:
            print("❌ Failed to create Rich Message")
            return False
        
        print("✅ Rich Message created")
        
        # Show preview
        print(f"\n📋 MESSAGE PREVIEW:")
        print(f"   Title: {smart_message.alt_text.split(':')[0] if ':' in smart_message.alt_text else smart_message.alt_text[:50]}")
        print(f"   Content: {smart_message.alt_text.split(':', 1)[1].strip()[:100] if ':' in smart_message.alt_text else smart_message.alt_text[50:150]}...")
        print(f"   Target: {user_id}")
        print(f"   Time: {datetime.now().strftime('%H:%M:%S')}")
        
        # Get confirmation
        print(f"\n🤔 Ready to send this Rich Message?")
        while True:
            response = input("Enter 'send' to confirm, 'cancel' to abort: ").lower().strip()
            if response == 'send':
                break
            elif response == 'cancel':
                print("❌ Send cancelled by user")
                return False
            else:
                print("Please enter 'send' or 'cancel'")
        
        # Send with rate limiting
        print(f"\n📤 Sending Rich Message...")
        
        send_result = rich_service.send_rich_message(
            flex_message=smart_message,
            user_id=user_id,
            bypass_rate_limit=False,  # Respect rate limits
            dry_run=False  # Actually send
        )
        
        if send_result["success"]:
            if send_result.get("sent"):
                print("🎉 Rich Message sent successfully!")
                print(f"   📊 Daily count now: {send_result['rate_limit_info']['daily_count']}")
                print(f"   ⏰ Next send allowed in: 5 minutes")
                print("\n📱 CHECK YOUR LINE APP!")
                return True
            else:
                print("❓ Unexpected result - message may not have been sent")
                return False
        else:
            if send_result.get("blocked"):
                print(f"🚫 Send blocked: {send_result['reason']}")
                return False
            else:
                print(f"❌ Send failed: {send_result.get('error', 'Unknown error')}")
                return False
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🎯 SINGLE RICH MESSAGE SENDER")
    print("This script sends exactly ONE Rich Message with safety controls")
    print()
    
    if "--help" in sys.argv:
        print("Usage: python send_one_rich_message.py")
        print()
        print("This script will:")
        print("1. Check rate limits and send status")
        print("2. Create a smart Rich Message with contextual image")
        print("3. Show preview and ask for confirmation")
        print("4. Send exactly one message if confirmed")
        print("5. Respect 5-minute cooldown between sends")
        sys.exit(0)
    
    success = send_single_rich_message()
    
    if success:
        print("\n✅ SUCCESS: One Rich Message sent")
        print("🛡️ Rate limiting active - next send in 5 minutes")
    else:
        print("\n❌ FAILED: No message sent")
        print("💡 Check status above for details")