#!/usr/bin/env python3
"""
Check Webhook Logs

Simple script to check if the webhook is receiving and processing
postback events from Rich Message button clicks.
"""

import sys
import os
import time
from datetime import datetime

# Add src to path
sys.path.append('/home/runner/workspace/src')

def test_webhook_reception():
    """Test webhook reception and logging"""
    
    print("🔍 WEBHOOK RECEPTION TEST")
    print("Checking if webhook receives postback events")
    print("=" * 50)
    
    try:
        from src.services.line_service import LineService
        from src.services.openai_service import OpenAIService
        from src.services.conversation_service import ConversationService
        from src.config.settings import Settings
        
        # Initialize services
        settings = Settings()
        conversation_service = ConversationService()
        openai_service = OpenAIService(settings, conversation_service)
        line_service = LineService(settings, openai_service, conversation_service)
        
        print("✅ Services initialized")
        
        # Test postback handling directly
        print("\n🧪 Testing postback data parsing...")
        
        # Sample postback data that should be sent by buttons
        test_postback_data = {
            "action": "conversation_trigger",
            "trigger_type": "elaborate",
            "content_id": "test_content_123",
            "prompt_context": "User wants to hear more depth and perspective on this topic in Bourdain's storytelling style"
        }
        
        import json
        postback_json = json.dumps(test_postback_data)
        print(f"   Sample postback JSON: {postback_json}")
        
        # Test parsing
        try:
            parsed = json.loads(postback_json)
            action = parsed.get('action', '')
            trigger_type = parsed.get('trigger_type', '')
            
            print(f"   ✅ Parsing successful:")
            print(f"      Action: {action}")
            print(f"      Trigger: {trigger_type}")
            
            if action == "conversation_trigger":
                print(f"   ✅ Action recognition working")
            else:
                print(f"   ❌ Action not recognized")
                
        except json.JSONDecodeError as e:
            print(f"   ❌ JSON parsing failed: {e}")
            return False
        
        # Test interaction handler
        print("\n🔧 Testing interaction handler...")
        
        from src.utils.interaction_handler import get_interaction_handler
        
        # Get interaction handler with OpenAI service
        interaction_handler = get_interaction_handler(openai_service)
        print(f"   ✅ Interaction handler created")
        print(f"   OpenAI service available: {interaction_handler.openai_service is not None}")
        print(f"   Content generator available: {interaction_handler.content_generator is not None}")
        
        # Test the actual interaction handling
        print("\n🎭 Testing conversation trigger processing...")
        
        user_id = "test_user_123"
        result = interaction_handler.handle_user_interaction(user_id, test_postback_data)
        
        print(f"   Processing result:")
        print(f"      Success: {result.get('success', False)}")
        print(f"      Response type: {result.get('response_type', 'none')}")
        print(f"      Message length: {len(result.get('message', ''))}")
        print(f"      AI generated: {result.get('ai_generated', False)}")
        
        if result.get('success'):
            print(f"   ✅ Interaction processing working")
            print(f"   📝 Sample response: {result.get('message', '')[:100]}...")
        else:
            print(f"   ❌ Interaction processing failed: {result.get('error')}")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def show_debugging_tips():
    """Show debugging tips for webhook issues"""
    
    print("\n🔧 DEBUGGING TIPS")
    print("=" * 50)
    
    print("📋 Things to check:")
    print("1. **Webhook URL**: Ensure LINE webhook URL is set to your Replit app URL + /webhook")
    print("2. **LINE Console**: Check LINE Developers Console for webhook delivery status")
    print("3. **Replit Logs**: Check Replit console for webhook request logs")
    print("4. **IP Validation**: Webhook might be blocked by IP validation")
    print("5. **Rate Limiting**: Webhook might be rate limited")
    
    print("\n🌐 Expected webhook URL format:")
    print("   https://line-bot-connect-tkhongsap.replit.app/webhook")
    
    print("\n📊 In LINE Developers Console:")
    print("   • Go to your LINE Bot settings")
    print("   • Check 'Webhook URL' is correct")
    print("   • Verify 'Webhook' is enabled")
    print("   • Look for delivery success/failure logs")
    
    print("\n🔍 In Replit Console:")
    print("   • Look for 'Received webhook request' logs")
    print("   • Look for 'Received postback from user' logs")
    print("   • Check for any error messages")
    
    print("\n⚙️ Potential fixes:")
    print("   • Try disabling IP validation in DEBUG mode")
    print("   • Check if webhook signature verification is working")
    print("   • Verify Flask app is running and accessible")

if __name__ == "__main__":
    print("🔍 WEBHOOK DEBUGGING TOOL")
    print("Testing webhook reception and postback processing")
    print()
    
    # Test webhook components
    success = test_webhook_reception()
    
    # Show debugging tips
    show_debugging_tips()
    
    print("\n" + "=" * 50)
    if success:
        print("✅ WEBHOOK COMPONENTS WORKING")
        print()
        print("🔧 The postback processing system is functional")
        print("🕵️ Issue is likely in webhook delivery from LINE to your app")
        print()
        print("📱 NEXT STEPS:")
        print("1. Check LINE Developers Console for webhook logs")
        print("2. Verify webhook URL is correct in LINE settings")
        print("3. Check Replit console for incoming webhook requests")
        print("4. Try clicking buttons again and watch logs")
    else:
        print("❌ WEBHOOK COMPONENTS FAILED")
        print("Fix the issues above before testing button clicks")