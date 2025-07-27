#!/usr/bin/env python3
"""
Send Rich Message Test to LINE OA

This script sends a Rich Message with background image to test the fixes.
"""

import sys
import os
from datetime import datetime

# Add src to path
sys.path.append('/home/runner/workspace/src')

def send_test_rich_message(user_id):
    """Send a test Rich Message with background image"""
    
    print("📤 SENDING RICH MESSAGE TEST TO LINE OA")
    print("=" * 50)
    print(f"📱 Target User: {user_id}")
    print(f"🕐 Send Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    try:
        # Import services
        from src.services.rich_message_service import RichMessageService
        from src.services.line_service import LineService
        from src.services.openai_service import OpenAIService
        from src.services.conversation_service import ConversationService
        from src.config.settings import Settings
        
        print("✅ 1. Services imported successfully")
        
        # Initialize services
        settings = Settings()
        conversation_service = ConversationService()
        openai_service = OpenAIService(settings, conversation_service)
        line_service = LineService(settings, openai_service, conversation_service)
        
        # Create RichMessageService with explicit base URL
        rich_service = RichMessageService(
            line_bot_api=line_service.line_bot_api,
            base_url='https://line-bot-connect.replit.app'
        )
        print("✅ 2. Rich Message service initialized")
        
        # Select a nice template for testing
        template_name = "productivity_monday_coffee.png"  # Known working template
        template_path = f"/home/runner/workspace/templates/rich_messages/backgrounds/{template_name}"
        
        if not os.path.exists(template_path):
            print(f"❌ Template not found: {template_path}")
            return False
        
        file_size = os.path.getsize(template_path)
        print(f"✅ 3. Template selected: {template_name} ({file_size:,} bytes)")
        
        # Create engaging content
        title = "🚀 Background Image Test!"
        content = "This Rich Message should now display a beautiful coffee-themed background image instead of a blank white background. The fixes have been applied! ☕✨"
        
        print(f"✅ 4. Content prepared")
        print(f"   📋 Title: {title}")
        print(f"   💼 Content: {content[:60]}...")
        
        # Create Rich Message with background image
        print("🎨 5. Creating Rich Message with background image...")
        
        flex_message = rich_service.create_flex_message(
            title=title,
            content=content,
            image_path=template_path,
            content_id=f"bg_test_{int(datetime.now().timestamp())}",
            user_id=user_id,
            include_interactions=True
        )
        
        print("✅ 6. Rich Message created successfully")
        
        # Verify the structure before sending
        flex_dict = flex_message.as_json_dict()
        bubble = flex_dict.get('contents', {})
        hero = bubble.get('hero', {})
        
        if hero and hero.get('url'):
            print(f"✅ 7. Background image verified: {hero['url']}")
        else:
            print("❌ 7. Warning: No background image found in message")
            return False
        
        # Send the message
        print("📤 8. Sending Rich Message to LINE OA...")
        
        try:
            line_service.line_bot_api.push_message(user_id, flex_message)
            print("✅ 9. Rich Message sent successfully!")
            print()
            print("🎯 CHECK YOUR LINE APP NOW!")
            print("You should see a Rich Message with:")
            print("   📸 Coffee-themed background image")
            print("   📱 Text overlay with title and content")
            print("   🔘 Interactive buttons at the bottom")
            print()
            print("🔍 If you still see a blank white background, check:")
            print("   1. Your app is deployed on Replit")
            print("   2. The image serving route is accessible")
            print("   3. LINE can reach your HTTPS endpoint")
            
            return True
            
        except Exception as send_error:
            print(f"❌ 9. Failed to send message: {str(send_error)}")
            print("🔧 This could be due to:")
            print("   - Invalid user ID")
            print("   - LINE API credentials not configured")
            print("   - Network connectivity issues")
            return False
        
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    # You need to set your LINE user ID here
    # Check GET_YOUR_LINE_USER_ID.md for instructions on how to get it
    
    # Common LINE user ID patterns (replace with your actual ID):
    TEST_USER_ID = "YOUR_LINE_USER_ID_HERE"
    
    if TEST_USER_ID == "YOUR_LINE_USER_ID_HERE":
        print("⚠️  Please set your LINE user ID in the script")
        print("📖 To get your LINE user ID:")
        print("   1. Check GET_YOUR_LINE_USER_ID.md")
        print("   2. Or run: python get_my_user_id.py")
        print("   3. Then edit this script and set TEST_USER_ID")
        exit(1)
    
    success = send_test_rich_message(TEST_USER_ID)
    
    if success:
        print("\n🎉 Rich Message sent successfully!")
        print("📱 Check your LINE app to see the background image!")
    else:
        print("\n❌ Failed to send Rich Message")
        print("🔧 Check the error messages above for troubleshooting")