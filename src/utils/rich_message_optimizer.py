"""
Rich Message optimization utilities for enhanced performance and engagement.

This module provides advanced optimization capabilities for Rich Message
delivery, template selection, content generation, and user engagement analytics.
"""

import logging
import time
import json
import hashlib
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

from src.utils.redis_cache import redis_cache, cache_result
from src.utils.performance_monitor import monitored_operation, measure_performance

logger = logging.getLogger(__name__)


class OptimizationStrategy(Enum):
    """Optimization strategies for Rich Message delivery."""
    PERFORMANCE = "performance"
    ENGAGEMENT = "engagement" 
    DELIVERY_SUCCESS = "delivery_success"
    USER_PREFERENCE = "user_preference"


@dataclass
class RichMessageMetrics:
    """Metrics for Rich Message performance analysis."""
    template_id: str
    user_id: str
    generation_time_ms: float
    delivery_time_ms: float
    engagement_score: float
    user_interaction: bool
    delivery_success: bool
    content_quality_score: float
    timestamp: datetime


class RichMessageOptimizer:
    """Advanced optimizer for Rich Message system performance."""
    
    def __init__(self, cache_ttl: int = 3600):
        """
        Initialize Rich Message optimizer.
        
        Args:
            cache_ttl: Cache time-to-live in seconds
        """
        self.cache_ttl = cache_ttl
        self.cache = redis_cache
        self.metrics_history = []
        self.optimization_rules = self._initialize_optimization_rules()
    
    def _initialize_optimization_rules(self) -> Dict[str, Any]:
        """Initialize optimization rules and thresholds."""
        return {
            'template_selection': {
                'engagement_threshold': 0.7,
                'performance_threshold_ms': 200,
                'cache_duration': 1800  # 30 minutes
            },
            'content_generation': {
                'quality_threshold': 0.8,
                'generation_timeout_ms': 5000,
                'retry_attempts': 3
            },
            'delivery_optimization': {
                'batch_size': 50,
                'delivery_window_hours': 2,
                'retry_delay_minutes': 15
            },
            'user_engagement': {
                'interaction_window_minutes': 30,
                'engagement_scoring_weights': {
                    'click_rate': 0.4,
                    'response_time': 0.3,
                    'interaction_depth': 0.3
                }
            }
        }
    
    @monitored_operation("template_optimization")
    def optimize_template_selection(self, content_category: str, user_preferences: Dict[str, Any],
                                  time_of_day: str, optimization_strategy: OptimizationStrategy = OptimizationStrategy.ENGAGEMENT) -> Dict[str, Any]:
        """
        Optimize template selection based on multiple factors.
        
        Args:
            content_category: Category of content (motivation, wellness, etc.)
            user_preferences: User preference data
            time_of_day: Time of day for delivery
            optimization_strategy: Optimization strategy to use
            
        Returns:
            Optimized template selection with confidence score
        """
        cache_key = f"template_opt_{content_category}_{time_of_day}_{optimization_strategy.value}"
        
        # Try cache first
        cached_result = self.cache.get(cache_key, "template_optimization")
        if cached_result:
            logger.debug(f"Template optimization cache hit for {cache_key}")
            return cached_result
        
        with measure_performance("template_selection_optimization"):
            # Get template performance data
            template_metrics = self._get_template_performance_metrics(content_category)
            
            # Apply optimization strategy
            if optimization_strategy == OptimizationStrategy.ENGAGEMENT:
                optimized_template = self._optimize_for_engagement(template_metrics, user_preferences)
            elif optimization_strategy == OptimizationStrategy.PERFORMANCE:
                optimized_template = self._optimize_for_performance(template_metrics)
            elif optimization_strategy == OptimizationStrategy.USER_PREFERENCE:
                optimized_template = self._optimize_for_user_preference(template_metrics, user_preferences)
            else:
                optimized_template = self._optimize_for_delivery_success(template_metrics)
            
            # Add time-based optimization
            time_optimized = self._apply_time_based_optimization(optimized_template, time_of_day)
            
            # Calculate confidence score
            confidence_score = self._calculate_optimization_confidence(time_optimized, template_metrics)
            
            result = {
                'template_id': time_optimized['template_id'],
                'template_metadata': time_optimized,
                'optimization_strategy': optimization_strategy.value,
                'confidence_score': confidence_score,
                'optimization_factors': {
                    'engagement_score': time_optimized.get('engagement_score', 0),
                    'performance_score': time_optimized.get('performance_score', 0),
                    'user_preference_match': time_optimized.get('user_preference_match', 0),
                    'time_optimization_bonus': time_optimized.get('time_bonus', 0)
                },
                'cache_timestamp': time.time()
            }
            
            # Cache result
            self.cache.set(cache_key, result, self.cache_ttl, "template_optimization")
            
            return result
    
    def _get_template_performance_metrics(self, category: str) -> List[Dict[str, Any]]:
        """Get historical performance metrics for templates in category."""
        cache_key = f"template_metrics_{category}"
        
        cached_metrics = self.cache.get(cache_key, "template_metrics")
        if cached_metrics:
            return cached_metrics
        
        # Simulate template performance data (replace with actual analytics)
        templates = [
            {
                'template_id': f'{category}_template_01',
                'engagement_score': 0.85,
                'performance_score': 0.90,
                'delivery_success_rate': 0.95,
                'avg_generation_time_ms': 150,
                'user_interaction_rate': 0.75,
                'content_quality_score': 0.88
            },
            {
                'template_id': f'{category}_template_02',
                'engagement_score': 0.78,
                'performance_score': 0.85,
                'delivery_success_rate': 0.92,
                'avg_generation_time_ms': 180,
                'user_interaction_rate': 0.68,
                'content_quality_score': 0.82
            },
            {
                'template_id': f'{category}_template_03',
                'engagement_score': 0.92,
                'performance_score': 0.88,
                'delivery_success_rate': 0.97,
                'avg_generation_time_ms': 120,
                'user_interaction_rate': 0.89,
                'content_quality_score': 0.91
            }
        ]
        
        # Cache for 30 minutes
        self.cache.set(cache_key, templates, 1800, "template_metrics")
        return templates
    
    def _optimize_for_engagement(self, templates: List[Dict[str, Any]], 
                                user_preferences: Dict[str, Any]) -> Dict[str, Any]:
        """Optimize template selection for maximum user engagement."""
        weighted_scores = []
        
        for template in templates:
            # Calculate weighted engagement score
            engagement_weight = 0.5
            interaction_weight = 0.3
            quality_weight = 0.2
            
            score = (
                template['engagement_score'] * engagement_weight +
                template['user_interaction_rate'] * interaction_weight +
                template['content_quality_score'] * quality_weight
            )
            
            # Apply user preference bonus
            preference_bonus = self._calculate_user_preference_bonus(template, user_preferences)
            final_score = score + preference_bonus
            
            weighted_scores.append((final_score, template))
        
        # Return highest scoring template
        best_template = max(weighted_scores, key=lambda x: x[0])[1]
        best_template['optimization_score'] = max(weighted_scores, key=lambda x: x[0])[0]
        
        return best_template
    
    def _optimize_for_performance(self, templates: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Optimize template selection for maximum performance."""
        performance_scores = []
        
        for template in templates:
            # Calculate performance score (lower generation time = higher score)
            time_score = max(0, 1 - (template['avg_generation_time_ms'] / 1000))
            delivery_score = template['delivery_success_rate']
            performance_score = template['performance_score']
            
            final_score = (time_score * 0.4 + delivery_score * 0.3 + performance_score * 0.3)
            performance_scores.append((final_score, template))
        
        best_template = max(performance_scores, key=lambda x: x[0])[1]
        best_template['optimization_score'] = max(performance_scores, key=lambda x: x[0])[0]
        
        return best_template
    
    def _optimize_for_user_preference(self, templates: List[Dict[str, Any]], 
                                    user_preferences: Dict[str, Any]) -> Dict[str, Any]:
        """Optimize template selection based on user preferences."""
        preference_scores = []
        
        for template in templates:
            preference_match = self._calculate_user_preference_bonus(template, user_preferences)
            base_quality = template['content_quality_score'] * 0.5
            engagement_factor = template['engagement_score'] * 0.3
            
            final_score = preference_match + base_quality + engagement_factor
            preference_scores.append((final_score, template))
        
        best_template = max(preference_scores, key=lambda x: x[0])[1]
        best_template['optimization_score'] = max(preference_scores, key=lambda x: x[0])[0]
        
        return best_template
    
    def _optimize_for_delivery_success(self, templates: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Optimize template selection for maximum delivery success."""
        delivery_scores = []
        
        for template in templates:
            delivery_rate = template['delivery_success_rate']
            performance_factor = template['performance_score'] * 0.3
            reliability_score = min(1.0, template['avg_generation_time_ms'] / 500) * 0.2
            
            final_score = delivery_rate * 0.5 + performance_factor + reliability_score
            delivery_scores.append((final_score, template))
        
        best_template = max(delivery_scores, key=lambda x: x[0])[1]
        best_template['optimization_score'] = max(delivery_scores, key=lambda x: x[0])[0]
        
        return best_template
    
    def _apply_time_based_optimization(self, template: Dict[str, Any], 
                                     time_of_day: str) -> Dict[str, Any]:
        """Apply time-based optimization to template selection."""
        time_bonuses = {
            'morning': {'energy': 0.1, 'motivation': 0.15, 'productivity': 0.1},
            'afternoon': {'productivity': 0.15, 'focus': 0.1, 'motivation': 0.05},
            'evening': {'wellness': 0.15, 'relaxation': 0.1, 'reflection': 0.1},
            'night': {'wellness': 0.1, 'mindfulness': 0.15, 'rest': 0.1}
        }
        
        template_copy = template.copy()
        
        # Apply time-specific bonuses
        if time_of_day in time_bonuses:
            for theme, bonus in time_bonuses[time_of_day].items():
                if theme in template_copy.get('themes', []):
                    template_copy['time_bonus'] = template_copy.get('time_bonus', 0) + bonus
        
        return template_copy
    
    def _calculate_user_preference_bonus(self, template: Dict[str, Any], 
                                       user_preferences: Dict[str, Any]) -> float:
        """Calculate user preference bonus for template."""
        if not user_preferences:
            return 0.0
        
        bonus = 0.0
        
        # Theme preferences
        preferred_themes = user_preferences.get('themes', [])
        template_themes = template.get('themes', [])
        
        theme_matches = len(set(preferred_themes) & set(template_themes))
        if theme_matches > 0:
            bonus += min(0.2, theme_matches * 0.1)
        
        # Style preferences
        preferred_style = user_preferences.get('style', '')
        template_style = template.get('style', '')
        
        if preferred_style and preferred_style == template_style:
            bonus += 0.15
        
        # Historical interaction bonus
        interaction_history = user_preferences.get('template_interactions', {})
        template_id = template.get('template_id', '')
        
        if template_id in interaction_history:
            interaction_rate = interaction_history[template_id].get('interaction_rate', 0)
            bonus += min(0.1, interaction_rate)
        
        return bonus
    
    def _calculate_optimization_confidence(self, template: Dict[str, Any], 
                                         all_templates: List[Dict[str, Any]]) -> float:
        """Calculate confidence score for optimization decision."""
        if not all_templates:
            return 0.5
        
        # Calculate score variance
        scores = [t.get('optimization_score', 0) for t in all_templates]
        if not scores:
            return 0.5
        
        best_score = template.get('optimization_score', 0)
        avg_score = sum(scores) / len(scores)
        max_score = max(scores)
        
        if max_score == avg_score:
            return 0.5
        
        # Higher confidence when chosen template significantly outperforms average
        confidence = min(1.0, (best_score - avg_score) / (max_score - avg_score))
        
        # Boost confidence for templates with high base metrics
        base_quality = template.get('content_quality_score', 0)
        delivery_success = template.get('delivery_success_rate', 0)
        
        quality_bonus = (base_quality + delivery_success) / 2 * 0.2
        final_confidence = min(1.0, confidence + quality_bonus)
        
        return round(final_confidence, 3)
    
    @monitored_operation("content_generation_optimization")
    @cache_result(ttl=1800, prefix="content_optimization")
    def optimize_content_generation(self, content_category: str, user_context: Dict[str, Any],
                                  quality_threshold: float = 0.8) -> Dict[str, Any]:
        """
        Optimize content generation for better quality and relevance.
        
        Args:
            content_category: Category of content to generate
            user_context: User context and preferences
            quality_threshold: Minimum quality threshold
            
        Returns:
            Optimized content generation parameters
        """
        with measure_performance("content_generation_optimization"):
            # Analyze user context for content optimization
            context_analysis = self._analyze_user_context(user_context)
            
            # Generate optimized prompts
            optimized_prompts = self._optimize_content_prompts(
                content_category, context_analysis, quality_threshold
            )
            
            # Calculate content parameters
            content_params = self._calculate_optimal_content_params(
                content_category, context_analysis
            )
            
            return {
                'prompts': optimized_prompts,
                'parameters': content_params,
                'context_analysis': context_analysis,
                'optimization_timestamp': time.time(),
                'quality_threshold': quality_threshold
            }
    
    def _analyze_user_context(self, user_context: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze user context for content optimization."""
        analysis = {
            'engagement_level': 'medium',
            'content_preferences': [],
            'interaction_patterns': {},
            'optimal_content_length': 'medium',
            'preferred_tone': 'friendly'
        }
        
        # Analyze historical interactions
        if 'message_history' in user_context:
            history = user_context['message_history']
            
            # Determine engagement level
            if len(history) > 10:
                analysis['engagement_level'] = 'high'
            elif len(history) < 3:
                analysis['engagement_level'] = 'low'
        
        # Analyze content preferences from interactions
        if 'interaction_data' in user_context:
            interactions = user_context['interaction_data']
            
            # Extract preferred content themes
            theme_counts = {}
            for interaction in interactions:
                themes = interaction.get('themes', [])
                for theme in themes:
                    theme_counts[theme] = theme_counts.get(theme, 0) + 1
            
            # Get top themes
            if theme_counts:
                analysis['content_preferences'] = [
                    theme for theme, _ in sorted(theme_counts.items(), 
                                               key=lambda x: x[1], reverse=True)[:3]
                ]
        
        return analysis
    
    def _optimize_content_prompts(self, category: str, context_analysis: Dict[str, Any],
                                quality_threshold: float) -> Dict[str, Any]:
        """Generate optimized prompts for content generation."""
        base_prompts = {
            'motivation': "Create an inspiring and motivational message that encourages action and positive thinking.",
            'wellness': "Generate a wellness-focused message promoting self-care and mental health.",
            'productivity': "Create a productivity tip that helps users focus and achieve their goals.",
            'inspiration': "Generate an inspirational message that uplifts and motivates the reader."
        }
        
        # Get base prompt
        base_prompt = base_prompts.get(category, base_prompts['motivation'])
        
        # Enhance with user context
        engagement_level = context_analysis.get('engagement_level', 'medium')
        preferences = context_analysis.get('content_preferences', [])
        tone = context_analysis.get('preferred_tone', 'friendly')
        
        # Build enhanced prompt
        enhanced_prompt = base_prompt
        
        if preferences:
            enhanced_prompt += f" Focus on themes related to: {', '.join(preferences)}."
        
        enhanced_prompt += f" Use a {tone} tone and target {engagement_level} engagement level."
        
        if quality_threshold > 0.8:
            enhanced_prompt += " Ensure high quality, originality, and emotional resonance."
        
        return {
            'primary_prompt': enhanced_prompt,
            'category': category,
            'context_enhanced': True,
            'quality_optimized': quality_threshold > 0.8
        }
    
    def _calculate_optimal_content_params(self, category: str, 
                                        context_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate optimal parameters for content generation."""
        # Base parameters by category
        category_params = {
            'motivation': {'temperature': 0.8, 'max_length': 150, 'creativity': 0.7},
            'wellness': {'temperature': 0.6, 'max_length': 180, 'creativity': 0.5},
            'productivity': {'temperature': 0.5, 'max_length': 120, 'creativity': 0.4},
            'inspiration': {'temperature': 0.9, 'max_length': 160, 'creativity': 0.8}
        }
        
        params = category_params.get(category, category_params['motivation']).copy()
        
        # Adjust based on engagement level
        engagement_level = context_analysis.get('engagement_level', 'medium')
        
        if engagement_level == 'high':
            params['temperature'] += 0.1
            params['creativity'] += 0.1
            params['max_length'] += 20
        elif engagement_level == 'low':
            params['temperature'] -= 0.1
            params['creativity'] -= 0.1
            params['max_length'] -= 20
        
        # Ensure valid ranges
        params['temperature'] = max(0.1, min(1.0, params['temperature']))
        params['creativity'] = max(0.1, min(1.0, params['creativity']))
        params['max_length'] = max(50, min(200, params['max_length']))
        
        return params
    
    def get_optimization_metrics(self) -> Dict[str, Any]:
        """Get comprehensive optimization metrics."""
        return {
            'cache_stats': self.cache.get_stats(),
            'optimization_rules': self.optimization_rules,
            'metrics_count': len(self.metrics_history),
            'performance_summary': self._calculate_performance_summary()
        }
    
    def _calculate_performance_summary(self) -> Dict[str, Any]:
        """Calculate performance summary from metrics history."""
        if not self.metrics_history:
            return {}
        
        recent_metrics = [m for m in self.metrics_history 
                         if (datetime.now() - m.timestamp).seconds < 3600]
        
        if not recent_metrics:
            return {}
        
        return {
            'avg_generation_time_ms': sum(m.generation_time_ms for m in recent_metrics) / len(recent_metrics),
            'avg_delivery_time_ms': sum(m.delivery_time_ms for m in recent_metrics) / len(recent_metrics),
            'avg_engagement_score': sum(m.engagement_score for m in recent_metrics) / len(recent_metrics),
            'delivery_success_rate': sum(1 for m in recent_metrics if m.delivery_success) / len(recent_metrics),
            'user_interaction_rate': sum(1 for m in recent_metrics if m.user_interaction) / len(recent_metrics),
            'sample_size': len(recent_metrics)
        }


# Global Rich Message optimizer instance
rich_message_optimizer = RichMessageOptimizer()