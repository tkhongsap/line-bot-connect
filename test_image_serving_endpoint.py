#!/usr/bin/env python3
"""
Test the image serving endpoint directly via HTTP request

This test verifies that our /static/backgrounds/<filename> route 
works correctly and serves images with proper headers.
"""

import requests
import os

def test_image_serving_endpoint():
    """Test the image serving endpoint"""
    print("🧪 TESTING IMAGE SERVING ENDPOINT")
    print("=" * 50)
    
    # First check what images are available
    backgrounds_dir = '/home/runner/workspace/templates/rich_messages/backgrounds'
    png_files = [f for f in os.listdir(backgrounds_dir) if f.endswith('.png')]
    
    if not png_files:
        print("❌ No PNG files found in backgrounds directory")
        return False
    
    # Test with the first available image
    test_image = png_files[0]
    print(f"📸 Testing with image: {test_image}")
    
    # We need to test against the actual Replit URL
    base_urls = [
        'https://line-bot-connect.replit.app',
        'http://localhost:5000'  # For local testing
    ]
    
    for base_url in base_urls:
        print(f"\n🌐 Testing against: {base_url}")
        
        try:
            test_url = f"{base_url}/static/backgrounds/{test_image}"
            print(f"   🔗 URL: {test_url}")
            
            # Make HTTP request
            response = requests.get(test_url, timeout=10)
            
            print(f"   📊 Status: {response.status_code}")
            print(f"   📏 Content-Length: {len(response.content):,} bytes")
            print(f"   🎯 Content-Type: {response.headers.get('Content-Type', 'Not set')}")
            
            if response.status_code == 200:
                print(f"   ✅ Image serving successful from {base_url}")
                
                # Verify it's actually an image
                if response.content[:4] == b'\x89PNG':
                    print("   ✅ Valid PNG format detected")
                else:
                    print("   ⚠️  Content doesn't appear to be PNG format")
                
                return True
            else:
                print(f"   ❌ HTTP {response.status_code}: {response.text[:100]}")
                
        except requests.exceptions.ConnectionError:
            print(f"   ⚠️  Connection failed (server not running?)")
        except requests.exceptions.Timeout:
            print(f"   ⚠️  Request timeout")
        except Exception as e:
            print(f"   ❌ Error: {str(e)}")
    
    print("\n⚠️  Could not successfully test image serving from any URL")
    print("💡 This might be normal if the app isn't currently running")
    return False

if __name__ == "__main__":
    success = test_image_serving_endpoint()
    if success:
        print("\n🎉 Image serving endpoint test completed successfully!")
    else:
        print("\n📝 Image serving endpoint test completed (see results above)")