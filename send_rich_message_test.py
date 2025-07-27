#!/usr/bin/env python3
"""
Send Test Rich Message to LINE OA

Send an optimized Rich Message with working interactive buttons to test the 
server-side context storage solution.
"""

import sys
import os
import time
from datetime import datetime

# Add src to path
sys.path.append('/home/runner/workspace/src')

def send_rich_message_test():
    """Send a Rich Message with optimized buttons to LINE OA"""
    
    print("📱 SENDING RICH MESSAGE TEST")
    print("Testing optimized button system with your LINE OA")
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
        
        # Initialize with OpenAI for dynamic content
        conversation_service = ConversationService()
        openai_service = OpenAIService(settings, conversation_service)
        
        # Create Rich Message Service with full AI capabilities
        rich_message_service = RichMessageService(
            line_bot_api=line_bot_api,
            openai_service=openai_service
        )
        
        print("✅ Services initialized with AI content generation")
        
        # Your LINE user ID
        test_user_id = "U595491d702720bc7c90d50618324cac3"
        
        # Generate unique content ID for tracking
        content_id = f"live_test_{int(time.time())}"
        
        print(f"📋 Message Details:")
        print(f"   Target: Your LINE OA")
        print(f"   User ID: {test_user_id[:12]}...")
        print(f"   Content ID: {content_id}")
        
        # Create Smart Rich Message with AI-generated content
        print(f"\n🎨 Creating Smart Rich Message...")
        print(f"   Theme: motivation")
        print(f"   AI Generation: enabled")
        print(f"   Interactive Buttons: enabled")
        print(f"   Context Storage: optimized")
        
        flex_message = rich_message_service.create_smart_rich_message(
            theme="motivation",
            user_context="Live test of the optimized button system with enhanced AI responses",
            content_id=content_id,
            user_id=test_user_id,
            include_interactions=True,
            force_ai_generation=True
        )
        
        print(f"✅ Rich Message created successfully")
        print(f"   Type: {type(flex_message).__name__}")
        print(f"   Alt Text: {flex_message.alt_text}")
        
        # Send the message
        print(f"\n📤 Sending to your LINE OA...")
        
        send_result = rich_message_service.send_rich_message(
            flex_message=flex_message,
            user_id=test_user_id,
            bypass_rate_limit=True
        )
        
        if send_result['success']:
            print(f"✅ Rich Message sent successfully!")
            print(f"   Status: {send_result.get('status', 'sent')}")
            print(f"   Rate limit bypassed: Yes")
            
            # Verify context storage
            print(f"\n🗄️ Verifying context storage...")
            stored_context = rich_message_service.get_button_context(content_id)
            
            if stored_context:
                print(f"✅ Context stored successfully")
                print(f"   Title: {stored_context.get('title', 'N/A')}")
                print(f"   Content Preview: {stored_context.get('content', '')[:50]}...")
                print(f"   Theme: {stored_context.get('theme', 'N/A')}")
                print(f"   Image Context: {stored_context.get('image_context', {}).get('description', 'N/A')}")
                
                # Show button optimization info
                print(f"\n📊 Button Optimization Status:")
                from src.utils.interaction_handler import get_interaction_handler
                interaction_handler = get_interaction_handler(openai_service)
                
                buttons = interaction_handler.create_interactive_buttons(
                    content_id=content_id,
                    rich_message_context=stored_context,
                    rich_message_service=rich_message_service
                )
                
                for i, button in enumerate(buttons, 1):
                    data_size = len(button['data'])
                    status = "✅" if data_size <= 300 else "❌"
                    print(f"   Button {i} '{button['label']}': {data_size} chars {status}")
                
            else:
                print(f"❌ Context storage verification failed")
            
            print(f"\n🎯 TEST COMPLETE!")
            print(f"📱 Check your LINE app now for the Rich Message")
            print(f"🔘 Try clicking the interactive buttons:")
            print(f"   • 'Tell me more' - Get deeper perspective")
            print(f"   • 'What's real here?' - Get authentic take")
            print(f"   • 'Been there?' - Get personal story")
            print(f"   • 'Recipe?' - Get practical advice")
            print(f"")
            print(f"🤖 Each button should generate a Bourdain-style response that:")
            print(f"   ✓ References the message content")
            print(f"   ✓ Mentions the background image/setting")
            print(f"   ✓ Provides contextual, authentic advice")
            print(f"")
            print(f"🔍 Watch the Replit console for button interaction logs")
            
            return True
            
        else:
            print(f"❌ Failed to send Rich Message: {send_result.get('error')}")
            return False
            
    except Exception as e:
        print(f"❌ Send test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("📱 RICH MESSAGE SEND TEST")
    print("Sending optimized Rich Message to your LINE OA")
    print()
    
    success = send_rich_message_test()
    
    print("\n" + "=" * 50)
    if success:
        print("✅ SEND TEST SUCCESSFUL")
        print()
        print("📱 Rich Message delivered to your LINE OA")
        print("🔘 Test the interactive buttons to verify AI responses")
        print("🔍 Watch console for button interaction processing")
        print()
        print("Expected behavior:")
        print("• Buttons should respond immediately")
        print("• Responses should reference image context") 
        print("• Anthony Bourdain personality should be evident")
        print("• No '400 - invalid message' errors")
    else:
        print("❌ SEND TEST FAILED")
        print("Check errors above")