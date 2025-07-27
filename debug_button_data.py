#!/usr/bin/env python3
"""
Debug Button Data Size

Check if the enhanced button data is too large for LINE's postback limits.
LINE has a 300 character limit for postback data.
"""

import sys
import os
import json

# Add src to path
sys.path.append('/home/runner/workspace/src')

def test_button_data_size():
    """Test the size of enhanced button data"""
    
    print("🔍 BUTTON DATA SIZE ANALYSIS")
    print("=" * 50)
    
    try:
        from src.utils.interaction_handler import InteractionHandler
        
        # Create interaction handler
        interaction_handler = InteractionHandler()
        
        # Create sample rich context
        sample_context = {
            'title': '🔥 Earned Wisdom',
            'content': 'Real motivation comes from people with scars, not people with perfect Instagram feeds. Trust the struggle.',
            'theme': 'motivation',
            'image_context': {
                'description': 'Monday morning coffee setup with warm, energizing atmosphere',
                'mood': 'energetic and focused',
                'filename': 'motivation_weekend_energy.png'
            }
        }
        
        print("📋 Sample Rich Message Context:")
        print(f"   Title: {sample_context['title']}")
        print(f"   Content: {sample_context['content'][:50]}...")
        print(f"   Theme: {sample_context['theme']}")
        print(f"   Image: {sample_context['image_context']['filename']}")
        
        # Create buttons with rich context
        buttons = interaction_handler.create_interactive_buttons(
            content_id="test_content_123",
            rich_message_context=sample_context
        )
        
        print(f"\n📊 BUTTON DATA ANALYSIS:")
        print(f"   Number of buttons: {len(buttons)}")
        
        # Check each button's data size
        for i, button in enumerate(buttons, 1):
            button_data = button.get('data', '')
            data_length = len(button_data)
            
            print(f"\n   Button {i}: {button['label']}")
            print(f"      Data length: {data_length} characters")
            print(f"      Within limit: {'✅ Yes' if data_length <= 300 else '❌ No (LINE limit is 300)'}")
            
            if data_length > 200:  # Show data if it's getting large
                print(f"      Data preview: {button_data[:100]}...")
            
            # Parse JSON to see structure
            try:
                parsed_data = json.loads(button_data)
                print(f"      Keys: {list(parsed_data.keys())}")
            except json.JSONDecodeError as e:
                print(f"      ❌ Invalid JSON: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def suggest_optimizations():
    """Suggest ways to optimize button data if too large"""
    
    print("\n🔧 OPTIMIZATION STRATEGIES")
    print("=" * 50)
    
    print("📋 If data is too large:")
    print("1. **Store context server-side** - Use content_id to lookup context")
    print("2. **Compress data** - Use shorter keys and abbreviations")
    print("3. **Essential data only** - Only include critical context")
    print("4. **Base64 encoding** - Compress JSON data")
    print("5. **Context lookup** - Store rich context in service, reference by ID")
    
    print("\n💡 Recommended approach:")
    print("• Store rich context in RichMessageService indexed by content_id")
    print("• Button data only contains: action, trigger_type, content_id")
    print("• Lookup full context when processing button click")
    print("• Keeps button data minimal while preserving rich context")

if __name__ == "__main__":
    print("🔍 ENHANCED BUTTON DATA DEBUG")
    print("Checking if rich context data fits in LINE postback limits")
    print()
    
    success = test_button_data_size()
    suggest_optimizations()
    
    print("\n" + "=" * 50)
    if success:
        print("✅ BUTTON DATA ANALYSIS COMPLETE")
        print("Check the data sizes above to see if optimization is needed")
    else:
        print("❌ ANALYSIS FAILED")
        print("Check errors above")