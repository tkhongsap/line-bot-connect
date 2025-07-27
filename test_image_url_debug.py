#!/usr/bin/env python3
"""
Debug the exact image URLs being generated for rich messages
"""

import sys
import os
import requests

# Add src to path
sys.path.append('/home/runner/workspace/src')

def test_image_url_generation():
    """Test what URLs are being generated for rich message images"""
    
    print("🔍 DEBUGGING IMAGE URL GENERATION")
    print("=" * 40)
    
    try:
        from src.services.rich_message_service import RichMessageService
        from src.services.line_service import LineService
        from src.services.openai_service import OpenAIService
        from src.services.conversation_service import ConversationService
        from src.config.settings import Settings
        
        # Initialize services
        settings = Settings()
        conversation_service = ConversationService()
        openai_service = OpenAIService(settings, conversation_service)
        line_service = LineService(settings, openai_service, conversation_service)
        line_bot_api = line_service.line_bot_api
        
        rich_service = RichMessageService(line_bot_api=line_bot_api)
        
        # Test URL generation
        test_image_path = "/home/runner/workspace/templates/rich_messages/backgrounds/productivity_monday_coffee.png"
        
        # Check the _get_base_url method
        base_url = rich_service._get_base_url()
        print(f"📍 Base URL: {base_url}")
        
        # Generate the image URL
        filename = os.path.basename(test_image_path)
        public_image_url = f"{base_url}/static/backgrounds/{filename}"
        print(f"🖼️ Generated Image URL: {public_image_url}")
        
        # Test if URL is accessible
        print("\n🌐 Testing URL accessibility...")
        try:
            response = requests.head(public_image_url, timeout=10)
            print(f"✅ Status Code: {response.status_code}")
            print(f"📄 Headers: {dict(response.headers)}")
            
            if response.status_code == 200:
                print("✅ URL is accessible!")
            else:
                print(f"❌ URL not accessible: {response.status_code}")
                
        except Exception as e:
            print(f"❌ Failed to access URL: {e}")
        
        # Test creating a flex message and see what URL it uses
        print("\n🔧 Testing Flex Message Creation...")
        
        flex_message = rich_service.create_flex_message(
            title="URL Test",
            content="Testing image URL generation",
            image_path=test_image_path,
            content_id="url_test_123"
        )
        
        if flex_message:
            # Extract the actual URL from the flex message
            flex_content = flex_message.contents
            if hasattr(flex_content, 'hero') and flex_content.hero:
                actual_url = flex_content.hero.url
                print(f"🎯 Actual URL in Flex Message: {actual_url}")
                
                # Test this URL too
                try:
                    response = requests.head(actual_url, timeout=10)
                    print(f"✅ Flex URL Status: {response.status_code}")
                except Exception as e:
                    print(f"❌ Flex URL Failed: {e}")
            else:
                print("❌ No hero image found in flex message")
        else:
            print("❌ Failed to create flex message")
            
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_direct_urls():
    """Test various URL formats directly"""
    
    print("\n🧪 TESTING DIFFERENT URL FORMATS")
    print("=" * 35)
    
    urls_to_test = [
        "https://line-bot-connect-tkhongsap.replit.app/static/backgrounds/productivity_monday_coffee.png",
        "https://3a0d8469-1495-4b1d-afe6-dc163885326a-00-2icgob4ardifi.worf.replit.dev/static/backgrounds/productivity_monday_coffee.png"
    ]
    
    for url in urls_to_test:
        print(f"\n🔗 Testing: {url}")
        try:
            response = requests.head(url, timeout=10)
            print(f"   Status: {response.status_code}")
            print(f"   Content-Type: {response.headers.get('content-type', 'Not set')}")
            print(f"   Content-Length: {response.headers.get('content-length', 'Not set')}")
            
            if response.status_code == 200:
                print("   ✅ Accessible")
            else:
                print(f"   ❌ Not accessible")
                
        except Exception as e:
            print(f"   ❌ Error: {e}")

if __name__ == "__main__":
    print("🔍 IMAGE URL DEBUG TEST")
    print("=" * 25)
    
    success = test_image_url_generation()
    test_direct_urls()
    
    print("\n📋 Summary:")
    print("- Check if the generated URL matches what LINE expects")
    print("- Verify the URL is accessible from external sources")
    print("- Look for any URL format issues")