#!/usr/bin/env python3
"""
LineOA Rich Message Testing

Test sending rich messages through your LINE Official Account.
Supports both individual user testing and broadcast preparation.
"""

import sys
import os
from datetime import datetime

# Add src to path
sys.path.append('/home/runner/workspace/src')

def generate_lineoa_content_with_llm(openai_service, template_theme="productivity"):
    """Generate content tailored for LineOA messaging"""
    
    prompts = {
        "productivity": """Create a professional productivity message for a LINE Official Account. Include:

1. A compelling title with emoji (max 30 characters)
2. Main message about workplace efficiency and focus (2-3 sentences)
3. One actionable tip for immediate implementation
4. Professional closing that builds trust

Theme: Professional productivity, workplace efficiency
Tone: Expert, helpful, trustworthy
Audience: Working professionals following your LineOA
Format: Concise, actionable, business-appropriate""",

        "inspiration": """Create an inspiring message for a LINE Official Account. Include:

1. An uplifting title with emoji (max 30 characters)  
2. Motivational message about personal growth (2-3 sentences)
3. One practical action step
4. Encouraging closing that builds community

Theme: Personal inspiration, growth mindset
Tone: Uplifting, supportive, motivating
Audience: Individuals seeking motivation and growth
Format: Inspiring, actionable, community-building""",

        "wellness": """Create a wellness-focused message for a LINE Official Account. Include:

1. A calming title with emoji (max 30 characters)
2. Message about mental health and well-being (2-3 sentences) 
3. One simple wellness practice
4. Caring closing that shows support

Theme: Mental wellness, self-care, balance
Tone: Caring, gentle, supportive
Audience: People focused on health and wellness
Format: Calming, practical, supportive"""
    }
    
    prompt = prompts.get(template_theme, prompts["productivity"])
    
    try:
        response = openai_service.get_response("lineoa_content_gen", prompt, use_streaming=False)
        
        if response and response.get('success') and response.get('message'):
            return response['message'].strip()
        else:
            print(f"⚠️ LLM response issue: {response}")
            return None
    except Exception as e:
        print(f"⚠️ LLM generation failed: {str(e)}")
        return None

def parse_lineoa_content(llm_response):
    """Parse LLM response for LineOA messaging"""
    
    if not llm_response:
        return None
    
    lines = [line.strip() for line in llm_response.split('\n') if line.strip()]
    
    if len(lines) >= 2:
        title = lines[0]
        
        # Clean title formatting
        if title.startswith('1.') or title.startswith('Title:'):
            title = title.split(':', 1)[-1].split('.', 1)[-1].strip()
        
        # Combine remaining lines as content
        content = ' '.join(lines[1:])
        content = content.replace('2.', '').replace('3.', '').replace('4.', '').strip()
        
        return {
            'title': title,
            'content': content
        }
    
    return {
        'title': '🔔 Official Update',
        'content': llm_response
    }

