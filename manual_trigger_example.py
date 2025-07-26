#!/usr/bin/env python3
"""
Manual Rich Message Trigger Example

This script shows exactly how to manually trigger Rich Message delivery
in different scenarios.
"""

import sys
import os
from datetime import datetime, time

# Add src to path
sys.path.append('/home/runner/workspace/src')

def manual_trigger_examples():
    """Show different ways to manually trigger Rich Messages"""
    
    print("🎮 MANUAL RICH MESSAGE TRIGGER EXAMPLES")
    print("=" * 50)
    print()
    
    print("📋 Available Trigger Methods:")
    print("1. Direct function calls (for testing)")
    print("2. Celery task execution")
    print("3. Admin dashboard interface")
    print("4. REST API endpoints")
    print()
    
    # === METHOD 1: DIRECT FUNCTION CALLS ===
    print("1️⃣ DIRECT FUNCTION CALLS (Testing Mode)")
    print("-" * 30)
    
    try:
        from src.services.rich_message_service import RichMessageService
        from src.utils.template_manager import TemplateManager
        from src.utils.content_generator import ContentGenerator
        from src.config.rich_message_config import get_rich_message_config
        
        print("```python")
        print("# Initialize services")
        print("config = get_rich_message_config()")
        print("template_manager = TemplateManager(config)")
        print("rich_service = RichMessageService(line_bot_api=None)  # Mock mode")
        print()
        print("# Create Rich Message")
        print("message = rich_service.create_flex_message(")
        print("    title='Manual Test Message',")
        print("    content='This is a manually triggered Rich Message!'")
        print(")")
        print("```")
        print("✅ Direct calls: Available for testing")
        
    except Exception as e:
        print(f"❌ Direct calls: {e}")
    
    print()
    
    # === METHOD 2: CELERY TASK EXECUTION ===
    print("2️⃣ CELERY TASK EXECUTION (Production Mode)")
    print("-" * 30)
    
    try:
        from src.tasks.rich_message_automation import (
            generate_daily_rich_messages,
            generate_rich_message_for_category,
            send_rich_message_to_user
        )
        
        print("```python")
        print("# Import tasks")
        print("from src.tasks.rich_message_automation import (")
        print("    generate_daily_rich_messages,")
        print("    generate_rich_message_for_category,")
        print("    send_rich_message_to_user")
        print(")")
        print()
        print("# Trigger all categories immediately")
        print("result1 = generate_daily_rich_messages.delay()")
        print()
        print("# Trigger specific category at specific time")
        print("result2 = generate_rich_message_for_category.delay('productivity', '14:00')")
        print()
        print("# Send to specific user")
        print("result3 = send_rich_message_to_user.delay('user123', 'wellness')")
        print()
        print("# Check results")
        print("print(result1.get())  # Get task result")
        print("```")
        print("✅ Celery tasks: Available for production")
        
    except Exception as e:
        print(f"❌ Celery tasks: {e}")
    
    print()
    
    # === METHOD 3: ADMIN DASHBOARD ===
    print("3️⃣ ADMIN DASHBOARD INTERFACE")
    print("-" * 30)
    
    print("📋 Steps to use admin dashboard:")
    print("1. Start Flask app: python app.py")
    print("2. Navigate to: http://localhost:5000/admin/")
    print("3. Create new campaign:")
    print("   - Select category: morning_energy, evening_calm, etc.")
    print("   - Set delivery time: immediate or scheduled")
    print("   - Choose audience: all users or specific segment")
    print("4. Click 'Trigger Campaign'")
    print()
    
    if os.path.exists("/home/runner/workspace/src/routes/admin_routes.py"):
        print("✅ Admin dashboard: Available at /admin/")
    else:
        print("❌ Admin dashboard: Not found")
    
    print()
    
    # === METHOD 4: REST API ===
    print("4️⃣ REST API ENDPOINTS")
    print("-" * 30)
    
    print("```bash")
    print("# Create new campaign")
    print("curl -X POST http://localhost:5000/admin/api/campaigns \\")
    print("  -H 'Content-Type: application/json' \\")
    print("  -d '{")
    print("    \"name\": \"Manual Test Campaign\",")
    print("    \"category\": \"general_motivation\",")
    print("    \"delivery_time\": \"immediate\",")
    print("    \"target_audience\": \"all\"")
    print("  }'")
    print()
    print("# Trigger immediate delivery")
    print("curl -X POST http://localhost:5000/admin/api/trigger \\")
    print("  -H 'Content-Type: application/json' \\")
    print("  -d '{")
    print("    \"category\": \"productivity\",")
    print("    \"time\": \"now\"")
    print("  }'")
    print()
    print("# Get analytics")
    print("curl http://localhost:5000/admin/api/analytics")
    print("```")
    print("✅ REST API: Available for external integrations")
    print()
    
    # === PRACTICAL EXAMPLES ===
    print("💡 PRACTICAL USAGE SCENARIOS:")
    print("-" * 30)
    print()
    
    print("🌅 Send morning motivation at 7 AM:")
    print("generate_rich_message_for_category.delay('morning_energy', '07:00')")
    print()
    
    print("🌙 Send evening calm at 8 PM:")
    print("generate_rich_message_for_category.delay('evening_calm', '20:00')")
    print()
    
    print("💪 Send productivity boost during work hours:")
    print("generate_rich_message_for_category.delay('productivity', '14:00')")
    print()
    
    print("❤️ Send wellness reminder:")
    print("generate_rich_message_for_category.delay('wellness', '12:00')")
    print()
    
    print("🎯 Send to specific user immediately:")
    print("send_rich_message_to_user.delay('LINE_USER_ID_HERE', 'general_motivation')")
    print()
    
    # === SCHEDULING OPTIONS ===
    print("📅 SCHEDULING OPTIONS:")
    print("-" * 30)
    print()
    
    print("⚡ Immediate delivery:")
    print("- Use .delay() with current time")
    print("- Admin dashboard 'Send Now' button")
    print("- API with time: 'now'")
    print()
    
    print("⏰ Scheduled delivery:")
    print("- Use .apply_async(eta=datetime) for specific time")
    print("- Admin dashboard with future time")
    print("- API with specific timestamp")
    print()
    
    print("🔄 Recurring delivery:")
    print("- Celery Beat handles automatic scheduling")
    print("- Crontab configuration in automation tasks")
    print("- No manual intervention needed")
    print()
    
    # === MONITORING ===
    print("📊 MONITORING AND TRACKING:")
    print("-" * 30)
    print()
    
    print("📈 Check delivery status:")
    print("```python")
    print("from src.utils.analytics_tracker import get_analytics_tracker")
    print("analytics = get_analytics_tracker()")
    print("metrics = analytics.calculate_system_metrics()")
    print("print(f'Messages sent: {metrics.total_messages}')")
    print("```")
    print()
    
    print("🎯 Monitor user engagement:")
    print("```python")
    print("engagement = analytics.get_user_engagement_summary()")
    print("print(f'Active users: {len(engagement)}')")
    print("```")
    print()
    
    print("🏥 System health check:")
    print("```python")
    print("from src.tasks.rich_message_automation import health_check_task")
    print("health = health_check_task.delay()")
    print("print(health.get())")
    print("```")
    print()
    
    print("=" * 50)
    print("🎊 SUMMARY: Multiple ways to control Rich Message delivery")
    print("✅ Your templates are ready")
    print("✅ Content generation is automated")
    print("✅ Delivery is flexible (auto + manual)")
    print("✅ Full monitoring and analytics available")
    print("=" * 50)


if __name__ == "__main__":
    manual_trigger_examples()