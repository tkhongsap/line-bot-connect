#!/usr/bin/env python3
"""
Fix Webhook Delivery Issues

Diagnose and fix common webhook delivery problems that prevent
button clicks from reaching the Flask application.
"""

import sys
import os
import requests
from datetime import datetime

# Add src to path
sys.path.append('/home/runner/workspace/src')

def check_webhook_accessibility():
    """Check if the webhook URL is accessible from the internet"""
    
    print("🌐 CHECKING WEBHOOK ACCESSIBILITY")
    print("=" * 50)
    
    webhook_url = "https://line-bot-connect-tkhongsap.replit.app/webhook"
    
    try:
        print(f"🔗 Testing GET request to: {webhook_url}")
        
        # Test GET request (should return webhook verification response)
        response = requests.get(webhook_url, timeout=10)
        
        print(f"   Status Code: {response.status_code}")
        print(f"   Response: {response.text[:100]}...")
        
        if response.status_code == 200:
            print("   ✅ Webhook endpoint is accessible")
            return True
        else:
            print("   ❌ Webhook endpoint returned error")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"   ❌ Failed to reach webhook: {str(e)}")
        return False

def check_line_webhook_config():
    """Provide instructions for checking LINE webhook configuration"""
    
    print("\n⚙️ LINE WEBHOOK CONFIGURATION CHECK")
    print("=" * 50)
    
    print("📋 Please verify these settings in LINE Developers Console:")
    print()
    print("1. **Go to LINE Developers Console:**")
    print("   https://developers.line.biz/console/")
    print()
    print("2. **Select your bot and go to 'Messaging API' tab**")
    print()
    print("3. **Check Webhook Settings:**")
    print("   • Webhook URL: https://line-bot-connect-tkhongsap.replit.app/webhook")
    print("   • Webhook: Use webhook = ✅ ENABLED")
    print("   • Redelivery: ✅ ENABLED (optional)")
    print()
    print("4. **Verify Bot Settings:**")
    print("   • Response message: ❌ DISABLED")
    print("   • Greeting message: ❌ DISABLED")
    print("   • Auto-reply message: ❌ DISABLED")
    print("   • Webhook: ✅ ENABLED")
    print()
    print("5. **Test Webhook Connection:**")
    print("   • Click 'Verify' button next to webhook URL")
    print("   • Should show 'Success' if connection works")

def show_common_webhook_issues():
    """Show common webhook delivery issues and solutions"""
    
    print("\n🔧 COMMON WEBHOOK ISSUES & FIXES")
    print("=" * 50)
    
    print("❌ **Issue 1: Webhook URL incorrect**")
    print("   Fix: Ensure exact URL: https://line-bot-connect-tkhongsap.replit.app/webhook")
    print("   Note: Must be HTTPS, not HTTP")
    print()
    
    print("❌ **Issue 2: Replit app sleeping**")
    print("   Fix: Keep app awake by:")
    print("   • Using UptimeRobot or similar ping service")
    print("   • Making regular requests to keep app active")
    print("   • Upgrading to Replit paid plan")
    print()
    
    print("❌ **Issue 3: Webhook disabled in LINE**")
    print("   Fix: Enable webhook in LINE Developers Console")
    print("   Location: Messaging API > Webhook settings")
    print()
    
    print("❌ **Issue 4: Response messages enabled**")
    print("   Fix: Disable auto-reply features in LINE Console")
    print("   These can interfere with webhook delivery")
    print()
    
    print("❌ **Issue 5: SSL/TLS certificate issues**")
    print("   Fix: Replit should handle this automatically")
    print("   If issues persist, contact Replit support")

