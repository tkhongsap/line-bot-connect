"""
Security utilities and middleware for the Flask application
"""

from flask import make_response, request
from functools import wraps
import os

def add_security_headers(response):
    """Add security headers to response"""
    # Content Security Policy
    csp = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "font-src 'self' https://cdn.jsdelivr.net; "
        "img-src 'self' data: https:; "
        "connect-src 'self'"
    )
    response.headers['Content-Security-Policy'] = csp
    
    # Other security headers
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
    
    # HSTS (only in production)
    if os.environ.get("DEBUG", "False").lower() != "true":
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    
    return response

def security_headers(f):
    """Decorator to add security headers to responses"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        response = make_response(f(*args, **kwargs))
        return add_security_headers(response)
    return decorated_function

def setup_cors(app, allowed_origins=None):
    """Setup CORS for the application"""
    if allowed_origins is None:
        allowed_origins = os.environ.get('ALLOWED_ORIGINS', '').split(',')
        allowed_origins = [origin.strip() for origin in allowed_origins if origin.strip()]
    
    @app.after_request
    def after_request(response):
        # Add security headers
        response = add_security_headers(response)
        
        # Add CORS headers if origin is allowed
        origin = request.headers.get('Origin')
        if origin and (not allowed_origins or origin in allowed_origins or '*' in allowed_origins):
            response.headers['Access-Control-Allow-Origin'] = origin
            response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-Line-Signature'
            response.headers['Access-Control-Max-Age'] = '3600'
        
        return response
    
    return app

# LINE webhook IP ranges (as of 2024)
# Source: https://developers.line.biz/en/docs/messaging-api/set-webhook-url/
LINE_WEBHOOK_IPS = [
    '147.92.128.0/22',
    '147.92.132.0/22', 
    '147.92.136.0/22',
    '147.92.140.0/22',
    '147.92.144.0/22',
    '147.92.148.0/22',
    '147.92.152.0/22',
    '147.92.156.0/22'
]

def is_valid_line_ip(ip_address):
    """Check if IP address is from LINE's webhook servers"""
    import ipaddress
    
    try:
        ip = ipaddress.ip_address(ip_address)
        for line_network in LINE_WEBHOOK_IPS:
            if ip in ipaddress.ip_network(line_network):
                return True
        return False
    except ValueError:
        return False

def validate_webhook_ip(f):
    """Decorator to validate webhook requests come from LINE servers"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Skip IP validation in development mode
        if os.environ.get("DEBUG", "False").lower() == "true":
            return f(*args, **kwargs)
        
        # Get client IP (considering proxy)
        from flask import request
        client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        if client_ip:
            # Take the first IP if there are multiple (proxy chain)
            client_ip = client_ip.split(',')[0].strip()
        
        if not is_valid_line_ip(client_ip):
            from flask import abort
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Webhook request from unauthorized IP: {client_ip}")
            abort(403)  # Forbidden
        
        return f(*args, **kwargs)
    return decorated_function