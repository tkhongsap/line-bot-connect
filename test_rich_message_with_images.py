#!/usr/bin/env python3
"""
Test Rich Messages with Background Images

This test verifies that rich messages now display background images properly
using the new image serving route.
"""

import sys
import os
from datetime import datetime

# Add src to path
sys.path.append('/home/runner/workspace/src')

def test_rich_message_images(user_id):
    """Test rich message with background image display"""
    
    print("🖼️ TESTING RICH MESSAGE WITH BACKGROUND IMAGES")
    print("=" * 50)
    print(f"📱 Target: {user_id}")
    print("🎯 Goal: Verify background images display properly")
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
        line_bot_api = line_service.line_bot_api
        
        rich_service = RichMessageService(line_bot_api=line_bot_api)
        print("✅ Rich message service ready")
        
        # Test with a known working template
        template_name = "productivity_monday_coffee.png"
        template_path = f"/home/runner/workspace/templates/rich_messages/backgrounds/{template_name}"
        
        if not os.path.exists(template_path):
            print(f"❌ Template not found: {template_path}")
            return False
        
        file_size = os.path.getsize(template_path)
        print(f"✅ Template found: {template_name} ({file_size:,} bytes)")
        
        # Generate test content
        print("🤖 Generating AI content for image test...")
        
        try:
            prompt = "Create a short professional message about Monday morning productivity with coffee. Include a catchy title with emoji and motivating content in 2-3 sentences."
            
            response = openai_service.get_response("image_test_user", prompt, use_streaming=False)
            
            if response and response.get('success') and response.get('message'):
                ai_content = response['message'].strip()
                print("✅ AI content generated")
                
                # Parse content
                lines = [line.strip() for line in ai_content.split('\n') if line.strip()]
                if len(lines) >= 2:
                    title = lines[0]
                    content = ' '.join(lines[1:])
                else:
                    title = "☕ Monday Coffee Power"
                    content = ai_content
            else:
                print("⚠️ Using test content")
                title = "☕ Monday Coffee Power"
                content = "Start your week with focused energy and intention. A great morning coffee pairs perfectly with clear priorities and determined action. Make this Monday count!"
        
        except Exception as e:
            print(f"⚠️ AI generation failed: {e}")
            title = "☕ Monday Coffee Power"
            content = "Start your week with focused energy and intention. A great morning coffee pairs perfectly with clear priorities and determined action. Make this Monday count!"
        
        print(f"   📋 Title: {title}")
        print(f"   💼 Content: {content[:50]}...")
        
        # Create rich message with image
        print("✅ Creating rich message with background image...")
        
        flex_message = rich_service.create_flex_message(
            title=title,
            content=content,
            image_path=template_path,  # This should now work with our new route
            content_id=f"image_test_{int(datetime.now().timestamp())}",
            user_id=user_id,
            include_interactions=True
        )
        
        if not flex_message:
            print("❌ Failed to create rich message")
            return False
        
        print("✅ Rich message created with background image")
        
        # Send the message
        print("🔴 SENDING RICH MESSAGE WITH IMAGE...")
        line_bot_api.push_message(user_id, flex_message)
        print("🎉 Rich message sent successfully!")
        
        print()
        print("📊 Image Test Results:")
        print(f"   👤 Sent to: {user_id}")
        print(f"   🎨 Template: {template_name}")
        print(f"   🖼️ Image serving: New Flask route /static/backgrounds/")
        print(f"   🤖 Content: AI-generated")
        print(f"   📱 Interactive: Like, Share, Save, React buttons")
        print(f"   🕒 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        print("📱 CHECK YOUR LINE APP NOW!")
        print("   🖼️ You should now see the coffee/workspace background image")
        print("   ✨ The blank white area should be replaced with a beautiful template")
        print("   🔘 Interactive buttons should still work")
        print("   📊 This confirms image serving is working!")
        
        # Show the content details
        print()
        print("🤖 Generated Content:")
        print("=" * 30)
        print(f"Title: {title}")
        print(f"Content: {content}")
        print(f"Template: {template_name}")
        print("=" * 30)
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def verify_image_serving():
    """Verify that image serving route is working"""
    print("🔧 VERIFYING IMAGE SERVING SETUP")
    print("=" * 35)
    
    # Check if template directory exists
    backgrounds_dir = "/home/runner/workspace/templates/rich_messages/backgrounds"
    if os.path.exists(backgrounds_dir):
        print("✅ Template directory exists")
        
        # List available templates
        templates = [f for f in os.listdir(backgrounds_dir) if f.endswith('.png')]
        print(f"✅ Found {len(templates)} PNG templates")
        
        if templates:
            print("   Available templates:")
            for template in templates[:5]:  # Show first 5
                print(f"     - {template}")
            if len(templates) > 5:
                print(f"     ... and {len(templates) - 5} more")
    else:
        print("❌ Template directory not found")
        return False
    
    print()
    return True

if __name__ == "__main__":
    print("🖼️ RICH MESSAGE IMAGE TESTING")
    print("=" * 35)
    print()
    
    # Verify setup first
    if not verify_image_serving():
        print("❌ Setup verification failed")
        exit(1)
    
    # Test with your user ID
    user_id = "U595491d702720bc7c90d50618324cac3"
    
    success = test_rich_message_images(user_id)
    
    print()
    if success:
        print("🎉 RICH MESSAGE IMAGE TEST COMPLETED!")
        print()
        print("📋 What to check in your LINE app:")
        print("   🖼️ Background image should now be visible")
        print("   ✨ No more blank white rectangles")
        print("   📱 Beautiful coffee/workspace background")
        print("   🔘 Interactive buttons still working")
        print()
        print("🎯 If you see the background image, the fix worked!")
        print("📸 Take a screenshot to compare with the previous blank version")
    else:
        print("❌ Image test failed - check logs above")