"""
Template Selection algorithms for Rich Message automation system.

This module implements intelligent template selection based on content mood,
theme, time of day, user preferences, and seasonal factors.
"""

import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, time
from dataclasses import dataclass
import random
from enum import Enum

from src.models.rich_message_models import RichMessageTemplate, ContentCategory, ContentTheme
from src.utils.template_manager import TemplateManager
from src.utils.content_generator import GeneratedContent, ContentRequest
from src.config.rich_message_config import get_rich_message_config

logger = logging.getLogger(__name__)


class SelectionStrategy(Enum):
    """Template selection strategies"""
    TIME_OPTIMIZED = "time_optimized"
    MOOD_BASED = "mood_based"
    THEME_MATCHING = "theme_matching"
    ENERGY_LEVEL = "energy_level"
    SEASONAL = "seasonal"
    RANDOM_WEIGHTED = "random_weighted"
    USER_PREFERENCE = "user_preference"


@dataclass
class SelectionCriteria:
    """Criteria for template selection"""
    category: ContentCategory
    theme: Optional[ContentTheme] = None
    mood: Optional[str] = None
    energy_level: str = "medium"
    time_context: Optional[time] = None
    season: Optional[str] = None
    user_preferences: Optional[Dict[str, Any]] = None
    language: str = "en"
    strategy: SelectionStrategy = SelectionStrategy.TIME_OPTIMIZED


@dataclass
class TemplateScore:
    """Scoring information for a template"""
    template: RichMessageTemplate
    total_score: float
    score_breakdown: Dict[str, float]
    selection_reason: str


