#!/usr/bin/env python3
"""
Debug Button Issue

Test script to debug why button clicks are returning static fallback responses
instead of dynamic AI-generated content.
"""

import sys
import os
sys.path.append('/home/runner/workspace/src')

def debug_button_processing():
    """Debug the button processing flow to identify the issue"""
    
    print("🔍 DEBUGGING BUTTON PROCESSING ISSUE")
    print("Investigating why buttons return static fallback responses")
    print("=" * 60)
    
    try:
        # Step 1: Initialize services (same as production)
        print("\n1️⃣ Initializing services...")
        
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
        
        print("   ✅ All services initialized successfully")
        print(f"   OpenAI Service: {type(openai_service).__name__}")
        print(f"   Rich Message Service: {type(rich_message_service).__name__}")
        
        # Step 2: Test interaction handler initialization
        print("\n2️⃣ Testing interaction handler initialization...")
        
        from src.utils.interaction_handler import get_interaction_handler
        
        # Get interaction handler (same as production)
        interaction_handler = get_interaction_handler(openai_service)
        
        print(f"   ✅ Interaction handler created: {type(interaction_handler).__name__}")
        print(f"   OpenAI service passed: {interaction_handler.openai_service is not None}")
        print(f"   Content generator available: {interaction_handler.content_generator is not None}")
        
        if interaction_handler.content_generator is None:
            print("   ❌ ISSUE FOUND: content_generator is None!")
            print("   This explains why fallback responses are being used")
        else:
            print(f"   ✅ Content generator: {type(interaction_handler.content_generator).__name__}")
        
        # Step 3: Test content generator import directly
        print("\n3️⃣ Testing content generator import directly...")
        
        try:
            from src.utils.rich_message_content_generator import RichMessageContentGenerator
            test_generator = RichMessageContentGenerator(openai_service)
            print("   ✅ Direct import and initialization successful")
            print(f"   Generator type: {type(test_generator).__name__}")
        except Exception as e:
            print(f"   ❌ Direct import/initialization failed: {str(e)}")
            import traceback
            traceback.print_exc()
        
        # Step 4: Create test content and button context
        print("\n4️⃣ Creating test content and context...")
        
        content_id = f"debug_test_{int(time.time())}"
        
        # Store test context (same as production)
        test_context = {
            "title": "Test Content for Debugging",
            "content": "Testing dynamic button responses with AI generation",
            "theme": "productivity",
            "image_context": "Professional workspace with coffee and notebook",
            "visual_mood": "focused"
        }
        
        rich_message_service.store_button_context(content_id, test_context)
        
        # Verify context storage
        stored_context = rich_message_service.get_button_context(content_id)
        if stored_context:
            print("   ✅ Button context stored and retrieved successfully")
            print(f"   Context keys: {list(stored_context.keys())}")
        else:
            print("   ❌ Button context storage failed")
        
        # Step 5: Test button interaction directly
        print("\n5️⃣ Testing button interaction processing...")
        
        # Simulate "Tell me more" button click (exact same as production)
        test_interaction = {
            "action": "conversation_trigger",
            "trigger_type": "elaborate",
            "content_id": content_id
        }
        
        print(f"   Testing interaction: {test_interaction}")
        
        # Process the interaction (same as production)
        result = interaction_handler.handle_user_interaction(
            user_id="debug_test_user",
            interaction_data=test_interaction,
            rich_message_service=rich_message_service
        )
        
        print(f"\n📊 INTERACTION RESULT:")
        print(f"   Success: {result.get('success')}")
        print(f"   Response type: {result.get('response_type')}")
        print(f"   AI generated: {result.get('ai_generated', 'N/A')}")
        
        if result.get('success'):
            message = result.get('message', '')
            print(f"   Message length: {len(message)} chars")
            print(f"   Message preview: {message[:100]}...")
            
            # Check if it's a fallback response
            fallback_patterns = [
                "There's always more to the story",
                "Cut through the bullshit", 
                "I've been there. Different kitchen",
                "Simple recipe: Stay curious"
            ]
            
            is_fallback = any(pattern in message for pattern in fallback_patterns)
            if is_fallback:
                print("   ❌ ISSUE CONFIRMED: Using static fallback response!")
                print("   Expected: Dynamic AI-generated response")
                print("   Actual: Static fallback pattern detected")
            else:
                print("   ✅ SUCCESS: Dynamic AI response generated!")
        else:
            print(f"   ❌ Interaction failed: {result.get('error')}")
        
        # Step 6: Debug the condition that triggers fallbacks
        print("\n6️⃣ Debugging fallback condition...")
        
        print(f"   interaction_handler.openai_service is None: {interaction_handler.openai_service is None}")
        print(f"   interaction_handler.content_generator is None: {interaction_handler.content_generator is None}")
        
        fallback_condition = not interaction_handler.openai_service or not interaction_handler.content_generator
        print(f"   Fallback condition evaluates to: {fallback_condition}")
        
        if fallback_condition:
            print("   ❌ ISSUE IDENTIFIED: Fallback condition is True")
            if not interaction_handler.openai_service:
                print("      - OpenAI service is missing")
            if not interaction_handler.content_generator:
                print("      - Content generator is missing")
        else:
            print("   ✅ Fallback condition is False - should use AI generation")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Debug script failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    import time
    
    print("🔧 BUTTON ISSUE DEBUGGING SCRIPT")
    print("Identifying why dynamic responses aren't working")
    print()
    
    success = debug_button_processing()
    
    print("\n" + "=" * 60)
    if success:
        print("✅ DEBUG COMPLETED")
        print()
        print("Check the output above to identify the specific issue")
        print("preventing dynamic AI responses from being generated.")
    else:
        print("❌ DEBUG FAILED")
        print("Unable to complete debugging due to errors.")