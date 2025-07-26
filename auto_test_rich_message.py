#!/usr/bin/env python3
"""
Automated Rich Message Test

This script automatically configures and tests Rich Message with your User ID.
"""

import sys
import os
from datetime import datetime

# Add src to path
sys.path.append('/home/runner/workspace/src')

def auto_test_with_user_id(user_id, send_mode=False):
    """
    Automatically test Rich Message with the provided User ID
    
    Args:
        user_id (str): Your LINE User ID (starts with 'U')
        send_mode (bool): If True, actually sends the message
    """
    
    print("🤖 AUTOMATED RICH MESSAGE TEST")
    print("=" * 50)
    print()
    print(f"🎯 Target User ID: {user_id}")
    print(f"📨 Send Mode: {'LIVE (will send!)' if send_mode else 'MOCK (safe testing)'}")
    print(f"🎨 Template: Little Prince (inspiration_prince_01.png)")
    print()
    
    # Validate User ID format
    if not user_id.startswith('U') or len(user_id) != 33:
        print("❌ Invalid User ID format!")
        print("   Expected: U + 32 characters")
        print(f"   Received: {user_id} (length: {len(user_id)})")
        print()
        print("💡 Please provide the correct LINE User ID")
        return False
    
    try:
        # Import components
        print("📦 Loading Rich Message components...")
        from src.services.rich_message_service import RichMessageService
        from src.services.line_service import LineService
        from src.services.openai_service import OpenAIService
        from src.services.conversation_service import ConversationService
        from src.config.settings import Settings
        from unittest.mock import Mock
        print("✅ Components loaded successfully")
        
        # Initialize services
        print()
        print("⚙️ Initializing services...")
        settings = Settings()
        
        if send_mode:
            # Real services for actual sending
            print("🔴 Initializing REAL services (will send message!)")
            openai_service = OpenAIService(settings)
            conversation_service = ConversationService(settings)
            line_service = LineService(settings, openai_service, conversation_service)
            line_bot_api = line_service.line_bot_api
        else:
            # Mock services for safe testing
            print("🟡 Initializing MOCK services (safe mode)")
            line_bot_api = Mock()
            line_bot_api.push_message = Mock()
        
        rich_service = RichMessageService(line_bot_api=line_bot_api)
        print("✅ Services initialized")
        
        # Check Little Prince template
        print()
        print("🎨 Checking Little Prince template...")
        prince_template = "/home/runner/workspace/templates/rich_messages/backgrounds/inspiration_prince_01.png"
        
        if os.path.exists(prince_template):
            print("✅ Little Prince template found")
            file_size = os.path.getsize(prince_template)
            print(f"   📏 Size: {file_size:,} bytes")
        else:
            print("⚠️  Original template not found, checking alternatives...")
            # Check for converted version
            converted_prince = "/home/runner/workspace/templates/rich_messages/backgrounds/general_motivation_inspiration_prince_01_v1.jpg"
            if os.path.exists(converted_prince):
                prince_template = converted_prince
                print(f"✅ Found converted Little Prince template: {prince_template}")
            else:
                print("❌ No Little Prince template found")
                return False
        
        # Create Little Prince themed content
        print()
        print("✍️ Creating Little Prince themed content...")
        
        little_prince_quotes = [
            "What is essential is invisible to the eye. It is only with the heart that one can see rightly.",
            "All grown-ups were once children... but only few of them remember it.",
            "You become responsible, forever, for what you have tamed.",
            "A goal without a plan is just a wish. But you have the power to make your dreams reality!",
            "The most beautiful things in the world cannot be seen or touched, they are felt with the heart."
        ]
        
        import random
        selected_quote = random.choice(little_prince_quotes)
        
        rich_content = {
            "title": "🌟 The Little Prince's Wisdom",
            "content": f'"{selected_quote}" ✨\n\nLet your heart guide your dreams today. Every moment is a new adventure waiting to be discovered!',
            "template_path": prince_template
        }
        
        print("✅ Content created:")
        print(f"   📝 Title: {rich_content['title']}")
        print(f"   💭 Quote: {selected_quote[:50]}...")
        
        # Create Rich Message
        print()
        print("🎨 Creating Rich Message with interactive features...")
        
        flex_message = rich_service.create_flex_message(
            title=rich_content["title"],
            content=rich_content["content"],
            image_path=rich_content["template_path"],
            content_id=f"auto_test_{int(datetime.now().timestamp())}",
            user_id=user_id,
            include_interactions=True
        )
        
        if flex_message:
            print("✅ Rich Message created successfully!")
            print(f"   🎭 Alt Text: {flex_message.alt_text[:50]}...")
            print("   🔘 Interactive: Like, Share, Save, React buttons")
            print("   🎨 Template: Little Prince artwork")
        else:
            print("❌ Failed to create Rich Message")
            return False
        
        # Send the message
        print()
        print("📤 Sending Rich Message...")
        
        try:
            if send_mode:
                print("🔴 SENDING LIVE MESSAGE...")
                line_bot_api.push_message(user_id, flex_message)
                print("✅ Rich Message sent successfully!")
                print()
                print("📱 CHECK YOUR LINE APP!")
                print("   🎨 Look for the Little Prince message")
                print("   🔘 Try the interactive buttons:")
                print("      💝 Like - Track engagement")
                print("      📤 Share - Test sharing")
                print("      💾 Save - Test saving")
                print("      😊 React - Test reactions")
                
            else:
                print("🟡 MOCK SEND (safe mode)")
                line_bot_api.push_message(user_id, flex_message)
                print("✅ Mock send successful!")
                print("   (No actual message sent)")
            
            # Log the send
            print()
            print("📊 Send Details:")
            print(f"   👤 Recipient: {user_id}")
            print(f"   🕒 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"   🎨 Template: Little Prince inspiration")
            print(f"   📨 Mode: {'LIVE' if send_mode else 'MOCK'}")
            
            return True
            
        except Exception as e:
            print(f"❌ Send failed: {str(e)}")
            print()
            print("💡 Possible issues:")
            print("   - LINE Bot API configuration")
            print("   - Invalid User ID")
            print("   - Network connectivity")
            print("   - LINE Bot permissions")
            return False
        
    except ImportError as e:
        print(f"❌ Import error: {str(e)}")
        print("💡 Make sure you're in the project root directory")
        return False
        
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        return False

def main():
    """Main function with command line options"""
    
    print("🤖 Automated Rich Message Test Tool")
    print()
    
    if len(sys.argv) < 2:
        print("❌ Missing User ID!")
        print()
        print("Usage:")
        print("   python auto_test_rich_message.py <USER_ID>")
        print("   python auto_test_rich_message.py <USER_ID> --send")
        print()
        print("Example:")
        print("   python auto_test_rich_message.py U1234567890abcdef1234567890abcdef")
        print("   python auto_test_rich_message.py U1234567890abcdef1234567890abcdef --send")
        print()
        print("💡 Run capture_user_id.py first to get your User ID")
        return
    
    user_id = sys.argv[1]
    send_mode = "--send" in sys.argv
    
    if send_mode:
        print("⚠️  LIVE SEND MODE - Message will be sent to your LINE account!")
        print("   Continue? (press Enter to confirm, Ctrl+C to cancel)")
        try:
            input()
        except KeyboardInterrupt:
            print("\n❌ Cancelled by user")
            return
    
    # Run the automated test
    success = auto_test_with_user_id(user_id, send_mode)
    
    print()
    print("=" * 50)
    if success:
        print("🎉 AUTOMATED TEST COMPLETE!")
        if send_mode:
            print("📱 Check your LINE app for the Little Prince message!")
        else:
            print("🔧 Run with --send to actually send the message")
    else:
        print("❌ Test failed - check the errors above")
    print("=" * 50)

if __name__ == "__main__":
    main()