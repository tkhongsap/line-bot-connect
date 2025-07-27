import os
import logging
import secrets
from flask import Flask, request, render_template, jsonify, send_from_directory, abort
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# LINE Bot Flask Application
# This application provides webhook endpoints for LINE Bot integration with Azure OpenAI

# Configure logging using centralized utility
from src.utils.logger import configure_root_logger

configure_root_logger()
logger = logging.getLogger(__name__)

# Import services
from src.services.line_service import LineService
from src.services.openai_service import OpenAIService
from src.services.conversation_factory import create_conversation_service
from src.config.settings import Settings
from src.utils.security import setup_cors, validate_webhook_ip

# Import admin routes
from src.routes.admin_routes import admin_bp

# Create Flask app
app = Flask(__name__)

# Secure session secret handling
session_secret = os.environ.get("SESSION_SECRET")
if not session_secret:
    # Generate a cryptographically secure secret for development
    # In production, SESSION_SECRET must be set as environment variable
    if os.environ.get("DEBUG", "False").lower() == "true":
        session_secret = secrets.token_urlsafe(32)
        logger.warning("Generated random session secret for development. Set SESSION_SECRET env var in production!")
    else:
        raise ValueError("SESSION_SECRET environment variable is required in production")
app.secret_key = session_secret

app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Configure rate limiting
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",
    headers_enabled=True  # Include rate limit headers in responses
)

# Setup CORS and security headers
app = setup_cors(app)

# Register admin blueprint
app.register_blueprint(admin_bp)

# Initialize settings
settings = Settings()

# Initialize services
conversation_service = create_conversation_service()
openai_service = OpenAIService(settings, conversation_service)
line_service = LineService(settings, openai_service, conversation_service)

@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('index.html', 
                         webhook_url=f"{request.url_root}webhook",
                         total_users=len(conversation_service.conversations))

@app.route('/webhook', methods=['POST'])
@limiter.limit("30 per minute")  # Allow 30 webhook calls per minute per IP
@validate_webhook_ip  # Validate request comes from LINE servers
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
@limiter.limit("60 per minute")  # Health checks can be more frequent
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
@limiter.limit("10 per minute")  # Limit conversation status checks
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

@app.route('/static/backgrounds/<filename>')
@limiter.limit("100 per minute")  # Allow frequent access to background images
def serve_template_image(filename):
    """Serve background images for Rich Messages"""
    try:
        # Security check: ensure filename doesn't contain path traversal
        if '..' in filename or '/' in filename or '\\' in filename:
            logger.warning(f"Invalid filename attempted: {filename}")
            abort(400)
        
        # Check if file exists and is an image
        allowed_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.webp'}
        file_ext = os.path.splitext(filename)[1].lower()
        
        if file_ext not in allowed_extensions:
            logger.warning(f"Invalid file extension: {filename}")
            abort(400)
        
        # Serve from templates/rich_messages/backgrounds directory
        backgrounds_dir = os.path.join(os.getcwd(), 'templates', 'rich_messages', 'backgrounds')
        file_path = os.path.join(backgrounds_dir, filename)
        
        if not os.path.exists(file_path):
            logger.warning(f"Background image not found: {filename}")
            abort(404)
        
        logger.info(f"Serving background image: {filename}")
        return send_from_directory(backgrounds_dir, filename, 
                                 mimetype=f'image/{file_ext[1:]}')
        
    except Exception as e:
        logger.error(f"Error serving background image {filename}: {str(e)}")
        abort(500)

if __name__ == '__main__':
    # Only enable debug mode if explicitly set in environment
    debug_mode = os.environ.get("DEBUG", "False").lower() == "true"
    app.run(host="0.0.0.0", port=5000, debug=debug_mode)
