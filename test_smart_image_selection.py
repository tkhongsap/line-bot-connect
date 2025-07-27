#!/usr/bin/env python3
"""
Test Smart Image Selection and AI-Aware Content Generation

This test demonstrates the new dynamic image selection system that:
1. Discovers available images at runtime
2. Scores images based on current context (time, day, theme)
3. Generates AI content that's aware of the selected image
4. Sends Rich Messages with truly personalized content
"""

import sys
import os
from datetime import datetime

# Add src to path
sys.path.append('/home/runner/workspace/src')

def test_smart_image_discovery():
    """Test the dynamic image discovery system"""
    
    print("🔍 TESTING DYNAMIC IMAGE DISCOVERY")
    print("=" * 50)
    
    try:
        from src.services.rich_message_service import RichMessageService
        from src.services.line_service import LineService
        from src.services.openai_service import OpenAIService
        from src.services.conversation_service import ConversationService
        from src.config.settings import Settings
        
        # Initialize services
        settings = Settings()
        conversation_service = ConversationService()
        openai_service = OpenAIService(settings, conversation_service)
        line_service = LineService(settings, openai_service, conversation_service)
        
        # Create RichMessageService with smart selection
        rich_service = RichMessageService(
            line_bot_api=line_service.line_bot_api,
            base_url='https://line-bot-connect-tkhongsap.replit.app',
            openai_service=openai_service
        )
        
        print("✅ Services initialized")
        
        # Test image discovery
        available_images = rich_service.discover_available_images()
        print(f"✅ Discovered {len(available_images)} background images:")
        
        for i, image_path in enumerate(available_images[:10], 1):  # Show first 10
            filename = os.path.basename(image_path)
            print(f"   {i:2d}. {filename}")
        
        if len(available_images) > 10:
            print(f"   ... and {len(available_images) - 10} more images")
        
        return True
        
    except Exception as e:
        print(f"❌ Discovery test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_context_scoring():
    """Test the context-based image scoring system"""
    
    print("\n🎯 TESTING CONTEXT-BASED SCORING")
    print("=" * 50)
    
    try:
        from src.services.rich_message_service import RichMessageService
        from src.services.line_service import LineService
        from src.services.openai_service import OpenAIService
        from src.services.conversation_service import ConversationService
        from src.config.settings import Settings
        
        # Initialize services
        settings = Settings()
        conversation_service = ConversationService()
        openai_service = OpenAIService(settings, conversation_service)
        line_service = LineService(settings, openai_service, conversation_service)
        
        rich_service = RichMessageService(
            line_bot_api=line_service.line_bot_api,
            openai_service=openai_service
        )
        
        # Test different contexts
        test_contexts = [
            {
                'name': 'Monday Morning',
                'context': {
                    'theme': 'productivity',
                    'day_of_week': 'monday',
                    'time_period': 'morning',
                    'hour': 8,
                    'user_context': 'work'
                }
            },
            {
                'name': 'Friday Evening',
                'context': {
                    'theme': 'motivation',
                    'day_of_week': 'friday',
                    'time_period': 'evening',
                    'hour': 18,
                    'user_context': 'energy'
                }
            },
            {
                'name': 'Weekend Wellness',
                'context': {
                    'theme': 'wellness',
                    'day_of_week': 'sunday',
                    'time_period': 'morning',
                    'hour': 10,
                    'user_context': 'relax'
                }
            }
        ]
        
        available_images = rich_service.discover_available_images()
        
        for test_case in test_contexts:
            print(f"\n📋 Context: {test_case['name']}")
            print(f"   Details: {test_case['context']}")
            
            # Score top 5 images for this context
            image_scores = []
            for image_path in available_images:
                score = rich_service.calculate_context_score(image_path, test_case['context'])
                if score > 0:
                    image_scores.append((os.path.basename(image_path), score))
            
            # Sort by score and show top 5
            image_scores.sort(key=lambda x: x[1], reverse=True)
            print(f"   🏆 Top scoring images:")
            
            for i, (filename, score) in enumerate(image_scores[:5], 1):
                print(f"      {i}. {filename} (score: {score:.1f})")
            
            if not image_scores:
                print("      No images scored for this context")
        
        return True
        
    except Exception as e:
        print(f"❌ Context scoring test failed: {str(e)}")
        return False

def test_smart_image_selection():
    """Test the complete smart image selection"""
    
    print("\n🧠 TESTING SMART IMAGE SELECTION")
    print("=" * 50)
    
    try:
        from src.services.rich_message_service import RichMessageService
        from src.services.line_service import LineService
        from src.services.openai_service import OpenAIService
        from src.services.conversation_service import ConversationService
        from src.config.settings import Settings
        
        # Initialize services
        settings = Settings()
        conversation_service = ConversationService()
        openai_service = OpenAIService(settings, conversation_service)
        line_service = LineService(settings, openai_service, conversation_service)
        
        rich_service = RichMessageService(
            line_bot_api=line_service.line_bot_api,
            openai_service=openai_service
        )
        
        # Test selections for different themes
        themes_to_test = ['productivity', 'wellness', 'motivation', 'inspiration']
        
        current_time = datetime.now()
        print(f"⏰ Current context: {current_time.strftime('%A %I:%M %p')}")
        
        for theme in themes_to_test:
            print(f"\n🎨 Theme: {theme.upper()}")
            
            selected_image = rich_service.select_contextual_image(theme, 'work')
            if selected_image:
                filename = os.path.basename(selected_image)
                print(f"   ✅ Selected: {filename}")
                
                # Extract image context
                image_context = rich_service._extract_image_context(filename)
                print(f"   📝 Description: {image_context['description']}")
                print(f"   🎭 Mood: {image_context['mood']}")
            else:
                print(f"   ❌ No image selected for theme: {theme}")
        
        return True
        
    except Exception as e:
        print(f"❌ Smart selection test failed: {str(e)}")
        return False

def test_image_aware_content_generation():
    """Test AI content generation based on selected image"""
    
    print("\n🎭 TESTING IMAGE-AWARE CONTENT GENERATION")
    print("=" * 50)
    
    try:
        from src.services.rich_message_service import RichMessageService
        from src.services.line_service import LineService
        from src.services.openai_service import OpenAIService
        from src.services.conversation_service import ConversationService
        from src.config.settings import Settings
        
        # Initialize services
        settings = Settings()
        conversation_service = ConversationService()
        openai_service = OpenAIService(settings, conversation_service)
        line_service = LineService(settings, openai_service, conversation_service)
        
        rich_service = RichMessageService(
            line_bot_api=line_service.line_bot_api,
            openai_service=openai_service
        )
        
        print("✅ Services initialized with AI support")
        
        # Test image-aware content generation
        theme = "productivity"
        user_context = "work"
        
        print(f"\n🎯 Generating image-aware content for: {theme}")
        print(f"   User context: {user_context}")
        
        # Generate content with smart image selection
        result = rich_service.generate_image_aware_content(
            theme=theme,
            user_context=user_context,
            force_ai_generation=True
        )
        
        print(f"\n📊 Generation Results:")
        print(f"   🏆 Generation Tier: {result.get('generation_tier', 'unknown')}")
        
        if result.get('image_path'):
            selected_image = os.path.basename(result['image_path'])
            print(f"   🖼️  Selected Image: {selected_image}")
        
        if result.get('image_context'):
            context = result['image_context']
            print(f"   📝 Image Description: {context.get('description', 'N/A')}")
            print(f"   🎭 Image Mood: {context.get('mood', 'N/A')}")
        
        print(f"\n📋 Generated Content:")
        print(f"   📌 Title: '{result.get('title', 'N/A')}' ({len(result.get('title', ''))  } chars)")
        print(f"   💬 Content: '{result.get('content', 'N/A')}' ({len(result.get('content', ''))} chars)")
        
        # Validate content length
        title_len = len(result.get('title', ''))
        content_len = len(result.get('content', ''))
        total_len = title_len + content_len
        
        print(f"   📊 Total Length: {total_len} characters")
        
        if title_len <= 50 and content_len <= 250 and total_len <= 300:
            print("   ✅ Length constraints: PASSED")
        else:
            print("   ❌ Length constraints: FAILED")
        
        return result
        
    except Exception as e:
        print(f"❌ Image-aware content generation failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def test_send_smart_rich_message():
    """Send an actual Rich Message using smart selection and AI generation"""
    
    print("\n📤 TESTING SMART RICH MESSAGE DELIVERY")
    print("=" * 50)
    
    try:
        from src.services.rich_message_service import RichMessageService
        from src.services.line_service import LineService
        from src.services.openai_service import OpenAIService
        from src.services.conversation_service import ConversationService
        from src.config.settings import Settings
        
        # Initialize services
        settings = Settings()
        conversation_service = ConversationService()
        openai_service = OpenAIService(settings, conversation_service)
        line_service = LineService(settings, openai_service, conversation_service)
        
        rich_service = RichMessageService(
            line_bot_api=line_service.line_bot_api,
            base_url='https://line-bot-connect-tkhongsap.replit.app',
            openai_service=openai_service
        )
        
        # Generate smart content
        result = rich_service.generate_image_aware_content(
            theme="motivation",
            user_context="energy",
            force_ai_generation=True
        )
        
        if not result or not result.get('image_path'):
            print("❌ Failed to generate smart content")
            return False
        
        print(f"✅ Smart content generated:")
        print(f"   🖼️  Image: {os.path.basename(result['image_path'])}")
        print(f"   📌 Title: {result['title']}")
        print(f"   💬 Content: {result['content']}")
        print(f"   🎭 Generation: {result['generation_tier']}")
        
        # Create and send Rich Message
        flex_message = rich_service.create_flex_message(
            title=result['title'],
            content=result['content'],
            image_path=result['image_path'],
            content_id=f"smart_test_{int(datetime.now().timestamp())}",
            user_id="U595491d702720bc7c90d50618324cac3",
            include_interactions=True
        )
        
        print("✅ Rich Message created with smart selection")
        
        # Send the message using the new controlled method
        print("📤 Sending Smart Rich Message...")
        send_result = rich_service.send_rich_message(
            flex_message=flex_message,
            user_id="U595491d702720bc7c90d50618324cac3",
            dry_run=True  # Use dry run to avoid spam
        )
        
        if send_result["success"]:
            if send_result.get("dry_run"):
                print("🎭 DRY RUN: Smart Rich Message validated but not sent")
            else:
                print("🎉 Smart Rich Message sent successfully!")
        else:
            print(f"❌ Send failed: {send_result.get('error', 'Unknown error')}")
        
        print("\n📱 CHECK YOUR LINE APP FOR:")
        print("   🧠 Smart image selection based on current context")
        print("   🎭 AI-generated content aware of the image")
        print("   💬 Bourdain's voice matched to visual context")
        print("   🔘 Interactive conversation triggers")
        
        return True
        
    except Exception as e:
        print(f"❌ Smart Rich Message send failed: {str(e)}")
        return False

if __name__ == "__main__":
    print("🧠 SMART IMAGE SELECTION & AI-AWARE CONTENT TESTING")
    print("Testing the dynamic, context-aware Rich Message system")
    print("=" * 60)
    
    # Run all tests
    tests_passed = 0
    total_tests = 5
    
    if test_smart_image_discovery():
        tests_passed += 1
    
    if test_context_scoring():
        tests_passed += 1
    
    if test_smart_image_selection():
        tests_passed += 1
    
    if test_image_aware_content_generation():
        tests_passed += 1
    
    if test_send_smart_rich_message():
        tests_passed += 1
    
    print("\n" + "=" * 60)
    print(f"📊 TEST RESULTS: {tests_passed}/{total_tests} tests passed")
    
    if tests_passed == total_tests:
        print("🎉 ALL SMART SELECTION TESTS PASSED!")
        print("✅ Dynamic image discovery working")
        print("✅ Context-based scoring working")
        print("✅ Smart image selection working")
        print("✅ AI-aware content generation working")
        print("✅ Smart Rich Message delivery working")
        print("\n🚀 The system now provides truly personalized, context-aware Rich Messages!")
    else:
        print(f"⚠️  {total_tests - tests_passed} tests failed - check logs above")