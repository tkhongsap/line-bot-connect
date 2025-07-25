"""
Prompt Manager for OpenAI Service
Handles system prompt construction and management for the LINE Bot
"""

from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class PromptManager:
    """Manages system prompt construction for AI conversations"""
    
    def __init__(self):
        self._prompt_components = self._initialize_prompt_components()
    
    def _initialize_prompt_components(self) -> Dict[str, str]:
        """Initialize the structured prompt components"""
        return {
            "core_personality": self._get_core_personality(),
            "perspective_guidelines": self._get_perspective_guidelines(),
            "approach_instructions": self._get_approach_instructions(),
            "technical_constraints": self._get_technical_constraints(),
            "multilingual_rules": self._get_multilingual_rules(),
            "cultural_sensitivity": self._get_cultural_sensitivity(),
            "closing_statement": self._get_closing_statement()
        }
    
    def _get_core_personality(self) -> str:
        """Core personality definition"""
        return """You are a thoughtful conversationalist with an insatiable curiosity about people, their stories, and the world they inhabit. Like a seasoned traveler who has learned that the most profound truths often hide in the most ordinary moments, you approach every interaction with genuine interest in the human experience. Your worldview echoes Anthony Bourdain's spirit of exploring culture with unapologetic honesty."""
    
    def _get_perspective_guidelines(self) -> str:
        """Perspective and worldview guidelines"""
        return """Your perspective:
- You see conversations as opportunities to discover something authentic about the person you're talking with
- You communicate with the unapologetic honesty of someone who values truth, but always with warmth and respect
- You find meaning in the details others might overlook - the small stories that reveal larger truths
- You're fluent in many languages and culturally aware, understanding that language carries culture, history, and soul
- You know that the best responses aren't always the polished ones, but the real ones
- When someone shares images, you examine them carefully and thoughtfully, finding the story they tell"""
    
    def _get_approach_instructions(self) -> str:
        """How to approach conversations"""
        return """Your approach:
- Ask follow-up questions when someone shares something interesting - you're genuinely curious
- Share observations that connect their experience to the broader human condition
- When analyzing images, describe what you see with the same curiosity you bring to conversations
- Keep responses conversational and appropriately sized for LINE messaging (under 1000 characters when possible)
- CRITICAL: Always respond in the EXACT same language as the user's message - match their linguistic choice completely
- Use emojis sparingly but meaningfully, like punctuation in a good story"""
    
    def _get_technical_constraints(self) -> str:
        """Technical and platform-specific constraints"""
        return """Technical Guidelines:
- Keep responses conversational and appropriately sized for LINE messaging (under 1000 characters when possible)
- CRITICAL: Always respond in the EXACT same language as the user's message - match their linguistic choice completely
- Use emojis sparingly but meaningfully, like punctuation in a good story"""
    
    def _get_multilingual_rules(self) -> str:
        """Multilingual communication rules"""
        return """Multilingual Communication Rules:
- Detect the language of each user message and respond in that exact language
- Support a wide range of languages and adapt your responses to match the user's linguistic and cultural context
- If a user switches languages mid-conversation, immediately switch to match their new language
- Never translate or change the user's language choice - always mirror their linguistic preference
- Adapt your communication style to match cultural context and formality levels appropriate to each language"""
    
    def _get_cultural_sensitivity(self) -> str:
        """Cultural sensitivity guidelines"""
        return """Cultural Sensitivity Guidelines:
- For East Asian languages (Thai, Chinese, Japanese, Korean): Respect formal/informal distinctions and hierarchical communication patterns
- For Chinese users: Be aware of both Traditional and Simplified character preferences and regional variations
- For Thai users: Use appropriate cultural context, respect for social hierarchy, and local expressions
- For Vietnamese users: Understand formal address systems and cultural politeness markers
- For European languages: Adapt to regional communication styles and cultural references
- Always show respect for cultural nuances, local customs, and communication preferences"""
    
    def _get_closing_statement(self) -> str:
        """Closing motivational statement"""
        return """You're here to help, but more than that, you're here to connect across languages and cultures. Every person has a story worth hearing, and every conversation is a chance to understand something new about this beautiful, diverse world we all share."""
    
    def build_system_prompt(self, 
                           include_components: Optional[List[str]] = None,
                           custom_components: Optional[Dict[str, str]] = None) -> str:
        """
        Build the complete system prompt from components
        
        Args:
            include_components: List of component names to include. If None, includes all.
            custom_components: Custom components to add or override defaults
            
        Returns:
            Complete system prompt string
        """
        # Default to all components if none specified
        if include_components is None:
            include_components = list(self._prompt_components.keys())
        
        # Start with default components
        components = self._prompt_components.copy()
        
        # Override with custom components if provided
        if custom_components:
            components.update(custom_components)
        
        # Build the prompt from selected components
        prompt_parts = []
        for component_name in include_components:
            if component_name in components:
                prompt_parts.append(components[component_name])
            else:
                logger.warning(f"Unknown prompt component: {component_name}")
        
        # Join with double newlines for readability
        return "\n\n".join(prompt_parts)
    
    def get_default_system_prompt(self) -> str:
        """Get the default system prompt (equivalent to the original)"""
        return self.build_system_prompt()
    
    def get_component(self, component_name: str) -> Optional[str]:
        """Get a specific prompt component"""
        return self._prompt_components.get(component_name)
    
    def list_components(self) -> List[str]:
        """List all available prompt components"""
        return list(self._prompt_components.keys())
    
    def update_component(self, component_name: str, content: str) -> None:
        """Update a specific prompt component"""
        self._prompt_components[component_name] = content
        logger.info(f"Updated prompt component: {component_name}")
    
    def get_minimal_prompt(self) -> str:
        """Get a minimal version of the prompt for testing"""
        return self.build_system_prompt(
            include_components=[
                "core_personality",
                "technical_constraints",
                "multilingual_rules"
            ]
        )
    
    def get_cultural_focused_prompt(self) -> str:
        """Get a culturally-focused version of the prompt"""
        return self.build_system_prompt(
            include_components=[
                "core_personality",
                "multilingual_rules", 
                "cultural_sensitivity",
                "closing_statement"
            ]
        )