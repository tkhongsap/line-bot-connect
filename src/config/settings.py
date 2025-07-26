import os
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

class Settings:
    """Configuration settings for the LINE Bot application"""
    
    def __init__(self):
        # LINE Bot Configuration
        self.LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
        self.LINE_CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET")
        self.LINE_CHANNEL_ID = os.environ.get("LINE_CHANNEL_ID")
        
        # Azure OpenAI Configuration
        # Note: Using Responses API which requires preview API version for full feature access
        self.AZURE_OPENAI_API_KEY = os.environ.get("AZURE_OPENAI_API_KEY")
        self.AZURE_OPENAI_ENDPOINT = os.environ.get(
            "AZURE_OPENAI_ENDPOINT", 
            "https://thaibev-azure-subscription-ai-foundry.cognitiveservices.azure.com"
        )
        # Responses API compatibility: We use preview in the service itself, but keep this for reference
        self.AZURE_OPENAI_API_VERSION = os.environ.get("AZURE_OPENAI_API_VERSION", "2025-01-01-preview")
        self.AZURE_OPENAI_DEPLOYMENT_NAME = os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4.1-nano")
        
        # Application Configuration
        self.DEBUG = os.environ.get("DEBUG", "True").lower() == "true"
        self.LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
        
        # Conversation limits (for demo purposes)
        self.MAX_MESSAGES_PER_USER = int(os.environ.get("MAX_MESSAGES_PER_USER", "100"))
        self.MAX_TOTAL_CONVERSATIONS = int(os.environ.get("MAX_TOTAL_CONVERSATIONS", "1000"))
        
        # Rich Message Configuration
        self.RICH_MESSAGE_ENABLED = os.environ.get("RICH_MESSAGE_ENABLED", "false").lower() == "true"
        self.RICH_MESSAGE_DEFAULT_SEND_HOUR = int(os.environ.get("RICH_MESSAGE_DEFAULT_SEND_HOUR", "9"))
        self.RICH_MESSAGE_TIMEZONE_AWARE = os.environ.get("RICH_MESSAGE_TIMEZONE_AWARE", "true").lower() == "true"
        self.RICH_MESSAGE_ANALYTICS_ENABLED = os.environ.get("RICH_MESSAGE_ANALYTICS_ENABLED", "true").lower() == "true"
        self.RICH_MESSAGE_TEMPLATE_CACHE_HOURS = int(os.environ.get("RICH_MESSAGE_TEMPLATE_CACHE_HOURS", "24"))
        self.RICH_MESSAGE_CONTENT_CACHE_HOURS = int(os.environ.get("RICH_MESSAGE_CONTENT_CACHE_HOURS", "6"))
        self.RICH_MESSAGE_MAX_RETRIES = int(os.environ.get("RICH_MESSAGE_MAX_RETRIES", "3"))
        self.RICH_MESSAGE_BATCH_SIZE = int(os.environ.get("RICH_MESSAGE_BATCH_SIZE", "100"))
        
        # Validate required settings
        self._validate_settings()
    
    def _validate_settings(self):
        """Validate that all required settings are present"""
        required_settings = [
            ("LINE_CHANNEL_ACCESS_TOKEN", self.LINE_CHANNEL_ACCESS_TOKEN),
            ("LINE_CHANNEL_SECRET", self.LINE_CHANNEL_SECRET),
            ("AZURE_OPENAI_API_KEY", self.AZURE_OPENAI_API_KEY),
            ("AZURE_OPENAI_ENDPOINT", self.AZURE_OPENAI_ENDPOINT),
            ("AZURE_OPENAI_DEPLOYMENT_NAME", self.AZURE_OPENAI_DEPLOYMENT_NAME)
        ]
        
        missing_settings = []
        for setting_name, setting_value in required_settings:
            if not setting_value:
                missing_settings.append(setting_name)
        
        if missing_settings:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing_settings)}. "
                "Please check your .env file or environment configuration."
            )
    
    def get_summary(self):
        """Get a summary of current settings (without sensitive values)"""
        return {
            "debug_mode": self.DEBUG,
            "log_level": self.LOG_LEVEL,
            "azure_endpoint": self.AZURE_OPENAI_ENDPOINT,
            "api_version": self.AZURE_OPENAI_API_VERSION,
            "deployment_name": self.AZURE_OPENAI_DEPLOYMENT_NAME,
            "max_messages_per_user": self.MAX_MESSAGES_PER_USER,
            "max_total_conversations": self.MAX_TOTAL_CONVERSATIONS,
            "line_channel_configured": bool(self.LINE_CHANNEL_ACCESS_TOKEN),
            "azure_openai_configured": bool(self.AZURE_OPENAI_API_KEY),
            "api_type": "Azure OpenAI Responses API",  # Updated to reflect new API usage
            "rich_message_enabled": self.RICH_MESSAGE_ENABLED,
            "rich_message_send_hour": self.RICH_MESSAGE_DEFAULT_SEND_HOUR,
            "rich_message_timezone_aware": self.RICH_MESSAGE_TIMEZONE_AWARE,
            "rich_message_analytics": self.RICH_MESSAGE_ANALYTICS_ENABLED,
            "rich_message_max_retries": self.RICH_MESSAGE_MAX_RETRIES,
            "rich_message_batch_size": self.RICH_MESSAGE_BATCH_SIZE
        }
