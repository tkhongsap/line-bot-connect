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
        self.AZURE_OPENAI_API_VERSION = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
        self.AZURE_OPENAI_DEPLOYMENT_NAME = os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4-1-mini")
        
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
        # Set default values if not provided (for demo purposes)
        if not self.LINE_CHANNEL_ACCESS_TOKEN:
            self.LINE_CHANNEL_ACCESS_TOKEN = "JONXjpaqG/G6wOjwzhQry/mCWjSK4/nBQbuiwZ6ueH+Ry3drttiVcVZYiz2GlS0eUZqd5/G4SpfnQSoRXgg0tcdww6YPJm1vTUy4InLkeYWzRgGAfCumG0nnDcNa7lL6RINHfyqVzSAyZRmOKJ4wcQdB04t89/1O/w1cDnyilFU="
        
        if not self.LINE_CHANNEL_SECRET:
            self.LINE_CHANNEL_SECRET = "b7cfa8eef4243c0f44491d8a37d73be8"
            
        if not self.AZURE_OPENAI_API_KEY:
            self.AZURE_OPENAI_API_KEY = "demo-key-needs-replacement"
        
        required_settings = [
            ("LINE_CHANNEL_ACCESS_TOKEN", self.LINE_CHANNEL_ACCESS_TOKEN),
            ("LINE_CHANNEL_SECRET", self.LINE_CHANNEL_SECRET),
            ("AZURE_OPENAI_API_KEY", self.AZURE_OPENAI_API_KEY),
        ]
        
        missing_settings = []
        for name, value in required_settings:
            if not value or value == "your_azure_openai_api_key_here":
                missing_settings.append(name)
        
        if missing_settings:
            print(f"WARNING: Missing or placeholder values for: {', '.join(missing_settings)}")
            print("The chatbot will start but Azure OpenAI integration may not work until you provide the real API key.")
        
        # Only fail if LINE credentials are missing (Azure OpenAI can be added later)
        critical_missing = [name for name, value in required_settings[:2] if not value]
        if critical_missing:
            raise ValueError(
                f"Missing critical environment variables: {', '.join(critical_missing)}. "
                f"Please check your .env file or environment configuration."
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
