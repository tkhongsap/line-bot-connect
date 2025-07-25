import logging
import os
from datetime import datetime

class Logger:
    """Centralized logging utilities for the LINE Bot application"""
    
    @staticmethod
    def setup_logger(name: str = __name__, level: str = "INFO"):
        """Set up logger with consistent formatting"""
        
        # Get log level from environment or use provided level
        log_level = os.environ.get("LOG_LEVEL", level).upper()
        
        # Create logger
        logger = logging.getLogger(name)
        logger.setLevel(getattr(logging, log_level, logging.INFO))
        
        # Avoid duplicate handlers
        if logger.handlers:
            return logger
        
        # Create formatter
        formatter = logging.Formatter(
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(getattr(logging, log_level, logging.INFO))
        console_handler.setFormatter(formatter)
        
        # Add handlers to logger
        logger.addHandler(console_handler)
        
        return logger
    
    @staticmethod
    def log_webhook_event(user_id: str = "", message: str = "", response: str = "", error: str = ""):
        """Log webhook events for monitoring and debugging"""
        logger = logging.getLogger("webhook")
        
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "user_id": user_id[:8] + "..." if user_id else "unknown",  # Privacy
            "message_length": len(message) if message else 0,
            "response_length": len(response) if response else 0,
            "has_error": bool(error)
        }
        
        if error:
            logger.error(f"Webhook Error: {log_data} - Error: {error}")
        else:
            logger.info(f"Webhook Success: {log_data}")
    
    @staticmethod
    def log_openai_usage(user_id: str = "", tokens_used: int = 0, model: str = "", success: bool = False):
        """Log OpenAI API usage for monitoring costs and performance"""
        logger = logging.getLogger("openai_usage")
        
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "user_id": user_id[:8] + "..." if user_id else "unknown",
            "tokens_used": tokens_used,
            "model": model or "unknown",
            "success": success
        }
        
        logger.info(f"OpenAI Usage: {log_data}")

def configure_root_logger(level: str = "INFO") -> None:
    """Configure the root logger once for the whole application."""
    log_level = os.environ.get("LOG_LEVEL", level).upper()
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

# Configure root logger on import for convenience
configure_root_logger()
