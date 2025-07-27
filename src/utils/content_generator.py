"""
Content Generator for Rich Message automation system.

This module handles AI-powered content generation using Azure OpenAI
for creating themed inspirational and motivational content.
"""

import json
import logging
import random
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, time
from dataclasses import dataclass
import hashlib

from src.services.openai_service import OpenAIService
from src.models.rich_message_models import RichMessageContent, ContentCategory, ContentTheme, ValidationError
from src.config.rich_message_config import get_rich_message_config

logger = logging.getLogger(__name__)


@dataclass
class ContentRequest:
    """Request parameters for content generation"""
    category: ContentCategory
    theme: Optional[ContentTheme] = None
    length: str = "medium"  # "short", "medium", "long"
    tone: str = "friendly"  # "energetic", "calm", "professional", "friendly"
    language: str = "en"  # Language code
    time_context: Optional[time] = None
    energy_level: str = "medium"  # "low", "medium", "high"
    custom_context: Optional[str] = None


@dataclass
class GeneratedContent:
    """Generated content result"""
    title: str
    content: str
    language: str
    category: ContentCategory
    theme: Optional[ContentTheme]
    metadata: Dict[str, Any]
    generation_time: datetime


class ContentGenerator:
    """
    Generates themed inspirational and motivational content using Azure OpenAI.
    
    Provides intelligent content generation with cultural sensitivity,
    length control, and thematic consistency for Rich Message automation.
    """
    
    def __init__(self, openai_service: Optional[OpenAIService] = None, config=None):
        """
        Initialize the ContentGenerator.
        
        Args:
            openai_service: OpenAI service instance
            config: Optional configuration object
        """
        self.config = config or get_rich_message_config()
        self.openai_service = openai_service
        self.content_cache: Dict[str, GeneratedContent] = {}
        
        # Load content prompts
        self._load_content_prompts()
    
    def _load_content_prompts(self) -> None:
        """Load content generation prompts from configuration file."""
        try:
            # Load prompts from the JSON file
            prompts_file = "/home/runner/workspace/src/config/content_prompts.json"
            with open(prompts_file, 'r', encoding='utf-8') as f:
                self.content_prompts = json.load(f)
            
            logger.info("Content prompts loaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to load content prompts: {str(e)}")
            # Fallback to basic prompts
            self.content_prompts = {
                "content_prompts": {
                    "motivation": {
                        "morning_energy": {
                            "system_prompt": "You are a motivational speaker creating inspiring content.",
                            "user_prompts": ["Create an inspiring message about seizing the day."],
                            "style_guidelines": "Use positive, action-oriented language."
                        }
                    }
                }
            }
    
    def _get_cache_key(self, request: ContentRequest) -> str:
        """Generate a cache key for content request."""
        key_data = f"{request.category.value}_{request.theme}_{request.length}_{request.tone}_{request.language}_{request.energy_level}"
        if request.time_context:
            key_data += f"_{request.time_context.hour}"
        if request.custom_context:
            key_data += f"_{request.custom_context}"
        
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def _is_cache_valid(self, cached_content: GeneratedContent) -> bool:
        """Check if cached content is still valid."""
        cache_duration_hours = self.config.content_generation.content_cache_hours
        time_since_generation = datetime.now() - cached_content.generation_time
        return time_since_generation.total_seconds() < (cache_duration_hours * 3600)
    
    def _select_prompt_template(self, request: ContentRequest) -> Dict[str, Any]:
        """Select appropriate prompt template based on request parameters."""
        try:
            category_prompts = self.content_prompts["content_prompts"].get(
                request.category.value, {}
            )
            
            # Try to find specific theme
            if request.theme and request.theme.value in category_prompts:
                return category_prompts[request.theme.value]
            
            # Fallback to first available theme for category
            if category_prompts:
                first_theme = next(iter(category_prompts.values()))
                return first_theme
            
            # Ultimate fallback
            logger.warning(f"No prompts found for category {request.category}, using fallback")
            return {
                "system_prompt": f"You are an expert in {request.category.value} content creation.",
                "user_prompts": [f"Create inspiring {request.category.value} content."],
                "style_guidelines": "Use clear, positive language appropriate for the theme."
            }
            
        except Exception as e:
            logger.error(f"Error selecting prompt template: {str(e)}")
            return {
                "system_prompt": "You are a content creator.",
                "user_prompts": ["Create inspiring content."],
                "style_guidelines": "Use positive, encouraging language."
            }
    
    def _build_generation_prompt(self, request: ContentRequest, template: Dict[str, Any]) -> Tuple[str, str]:
        """Build system and user prompts for content generation."""
        # Base system prompt
        system_prompt = template["system_prompt"]
        
        # Add style guidelines
        style_guidelines = template.get("style_guidelines", "")
        if style_guidelines:
            system_prompt += f"\n\nStyle Guidelines: {style_guidelines}"
        
        # Add length modifier
        length_modifiers = self.content_prompts.get("prompt_modifiers", {}).get("length", {})
        length_instruction = length_modifiers.get(request.length, "")
        if length_instruction:
            system_prompt += f"\n\nLength: {length_instruction}"
        
        # Add tone modifier
        tone_modifiers = self.content_prompts.get("prompt_modifiers", {}).get("tone", {})
        tone_instruction = tone_modifiers.get(request.tone, "")
        if tone_instruction:
            system_prompt += f"\n\nTone: {tone_instruction}"
        
        # Add language-specific instructions
        language_modifiers = self.content_prompts.get("prompt_modifiers", {}).get("language_specific", {})
        language_instruction = language_modifiers.get(request.language, "")
        if language_instruction:
            system_prompt += f"\n\nLanguage Guidelines: {language_instruction}"
        
        # Cultural context
        if request.language != "en":
            cultural_modifiers = self.content_prompts.get("prompt_modifiers", {}).get("cultural_context", {})
            cultural_instruction = cultural_modifiers.get("eastern" if request.language in ["th", "zh", "ja", "ko"] else "international", "")
            if cultural_instruction:
                system_prompt += f"\n\nCultural Context: {cultural_instruction}"
        
        # Select user prompt
        user_prompts = template.get("user_prompts", ["Create inspiring content."])
        base_user_prompt = random.choice(user_prompts)
        
        # Add time context
        if request.time_context:
            hour = request.time_context.hour
            if 5 <= hour < 12:
                time_context = "morning"
            elif 12 <= hour < 17:
                time_context = "afternoon" 
            elif 17 <= hour < 21:
                time_context = "evening"
            else:
                time_context = "night"
            
            base_user_prompt += f" This content is for {time_context} delivery."
        
        # Add energy level context
        if request.energy_level:
            energy_context = {
                "low": "Create content that is calming and gentle.",
                "medium": "Create content that is balanced and encouraging.", 
                "high": "Create content that is energizing and dynamic."
            }
            energy_instruction = energy_context.get(request.energy_level, "")
            if energy_instruction:
                base_user_prompt += f" {energy_instruction}"
        
        # Add custom context
        if request.custom_context:
            base_user_prompt += f" Additional context: {request.custom_context}"
        
        # Add response format instruction
        base_user_prompt += "\n\nPlease provide your response in this exact JSON format:\n"
        base_user_prompt += '{"title": "Short catchy title", "content": "Main inspirational content"}'
        
        return system_prompt, base_user_prompt
    
    def _validate_generated_content(self, content_dict: Dict[str, str], request: ContentRequest) -> bool:
        """Validate generated content meets requirements."""
        try:
            # Check required fields
            if "title" not in content_dict or "content" not in content_dict:
                logger.error("Generated content missing required fields")
                return False
            
            title = content_dict["title"].strip()
            content = content_dict["content"].strip()
            
            # Check length constraints
            max_title_length = self.config.content_generation.max_title_length
            max_content_length = self.config.content_generation.max_content_length
            
            if len(title) > max_title_length:
                logger.error(f"Title too long: {len(title)} > {max_title_length}")
                return False
            
            if len(content) > max_content_length:
                logger.error(f"Content too long: {len(content)} > {max_content_length}")
                return False
            
            # Check for empty content
            if not title or not content:
                logger.error("Generated content is empty")
                return False
            
            # Content appropriateness checks
            avoid_terms = self.content_prompts.get("content_validation", {}).get("avoid", [])
            content_lower = (title + " " + content).lower()
            
            for term in avoid_terms:
                if term.lower() in content_lower:
                    logger.warning(f"Content contains avoided term: {term}")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Content validation error: {str(e)}")
            return False
    
    def generate_content(self, request: ContentRequest, use_cache: bool = True) -> Optional[GeneratedContent]:
        """
        Generate themed content based on request parameters.
        
        Args:
            request: Content generation request
            use_cache: Whether to use cached content if available
            
        Returns:
            Generated content or None if generation failed
        """
        try:
            # Check cache first
            cache_key = self._get_cache_key(request)
            if use_cache and cache_key in self.content_cache:
                cached_content = self.content_cache[cache_key]
                if self._is_cache_valid(cached_content):
                    logger.debug(f"Using cached content for {request.category}")
                    return cached_content
            
            # Ensure OpenAI service is available
            if not self.openai_service:
                logger.error("OpenAI service not available for content generation")
                return None
            
            # Select prompt template
            template = self._select_prompt_template(request)
            
            # Build prompts
            system_prompt, user_prompt = self._build_generation_prompt(request, template)
            
            logger.info(f"Generating {request.category.value} content with theme {request.theme}")
            
            # Generate content using OpenAI
            ai_response = self.openai_service.get_response(
                user_id="content_generator",
                message=user_prompt,
                system_prompt=system_prompt,
                use_streaming=False
            )
            
            if not ai_response.get('success'):
                logger.error(f"AI content generation failed: {ai_response.get('error')}")
                return None
            
            # Parse response
            ai_content = ai_response.get('message', '').strip()
            
            # Try to parse as JSON
            try:
                if ai_content.startswith('```json'):
                    ai_content = ai_content.split('```json')[1].split('```')[0].strip()
                elif ai_content.startswith('```'):
                    ai_content = ai_content.split('```')[1].split('```')[0].strip()
                
                content_dict = json.loads(ai_content)
            except json.JSONDecodeError:
                logger.warning("Failed to parse JSON response, attempting text extraction")
                # Fallback: try to extract title and content from text
                lines = ai_content.split('\n')
                content_dict = {
                    "title": lines[0][:self.config.content_generation.max_title_length],
                    "content": '\n'.join(lines[1:])[:self.config.content_generation.max_content_length]
                }
            
            # Validate content
            if not self._validate_generated_content(content_dict, request):
                logger.error("Generated content failed validation")
                return None
            
            # Create content object
            generated_content = GeneratedContent(
                title=content_dict["title"].strip(),
                content=content_dict["content"].strip(),
                language=request.language,
                category=request.category,
                theme=request.theme,
                metadata={
                    "generation_model": self.config.content_generation.ai_model,
                    "prompt_template": template,
                    "generation_params": {
                        "length": request.length,
                        "tone": request.tone,
                        "energy_level": request.energy_level,
                        "time_context": request.time_context.strftime("%H:%M") if request.time_context else None
                    },
                    "tokens_used": ai_response.get('tokens_used', 0)
                },
                generation_time=datetime.now()
            )
            
            # Cache the content
            if use_cache:
                self.content_cache[cache_key] = generated_content
            
            logger.info(f"Successfully generated content: '{generated_content.title}'")
            return generated_content
            
        except Exception as e:
            logger.error(f"Content generation error: {str(e)}")
            return None
    
    def generate_daily_content(self, category: ContentCategory, 
                             current_time: Optional[time] = None,
                             language: str = "en") -> Optional[GeneratedContent]:
        """
        Generate content optimized for daily delivery.
        
        Args:
            category: Content category
            current_time: Current time for context
            language: Target language
            
        Returns:
            Generated content optimized for the time of day
        """
        if current_time is None:
            current_time = datetime.now().time()
        
        # Determine theme and energy based on time
        hour = current_time.hour
        
        if 5 <= hour < 12:  # Morning
            theme = ContentTheme.MORNING_ENERGY if category == ContentCategory.MOTIVATION else None
            energy_level = "high"
            tone = "energetic"
        elif 12 <= hour < 17:  # Afternoon
            theme = ContentTheme.GOAL_ACHIEVEMENT if category == ContentCategory.MOTIVATION else None
            energy_level = "medium"
            tone = "professional"
        elif 17 <= hour < 21:  # Evening
            theme = ContentTheme.MINDFULNESS if category == ContentCategory.WELLNESS else None
            energy_level = "medium"
            tone = "calm"
        else:  # Night
            theme = ContentTheme.MINDFULNESS if category == ContentCategory.WELLNESS else None
            energy_level = "low"
            tone = "calm"
        
        request = ContentRequest(
            category=category,
            theme=theme,
            length="medium",
            tone=tone,
            language=language,
            time_context=current_time,
            energy_level=energy_level
        )
        
        return self.generate_content(request)
    
    def generate_content_variations(self, base_request: ContentRequest, 
                                   count: int = 3) -> List[GeneratedContent]:
        """
        Generate multiple variations of content for the same request.
        
        Args:
            base_request: Base content request
            count: Number of variations to generate
            
        Returns:
            List of generated content variations
        """
        variations = []
        
        for i in range(count):
            # Add slight variation to avoid exact caching
            varied_request = ContentRequest(
                category=base_request.category,
                theme=base_request.theme,
                length=base_request.length,
                tone=base_request.tone,
                language=base_request.language,
                time_context=base_request.time_context,
                energy_level=base_request.energy_level,
                custom_context=f"{base_request.custom_context or ''} variation_{i+1}"
            )
            
            content = self.generate_content(varied_request, use_cache=False)
            if content:
                variations.append(content)
        
        return variations
    
    def clear_cache(self) -> None:
        """Clear the content cache."""
        self.content_cache.clear()
        logger.info("Content cache cleared")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get content cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        return {
            "cached_items": len(self.content_cache),
            "cache_enabled": True,
            "total_generations": sum(1 for _ in self.content_cache.values())
        }
    
    def validate_content_quality(self, content: GeneratedContent) -> Dict[str, Any]:
        """
        Validate the quality of generated content.
        
        Args:
            content: Generated content to validate
            
        Returns:
            Validation results with scores and recommendations
        """
        quality_score = 100
        issues = []
        recommendations = []
        
        # Length validation
        title_length = len(content.title)
        content_length = len(content.content)
        
        if title_length < 10:
            quality_score -= 10
            issues.append("Title too short")
            recommendations.append("Consider a more descriptive title")
        
        if content_length < 50:
            quality_score -= 15
            issues.append("Content too brief")
            recommendations.append("Add more inspirational detail")
        
        # Language appropriateness
        required_elements = self.content_prompts.get("content_validation", {}).get("required_elements", [])
        content_text = (content.title + " " + content.content).lower()
        
        for element in required_elements:
            element_check = element.replace("_", " ")
            if element_check not in content_text:
                quality_score -= 5
                issues.append(f"Missing {element}")
        
        # Determine quality level
        if quality_score >= 90:
            quality_level = "excellent"
        elif quality_score >= 75:
            quality_level = "good"
        elif quality_score >= 60:
            quality_level = "acceptable"
        else:
            quality_level = "needs_improvement"
        
        return {
            "quality_score": quality_score,
            "quality_level": quality_level,
            "issues": issues,
            "recommendations": recommendations,
            "content_stats": {
                "title_length": title_length,
                "content_length": content_length,
                "language": content.language,
                "category": content.category.value
            }
        }