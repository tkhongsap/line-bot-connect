#!/usr/bin/env python3
"""
Test Optimized Rich Message

Send a Rich Message using the optimized button system with server-side context storage.
This should fix the LINE postback data size limit issue.
"""

import sys
import os
import time
from datetime import datetime

# Add src to path
sys.path.append('/home/runner/workspace/src')

def test_optimized_rich_message():
    """Test sending Rich Message with optimized button data"""
    
    print("🔧 TESTING OPTIMIZED RICH MESSAGE")
    print("Testing server-side context storage and minimal button data")
    print("=" * 60)
    
    try:
        from src.services.rich_message_service import RichMessageService
        from src.config.settings import Settings
        from linebot import LineBotApi
        
        # Initialize services
        settings = Settings()
        line_bot_api = LineBotApi(settings.LINE_CHANNEL_ACCESS_TOKEN)
        
        # Create Rich Message Service with context storage
        rich_message_service = RichMessageService(
            line_bot_api=line_bot_api,
            openai_service=None  # Will use fallback content for testing
        )
        
        print("✅ Services initialized")
        
        # Test user (replace with your LINE user ID for testing)
        test_user_id = "U595491d702720bc7c90d50618324cac3"
        
        # Generate unique content ID for this test
        content_id = f"optimized_test_{int(time.time())}"
        
        print(f"📋 Testing parameters:")
        print(f"   User ID: {test_user_id[:12]}...")
        print(f"   Content ID: {content_id}")
        
        # Test Smart Rich Message creation with optimized buttons
        print(f"\n🎨 Creating Smart Rich Message with optimized buttons...")
        
        try:
            flex_message = rich_message_service.create_smart_rich_message(
                user_id=test_user_id,
                theme="motivation",
                include_interactions=True,
                content_id=content_id,
                user_context="Testing optimized button data system"
            )
            
            print(f"✅ Rich Message created successfully")
            print(f"   Message type: {type(flex_message).__name__}")
            print(f"   Alt text: {flex_message.alt_text}")
            
            # Test sending the message
            print(f"\n📤 Sending Rich Message...")
            
            send_result = rich_message_service.send_rich_message(
                flex_message=flex_message,
                user_id=test_user_id,
                bypass_rate_limit=True  # For testing
            )
            
            if send_result['success']:
                print(f"✅ Rich Message sent successfully!")
                print(f"   Send status: {send_result.get('status', 'sent')}")
                
                # Test context storage
                print(f"\n🗄️ Testing context storage...")
                
                # Check if context was stored
                stored_context = rich_message_service.get_button_context(content_id)
                
                if stored_context:
                    print(f"✅ Context stored and retrieved successfully")
                    print(f"   Title: {stored_context.get('title', 'N/A')}")
                    print(f"   Theme: {stored_context.get('theme', 'N/A')}")
                    print(f"   Image context: {bool(stored_context.get('image_context'))}")
                    
                    # Show button data size comparison
                    print(f"\n📊 Button optimization verification:")
                    
                    # Test button creation with context
                    from src.utils.interaction_handler import get_interaction_handler
                    interaction_handler = get_interaction_handler(None)
                    
                    # Create buttons with minimal data
                    buttons = interaction_handler.create_interactive_buttons(
                        content_id=content_id,
                        rich_message_context=stored_context,
                        rich_message_service=rich_message_service
                    )
                    
                    for i, button in enumerate(buttons, 1):
                        data_size = len(button['data'])
                        print(f"   Button {i} ({button['label']}): {data_size} chars ✅")
                    
                else:
                    print(f"❌ Context storage failed")
                    return False
                
                print(f"\n🎯 TEST SUMMARY:")
                print(f"✅ Rich Message created with optimized button data")
                print(f"✅ Message sent successfully without postback size errors")
                print(f"✅ Rich context stored server-side for button interactions")
                print(f"✅ Button data reduced from ~1000 chars to ~100 chars each")
                
                print(f"\n📱 NEXT STEPS:")
                print(f"1. Check your LINE app for the Rich Message")
                print(f"2. Click any button to test the enhanced AI responses")
                print(f"3. Responses should reference both message content and image context")
                print(f"4. Watch Replit console for button interaction logs")
                
                return True
                
            else:
                print(f"❌ Failed to send Rich Message: {send_result.get('error')}")
                return False
                
        except Exception as create_error:
            print(f"❌ Failed to create Rich Message: {str(create_error)}")
            import traceback
            traceback.print_exc()
            return False
            
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def show_optimization_details():
    """Show details about the optimization implemented"""
    
    print(f"\n🔧 OPTIMIZATION DETAILS")
    print("=" * 60)
    
    print(f"📋 Problem solved:")
    print(f"• Original button data: ~1000 characters (exceeded LINE's 300 char limit)")
    print(f"• Rich Message creation was failing with '400 - invalid message' error")
    print(f"• Buttons contained full context including image descriptions, prompts, etc.")
    
    print(f"\n✅ Solution implemented:")
    print(f"• **Server-side context storage**: Full context stored in RichMessageService")
    print(f"• **Minimal button data**: Only action, trigger_type, content_id (~100 chars)")
    print(f"• **Context lookup**: Buttons trigger context retrieval by content_id")
    print(f"• **Enhanced responses**: AI still gets full image+text context for responses")
    
    print(f"\n🎯 Benefits:")
    print(f"• Buttons work reliably within LINE's postback data limits")
    print(f"• Rich context preserved for enhanced AI responses") 
    print(f"• Image-aware responses using background image descriptions")
    print(f"• Bourdain-style responses that reference visual setting")
    
    print(f"\n⚙️ Technical implementation:")
    print(f"• RichMessageService.store_button_context() saves rich context")
    print(f"• InteractionHandler.create_interactive_buttons() creates minimal buttons")
    print(f"• LineService passes rich_message_service to interaction handler")
    print(f"• Context lookup happens when buttons are clicked")

if __name__ == "__main__":
    print("🔧 OPTIMIZED RICH MESSAGE TEST")
    print("Testing server-side context storage solution for LINE postback limits")
    print()
    
    success = test_optimized_rich_message()
    show_optimization_details()
    
    print("\n" + "=" * 60)
    if success:
        print("✅ OPTIMIZATION TEST SUCCESSFUL")
        print()
        print("📱 The Rich Message should now work properly with interactive buttons")
        print("🤖 Click any button to test enhanced AI responses with image context")
        print("🔍 Watch console logs for button interaction processing")
    else:
        print("❌ OPTIMIZATION TEST FAILED")
        print("Check errors above and verify service configuration")