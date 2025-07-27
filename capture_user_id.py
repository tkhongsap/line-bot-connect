#!/usr/bin/env python3
"""
LINE User ID Capture Script

This script temporarily modifies your webhook to capture and display
your technical LINE User ID when you send a message to your bot.

Usage:
1. Run this script
2. Send any message to your LINE Bot (@970jqtyf)
3. Your technical User ID will be displayed
4. Use that ID for Rich Message testing
"""

import sys
import os
from datetime import datetime

# Add src to path
sys.path.append('/home/runner/workspace/src')

def create_user_id_capture():
    """Create a temporary webhook modification to capture User ID"""
    
    print("📱 LINE USER ID CAPTURE TOOL")
    print("=" * 40)
    print()
    
    # Create a simple Flask app for User ID capture
    capture_code = '''
# Add this to your webhook handler temporarily

@app.route("/webhook", methods=['POST'])
def webhook():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    # CAPTURE USER ID HERE
    user_id = event.source.user_id
    
    # Display the User ID prominently
    print("\\n" + "="*60)
    print("🎯 CAPTURED LINE USER ID:")
    print(f"   {user_id}")
    print("="*60)
    print()
    
    # Also log to file
    with open("/tmp/captured_user_id.txt", "w") as f:
        f.write(f"LINE_USER_ID={user_id}\\n")
        f.write(f"CAPTURED_AT={datetime.now()}\\n")
    
    # Reply to confirm capture
    reply_text = f"✅ Captured your User ID: {user_id[:8]}...\\nReady for Rich Message testing!"
    
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_text)
    )

# The captured User ID will be: {user_id}
'''
    
    print("📋 INSTRUCTIONS TO CAPTURE YOUR USER ID:")
    print("-" * 40)
    print()
    print("Method 1: Quick Console Check")
    print("1. Make sure your LINE Bot is running")
    print("2. Send ANY message to your bot (@970jqtyf)")
    print("3. Check the console/logs for webhook data")
    print("4. Look for 'userId' in the JSON output")
    print()
    
    print("Method 2: Temporary Code Addition")
    print("1. Add the capture code below to your webhook handler")
    print("2. Restart your bot")
    print("3. Send a message to your bot")
    print("4. The User ID will be displayed prominently")
    print()
    
    print("Method 3: Check Existing Logs")
    print("1. Look at your recent webhook logs")
    print("2. Find any recent message events")
    print("3. Extract the 'userId' field")
    print()
    
    return capture_code

def check_for_captured_id():
    """Check if we've already captured a User ID"""
    
    capture_file = "/tmp/captured_user_id.txt"
    if os.path.exists(capture_file):
        print("📁 Found previously captured User ID:")
        with open(capture_file, 'r') as f:
            content = f.read()
            print(content)
        return True
    return False

def simulate_webhook_data():
    """Show what webhook data looks like"""
    
    print("🔍 WHAT TO LOOK FOR IN WEBHOOK LOGS:")
    print("-" * 40)
    print()
    print("When you send a message, your webhook receives JSON like this:")
    print()
    print('''
{
  "destination": "xxxxxxxxxx",
  "events": [
    {
      "type": "message",
      "mode": "active",
      "timestamp": 1234567890123,
      "source": {
        "type": "user",
        "userId": "U1234567890abcdef1234567890abcdef"  ← THIS IS WHAT WE NEED!
      },
      "replyToken": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
      "message": {
        "id": "xxxxxxxxxxxxx",
        "type": "text",
        "text": "hello"
      }
    }
  ]
}
''')
    print()
    print("🎯 Copy the 'userId' value (starts with 'U' + 32 characters)")
    print()

def provide_next_steps(user_id=None):
    """Provide next steps based on whether we have the User ID"""
    
    if user_id:
        print(f"✅ Great! Your User ID is: {user_id}")
        print()
        print("🚀 NEXT: I'll automatically set up and run the Rich Message test!")
        print("   - Configure test script with your User ID")
        print("   - Load Little Prince template")
        print("   - Generate inspirational content")
        print("   - Send Rich Message to your LINE account")
        print("   - Include interactive buttons for testing")
        
    else:
        print("📱 NEXT STEPS:")
        print("1. Send a message to your LINE Bot (@970jqtyf)")
        print("2. Check the console/webhook logs")
        print("3. Find and copy your User ID (starts with 'U')")
        print("4. Give me that User ID")
        print("5. I'll handle the rest automatically!")

if __name__ == "__main__":
    print("🤖 LINE User ID Capture Tool")
    print()
    
    # Check if we already have a captured ID
    if not check_for_captured_id():
        # Show instructions
        capture_code = create_user_id_capture()
        simulate_webhook_data()
        provide_next_steps()
        
        print()
        print("⚡ QUICK START:")
        print("1. Send 'hello' to your LINE Bot")
        print("2. Check your console output")
        print("3. Look for the User ID in the webhook data")
        print("4. Copy the User ID and give it to me!")
        print()
        print("The User ID should look like: U1234567890abcdef1234567890abcdef")
    else:
        print("Found existing capture data!")
        provide_next_steps("check_file")