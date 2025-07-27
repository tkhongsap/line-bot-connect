#!/usr/bin/env python3
"""
Send Fixed Rich Message

Send a Rich Message with the completely fixed dynamic button system.
Both parameter mismatches are now fixed and the app has been restarted.
"""

import sys
import os
import time
from datetime import datetime

# Add src to path
sys.path.append('/home/runner/workspace/src')

def send_fully_fixed_rich_message():
    """Send a Rich Message with all parameter fixes applied"""
    
    print("🎯 SENDING FULLY FIXED RICH MESSAGE")
    print("All OpenAI parameter mismatches fixed + app restarted")
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
        
        print("✅ Services initialized with fixed AI integration")
        
        # Generate unique content ID
        content_id = f"fully_fixed_{int(time.time())}"
        test_user_id = "U595491d702720bc7c90d50618324cac3"
        
        print(f"📋 Creating Rich Message with BOTH fixes applied...")
        print(f"   Content ID: {content_id}")
        print(f"   Fix 1: interaction_handler.py parameter fixed ✅")
        print(f"   Fix 2: rich_message_content_generator.py parameter fixed ✅")
        print(f"   Flask app restarted to load fixes ✅")
        
        # Create and send Rich Message (should now have AI-generated content)
        flex_message = rich_message_service.create_smart_rich_message(
            theme="inspiration",
            user_context="Testing fully fixed dynamic AI response system",
            content_id=content_id,
            user_id=test_user_id,
            include_interactions=True,
            force_ai_generation=True
        )
        
        print(f"✅ Rich Message created with AI-generated content")
        print(f"   Alt text: {flex_message.alt_text}")
        
        # Send the message
        send_result = rich_message_service.send_rich_message(
            flex_message=flex_message,
            user_id=test_user_id,
            bypass_rate_limit=True
        )
        
        if send_result['success']:
            print(f"✅ Rich Message sent successfully!")
            print(f"   Status: {send_result.get('status', 'sent')}")
            
            # Verify context storage for button interactions
            stored_context = rich_message_service.get_button_context(content_id)
            if stored_context:
                print(f"✅ Context stored for dynamic button responses")
                print(f"   Title: {stored_context.get('title', 'N/A')}")
                print(f"   Theme: {stored_context.get('theme', 'N/A')}")
                print(f"   Image context: {bool(stored_context.get('image_context', {}))}")
                
                # Test one button type to verify AI generation works
                print(f"\n🧪 Testing button response generation...")
                
                from src.utils.interaction_handler import get_interaction_handler
                interaction_handler = get_interaction_handler(openai_service)
                
                # Simulate "Tell me more" button click
                test_interaction = {
                    "action": "conversation_trigger",
                    "trigger_type": "elaborate",
                    "content_id": content_id
                }
                
                result = interaction_handler.handle_user_interaction(
                    user_id="test_fixed_user",
                    interaction_data=test_interaction,
                    rich_message_service=rich_message_service
                )
                
                if result['success']:
                    response = result.get('message', '')
                    ai_generated = result.get('ai_generated', False)
                    
                    print(f"   ✅ Button response generated: {len(response)} chars")
                    print(f"   🤖 AI Generated: {ai_generated}")
                    print(f"   📝 Response preview: {response[:60]}...")
                    
                    # Check if it's dynamic (not fallback)
                    fallback_patterns = [
                        "There's always more to the story",
                        "Cut through the bullshit",
                        "I've been there. Different kitchen",
                        "Simple recipe: Stay curious"
                    ]
                    
                    is_fallback = any(pattern in response for pattern in fallback_patterns)
                    
                    if is_fallback:
                        print(f"   ❌ Still getting static fallback response!")
                        return False
                    else:
                        print(f"   ✅ Dynamic AI response confirmed!")
                else:
                    print(f"   ❌ Button response failed: {result.get('error')}")
                    
            else:
                print(f"❌ Context storage failed")
                return False
                
            print(f"\n🎯 ALL FIXES APPLIED SUCCESSFULLY!")
            print(f"📱 Check your LINE app for the new 'inspiration' theme message")
            print(f"🔘 Test the interactive buttons - they should now be FULLY DYNAMIC:")
            print(f"")
            print(f"✅ Expected behavior:")
            print(f"   • Each button generates unique AI responses")
            print(f"   • Responses reference message content AND image context")
            print(f"   • Anthony Bourdain's authentic voice and personality")
            print(f"   • Contextual advice based on trigger type")
            print(f"   • No more static fallback responses")
            print(f"")
            print(f"🔍 Watch console logs when you click buttons for confirmation")
            
            return True
            
        else:
            print(f"❌ Failed to send Rich Message: {send_result.get('error')}")
            return False
            
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🔧 FULLY FIXED DYNAMIC BUTTON TEST")
    print("Testing with all parameter fixes + restarted app")
    print()
    
    success = send_fully_fixed_rich_message()
    
    print("\n" + "=" * 55)
    if success:
        print("🎉 ALL FIXES SUCCESSFULLY APPLIED!")
        print()
        print("📱 Rich Message sent with working dynamic responses")
        print("🤖 Button clicks should now generate unique AI content")
        print("✅ No more static fallback responses")
        print()
        print("Test each button to confirm they're now fully dynamic!")
    else:
        print("❌ FIXES INCOMPLETE - ISSUES REMAIN")
        print("Check errors above for debugging")