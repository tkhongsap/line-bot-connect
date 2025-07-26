#!/usr/bin/env python3
"""
Get Your LINE User ID Tool

This simple tool helps you capture your LINE User ID by monitoring
webhook events when you send a message to your bot.

Usage:
1. Run this script: python get_my_user_id.py
2. Send any message to your LINE Bot
3. Your User ID will be displayed and saved to user_id.txt

This makes it easy to get your User ID for testing rich messages!
"""

import sys
import time
import json
from datetime import datetime

# Add src to path
sys.path.append('/home/runner/workspace/src')

def monitor_for_user_id():
    """Monitor for incoming LINE messages to capture User ID"""
    
    print("📱 LINE USER ID CAPTURE TOOL")
    print("=" * 40)
    print()
    print("🎯 Instructions:")
    print("1. Keep this script running")
    print("2. Send ANY message to your LINE Bot")
    print("3. Your User ID will be captured and displayed")
    print()
    print("⏳ Waiting for your message...")
    print("   (Press Ctrl+C to stop)")
    print()
    
    # Store captured user IDs
    captured_users = set()
    
    try:
        # Import services to access the LINE service
        from src.services.line_service import LineService
        from src.services.openai_service import OpenAIService
        from src.services.conversation_service import ConversationService
        from src.config.settings import Settings
        
        # Initialize services
        settings = Settings()
        conversation_service = ConversationService()
        openai_service = OpenAIService(settings, conversation_service)
        line_service = LineService(settings, openai_service, conversation_service)
        
        print("✅ LINE Bot services connected")
        print("📡 Monitoring webhook events...")
        print()
        print("💡 TIP: Send a simple message like 'hello' to your bot")
        print()
        
        # Patch the text message handler to capture user IDs
        original_handle_text = line_service._handle_text_message
        
        def capture_user_id_handler(event):
            user_id = event.source.user_id
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            if user_id not in captured_users:
                captured_users.add(user_id)
                
                print(f"🎉 USER ID CAPTURED!")
                print(f"   👤 User ID: {user_id}")
                print(f"   🕒 Time: {timestamp}")
                print(f"   📝 Message: {event.message.text}")
                print()
                
                # Save to file
                with open('user_id.txt', 'w') as f:
                    f.write(f"# Your LINE User ID (captured on {timestamp})\n")
                    f.write(f"USER_ID = \"{user_id}\"\n")
                
                print("💾 Saved to user_id.txt")
                print()
                print("✅ SUCCESS! You can now use this User ID for rich message testing.")
                print(f"   Copy this: {user_id}")
                print()
                print("🎨 Next steps:")
                print("   1. Copy your User ID above")
                print("   2. Edit send_test_rich_message.py")
                print("   3. Replace YOUR_LINE_USER_ID_HERE with your actual ID")
                print("   4. Run: python send_test_rich_message.py")
                print()
                print("Press Ctrl+C to exit...")
            
            # Still call the original handler
            return original_handle_text(event)
        
        # Replace the handler
        line_service._handle_text_message = capture_user_id_handler
        
        # Keep the script running
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n👋 Monitoring stopped")
        if captured_users:
            print("✅ User IDs captured:")
            for user_id in captured_users:
                print(f"   📋 {user_id}")
        else:
            print("ℹ️  No messages received")
        
    except ImportError as e:
        print(f"❌ Import error: {str(e)}")
        print("💡 Make sure you're in the project root directory")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        print()
        print("💡 Alternative method:")
        print("   1. Send a message to your LINE Bot")
        print("   2. Check the Replit console logs")
        print("   3. Look for webhook events with 'user_id' field")

def show_manual_instructions():
    """Show manual instructions for getting User ID"""
    
    print("📋 MANUAL METHOD TO GET YOUR USER ID:")
    print("=" * 50)
    print()
    print("If the automatic capture doesn't work, follow these steps:")
    print()
    print("1. 📱 Send any message to your LINE Bot")
    print("   (A simple 'hello' works fine)")
    print()
    print("2. 👀 Check your Replit console logs")
    print("   Look for webhook events in the bottom panel")
    print()
    print("3. 🔍 Find the JSON with 'user_id' field")
    print("   It looks like this:")
    print('   "source": {')
    print('     "type": "user",')
    print('     "userId": "Udeadbeefdeadbeefdeadbeef..." ← This is your ID')
    print('   }')
    print()
    print("4. 📋 Copy the User ID")
    print("   It starts with 'U' and has 32 more characters")
    print("   Total length: 33 characters")
    print()
    print("5. 🔧 Use it in the test script")
    print("   Edit send_test_rich_message.py")
    print("   Replace YOUR_LINE_USER_ID_HERE with your actual ID")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--manual":
        show_manual_instructions()
    else:
        monitor_for_user_id()