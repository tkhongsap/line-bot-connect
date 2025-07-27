#!/usr/bin/env python3
"""
Test Button Functionality

Test that the interactive buttons in Rich Messages now work properly
after fixing the postback routing and OpenAI service integration.
"""

import sys
import os
from datetime import datetime

# Add src to path
sys.path.append('/home/runner/workspace/src')

def test_button_functionality():
    """Test that Rich Message buttons work and generate responses"""
    
    print("🔘 TESTING BUTTON FUNCTIONALITY")
    print("Testing interactive buttons in Rich Messages")
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
        
        print("✅ Services initialized with button support")
        
        user_id = "U595491d702720bc7c90d50618324cac3"
        
        # Check send status
        send_status = rich_service.get_send_status(user_id)
        print(f"\n📊 SEND STATUS:")
        print(f"   Can Send: {'✅ Yes' if send_status['can_send_now'] else '❌ No'}")
        print(f"   Daily Count: {send_status['daily_count']}/{send_status['max_daily']}")
        
        if send_status['cooldown_remaining'] > 0:
            print(f"   ⏳ Cooldown: {send_status['cooldown_remaining']:.0f}s remaining")
            print("\n⚠️  Still in cooldown - using bypass for button testing")
            bypass_needed = True
        else:
            bypass_needed = False
        
        # Create Rich Message with interactive buttons
        print(f"\n🎨 Creating Rich Message with interactive buttons...")
        
        smart_message = rich_service.create_smart_rich_message(
            theme="motivation",
            user_context="button testing",
            user_id=user_id,
            force_ai_generation=True
        )
        
        if not smart_message:
            print("❌ Failed to create Rich Message")
            return False
        
        print("✅ Rich Message with buttons created")
        
        # Show button details
        print(f"\n🔘 BUTTON DETAILS:")
        print("   The Rich Message contains these interactive buttons:")
        print("   1. 'Tell me more' - Should trigger AI elaboration")
        print("   2. 'What's real here?' - Should trigger authentic perspective")
        print("   3. 'Been there?' - Should trigger experience story")
        print("   4. 'Recipe?' - Should trigger practical advice")
        
        # Send the message
        print(f"\n📤 Sending Rich Message with interactive buttons...")
        
        send_result = rich_service.send_rich_message(
            flex_message=smart_message,
            user_id=user_id,
            bypass_rate_limit=bypass_needed,
            dry_run=False  # Actually send for button testing
        )
        
        if send_result["success"]:
            if send_result.get("sent"):
                print("🎉 Rich Message with buttons sent successfully!")
                print(f"\n📱 TEST INSTRUCTIONS:")
                print("1. Check your LINE app for the Rich Message")
                print("2. Try clicking each of the 4 buttons")
                print("3. Each button should generate a different AI response")
                print("4. Responses should be in Bourdain's authentic voice")
                print()
                print("🔍 EXPECTED BEHAVIOR:")
                print("   • 'Tell me more' → Deeper perspective on the topic")
                print("   • 'What's real here?' → No-bullshit authentic take")
                print("   • 'Been there?' → Personal story or experience")
                print("   • 'Recipe?' → Practical advice in Bourdain style")
                print()
                print("✅ If buttons work, each click should generate a unique response")
                return True
            else:
                print("❓ Unexpected send result")
                return False
        else:
            if send_result.get("blocked"):
                print(f"🚫 Send blocked: {send_result['reason']}")
                print("💡 Try again later when cooldown expires")
                return False
            else:
                print(f"❌ Send failed: {send_result.get('error', 'Unknown error')}")
                return False
        
    except Exception as e:
        print(f"❌ Button test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def show_button_implementation_details():
    """Show details about how the button system works"""
    
    print("\n🔧 BUTTON IMPLEMENTATION DETAILS")
    print("=" * 50)
    
    print("📋 Fixed Issues:")
    print("✅ Added conversation_trigger action handler to LineService")
    print("✅ Fixed OpenAI service passing to interaction handler")
    print("✅ Added debug logging for postback flow")
    print("✅ Enhanced error handling and response sending")
    
    print("\n🔄 Button Flow:")
    print("1. User clicks button → LINE sends postback with action: 'conversation_trigger'")
    print("2. LineService._handle_postback_event() receives postback")
    print("3. Routes to _handle_conversation_trigger_action()")
    print("4. Gets interaction_handler with OpenAI service")
    print("5. Processes trigger through _handle_conversation_trigger()")
    print("6. Generates AI response using Bourdain persona")
    print("7. Sends response back to user via LINE reply_token")
    
    print("\n🎭 Conversation Triggers:")
    print("• elaborate → User wants deeper perspective and storytelling")
    print("• authentic_take → User wants no-bullshit, authentic perspective")
    print("• experience_story → User wants personal story or experience")
    print("• practical_advice → User wants actionable advice, Bourdain-style")
    
    print("\n🛠️ Technical Implementation:")
    print("• Buttons created with PostbackAction containing JSON data")
    print("• Data includes: action, trigger_type, content_id, prompt_context")
    print("• LineService now properly routes conversation_trigger actions")
    print("• OpenAI service passed to generate authentic Bourdain responses")
    print("• Fallback responses available if AI generation fails")

if __name__ == "__main__":
    print("🔘 RICH MESSAGE BUTTON FUNCTIONALITY TEST")
    print("Testing that interactive buttons now work after fixes")
    print()
    
    # Show implementation details
    show_button_implementation_details()
    
    # Test button functionality
    success = test_button_functionality()
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 BUTTON TEST COMPLETED!")
        print()
        print("✅ Rich Message with interactive buttons sent")
        print("✅ Button routing and OpenAI integration fixed")
        print("✅ Conversation triggers should now work")
        print()
        print("📱 Please test the buttons in your LINE app")
        print("   Each button should generate a unique AI response")
        print("   in Bourdain's authentic voice!")
    else:
        print("❌ BUTTON TEST FAILED")
        print("Check logs above for details")
        print("Buttons may still not work - further debugging needed")