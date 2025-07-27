#!/usr/bin/env python3
"""
Test Multiple Template Rich Messages

This test verifies that Rich Messages work with different background templates.
"""

import sys
import os
from datetime import datetime

# Add src to path
sys.path.append('/home/runner/workspace/src')

def test_multiple_templates():
    """Test Rich Messages with different template backgrounds"""
    
    print("🎨 TESTING MULTIPLE TEMPLATE BACKGROUNDS")
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
            base_url='https://line-bot-connect.replit.app'
        )
        
        print("✅ Services initialized")
        
        # Get available templates
        backgrounds_dir = '/home/runner/workspace/templates/rich_messages/backgrounds'
        png_files = [f for f in os.listdir(backgrounds_dir) if f.endswith('.png')]
        
        # Test with 5 different templates
        test_templates = [
            ("productivity_monday_coffee.png", "☕ Monday Motivation", "Start your week strong with clear priorities and focused energy!"),
            ("motivation_abstract_geometric.png", "🎯 Focus Mode", "Eliminate distractions and tackle your most important task first."),
            ("wellness_nature_spirits.png", "🌿 Mindful Moment", "Take a deep breath and connect with your inner calm."),
            ("inspiration_creative_minimal.png", "✨ Creative Flow", "Let your imagination guide you to innovative solutions."),
            ("motivation_weekend_energy.png", "🚀 Weekend Power", "Use this time to recharge and pursue your passions.")
        ]
        
        successful_tests = 0
        
        for template_name, title, content in test_templates:
            template_path = os.path.join(backgrounds_dir, template_name)
            
            if not os.path.exists(template_path):
                print(f"⚠️  Template not found: {template_name}")
                continue
            
            print(f"\n📸 Testing: {template_name}")
            print(f"   📋 Title: {title}")
            print(f"   💼 Content: {content[:40]}...")
            
            try:
                # Create Rich Message
                flex_message = rich_service.create_flex_message(
                    title=title,
                    content=content,
                    image_path=template_path,
                    content_id=f"multi_test_{int(datetime.now().timestamp())}",
                    user_id="test_user",
                    include_interactions=True
                )
                
                # Check if background image is included
                flex_dict = flex_message.as_json_dict()
                bubble = flex_dict.get('contents', {})
                hero = bubble.get('hero', {})
                
                if hero and hero.get('url'):
                    print(f"   ✅ Background image: {hero['url']}")
                    successful_tests += 1
                else:
                    print(f"   ❌ No background image found")
                
            except Exception as e:
                print(f"   ❌ Failed: {str(e)}")
        
        print(f"\n📊 RESULTS:")
        print(f"✅ Successful tests: {successful_tests}/{len(test_templates)}")
        print(f"📁 Total templates available: {len(png_files)}")
        
        if successful_tests == len([t for t in test_templates if os.path.exists(os.path.join(backgrounds_dir, t[0]))]):
            print("🎉 All template tests PASSED!")
            return True
        else:
            print("⚠️  Some template tests failed")
            return False
        
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        return False

if __name__ == "__main__":
    success = test_multiple_templates()
    exit(0 if success else 1)