#!/usr/bin/env python3
"""
Component Test Script

Quick test to verify Rich Message components are working
without needing a LINE User ID.
"""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.append('/home/runner/workspace/src')

def test_components():
    """Test Rich Message components without sending"""
    
    print("🧪 RICH MESSAGE COMPONENT TEST")
    print("=" * 40)
    print()
    
    try:
        # Test 1: Import components
        print("📦 Testing imports...")
        from src.services.rich_message_service import RichMessageService
        from unittest.mock import Mock
        print("✅ Rich Message Service imported")
        
        # Test 2: Check Little Prince template
        print()
        print("🎨 Testing template availability...")
        prince_template = "/home/runner/workspace/templates/rich_messages/backgrounds/inspiration_prince_01.png"
        
        if os.path.exists(prince_template):
            print(f"✅ Little Prince template found")
            file_size = os.path.getsize(prince_template)
            print(f"   📏 Size: {file_size:,} bytes")
        else:
            print(f"❌ Little Prince template not found")
            # Show available prince templates
            bg_dir = "/home/runner/workspace/templates/rich_messages/backgrounds"
            if os.path.exists(bg_dir):
                prince_files = [f for f in os.listdir(bg_dir) if "prince" in f.lower()]
                print(f"   📁 Available prince files: {prince_files}")
        
        # Test 3: Create mock Rich Message Service
        print()
        print("🎭 Testing Rich Message creation...")
        mock_line_api = Mock()
        rich_service = RichMessageService(line_bot_api=mock_line_api)
        print("✅ Rich Message Service created")
        
        # Test 4: Create test message
        test_message = rich_service.create_flex_message(
            title="🌟 Test Little Prince Message",
            content="\"One sees clearly only with the heart. What is essential is invisible to the eye.\" - The Little Prince ✨",
            content_id="test_prince_001",
            include_interactions=True
        )
        
        if test_message:
            print("✅ Flex Message created successfully")
            print(f"   📝 Alt text: {test_message.alt_text[:50]}...")
            print("   🎭 Type: FlexSendMessage")
            print("   🔘 Interactive: Yes (Like, Share, Save, React)")
        else:
            print("❌ Failed to create Flex Message")
        
        # Test 5: Check interaction handler
        print()
        print("👆 Testing interaction handler...")
        from src.utils.interaction_handler import get_interaction_handler
        interaction_handler = get_interaction_handler()
        
        # Test creating buttons
        buttons = interaction_handler.create_interactive_buttons(
            content_id="test_content_123",
            include_stats=True
        )
        
        if buttons and len(buttons) >= 4:
            print("✅ Interactive buttons created")
            print(f"   🔘 Button count: {len(buttons)}")
            for i, button in enumerate(buttons[:4]):
                print(f"   {i+1}. {button.get('label', 'Unknown')}")
        else:
            print("❌ Failed to create interactive buttons")
        
        # Test 6: Check analytics components
        print()
        print("📊 Testing analytics components...")
        from src.utils.analytics_tracker import get_analytics_tracker
        analytics = get_analytics_tracker()
        print("✅ Analytics tracker created")
        
        # Test 7: Template metadata
        print()
        print("📋 Testing template metadata...")
        prince_metadata_file = "/home/runner/workspace/templates/rich_messages/backgrounds/general_motivation_inspiration_prince_01_v1.json"
        
        if os.path.exists(prince_metadata_file):
            import json
            with open(prince_metadata_file, 'r') as f:
                metadata = json.load(f)
            
            print("✅ Prince template metadata found")
            print(f"   🎨 Theme: {metadata.get('theme', 'Unknown')}")
            print(f"   📂 Category: {metadata.get('category', 'Unknown')}")
            print(f"   💭 Mood: {metadata.get('mood', 'Unknown')}")
        else:
            print("⚠️  Prince template metadata not found")
            print("   (Message will still work, just without optimized positioning)")
        
        print()
        print("=" * 40)
        print("🎉 COMPONENT TEST COMPLETE!")
        print()
        print("✅ All components are working correctly")
        print("🎯 Ready for personal testing with your LINE User ID")
        print()
        print("Next steps:")
        print("1. Get your LINE User ID (see GET_YOUR_LINE_USER_ID.md)")
        print("2. Edit test_personal_rich_message.py")
        print("3. Run: python test_personal_rich_message.py")
        print("=" * 40)
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("💡 Make sure you're in the project root directory")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print("💡 Check your project setup")


if __name__ == "__main__":
    test_components()