"""
Content quality enhancement utilities for improved AI-generated content.

This module provides advanced content quality analysis, enhancement,
and optimization for multilingual content generation with cultural sensitivity.
"""

import logging
import re
import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
import hashlib

from src.utils.redis_cache import redis_cache, cache_result
from src.utils.performance_monitor import monitored_operation

logger = logging.getLogger(__name__)


class ContentLanguage(Enum):
    """Supported languages for content enhancement."""
    ENGLISH = "en"
    THAI = "th" 
    CHINESE = "zh"
    JAPANESE = "ja"
    KOREAN = "ko"
    VIETNAMESE = "vi"
    SPANISH = "es"
    FRENCH = "fr"
    GERMAN = "de"


class ContentQuality(Enum):
    """Content quality levels."""
    EXCELLENT = "excellent"
    GOOD = "good"
    ACCEPTABLE = "acceptable"
    POOR = "poor"


@dataclass
class ContentAnalysis:
    """Content analysis results."""
    quality_score: float
    readability_score: float
    engagement_potential: float
    cultural_appropriateness: float
    language_quality: float
    content_length: int
    detected_language: ContentLanguage
    improvement_suggestions: List[str]
    quality_level: ContentQuality


class ContentQualityEnhancer:
    """Advanced content quality enhancement and optimization."""
    
    def __init__(self):
        """Initialize content quality enhancer."""
        self.cache = redis_cache
        self.language_patterns = self._initialize_language_patterns()
        self.quality_thresholds = {
            'excellent': 0.9,
            'good': 0.75,
            'acceptable': 0.6,
            'poor': 0.0
        }
        
        # Cultural sensitivity rules
        self.cultural_rules = self._initialize_cultural_rules()
        
        # Quality enhancement prompts
        self.enhancement_prompts = self._initialize_enhancement_prompts()
    
    def _initialize_language_patterns(self) -> Dict[str, Dict[str, Any]]:
        """Initialize language-specific patterns and rules."""
        return {
            'en': {
                'formal_markers': ['please', 'kindly', 'would you', 'could you'],
                'casual_markers': ['hey', 'hi', 'cool', 'awesome', 'great'],
                'readability_factors': {
                    'avg_sentence_length': 15,
                    'complex_words_ratio': 0.1,
                    'passive_voice_limit': 0.2
                }
            },
            'th': {
                'formal_markers': ['ครับ', 'ค่ะ', 'กรุณา', 'โปรด'],
                'casual_markers': ['จ้า', 'นะ', 'เนอะ', 'ฮะ'],
                'cultural_respect': ['พี่', 'น้อง', 'คุณ', 'ท่าน']
            },
            'ja': {
                'formal_markers': ['です', 'ます', 'であります', 'ございます'],
                'casual_markers': ['だ', 'である', 'じゃん', 'よね'],
                'honorific_levels': ['丁寧語', '尊敬語', '謙譲語']
            },
            'zh': {
                'formal_markers': ['您', '请', '敬请', '谢谢'],
                'casual_markers': ['你', '嗯', '哦', '呢'],
                'traditional_vs_simplified': True
            },
            'ko': {
                'formal_markers': ['합니다', '습니다', '입니다', '하세요'],
                'casual_markers': ['해', '야', '지', '네'],
                'honorific_system': ['높임말', '평어', '낮춤말']
            }
        }
    
    def _initialize_cultural_rules(self) -> Dict[str, Dict[str, Any]]:
        """Initialize cultural sensitivity rules."""
        return {
            'th': {
                'avoid_topics': ['monarchy', 'politics'],
                'respect_hierarchy': True,
                'buddhist_awareness': True,
                'formal_default': True
            },
            'ja': {
                'respect_hierarchy': True,
                'indirect_communication': True,
                'group_harmony': True,
                'formal_default': True
            },
            'ko': {
                'respect_hierarchy': True,
                'age_awareness': True,
                'formal_default': True,
                'avoid_japanese_references': True
            },
            'zh': {
                'respect_elders': True,
                'family_values': True,
                'harmony_emphasis': True
            },
            'en': {
                'casual_default': True,
                'direct_communication': True,
                'individual_focus': True
            }
        }
    
    def _initialize_enhancement_prompts(self) -> Dict[str, str]:
        """Initialize content enhancement prompts by language."""
        return {
            'en': {
                'clarity': "Make this content clearer and more engaging while maintaining its original meaning",
                'cultural': "Ensure this content is culturally appropriate for English-speaking audiences",
                'engagement': "Enhance this content to be more engaging and motivational",
                'formality': "Adjust the formality level of this content to be {formality_level}"
            },
            'th': {
                'clarity': "ทำให้เนื้อหานี้ชัดเจนและน่าสนใจมากขึ้นโดยรักษาความหมายเดิม",
                'cultural': "ตรวจสอบให้แน่ใจว่าเนื้อหานี้เหมาะสมทางวัฒนธรรมสำหรับผู้อ่านไทย",
                'respect': "ปรับภาษาให้มีความสุภาพและเหมาะสมตามวัฒนธรรมไทย"
            },
            'ja': {
                'clarity': "この内容をより明確で魅力的にし、元の意味を保持してください",
                'cultural': "この内容が日本の文化に適切であることを確認してください",
                'politeness': "適切な敬語レベルに調整してください"
            }
        }
    
    @monitored_operation("content_quality_analysis")
    def analyze_content_quality(self, content: str, target_language: str = "en",
                              cultural_context: Optional[Dict[str, Any]] = None) -> ContentAnalysis:
        """
        Comprehensive content quality analysis.
        
        Args:
            content: Content to analyze
            target_language: Target language code
            cultural_context: Optional cultural context
            
        Returns:
            Detailed content analysis
        """
        # Detect language
        detected_lang = self._detect_language(content)
        
        # Calculate quality scores
        quality_score = self._calculate_quality_score(content, detected_lang)
        readability_score = self._calculate_readability_score(content, detected_lang)
        engagement_score = self._calculate_engagement_potential(content, detected_lang)
        cultural_score = self._calculate_cultural_appropriateness(
            content, detected_lang, cultural_context
        )
        language_quality = self._calculate_language_quality(content, detected_lang)
        
        # Overall quality assessment
        overall_quality = (
            quality_score * 0.3 +
            readability_score * 0.2 +
            engagement_score * 0.2 +
            cultural_score * 0.15 +
            language_quality * 0.15
        )
        
        # Determine quality level
        quality_level = self._determine_quality_level(overall_quality)
        
        # Generate improvement suggestions
        suggestions = self._generate_improvement_suggestions(
            content, overall_quality, detected_lang, cultural_context
        )
        
        return ContentAnalysis(
            quality_score=round(overall_quality, 3),
            readability_score=round(readability_score, 3),
            engagement_potential=round(engagement_score, 3),
            cultural_appropriateness=round(cultural_score, 3),
            language_quality=round(language_quality, 3),
            content_length=len(content),
            detected_language=detected_lang,
            improvement_suggestions=suggestions,
            quality_level=quality_level
        )
    
    @cache_result(ttl=3600, prefix="content_enhancement")
    def enhance_content(self, content: str, target_language: str = "en",
                       enhancement_goals: List[str] = None,
                       cultural_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Enhance content quality with specific goals.
        
        Args:
            content: Original content
            target_language: Target language
            enhancement_goals: List of enhancement goals
            cultural_context: Cultural context for enhancement
            
        Returns:
            Enhanced content with improvement metrics
        """
        if not enhancement_goals:
            enhancement_goals = ['clarity', 'engagement', 'cultural']
        
        # Analyze original content
        original_analysis = self.analyze_content_quality(content, target_language, cultural_context)
        
        # Apply enhancements
        enhanced_content = content
        enhancement_log = []
        
        for goal in enhancement_goals:
            if goal in ['clarity', 'readability']:
                enhanced_content = self._enhance_clarity(enhanced_content, target_language)
                enhancement_log.append(f"Applied clarity enhancement for {target_language}")
            
            elif goal in ['engagement', 'motivation']:
                enhanced_content = self._enhance_engagement(enhanced_content, target_language)
                enhancement_log.append(f"Applied engagement enhancement")
            
            elif goal in ['cultural', 'cultural_sensitivity']:
                enhanced_content = self._enhance_cultural_appropriateness(
                    enhanced_content, target_language, cultural_context
                )
                enhancement_log.append(f"Applied cultural enhancement")
            
            elif goal in ['formality', 'tone']:
                enhanced_content = self._adjust_formality(
                    enhanced_content, target_language, cultural_context
                )
                enhancement_log.append(f"Adjusted formality level")
        
        # Analyze enhanced content
        enhanced_analysis = self.analyze_content_quality(
            enhanced_content, target_language, cultural_context
        )
        
        # Calculate improvement metrics
        improvement_metrics = self._calculate_improvement_metrics(
            original_analysis, enhanced_analysis
        )
        
        return {
            'original_content': content,
            'enhanced_content': enhanced_content,
            'original_analysis': original_analysis,
            'enhanced_analysis': enhanced_analysis,
            'improvement_metrics': improvement_metrics,
            'enhancement_log': enhancement_log,
            'enhancement_timestamp': time.time()
        }
    
    def _detect_language(self, content: str) -> ContentLanguage:
        """Detect content language using simple pattern matching."""
        # Simple language detection based on character patterns
        if re.search(r'[\u0E00-\u0E7F]', content):  # Thai
            return ContentLanguage.THAI
        elif re.search(r'[\u4E00-\u9FFF]', content):  # Chinese/Japanese
            if re.search(r'[\u3040-\u309F\u30A0-\u30FF]', content):  # Hiragana/Katakana
                return ContentLanguage.JAPANESE
            else:
                return ContentLanguage.CHINESE
        elif re.search(r'[\uAC00-\uD7AF]', content):  # Korean
            return ContentLanguage.KOREAN
        elif re.search(r'[àáâãäåèéêëìíîïòóôõöùúûüýÿ]', content):  # European accents
            if re.search(r'[ñüáéíóúç]', content):
                return ContentLanguage.SPANISH
            elif re.search(r'[àâäçéèêëïîôöùûüÿ]', content):
                return ContentLanguage.FRENCH
            elif re.search(r'[äöüß]', content):
                return ContentLanguage.GERMAN
        
        # Default to English
        return ContentLanguage.ENGLISH
    
    def _calculate_quality_score(self, content: str, language: ContentLanguage) -> float:
        """Calculate overall content quality score."""
        if not content.strip():
            return 0.0
        
        scores = []
        
        # Length appropriateness (50-200 chars optimal for Rich Messages)
        length_score = self._calculate_length_score(len(content))
        scores.append(length_score)
        
        # Sentence structure
        sentence_score = self._calculate_sentence_structure_score(content)
        scores.append(sentence_score)
        
        # Vocabulary richness
        vocab_score = self._calculate_vocabulary_score(content, language)
        scores.append(vocab_score)
        
        # Grammar and correctness (simplified)
        grammar_score = self._calculate_grammar_score(content, language)
        scores.append(grammar_score)
        
        return sum(scores) / len(scores) if scores else 0.0
    
    def _calculate_length_score(self, length: int) -> float:
        """Calculate score based on content length."""
        if 50 <= length <= 200:
            return 1.0
        elif 30 <= length < 50 or 200 < length <= 300:
            return 0.8
        elif 20 <= length < 30 or 300 < length <= 400:
            return 0.6
        elif 10 <= length < 20 or 400 < length <= 500:
            return 0.4
        else:
            return 0.2
    
    def _calculate_sentence_structure_score(self, content: str) -> float:
        """Analyze sentence structure quality."""
        sentences = re.split(r'[.!?]+', content.strip())
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if not sentences:
            return 0.0
        
        scores = []
        
        # Average sentence length
        avg_length = sum(len(s.split()) for s in sentences) / len(sentences)
        if 8 <= avg_length <= 20:
            length_score = 1.0
        elif 5 <= avg_length < 8 or 20 < avg_length <= 30:
            length_score = 0.8
        else:
            length_score = 0.6
        scores.append(length_score)
        
        # Sentence variety
        lengths = [len(s.split()) for s in sentences]
        if len(set(lengths)) > 1:
            variety_score = 0.9
        else:
            variety_score = 0.6
        scores.append(variety_score)
        
        return sum(scores) / len(scores)
    
    def _calculate_vocabulary_score(self, content: str, language: ContentLanguage) -> float:
        """Calculate vocabulary richness score."""
        words = re.findall(r'\b\w+\b', content.lower())
        if not words:
            return 0.0
        
        unique_words = set(words)
        vocabulary_ratio = len(unique_words) / len(words)
        
        # Vocabulary diversity score
        if vocabulary_ratio >= 0.8:
            return 1.0
        elif vocabulary_ratio >= 0.6:
            return 0.8
        elif vocabulary_ratio >= 0.4:
            return 0.6
        else:
            return 0.4
    
    def _calculate_grammar_score(self, content: str, language: ContentLanguage) -> float:
        """Simplified grammar quality assessment."""
        # Basic grammar checks
        grammar_score = 1.0
        
        # Check for proper capitalization
        sentences = re.split(r'[.!?]+', content.strip())
        for sentence in sentences:
            sentence = sentence.strip()
            if sentence and not sentence[0].isupper():
                grammar_score -= 0.1
        
        # Check for excessive punctuation
        punct_ratio = len(re.findall(r'[!?.,;:]', content)) / len(content) if content else 0
        if punct_ratio > 0.15:  # Too much punctuation
            grammar_score -= 0.2
        
        return max(0.0, grammar_score)
    
    def _calculate_readability_score(self, content: str, language: ContentLanguage) -> float:
        """Calculate content readability score."""
        if not content.strip():
            return 0.0
        
        # Simplified readability metrics
        words = re.findall(r'\b\w+\b', content)
        sentences = len(re.split(r'[.!?]+', content.strip()))
        
        if not words or sentences == 0:
            return 0.0
        
        avg_words_per_sentence = len(words) / sentences
        
        # Optimal range for messaging: 5-15 words per sentence
        if 5 <= avg_words_per_sentence <= 15:
            readability = 1.0
        elif 3 <= avg_words_per_sentence < 5 or 15 < avg_words_per_sentence <= 25:
            readability = 0.8
        else:
            readability = 0.6
        
        return readability
    
    def _calculate_engagement_potential(self, content: str, language: ContentLanguage) -> float:
        """Calculate content engagement potential."""
        engagement_score = 0.5  # Base score
        
        # Positive words boost engagement
        positive_words = {
            'en': ['amazing', 'awesome', 'great', 'wonderful', 'fantastic', 'excellent', 'inspiring', 'motivating'],
            'th': ['ยอดเยี่ยม', 'ดีมาก', 'สุดยอด', 'เจ๋ง', 'เยี่ยม', 'แสนดี'],
            'ja': ['素晴らしい', 'すごい', '最高', '感動', 'やる気'],
            'ko': ['훌륭한', '멋진', '최고', '감동', '대단한'],
            'zh': ['太棒了', '很好', '优秀', '激励', '精彩']
        }
        
        lang_key = language.value
        if lang_key in positive_words:
            for word in positive_words[lang_key]:
                if word.lower() in content.lower():
                    engagement_score += 0.1
        
        # Action words increase engagement
        action_words = {
            'en': ['achieve', 'succeed', 'grow', 'improve', 'transform', 'create', 'build'],
            'th': ['บรรลุ', 'สำเร็จ', 'เติบโต', 'พัฒนา', 'เปลี่ยนแปลง'],
            'ja': ['達成', '成功', '成長', '向上', '変化'],
            'ko': ['달성', '성공', '성장', '향상', '변화'],
            'zh': ['达成', '成功', '成长', '提高', '改变']
        }
        
        if lang_key in action_words:
            for word in action_words[lang_key]:
                if word.lower() in content.lower():
                    engagement_score += 0.05
        
        return min(1.0, engagement_score)
    
    def _calculate_cultural_appropriateness(self, content: str, language: ContentLanguage,
                                          cultural_context: Optional[Dict[str, Any]] = None) -> float:
        """Calculate cultural appropriateness score."""
        lang_key = language.value
        
        if lang_key not in self.cultural_rules:
            return 0.8  # Default score for languages without specific rules
        
        rules = self.cultural_rules[lang_key]
        score = 1.0
        
        # Check for cultural sensitivity violations
        if 'avoid_topics' in rules:
            for topic in rules['avoid_topics']:
                if topic.lower() in content.lower():
                    score -= 0.3
        
        # Check formality requirements
        if rules.get('formal_default') and lang_key in self.language_patterns:
            patterns = self.language_patterns[lang_key]
            has_formal = any(marker in content for marker in patterns.get('formal_markers', []))
            has_casual = any(marker in content for marker in patterns.get('casual_markers', []))
            
            if has_casual and not has_formal:
                score -= 0.2
        
        return max(0.0, score)
    
    def _calculate_language_quality(self, content: str, language: ContentLanguage) -> float:
        """Calculate language-specific quality metrics."""
        lang_key = language.value
        
        if lang_key not in self.language_patterns:
            return 0.8  # Default for unsupported languages
        
        patterns = self.language_patterns[lang_key]
        quality_score = 0.8  # Base score
        
        # Language-specific quality checks
        if 'readability_factors' in patterns:
            factors = patterns['readability_factors']
            
            # Check average sentence length
            sentences = re.split(r'[.!?]+', content.strip())
            if sentences:
                avg_length = sum(len(s.split()) for s in sentences) / len(sentences)
                target_length = factors.get('avg_sentence_length', 15)
                
                if abs(avg_length - target_length) <= 3:
                    quality_score += 0.1
        
        return min(1.0, quality_score)
    
    def _determine_quality_level(self, score: float) -> ContentQuality:
        """Determine quality level from score."""
        if score >= self.quality_thresholds['excellent']:
            return ContentQuality.EXCELLENT
        elif score >= self.quality_thresholds['good']:
            return ContentQuality.GOOD
        elif score >= self.quality_thresholds['acceptable']:
            return ContentQuality.ACCEPTABLE
        else:
            return ContentQuality.POOR
    
    def _generate_improvement_suggestions(self, content: str, quality_score: float,
                                        language: ContentLanguage,
                                        cultural_context: Optional[Dict[str, Any]] = None) -> List[str]:
        """Generate specific improvement suggestions."""
        suggestions = []
        
        # Length suggestions
        if len(content) < 30:
            suggestions.append("Content is too short. Consider adding more detail or context.")
        elif len(content) > 300:
            suggestions.append("Content is too long. Consider making it more concise.")
        
        # Quality-based suggestions
        if quality_score < 0.6:
            suggestions.append("Overall quality is low. Review grammar, vocabulary, and structure.")
        elif quality_score < 0.8:
            suggestions.append("Content quality is acceptable but could be improved.")
        
        # Language-specific suggestions
        lang_key = language.value
        if lang_key in self.cultural_rules:
            rules = self.cultural_rules[lang_key]
            
            if rules.get('formal_default'):
                if lang_key in self.language_patterns:
                    patterns = self.language_patterns[lang_key]
                    has_formal = any(marker in content for marker in patterns.get('formal_markers', []))
                    if not has_formal:
                        suggestions.append(f"Consider using more formal language appropriate for {language.value} culture.")
        
        # Engagement suggestions
        if not any(word in content.lower() for word in ['you', 'your', 'คุณ', 'あなた', '당신', '你']):
            suggestions.append("Make content more personal by addressing the reader directly.")
        
        return suggestions
    
    def _enhance_clarity(self, content: str, language: str) -> str:
        """Enhance content clarity (simplified implementation)."""
        # Basic clarity enhancements
        enhanced = content
        
        # Remove excessive punctuation
        enhanced = re.sub(r'[!]{2,}', '!', enhanced)
        enhanced = re.sub(r'[?]{2,}', '?', enhanced)
        enhanced = re.sub(r'[.]{3,}', '...', enhanced)
        
        # Ensure proper spacing
        enhanced = re.sub(r'\s+', ' ', enhanced)
        
        return enhanced.strip()
    
    def _enhance_engagement(self, content: str, language: str) -> str:
        """Enhance content engagement (simplified implementation)."""
        # Basic engagement enhancements
        enhanced = content
        
        # Ensure content ends with encouraging punctuation
        if not enhanced.endswith(('!', '?', '.')):
            enhanced += '!'
        
        return enhanced
    
    def _enhance_cultural_appropriateness(self, content: str, language: str,
                                        cultural_context: Optional[Dict[str, Any]] = None) -> str:
        """Enhance cultural appropriateness (simplified implementation)."""
        # Basic cultural enhancements would go here
        # This is a simplified version - real implementation would be more sophisticated
        return content
    
    def _adjust_formality(self, content: str, language: str,
                         cultural_context: Optional[Dict[str, Any]] = None) -> str:
        """Adjust content formality level (simplified implementation)."""
        # Basic formality adjustments would go here
        return content
    
    def _calculate_improvement_metrics(self, original: ContentAnalysis,
                                     enhanced: ContentAnalysis) -> Dict[str, float]:
        """Calculate improvement metrics between original and enhanced content."""
        return {
            'quality_improvement': enhanced.quality_score - original.quality_score,
            'readability_improvement': enhanced.readability_score - original.readability_score,
            'engagement_improvement': enhanced.engagement_potential - original.engagement_potential,
            'cultural_improvement': enhanced.cultural_appropriateness - original.cultural_appropriateness,
            'language_improvement': enhanced.language_quality - original.language_quality,
            'overall_improvement': (
                (enhanced.quality_score - original.quality_score) +
                (enhanced.readability_score - original.readability_score) +
                (enhanced.engagement_potential - original.engagement_potential)
            ) / 3
        }


# Global content quality enhancer instance
content_quality_enhancer = ContentQualityEnhancer()