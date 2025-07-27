#!/usr/bin/env python3
"""
Rich Message Test Tool - Send Beautiful Messages to Yourself First

This tool helps you test rich message automation safely by sending to your
LINE account only (no broadcast to all users).

Features:
- Test with beautiful templates (Little Prince, Motivation, Nature, etc.)
- Interactive buttons (Like, Share, Save, React)
- Safe testing mode (no actual sending)
- Easy template selection

Usage:
1. Get your LINE User ID by sending any message to your bot
2. Set YOUR_USER_ID below
3. Run: python send_test_rich_message.py
4. Choose a template and test!
"""

import sys
import os
import random
from datetime import datetime
from pathlib import Path

# Add src to path for imports
sys.path.append('/home/runner/workspace/src')

# ⚠️ IMPORTANT: Set your LINE User ID here
# Get this by sending any message to your LINE bot and checking the logs
YOUR_USER_ID = "YOUR_LINE_USER_ID_HERE"  # Replace with your actual User ID

# Available templates with their themes (updated with new naming convention)
AVAILABLE_TEMPLATES = {
    "1": {
        "name": "🌟 The Little Prince",
        "file": "inspiration_little_prince.png",
        "theme": "inspiration",
        "quotes": [
            "What is essential is invisible to the eye. It is only with the heart that one can see rightly.",
            "All grown-ups were once children... but only few of them remember it.",
            "You become responsible, forever, for what you have tamed.",
            "The most beautiful things in the world cannot be seen or touched, they are felt with the heart."
        ]
    },
    "2": {
        "name": "🦁 Lion Duality",
        "file": "motivation_lion_duality.png",
        "theme": "motivation",
        "quotes": [
            "Be brave. Take risks. Nothing can substitute experience.",
            "A lion doesn't concern itself with the opinion of sheep.",
            "Courage isn't the absence of fear, it's feeling the fear and doing it anyway.",
            "The brave may not live forever, but the cautious do not live at all."
        ]
    },
    "3": {
        "name": "🏃 Running Energy",
        "file": "motivation_running_figure.png",
        "theme": "motivation",
        "quotes": [
            "Every mile begins with a single step.",
            "Your body can do it. It's your mind you have to convince.",
            "Run when you have to, walk if you can, crawl if you must; just never give up.",
            "The miracle isn't that I finished. The miracle is that I had the courage to start."
        ]
    },
    "4": {
        "name": "🌸 Nature Spirits",
        "file": "wellness_nature_spirits.png",
        "theme": "wellness",
        "quotes": [
            "In nature, nothing is perfect and everything is perfect.",
            "Look deep into nature, and then you will understand everything better.",
            "Nature does not hurry, yet everything is accomplished.",
            "The earth has music for those who listen."
        ]
    },
    "5": {
        "name": "🎨 Creative Inspiration",
        "file": "inspiration_creative_minimal.png",
        "theme": "inspiration",
        "quotes": [
            "Creativity takes courage.",
            "Every artist was first an amateur.",
            "The secret to creativity is knowing how to hide your sources.",
            "Art enables us to find ourselves and lose ourselves at the same time."
        ]
    },
    "6": {
        "name": "🎮 GameBoy Aquarium",
        "file": "inspiration_gameboy_aquarium.png",
        "theme": "inspiration",
        "quotes": [
            "Every morning brings new potential, but only if you make the most of it.",
            "Today is the first day of the rest of your life.",
            "Innovation happens when imagination meets possibility.",
            "The future belongs to those who believe in the beauty of their dreams."
        ]
    },
    "7": {
        "name": "☕ Monday Coffee",
        "file": "productivity_monday_coffee.png",
        "theme": "productivity",
        "quotes": [
            "Monday is a fresh start. Make it amazing!",
            "Coffee: because adulting is hard.",
            "Start where you are. Use what you have. Do what you can.",
            "The way to get started is to quit talking and begin doing."
        ]
    },
    "8": {
        "name": "🐱 Wellness Cats",
        "file": "wellness_cats_storybook.png",
        "theme": "wellness",
        "quotes": [
            "Sometimes the smallest things take up the most room in your heart.",
            "Happiness is a warm cat.",
            "Time spent with cats is never wasted.",
            "A cat has absolute emotional honesty: human beings, for one reason or another, may hide their feelings, but a cat does not."
        ]
    }
}

