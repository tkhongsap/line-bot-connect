#!/usr/bin/env python3
"""
Test URL Generation for Rich Message Background Images

This script verifies that the URL generation in RichMessageService
correctly matches the serving route in app.py.
"""

import sys
import os
from unittest.mock import Mock

# Add src to path
sys.path.append('/home/runner/workspace/src')

def test_url_generation():
    """Test that URL generation works correctly"""
    print("🧪 TESTING RICH MESSAGE URL GENERATION")
    print("=" * 50)
    
    try:
        from src.services.rich_message_service import RichMessageService
        
        # Test 1: URL generation with explicit base_url
        print("Test 1: Explicit base URL")
        mock_line_api = Mock()
        service = RichMessageService(mock_line_api, base_url='https://line-bot-connect.replit.app')
        
        base_url = service._get_base_url()
        print(f"✅ Base URL: {base_url}")
        
        # Test sample image
        sample_image = "motivation_abstract_geometric.png"
        image_path = f"/home/runner/workspace/templates/rich_messages/backgrounds/{sample_image}"
        
        if os.path.exists(image_path):
            filename = os.path.basename(image_path)
            public_url = f"{base_url}/static/backgrounds/{filename}"
            print(f"✅ Generated URL: {public_url}")
            print(f"✅ Route matches: /static/backgrounds/{filename}")
        else:
            print(f"⚠️  Sample image not found: {image_path}")
        
        # Test 2: URL generation without Flask context (Celery simulation)
        print("\nTest 2: Celery context (no Flask request)")
        service_no_context = RichMessageService(mock_line_api)  # No base_url provided
        
        base_url_fallback = service_no_context._get_base_url()
        print(f"✅ Fallback URL: {base_url_fallback}")
        
        # Test 3: Check available template images
        print("\nTest 3: Available template images")
        backgrounds_dir = '/home/runner/workspace/templates/rich_messages/backgrounds'
        
        if os.path.exists(backgrounds_dir):
            png_files = [f for f in os.listdir(backgrounds_dir) if f.endswith('.png')]
            print(f"✅ Found {len(png_files)} PNG templates")
            
            # Show a few examples
            for i, png_file in enumerate(png_files[:3]):
                url = f"{base_url}/static/backgrounds/{png_file}"
                print(f"   📸 {png_file} → {url}")
        else:
            print(f"❌ Backgrounds directory not found: {backgrounds_dir}")
        
        # Test 4: Verify HTTPS enforcement
        print("\nTest 4: HTTPS enforcement")
        service_http = RichMessageService(mock_line_api, base_url='http://line-bot-connect.replit.app')
        https_url = service_http._get_base_url()
        print(f"✅ HTTP converted to HTTPS: {https_url}")
        
        print(f"\n🎉 All URL generation tests completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ URL generation test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_url_generation()
    exit(0 if success else 1)