class TemplateSelector:
    """
    Intelligent template selection system.
    
    Provides multiple algorithms for selecting the most appropriate template
    based on various criteria including time, mood, theme, and user preferences.
    """
    
    def __init__(self, template_manager: Optional[TemplateManager] = None, config=None):
        """
        Initialize the TemplateSelector.
        
        Args:
            template_manager: TemplateManager instance
            config: Optional configuration object
        """
        self.config = config or get_rich_message_config()
        self.template_manager = template_manager or TemplateManager(config=self.config)
        
        # Weight configurations for scoring
        self.scoring_weights = {
            "time_match": 3.0,
            "energy_match": 2.5,
            "theme_match": 2.0,
            "mood_match": 2.0,
            "category_match": 4.0,
            "seasonal_match": 1.5,
            "text_area_quality": 1.0,
            "user_preference": 3.5,
            "novelty": 1.0
        }
        
        # Recent selections for novelty tracking
        self.recent_selections: List[str] = []
        self.max_recent_history = 10
    
    def _get_current_season(self) -> str:
        """
        Determine current season based on month.
        
        Returns:
            Season name ("spring", "summer", "autumn", "winter")
        """
        month = datetime.now().month
        
        if month in [3, 4, 5]:
            return "spring"
        elif month in [6, 7, 8]:
            return "summer"
        elif month in [9, 10, 11]:
            return "autumn"
        else:
            return "winter"
    
    def _calculate_time_score(self, template: RichMessageTemplate, 
                            target_time: Optional[time]) -> float:
        """
        Calculate time-based scoring for a template.
        
        Args:
            template: Template to score
            target_time: Target time for delivery
            
        Returns:
            Score between 0.0 and 1.0
        """
        if not target_time or not template.preferred_times:
            return 0.5  # Neutral score
        
        target_hour = target_time.hour
        
        # Convert preferred times to hours
        preferred_hours = []
        for time_str in template.preferred_times:
            try:
                hour = int(time_str.split(':')[0])
                preferred_hours.append(hour)
            except (ValueError, IndexError):
                continue
        
        if not preferred_hours:
            return 0.5
        
        # Find closest preferred time
        min_distance = min(abs(target_hour - hour) for hour in preferred_hours)
        
        # Score inversely proportional to distance (closer = higher score)
        if min_distance == 0:
            return 1.0
        elif min_distance <= 2:
            return 0.8
        elif min_distance <= 4:
            return 0.6
        elif min_distance <= 6:
            return 0.4
        else:
            return 0.2
    
    def _calculate_energy_score(self, template: RichMessageTemplate, 
                              target_energy: str) -> float:
        """
        Calculate energy level matching score.
        
        Args:
            template: Template to score
            target_energy: Target energy level ("low", "medium", "high")
            
        Returns:
            Score between 0.0 and 1.0
        """
        if not hasattr(template, 'energy_level') or not template.energy_level:
            return 0.5
        
        energy_mapping = {"low": 1, "medium": 2, "high": 3}
        template_energy = energy_mapping.get(template.energy_level, 2)
        target_energy_val = energy_mapping.get(target_energy, 2)
        
        # Perfect match gets full score
        if template_energy == target_energy_val:
            return 1.0
        
        # Adjacent levels get partial score
        distance = abs(template_energy - target_energy_val)
        if distance == 1:
            return 0.7
        else:
            return 0.3
    
    def _calculate_theme_score(self, template: RichMessageTemplate, 
                             target_theme: Optional[ContentTheme]) -> float:
        """
        Calculate theme matching score.
        
        Args:
            template: Template to score
            target_theme: Target theme
            
        Returns:
            Score between 0.0 and 1.0
        """
        if not target_theme:
            return 0.5
        
        template_theme = getattr(template, 'theme', None)
        if not template_theme:
            return 0.5
        
        # Direct theme match
        if template_theme == target_theme.value:
            return 1.0
        
        # Partial theme matching based on semantic similarity
        theme_similarities = {
            ContentTheme.MORNING_ENERGY: ["energetic", "dynamic", "active"],
            ContentTheme.GOAL_ACHIEVEMENT: ["success", "achievement", "progress"],
            ContentTheme.CREATIVITY: ["creative", "artistic", "innovative"],
            ContentTheme.PERSONAL_GROWTH: ["growth", "development", "improvement"],
            ContentTheme.MINDFULNESS: ["calm", "peaceful", "serene"],
            ContentTheme.HEALTHY_LIVING: ["health", "wellness", "vitality"]
        }
        
        target_keywords = theme_similarities.get(target_theme, [])
        if any(keyword in template_theme.lower() for keyword in target_keywords):
            return 0.7
        
        return 0.3
    
    def _calculate_mood_score(self, template: RichMessageTemplate, 
                            target_mood: Optional[str]) -> float:
        """
        Calculate mood matching score.
        
        Args:
            template: Template to score
            target_mood: Target mood
            
        Returns:
            Score between 0.0 and 1.0
        """
        if not target_mood:
            return 0.5
        
        template_mood = getattr(template, 'mood', None)
        if not template_mood:
            return 0.5
        
        # Direct mood match
        if template_mood.lower() == target_mood.lower():
            return 1.0
        
        # Mood similarity mapping
        mood_groups = {
            "energetic": ["dynamic", "active", "vibrant", "powerful"],
            "calm": ["peaceful", "serene", "tranquil", "relaxed"],
            "inspiring": ["uplifting", "motivational", "encouraging"],
            "professional": ["formal", "business", "corporate"],
            "creative": ["artistic", "innovative", "imaginative"],
            "warm": ["friendly", "welcoming", "cozy"]
        }
        
        # Check if moods are in the same group
        for group_mood, similar_moods in mood_groups.items():
            if (target_mood.lower() in [group_mood] + similar_moods and
                template_mood.lower() in [group_mood] + similar_moods):
                return 0.8
        
        return 0.3
    
    def _calculate_seasonal_score(self, template: RichMessageTemplate, 
                                target_season: Optional[str]) -> float:
        """
        Calculate seasonal appropriateness score.
        
        Args:
            template: Template to score
            target_season: Target season
            
        Returns:
            Score between 0.0 and 1.0
        """
        if not target_season:
            return 0.5
        
        # Check template tags for seasonal indicators
        template_tags = getattr(template, 'tags', [])
        if not template_tags:
            return 0.5
        
        seasonal_keywords = {
            "spring": ["spring", "bloom", "fresh", "new", "growth"],
            "summer": ["summer", "bright", "sunny", "energy", "vibrant"],
            "autumn": ["autumn", "fall", "warm", "cozy", "reflection"],
            "winter": ["winter", "calm", "peaceful", "quiet", "contemplation"]
        }
        
        target_keywords = seasonal_keywords.get(target_season, [])
        tag_text = " ".join(template_tags).lower()
        
        matches = sum(1 for keyword in target_keywords if keyword in tag_text)
        
        if matches > 0:
            return min(1.0, 0.5 + (matches * 0.2))
        
        return 0.5
    
    def _calculate_text_area_score(self, template: RichMessageTemplate) -> float:
        """
        Calculate text area quality score.
        
        Args:
            template: Template to score
            
        Returns:
            Score between 0.0 and 1.0
        """
        text_areas = getattr(template, 'text_areas', [])
        
        if not text_areas:
            return 0.2  # Low score for no text areas
        
        score = 0.0
        
        # Number of text areas (more is better, up to a point)
        area_count_score = min(1.0, len(text_areas) * 0.4)
        score += area_count_score * 0.3
        
        # Text area size and positioning quality
        for area in text_areas:
            # Prefer larger areas
            area_size = area.width * area.height
            size_score = min(1.0, area_size / (300 * 100))  # Normalize to reasonable size
            score += size_score * 0.4
            
            # Prefer areas with good positioning (not too close to edges)
            if hasattr(area, 'x') and hasattr(area, 'y'):
                # Simple heuristic: prefer areas not too close to edges
                position_score = 0.8 if area.x > 50 and area.y > 50 else 0.5
                score += position_score * 0.3
        
        return min(1.0, score / len(text_areas))
    
    def _calculate_novelty_score(self, template: RichMessageTemplate) -> float:
        """
        Calculate novelty score based on recent usage.
        
        Args:
            template: Template to score
            
        Returns:
            Score between 0.0 and 1.0
        """
        if template.template_id not in self.recent_selections:
            return 1.0  # Maximum novelty for unused templates
        
        # Reduce score based on how recently it was used
        recent_index = self.recent_selections.index(template.template_id)
        recency = len(self.recent_selections) - recent_index
        
        # More recent usage = lower novelty score
        return max(0.1, 1.0 - (recency / len(self.recent_selections)) * 0.8)
    
    def _calculate_user_preference_score(self, template: RichMessageTemplate,
                                       user_preferences: Optional[Dict[str, Any]]) -> float:
        """
        Calculate user preference score.
        
        Args:
            template: Template to score
            user_preferences: User preference data
            
        Returns:
            Score between 0.0 and 1.0
        """
        if not user_preferences:
            return 0.5
        
        score = 0.5  # Base score
        
        # Preferred categories
        preferred_categories = user_preferences.get('preferred_categories', [])
        if template.category.value in preferred_categories:
            score += 0.3
        
        # Preferred themes
        preferred_themes = user_preferences.get('preferred_themes', [])
        template_theme = getattr(template, 'theme', None)
        if template_theme and template_theme in preferred_themes:
            score += 0.2
        
        # Preferred times
        preferred_times = user_preferences.get('preferred_times', [])
        template_times = getattr(template, 'preferred_times', [])
        if any(time in preferred_times for time in template_times):
            score += 0.2
        
        # Disliked templates
        disliked_templates = user_preferences.get('disliked_templates', [])
        if template.template_id in disliked_templates:
            score -= 0.5
        
        return max(0.0, min(1.0, score))
    
    def score_template(self, template: RichMessageTemplate, 
                      criteria: SelectionCriteria) -> TemplateScore:
        """
        Calculate comprehensive score for a template.
        
        Args:
            template: Template to score
            criteria: Selection criteria
            
        Returns:
            TemplateScore with detailed scoring information
        """
        scores = {}
        
        # Category match (mandatory)
        if template.category != criteria.category:
            return TemplateScore(
                template=template,
                total_score=0.0,
                score_breakdown={"category_mismatch": 0.0},
                selection_reason="Category mismatch"
            )
        
        scores["category_match"] = 1.0
        
        # Calculate individual scores
        scores["time_match"] = self._calculate_time_score(template, criteria.time_context)
        scores["energy_match"] = self._calculate_energy_score(template, criteria.energy_level)
        scores["theme_match"] = self._calculate_theme_score(template, criteria.theme)
        scores["mood_match"] = self._calculate_mood_score(template, criteria.mood)
        scores["seasonal_match"] = self._calculate_seasonal_score(template, criteria.season)
        scores["text_area_quality"] = self._calculate_text_area_score(template)
        scores["novelty"] = self._calculate_novelty_score(template)
        scores["user_preference"] = self._calculate_user_preference_score(
            template, criteria.user_preferences
        )
        
        # Calculate weighted total score
        total_score = 0.0
        for score_type, score_value in scores.items():
            weight = self.scoring_weights.get(score_type, 1.0)
            total_score += score_value * weight
        
        # Normalize by total possible score
        max_possible_score = sum(self.scoring_weights.values())
        normalized_score = total_score / max_possible_score
        
        # Generate selection reason
        best_aspects = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:3]
        selection_reason = f"High scores in: {', '.join([aspect.replace('_', ' ') for aspect, _ in best_aspects])}"
        
        return TemplateScore(
            template=template,
            total_score=normalized_score,
            score_breakdown=scores,
            selection_reason=selection_reason
        )
    
    def select_template(self, criteria: SelectionCriteria) -> Optional[RichMessageTemplate]:
        """
        Select the best template based on criteria.
        
        Args:
            criteria: Selection criteria
            
        Returns:
            Selected template or None if no suitable template found
        """
        # Get all templates for the category
        available_templates = self.template_manager.get_templates_by_category(criteria.category)
        
        if not available_templates:
            logger.warning(f"No templates found for category: {criteria.category}")
            return None
        
        # Score all templates
        scored_templates = []
        for template in available_templates:
            score_result = self.score_template(template, criteria)
            if score_result.total_score > 0:  # Only consider valid templates
                scored_templates.append(score_result)
        
        if not scored_templates:
            logger.warning("No templates passed scoring criteria")
            return None
        
        # Select based on strategy
        selected_template = self._apply_selection_strategy(scored_templates, criteria.strategy)
        
        if selected_template:
            # Track selection for novelty
            self._track_selection(selected_template.template_id)
            logger.info(f"Selected template {selected_template.template_id}: {selected_template.selection_reason}")
        
        return selected_template
    
    def _apply_selection_strategy(self, scored_templates: List[TemplateScore], 
                                strategy: SelectionStrategy) -> Optional[RichMessageTemplate]:
        """
        Apply selection strategy to choose from scored templates.
        
        Args:
            scored_templates: List of scored templates
            strategy: Selection strategy to apply
            
        Returns:
            Selected template or None
        """
        if strategy == SelectionStrategy.TIME_OPTIMIZED:
            # Prefer templates with high time match scores
            best = max(scored_templates, 
                      key=lambda x: x.score_breakdown.get("time_match", 0) + x.total_score * 0.5)
            return best.template
        
        elif strategy == SelectionStrategy.MOOD_BASED:
            # Prefer templates with high mood match scores
            best = max(scored_templates,
                      key=lambda x: x.score_breakdown.get("mood_match", 0) + x.total_score * 0.5)
            return best.template
        
        elif strategy == SelectionStrategy.ENERGY_LEVEL:
            # Prefer templates with high energy match scores
            best = max(scored_templates,
                      key=lambda x: x.score_breakdown.get("energy_match", 0) + x.total_score * 0.5)
            return best.template
        
        elif strategy == SelectionStrategy.RANDOM_WEIGHTED:
            # Weighted random selection based on scores
            weights = [score.total_score for score in scored_templates]
            if sum(weights) > 0:
                selected = random.choices(scored_templates, weights=weights)[0]
                return selected.template
        
        elif strategy == SelectionStrategy.USER_PREFERENCE:
            # Prefer templates with high user preference scores
            best = max(scored_templates,
                      key=lambda x: x.score_breakdown.get("user_preference", 0) + x.total_score * 0.3)
            return best.template
        
        else:  # Default: highest total score
            best = max(scored_templates, key=lambda x: x.total_score)
            return best.template
        
        return None
    
    def _track_selection(self, template_id: str) -> None:
        """
        Track template selection for novelty calculation.
        
        Args:
            template_id: ID of selected template
        """
        if template_id in self.recent_selections:
            self.recent_selections.remove(template_id)
        
        self.recent_selections.append(template_id)
        
        # Keep only recent history
        if len(self.recent_selections) > self.max_recent_history:
            self.recent_selections.pop(0)
    
    def get_template_recommendations(self, criteria: SelectionCriteria, 
                                   count: int = 3) -> List[TemplateScore]:
        """
        Get multiple template recommendations with scores.
        
        Args:
            criteria: Selection criteria
            count: Number of recommendations to return
            
        Returns:
            List of top scored templates
        """
        available_templates = self.template_manager.get_templates_by_category(criteria.category)
        
        if not available_templates:
            return []
        
        # Score all templates
        scored_templates = []
        for template in available_templates:
            score_result = self.score_template(template, criteria)
            if score_result.total_score > 0:
                scored_templates.append(score_result)
        
        # Return top N
        scored_templates.sort(key=lambda x: x.total_score, reverse=True)
        return scored_templates[:count]
    
    def clear_selection_history(self) -> None:
        """Clear the selection history for novelty tracking."""
        self.recent_selections.clear()
        logger.info("Selection history cleared")
    
    def get_selection_stats(self) -> Dict[str, Any]:
        """
        Get selection statistics.
        
        Returns:
            Dictionary with selection statistics
        """
        return {
            "recent_selections": len(self.recent_selections),
            "max_history_size": self.max_recent_history,
            "scoring_weights": self.scoring_weights,
            "available_strategies": [strategy.value for strategy in SelectionStrategy]
        }