def test_webhook_manually():
    """Test webhook with a manual POST request"""
    
    print("\n🧪 MANUAL WEBHOOK TEST")
    print("=" * 50)
    
    webhook_url = "https://line-bot-connect-tkhongsap.replit.app/webhook"
    
    # Sample LINE webhook payload for postback
    test_payload = {
        "destination": "U123456789",
        "events": [
            {
                "type": "postback",
                "mode": "active",
                "timestamp": int(datetime.now().timestamp() * 1000),
                "source": {
                    "type": "user",
                    "userId": "U595491d702720bc7c90d50618324cac3"
                },
                "replyToken": "test_reply_token_123",
                "postback": {
                    "data": '{"action": "conversation_trigger", "trigger_type": "elaborate", "content_id": "test_123", "prompt_context": "Test postback"}'
                }
            }
        ]
    }
    
    print("📤 Sending test postback to webhook...")
    print("   This simulates a button click from LINE")
    
    try:
        # Note: This will fail signature verification, but should reach our code
        response = requests.post(
            webhook_url,
            json=test_payload,
            headers={
                'Content-Type': 'application/json',
                'X-Line-Signature': 'test_signature'
            },
            timeout=10
        )
        
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.text}")
        
        if response.status_code == 400:
            print("   ✅ Webhook received request (signature verification failed as expected)")
            print("   This means the webhook endpoint is working")
        elif response.status_code == 200:
            print("   ✅ Webhook processed request successfully")
        else:
            print("   ❓ Unexpected response - check server logs")
            
    except Exception as e:
        print(f"   ❌ Failed to send test request: {str(e)}")

def provide_debugging_steps():
    """Provide step-by-step debugging instructions"""
    
    print("\n🕵️ STEP-BY-STEP DEBUGGING")
    print("=" * 50)
    
    print("📱 **Step 1: Test button click while watching logs**")
    print("   1. Open Replit console/shell")
    print("   2. Click a button in LINE app")
    print("   3. Look for these log messages:")
    print("      • 'Received webhook request'")
    print("      • 'Received postback from user'")
    print("      • 'Processing conversation trigger'")
    print()
    
    print("🔍 **Step 2: If no webhook logs appear**")
    print("   → Problem: LINE not sending requests to your app")
    print("   → Check LINE webhook configuration")
    print("   → Verify app is running and accessible")
    print()
    
    print("📨 **Step 3: If webhook logs appear but no postback logs**")
    print("   → Problem: Request format or parsing issue")
    print("   → Check request body in logs")
    print("   → Verify signature verification")
    print()
    
    print("🎭 **Step 4: If postback logs appear but no response**")
    print("   → Problem: Response generation or sending")
    print("   → Check interaction handler logs")
    print("   → Verify OpenAI service integration")

if __name__ == "__main__":
    print("🔧 WEBHOOK DELIVERY DIAGNOSTIC TOOL")
    print("Diagnosing why button clicks aren't reaching the webhook")
    print()
    
    # Test webhook accessibility
    webhook_accessible = check_webhook_accessibility()
    
    # Show configuration check
    check_line_webhook_config()
    
    # Show common issues
    show_common_webhook_issues()
    
    # Test webhook manually
    if webhook_accessible:
        test_webhook_manually()
    
    # Provide debugging steps
    provide_debugging_steps()
    
    print("\n" + "=" * 50)
    print("🎯 SUMMARY")
    print()
    if webhook_accessible:
        print("✅ Your webhook endpoint is accessible")
        print("🔍 Issue is likely in LINE webhook configuration")
        print()
        print("📋 IMMEDIATE ACTION ITEMS:")
        print("1. Check LINE Developers Console webhook settings")
        print("2. Verify webhook URL is exactly correct")
        print("3. Ensure webhook is enabled in LINE")
        print("4. Click button while watching Replit console logs")
    else:
        print("❌ Your webhook endpoint is not accessible")
        print("🚨 Fix app accessibility first before testing buttons")
        print()
        print("📋 IMMEDIATE ACTION ITEMS:")
        print("1. Ensure Replit app is running")
        print("2. Check app URL is correct")
        print("3. Verify no firewall/proxy issues")
    
    print("\n💡 TIP: Watch Replit console logs when clicking buttons")
    print("   This will show exactly what's happening with webhook delivery")