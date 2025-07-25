import os
import logging
from flask import Flask, request, render_template, jsonify
from werkzeug.middleware.proxy_fix import ProxyFix

# LINE Bot Flask Application
# This application provides webhook endpoints for LINE Bot integration with Azure OpenAI

# Configure logging using centralized utility
from src.utils.logger import configure_root_logger

configure_root_logger()
logger = logging.getLogger(__name__)

# Import services
from src.services.line_service import LineService
from src.services.openai_service import OpenAIService
from src.services.conversation_service import ConversationService
from src.config.settings import Settings

# Create Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key-change-in-production")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Initialize settings
settings = Settings()

# Initialize services
conversation_service = ConversationService()
openai_service = OpenAIService(settings, conversation_service)
line_service = LineService(settings, openai_service, conversation_service)

@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('index.html', 
                         webhook_url=f"{request.url_root}webhook",
                         total_users=len(conversation_service.conversations))

@app.route('/webhook', methods=['POST'])
def webhook():
    """LINE webhook endpoint"""
    try:
        # Get request signature for verification
        signature = request.headers.get('X-Line-Signature', '')
        
        # Get request body
        body = request.get_data(as_text=True)
        
        logger.info(f"Received webhook request. Signature: {signature}")
        logger.debug(f"Request body: {body}")
        
        # Verify and handle the webhook
        result = line_service.handle_webhook(signature, body)
        
        if result['success']:
            return 'OK', 200
        else:
            logger.error(f"Webhook handling failed: {result['error']}")
            return 'Bad Request', 400
            
    except Exception as e:
        logger.error(f"Webhook error: {str(e)}")
        return 'Internal Server Error', 500

@app.route('/webhook', methods=['GET'])
def webhook_verification():
    """LINE webhook verification endpoint"""
    return 'Webhook endpoint is active', 200

@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'total_conversations': len(conversation_service.conversations),
        'services': {
            'line_service': 'active',
            'openai_service': 'active',
            'conversation_service': 'active'
        }
    })

@app.route('/conversations')
def conversations_status():
    """Get conversation statistics"""
    return jsonify({
        'total_users': len(conversation_service.conversations),
        'active_conversations': [
            {
                'user_id': user_id[:8] + '...',  # Hide full user ID for privacy
                'message_count': len(conv['messages']),
                'last_activity': conv.get('last_activity', 'Unknown')
            }
            for user_id, conv in conversation_service.conversations.items()
        ]
    })

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)