def show_available_templates():
    """Display all available templates"""
    print("🎨 AVAILABLE RICH MESSAGE TEMPLATES:")
    print("=" * 50)
    print()
    
    for key, template in AVAILABLE_TEMPLATES.items():
        print(f"{key}. {template['name']}")
        print(f"   🎯 Theme: {template['theme'].title()}")
        print(f"   📝 Sample: {template['quotes'][0][:60]}...")
        print()

def test_rich_message(template_choice, send_mode=False):
    """
    Test Rich Message with selected template
    
    Args:
        template_choice: Template number (1-6)
        send_mode: If True, actually sends the message
    """
    
    # Validate User ID
    if YOUR_USER_ID == "YOUR_LINE_USER_ID_HERE":
        print("❌ ERROR: Please set YOUR_USER_ID in this script first!")
        print()
        print("💡 To get your LINE User ID:")
        print("   1. Send any message to your LINE Bot")
        print("   2. Check the webhook logs in your Replit console")
        print("   3. Look for the 'user_id' field (starts with 'U')")
        print("   4. Replace YOUR_LINE_USER_ID_HERE with your actual ID")
        return False
    
    # Validate template choice
    if template_choice not in AVAILABLE_TEMPLATES:
        print(f"❌ Invalid template choice: {template_choice}")
        print("Please choose a number from 1-8")
        return False
    
    template = AVAILABLE_TEMPLATES[template_choice]
    
    print(f"🎨 TESTING: {template['name']}")
    print("=" * 50)
    print()
    print(f"🎯 Target User: {YOUR_USER_ID}")
    print(f"📨 Send Mode: {'LIVE (will send!)' if send_mode else 'MOCK (safe testing)'}")
    print(f"🎨 Template: {template['file']}")
    print()
    
    try:
        # Import required services
        print("📦 Loading Rich Message services...")
        from src.services.rich_message_service import RichMessageService
        from src.services.line_service import LineService
        from src.services.openai_service import OpenAIService
        from src.services.conversation_service import ConversationService
        from src.config.settings import Settings
        from unittest.mock import Mock
        print("✅ Services loaded successfully")
        
        # Initialize services
        print()
        print("⚙️ Initializing services...")
        settings = Settings()
        
        if send_mode:
            # Real services for actual sending
            print("🔴 Initializing REAL services (will send message!)")
            conversation_service = ConversationService()
            openai_service = OpenAIService(settings, conversation_service)
            line_service = LineService(settings, openai_service, conversation_service)
            line_bot_api = line_service.line_bot_api
        else:
            # Mock services for safe testing
            print("🟡 Initializing MOCK services (safe mode)")
            line_bot_api = Mock()
            line_bot_api.push_message = Mock()
        
        rich_service = RichMessageService(line_bot_api=line_bot_api)
        print("✅ Services initialized")
        
        # Check template file
        print()
        print("🎨 Checking template file...")
        template_path = f"/home/runner/workspace/templates/rich_messages/backgrounds/{template['file']}"
        
        if os.path.exists(template_path):
            print(f"✅ Template found: {template['file']}")
            file_size = os.path.getsize(template_path)
            print(f"   📏 Size: {file_size:,} bytes")
        else:
            print(f"❌ Template not found: {template_path}")
            return False
        
        # Create content with random quote
        print()
        print("✍️ Creating rich content...")
        selected_quote = random.choice(template['quotes'])
        
        content_data = {
            "title": f"{template['name']} - Daily Inspiration",
            "content": f'"{selected_quote}"\n\n✨ Let this message inspire your day! Every moment is an opportunity to grow and shine.',
            "template_path": template_path,
            "theme": template['theme']
        }
        
        print("✅ Content created:")
        print(f"   📝 Title: {content_data['title']}")
        print(f"   💭 Quote: {selected_quote[:60]}...")
        
        # Create Rich Message with interactive features
        print()
        print("🎨 Creating Rich Message with interactive buttons...")
        
        flex_message = rich_service.create_flex_message(
            title=content_data["title"],
            content=content_data["content"],
            image_path=content_data["template_path"],
            content_id=f"test_{template_choice}_{int(datetime.now().timestamp())}",
            user_id=YOUR_USER_ID,
            include_interactions=True
        )
        
        if flex_message:
            print("✅ Rich Message created successfully!")
            print(f"   🎭 Alt Text: {flex_message.alt_text}")
            print("   🔘 Interactive: Like, Share, Save, React buttons")
            print(f"   🎨 Theme: {template['theme'].title()}")
        else:
            print("❌ Failed to create Rich Message")
            return False
        
        # Send the message
        print()
        print("📤 Sending Rich Message...")
        
        try:
            if send_mode:
                print("🔴 SENDING LIVE MESSAGE...")
                line_bot_api.push_message(YOUR_USER_ID, flex_message)
                print("✅ Rich Message sent successfully!")
                print()
                print("📱 CHECK YOUR LINE APP!")
                print(f"   🎨 Look for: {template['name']}")
                print("   🔘 Try the interactive buttons:")
                print("      💝 Like - Track engagement")
                print("      📤 Share - Test sharing")
                print("      💾 Save - Test saving")
                print("      😊 React - Test reactions")
                
            else:
                print("🟡 MOCK SEND (safe mode)")
                line_bot_api.push_message(YOUR_USER_ID, flex_message)
                print("✅ Mock send successful!")
                print("   (No actual message sent)")
            
            # Show send details
            print()
            print("📊 Send Details:")
            print(f"   👤 Recipient: {YOUR_USER_ID}")
            print(f"   🕒 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"   🎨 Template: {template['name']}")
            print(f"   📨 Mode: {'LIVE' if send_mode else 'MOCK'}")
            
            return True
            
        except Exception as e:
            print(f"❌ Send failed: {str(e)}")
            print()
            print("💡 Possible issues:")
            print("   - LINE Bot API configuration")
            print("   - Invalid User ID")
            print("   - Network connectivity")
            return False
        
    except ImportError as e:
        print(f"❌ Import error: {str(e)}")
        print("💡 Make sure you're in the project root directory")
        return False
        
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        return False

def main():
    """Main interactive menu"""
    
    print("🤖 RICH MESSAGE TEST TOOL")
    print("=" * 30)
    print()
    
    # Check User ID
    if YOUR_USER_ID == "YOUR_LINE_USER_ID_HERE":
        print("⚠️  Please set your LINE User ID first!")
        print()
        print("💡 Steps to get your User ID:")
        print("1. Send any message to your LINE Bot")
        print("2. Check the Replit console logs")
        print("3. Find the 'user_id' field (starts with 'U')")
        print("4. Edit this script and replace YOUR_LINE_USER_ID_HERE")
        print()
        print("User ID format: U + 32 characters")
        print("Example: Udeadbeefdeadbeefdeadbeefdeadbeef")
        return
    
    while True:
        print()
        show_available_templates()
        
        print("🎮 TESTING OPTIONS:")
        print("=" * 20)
        print("• Choose template number (1-8)")
        print("• Add '--send' to actually send (e.g., '1 --send')")
        print("• Type 'quit' to exit")
        print()
        
        try:
            user_input = input("👉 Your choice: ").strip().lower()
            
            if user_input == 'quit':
                print("👋 Goodbye!")
                break
            
            # Parse input
            parts = user_input.split()
            if not parts:
                continue
                
            template_choice = parts[0]
            send_mode = '--send' in parts
            
            if template_choice not in AVAILABLE_TEMPLATES:
                print(f"❌ Invalid choice: {template_choice}")
                print("Please choose a number from 1-8")
                continue
            
            # Confirm live sending
            if send_mode:
                print()
                print("⚠️  LIVE SEND MODE - Message will be sent to your LINE account!")
                confirm = input("Continue? (y/N): ").strip().lower()
                if confirm not in ['y', 'yes']:
                    print("❌ Cancelled")
                    continue
            
            # Run the test
            print()
            success = test_rich_message(template_choice, send_mode)
            
            print()
            print("=" * 50)
            if success:
                print("🎉 TEST COMPLETE!")
                if send_mode:
                    print("📱 Check your LINE app for the message!")
                else:
                    print("🔧 Add --send to actually send the message")
            else:
                print("❌ Test failed - check the errors above")
            print("=" * 50)
            
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    main()