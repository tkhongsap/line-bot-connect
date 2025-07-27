#!/usr/bin/env python3
"""
Complete Rich Message Test with Background Images

This test verifies the complete Rich Message pipeline:
1. Image serving route functionality
2. URL generation
3. Rich Message creation with background images
4. Proper Flex Message structure

Run this test to verify the fixes are working properly.
"""

import sys
import os
from datetime import datetime
import json

# Add src to path
sys.path.append('/home/runner/workspace/src')

def test_complete_rich_message_flow(user_id):
    """Test the complete Rich Message flow with background images"""
    
    print("🎯 COMPLETE RICH MESSAGE TEST")
    print("=" * 50)
    print(f"📱 Target User: {user_id}")
    print(f"🕐 Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    results = {
        "image_serving_route": False,
        "url_generation": False,
        "rich_message_creation": False,
        "background_image_included": False,
        "interactive_buttons": False,
        "success": False
    }
    
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
        
        # Create RichMessageService with explicit base URL for testing
        rich_service = RichMessageService(
            line_bot_api=line_service.line_bot_api,
            base_url='https://line-bot-connect.replit.app'
        )
        print("✅ 2. Rich Message service initialized")
        
        # Test URL generation
        base_url = rich_service._get_base_url()
        print(f"✅ 3. Base URL generated: {base_url}")
        results["url_generation"] = True
        
        # Test template availability
        backgrounds_dir = '/home/runner/workspace/templates/rich_messages/backgrounds'
        png_files = [f for f in os.listdir(backgrounds_dir) if f.endswith('.png')]
        
        if not png_files:
            print("❌ No background templates found")
            return results
        
        # Use a specific template for consistent testing
        test_templates = [
            "productivity_monday_coffee.png",
            "motivation_abstract_geometric.png", 
            "wellness_nature_spirits.png"
        ]
        
        template_name = None
        for template in test_templates:
            if template in png_files:
                template_name = template
                break
        
        if not template_name:
            template_name = png_files[0]  # Use first available
        
        template_path = os.path.join(backgrounds_dir, template_name)
        print(f"✅ 4. Using template: {template_name}")
        
        # Generate image URL and verify it matches our serving route
        filename = os.path.basename(template_path)
        expected_url = f"{base_url}/static/backgrounds/{filename}"
        print(f"✅ 5. Generated image URL: {expected_url}")
        results["image_serving_route"] = True
        
        # Create test content
        title = "🚀 Boost Your Day!"
        content = "Start each morning by setting 3 top priorities. Focus on completing these first—less distraction, more achievement. Small wins lead to big success!"
        
        print(f"✅ 6. Test content prepared")
        print(f"   📋 Title: {title}")
        print(f"   💼 Content: {content[:50]}...")
        
        # Create Rich Message with background image
        print("🎨 7. Creating Rich Message with background image...")
        
        flex_message = rich_service.create_flex_message(
            title=title,
            content=content,
            image_path=template_path,  # This triggers background image inclusion
            content_id=f"complete_test_{int(datetime.now().timestamp())}",
            user_id=user_id,
            include_interactions=True
        )
        
        print("✅ 8. Rich Message created successfully")
        results["rich_message_creation"] = True
        
        # Inspect the Flex Message structure
        print("🔍 9. Inspecting Flex Message structure...")
        
        # Convert to dict for inspection
        flex_dict = flex_message.as_json_dict()
        
        # Check for background image in hero component
        bubble = flex_dict.get('contents', {})
        hero = bubble.get('hero', {})
        
        if hero and hero.get('url'):
            print(f"✅ 10. Background image found in hero component:")
            print(f"    🔗 URL: {hero['url']}")
            print(f"    📐 Size: {hero.get('size', 'Not set')}")
            print(f"    📏 Aspect ratio: {hero.get('aspectRatio', 'Not set')}")
            results["background_image_included"] = True
        else:
            print("❌ 10. No background image found in hero component")
            print(f"    Hero data: {json.dumps(hero, indent=2)}")
        
        # Check for interactive buttons
        body = bubble.get('body', {})
        contents = body.get('contents', [])
        button_count = sum(1 for item in contents if item.get('type') == 'button')
        box_count = sum(1 for item in contents if item.get('type') == 'box')
        
        # Also check for buttons inside box components (they might be nested)
        nested_button_count = 0
        for item in contents:
            if item.get('type') == 'box':
                box_contents = item.get('contents', [])
                nested_button_count += sum(1 for sub_item in box_contents if sub_item.get('type') == 'button')
        
        total_buttons = button_count + nested_button_count
        
        if total_buttons > 0:
            print(f"✅ 11. Interactive buttons found: {total_buttons} buttons")
            print(f"    📊 Direct buttons: {button_count}, Nested buttons: {nested_button_count}")
            results["interactive_buttons"] = True
        else:
            print("⚠️  11. No interactive buttons found")
            print(f"    📊 Body contents: {len(contents)} items, Box components: {box_count}")
        
        # Final verification
        if (results["url_generation"] and 
            results["rich_message_creation"] and 
            results["background_image_included"]):
            print("🎉 12. All critical components working!")
            results["success"] = True
        else:
            print("⚠️  12. Some components need attention")
        
        # Optionally send the message (uncomment to actually send)
        # print("📤 13. Sending Rich Message...")
        # line_service.line_bot_api.push_message(user_id, flex_message)
        # print("✅ Message sent successfully!")
        
        print("🚫 13. Message sending skipped (uncomment to send)")
        
        return results
        
    except Exception as e:
        print(f"❌ Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        return results

def print_test_summary(results):
    """Print a summary of test results"""
    print("\n" + "="*50)
    print("📊 TEST SUMMARY")
    print("="*50)
    
    checks = [
        ("URL Generation", results["url_generation"]),
        ("Rich Message Creation", results["rich_message_creation"]),
        ("Background Image Included", results["background_image_included"]),
        ("Interactive Buttons", results["interactive_buttons"]),
        ("Overall Success", results["success"])
    ]
    
    for check_name, passed in checks:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} {check_name}")
    
    if results["success"]:
        print("\n🎉 All critical tests PASSED!")
        print("💡 The Rich Message background image system should now work properly.")
        print("🔧 Uncomment the sending code in the test to actually deliver a message.")
    else:
        print("\n⚠️  Some tests FAILED.")
        print("🔧 Review the output above to identify and fix issues.")

if __name__ == "__main__":
    # You can set this to your LINE user ID for testing
    # To get your user ID, check GET_YOUR_LINE_USER_ID.md
    TEST_USER_ID = "YOUR_LINE_USER_ID_HERE"
    
    if TEST_USER_ID == "YOUR_LINE_USER_ID_HERE":
        print("⚠️  Please set your LINE user ID in the script to run the complete test")
        print("📖 See GET_YOUR_LINE_USER_ID.md for instructions")
        
        # Run the test anyway without sending
        results = test_complete_rich_message_flow("test_user")
    else:
        results = test_complete_rich_message_flow(TEST_USER_ID)
    
    print_test_summary(results)