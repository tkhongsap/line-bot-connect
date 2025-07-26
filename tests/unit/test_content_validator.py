"""
Unit tests for ContentValidator
"""

import pytest
from unittest.mock import patch, mock_open
import json
from datetime import datetime

from src.utils.content_validator import (
    ContentValidator, ValidationLevel, ValidationResult, 
    ValidationIssue, ContentValidationResult
)
from src.utils.content_generator import GeneratedContent
from src.models.rich_message_models import ContentCategory


class TestContentValidator:
    """Test cases for ContentValidator"""
    
    @pytest.fixture
    def sample_validation_config(self):
        """Create sample validation configuration"""
        return {
            "content_validation": {
                "required_elements": ["positive_tone", "actionable_insight"],
                "avoid": ["negative_language", "controversial_topics", "inappropriate_content"],
                "quality_checks": ["grammar_and_spelling", "tone_consistency", "message_clarity"]
            }
        }
    
    @pytest.fixture
    def content_validator(self, sample_validation_config):
        """Create a ContentValidator instance"""
        config_json = json.dumps(sample_validation_config)
        
        with patch('builtins.open', mock_open(read_data=config_json)):
            validator = ContentValidator(validation_level=ValidationLevel.MODERATE)
            return validator
    
    @pytest.fixture
    def good_content(self):
        """Create content that should pass validation"""
        return GeneratedContent(
            title="Start Your Day with Positive Energy",
            content="Every morning brings new opportunities to achieve greatness. Take action today and create the success you deserve!",
            language="en",
            category=ContentCategory.MOTIVATION,
            theme=None,
            metadata={},
            generation_time=datetime.now()
        )
    
    @pytest.fixture
    def problematic_content(self):
        """Create content with validation issues"""
        return GeneratedContent(
            title="Hate",
            content="You can't succeed because failure is inevitable and you're hopeless.",
            language="en",
            category=ContentCategory.MOTIVATION,
            theme=None,
            metadata={},
            generation_time=datetime.now()
        )
    
    def test_initialization_with_config(self, content_validator):
        """Test ContentValidator initialization with valid config"""
        assert content_validator.validation_level == ValidationLevel.MODERATE
        assert "positive_tone" in content_validator.required_elements
        assert "negative_language" in content_validator.avoid_terms
        assert len(content_validator.inappropriate_patterns) > 0
    
    def test_initialization_fallback_config(self):
        """Test ContentValidator initialization with fallback config"""
        with patch('builtins.open', side_effect=FileNotFoundError()):
            validator = ContentValidator()
            
            # Should have fallback rules
            assert len(validator.required_elements) > 0
            assert len(validator.avoid_terms) > 0
    
    def test_validate_content_good_content(self, content_validator, good_content):
        """Test validation of good content"""
        result = content_validator.validate_content(good_content)
        
        assert isinstance(result, ContentValidationResult)
        assert result.result in [ValidationResult.APPROVED, ValidationResult.WARNING]
        assert result.score > 0.5
        assert isinstance(result.issues, list)
        assert isinstance(result.recommendations, list)
        assert "validation_level" in result.metadata
    
    def test_validate_content_problematic_content(self, content_validator, problematic_content):
        """Test validation of problematic content"""
        result = content_validator.validate_content(problematic_content)
        
        assert result.result in [ValidationResult.REJECTED, ValidationResult.WARNING]
        assert result.score < 0.8
        assert len(result.issues) > 0
        
        # Should have issues with inappropriate content and negative language
        issue_types = [issue.type for issue in result.issues]
        assert any("inappropriate" in issue_type or "negative" in issue_type for issue_type in issue_types)
    
    def test_check_appropriateness_inappropriate_content(self, content_validator):
        """Test appropriateness checking with inappropriate content"""
        content = GeneratedContent(
            title="Hate and Violence",
            content="This contains hate speech and inappropriate language.",
            language="en",
            category=ContentCategory.MOTIVATION,
            theme=None,
            metadata={},
            generation_time=datetime.now()
        )
        
        full_text = f"{content.title} {content.content}".lower()
        issues = content_validator._check_appropriateness(content, full_text)
        
        assert len(issues) > 0
        assert any(issue.type == "inappropriate_content" for issue in issues)
        assert any(issue.severity == "high" for issue in issues)
    
    def test_check_appropriateness_commercial_content(self, content_validator):
        """Test appropriateness checking with commercial content"""
        content = GeneratedContent(
            title="Buy Our Product Now",
            content="Purchase our amazing service for the best price and special discount!",
            language="en",
            category=ContentCategory.MOTIVATION,
            theme=None,
            metadata={},
            generation_time=datetime.now()
        )
        
        full_text = f"{content.title} {content.content}".lower()
        issues = content_validator._check_appropriateness(content, full_text)
        
        assert any(issue.type == "commercial_content" for issue in issues)
    
    def test_check_appropriateness_medical_advice(self, content_validator):
        """Test appropriateness checking with medical advice"""
        content = GeneratedContent(
            title="Medical Treatment Advice",
            content="You should take this medication and see a doctor for your illness.",
            language="en",
            category=ContentCategory.WELLNESS,
            theme=None,
            metadata={},
            generation_time=datetime.now()
        )
        
        full_text = f"{content.title} {content.content}".lower()
        issues = content_validator._check_appropriateness(content, full_text)
        
        assert any(issue.type == "medical_advice" for issue in issues)
    
    def test_check_quality_positive_tone(self, content_validator):
        """Test quality checking for positive tone"""
        # Content with positive language
        positive_content = GeneratedContent(
            title="Achieve Success Today",
            content="You can improve and grow by taking positive action towards your goals.",
            language="en",
            category=ContentCategory.MOTIVATION,
            theme=None,
            metadata={},
            generation_time=datetime.now()
        )
        
        full_text = f"{positive_content.title} {positive_content.content}".lower()
        issues = content_validator._check_quality(positive_content, full_text)
        
        # Should have fewer issues with positive content
        tone_issues = [issue for issue in issues if issue.type == "tone_quality"]
        assert len(tone_issues) == 0  # Should not flag positive content
    
    def test_check_quality_negative_tone(self, content_validator):
        """Test quality checking for negative tone"""
        negative_content = GeneratedContent(
            title="You Can't Succeed",
            content="Failure is inevitable and you cannot achieve anything because it's impossible.",
            language="en",
            category=ContentCategory.MOTIVATION,
            theme=None,
            metadata={},
            generation_time=datetime.now()
        )
        
        full_text = f"{negative_content.title} {negative_content.content}".lower()
        issues = content_validator._check_quality(negative_content, full_text)
        
        # Should flag excessive negative language
        negative_issues = [issue for issue in issues if issue.type == "negative_tone"]
        assert len(negative_issues) > 0
    
    def test_check_quality_actionable_content(self, content_validator):
        """Test quality checking for actionable content"""
        # Content without action words
        passive_content = GeneratedContent(
            title="Thinking About Success",
            content="Success exists and happiness is possible when things happen.",
            language="en",
            category=ContentCategory.MOTIVATION,
            theme=None,
            metadata={},
            generation_time=datetime.now()
        )
        
        full_text = f"{passive_content.title} {passive_content.content}".lower()
        issues = content_validator._check_quality(passive_content, full_text)
        
        # Should flag lack of actionable language
        action_issues = [issue for issue in issues if issue.type == "actionable_content"]
        assert len(action_issues) > 0
    
    def test_check_safety_harmful_advice(self, content_validator):
        """Test safety checking for harmful advice"""
        harmful_content = GeneratedContent(
            title="Give Up Now",
            content="You should quit everything and abandon your dreams because it's too extreme.",
            language="en",
            category=ContentCategory.MOTIVATION,
            theme=None,
            metadata={},
            generation_time=datetime.now()
        )
        
        full_text = f"{harmful_content.title} {harmful_content.content}".lower()
        issues = content_validator._check_safety(harmful_content, full_text)
        
        assert any(issue.type == "potentially_harmful" for issue in issues)
    
    def test_check_safety_overpromising(self, content_validator):
        """Test safety checking for overpromising"""
        overpromise_content = GeneratedContent(
            title="Guaranteed Instant Success",
            content="This magic solution will definitely give you overnight results and miracle transformation.",
            language="en",
            category=ContentCategory.MOTIVATION,
            theme=None,
            metadata={},
            generation_time=datetime.now()
        )
        
        full_text = f"{overpromise_content.title} {overpromise_content.content}".lower()
        issues = content_validator._check_safety(overpromise_content, full_text)
        
        assert any(issue.type == "overpromising" for issue in issues)
    
    def test_check_length_requirements_title_too_short(self, content_validator):
        """Test length checking for short title"""
        short_title_content = GeneratedContent(
            title="Hi",
            content="This is a reasonable length content that should be fine for validation purposes.",
            language="en",
            category=ContentCategory.MOTIVATION,
            theme=None,
            metadata={},
            generation_time=datetime.now()
        )
        
        issues = content_validator._check_length_requirements(short_title_content)
        
        assert any(issue.type == "title_too_short" for issue in issues)
    
    def test_check_length_requirements_content_too_short(self, content_validator):
        """Test length checking for short content"""
        short_content = GeneratedContent(
            title="Good Title Length",
            content="Short.",
            language="en",
            category=ContentCategory.MOTIVATION,
            theme=None,
            metadata={},
            generation_time=datetime.now()
        )
        
        issues = content_validator._check_length_requirements(short_content)
        
        assert any(issue.type == "content_too_short" for issue in issues)
    
    def test_check_length_requirements_content_too_long(self, content_validator):
        """Test length checking for long content"""
        long_content = GeneratedContent(
            title="Good Title Length",
            content="x" * 1500,  # Very long content
            language="en",
            category=ContentCategory.MOTIVATION,
            theme=None,
            metadata={},
            generation_time=datetime.now()
        )
        
        issues = content_validator._check_length_requirements(long_content)
        
        assert any(issue.type == "content_too_long" for issue in issues)
    
    def test_check_cultural_sensitivity(self, content_validator):
        """Test cultural sensitivity checking"""
        cultural_content = GeneratedContent(
            title="Cultural Traditions",
            content="This content references various cultural and religious traditions around the world.",
            language="en",
            category=ContentCategory.MOTIVATION,
            theme=None,
            metadata={},
            generation_time=datetime.now()
        )
        
        full_text = f"{cultural_content.title} {cultural_content.content}".lower()
        issues = content_validator._check_cultural_sensitivity(cultural_content, full_text)
        
        # Should flag for manual review
        assert any(issue.type == "cultural_reference" for issue in issues)
        # Should be low severity (for review, not rejection)
        cultural_issues = [issue for issue in issues if issue.type == "cultural_reference"]
        assert all(issue.severity == "low" for issue in cultural_issues)
    
    def test_check_required_elements_missing(self, content_validator):
        """Test checking for missing required elements"""
        # Content without positive tone or actionable insights
        bland_content = GeneratedContent(
            title="Some Title",
            content="This is neutral content without specific positive or action words.",
            language="en",
            category=ContentCategory.MOTIVATION,
            theme=None,
            metadata={},
            generation_time=datetime.now()
        )
        
        full_text = f"{bland_content.title} {bland_content.content}".lower()
        issues = content_validator._check_required_elements(bland_content, full_text)
        
        # Should flag missing required elements
        assert any(issue.type == "missing_required_element" for issue in issues)
    
    def test_calculate_readability_score(self, content_validator):
        """Test readability score calculation"""
        # Simple, readable text
        simple_text = "This is simple. Easy to read. Short sentences work well."
        simple_score = content_validator._calculate_readability_score(simple_text)
        
        # Complex, hard to read text
        complex_text = "This extraordinarily complicated sentence contains numerous multisyllabic words and convoluted grammatical structures that significantly impede comprehension and readability metrics."
        complex_score = content_validator._calculate_readability_score(complex_text)
        
        assert simple_score > complex_score
        assert 0.0 <= simple_score <= 1.0
        assert 0.0 <= complex_score <= 1.0
    
    def test_calculate_validation_score_no_issues(self, content_validator):
        """Test validation score calculation with no issues"""
        score = content_validator._calculate_validation_score([])
        assert score == 1.0
    
    def test_calculate_validation_score_with_issues(self, content_validator):
        """Test validation score calculation with various issues"""
        issues = [
            ValidationIssue("test1", "low", "Low severity issue"),
            ValidationIssue("test2", "medium", "Medium severity issue"),
            ValidationIssue("test3", "high", "High severity issue")
        ]
        
        score = content_validator._calculate_validation_score(issues)
        assert 0.0 <= score < 1.0
    
    def test_determine_validation_result_strict(self, content_validator):
        """Test validation result determination with strict level"""
        content_validator.validation_level = ValidationLevel.STRICT
        
        # High score, no issues
        result = content_validator._determine_validation_result(0.95, [])
        assert result == ValidationResult.APPROVED
        
        # Medium score
        result = content_validator._determine_validation_result(0.85, [])
        assert result == ValidationResult.WARNING
        
        # Low score
        result = content_validator._determine_validation_result(0.7, [])
        assert result == ValidationResult.REJECTED
    
    def test_determine_validation_result_basic(self, content_validator):
        """Test validation result determination with basic level"""
        content_validator.validation_level = ValidationLevel.BASIC
        
        # Even lower standards should pass
        result = content_validator._determine_validation_result(0.7, [])
        assert result == ValidationResult.APPROVED
        
        # Very low score should reject
        result = content_validator._determine_validation_result(0.3, [])
        assert result == ValidationResult.REJECTED
    
    def test_quick_validate_good_text(self, content_validator):
        """Test quick validation with good text"""
        good_text = "This is positive and inspiring content that should pass validation."
        result = content_validator.quick_validate(good_text)
        assert result is True
    
    def test_quick_validate_bad_text(self, content_validator):
        """Test quick validation with problematic text"""
        bad_text = "hate violence inappropriate"
        result = content_validator.quick_validate(bad_text)
        assert result is False
    
    def test_quick_validate_too_short(self, content_validator):
        """Test quick validation with too short text"""
        short_text = "Hi"
        result = content_validator.quick_validate(short_text)
        assert result is False
    
    def test_quick_validate_excessive_negative(self, content_validator):
        """Test quick validation with excessive negative language"""
        negative_text = "You can't succeed because failure is impossible and hopeless and terrible"
        result = content_validator.quick_validate(negative_text)
        assert result is False
    
    def test_generate_recommendations(self, content_validator, good_content):
        """Test recommendation generation"""
        issues = [
            ValidationIssue("tone_quality", "medium", "Lacks positive tone", 
                          "Add more positive language"),
            ValidationIssue("actionable_content", "low", "Lacks action words", 
                          "Include action-oriented language")
        ]
        
        recommendations = content_validator._generate_recommendations(issues, good_content)
        
        assert isinstance(recommendations, list)
        assert len(recommendations) > 0
        assert "Add more positive language" in recommendations
        assert "Include action-oriented language" in recommendations
    
    def test_get_validation_stats(self, content_validator):
        """Test getting validation statistics"""
        stats = content_validator.get_validation_stats()
        
        assert "validation_level" in stats
        assert "filter_categories" in stats
        assert "required_elements" in stats
        assert "quality_checks" in stats
        assert "supported_languages" in stats
        
        assert stats["validation_level"] == "moderate"
        assert isinstance(stats["filter_categories"], dict)
        assert isinstance(stats["supported_languages"], list)
    
    def test_validation_issue_creation(self):
        """Test ValidationIssue creation"""
        issue = ValidationIssue(
            type="test_issue",
            severity="medium",
            message="Test message",
            suggestion="Test suggestion",
            location="title"
        )
        
        assert issue.type == "test_issue"
        assert issue.severity == "medium"
        assert issue.message == "Test message"
        assert issue.suggestion == "Test suggestion"
        assert issue.location == "title"
    
    def test_content_validation_result_creation(self, good_content):
        """Test ContentValidationResult creation"""
        issues = [ValidationIssue("test", "low", "Test issue")]
        recommendations = ["Test recommendation"]
        metadata = {"test": "data"}
        
        result = ContentValidationResult(
            result=ValidationResult.APPROVED,
            score=0.85,
            issues=issues,
            recommendations=recommendations,
            metadata=metadata
        )
        
        assert result.result == ValidationResult.APPROVED
        assert result.score == 0.85
        assert result.issues == issues
        assert result.recommendations == recommendations
        assert result.metadata == metadata
    
    def test_validation_levels(self):
        """Test validation level enum values"""
        assert ValidationLevel.BASIC.value == "basic"
        assert ValidationLevel.MODERATE.value == "moderate"
        assert ValidationLevel.STRICT.value == "strict"
    
    def test_validation_results(self):
        """Test validation result enum values"""
        assert ValidationResult.APPROVED.value == "approved"
        assert ValidationResult.WARNING.value == "warning"
        assert ValidationResult.REJECTED.value == "rejected"