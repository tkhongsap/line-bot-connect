# Rich Message Testing Guide

You now have a complete rich message automation system with beautiful templates ready to test!

## Quick Start (3 Steps)

### 1. Get Your LINE User ID
```bash
python get_my_user_id.py
```
- Keep the script running
- Send any message to your LINE Bot  
- Your User ID will be captured and saved

### 2. Test Rich Messages (Safe Mode)
```bash
python quick_rich_test.py
```
- Edit the script and set `YOUR_USER_ID`
- This runs in safe mock mode (no actual sending)

### 3. Send Real Test Message
```bash
python quick_rich_test.py --send
```
- Sends a beautiful rich message to your LINE account only
- Includes interactive buttons (Like, Share, Save, React)

## Available Templates

Your system includes many beautiful templates:

🌟 **The Little Prince** - Whimsical inspiration messages
🦁 **Lion Motivation** - Powerful courage themes  
🏃 **Running Energy** - Fitness and perseverance
🌸 **Nature Serenity** - Peaceful wellness themes
🎨 **Creative Inspiration** - Artistic motivation
🌅 **Morning Energy** - Uplifting start-of-day messages

## Advanced Testing

### Multiple Template Options
```bash
python send_test_rich_message.py
```
- Interactive menu with 6+ templates
- Choose theme, test safely, then send

### Test with Specific User ID
```bash
python quick_rich_test.py --user U1234567890abcdef1234567890abcdef
```

## Rich Message Features

✅ **Interactive Buttons**: Like, Share, Save, React  
✅ **Beautiful Templates**: Professional artwork backgrounds  
✅ **Responsive Design**: Works on all LINE app versions  
✅ **Analytics Tracking**: User engagement metrics  
✅ **Safe Testing**: Mock mode prevents accidental broadcasting

## Safety Features

- **Mock Mode**: Test without sending (default)
- **Personal Testing**: Send to yourself only (not all users)  
- **Confirmation**: Prompts before live sending
- **User ID Validation**: Prevents invalid sends

## Next Steps

1. **Test Templates**: Try different themes and templates
2. **Create Custom Content**: Modify quotes and messages  
3. **Scale Up**: When ready, use for broader campaigns
4. **Analytics**: Monitor engagement through interaction buttons

## File Overview

- `quick_rich_test.py` - Simple testing (recommended)
- `send_test_rich_message.py` - Advanced template selection
- `get_my_user_id.py` - Helper to capture your User ID
- `templates/rich_messages/backgrounds/` - All available templates

## Troubleshooting

**User ID Issues**: Use `get_my_user_id.py` to capture it properly  
**Template Not Found**: Check `/templates/rich_messages/backgrounds/`  
**Send Fails**: Verify LINE Bot API configuration in environment

Happy testing! 🚀