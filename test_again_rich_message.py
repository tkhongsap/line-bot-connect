#!/usr/bin/env python3
"""
Test Again - Rich Message Dynamic Buttons

Send another Rich Message to test the dynamic button responses
and verify the fixes are working consistently.
"""

import sys
import os
import time
from datetime import datetime

# Add src to path
sys.path.append('/home/runner/workspace/src')

def test_dynamic_buttons_again():
    """Send another Rich Message to test dynamic button responses"""
    
    print("🔄 TESTING DYNAMIC BUTTONS AGAIN")
    print("Sending fresh Rich Message to verify consistent fixes")
    print("=" * 55)
    
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
        
        # Generate unique content ID
        content_id = f"test_again_{int(time.time())}"
        test_user_id = "U595491d702720bc7c90d50618324cac3"
        
        print(f"📋 Test Details:")
        print(f"   Content ID: {content_id}")
        print(f"   Theme: productivity (different from last test)")
        print(f"   Target: Your LINE OA")
        
        # Create Rich Message with different theme for variety
        print(f"\n🎨 Creating Rich Message...")
        
        flex_message = rich_message_service.create_smart_rich_message(
            theme="productivity",
            user_context="Second test of dynamic AI button responses - productivity theme",
            content_id=content_id,
            user_id=test_user_id,
            include_interactions=True,
            force_ai_generation=True
        )
        
        print(f"✅ Rich Message created")
        print(f"   Alt text: {flex_message.alt_text}")
        
        # Send the message
        print(f"\n📤 Sending to your LINE OA...")
        
        send_result = rich_message_service.send_rich_message(
            flex_message=flex_message,
            user_id=test_user_id,
            bypass_rate_limit=True
        )
        
        if send_result['success']:
            print(f"✅ Rich Message sent successfully!")
            
            # Verify context storage
            stored_context = rich_message_service.get_button_context(content_id)
            if stored_context:
                print(f"✅ Button context stored")
                print(f"   Title: {stored_context.get('title', 'N/A')}")
                print(f"   Theme: {stored_context.get('theme', 'N/A')}")
                
                # Test all 4 button types to verify each generates unique responses
                print(f"\n🧪 Testing all 4 button types for unique responses...")
                
                from src.utils.interaction_handler import get_interaction_handler
                interaction_handler = get_interaction_handler(openai_service)
                
                button_tests = [
                    ("elaborate", "Tell me more"),
                    ("authentic_take", "What's real here?"),
                    ("experience_story", "Been there?"),
                    ("practical_advice", "Recipe?")
                ]
                
                all_responses = []
                all_dynamic = True
                
                for trigger_type, button_label in button_tests:
                    test_interaction = {
                        "action": "conversation_trigger",
                        "trigger_type": trigger_type,
                        "content_id": content_id
                    }
                    
                    result = interaction_handler.handle_user_interaction(
                        user_id=f"test_{trigger_type}",
                        interaction_data=test_interaction,
                        rich_message_service=rich_message_service
                    )
                    
                    if result['success']:
                        response = result.get('message', '')
                        ai_generated = result.get('ai_generated', False)
                        
                        print(f"   🔘 {button_label}: {len(response)} chars, AI: {ai_generated}")
                        print(f"      Preview: {response[:50]}...")
                        
                        all_responses.append(response)
                        
                        # Check for static fallbacks
                        fallback_patterns = [
                            "There's always more to the story",
                            "Cut through the bullshit",
                            "I've been there. Different kitchen", 
                            "Simple recipe: Stay curious"
                        ]
                        
                        is_fallback = any(pattern in response for pattern in fallback_patterns)
                        if is_fallback:
                            print(f"      ❌ Static fallback detected!")
                            all_dynamic = False
                        else:
                            print(f"      ✅ Dynamic AI response")
                    else:
                        print(f"   ❌ {button_label}: Failed - {result.get('error')}")
                        all_dynamic = False
                
                # Check if all responses are unique
                unique_responses = len(set(all_responses)) == len(all_responses)
                
                print(f"\n📊 RESPONSE ANALYSIS:")
                print(f"   Dynamic responses: {'✅ All dynamic' if all_dynamic else '❌ Some static'}")
                print(f"   Unique responses: {'✅ All unique' if unique_responses else '❌ Some duplicates'}")
                print(f"   Total responses: {len(all_responses)}")
                
                if all_dynamic and unique_responses:
                    print(f"\n🎉 PERFECT! All button responses are dynamic and unique!")
                    return True
                else:
                    print(f"\n⚠️ Some issues detected with button responses")
                    return False
                    
            else:
                print(f"❌ Context storage failed")
                return False
                
        else:
            print(f"❌ Failed to send Rich Message: {send_result.get('error')}")
            return False
            
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🔄 REPEAT TEST - DYNAMIC BUTTON RESPONSES")
    print("Testing for consistent dynamic AI responses")
    print()
    
    success = test_dynamic_buttons_again()
    
    print("\n" + "=" * 55)
    if success:
        print("✅ REPEAT TEST SUCCESSFUL!")
        print()
        print("📱 New productivity-themed Rich Message sent to your LINE OA")
        print("🤖 All 4 buttons generate unique, dynamic AI responses")
        print("✅ Fixes are working consistently")
        print()
        print("🔘 Test the buttons on this new message to confirm:")
        print("   • Each button gives different AI-generated content")
        print("   • Responses reference the message content and image")
        print("   • Anthony Bourdain's voice and personality comes through")
        print("   • No static fallback responses")
        print()
        print("This confirms the dynamic button system is fully functional!")
    else:
        print("❌ REPEAT TEST FAILED")
        print("There are still issues with the dynamic response system")
        print("Check the analysis above for details")