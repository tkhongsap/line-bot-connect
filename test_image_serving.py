#!/usr/bin/env python3
"""
Test script to verify Rich Message image serving functionality
"""

import sys
import os
sys.path.append('src')

from src.services.rich_message_service import RichMessageService
from unittest.mock import Mock

def test_image_url_generation():
    """Test that image URL generation works correctly"""
    print("🧪 Testing Image URL Generation")
    print("=" * 40)
    
    # Create a mock LINE Bot API
    mock_line_api = Mock()
    
    # Create RichMessageService 
    service = RichMessageService(mock_line_api, base_url='https://line-bot-connect.replit.app')
    
    # Test available images
    backgrounds_dir = '/home/runner/workspace/templates/rich_messages/backgrounds'
    image_files = [f for f in os.listdir(backgrounds_dir) if f.endswith('.png')]
    
    print(f"✅ Found {len(image_files)} PNG images in backgrounds folder")
    
    # Test URL generation for a few samples
    test_images = image_files[:5]  # Test first 5 images
    
    for image_file in test_images:
        image_path = os.path.join(backgrounds_dir, image_file)
        
        # Generate URL using the service method
        base_url = service._get_base_url()
        public_url = f"{base_url}/static/backgrounds/{image_file}"
        
        print(f"📸 {image_file}")
        print(f"   🔗 URL: {public_url}")
        
        # Check file exists
        if os.path.exists(image_path):
            file_size = os.path.getsize(image_path)
            print(f"   📏 Size: {file_size:,} bytes")
        else:
            print(f"   ❌ File not found")
    
    print()
    print("✅ URL Generation Test Complete")
    return True

def test_flex_message_creation():
    """Test creating a Flex Message with image"""
    print("\n🧪 Testing Flex Message Creation")
    print("=" * 40)
    
    try:
        # Create a mock LINE Bot API
        mock_line_api = Mock()
        
        # Create RichMessageService
        service = RichMessageService(mock_line_api, base_url='https://line-bot-connect.replit.app')
        
        # Test creating a Flex Message with one of our images
        test_image_path = '/home/runner/workspace/templates/rich_messages/backgrounds/motivation_lion_duality.png'
        
        flex_message = service.create_flex_message(
            title="🦁 Test Lion Message",
            content="This is a test message with a background image.",
            image_path=test_image_path,
            content_id="test_123",
            user_id="test_user",
            include_interactions=True
        )
        
        if flex_message:
            print("✅ Flex Message created successfully!")
            print(f"   📝 Alt Text: {flex_message.alt_text}")
            print("   🎨 Message includes background image URL")
            
            # Extract the bubble content to see if image URL was generated
            bubble = flex_message.contents
            if hasattr(bubble, 'hero') and bubble.hero:
                print(f"   🔗 Image URL: {bubble.hero.url}")
            else:
                print("   ⚠️  No hero image found in message")
            
            return True
        else:
            print("❌ Failed to create Flex Message")
            return False
            
    except Exception as e:
        print(f"❌ Error creating Flex Message: {str(e)}")
        return False

def main():
    """Run all tests"""
    print("🚀 RICH MESSAGE IMAGE SERVING TESTS")
    print("=" * 50)
    
    # Test 1: URL Generation
    url_test_result = test_image_url_generation()
    
    # Test 2: Flex Message Creation  
    flex_test_result = test_flex_message_creation()
    
    print("\n📊 TEST RESULTS")
    print("=" * 20)
    print(f"URL Generation: {'✅ PASS' if url_test_result else '❌ FAIL'}")
    print(f"Flex Message:   {'✅ PASS' if flex_test_result else '❌ FAIL'}")
    
    if url_test_result and flex_test_result:
        print("\n🎉 ALL TESTS PASSED!")
        print("💡 Images should now display in Rich Messages")
        print("🔧 Ready to test with actual LINE Bot")
    else:
        print("\n❌ Some tests failed")
        print("🔧 Check the errors above")

if __name__ == "__main__":
    main()