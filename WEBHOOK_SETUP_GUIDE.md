# LINE Webhook Setup Guide

## Available Webhook URLs

### Production (Recommended)
- **URL**: `https://line-bot-connect-tkhongsap.replit.app/webhook`
- **Use for**: Final testing and production LINE Official Account
- **Status**: ✅ Always available (deployed app)

### Development  
- **URL**: `https://3a0d8469-1495-4b1d-afe6-dc163885326a-00-2icgob4ardifi.worf.replit.dev/webhook`
- **Use for**: Development and testing while coding
- **Status**: Available when workspace is active
- **Note**: This URL changes each workspace session - check your dashboard for current URL

## LINE Developer Console Configuration

### 1. Provider Setup
- Go to [LINE Developers Console](https://developers.line.biz/console/)
- Select your provider: "D&T Bot MVP"
- Accept Messaging API Terms and Conditions

### 2. Messaging API Settings
- Navigate to your channel: "D&T Bot MVP"
- Go to "Messaging API" tab
- Verify status shows "Enabled"

### 3. Webhook Configuration
```
Webhook URL: https://line-bot-connect-tkhongsap.replit.app/webhook
Use webhook: ✅ Enabled
Verify webhook: Click to test connection
```

### 4. Response Settings
```
Auto-reply messages: ❌ Disabled
Greeting messages: ❌ Disabled (optional)
Webhooks: ✅ Enabled
```

## Testing Your Bot

### Quick Test Commands
```bash
# Test webhook endpoint
curl -X GET https://line-bot-connect-tkhongsap.replit.app/webhook

# Expected response: "Webhook endpoint is active"
```

### Bot Testing Steps
1. Add your LINE Official Account as friend
2. Send a test message: "Hello"
3. Your AI should respond intelligently in the same language you used for the test message
4. Check dashboard: `https://line-bot-connect-tkhongsap.replit.app/`

## Troubleshooting

### Common Issues
- **Webhook verification fails**: Check URL is exactly correct
- **Bot doesn't respond**: Verify webhook is enabled and auto-reply is disabled
- **Server not responding**: Check if Replit app is deployed and running

### Support
- LINE API Status: [LINE Developers](https://developers.line.biz/console/)
- Bot Dashboard: Monitor activity and debug issues
- Logs: Check Replit console for webhook events

## Security Notes
- All credentials properly configured in Replit Secrets
- Webhook signature verification enabled
- HTTPS required for all LINE webhooks