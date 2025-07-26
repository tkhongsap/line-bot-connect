"""
Unit tests for TemplateSelector
"""

import pytest
from unittest.mock import Mock, patch
from datetime import time
from src.utils.template_selector import TemplateSelector, SelectionCriteria, TemplateScore, SelectionStrategy
from src.models.rich_message_models import RichMessageTemplate, ContentCategory, ContentTheme, TextArea


class TestTemplateSelector:
    """Test cases for TemplateSelector"""
    
    @pytest.fixture
    def mock_config(self):
        """Create a mock configuration"""
        return Mock()
    
    @pytest.fixture
    def mock_template_manager(self):
        """Create a mock template manager"""
        manager = Mock()
        return manager
    
    @pytest.fixture
    def sample_templates(self):
        """Create sample templates for testing"""
        templates = [
            RichMessageTemplate(
                template_id="morning_motivation",
                category=ContentCategory.MOTIVATION,
                filename="morning.png",
                theme="morning_energy",
                mood="energetic",
                preferred_times=["07:00", "08:00", "09:00"],
                energy_level="high",
                text_areas=[
                    TextArea(x=100, y=200, width=300, height=100, alignment="center")
                ],
                tags=["morning", "energy", "dynamic"]
            ),
            RichMessageTemplate(
                template_id="evening_calm",
                category=ContentCategory.WELLNESS,
                filename="evening.png",
                theme="mindfulness",
                mood="calm",
                preferred_times=["18:00", "19:00", "20:00"],
                energy_level="low",
                text_areas=[
                    TextArea(x=50, y=300, width=400, height=150, alignment="center")
                ],
                tags=["evening", "peaceful", "serene"]
            ),
            RichMessageTemplate(
                template_id="productivity_focus",
                category=ContentCategory.PRODUCTIVITY,
                filename="focus.png",
                theme="focus",
                mood="professional",
                preferred_times=["10:00", "14:00", "16:00"],
                energy_level="medium",
                text_areas=[
                    TextArea(x=75, y=250, width=350, height=120, alignment="left")
                ],
                tags=["work", "focus", "professional"]
            )
        ]
        return templates
    
    @pytest.fixture
    def template_selector(self, mock_template_manager, mock_config):
        """Create a TemplateSelector instance"""
        with patch('src.utils.template_selector.get_rich_message_config', return_value=mock_config):
            selector = TemplateSelector(template_manager=mock_template_manager, config=mock_config)
            return selector
    
    def test_initialization(self, template_selector, mock_template_manager, mock_config):
        """Test TemplateSelector initialization"""
        assert template_selector.config == mock_config
        assert template_selector.template_manager == mock_template_manager
        assert isinstance(template_selector.scoring_weights, dict)
        assert template_selector.recent_selections == []
    
    def test_get_current_season_spring(self, template_selector):
        """Test season detection for spring"""
        with patch('src.utils.template_selector.datetime') as mock_datetime:
            mock_datetime.now.return_value.month = 4  # April
            season = template_selector._get_current_season()
            assert season == "spring"
    
    def test_get_current_season_summer(self, template_selector):
        """Test season detection for summer"""
        with patch('src.utils.template_selector.datetime') as mock_datetime:
            mock_datetime.now.return_value.month = 7  # July
            season = template_selector._get_current_season()
            assert season == "summer"
    
    def test_get_current_season_autumn(self, template_selector):
        """Test season detection for autumn"""
        with patch('src.utils.template_selector.datetime') as mock_datetime:
            mock_datetime.now.return_value.month = 10  # October
            season = template_selector._get_current_season()
            assert season == "autumn"
    
    def test_get_current_season_winter(self, template_selector):
        """Test season detection for winter"""
        with patch('src.utils.template_selector.datetime') as mock_datetime:
            mock_datetime.now.return_value.month = 1  # January
            season = template_selector._get_current_season()
            assert season == "winter"
    
    def test_calculate_time_score_perfect_match(self, template_selector, sample_templates):
        """Test time score calculation with perfect match"""
        template = sample_templates[0]  # morning_motivation with times 07:00-09:00
        target_time = time(8, 0)  # 8:00 AM
        
        score = template_selector._calculate_time_score(template, target_time)
        assert score == 1.0  # Perfect match
    
    def test_calculate_time_score_close_match(self, template_selector, sample_templates):
        """Test time score calculation with close match"""
        template = sample_templates[0]  # morning_motivation with times 07:00-09:00
        target_time = time(10, 0)  # 10:00 AM (1 hour off)
        
        score = template_selector._calculate_time_score(template, target_time)
        assert score == 0.8  # Close match
    
    def test_calculate_time_score_no_preferred_times(self, template_selector):
        """Test time score calculation with no preferred times"""
        template = RichMessageTemplate(
            template_id="test",
            category=ContentCategory.MOTIVATION,
            filename="test.png",
            theme="test",
            mood="test",
            preferred_times=[],  # No preferred times
            energy_level="medium",
            text_areas=[],
            tags=[]
        )
        target_time = time(8, 0)
        
        score = template_selector._calculate_time_score(template, target_time)
        assert score == 0.5  # Neutral score
    
    def test_calculate_energy_score_perfect_match(self, template_selector, sample_templates):
        """Test energy score calculation with perfect match"""
        template = sample_templates[0]  # high energy
        target_energy = "high"
        
        score = template_selector._calculate_energy_score(template, target_energy)
        assert score == 1.0
    
    def test_calculate_energy_score_adjacent_match(self, template_selector, sample_templates):
        """Test energy score calculation with adjacent match"""
        template = sample_templates[0]  # high energy
        target_energy = "medium"
        
        score = template_selector._calculate_energy_score(template, target_energy)
        assert score == 0.7
    
    def test_calculate_energy_score_no_energy_level(self, template_selector):
        """Test energy score calculation with no energy level"""
        template = RichMessageTemplate(
            template_id="test",
            category=ContentCategory.MOTIVATION,
            filename="test.png",
            theme="test",
            mood="test",
            preferred_times=[],
            energy_level=None,  # No energy level
            text_areas=[],
            tags=[]
        )
        target_energy = "high"
        
        score = template_selector._calculate_energy_score(template, target_energy)
        assert score == 0.5
    
    def test_calculate_theme_score_direct_match(self, template_selector, sample_templates):
        """Test theme score calculation with direct match"""
        template = sample_templates[0]  # theme: morning_energy
        target_theme = ContentTheme.MORNING_ENERGY
        
        score = template_selector._calculate_theme_score(template, target_theme)
        assert score == 1.0
    
    def test_calculate_theme_score_no_theme(self, template_selector, sample_templates):
        """Test theme score calculation with no target theme"""
        template = sample_templates[0]
        target_theme = None
        
        score = template_selector._calculate_theme_score(template, target_theme)
        assert score == 0.5
    
    def test_calculate_mood_score_direct_match(self, template_selector, sample_templates):
        """Test mood score calculation with direct match"""
        template = sample_templates[0]  # mood: energetic
        target_mood = "energetic"
        
        score = template_selector._calculate_mood_score(template, target_mood)
        assert score == 1.0
    
    def test_calculate_mood_score_similar_mood(self, template_selector, sample_templates):
        """Test mood score calculation with similar mood"""
        template = sample_templates[0]  # mood: energetic
        target_mood = "dynamic"  # Similar to energetic
        
        score = template_selector._calculate_mood_score(template, target_mood)
        assert score == 0.8
    
    def test_calculate_seasonal_score_matching_tags(self, template_selector, sample_templates):
        """Test seasonal score calculation with matching tags"""
        template = sample_templates[0]  # tags include "energy" which matches summer
        target_season = "summer"
        
        score = template_selector._calculate_seasonal_score(template, target_season)
        assert score >= 0.5  # Should get some points for matching keywords
    
    def test_calculate_text_area_score_good_areas(self, template_selector, sample_templates):
        """Test text area score calculation with good areas"""
        template = sample_templates[0]  # Has text areas
        
        score = template_selector._calculate_text_area_score(template)
        assert score > 0.2  # Should be better than no text areas
    
    def test_calculate_text_area_score_no_areas(self, template_selector):
        """Test text area score calculation with no text areas"""
        template = RichMessageTemplate(
            template_id="test",
            category=ContentCategory.MOTIVATION,
            filename="test.png",
            theme="test",
            mood="test",
            preferred_times=[],
            energy_level="medium",
            text_areas=[],  # No text areas
            tags=[]
        )
        
        score = template_selector._calculate_text_area_score(template)
        assert score == 0.2
    
    def test_calculate_novelty_score_new_template(self, template_selector, sample_templates):
        """Test novelty score calculation for new template"""
        template = sample_templates[0]
        # Template not in recent selections
        
        score = template_selector._calculate_novelty_score(template)
        assert score == 1.0
    
    def test_calculate_novelty_score_recent_template(self, template_selector, sample_templates):
        """Test novelty score calculation for recently used template"""
        template = sample_templates[0]
        template_selector.recent_selections = [template.template_id]
        
        score = template_selector._calculate_novelty_score(template)
        assert score < 1.0  # Should be penalized for recent use
    
    def test_calculate_user_preference_score_preferred_category(self, template_selector, sample_templates):
        """Test user preference score with preferred category"""
        template = sample_templates[0]  # MOTIVATION category
        user_preferences = {
            "preferred_categories": ["motivation"]
        }
        
        score = template_selector._calculate_user_preference_score(template, user_preferences)
        assert score > 0.5  # Should get bonus for preferred category
    
    def test_calculate_user_preference_score_disliked_template(self, template_selector, sample_templates):
        """Test user preference score with disliked template"""
        template = sample_templates[0]
        user_preferences = {
            "disliked_templates": [template.template_id]
        }
        
        score = template_selector._calculate_user_preference_score(template, user_preferences)
        assert score < 0.5  # Should be penalized
    
    def test_score_template_category_mismatch(self, template_selector, sample_templates):
        """Test template scoring with category mismatch"""
        template = sample_templates[0]  # MOTIVATION category
        criteria = SelectionCriteria(category=ContentCategory.WELLNESS)  # Different category
        
        score_result = template_selector.score_template(template, criteria)
        assert score_result.total_score == 0.0
        assert "mismatch" in score_result.selection_reason.lower()
    
    def test_score_template_valid(self, template_selector, sample_templates):
        """Test template scoring with matching category"""
        template = sample_templates[0]  # MOTIVATION category
        criteria = SelectionCriteria(
            category=ContentCategory.MOTIVATION,
            time_context=time(8, 0),
            energy_level="high"
        )
        
        score_result = template_selector.score_template(template, criteria)
        assert score_result.total_score > 0.0
        assert isinstance(score_result.score_breakdown, dict)
        assert "category_match" in score_result.score_breakdown
    
    def test_select_template_success(self, template_selector, sample_templates):
        """Test successful template selection"""
        criteria = SelectionCriteria(category=ContentCategory.MOTIVATION)
        
        # Mock template manager to return motivation templates
        motivation_templates = [t for t in sample_templates if t.category == ContentCategory.MOTIVATION]
        template_selector.template_manager.get_templates_by_category.return_value = motivation_templates
        
        selected = template_selector.select_template(criteria)
        
        assert selected is not None
        assert selected.category == ContentCategory.MOTIVATION
        assert selected.template_id in template_selector.recent_selections
    
    def test_select_template_no_templates(self, template_selector):
        """Test template selection with no available templates"""
        criteria = SelectionCriteria(category=ContentCategory.MOTIVATION)
        template_selector.template_manager.get_templates_by_category.return_value = []
        
        selected = template_selector.select_template(criteria)
        assert selected is None
    
    def test_select_template_different_strategies(self, template_selector, sample_templates):
        """Test template selection with different strategies"""
        criteria = SelectionCriteria(
            category=ContentCategory.MOTIVATION,
            strategy=SelectionStrategy.TIME_OPTIMIZED,
            time_context=time(8, 0)
        )
        
        motivation_templates = [t for t in sample_templates if t.category == ContentCategory.MOTIVATION]
        template_selector.template_manager.get_templates_by_category.return_value = motivation_templates
        
        # Test TIME_OPTIMIZED strategy
        selected = template_selector.select_template(criteria)
        assert selected is not None
        
        # Test RANDOM_WEIGHTED strategy
        criteria.strategy = SelectionStrategy.RANDOM_WEIGHTED
        template_selector.clear_selection_history()  # Clear history
        selected = template_selector.select_template(criteria)
        assert selected is not None
    
    def test_get_template_recommendations(self, template_selector, sample_templates):
        """Test getting template recommendations"""
        criteria = SelectionCriteria(category=ContentCategory.MOTIVATION)
        motivation_templates = [t for t in sample_templates if t.category == ContentCategory.MOTIVATION]
        template_selector.template_manager.get_templates_by_category.return_value = motivation_templates
        
        recommendations = template_selector.get_template_recommendations(criteria, count=2)
        
        assert isinstance(recommendations, list)
        assert len(recommendations) <= 2
        assert all(isinstance(rec, TemplateScore) for rec in recommendations)
        
        # Should be sorted by score (highest first)
        if len(recommendations) > 1:
            assert recommendations[0].total_score >= recommendations[1].total_score
    
    def test_get_template_recommendations_no_templates(self, template_selector):
        """Test getting recommendations with no templates"""
        criteria = SelectionCriteria(category=ContentCategory.MOTIVATION)
        template_selector.template_manager.get_templates_by_category.return_value = []
        
        recommendations = template_selector.get_template_recommendations(criteria)
        assert recommendations == []
    
    def test_track_selection(self, template_selector):
        """Test selection tracking"""
        template_id = "test_template"
        
        # First tracking
        template_selector._track_selection(template_id)
        assert template_id in template_selector.recent_selections
        
        # Second tracking should move to end
        template_selector._track_selection("other_template")
        template_selector._track_selection(template_id)
        assert template_selector.recent_selections[-1] == template_id
    
    def test_track_selection_max_history(self, template_selector):
        """Test selection tracking with max history limit"""
        template_selector.max_recent_history = 3
        
        # Add more than max history
        for i in range(5):
            template_selector._track_selection(f"template_{i}")
        
        assert len(template_selector.recent_selections) == 3
        # Should contain the 3 most recent
        expected = ["template_2", "template_3", "template_4"]
        assert template_selector.recent_selections == expected
    
    def test_clear_selection_history(self, template_selector):
        """Test clearing selection history"""
        template_selector.recent_selections = ["template1", "template2"]
        
        template_selector.clear_selection_history()
        assert template_selector.recent_selections == []
    
    def test_get_selection_stats(self, template_selector):
        """Test getting selection statistics"""
        template_selector.recent_selections = ["template1", "template2"]
        
        stats = template_selector.get_selection_stats()
        
        assert "recent_selections" in stats
        assert "max_history_size" in stats
        assert "scoring_weights" in stats
        assert "available_strategies" in stats
        
        assert stats["recent_selections"] == 2
        assert isinstance(stats["available_strategies"], list)
    
    def test_selection_criteria_creation(self):
        """Test SelectionCriteria creation"""
        criteria = SelectionCriteria(
            category=ContentCategory.MOTIVATION,
            theme=ContentTheme.MORNING_ENERGY,
            mood="energetic",
            energy_level="high",
            time_context=time(8, 0),
            strategy=SelectionStrategy.TIME_OPTIMIZED
        )
        
        assert criteria.category == ContentCategory.MOTIVATION
        assert criteria.theme == ContentTheme.MORNING_ENERGY
        assert criteria.mood == "energetic"
        assert criteria.energy_level == "high"
        assert criteria.time_context == time(8, 0)
        assert criteria.strategy == SelectionStrategy.TIME_OPTIMIZED
    
    def test_template_score_creation(self, sample_templates):
        """Test TemplateScore creation"""
        template = sample_templates[0]
        score_breakdown = {
            "time_match": 1.0,
            "energy_match": 0.8,
            "theme_match": 0.9
        }
        
        template_score = TemplateScore(
            template=template,
            total_score=0.85,
            score_breakdown=score_breakdown,
            selection_reason="High scores in time and theme matching"
        )
        
        assert template_score.template == template
        assert template_score.total_score == 0.85
        assert template_score.score_breakdown == score_breakdown
        assert "time and theme" in template_score.selection_reason
    
    def test_selection_strategy_enum(self):
        """Test SelectionStrategy enum values"""
        strategies = list(SelectionStrategy)
        
        assert SelectionStrategy.TIME_OPTIMIZED in strategies
        assert SelectionStrategy.MOOD_BASED in strategies
        assert SelectionStrategy.RANDOM_WEIGHTED in strategies
        assert SelectionStrategy.USER_PREFERENCE in strategies
        
        # Test string values
        assert SelectionStrategy.TIME_OPTIMIZED.value == "time_optimized"
        assert SelectionStrategy.MOOD_BASED.value == "mood_based"