"""
Content Validation and Appropriateness Filtering for Rich Message automation.

This module provides comprehensive content validation, appropriateness filtering,
and quality assurance for generated Rich Message content.
"""

import logging
import re
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass
from enum import Enum
import json

from src.utils.content_generator import GeneratedContent
from src.models.rich_message_models import ContentCategory, ValidationError

logger = logging.getLogger(__name__)


class ValidationLevel(Enum):
    """Content validation levels"""
    BASIC = "basic"
    MODERATE = "moderate"
    STRICT = "strict"


class ValidationResult(Enum):
    """Validation result types"""
    APPROVED = "approved"
    WARNING = "warning"
    REJECTED = "rejected"


@dataclass
class ValidationIssue:
    """Individual validation issue"""
    type: str
    severity: str  # "low", "medium", "high"
    message: str
    suggestion: Optional[str] = None
    location: Optional[str] = None  # "title", "content", "both"


@dataclass
class ContentValidationResult:
    """Complete validation result"""
    result: ValidationResult
    score: float  # 0.0 to 1.0
    issues: List[ValidationIssue]
    recommendations: List[str]
    metadata: Dict[str, Any]


class ContentValidator:
    """
    Comprehensive content validation and filtering system.
    
    Provides multiple validation layers including appropriateness filtering,
    quality assessment, cultural sensitivity, and safety checks.
    """
    
    def __init__(self, validation_level: ValidationLevel = ValidationLevel.MODERATE):
        """
        Initialize the ContentValidator.
        
        Args:
            validation_level: Level of validation strictness
        """
        self.validation_level = validation_level
        self.load_validation_rules()
        
        # Initialize validation components
        self._init_filters()
        self._init_quality_checks()
        self._init_safety_checks()
    
    def load_validation_rules(self) -> None:
        """Load validation rules and filters from configuration."""
        try:
            # Load from content prompts file which contains validation rules
            prompts_file = "/home/runner/workspace/src/config/content_prompts.json"
            with open(prompts_file, 'r', encoding='utf-8') as f:
                prompts_data = json.load(f)
            
            self.validation_config = prompts_data.get("content_validation", {})
            
            # Extract validation rules
            self.required_elements = set(self.validation_config.get("required_elements", []))
            self.avoid_terms = set(self.validation_config.get("avoid", []))
            self.quality_checks = set(self.validation_config.get("quality_checks", []))
            
        except Exception as e:
            logger.error(f"Failed to load validation rules: {str(e)}")
            # Fallback to basic rules
            self._load_fallback_rules()
    
    def _load_fallback_rules(self) -> None:
        """Load fallback validation rules if main config fails."""
        self.validation_config = {}
        self.required_elements = {"positive_tone", "actionable_insight"}
        self.avoid_terms = {
            "negative_language", "controversial_topics", 
            "inappropriate_content", "offensive_language"
        }
        self.quality_checks = {
            "grammar_and_spelling", "tone_consistency", 
            "message_clarity", "length_compliance"
        }
    
    def _init_filters(self) -> None:
        """Initialize content filters."""
        # Inappropriate content filters
        self.inappropriate_patterns = [
            r'\b(hate|violence|discrimination|racism|sexism)\b',
            r'\b(offensive|inappropriate|vulgar|profanity)\b',
            r'\b(politics|political|religion|religious)\b',
            r'\b(controversial|divisive|polarizing)\b'
        ]
        
        # Negative sentiment patterns
        self.negative_patterns = [
            r'\b(can\'t|cannot|impossible|never|hopeless)\b',
            r'\b(failure|failed|failing|defeat|lose|losing)\b',
            r'\b(terrible|awful|horrible|dreadful|worst)\b',
            r'\b(depression|anxiety|stress|overwhelm)\b'
        ]
        
        # Commercial/promotional patterns
        self.commercial_patterns = [
            r'\b(buy|purchase|sale|discount|price|cost)\b',
            r'\b(product|service|company|business|brand)\b',
            r'\b(advertisement|promotion|marketing|sponsor)\b'
        ]
        
        # Medical/health advice patterns (to avoid giving medical advice)
        self.medical_patterns = [
            r'\b(diagnose|treatment|medication|prescription|cure)\b',
            r'\b(disease|illness|symptom|medical|doctor)\b',
            r'\b(therapy|therapeutic|clinical|pharmaceutical)\b'
        ]
    
    def _init_quality_checks(self) -> None:
        """Initialize quality check patterns."""
        # Positive indicators
        self.positive_indicators = [
            r'\b(achieve|success|growth|improve|better)\b',
            r'\b(opportunity|possibility|potential|hope)\b',
            r'\b(inspire|motivate|encourage|empower)\b',
            r'\b(positive|optimistic|confident|strong)\b'
        ]
        
        # Action-oriented language
        self.action_indicators = [
            r'\b(start|begin|take|create|build|develop)\b',
            r'\b(action|step|move|progress|forward)\b',
            r'\b(do|act|make|work|try|attempt)\b'
        ]
        
        # Quality language patterns
        self.quality_patterns = [
            r'\b(today|now|moment|present|immediate)\b',
            r'\b(you|your|yourself|personal)\b',
            r'\b(can|will|able|capable|possible)\b'
        ]
    
    def _init_safety_checks(self) -> None:
        """Initialize safety check patterns."""
        # Potentially harmful advice patterns
        self.harmful_patterns = [
            r'\b(quit|give up|abandon|surrender)\b',
            r'\b(extreme|drastic|radical|dangerous)\b',
            r'\b(ignore|avoid|escape|run away)\b'
        ]
        
        # Overpromising patterns
        self.overpromise_patterns = [
            r'\b(guarantee|promised|definitely|certainly will)\b',
            r'\b(instant|immediate|overnight|quick fix)\b',
            r'\b(magic|miracle|secret|ultimate solution)\b'
        ]
    
    def validate_content(self, content: GeneratedContent) -> ContentValidationResult:
        """
        Perform comprehensive content validation.
        
        Args:
            content: Generated content to validate
            
        Returns:
            Complete validation result
        """
        issues = []
        recommendations = []
        
        # Combine title and content for analysis
        full_text = f"{content.title} {content.content}".lower()
        
        # Run all validation checks
        issues.extend(self._check_appropriateness(content, full_text))
        issues.extend(self._check_quality(content, full_text))
        issues.extend(self._check_safety(content, full_text))
        issues.extend(self._check_length_requirements(content))
        issues.extend(self._check_cultural_sensitivity(content, full_text))
        issues.extend(self._check_required_elements(content, full_text))
        
        # Calculate overall score
        score = self._calculate_validation_score(issues)
        
        # Determine result based on score and validation level
        result = self._determine_validation_result(score, issues)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(issues, content)
        
        # Create metadata
        metadata = {
            "validation_level": self.validation_level.value,
            "content_length": len(content.content),
            "title_length": len(content.title),
            "language": content.language,
            "category": content.category.value,
            "issue_count": len(issues),
            "high_severity_issues": len([i for i in issues if i.severity == "high"])
        }
        
        return ContentValidationResult(
            result=result,
            score=score,
            issues=issues,
            recommendations=recommendations,
            metadata=metadata
        )
    
    def _check_appropriateness(self, content: GeneratedContent, full_text: str) -> List[ValidationIssue]:
        """Check content appropriateness."""
        issues = []
        
        # Check for inappropriate content
        for pattern in self.inappropriate_patterns:
            if re.search(pattern, full_text, re.IGNORECASE):
                issues.append(ValidationIssue(
                    type="inappropriate_content",
                    severity="high",
                    message="Content contains potentially inappropriate language",
                    suggestion="Remove or replace inappropriate terms with positive alternatives",
                    location="both"
                ))
        
        # Check for commercial content
        commercial_matches = sum(1 for pattern in self.commercial_patterns 
                               if re.search(pattern, full_text, re.IGNORECASE))
        if commercial_matches >= 2:
            issues.append(ValidationIssue(
                type="commercial_content",
                severity="medium",
                message="Content appears to be commercial or promotional",
                suggestion="Focus on inspirational messaging rather than commercial language",
                location="both"
            ))
        
        # Check for medical advice
        for pattern in self.medical_patterns:
            if re.search(pattern, full_text, re.IGNORECASE):
                issues.append(ValidationIssue(
                    type="medical_advice",
                    severity="high",
                    message="Content may contain medical advice",
                    suggestion="Avoid specific medical or health advice, focus on general wellness",
                    location="both"
                ))
        
        return issues
    
    def _check_quality(self, content: GeneratedContent, full_text: str) -> List[ValidationIssue]:
        """Check content quality indicators."""
        issues = []
        
        # Check for positive tone
        positive_matches = sum(1 for pattern in self.positive_indicators 
                             if re.search(pattern, full_text, re.IGNORECASE))
        if positive_matches == 0:
            issues.append(ValidationIssue(
                type="tone_quality",
                severity="medium",
                message="Content lacks positive language indicators",
                suggestion="Include more positive and uplifting language",
                location="both"
            ))
        
        # Check for action-oriented language
        action_matches = sum(1 for pattern in self.action_indicators 
                           if re.search(pattern, full_text, re.IGNORECASE))
        if action_matches == 0:
            issues.append(ValidationIssue(
                type="actionable_content",
                severity="low",
                message="Content lacks actionable language",
                suggestion="Include more action-oriented words to inspire engagement",
                location="both"
            ))
        
        # Check for excessive negative language
        negative_matches = sum(1 for pattern in self.negative_patterns 
                             if re.search(pattern, full_text, re.IGNORECASE))
        if negative_matches >= 3:
            issues.append(ValidationIssue(
                type="negative_tone",
                severity="high",
                message="Content contains excessive negative language",
                suggestion="Replace negative terms with neutral or positive alternatives",
                location="both"
            ))
        
        # Check readability
        if self._calculate_readability_score(content.content) < 0.3:
            issues.append(ValidationIssue(
                type="readability",
                severity="medium",
                message="Content may be difficult to read",
                suggestion="Use simpler language and shorter sentences",
                location="content"
            ))
        
        return issues
    
    def _check_safety(self, content: GeneratedContent, full_text: str) -> List[ValidationIssue]:
        """Check content safety."""
        issues = []
        
        # Check for potentially harmful advice
        for pattern in self.harmful_patterns:
            if re.search(pattern, full_text, re.IGNORECASE):
                issues.append(ValidationIssue(
                    type="potentially_harmful",
                    severity="high",
                    message="Content may contain potentially harmful advice",
                    suggestion="Reframe negative advice in a positive, constructive way",
                    location="both"
                ))
        
        # Check for overpromising
        for pattern in self.overpromise_patterns:
            if re.search(pattern, full_text, re.IGNORECASE):
                issues.append(ValidationIssue(
                    type="overpromising",
                    severity="medium",
                    message="Content may make unrealistic promises",
                    suggestion="Use more realistic and achievable language",
                    location="both"
                ))
        
        return issues
    
    def _check_length_requirements(self, content: GeneratedContent) -> List[ValidationIssue]:
        """Check length requirements."""
        issues = []
        
        # Title length check
        if len(content.title) < 5:
            issues.append(ValidationIssue(
                type="title_too_short",
                severity="medium",
                message="Title is too short",
                suggestion="Expand the title to be more descriptive",
                location="title"
            ))
        elif len(content.title) > 100:
            issues.append(ValidationIssue(
                type="title_too_long",
                severity="medium",
                message="Title is too long",
                suggestion="Shorten the title for better readability",
                location="title"
            ))
        
        # Content length check
        if len(content.content) < 20:
            issues.append(ValidationIssue(
                type="content_too_short",
                severity="high",
                message="Content is too short to be meaningful",
                suggestion="Expand the content with more inspirational detail",
                location="content"
            ))
        elif len(content.content) > 1000:
            issues.append(ValidationIssue(
                type="content_too_long",
                severity="medium",
                message="Content may be too long for optimal engagement",
                suggestion="Consider condensing the message for better impact",
                location="content"
            ))
        
        return issues
    
    def _check_cultural_sensitivity(self, content: GeneratedContent, full_text: str) -> List[ValidationIssue]:
        """Check cultural sensitivity."""
        issues = []
        
        # Cultural sensitivity patterns (basic implementation)
        culturally_sensitive_patterns = [
            r'\b(culture|cultural|tradition|traditional)\b',
            r'\b(religion|religious|belief|faith)\b',
            r'\b(race|racial|ethnic|ethnicity)\b'
        ]
        
        for pattern in culturally_sensitive_patterns:
            if re.search(pattern, full_text, re.IGNORECASE):
                # This is flagged for manual review, not automatically rejected
                issues.append(ValidationIssue(
                    type="cultural_reference",
                    severity="low",
                    message="Content references cultural or sensitive topics",
                    suggestion="Ensure cultural references are respectful and inclusive",
                    location="both"
                ))
                break  # Only flag once
        
        # Language-specific checks
        if content.language in ["th", "zh", "ja", "ko"]:
            # For Asian languages, check for appropriate formality
            if not self._check_appropriate_formality(content, content.language):
                issues.append(ValidationIssue(
                    type="formality_level",
                    severity="low",
                    message="Content may not match cultural formality expectations",
                    suggestion="Adjust tone to match cultural communication norms",
                    location="both"
                ))
        
        return issues
    
    def _check_required_elements(self, content: GeneratedContent, full_text: str) -> List[ValidationIssue]:
        """Check for required content elements."""
        issues = []
        
        # Check each required element
        for element in self.required_elements:
            if not self._has_required_element(full_text, element):
                issues.append(ValidationIssue(
                    type="missing_required_element",
                    severity="medium",
                    message=f"Content is missing required element: {element}",
                    suggestion=f"Include {element.replace('_', ' ')} in the content",
                    location="both"
                ))
        
        return issues
    
    def _has_required_element(self, text: str, element: str) -> bool:
        """Check if text contains a required element."""
        element_patterns = {
            "positive_tone": self.positive_indicators,
            "actionable_insight": self.action_indicators,
            "clear_message": [r'\b(clear|obvious|evident|understand)\b'],
            "appropriate_length": []  # Checked separately
        }
        
        patterns = element_patterns.get(element, [])
        if not patterns:
            return True  # Element not pattern-based
        
        return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)
    
    def _check_appropriate_formality(self, content: GeneratedContent, language: str) -> bool:
        """Check if content has appropriate formality for the language/culture."""
        # Simplified implementation - in practice, this would be more sophisticated
        formality_indicators = {
            "th": [r'\b(ครับ|ค่ะ|กรุณา)\b'],  # Thai polite particles
            "ja": [r'\b(です|ます|ございます)\b'],  # Japanese polite forms
            "ko": [r'\b(습니다|세요|시오)\b']  # Korean polite forms
        }
        
        if language not in formality_indicators:
            return True
        
        patterns = formality_indicators[language]
        full_text = f"{content.title} {content.content}"
        
        # If content is in the target language, check for formality markers
        # This is a simplified check - real implementation would be more sophisticated
        return any(re.search(pattern, full_text) for pattern in patterns)
    
    def _calculate_readability_score(self, text: str) -> float:
        """Calculate a simple readability score."""
        if not text:
            return 0.0
        
        words = text.split()
        sentences = text.split('.')
        
        if len(sentences) == 0:
            return 0.0
        
        avg_words_per_sentence = len(words) / len(sentences)
        avg_chars_per_word = sum(len(word) for word in words) / len(words) if words else 0
        
        # Simple readability heuristic (lower is more readable)
        readability = 1.0 - min(1.0, (avg_words_per_sentence / 20.0 + avg_chars_per_word / 10.0) / 2.0)
        
        return max(0.0, readability)
    
    def _calculate_validation_score(self, issues: List[ValidationIssue]) -> float:
        """Calculate overall validation score."""
        if not issues:
            return 1.0
        
        # Weight issues by severity
        severity_weights = {"low": 0.1, "medium": 0.3, "high": 0.6}
        total_penalty = sum(severity_weights.get(issue.severity, 0.3) for issue in issues)
        
        # Calculate score (1.0 = perfect, 0.0 = terrible)
        max_penalty = len(issues) * 0.6  # Assume all high severity
        score = max(0.0, 1.0 - (total_penalty / max(1.0, max_penalty)))
        
        return score
    
    def _determine_validation_result(self, score: float, issues: List[ValidationIssue]) -> ValidationResult:
        """Determine validation result based on score and validation level."""
        high_severity_issues = [i for i in issues if i.severity == "high"]
        
        # Strict validation
        if self.validation_level == ValidationLevel.STRICT:
            if high_severity_issues or score < 0.8:
                return ValidationResult.REJECTED
            elif score < 0.9:
                return ValidationResult.WARNING
            else:
                return ValidationResult.APPROVED
        
        # Moderate validation
        elif self.validation_level == ValidationLevel.MODERATE:
            if len(high_severity_issues) >= 2 or score < 0.6:
                return ValidationResult.REJECTED
            elif high_severity_issues or score < 0.75:
                return ValidationResult.WARNING
            else:
                return ValidationResult.APPROVED
        
        # Basic validation
        else:  # ValidationLevel.BASIC
            if len(high_severity_issues) >= 3 or score < 0.4:
                return ValidationResult.REJECTED
            elif len(high_severity_issues) >= 1 or score < 0.6:
                return ValidationResult.WARNING
            else:
                return ValidationResult.APPROVED
    
    def _generate_recommendations(self, issues: List[ValidationIssue], 
                                content: GeneratedContent) -> List[str]:
        """Generate recommendations based on validation issues."""
        recommendations = []
        
        # Collect unique suggestions from issues
        suggestions = set()
        for issue in issues:
            if issue.suggestion:
                suggestions.add(issue.suggestion)
        
        recommendations.extend(list(suggestions))
        
        # Add general recommendations based on content category
        if content.category == ContentCategory.MOTIVATION:
            recommendations.append("Ensure the message is inspiring and action-oriented")
        elif content.category == ContentCategory.WELLNESS:
            recommendations.append("Focus on mental well-being and self-care aspects")
        elif content.category == ContentCategory.PRODUCTIVITY:
            recommendations.append("Include practical tips and efficiency suggestions")
        
        # Add language-specific recommendations
        if content.language != "en":
            recommendations.append(f"Ensure cultural appropriateness for {content.language} audience")
        
        return recommendations[:5]  # Limit to top 5 recommendations
    
    def quick_validate(self, text: str) -> bool:
        """
        Quick validation for basic appropriateness.
        
        Args:
            text: Text to validate
            
        Returns:
            True if text passes basic validation
        """
        text_lower = text.lower()
        
        # Check for immediate disqualifiers
        for pattern in self.inappropriate_patterns:
            if re.search(pattern, text_lower):
                return False
        
        # Check for excessive negative language
        negative_count = sum(1 for pattern in self.negative_patterns 
                           if re.search(pattern, text_lower))
        if negative_count >= 3:
            return False
        
        # Check minimum length
        if len(text.strip()) < 10:
            return False
        
        return True
    
    def get_validation_stats(self) -> Dict[str, Any]:
        """
        Get validation system statistics.
        
        Returns:
            Dictionary with validation statistics
        """
        return {
            "validation_level": self.validation_level.value,
            "filter_categories": {
                "inappropriate_patterns": len(self.inappropriate_patterns),
                "negative_patterns": len(self.negative_patterns),
                "commercial_patterns": len(self.commercial_patterns),
                "medical_patterns": len(self.medical_patterns)
            },
            "required_elements": list(self.required_elements),
            "quality_checks": list(self.quality_checks),
            "supported_languages": ["en", "th", "zh", "ja", "ko"]
        }