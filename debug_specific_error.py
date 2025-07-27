#!/usr/bin/env python3
"""
Debug Specific Error

Find the exact line causing the "'str' object has no attribute 'get'" error
"""

import sys
import os
import traceback
sys.path.append('/home/runner/workspace/src')

def trace_get_calls():
    """Trace all .get() calls to find where the error occurs"""
    
    print("🔍 TRACING .get() CALLS TO FIND THE ERROR")
    print("=" * 50)
    
    try:
        # Initialize services
        from src.services.rich_message_service import RichMessageService
        from src.services.openai_service import OpenAIService
        from src.services.conversation_service import ConversationService
        from src.config.settings import Settings
        from linebot import LineBotApi
        
        settings = Settings()
        line_bot_api = LineBotApi(settings.LINE_CHANNEL_ACCESS_TOKEN)
        conversation_service = ConversationService()
        openai_service = OpenAIService(settings, conversation_service)
        
        rich_message_service = RichMessageService(
            line_bot_api=line_bot_api,
            openai_service=openai_service
        )
        
        # Get interaction handler
        from src.utils.interaction_handler import get_interaction_handler
        interaction_handler = get_interaction_handler(openai_service)
        
        # Create test context
        content_id = f"debug_specific_{int(time.time())}"
        test_context = {
            "title": "Test Content",
            "content": "Testing specific error location",
            "theme": "productivity",
            "image_context": "Professional workspace",
            "visual_mood": "focused"
        }
        
        rich_message_service.store_button_context(content_id, test_context)
        
        # Test the exact same call that's failing
        test_interaction = {
            "action": "conversation_trigger",
            "trigger_type": "elaborate",
            "content_id": content_id
        }
        
        print(f"Testing interaction: {test_interaction}")
        print(f"Content ID: {content_id}")
        print(f"Context stored: {rich_message_service.get_button_context(content_id) is not None}")
        
        # Call the method step by step to isolate the error
        print("\n🎯 Testing each step of conversation trigger...")
        
        # Test 1: Basic parameter extraction
        print("Step 1: Testing parameter extraction...")
        trigger_type = test_interaction.get("trigger_type")
        print(f"   trigger_type: {trigger_type}")
        
        # Test 2: Context retrieval
        print("Step 2: Testing context retrieval...")
        rich_context = rich_message_service.get_button_context(content_id)
        print(f"   rich_context type: {type(rich_context)}")
        print(f"   rich_context: {rich_context}")
        
        # Test 3: Check fallback condition
        print("Step 3: Testing fallback condition...")
        openai_available = interaction_handler.openai_service is not None
        content_generator_available = interaction_handler.content_generator is not None
        print(f"   OpenAI available: {openai_available}")
        print(f"   Content generator available: {content_generator_available}")
        
        if openai_available and content_generator_available:
            print("Step 4: Testing prompt building...")
            try:
                conversation_prompt = interaction_handler._build_conversation_trigger_prompt_with_context(
                    trigger_type, content_id, rich_context
                )
                print(f"   Prompt built successfully: {len(conversation_prompt)} chars")
                
                print("Step 5: Testing OpenAI service call...")
                response = interaction_handler.openai_service.get_response(
                    user_id=f"conversation_trigger_debug_us",
                    user_message=conversation_prompt,
                    use_streaming=False
                )
                
                print(f"   Response type: {type(response)}")
                print(f"   Response: {response}")
                
                # This is where the error likely occurs - test response handling
                print("Step 6: Testing response handling...")
                if response:
                    if isinstance(response, str):
                        print(f"   Response is string: {response[:100]}...")
                        ai_message = response.strip()
                    elif isinstance(response, dict):
                        print(f"   Response is dict with keys: {list(response.keys())}")
                        if response.get('success') and response.get('message'):
                            ai_message = response['message'].strip()
                            print(f"   Extracted message: {ai_message[:100]}...")
                        else:
                            print(f"   Dict response missing success/message")
                    else:
                        print(f"   Unexpected response type: {type(response)}")
                        
            except Exception as e:
                print(f"❌ Error in step-by-step testing: {str(e)}")
                print("\n📍 FULL TRACEBACK:")
                traceback.print_exc()
        else:
            print("   Skipping AI steps - would use fallback")
            
        # Now try the full method to see if we still get the error
        print("\nStep 7: Testing full method...")
        try:
            result = interaction_handler._handle_conversation_trigger(
                user_id="debug_user",
                content_id=content_id,
                interaction_data=test_interaction,
                rich_message_service=rich_message_service
            )
            print(f"✅ Full method result: {result}")
        except Exception as e:
            print(f"❌ Full method error: {str(e)}")
            print("\n📍 FULL TRACEBACK:")
            traceback.print_exc()
                    
        return True
        
    except Exception as e:
        print(f"❌ Setup failed: {str(e)}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    import time
    
    print("🔧 SPECIFIC ERROR DEBUGGING")
    print("Finding exact location of 'str' object has no attribute 'get' error")
    print()
    
    success = trace_get_calls()
    
    print("\n" + "=" * 50)
    if success:
        print("✅ ERROR TRACING COMPLETED")
        print("Check the traceback above to identify the problematic line")
    else:
        print("❌ ERROR TRACING FAILED")