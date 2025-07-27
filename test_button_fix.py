#!/usr/bin/env python3
"""
Test Button Fix

Send a Rich Message and test if the button responses are now dynamic
"""

import sys
import os
import time
sys.path.append('/home/runner/workspace/src')

def test_button_functionality():
    """Test the button functionality with a real Rich Message"""
    
    print("🔘 TESTING BUTTON FUNCTIONALITY")
    print("Sending Rich Message and testing button responses")
    print("=" * 50)
    
    try:
        from src.services.rich_message_service import RichMessageService
        from src.services.openai_service import OpenAIService
        from src.services.conversation_service import ConversationService  
        from src.config.settings import Settings
        from linebot import LineBotApi
        
        # Initialize services
        settings = Settings()
        line_bot_api = LineBotApi(settings.LINE_CHANNEL_ACCESS_TOKEN)
        
        conversation_service = ConversationService()
        openai_service = OpenAIService(settings, conversation_service)
        
        rich_message_service = RichMessageService(
            line_bot_api=line_bot_api,
            openai_service=openai_service
        )
        
        print("✅ Services initialized")
        
        # Create a Rich Message
        content_id = f"button_test_{int(time.time())}"
        test_user_id = "U595491d702720bc7c90d50618324cac3"  # Your LINE user ID
        
        print(f"\n📱 Creating Rich Message...")
        print(f"   Content ID: {content_id}")
        print(f"   Theme: motivation")
        
        flex_message = rich_message_service.create_smart_rich_message(
            theme="motivation",
            user_context="Testing button fix - dynamic AI responses",
            content_id=content_id,
            user_id=test_user_id,
            include_interactions=True,
            force_ai_generation=True
        )
        
        print(f"✅ Rich Message created")
        print(f"   Alt text: {flex_message.alt_text}")
        
        # Send the message
        print(f"\n📤 Sending Rich Message...")
        send_result = rich_message_service.send_rich_message(
            flex_message=flex_message,
            user_id=test_user_id,
            bypass_rate_limit=True
        )
        
        if send_result['success']:
            print(f"✅ Rich Message sent successfully!")
            
            # Verify context is stored
            stored_context = rich_message_service.get_button_context(content_id)
            if stored_context:
                print(f"✅ Button context stored")
                print(f"   Keys: {list(stored_context.keys())}")
            else:
                print(f"❌ Button context not stored")
                return False
            
            # Test button response generation
            print(f"\n🧪 Testing button responses...")
            
            from src.utils.interaction_handler import get_interaction_handler
            interaction_handler = get_interaction_handler(openai_service)
            
            # Test all 4 button types
            button_tests = [
                ("elaborate", "Tell me more"),
                ("authentic_take", "What's real here?"),
                ("experience_story", "Been there?"),
                ("practical_advice", "Recipe?")
            ]
            
            all_dynamic = True
            for trigger_type, button_label in button_tests:
                print(f"\n🔘 Testing '{button_label}' button...")
                
                test_interaction = {
                    "action": "conversation_trigger",
                    "trigger_type": trigger_type,
                    "content_id": content_id
                }
                
                # Test the button response directly
                result = interaction_handler.handle_user_interaction(
                    user_id=f"test_{trigger_type}",
                    interaction_data=test_interaction,
                    rich_message_service=rich_message_service
                )
                
                if result['success']:
                    response = result.get('message', '')
                    ai_generated = result.get('ai_generated', False)
                    
                    print(f"   ✅ Response generated: {len(response)} chars")
                    print(f"   🤖 AI Generated: {ai_generated}")
                    print(f"   📝 Preview: {response[:80]}...")
                    
                    # Check if it's a fallback response
                    fallback_patterns = [
                        "There's always more to the story",
                        "Cut through the bullshit",
                        "I've been there. Different kitchen",
                        "Simple recipe: Stay curious"
                    ]
                    
                    is_fallback = any(pattern in response for pattern in fallback_patterns)
                    if is_fallback:
                        print(f"   ❌ STATIC FALLBACK detected!")
                        all_dynamic = False
                    else:
                        print(f"   ✅ DYNAMIC AI response!")
                else:
                    print(f"   ❌ Button response failed: {result.get('error')}")
                    all_dynamic = False
            
            print(f"\n📊 FINAL RESULT:")
            if all_dynamic:
                print(f"   ✅ ALL BUTTONS GENERATE DYNAMIC AI RESPONSES!")
                print(f"   🎉 Button fix is working correctly")
            else:
                print(f"   ❌ Some buttons still use static fallback responses")
                print(f"   🔧 Button fix needs more work")
            
            return all_dynamic
        else:
            print(f"❌ Failed to send Rich Message: {send_result.get('error')}")
            return False
            
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🔧 BUTTON FIX TEST")
    print("Testing if button responses are now dynamic")
    print()
    
    success = test_button_functionality()
    
    print("\n" + "=" * 50)
    if success:
        print("✅ BUTTON FIX SUCCESSFUL!")
        print()
        print("📱 Check your LINE app for the new message")
        print("🔘 Test each button - they should now generate unique AI responses")
        print("🎯 Each click should produce different, contextual content")
    else:
        print("❌ BUTTON FIX STILL NEEDS WORK")
        print("The issue preventing dynamic responses hasn't been resolved yet")