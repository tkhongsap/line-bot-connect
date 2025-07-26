# How to Get Your LINE User ID

To test the Rich Message system, you need your personal LINE User ID. Here's how to find it:

## Method 1: From Your Bot Conversation (Easiest)

1. **Send a message to your LINE Bot** (@970jqtyf)
   - Any message like "hello" or "test"

2. **Check your application logs**
   - If running locally: Check the console output
   - If on Replit: Check the console/logs tab
   - Look for webhook data that looks like this:

```json
{
  "events": [
    {
      "source": {
        "userId": "Udeadbeefdeadbeefdeadbeefdeadbeef",
        "type": "user"
      },
      "message": {
        "text": "hello",
        "type": "text"
      }
    }
  ]
}
```

3. **Copy the userId value**
   - It starts with "U" followed by 32 characters
   - Example: `Udeadbeefdeadbeefdeadbeefdeadbeef`

## Method 2: Enable Debug Logging

Add this to your webhook handler to see user IDs:

```python
@app.route("/webhook", methods=['POST'])
def webhook():
    # ... existing code ...
    for event in events:
        if hasattr(event.source, 'user_id'):
            print(f"DEBUG: User ID = {event.source.user_id}")
```

## Method 3: Use LINE Bot SDK Directly

```python
from linebot.models import MessageEvent, TextMessage

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    print(f"Your LINE User ID: {user_id}")
```

## Security Note

🔒 **Keep your User ID private!** It's like your personal LINE address.

## What It Looks Like

Valid LINE User IDs always:
- Start with "U"
- Are exactly 33 characters long
- Contain only letters and numbers
- Example: `U1234567890abcdef1234567890abcdef`

## Next Steps

Once you have your User ID:

1. Edit `test_personal_rich_message.py`
2. Replace `YOUR_LINE_USER_ID_HERE` with your actual User ID
3. Run the test script:

```bash
# Safe mode (doesn't actually send)
python test_personal_rich_message.py

# Actually send the message
python test_personal_rich_message.py --send
```

## Troubleshooting

**Problem**: Can't find User ID in logs
**Solution**: Make sure your bot is properly configured and receiving webhooks

**Problem**: User ID looks wrong
**Solution**: Should start with "U" and be 33 characters total

**Problem**: Script says "Invalid User ID"
**Solution**: Double-check you copied the full User ID correctly