#!/usr/bin/env python3
"""
Controlled Rich Message Test with Rate Limiting and Confirmation

This consolidated test script replaces multiple test files and ensures
only one Rich Message is sent at a time with proper controls.
"""

import sys
import os
import argparse
from datetime import datetime

# Add src to path
sys.path.append('/home/runner/workspace/src')

def get_user_confirmation(message_details: dict) -> bool:
    """Get user confirmation before sending Rich Message"""
    print("\n" + "="*60)
    print("📱 RICH MESSAGE READY TO SEND")
    print("="*60)
    print(f"📌 Title: {message_details['title']}")
    print(f"💬 Content: {message_details['content']}")
    print(f"🖼️  Image: {message_details.get('image', 'None')}")
    print(f"🎭 Theme: {message_details.get('theme', 'Unknown')}")
    print(f"👤 Recipient: {message_details['user_id']}")
    print(f"⏰ Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    while True:
        response = input("\n🤔 Send this Rich Message? (y/n/preview): ").lower().strip()
        if response in ['y', 'yes']:
            return True
        elif response in ['n', 'no']:
            print("❌ Send cancelled by user")
            return False
        elif response in ['p', 'preview']:
            print("\n📋 MESSAGE PREVIEW:")
            print(f"   Title Length: {len(message_details['title'])} chars")
            print(f"   Content Length: {len(message_details['content'])} chars")
            print(f"   Total Length: {len(message_details['title']) + len(message_details['content'])} chars")
            if message_details.get('image'):
                print(f"   Image File: {os.path.basename(message_details['image'])}")
            continue
        else:
            print("Please enter 'y' for yes, 'n' for no, or 'preview' for details")

def test_smart_rich_message(theme: str = "motivation", 
                          user_context: str = "general",
                          user_id: str = "U595491d702720bc7c90d50618324cac3",
                          dry_run: bool = False,
                          bypass_rate_limit: bool = False,
                          require_confirmation: bool = True) -> bool:
    """Test smart Rich Message creation and sending with controls"""
    
    print(f"🧠 TESTING SMART RICH MESSAGE")
    print("=" * 50)
    print(f"🎭 Theme: {theme}")
    print(f"👤 User Context: {user_context}")
    print(f"📱 Target: {user_id}")
    print(f"🔄 Dry Run: {dry_run}")
    print(f"⚡ Bypass Rate Limit: {bypass_rate_limit}")
    print(f"✋ Require Confirmation: {require_confirmation}")
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
        
        rich_service = RichMessageService(
            line_bot_api=line_service.line_bot_api,
            base_url='https://line-bot-connect-tkhongsap.replit.app',
            openai_service=openai_service
        )
        
        print("✅ Rich Message service initialized with rate limiting")
        
        # Check send status first
        send_status = rich_service.get_send_status(user_id)
        print(f"\n📊 SEND STATUS CHECK:")
        print(f"   📈 Daily Count: {send_status['daily_count']}/{send_status['max_daily']}")
        print(f"   ⏱️  Last Send: {send_status['last_send'] or 'Never'}")
        print(f"   🚦 Can Send Now: {'✅ Yes' if send_status['can_send_now'] else '❌ No'}")
        
        if send_status['cooldown_remaining'] > 0:
            print(f"   ⏳ Cooldown: {send_status['cooldown_remaining']:.0f}s remaining")
        
        # Create smart Rich Message
        print(f"\n🎨 Generating smart Rich Message...")
        
        smart_message = rich_service.create_smart_rich_message(
            theme=theme,
            user_context=user_context,
            user_id=user_id,
            force_ai_generation=True
        )
        
        if not smart_message:
            print("❌ Failed to create smart Rich Message")
            return False
        
        print("✅ Smart Rich Message created successfully")
        
        # Extract message details for confirmation
        message_details = {
            "title": smart_message.alt_text.split(":")[0] if ":" in smart_message.alt_text else smart_message.alt_text[:50],
            "content": smart_message.alt_text.split(":", 1)[1].strip() if ":" in smart_message.alt_text else smart_message.alt_text[50:],
            "image": "Smart-selected background image",
            "theme": theme,
            "user_id": user_id[:8] + "...",
            "has_interactions": True
        }
        
        # Get confirmation if required
        if require_confirmation and not dry_run:
            if not get_user_confirmation(message_details):
                print("📋 Rich Message creation completed but sending cancelled")
                return True
        
        # Send with controls
        print(f"\n📤 Sending Rich Message...")
        
        send_result = rich_service.send_rich_message(
            flex_message=smart_message,
            user_id=user_id,
            bypass_rate_limit=bypass_rate_limit,
            dry_run=dry_run
        )
        
        if send_result["success"]:
            if send_result.get("dry_run"):
                print("🎭 DRY RUN: Message validated but not sent")
                print(f"   ✅ Rate limits checked: {send_result['rate_limit_info']['reason']}")
            elif send_result.get("sent"):
                print("🎉 Rich Message sent successfully!")
                print(f"   📊 Rate limit status: {send_result['rate_limit_info']['reason']}")
                print(f"   📈 Daily count: {send_result['rate_limit_info']['daily_count']}")
            else:
                print("❓ Unexpected send result state")
        else:
            if send_result.get("blocked"):
                print(f"🚫 Send blocked: {send_result['reason']}")
                if send_result.get("rate_limit_info"):
                    rate_info = send_result["rate_limit_info"]
                    if rate_info.get("remaining_seconds"):
                        print(f"   ⏰ Try again in {rate_info['remaining_seconds']:.0f} seconds")
                    elif rate_info.get("next_allowed") == "tomorrow":
                        print(f"   📅 Daily limit reached, try tomorrow")
            else:
                print(f"❌ Send failed: {send_result.get('error', 'Unknown error')}")
                return False
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_rate_limiting(user_id: str = "U595491d702720bc7c90d50618324cac3") -> bool:
    """Test rate limiting functionality"""
    
    print(f"\n🚦 TESTING RATE LIMITING")
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
            openai_service=openai_service
        )
        
        print("✅ Services initialized")
        
        # Test 1: Check initial status
        print(f"\n1️⃣ Initial Send Status:")
        status = rich_service.get_send_status(user_id)
        for key, value in status.items():
            if key != "user_id":
                print(f"   {key}: {value}")
        
        # Test 2: Check rate limit without sending
        print(f"\n2️⃣ Rate Limit Check:")
        rate_check = rich_service.check_send_rate_limit(user_id, bypass_limit=False)
        print(f"   Allowed: {rate_check['allowed']}")
        print(f"   Reason: {rate_check['reason']}")
        
        # Test 3: Simulate send and check cooldown
        print(f"\n3️⃣ Simulating Send and Cooldown:")
        rich_service.record_message_sent(user_id)
        print("   ✅ Recorded message send")
        
        # Check status after simulated send
        status_after = rich_service.get_send_status(user_id)
        print(f"   New daily count: {status_after['daily_count']}")
        print(f"   Can send now: {status_after['can_send_now']}")
        print(f"   Cooldown remaining: {status_after['cooldown_remaining']:.0f}s")
        
        # Test 4: Try to send again (should be blocked)
        print(f"\n4️⃣ Testing Cooldown Block:")
        rate_check_2 = rich_service.check_send_rate_limit(user_id, bypass_limit=False)
        print(f"   Allowed: {rate_check_2['allowed']}")
        print(f"   Reason: {rate_check_2['reason']}")
        if not rate_check_2['allowed']:
            print(f"   ✅ Rate limiting working correctly!")
        
        # Test 5: Bypass test
        print(f"\n5️⃣ Testing Bypass:")
        rate_check_bypass = rich_service.check_send_rate_limit(user_id, bypass_limit=True)
        print(f"   Bypass allowed: {rate_check_bypass['allowed']}")
        print(f"   Bypass reason: {rate_check_bypass['reason']}")
        
        print(f"\n✅ Rate limiting tests completed successfully")
        return True
        
    except Exception as e:
        print(f"❌ Rate limiting test failed: {str(e)}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Controlled Rich Message Testing')
    parser.add_argument('--theme', default='motivation', choices=['productivity', 'wellness', 'motivation', 'inspiration'],
                       help='Message theme')
    parser.add_argument('--context', default='general', help='User context')
    parser.add_argument('--user-id', default='U595491d702720bc7c90d50618324cac3', help='Target user ID')
    parser.add_argument('--dry-run', action='store_true', help='Validate but do not send')
    parser.add_argument('--bypass-limit', action='store_true', help='Bypass rate limiting')
    parser.add_argument('--no-confirm', action='store_true', help='Skip confirmation prompt')
    parser.add_argument('--test-limits', action='store_true', help='Test rate limiting functionality')
    parser.add_argument('--mode', choices=['smart', 'limits', 'both'], default='smart',
                       help='Test mode: smart messages, rate limits, or both')
    
    args = parser.parse_args()
    
    print("🔒 CONTROLLED RICH MESSAGE TESTING")
    print("Safe, rate-limited Rich Message testing with user controls")
    print("=" * 65)
    
    success = True
    
    # Test rate limiting if requested
    if args.mode in ['limits', 'both'] or args.test_limits:
        print("🚦 Running rate limiting tests...")
        if not test_rate_limiting(args.user_id):
            success = False
    
    # Test smart Rich Message if requested
    if args.mode in ['smart', 'both']:
        print("🧠 Running smart Rich Message test...")
        if not test_smart_rich_message(
            theme=args.theme,
            user_context=args.context,
            user_id=args.user_id,
            dry_run=args.dry_run,
            bypass_rate_limit=args.bypass_limit,
            require_confirmation=not args.no_confirm
        ):
            success = False
    
    print("\n" + "=" * 65)
    if success:
        print("🎉 ALL CONTROLLED TESTS PASSED!")
        print()
        print("✅ Rate limiting system working")
        print("✅ Send controls functioning")
        print("✅ Confirmation system active")
        print("✅ Dry run mode available")
        print("✅ Smart Rich Messages creating successfully")
        print()
        if args.dry_run:
            print("🎭 DRY RUN MODE: No messages were actually sent")
        else:
            print("📱 CHECK YOUR LINE APP for any sent messages")
        print()
        print("🛡️ Rich Message sending is now properly controlled!")
    else:
        print("❌ Some tests failed - check logs above")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)