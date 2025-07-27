"""
Rich Message Content Generator with Anthony Bourdain Persona

This module generates content specifically for Rich Messages using Anthony Bourdain's
authentic voice and perspective, optimized for the LINE messaging format.
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import random

from src.utils.prompt_manager import PromptManager

logger = logging.getLogger(__name__)


class RichMessageContentGenerator:
    """Generates Rich Message content using Anthony Bourdain's persona"""
    
    def __init__(self, openai_service=None):
        """
        Initialize the Rich Message content generator
        
        Args:
            openai_service: OpenAI service instance for content generation
        """
        self.openai_service = openai_service
        self.prompt_manager = PromptManager()
        
        # Rich Message specific constraints
        self.MAX_TITLE_LENGTH = 50  # Keep titles short for Rich Messages
        self.MAX_CONTENT_LENGTH = 250  # Bourdain-style: punchy, not verbose
        self.MIN_CONTENT_LENGTH = 80  # Ensure substance
        
        # Content themes mapped to Bourdain's worldview
        self.bourdain_themes = {
            "productivity": {
                "focus": "real work, authentic effort, cutting through corporate bullshit",
                "context": "workplace wisdom without the motivational speaker nonsense"
            },
            "wellness": {
                "focus": "genuine human connection, not sanitized self-care",
                "context": "real wellness comes from authentic experiences, not apps"
            },
            "motivation": {
                "focus": "honest encouragement rooted in real-world experience", 
                "context": "motivation through truth-telling, not empty cheerleading"
            },
            "inspiration": {
                "focus": "stories from the streets, kitchens, and real people",
                "context": "inspiration from authentic human stories, not Instagram quotes"
            },
            "food": {
                "focus": "honest food talk, street vendors over celebrity chefs",
                "context": "food as culture, community, and human connection"
            },
            "travel": {
                "focus": "real places where locals go, not tourist traps",
                "context": "travel as cultural immersion, not sightseeing"
            }
        }
        
        logger.info("RichMessageContentGenerator initialized with Bourdain persona")
    
    def generate_rich_message_content(self, 
                                    theme: str = "motivation",
                                    template_mood: Optional[str] = None,
                                    user_context: Optional[str] = None) -> Dict[str, str]:
        """
        Generate Rich Message content using Bourdain's persona
        
        Args:
            theme: Content theme (productivity, wellness, motivation, etc.)
            template_mood: Visual mood of the template being used
            user_context: Optional user context for personalization
            
        Returns:
            Dictionary with 'title' and 'content' keys
        """
        try:
            # Build Rich Message specific prompt
            prompt = self._build_rich_message_prompt(theme, template_mood, user_context)
            
            if self.openai_service:
                # Generate content using AI with Bourdain persona
                response = self.openai_service.get_response(
                    user_id="rich_message_generator",
                    message=prompt,
                    use_streaming=False
                )
                
                if response and response.get('success') and response.get('message'):
                    return self._parse_ai_response(response['message'], theme)
            
            # Fallback to curated Bourdain-style content
            logger.info("Using fallback Bourdain-style content")
            return self._get_fallback_content(theme, template_mood)
            
        except Exception as e:
            logger.error(f"Failed to generate Rich Message content: {str(e)}")
            return self._get_emergency_fallback(theme)
    
    def _build_rich_message_prompt(self, 
                                 theme: str, 
                                 template_mood: Optional[str] = None,
                                 user_context: Optional[str] = None) -> str:
        """Build a Bourdain-style prompt for Rich Message content"""
        
        theme_info = self.bourdain_themes.get(theme, self.bourdain_themes["motivation"])
        
        # Start with core Bourdain personality
        base_prompt = self.prompt_manager.get_component("core_personality")
        
        # Add Rich Message specific instructions
        rich_message_instructions = f"""
RICH MESSAGE FORMAT - CRITICAL CONSTRAINTS:
- You're creating content for a LINE Rich Message (mobile messaging)
- MAXIMUM 250 characters total (title + content combined)
- Title: 15-40 characters, punchy and authentic 
- Content: 80-200 characters, Bourdain's voice but mobile-friendly
- No corporate motivational speaker bullshit
- Real talk, authentic perspective, but appropriate for messaging

THEME: {theme}
FOCUS: {theme_info['focus']}
CONTEXT: {theme_info['context']}
"""
        
        if template_mood:
            rich_message_instructions += f"\nVISUAL MOOD: The background image has a {template_mood} feel - match that energy."
        
        if user_context:
            rich_message_instructions += f"\nUSER CONTEXT: {user_context}"
        
        # Content generation request
        content_request = """
Generate a Rich Message with:
1. A short, punchy title (with ONE emoji max)
2. Content that sounds like Bourdain having a quick conversation

Format as:
TITLE: [your title here]
CONTENT: [your content here]

Remember: This is going on someone's phone. Be conversational, authentic, but concise. Skip the philosophical speeches - give them something real they can use.
"""
        
        return f"{base_prompt}\n\n{rich_message_instructions}\n\n{content_request}"
    
    def _parse_ai_response(self, ai_response: str, theme: str) -> Dict[str, str]:
        """Parse AI response into title and content"""
        try:
            lines = [line.strip() for line in ai_response.split('\n') if line.strip()]
            
            title = ""
            content = ""
            
            for line in lines:
                if line.upper().startswith('TITLE:'):
                    title = line[6:].strip()
                elif line.upper().startswith('CONTENT:'):
                    content = line[8:].strip()
                elif not title and len(line) <= self.MAX_TITLE_LENGTH:
                    # First short line might be title
                    title = line
                elif not content and len(line) > len(title):
                    # Longer line might be content
                    content = line
            
            # If we didn't get proper format, try to split by common patterns
            if not title or not content:
                # Try to find title/content in the response
                if len(lines) >= 2:
                    title = lines[0][:self.MAX_TITLE_LENGTH]
                    content = ' '.join(lines[1:])[:self.MAX_CONTENT_LENGTH]
                elif len(lines) == 1:
                    # Single line - split it
                    full_text = lines[0]
                    if len(full_text) > self.MAX_TITLE_LENGTH:
                        # Find a good split point
                        split_point = full_text.find('. ') or full_text.find('! ') or full_text.find('? ')
                        if split_point > 10 and split_point < self.MAX_TITLE_LENGTH:
                            title = full_text[:split_point+1].strip()
                            content = full_text[split_point+1:].strip()
                        else:
                            title = self._generate_fallback_title(theme)
                            content = full_text[:self.MAX_CONTENT_LENGTH]
            
            # Validate and clean up
            title = title[:self.MAX_TITLE_LENGTH].strip()
            content = content[:self.MAX_CONTENT_LENGTH].strip()
            
            # Ensure we have both
            if not title:
                title = self._generate_fallback_title(theme)
            if not content:
                content = "Real talk. Real perspective. No bullshit."
            
            logger.info(f"Generated Bourdain-style Rich Message: '{title}' ({len(title)} chars)")
            return {"title": title, "content": content}
            
        except Exception as e:
            logger.error(f"Failed to parse AI response: {str(e)}")
            return self._get_emergency_fallback(theme)
    
    def _get_fallback_content(self, theme: str, template_mood: Optional[str] = None) -> Dict[str, str]:
        """Get curated Bourdain-style fallback content"""
        
        fallback_content = {
            "productivity": [
                {
                    "title": "☕ Real Work", 
                    "content": "Best conversations happen over coffee with people who actually do the work. Skip the meetings. Find the doers."
                },
                {
                    "title": "🎯 Cut the Bullshit",
                    "content": "Half the corporate productivity advice is garbage. Find what works for you. Do that. Ignore the rest."
                },
                {
                    "title": "🔧 Craft Over Hype",
                    "content": "Master your craft like a line cook masters their station. Consistent, focused, no wasted motion."
                }
            ],
            "wellness": [
                {
                    "title": "🚶‍♂️ Real Peace",
                    "content": "Real wellness isn't in an app. It's a walk. A good meal. Honest conversation. Time to think."
                },
                {
                    "title": "🌍 Human Connection",
                    "content": "Best therapy? Listening to someone's story over a shared meal. We're all figuring this out together."
                },
                {
                    "title": "🥃 Honest Moments",
                    "content": "Self-care isn't yoga poses. It's being honest about what you need and brave enough to ask for it."
                }
            ],
            "motivation": [
                {
                    "title": "🔥 Earned Wisdom",
                    "content": "Motivation from someone who's never failed is worthless. Trust the scars. Learn from people who've been there."
                },
                {
                    "title": "🛤️ Your Path",
                    "content": "Stop following someone else's blueprint. Your journey looks different because you're not them."
                },
                {
                    "title": "💪 Real Strength",
                    "content": "Strength isn't pretending everything's fine. It's showing up when things are messy."
                }
            ],
            "inspiration": [
                {
                    "title": "📖 Street Stories",
                    "content": "Best stories come from taxi drivers, street vendors, people grinding every day. Listen to them."
                },
                {
                    "title": "✨ Authentic Moments",
                    "content": "Real inspiration happens at plastic tables in places tourists don't go. Seek the authentic."
                },
                {
                    "title": "🎨 Create Reality",
                    "content": "Don't wait for inspiration. Make something real. Start where you are with what you have."
                }
            ]
        }
        
        theme_content = fallback_content.get(theme, fallback_content["motivation"])
        selected = random.choice(theme_content)
        
        logger.info(f"Using fallback Bourdain content for theme: {theme}")
        return selected
    
    def _get_emergency_fallback(self, theme: str) -> Dict[str, str]:
        """Emergency fallback content"""
        emergency_messages = {
            "productivity": {"title": "☕ Keep Moving", "content": "Real work happens one conversation at a time."},
            "wellness": {"title": "🚶‍♂️ Stay Real", "content": "Authentic moments beat perfect plans."},
            "motivation": {"title": "🔥 Stay True", "content": "Your story matters. Tell it honestly."},
            "inspiration": {"title": "✨ Find Truth", "content": "Real stories happen in real places."}
        }
        
        return emergency_messages.get(theme, emergency_messages["motivation"])
    
    def _generate_fallback_title(self, theme: str) -> str:
        """Generate a fallback title for the theme"""
        fallback_titles = {
            "productivity": "☕ Real Talk",
            "wellness": "🚶‍♂️ Honest Moment", 
            "motivation": "🔥 Keep Going",
            "inspiration": "✨ True Story"
        }
        
        return fallback_titles.get(theme, "💬 Real Talk")
    
    def validate_content_length(self, title: str, content: str) -> bool:
        """Validate that content meets Rich Message constraints"""
        total_length = len(title) + len(content)
        
        if total_length > 300:  # Give some buffer
            logger.warning(f"Rich Message content too long: {total_length} characters")
            return False
            
        if len(title) > self.MAX_TITLE_LENGTH:
            logger.warning(f"Title too long: {len(title)} characters")
            return False
            
        if len(content) < self.MIN_CONTENT_LENGTH:
            logger.warning(f"Content too short: {len(content)} characters")
            return False
            
        return True
    
    def optimize_content_for_template(self, 
                                    content: Dict[str, str], 
                                    template_name: str) -> Dict[str, str]:
        """Optimize content based on template characteristics"""
        
        # Template mood mapping for content optimization
        template_moods = {
            "coffee": "energetic and focused",
            "nature": "contemplative and grounded", 
            "abstract": "bold and direct",
            "wellness": "authentic and human",
            "productivity": "practical and real",
            "motivation": "honest and encouraging"
        }
        
        # Find template mood
        template_mood = None
        for mood_key, mood_desc in template_moods.items():
            if mood_key in template_name.lower():
                template_mood = mood_desc
                break
        
        if template_mood:
            logger.info(f"Optimized content for {template_mood} template mood")
        
        return content  # Content is already optimized through generation process