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
        self.AZURE_OPENAI_API_KEY = os.environ.get("AZURE_OPENAI_API_KEY")
        self.AZURE_OPENAI_ENDPOINT = os.environ.get(
            "AZURE_OPENAI_ENDPOINT", 
            "https://thaibev-azure-subscription-ai-foundry.cognitiveservices.azure.com"
        )
        self.AZURE_OPENAI_API_VERSION = os.environ.get("AZURE_OPENAI_API_VERSION", "2025-01-01-preview")
        self.AZURE_OPENAI_DEPLOYMENT_NAME = os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4.1")
        
        # Application Configuration
        self.DEBUG = os.environ.get("DEBUG", "True").lower() == "true"
        self.LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
        
        # Conversation limits (for demo purposes)
        self.MAX_MESSAGES_PER_USER = int(os.environ.get("MAX_MESSAGES_PER_USER", "100"))
        self.MAX_TOTAL_CONVERSATIONS = int(os.environ.get("MAX_TOTAL_CONVERSATIONS", "1000"))
        
        # Validate required settings
        self._validate_settings()
    
    def _validate_settings(self):
        """Validate that required environment variables are set"""
        required_settings = [
            ("LINE_CHANNEL_ACCESS_TOKEN", self.LINE_CHANNEL_ACCESS_TOKEN),
            ("LINE_CHANNEL_SECRET", self.LINE_CHANNEL_SECRET),
            ("AZURE_OPENAI_API_KEY", self.AZURE_OPENAI_API_KEY),
        ]
        
        missing_settings = []
        for name, value in required_settings:
            if not value:
                missing_settings.append(name)
        
        if missing_settings:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing_settings)}. "
                f"Please set these in Replit Secrets or your .env file."
            )
    
    def get_webhook_url(self, base_url: str) -> str:
        """Generate webhook URL for LINE configuration"""
        return f"{base_url.rstrip('/')}/webhook"
    
    def to_dict(self):
        """Return configuration as dictionary (excluding sensitive data)"""
        return {
            "LINE_CHANNEL_ID": self.LINE_CHANNEL_ID,
            "AZURE_OPENAI_ENDPOINT": self.AZURE_OPENAI_ENDPOINT,
            "AZURE_OPENAI_API_VERSION": self.AZURE_OPENAI_API_VERSION,
            "AZURE_OPENAI_DEPLOYMENT_NAME": self.AZURE_OPENAI_DEPLOYMENT_NAME,
            "DEBUG": self.DEBUG,
            "LOG_LEVEL": self.LOG_LEVEL,
            "MAX_MESSAGES_PER_USER": self.MAX_MESSAGES_PER_USER,
            "MAX_TOTAL_CONVERSATIONS": self.MAX_TOTAL_CONVERSATIONS,
        }
