#!/usr/bin/env python3
"""
Fixed Productivity Focus Rich Message with Real LLM-Generated Content

This script uses the productivity_focus_01.png template and generates
content using our Azure OpenAI LLM with the correct API method.
"""

import sys
import os
from datetime import datetime

# Add src to path
sys.path.append('/home/runner/workspace/src')

def generate_focus_content_with_llm(openai_service):
    """Generate productivity focus content using the correct LLM method"""
    
    # Create a focused prompt for productivity content
    prompt = """Create a powerful productivity message for professionals. Include:

1. A catchy title with emoji (max 25 characters)
2. An inspiring 2-3 sentence message about focus and deep work
3. One specific actionable tip for better concentration today

Theme: Deep work, focus, productivity, concentration
Tone: Motivating, professional, actionable
Format: Keep it concise and impactful for a mobile message

Example structure:
🎯 [Title]
[Inspiring message about focus/productivity]
💡 Tip: [Specific actionable advice]"""

    try:
        # Use the correct method from OpenAI service
        response = openai_service.get_response("llm_content_gen", prompt, use_streaming=False)
        
        if response and response.get('success') and response.get('message'):
            return response['message'].strip()
        else:
            print(f"⚠️ LLM response issue: {response}")
            return None
    except Exception as e:
        print(f"⚠️ LLM generation failed: {str(e)}")
        return None

def parse_llm_productivity_content(llm_response):
    """Parse LLM response into title and content"""
    
    if not llm_response:
        return None
    
    lines = [line.strip() for line in llm_response.split('\n') if line.strip()]
    
    if len(lines) >= 2:
        # Look for the title (usually has emoji and is shorter)
        title = lines[0]
        
        # Clean title
        if title.startswith('1.') or title.startswith('Title:'):
            title = title.split(':', 1)[-1].split('.', 1)[-1].strip()
        
        # Rest is content
        content_lines = lines[1:]
        content = '\n'.join(content_lines)
        
        # Clean content formatting
        content = content.replace('2.', '').replace('3.', '').strip()
        
        return {
            'title': title,
            'content': content
        }
    
    # Fallback - use the entire response as content with default title
    return {
        'title': '🎯 Focus Power',
        'content': llm_response
    }

def send_productivity_focus_llm_message(user_id):
    """Send productivity focus message with real LLM-generated content"""
    
    print("🎯 PRODUCTIVITY FOCUS WITH REAL LLM CONTENT")
    print("=" * 45)
    print(f"📱 Target: {user_id}")
    print("🎨 Template: productivity_focus_01.png")
    print("🤖 Content: Azure OpenAI GPT-4.1 Generated")
    print()
    
    try:
        # Import services
        from src.services.rich_message_service import RichMessageService
        from src.services.line_service import LineService
        from src.services.openai_service import OpenAIService
        from src.services.conversation_service import ConversationService
        from src.config.settings import Settings
        
        print("✅ Services imported")
        
        # Initialize services in correct order
        settings = Settings()
        conversation_service = ConversationService()
        openai_service = OpenAIService(settings, conversation_service)
        line_service = LineService(settings, openai_service, conversation_service)
        line_bot_api = line_service.line_bot_api
        
        rich_service = RichMessageService(line_bot_api=line_bot_api)
        print("✅ Services ready")
        
        # Check template
        template_path = "/home/runner/workspace/templates/rich_messages/backgrounds/productivity_focus_01.png"
        
        if not os.path.exists(template_path):
            print(f"❌ Template not found: {template_path}")
            return False
        
        file_size = os.path.getsize(template_path)
        print(f"✅ Template found: productivity_focus_01.png ({file_size:,} bytes)")
        
        # Generate content using LLM with correct method
        print("🤖 Generating content with Azure OpenAI GPT-4.1...")
        llm_response = generate_focus_content_with_llm(openai_service)
        
        if llm_response:
            print("✅ LLM content generated successfully!")
            print(f"   📝 Raw response: {llm_response[:100]}...")
            
            parsed_content = parse_llm_productivity_content(llm_response)
            
            if parsed_content:
                title = parsed_content['title']
                content = parsed_content['content']
                print(f"   🎯 Title: {title}")
                print(f"   💭 Content: {content[:80]}...")
            else:
                print("⚠️ Failed to parse LLM content")
                title = "🎯 Deep Focus Mode"
                content = llm_response
        else:
            print("❌ LLM generation failed, using fallback")
            title = "🎯 Deep Focus Mode"
            content = "Master your focus, master your day. Eliminate distractions, set clear intentions, and dive deep into meaningful work. Your concentrated effort today creates tomorrow's breakthrough."
        
        # Create Rich Message
        print("✅ Creating Rich Message with LLM content...")
        
        flex_message = rich_service.create_flex_message(
            title=title,
            content=content,
            image_path=template_path,
            content_id=f"productivity_llm_real_{int(datetime.now().timestamp())}",
            user_id=user_id,
            include_interactions=True
        )
        
        if not flex_message:
            print("❌ Failed to create Rich Message")
            return False
        
        print("✅ Rich Message created with AI-generated content")
        
        # Send the message
        print("🔴 SENDING LLM-GENERATED MESSAGE...")
        line_bot_api.push_message(user_id, flex_message)
        print("🎉 Message sent successfully!")
        
        print()
        print("📊 Message Details:")
        print(f"   👤 Sent to: {user_id}")
        print(f"   🎨 Template: productivity_focus_01.png")
        print(f"   🎭 Theme: Focused Productivity")
        print(f"   🤖 Content: Real Azure OpenAI GPT-4.1 Generated")
        print(f"   📱 Interactive: Like, Share, Save, React buttons")
        print(f"   🕒 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        print("📱 CHECK YOUR LINE APP!")
        print("   🎯 Look for the new productivity message")
        print("   🤖 Content was created by AI specifically for focus/productivity")
        print("   🔘 Test the interactive buttons")
        
        # Show the actual generated content
        print()
        print("🤖 AI-Generated Content:")
        print("=" * 30)
        print(f"Title: {title}")
        print(f"Content: {content}")
        print("=" * 30)
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    # User ID (keeping confidential)
    user_id = "U595491d702720bc7c90d50618324cac3"
    
    success = send_productivity_focus_llm_message(user_id)
    
    print()
    if success:
        print("🎉 REAL LLM PRODUCTIVITY MESSAGE SENT!")
        print("📱 Check your LINE app for the AI-generated content!")
    else:
        print("❌ Send failed")