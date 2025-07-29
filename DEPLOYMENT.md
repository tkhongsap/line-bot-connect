# LINE Bot Deployment Instructions

## Production Deployment on Replit

### Prerequisites
- Access to Replit deployment console
- Git repository synced with Replit

### Deployment Steps

1. **Ensure Latest Code is Pushed**
   ```bash
   git status
   git push origin feat/sub-agent-codebase-improvements
   ```

2. **Trigger Replit Redeployment**
   - Option A: Through Replit Console
     - Go to your Replit deployment
     - Click "Refresh" or "Restart" button
     - Wait for deployment to complete
   
   - Option B: Through Configuration Change
     - Any change to `.replit` file triggers redeployment
     - The configuration has been updated with image dependencies

3. **Verify Deployment**
   - Check deployment logs for startup messages
   - Look for: "Created connection pool for image downloads"
   - Verify no type errors in logs

4. **Test Image Functionality**
   - Send a test image through LINE Bot
   - Verify successful processing
   - Check for HEIC support messages in logs

### Key Fixes Applied

1. **Type Error Fixes**
   - `connection_pool.py`: Added type validation in retry logic
   - `error_handler.py`: Fixed attempt number type handling
   - `image_utils.py`: Explicit integer casting for max_attempts

2. **Dependencies Added**
   - `pillow-heif`: For HEIC/HEIF support (Samsung screenshots)
   - System packages: libheif, x265, libde265

3. **Runtime Safety**
   - Added defensive type checking throughout retry logic
   - Ensured all numeric operations use integers

### Monitoring After Deployment

1. **Check Logs**
   ```
   - No "unsupported operand type(s)" errors
   - "HEIC/HEIF support enabled" message appears
   - Image downloads complete successfully
   ```

2. **Health Check**
   - Visit: `https://your-app.replit.app/health`
   - Verify all services show "active"

3. **Test Image Processing**
   - Send various image formats (JPEG, PNG, HEIC)
   - Verify bot responds with processed images
   - Check response times are reasonable

### Troubleshooting

If type errors persist after deployment:

1. **Verify Code Version**
   - Check git log shows latest commits
   - Ensure Replit pulled latest changes

2. **Force Restart**
   - Stop the deployment completely
   - Clear any cached files
   - Start fresh deployment

3. **Check Dependencies**
   - Verify pillow-heif is installed
   - Run: `uv list | grep pillow`

4. **Debug Mode**
   - Enable debug logging
   - Check exact line numbers in errors
   - Compare with fixed code

### Rollback Plan

If issues occur:
1. Revert to previous commit
2. Redeploy from main branch
3. Investigate issues in development

### Contact

For deployment issues:
- Check Replit deployment logs
- Review error tracking dashboard
- Contact development team with correlation IDs