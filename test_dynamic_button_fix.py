#!/usr/bin/env python3
"""
Test Dynamic Button Fix

Test that the OpenAI parameter fix enables dynamic AI-generated responses 
instead of static fallbacks when buttons are clicked.
"""

import sys
import os
import time
from datetime import datetime

# Add src to path
sys.path.append('/home/runner/workspace/src')

def test_ai_conversation_trigger():
    """Test the conversation trigger with fixed AI integration"""
    
    print("🤖 TESTING AI CONVERSATION TRIGGER FIX")
    print("Verifying dynamic response generation works")
    print("=" * 55)
    
    try:
        from src.utils.interaction_handler import get_interaction_handler
        from src.services.openai_service import OpenAIService
        from src.services.conversation_service import ConversationService
        from src.services.rich_message_service import RichMessageService
        from src.config.settings import Settings
        from linebot import LineBotApi
        
        # Initialize services
        settings = Settings()
        conversation_service = ConversationService()
        openai_service = OpenAIService(settings, conversation_service)
        
        # Create Rich Message Service for context storage
        line_bot_api = LineBotApi(settings.LINE_CHANNEL_ACCESS_TOKEN)
        rich_message_service = RichMessageService(
            line_bot_api=line_bot_api,
            openai_service=openai_service
        )
        
        print("✅ Services initialized")
        
        # Create test context (simulating stored button context)
        test_content_id = f"fix_test_{int(time.time())}"
        test_context = {
            'title': '🔥 Earned Wisdom',
            'content': 'Real motivation comes from people with scars, not people with perfect Instagram feeds. Trust the struggle.',
            'theme': 'motivation',
            'image_context': {
                'description': 'motivational scene with warm morning coffee setup',
                'mood': 'energetic and focused',
                'filename': 'motivation_weekend_energy.png'
            }
        }
        
        # Store context
        rich_message_service.store_button_context(test_content_id, test_context)
        print(f"📋 Test context stored for: {test_content_id}")
        
        # Get interaction handler with AI service
        interaction_handler = get_interaction_handler(openai_service)
        
        # Test each button type
        button_tests = [
            ("elaborate", "Tell me more"),
            ("authentic_take", "What's real here?"),
            ("experience_story", "Been there?"),
            ("practical_advice", "Recipe?")
        ]
        
        print(f"\n🧪 Testing each button type:")
        
        for trigger_type, button_label in button_tests:
            print(f"\n🔘 Testing '{button_label}' ({trigger_type})...")
            
            # Simulate button click interaction data
            interaction_data = {
                "action": "conversation_trigger",
                "trigger_type": trigger_type,
                "content_id": test_content_id
            }
            
            # Process the interaction
            result = interaction_handler.handle_user_interaction(
                user_id="test_user_fix", 
                interaction_data=interaction_data,
                rich_message_service=rich_message_service
            )
            
            if result['success']:
                response = result.get('message', '')
                ai_generated = result.get('ai_generated', False)
                
                print(f"   ✅ Response generated: {len(response)} chars")
                print(f"   🤖 AI Generated: {ai_generated}")
                print(f"   📝 Preview: {response[:80]}...")
                
                # Check if it's a dynamic response (not a fallback)
                fallback_responses = [
                    "There's always more to the story",
                    "Cut through the bullshit", 
                    "I've been there. Different kitchen",
                    "Simple recipe: Stay curious"
                ]
                
                is_fallback = any(fallback in response for fallback in fallback_responses)
                
                if is_fallback:
                    print(f"   ❌ Static fallback detected!")
                    return False
                else:
                    print(f"   ✅ Dynamic AI response confirmed!")
                    
            else:
                print(f"   ❌ Response failed: {result.get('error')}")
                return False
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def send_test_rich_message():
    """Send a new Rich Message for live testing"""
    
    print(f"\n📱 SENDING NEW TEST RICH MESSAGE")
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
        
        # Generate unique content ID
        content_id = f"fixed_test_{int(time.time())}"
        test_user_id = "U595491d702720bc7c90d50618324cac3"
        
        print(f"📋 Creating Rich Message with fixed AI integration...")
        print(f"   Content ID: {content_id}")
        
        # Create and send Rich Message
        flex_message = rich_message_service.create_smart_rich_message(
            theme="wellness",
            user_context="Testing the fixed AI button responses",
            content_id=content_id,
            user_id=test_user_id,
            include_interactions=True,
            force_ai_generation=True
        )
        
        send_result = rich_message_service.send_rich_message(
            flex_message=flex_message,
            user_id=test_user_id,
            bypass_rate_limit=True
        )
        
        if send_result['success']:
            print(f"✅ Rich Message sent successfully!")
            print(f"   Alt text: {flex_message.alt_text}")
            
            # Verify context storage
            stored_context = rich_message_service.get_button_context(content_id)
            if stored_context:
                print(f"✅ Context stored for dynamic responses")
                print(f"   Theme: {stored_context.get('theme')}")
                print(f"   Image context available: {bool(stored_context.get('image_context'))}")
            else:
                print(f"❌ Context storage failed")
                
            return True
        else:
            print(f"❌ Failed to send: {send_result.get('error')}")
            return False
            
    except Exception as e:
        print(f"❌ Send failed: {str(e)}")
        return False

if __name__ == "__main__":
    print("🔧 DYNAMIC BUTTON RESPONSE FIX TEST")
    print("Testing AI parameter fix for conversation triggers")
    print()
    
    # Test 1: Verify AI conversation trigger works
    ai_test_success = test_ai_conversation_trigger()
    
    # Test 2: Send new Rich Message for live testing
    send_success = send_test_rich_message()
    
    print("\n" + "=" * 55)
    print("🎯 TEST RESULTS:")
    
    if ai_test_success:
        print("✅ AI Conversation Triggers: WORKING")
        print("   • Dynamic responses generated successfully")
        print("   • No static fallbacks detected")
        print("   • All 4 button types functional")
    else:
        print("❌ AI Conversation Triggers: FAILED")
        print("   • Still getting static fallback responses")
        
    if send_success:
        print("✅ Rich Message Delivery: WORKING")
        print("   • New message sent to your LINE OA")
        print("   • Context stored for button interactions")
    else:
        print("❌ Rich Message Delivery: FAILED")
        
    if ai_test_success and send_success:
        print("\n🎉 OVERALL STATUS: SUCCESS")
        print("📱 Check your LINE app and test the buttons!")
        print("🤖 You should now get dynamic AI responses that:")
        print("   • Reference the message content")
        print("   • Mention the background image/setting")
        print("   • Provide unique responses per button type")
        print("   • Show Anthony Bourdain's authentic voice")
    else:
        print("\n❌ OVERALL STATUS: ISSUES REMAIN")
        print("Check the errors above for debugging")