def test_lineoa_rich_message(user_id, template_name="productivity_focus_01.png", template_theme="productivity"):
    """Test rich message for LineOA"""
    
    print("🏢 LINEOA RICH MESSAGE TEST")
    print("=" * 35)
    print(f"📱 Test Target: {user_id}")
    print(f"🎨 Template: {template_name}")
    print(f"🎭 Theme: {template_theme}")
    print("🔔 Mode: LineOA Official Account Message")
    print()
    
    try:
        # Import services
        from src.services.rich_message_service import RichMessageService
        from src.services.line_service import LineService
        from src.services.openai_service import OpenAIService
        from src.services.conversation_service import ConversationService
        from src.config.settings import Settings
        
        print("✅ Services imported")
        
        # Initialize services
        settings = Settings()
        conversation_service = ConversationService()
        openai_service = OpenAIService(settings, conversation_service)
        line_service = LineService(settings, openai_service, conversation_service)
        line_bot_api = line_service.line_bot_api
        
        rich_service = RichMessageService(line_bot_api=line_bot_api)
        print("✅ LineOA services ready")
        
        # Check template - fix path
        if template_name == "productivity_focus_01.png":
            template_path = "/home/runner/workspace/templates/rich_messages/backgrounds/productivity_focus_01.png"
        else:
            template_path = f"/home/runner/workspace/templates/rich_messages/backgrounds/{template_name}"
        
        if not os.path.exists(template_path):
            print(f"❌ Template not found: {template_path}")
            return False
        
        file_size = os.path.getsize(template_path)
        print(f"✅ Template found: {template_name} ({file_size:,} bytes)")
        
        # Generate LineOA-appropriate content
        print(f"🤖 Generating {template_theme} content for LineOA...")
        llm_response = generate_lineoa_content_with_llm(openai_service, template_theme)
        
        if llm_response:
            print("✅ LineOA content generated")
            parsed_content = parse_lineoa_content(llm_response)
            
            if parsed_content:
                title = parsed_content['title']
                content = parsed_content['content']
                print(f"   📋 Title: {title}")
                print(f"   💼 Content: {content[:80]}...")
            else:
                title = "🔔 Official Update"
                content = llm_response
        else:
            print("⚠️ Using fallback content")
            title = "🔔 Professional Focus"
            content = "Transform your workday with focused productivity. Eliminate distractions, prioritize your most important tasks, and achieve meaningful progress. Your professional growth starts with intentional focus."
        
        # Create Rich Message for LineOA
        print("✅ Creating LineOA Rich Message...")
        
        flex_message = rich_service.create_flex_message(
            title=title,
            content=content,
            image_path=template_path,
            content_id=f"lineoa_test_{int(datetime.now().timestamp())}",
            user_id=user_id,
            include_interactions=True
        )
        
        if not flex_message:
            print("❌ Failed to create Rich Message")
            return False
        
        print("✅ LineOA Rich Message created")
        
        # Send test message
        print("🔴 SENDING LINEOA TEST MESSAGE...")
        line_bot_api.push_message(user_id, flex_message)
        print("🎉 LineOA message sent successfully!")
        
        print()
        print("📊 LineOA Message Details:")
        print(f"   👤 Test sent to: {user_id}")
        print(f"   🎨 Template: {template_name}")
        print(f"   🎭 Theme: {template_theme}")
        print(f"   🏢 Format: LINE Official Account Message")
        print(f"   🤖 Content: AI-generated for professional use")
        print(f"   📱 Interactive: Like, Share, Save, React buttons")
        print(f"   🕒 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        print("📱 CHECK YOUR LINE APP!")
        print("   🏢 This message was sent as an official account message")
        print("   💼 Professional content suitable for LineOA broadcasting")
        print("   🔘 Interactive buttons work the same as personal messages")
        print("   📊 Ready for follower engagement tracking")
        
        # Show generated content
        print()
        print("🤖 LineOA Content Generated:")
        print("=" * 35)
        print(f"Title: {title}")
        print(f"Content: {content}")
        print("=" * 35)
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main function to run LineOA tests"""
    
    print("🏢 LINE OFFICIAL ACCOUNT RICH MESSAGE TESTING")
    print("=" * 50)
    print()
    
    # Test user ID (using your personal account for testing)
    user_id = "U595491d702720bc7c90d50618324cac3"
    
    # Test different templates and themes
    test_scenarios = [
        {
            "template": "productivity_focus_01.png",
            "theme": "productivity",
            "description": "Professional productivity message"
        },
        {
            "template": "inspiration_sticker_01.png", 
            "theme": "inspiration",
            "description": "Motivational inspiration message"
        }
    ]
    
    print("Available Test Scenarios:")
    for i, scenario in enumerate(test_scenarios, 1):
        print(f"   {i}. {scenario['description']} ({scenario['template']})")
    print()
    
    # For now, test the first scenario (productivity)
    scenario = test_scenarios[0]
    print(f"🎯 Running Test: {scenario['description']}")
    print()
    
    success = test_lineoa_rich_message(
        user_id=user_id,
        template_name=scenario['template'],
        template_theme=scenario['theme']
    )
    
    print()
    if success:
        print("🎉 LINEOA RICH MESSAGE TEST SUCCESSFUL!")
        print("🏢 Your LineOA is ready to send rich messages!")
        print()
        print("📋 Next Steps for LineOA Broadcasting:")
        print("   1. ✅ Individual user testing completed")
        print("   2. 🔄 Test with different templates/themes")
        print("   3. 📢 Ready for follower broadcasting")
        print("   4. 📊 Enable engagement analytics")
    else:
        print("❌ LineOA test failed")

if __name__ == "__main__":
    main()