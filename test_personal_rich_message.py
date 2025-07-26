#!/usr/bin/env python3
"""
Personal Rich Message Test Script

This script safely tests the Rich Message automation system by sending
a beautiful Little Prince themed message to YOU ONLY (not broadcast).

Usage:
1. Set your LINE_USER_ID below
2. Choose mock_mode=True for testing without sending
3. Run: python test_personal_rich_message.py
"""

import sys
import os
from datetime import datetime
from pathlib import Path

# Add src to path for imports
sys.path.append('/home/runner/workspace/src')

# Your LINE User ID - REPLACE WITH YOUR ACTUAL LINE USER ID
YOUR_LINE_USER_ID = "YOUR_LINE_USER_ID_HERE"  # Get this from your LINE bot conversation

def test_personal_rich_message(mock_mode=True):
    """
    Test Rich Message with Little Prince template - sent to you only
    
    Args:
        mock_mode (bool): If True, simulates sending without actually sending
    """
    
    print("🎨 PERSONAL RICH MESSAGE TEST - THE LITTLE PRINCE")
    print("=" * 60)
    print()
    
    # Validate USER_ID is set
    if YOUR_LINE_USER_ID == "YOUR_LINE_USER_ID_HERE":
        print("❌ ERROR: Please set YOUR_LINE_USER_ID in this script first!")
        print("💡 Get your LINE User ID by:")
        print("   1. Send any message to your LINE Bot")
        print("   2. Check the webhook logs for the user_id field")
        print("   3. Replace YOUR_LINE_USER_ID_HERE with your actual ID")
        return
    
    print(f"🎯 Target: {YOUR_LINE_USER_ID}")
    print(f"🧪 Mock Mode: {'ON (safe testing)' if mock_mode else 'OFF (will actually send)'}")
    print()
    
    try:
        # Import Rich Message components
        from src.services.rich_message_service import RichMessageService
        from src.services.line_service import LineService
        from src.services.openai_service import OpenAIService
        from src.services.conversation_service import ConversationService
        from src.config.settings import Settings
        from unittest.mock import Mock
        
        print("✅ Imported Rich Message services successfully")
        
        # Initialize services
        settings = Settings()
        
        if mock_mode:
            # Create mock LINE Bot API for safe testing
            mock_line_bot_api = Mock()
            mock_line_bot_api.push_message = Mock()
            print("✅ Created mock LINE Bot API (safe mode)")
        else:
            # Use real LINE Bot API - WARNING: WILL ACTUALLY SEND!
            openai_service = OpenAIService(settings)
            conversation_service = ConversationService(settings)
            line_service = LineService(settings, openai_service, conversation_service)
            mock_line_bot_api = line_service.line_bot_api
            print("⚠️  Using REAL LINE Bot API - message will be sent!")
        
        # Create Rich Message Service
        rich_message_service = RichMessageService(line_bot_api=mock_line_bot_api)
        
        # Step 1: Check Little Prince template availability
        prince_template_path = "/home/runner/workspace/templates/rich_messages/backgrounds/inspiration_prince_01.png"
        
        if os.path.exists(prince_template_path):
            print(f"✅ Found Little Prince template: {prince_template_path}")
        else:
            print(f"❌ Little Prince template not found at: {prince_template_path}")
            print("📁 Available templates:")
            bg_dir = "/home/runner/workspace/templates/rich_messages/backgrounds"
            if os.path.exists(bg_dir):
                for file in os.listdir(bg_dir):
                    if "prince" in file.lower():
                        print(f"   - {file}")
            return
        
        # Step 2: Create Little Prince themed content
        little_prince_content = {
            "title": "🌟 The Little Prince's Wisdom",
            "content": "\"What is essential is invisible to the eye. It is only with the heart that one can see rightly.\" - Let your heart guide your dreams today. Every day is a new adventure waiting to be discovered! ✨",
            "image_path": prince_template_path,
            "theme": "inspiration",
            "mood": "uplifting"
        }
        
        print("✅ Created Little Prince themed content:")
        print(f"   📝 Title: {little_prince_content['title']}")
        print(f"   💭 Content: {little_prince_content['content'][:50]}...")
        print()
        
        # Step 3: Create Rich Message with interactive buttons
        print("🎨 Creating Rich Message with interactive features...")
        
        flex_message = rich_message_service.create_flex_message(
            title=little_prince_content["title"],
            content=little_prince_content["content"],
            image_path=little_prince_content["image_path"],
            content_id="personal_test_prince_001",
            user_id=YOUR_LINE_USER_ID,
            include_interactions=True  # Add Like, Share, Save, React buttons
        )
        
        if flex_message:
            print("✅ Rich Message created successfully!")
            print(f"   🎭 Alt Text: {flex_message.alt_text}")
            print("   🔘 Interactive buttons: Like, Share, Save, React")
        else:
            print("❌ Failed to create Rich Message")
            return
        
        # Step 4: Send to your LINE account
        print()
        print("📤 Sending Rich Message...")
        
        if mock_mode:
            # Simulate sending
            mock_line_bot_api.push_message(YOUR_LINE_USER_ID, flex_message)
            print("✅ SIMULATED sending Rich Message to your LINE account")
            print("   (Mock mode - no actual message sent)")
            
            # Show what would have been sent
            print()
            print("📋 Message Details:")
            print(f"   👤 Recipient: {YOUR_LINE_USER_ID}")
            print(f"   🎨 Template: Little Prince inspiration")
            print(f"   📱 Type: Flex Message with interactive buttons")
            print(f"   ⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
        else:
            # Actually send the message
            try:
                mock_line_bot_api.push_message(YOUR_LINE_USER_ID, flex_message)
                print("✅ Rich Message sent successfully to your LINE account!")
                print("📱 Check your LINE app to see the message with interactive buttons")
                
                # Track the send
                print()
                print("📊 Delivery tracking:")
                print(f"   ✉️  Sent to: {YOUR_LINE_USER_ID}")
                print(f"   🕒 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"   🎨 Template: inspiration_prince_01.png")
                
            except Exception as e:
                print(f"❌ Failed to send Rich Message: {str(e)}")
                print("💡 This might be due to:")
                print("   - Invalid LINE_USER_ID")
                print("   - LINE Bot API configuration issues")
                print("   - Network connectivity problems")
                return
        
        # Step 5: Instructions for testing interactions
        print()
        print("🎮 INTERACTION TESTING:")
        print("-" * 30)
        print("When you receive the message, try:")
        print("💝 Like button - Track user engagement")
        print("📤 Share button - Test sharing functionality") 
        print("💾 Save button - Test content saving")
        print("😊 React button - Test emoji reactions")
        print()
        print("📈 All interactions will be tracked in the analytics system!")
        
        # Step 6: How to check analytics
        print()
        print("📊 TO CHECK ANALYTICS AFTER TESTING:")
        print("-" * 40)
        print("```python")
        print("from src.utils.analytics_tracker import get_analytics_tracker")
        print("analytics = get_analytics_tracker()")
        print("metrics = analytics.calculate_system_metrics()")
        print("print(f'Messages sent: {metrics.total_messages}')")
        print("```")
        
    except ImportError as e:
        print(f"❌ Import error: {str(e)}")
        print("💡 Make sure you're running from the project root directory")
        
    except Exception as e:
        print(f"❌ Error during testing: {str(e)}")
        print("💡 Check your environment configuration and LINE Bot setup")
    
    print()
    print("=" * 60)
    print("🎉 Personal Rich Message Test Complete!")
    print("🔧 To actually send: Set mock_mode=False and run again")
    print("=" * 60)


def get_user_id_instructions():
    """Show instructions for getting your LINE User ID"""
    
    print("📱 HOW TO GET YOUR LINE USER ID:")
    print("=" * 40)
    print()
    print("Method 1: From webhook logs")
    print("1. Send any message to your LINE Bot")
    print("2. Check the webhook logs in your console")
    print("3. Look for the 'user_id' field in the JSON")
    print("4. Copy the user ID (starts with 'U' followed by 32 characters)")
    print()
    print("Method 2: From LINE Bot conversation")
    print("1. Add your bot as a friend")
    print("2. Send a message to it")
    print("3. Check the server logs for the user_id")
    print()
    print("Example LINE User ID format: Udeadbeefdeadbeefdeadbeefdeadbeef")
    print()
    print("⚠️  Keep your User ID private - it's like your personal LINE address!")


if __name__ == "__main__":
    print("🤖 Rich Message Personal Test Script")
    print()
    
    # Check if user has set their LINE User ID
    if len(sys.argv) > 1:
        if sys.argv[1] == "--help":
            get_user_id_instructions()
            sys.exit(0)
        elif sys.argv[1] == "--send":
            # Actually send the message
            test_personal_rich_message(mock_mode=False)
        elif sys.argv[1] == "--user-id":
            get_user_id_instructions()
        else:
            print(f"Unknown option: {sys.argv[1]}")
            print("Use --help for instructions or --send to actually send")
    else:
        # Default: mock mode (safe testing)
        test_personal_rich_message(mock_mode=True)