"""
Rich Message Service for LINE Bot automation

This service handles the creation, management, and delivery of Rich Messages
with automated content generation and template-based graphics.
"""

import json
import logging
import os
import glob
from typing import Dict, List, Optional, Any, Union, Tuple
from datetime import datetime, timedelta
import hashlib
import time
from src.utils.redis_manager import get_redis_manager, RedisConnectionManager
from src.utils.lru_cache_manager import get_lru_cache, CacheType
from linebot.models import (
    RichMenu, RichMenuSize, RichMenuArea, RichMenuBounds,
    PostbackAction, URIAction, MessageAction,
    FlexSendMessage, BubbleContainer, ImageComponent,
    BoxComponent, TextComponent, ButtonComponent
)
from linebot.exceptions import LineBotApiError

logger = logging.getLogger(__name__)


class RichMessageService:
    """Service for managing Rich Message automation and delivery"""
    
    def __init__(self, 
                 line_bot_api: Any,  # LineBotApi type
                 template_manager: Optional[Any] = None,
                 content_generator: Optional[Any] = None, 
                 base_url: Optional[str] = None,
                 openai_service: Optional[Any] = None,
                 redis_url: Optional[str] = None,
                 enable_redis: bool = True) -> None:
        """
        Initialize Rich Message Service
        
        Args:
            line_bot_api: LINE Bot API instance for sending messages
            template_manager: Template management utility (optional)
            content_generator: Content generation utility (optional)
            base_url: Base URL for generating image links (optional)
            openai_service: OpenAI service for Bourdain-style content generation (optional)
            redis_url: Redis connection URL (optional)
            enable_redis: Whether to enable Redis functionality
        """
        # Validate required parameters
        if not line_bot_api:
            raise ValueError("line_bot_api is required for RichMessageService")
        
        self.line_bot_api = line_bot_api
        
        self.template_manager = template_manager
        self.content_generator = content_generator
        self.base_url = base_url
        
        # Initialize Bourdain-style content generator
        self.openai_service = openai_service  # Store reference for interaction handler
        if not self.content_generator and openai_service:
            from src.utils.rich_message_content_generator import RichMessageContentGenerator
            self.content_generator = RichMessageContentGenerator(openai_service)
            logger.info("Initialized RichMessageContentGenerator with Bourdain persona")
        elif not self.content_generator:
            logger.warning("No OpenAI service provided - conversation triggers will use fallback responses")
        
        # Rich Menu dimensions for LINE
        self.RICH_MENU_WIDTH = 2500
        self.RICH_MENU_HEIGHT = 1686
        
        # Initialize Rich Menu configurations
        self._rich_menu_configs = self._load_rich_menu_configs()
        
        # Initialize Redis connection manager with graceful fallback
        self.enable_redis = enable_redis
        self.redis_manager: Optional[RedisConnectionManager] = None
        self._redis_available = False
        self._last_redis_check = None
        self._redis_check_interval = 60  # Check Redis health every 60 seconds
        
        if self.enable_redis:
            self._initialize_redis(redis_url)
        
        # Initialize LRU caching system with memory monitoring
        self.content_cache = get_lru_cache(
            name=f"rich_content_{id(self)}",
            max_size=200,
            max_memory_mb=50.0,
            default_ttl=3600,  # 1 hour TTL
            enable_memory_monitoring=True
        )
        
        self.mood_cache = get_lru_cache(
            name=f"rich_mood_{id(self)}",
            max_size=500,
            max_memory_mb=10.0,
            default_ttl=24*3600,  # 24 hour TTL (moods don't change often)
            enable_memory_monitoring=True
        )
        
        # Legacy fallback caches for Redis operations
        self._content_cache = {}  # For Redis fallback compatibility
        self._mood_cache = {}     # For Redis fallback compatibility
        self._cache_ttl = 3600    # Keep for Redis operations
        
        # Initialize send rate limiting system (in-memory fallback)
        self._send_history = {}   # Track last send times per user
        self._send_cooldown = 300 # 5 minutes cooldown between Rich Messages per user
        self._daily_send_limits = {} # Track daily send counts per user
        self._max_daily_sends = 10   # Maximum Rich Messages per user per day
        
        # Initialize button context storage (in-memory fallback)
        self._button_context_storage = {}
        
        # Log initialization status
        cache_backend = "Redis" if self._redis_available else "LRU+in-memory"
        logger.info(f"RichMessageService initialized with {cache_backend} caching, LRU eviction, and send rate limiting enabled")
    
    def _initialize_redis(self, redis_url: str = None):
        """Initialize Redis connection manager."""
        try:
            self.redis_manager = get_redis_manager(redis_url=redis_url)
            health_status = self.redis_manager.health_check()
            self._redis_available = health_status.get('is_healthy', False)
            self._last_redis_check = datetime.now()
            
            if self._redis_available:
                logger.info("RichMessageService initialized with Redis backend")
            else:
                logger.warning("Redis health check failed, using in-memory fallback")
                
        except Exception as e:
            logger.error(f"Failed to initialize Redis for RichMessageService: {e}")
            self._redis_available = False
    
    def _check_redis_health(self) -> bool:
        """Check Redis health periodically."""
        if not self.enable_redis or not self.redis_manager:
            return False
        
        now = datetime.now()
        if (self._last_redis_check and 
            (now - self._last_redis_check).total_seconds() < self._redis_check_interval):
            return self._redis_available
        
        try:
            health_status = self.redis_manager.health_check()
            self._redis_available = health_status.get('is_healthy', False)
            self._last_redis_check = now
            
            if self._redis_available:
                logger.debug("Redis connection healthy for RichMessageService")
            else:
                logger.warning("Redis connection degraded for RichMessageService")
                
        except Exception as e:
            logger.error(f"Redis health check failed in RichMessageService: {e}")
            self._redis_available = False
            
        return self._redis_available
    
    def _get_cache_key(self, theme: str, template_name: Optional[str] = None, user_context: Optional[str] = None) -> str:
        """Generate cache key for content generation parameters"""
        key_data = f"{theme}:{template_name or 'none'}:{user_context or 'none'}"
        return hashlib.md5(key_data.encode()).hexdigest()[:16]
    
    def _get_cached_content(self, cache_key: str) -> Optional[Dict[str, str]]:
        """Retrieve cached content with LRU -> Redis -> in-memory fallback hierarchy"""
        try:
            # Try LRU cache first (fastest and most intelligent)
            lru_result = self.content_cache.get(cache_key)
            if lru_result is not None:
                logger.debug(f"LRU cache hit for key: {cache_key}")
                return lru_result
            
            # Try Redis if available
            if self._check_redis_health():
                def redis_operation(client):
                    full_key = f"rich_content:{cache_key}"
                    data = client.get(full_key)
                    if data:
                        try:
                            cached_item = json.loads(data.decode('utf-8'))
                            if isinstance(cached_item, dict) and 'timestamp' in cached_item and 'content' in cached_item:
                                if time.time() - cached_item['timestamp'] < self._cache_ttl:
                                    # Cache in LRU for future requests
                                    self.content_cache.put(cache_key, cached_item['content'], cache_type=CacheType.CONTENT)
                                    return cached_item['content']
                        except (json.JSONDecodeError, KeyError) as e:
                            logger.warning(f"Invalid cached content format for key {cache_key}: {e}")
                    return None
                
                def fallback():
                    return None
                
                result = self.redis_manager.execute_with_fallback(
                    redis_operation, fallback, f"get_cached_content_{cache_key}"
                )
                
                if result is not None:
                    logger.debug(f"Redis cache hit for key: {cache_key}")
                    return result
            
            # Fallback to legacy in-memory cache
            if cache_key in self._content_cache:
                cached_item = self._content_cache[cache_key]
                if isinstance(cached_item, dict) and 'timestamp' in cached_item and 'content' in cached_item:
                    if time.time() - cached_item['timestamp'] < self._cache_ttl:
                        logger.debug(f"Legacy memory cache hit for key: {cache_key}")
                        # Migrate to LRU cache
                        self.content_cache.put(cache_key, cached_item['content'], cache_type=CacheType.CONTENT)
                        return cached_item['content']
                    else:
                        # Cache expired, remove it
                        del self._content_cache[cache_key]
                        logger.debug(f"Cache expired for key: {cache_key}")
                else:
                    # Invalid cache entry, remove it
                    del self._content_cache[cache_key]
                    logger.warning(f"Invalid cache entry removed for key: {cache_key}")
        except Exception as e:
            logger.error(f"Error retrieving cached content for key {cache_key}: {str(e)}")
        return None
    
    def _cache_content(self, cache_key: str, content: Dict[str, str]) -> None:
        """Cache generated content with LRU -> Redis -> in-memory hierarchy"""
        try:
            # Validate content before caching
            if not isinstance(content, dict) or 'title' not in content or 'content' not in content:
                logger.warning(f"Invalid content format for caching, key: {cache_key}")
                return
            
            # Cache in LRU first (most efficient)
            lru_success = self.content_cache.put(cache_key, content, cache_type=CacheType.CONTENT)
            if lru_success:
                logger.debug(f"Cached content in LRU cache for key: {cache_key}")
            
            # Also cache in Redis for persistence across restarts
            if self._check_redis_health():
                cache_item = {
                    'content': content,
                    'timestamp': time.time()
                }
                
                def redis_operation(client):
                    full_key = f"rich_content:{cache_key}"
                    serialized_data = json.dumps(cache_item)
                    return client.setex(full_key, self._cache_ttl, serialized_data)
                
                def fallback():
                    return False
                
                success = self.redis_manager.execute_with_fallback(
                    redis_operation, fallback, f"cache_content_{cache_key}"
                )
                
                if success:
                    logger.debug(f"Cached content in Redis for key: {cache_key}")
                    return
            
            # Fallback to legacy in-memory cache only if LRU failed
            if not lru_success:
                cache_item = {
                    'content': content,
                    'timestamp': time.time()
                }
                
                # Clean cache if it's getting too large (legacy logic)
                max_cache_size = getattr(self, '_max_cache_size', 100)
                if len(self._content_cache) >= max_cache_size:
                    self._clean_old_cache_entries()
                
                self._content_cache[cache_key] = cache_item
                logger.debug(f"Cached content in legacy memory for key: {cache_key}")
        except Exception as e:
            logger.error(f"Error caching content for key {cache_key}: {str(e)}")
    
    def _clean_old_cache_entries(self) -> None:
        """Remove oldest cache entries to make room"""
        current_time = time.time()
        # Remove expired entries first
        expired_keys = [
            key for key, value in self._content_cache.items()
            if current_time - value['timestamp'] > self._cache_ttl
        ]
        for key in expired_keys:
            del self._content_cache[key]
        
        # If still too large, remove oldest entries
        if len(self._content_cache) >= self._max_cache_size:
            sorted_items = sorted(
                self._content_cache.items(),
                key=lambda x: x[1]['timestamp']
            )
            # Remove oldest 20% of entries
            remove_count = max(1, len(sorted_items) // 5)
            for key, _ in sorted_items[:remove_count]:
                del self._content_cache[key]
        
        logger.debug(f"Cache cleanup completed, {len(self._content_cache)} entries remaining")
    
    def check_send_rate_limit(self, user_id: str, bypass_limit: bool = False) -> Dict[str, Any]:
        """
        Check if user can receive a Rich Message based on rate limiting rules with Redis fallback.
        
        Args:
            user_id: User identifier
            bypass_limit: If True, bypasses rate limiting (for admin/testing)
            
        Returns:
            Dictionary with 'allowed', 'reason', and timing information
        """
        if bypass_limit:
            logger.info(f"Rate limit bypassed for user {user_id[:8]}...")
            return {"allowed": True, "reason": "bypassed", "next_allowed": None}
        
        current_time = time.time()
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Get rate limit data with Redis fallback
        send_history = self._get_rate_limit_data(user_id, "send_history")
        daily_limits = self._get_rate_limit_data(user_id, "daily_limits", today)
        
        # Check cooldown period
        if send_history:
            time_since_last = current_time - send_history
            if time_since_last < self._send_cooldown:
                remaining_cooldown = self._send_cooldown - time_since_last
                next_allowed = datetime.fromtimestamp(current_time + remaining_cooldown)
                
                logger.warning(f"Rate limit hit for user {user_id[:8]}...: {remaining_cooldown:.0f}s remaining")
                return {
                    "allowed": False,
                    "reason": "cooldown",
                    "remaining_seconds": remaining_cooldown,
                    "next_allowed": next_allowed.strftime('%H:%M:%S')
                }
        
        # Check daily limit
        daily_count = daily_limits if daily_limits else 0
        
        if daily_count >= self._max_daily_sends:
            logger.warning(f"Daily limit reached for user {user_id[:8]}...: {daily_count}/{self._max_daily_sends}")
            return {
                "allowed": False,
                "reason": "daily_limit", 
                "daily_count": daily_count,
                "max_daily": self._max_daily_sends,
                "next_allowed": "tomorrow"
            }
        
        # Rate limit passed
        return {"allowed": True, "reason": "within_limits", "daily_count": daily_count}
    
    def record_message_sent(self, user_id: str) -> None:
        """Record that a Rich Message was sent to user for rate limiting with Redis fallback."""
        current_time = time.time()
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Update send history with Redis fallback
        self._set_rate_limit_data(user_id, "send_history", current_time)
        
        # Update daily count with Redis fallback
        current_daily_count = self._get_rate_limit_data(user_id, "daily_limits", today) or 0
        new_daily_count = current_daily_count + 1
        self._set_rate_limit_data(user_id, "daily_limits", new_daily_count, today)
        
        # Cleanup old daily records from in-memory fallback (Redis TTL handles its own cleanup)
        if not self._redis_available:
            self._cleanup_old_daily_records()
        
        logger.info(f"Recorded Rich Message send for user {user_id[:8]}... (daily: {new_daily_count}/{self._max_daily_sends})")
    
    def get_send_status(self, user_id: str) -> Dict[str, Any]:
        """Get current send status and history for a user."""
        current_time = time.time()
        today = datetime.now().strftime('%Y-%m-%d')
        daily_key = f"{user_id}:{today}"
        
        status = {
            "user_id": user_id[:8] + "...",
            "last_send": None,
            "time_since_last": None,
            "daily_count": self._daily_send_limits.get(daily_key, 0),
            "max_daily": self._max_daily_sends,
            "cooldown_remaining": 0,
            "can_send_now": True
        }
        
        if user_id in self._send_history:
            last_send_time = self._send_history[user_id]
            status["last_send"] = datetime.fromtimestamp(last_send_time).strftime('%Y-%m-%d %H:%M:%S')
            status["time_since_last"] = current_time - last_send_time
            
            if status["time_since_last"] < self._send_cooldown:
                status["cooldown_remaining"] = self._send_cooldown - status["time_since_last"]
                status["can_send_now"] = False
        
        if status["daily_count"] >= self._max_daily_sends:
            status["can_send_now"] = False
        
        return status
    
    def generate_bourdain_content(self, 
                                theme: str = "motivation",
                                template_name: Optional[str] = None,
                                user_context: Optional[str] = None) -> Dict[str, str]:
        """
        Generate Rich Message content using Anthony Bourdain's persona with multi-tier fallback system
        
        Args:
            theme: Content theme (productivity, wellness, motivation, inspiration, food, travel)
            template_name: Name of the template being used (for mood context)
            user_context: Optional user context for personalization
            
        Returns:
            Dictionary with 'title' and 'content' keys in Bourdain's authentic voice
        """
        # Check cache first (only for AI-generated content, not user-specific context)
        if not user_context:  # Only cache non-personalized content
            cache_key = self._get_cache_key(theme, template_name, user_context)
            cached_content = self._get_cached_content(cache_key)
            if cached_content:
                logger.info(f"Returning cached Bourdain content for theme: {theme}")
                return cached_content
        
        fallback_tier = 0
        template_mood = self._extract_template_mood(template_name) if template_name else None
        
        # Tier 1: Full AI Generation with OpenAI service
        if self.content_generator:
            try:
                fallback_tier = 1
                logger.debug(f"Attempting Tier 1 content generation for theme: {theme}")
                
                content = self.content_generator.generate_rich_message_content(
                    theme=theme,
                    template_mood=template_mood,
                    user_context=user_context
                )
                
                # Validate content meets Rich Message constraints
                if self.content_generator.validate_content_length(content['title'], content['content']):
                    logger.info(f"Tier 1 success: Generated Bourdain-style Rich Message content for theme: {theme}")
                    # Cache successful AI-generated content (if not user-specific)
                    if not user_context:
                        cache_key = self._get_cache_key(theme, template_name, user_context)
                        self._cache_content(cache_key, content)
                    return content
                else:
                    logger.warning("Tier 1 failed: Generated content too long, degrading to Tier 2")
                    
            except Exception as e:
                logger.warning(f"Tier 1 failed: AI generation error: {str(e)}, degrading to Tier 2")
        
        # Tier 2: AI Regeneration with stricter constraints
        if self.content_generator:
            try:
                fallback_tier = 2
                logger.debug(f"Attempting Tier 2 content generation with strict constraints")
                
                # Try again with stricter length requirements
                content = self.content_generator.generate_rich_message_content(
                    theme=theme,
                    template_mood=template_mood,
                    user_context="Keep it very short and punchy" + (f" {user_context}" if user_context else "")
                )
                
                # Force truncate if still too long
                if content and content.get('title') and content.get('content'):
                    title = content['title'][:50]  # Hard limit
                    content_text = content['content'][:200]  # Stricter limit
                    
                    if len(title) > 0 and len(content_text) > 50:  # Minimum viability check
                        logger.info(f"Tier 2 success: Generated constrained Bourdain content for theme: {theme}")
                        return {"title": title, "content": content_text}
                
                logger.warning("Tier 2 failed: Content still invalid, degrading to Tier 3")
                    
            except Exception as e:
                logger.warning(f"Tier 2 failed: AI regeneration error: {str(e)}, degrading to Tier 3")
        
        # Tier 3: Curated premium fallback with mood adaptation
        try:
            fallback_tier = 3
            logger.debug(f"Attempting Tier 3 premium fallback with mood adaptation")
            
            premium_content = self._get_premium_bourdain_content(theme, template_mood)
            if premium_content:
                logger.info(f"Tier 3 success: Using premium curated Bourdain content for theme: {theme}")
                return premium_content
                
        except Exception as e:
            logger.warning(f"Tier 3 failed: Premium fallback error: {str(e)}, degrading to Tier 4")
        
        # Tier 4: Emergency fallback (always works)
        fallback_tier = 4
        logger.warning(f"All higher tiers failed, using Tier 4 emergency fallback for theme: {theme}")
        return self._get_emergency_bourdain_content(theme)
    
    def _get_premium_bourdain_content(self, theme: str, template_mood: Optional[str] = None) -> Optional[Dict[str, str]]:
        """Premium curated Bourdain content with mood adaptation"""
        
        # Base premium content with higher quality than emergency fallback
        premium_content = {
            "productivity": [
                {
                    "title": "☕ Real Craft",
                    "content": "Productivity isn't about apps. It's about finding someone who's mastered their craft and learning how they think.",
                    "moods": ["energetic and focused", "authentic and conversational"]
                },
                {
                    "title": "🎯 Focus Truth",
                    "content": "Best work happens when you stop optimizing and start doing. Find your rhythm, ignore the noise.",
                    "moods": ["sharp and precise", "authentic and conversational"]
                }
            ],
            "wellness": [
                {
                    "title": "🚶‍♂️ Real Healing",
                    "content": "Wellness isn't a subscription. It's sharing a meal, having honest conversation, taking time to breathe.",
                    "moods": ["contemplative and grounded", "authentic and human"]
                },
                {
                    "title": "🌱 Human Truth",
                    "content": "Self-care is overrated. People-care isn't. Connect with someone real today.",
                    "moods": ["authentic and human", "contemplative and grounded"]
                }
            ],
            "motivation": [
                {
                    "title": "🔥 Earned Wisdom",
                    "content": "Real motivation comes from people with scars, not people with perfect Instagram feeds. Trust the struggle.",
                    "moods": ["honest and encouraging", "authentic and conversational"]
                },
                {
                    "title": "⚡ Street Truth",
                    "content": "Motivation without experience is just noise. Find mentors who've actually done the work.",
                    "moods": ["bold and artistic", "honest and encouraging"]
                }
            ],
            "inspiration": [
                {
                    "title": "✨ Real Stories",
                    "content": "Inspiration lives in the night shift nurse, the street vendor, the single mom. Listen to them.",
                    "moods": ["authentic and human", "contemplative and grounded"]
                },
                {
                    "title": "🎨 Authentic Art",
                    "content": "Best creativity comes from necessity, not leisure. Make something that matters.",
                    "moods": ["bold and artistic", "honest and encouraging"]
                }
            ]
        }
        
        theme_options = premium_content.get(theme, premium_content["motivation"])
        
        # Select content based on mood compatibility
        if template_mood:
            for option in theme_options:
                if template_mood in option.get("moods", []):
                    logger.debug(f"Selected mood-matched premium content: {template_mood}")
                    return {"title": option["title"], "content": option["content"]}
        
        # Fallback to first option if no mood match
        import random
        selected = random.choice(theme_options)
        return {"title": selected["title"], "content": selected["content"]}
    
    def _extract_template_mood(self, template_name: str) -> str:
        """Extract mood context from template name using weighted scoring system"""
        if not template_name or not isinstance(template_name, str):
            return "authentic and conversational"
        
        try:
            # Check mood cache first with Redis fallback
            cached_mood = self._get_mood_cache(template_name)
            if cached_mood:
                logger.debug(f"Mood cache hit for template: {template_name}")
                return cached_mood
                
            template_lower = template_name.lower()
            
            # Enhanced mood mapping with keywords and weights
            mood_keywords = {
                "energetic and focused": {
                    "keywords": ["coffee", "morning", "energy", "focus", "work", "productivity"],
                    "weights": [3.0, 2.5, 2.0, 2.5, 1.5, 2.0]
                },
                "contemplative and grounded": {
                    "keywords": ["nature", "forest", "mountain", "zen", "peaceful", "calm", "meditation"],
                    "weights": [3.0, 2.5, 2.5, 2.0, 2.0, 2.0, 2.0]
                },
                "bold and artistic": {
                    "keywords": ["abstract", "geometric", "art", "creative", "modern", "design"],
                    "weights": [3.0, 3.0, 2.5, 2.0, 1.5, 2.0]
                },
                "reflective and warm": {
                    "keywords": ["sunset", "evening", "golden", "warm", "reflection", "twilight"],
                    "weights": [3.0, 2.5, 2.0, 2.0, 2.5, 2.5]
                },
                "energetic and hopeful": {
                    "keywords": ["sunrise", "dawn", "bright", "new", "fresh", "beginning"],
                    "weights": [3.0, 2.5, 2.0, 2.0, 2.0, 2.5]
                },
                "authentic and human": {
                    "keywords": ["wellness", "people", "community", "real", "honest", "genuine"],
                    "weights": [3.0, 2.0, 2.0, 2.5, 2.5, 2.5]
                },
                "sharp and precise": {
                    "keywords": ["minimal", "clean", "simple", "line", "sharp", "precise"],
                    "weights": [2.5, 2.0, 2.0, 2.0, 3.0, 3.0]
                },
                "honest and encouraging": {
                    "keywords": ["motivation", "inspire", "strength", "courage", "hope", "determination"],
                    "weights": [3.0, 2.5, 2.0, 2.0, 2.0, 2.0]
                }
            }
            
            # Calculate scores for each mood
            mood_scores = {}
            for mood, data in mood_keywords.items():
                score = 0.0
                keywords = data["keywords"]
                weights = data["weights"]
                
                for keyword, weight in zip(keywords, weights):
                    if keyword in template_lower:
                        # Bonus for exact matches vs partial matches
                        if keyword == template_lower or f"_{keyword}_" in f"_{template_lower}_":
                            score += weight * 1.5  # Exact match bonus
                        else:
                            score += weight
                
                if score > 0:
                    mood_scores[mood] = score
            
            # Return mood with highest score, or default if no matches
            if mood_scores:
                best_mood = max(mood_scores.items(), key=lambda x: x[1])
                detected_mood = best_mood[0]
                logger.debug(f"Template mood detection: '{template_name}' → '{detected_mood}' (score: {best_mood[1]:.1f})")
            else:
                detected_mood = "authentic and conversational"
                logger.debug(f"Template mood detection: '{template_name}' → default mood (no matches)")
            
            # Cache the detected mood with Redis fallback
            self._set_mood_cache(template_name, detected_mood)
            return detected_mood
        
        except Exception as e:
            logger.error(f"Error detecting mood for template '{template_name}': {str(e)}")
            return "authentic and conversational"
    
    def _get_emergency_bourdain_content(self, theme: str) -> Dict[str, str]:
        """Emergency fallback content with multiple variations and rotation"""
        import random
        import time
        
        # Multiple high-quality emergency variations for each theme
        emergency_variations = {
            "productivity": [
                {
                    "title": "☕ Real Work",
                    "content": "Skip the productivity porn. Find people who actually do the work. Learn from them."
                },
                {
                    "title": "🔧 Honest Craft",
                    "content": "Real productivity is a line cook during rush hour. No apps, no hacks. Just focus and repetition."
                },
                {
                    "title": "⚡ Cut the Noise",
                    "content": "Half your tools are useless. Find what works. Do that. Ignore everything else."
                }
            ],
            "wellness": [
                {
                    "title": "🚶‍♂️ Honest Wellness", 
                    "content": "Real wellness isn't in an app. It's a walk, a conversation, time to think."
                },
                {
                    "title": "🍽️ Simple Truth",
                    "content": "Wellness is sharing a meal with someone you care about. Everything else is marketing."
                },
                {
                    "title": "🌱 Human Connection",
                    "content": "Self-care culture is bullshit. Care about people. That's where healing happens."
                }
            ],
            "motivation": [
                {
                    "title": "🔥 No Bullshit",
                    "content": "Motivation from people who've never failed is worthless. Trust your scars."
                },
                {
                    "title": "💪 Real Strength",
                    "content": "Strength comes from showing up when everything's falling apart. Not when it's easy."
                },
                {
                    "title": "🛤️ Your Path",
                    "content": "Stop following someone else's blueprint. Your journey looks different because you're not them."
                }
            ],
            "inspiration": [
                {
                    "title": "✨ Real Stories",
                    "content": "Best stories come from taxi drivers and street vendors. Listen to them."
                },
                {
                    "title": "🎭 Authentic Moments",
                    "content": "Inspiration happens at 3 AM in a diner with someone who's seen everything. Seek that."
                },
                {
                    "title": "🌍 Street Wisdom",
                    "content": "Real wisdom lives in the margins. Find the people nobody else talks to."
                }
            ],
            "food": [
                {
                    "title": "🍜 Honest Food",
                    "content": "Best meals happen at plastic tables with questionable hygiene. That's where the soul is."
                },
                {
                    "title": "🌮 Street Truth",
                    "content": "Michelin stars are nice. But the taco truck at 2 AM? That's where culture lives."
                },
                {
                    "title": "🥢 Real Flavor",
                    "content": "Great food comes from necessity, not Instagram. Find the hunger behind the dish."
                }
            ],
            "travel": [
                {
                    "title": "🗺️ Real Places",
                    "content": "Tourist traps are bullshit. Find where locals eat. That's where culture lives."
                },
                {
                    "title": "🚌 Off the Map",
                    "content": "Best experiences happen when you get lost. GPS kills adventure."
                },
                {
                    "title": "👥 Human Stories",
                    "content": "Travel isn't about places. It's about the people who show you how they live."
                }
            ]
        }
        
        # Get variations for the theme, fallback to motivation if theme not found
        theme_variations = emergency_variations.get(theme, emergency_variations["motivation"])
        
        # Time-based rotation to ensure variety while maintaining consistency
        # Uses current hour + day to create a semi-predictable but rotating selection
        current_time = time.time()
        hour_day_seed = int((current_time // 3600) % (24 * 7))  # Weekly rotation cycle
        variation_index = hour_day_seed % len(theme_variations)
        
        selected_variation = theme_variations[variation_index]
        
        logger.debug(f"Emergency content rotation: theme={theme}, variation={variation_index+1}/{len(theme_variations)}")
        return selected_variation
    
    def discover_available_images(self) -> List[str]:
        """Dynamically discover all available background images"""
        try:
            # Default templates path
            templates_path = "/home/runner/workspace/templates/rich_messages/backgrounds/*.png"
            available_images = glob.glob(templates_path)
            
            logger.debug(f"Discovered {len(available_images)} background images")
            return available_images
        except Exception as e:
            logger.error(f"Error discovering images: {str(e)}")
            return []
    
    def calculate_context_score(self, filename: str, context: Dict[str, Any]) -> float:
        """Calculate how well an image filename matches the current context"""
        try:
            filename_lower = filename.lower()
            score = 0.0
            
            # Time-based scoring
            time_patterns = {
                'morning': ['morning', 'coffee', 'dawn', 'breakfast'],
                'afternoon': ['afternoon', 'lunch', 'midday', 'work'],
                'evening': ['evening', 'sunset', 'dinner', 'twilight'],
                'night': ['night', 'late', 'moon', 'dark']
            }
            
            current_time_period = context.get('time_period', '')
            if current_time_period and current_time_period in time_patterns:
                for pattern in time_patterns[current_time_period]:
                    if pattern in filename_lower:
                        score += 2.5
                        logger.debug(f"Time match '{pattern}' in {filename}: +2.5")
            
            # Day of week scoring
            day_patterns = {
                'monday': ['monday', 'start', 'begin'],
                'tuesday': ['tuesday'],
                'wednesday': ['wednesday', 'middle', 'mid'],
                'thursday': ['thursday'],
                'friday': ['friday', 'end', 'finish'],
                'saturday': ['saturday', 'weekend'],
                'sunday': ['sunday', 'weekend']
            }
            
            current_day = context.get('day_of_week', '').lower()
            if current_day in day_patterns:
                for pattern in day_patterns[current_day]:
                    if pattern in filename_lower:
                        score += 3.0
                        logger.debug(f"Day match '{pattern}' in {filename}: +3.0")
            
            # Theme scoring (main theme gets priority)
            theme = context.get('theme', '').lower()
            if theme in filename_lower:
                score += 2.0
                logger.debug(f"Theme match '{theme}' in {filename}: +2.0")
            
            # Context-specific patterns
            context_patterns = {
                'work': ['workspace', 'office', 'desk', 'computer', 'productivity'],
                'relax': ['nature', 'calm', 'peaceful', 'zen', 'wellness'],
                'energy': ['energy', 'power', 'strong', 'motivation', 'active'],
                'creative': ['art', 'creative', 'design', 'inspiration', 'artistic'],
                'focus': ['focus', 'concentration', 'sharp', 'precise', 'minimal']
            }
            
            user_context = context.get('user_context', '').lower()
            if user_context in context_patterns:
                for pattern in context_patterns[user_context]:
                    if pattern in filename_lower:
                        score += 1.5
                        logger.debug(f"Context match '{pattern}' in {filename}: +1.5")
            
            # Mood scoring
            mood_patterns = {
                'energetic': ['energy', 'active', 'running', 'power', 'strong'],
                'calm': ['calm', 'peaceful', 'nature', 'zen', 'quiet'],
                'motivated': ['motivation', 'goal', 'achievement', 'success'],
                'creative': ['creative', 'art', 'design', 'inspiration'],
                'focused': ['focus', 'work', 'productivity', 'sharp']
            }
            
            desired_mood = context.get('mood', '').lower()
            if desired_mood in mood_patterns:
                for pattern in mood_patterns[desired_mood]:
                    if pattern in filename_lower:
                        score += 1.0
                        logger.debug(f"Mood match '{pattern}' in {filename}: +1.0")
            
            # Activity-specific scoring
            if 'hiking' in filename_lower and current_day in ['saturday', 'sunday']:
                score += 1.0
            if 'coffee' in filename_lower and current_time_period == 'morning':
                score += 1.5
            if 'workspace' in filename_lower and current_time_period in ['morning', 'afternoon']:
                score += 1.0
            
            logger.debug(f"Total score for {os.path.basename(filename)}: {score:.1f}")
            return score
            
        except Exception as e:
            logger.error(f"Error calculating context score for {filename}: {str(e)}")
            return 0.0
    
    def select_contextual_image(self, theme: str, user_context: Optional[str] = None) -> Optional[str]:
        """Smart selection of background image based on current context"""
        try:
            # Build context from current time and provided parameters
            now = datetime.now()
            hour = now.hour
            day_of_week = now.strftime('%A').lower()
            
            # Determine time period
            if 5 <= hour < 12:
                time_period = 'morning'
            elif 12 <= hour < 17:
                time_period = 'afternoon'
            elif 17 <= hour < 22:
                time_period = 'evening'
            else:
                time_period = 'night'
            
            context = {
                'theme': theme,
                'day_of_week': day_of_week,
                'time_period': time_period,
                'hour': hour,
                'user_context': user_context or 'general'
            }
            
            logger.info(f"Selecting image for context: {context}")
            
            # Discover available images
            available_images = self.discover_available_images()
            if not available_images:
                logger.warning("No background images found")
                return None
            
            # Score each image based on context
            image_scores = {}
            for image_path in available_images:
                score = self.calculate_context_score(image_path, context)
                if score > 0:  # Only consider images with positive scores
                    image_scores[image_path] = score
            
            if not image_scores:
                # No contextual matches, filter by theme and pick randomly
                theme_matches = [img for img in available_images if theme.lower() in os.path.basename(img).lower()]
                if theme_matches:
                    import random
                    selected = random.choice(theme_matches)
                    logger.info(f"No context matches, selected random theme match: {os.path.basename(selected)}")
                    return selected
                else:
                    # Absolutely no matches, pick any random image
                    import random
                    selected = random.choice(available_images)
                    logger.info(f"No matches at all, selected random image: {os.path.basename(selected)}")
                    return selected
            
            # Select highest scoring image
            best_image = max(image_scores.items(), key=lambda x: x[1])
            selected_image = best_image[0]
            best_score = best_image[1]
            
            logger.info(f"Smart selection: {os.path.basename(selected_image)} (score: {best_score:.1f})")
            return selected_image
            
        except Exception as e:
            logger.error(f"Error in contextual image selection: {str(e)}")
            return None
    
    def generate_image_aware_content(self, 
                                   theme: str = "motivation",
                                   user_context: Optional[str] = None,
                                   force_ai_generation: bool = True) -> Dict[str, Any]:
        """Generate content that's aware of the selected background image context"""
        try:
            # Step 1: Smart image selection based on context
            selected_image_path = self.select_contextual_image(theme, user_context)
            if not selected_image_path:
                logger.error("No image could be selected")
                return {
                    "title": "🎯 Real Talk",
                    "content": "Something went wrong with image selection, but the conversation continues.",
                    "image_path": None,
                    "generation_tier": "error"
                }
            
            # Step 2: Extract image context for AI prompt
            image_filename = os.path.basename(selected_image_path)
            image_context = self._extract_image_context(image_filename)
            
            # Step 3: Generate content based on the selected image
            if force_ai_generation and self.content_generator:
                try:
                    logger.info(f"Generating AI content for image: {image_filename}")
                    
                    # Build rich prompt describing the image context
                    image_prompt = f"""
Based on the background image '{image_filename}', generate Bourdain-style Rich Message content.

IMAGE CONTEXT: {image_context['description']}
VISUAL MOOD: {image_context['mood']}
THEME: {theme}
USER CONTEXT: {user_context or 'general'}

Create content that connects to this specific visual context. Make Bourdain's voice match the energy and setting of the image.
                    """
                    
                    content = self.content_generator.generate_rich_message_content(
                        theme=theme,
                        template_mood=image_context['mood'],
                        user_context=image_prompt
                    )
                    
                    if content and self.content_generator.validate_content_length(content['title'], content['content']):
                        logger.info(f"Successfully generated image-aware content for {image_filename}")
                        return {
                            "title": content['title'],
                            "content": content['content'],
                            "image_path": selected_image_path,
                            "image_context": image_context,
                            "generation_tier": "ai_image_aware"
                        }
                
                except Exception as e:
                    logger.warning(f"AI image-aware generation failed: {str(e)}")
            
            # Fallback: Use regular content generation with image mood
            template_mood = self._extract_template_mood(image_filename)
            fallback_content = self.generate_bourdain_content(theme, image_filename, user_context)
            
            return {
                "title": fallback_content['title'],
                "content": fallback_content['content'],
                "image_path": selected_image_path,
                "image_context": image_context,
                "generation_tier": "fallback_with_image"
            }
            
        except Exception as e:
            logger.error(f"Error in image-aware content generation: {str(e)}")
            return self._get_emergency_bourdain_content(theme)
    
    def _extract_image_context(self, filename: str) -> Dict[str, str]:
        """Extract rich context from image filename for AI prompt generation"""
        try:
            filename_lower = filename.lower()
            
            # Build contextual description
            description_parts = []
            mood_indicators = []
            
            # Time and day context
            if 'monday' in filename_lower and 'coffee' in filename_lower:
                description_parts.append("Monday morning coffee setup with warm, energizing atmosphere")
                mood_indicators.append("energetic and focused")
            elif 'workspace' in filename_lower:
                description_parts.append("productive workspace environment")
                mood_indicators.append("focused and professional")
            elif 'nature' in filename_lower:
                description_parts.append("natural outdoor setting")
                mood_indicators.append("contemplative and grounded")
            elif 'hiking' in filename_lower:
                description_parts.append("hiking or outdoor activity scene")
                mood_indicators.append("energetic and adventurous")
            elif 'sunset' in filename_lower or 'evening' in filename_lower:
                description_parts.append("evening or sunset atmosphere")
                mood_indicators.append("reflective and warm")
            
            # Visual elements
            if 'abstract' in filename_lower:
                description_parts.append("with abstract artistic elements")
                mood_indicators.append("bold and creative")
            elif 'geometric' in filename_lower:
                description_parts.append("featuring geometric design patterns")
                mood_indicators.append("sharp and precise")
            elif 'minimal' in filename_lower:
                description_parts.append("with clean, minimal design")
                mood_indicators.append("focused and clear")
            
            # Characters/subjects
            if 'cat' in filename_lower:
                description_parts.append("featuring cats or feline elements")
                mood_indicators.append("playful and relatable")
            elif 'lion' in filename_lower:
                description_parts.append("with powerful lion imagery")
                mood_indicators.append("strong and motivated")
            elif 'running' in filename_lower:
                description_parts.append("showing movement and activity")
                mood_indicators.append("energetic and determined")
            
            # Combine description
            if description_parts:
                description = " ".join(description_parts)
            else:
                # Generic description based on theme
                theme_descriptions = {
                    'productivity': 'work-focused environment',
                    'wellness': 'health and wellness themed setting',
                    'motivation': 'motivational and inspiring scene',
                    'inspiration': 'creative and inspirational atmosphere'
                }
                description = theme_descriptions.get(filename_lower.split('_')[0], 'general themed background')
            
            # Determine overall mood
            if mood_indicators:
                mood = mood_indicators[0]  # Use first/primary mood
            else:
                mood = "authentic and conversational"
            
            return {
                'description': description,
                'mood': mood,
                'filename': filename
            }
            
        except Exception as e:
            logger.error(f"Error extracting image context from {filename}: {str(e)}")
            return {
                'description': 'themed background image',
                'mood': 'authentic and conversational',
                'filename': filename
            }
    
    def _get_base_url(self) -> str:
        """Get the base URL for generating image links"""
        base_url = None
        
        if self.base_url:
            base_url = self.base_url.rstrip('/')
        else:
            # First try to get from Flask request context (if available)
            try:
                from flask import request, has_request_context
                if has_request_context() and hasattr(request, 'host_url'):
                    base_url = request.host_url.rstrip('/')
            except (ImportError, RuntimeError):
                # No Flask context available (e.g., in Celery tasks)
                pass
            
            # Fallback to environment variable or correct Replit default
            if not base_url:
                base_url = os.environ.get('BASE_URL', 'https://line-bot-connect-tkhongsap.replit.app')
        
        # Always ensure HTTPS for Replit deployments (LINE requires HTTPS)
        if 'replit.app' in base_url and base_url.startswith('http://'):
            base_url = base_url.replace('http://', 'https://')
        elif base_url.startswith('http://') and not base_url.startswith('http://localhost'):
            # Convert HTTP to HTTPS for production (except localhost)
            base_url = base_url.replace('http://', 'https://')
            
        return base_url.rstrip('/')
    
    def _load_rich_menu_configs(self) -> Dict[str, Any]:
        """Load Rich Menu configuration templates"""
        return {
            "default": {
                "size": RichMenuSize(width=self.RICH_MENU_WIDTH, height=self.RICH_MENU_HEIGHT),
                "selected": True,
                "name": "Daily Inspiration Menu",
                "chatBarText": "Tap for menu",
                "areas": [
                    # Full image tap area for main content interaction
                    RichMenuArea(
                        bounds=RichMenuBounds(x=0, y=0, width=self.RICH_MENU_WIDTH, height=self.RICH_MENU_HEIGHT),
                        action=PostbackAction(
                            label="View Content",
                            data="action=view_content&menu=daily_inspiration"
                        )
                    )
                ]
            }
        }
    
    def create_rich_menu(self, menu_type: str = "default", custom_image_path: Optional[str] = None) -> Optional[str]:
        """
        Create a new Rich Menu with specified configuration
        
        Args:
            menu_type: Type of menu configuration to use
            custom_image_path: Optional custom image path for the menu
            
        Returns:
            Rich Menu ID if successful, None otherwise
        """
        try:
            # Get menu configuration
            config = self._rich_menu_configs.get(menu_type, self._rich_menu_configs["default"])
            
            # Create Rich Menu object
            rich_menu = RichMenu(
                size=config["size"],
                selected=config["selected"],
                name=config["name"],
                chat_bar_text=config["chatBarText"],
                areas=config["areas"]
            )
            
            # Create the Rich Menu
            rich_menu_id = self.line_bot_api.create_rich_menu(rich_menu)
            logger.info(f"Created Rich Menu with ID: {rich_menu_id}")
            
            # Upload image if provided
            if custom_image_path and os.path.exists(custom_image_path):
                self.upload_rich_menu_image(rich_menu_id, custom_image_path)
            
            return rich_menu_id
            
        except LineBotApiError as e:
            error_message = e.error.message if e.error else "Unknown error"
            logger.error(f"Failed to create Rich Menu: {e.status_code} - {error_message}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error creating Rich Menu: {str(e)}")
            return None
    
    def upload_rich_menu_image(self, rich_menu_id: str, image_path: str) -> bool:
        """
        Upload an image to a Rich Menu
        
        Args:
            rich_menu_id: ID of the Rich Menu
            image_path: Path to the image file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with open(image_path, 'rb') as f:
                self.line_bot_api.set_rich_menu_image(rich_menu_id, 'image/png', f)
            
            logger.info(f"Uploaded image to Rich Menu {rich_menu_id}")
            return True
            
        except LineBotApiError as e:
            error_message = e.error.message if e.error else "Unknown error"
            logger.error(f"Failed to upload Rich Menu image: {e.status_code} - {error_message}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error uploading Rich Menu image: {str(e)}")
            return False
    
    def set_default_rich_menu(self, rich_menu_id: str) -> bool:
        """
        Set a Rich Menu as the default for all users
        
        Args:
            rich_menu_id: ID of the Rich Menu to set as default
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.line_bot_api.set_default_rich_menu(rich_menu_id)
            logger.info(f"Set Rich Menu {rich_menu_id} as default")
            return True
            
        except LineBotApiError as e:
            error_message = e.error.message if e.error else "Unknown error"
            logger.error(f"Failed to set default Rich Menu: {e.status_code} - {error_message}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error setting default Rich Menu: {str(e)}")
            return False
    
    def create_smart_rich_message(self,
                                theme: str = "motivation",
                                user_context: Optional[str] = None,
                                content_id: Optional[str] = None,
                                user_id: Optional[str] = None,
                                action_buttons: Optional[List[Dict[str, str]]] = None,
                                include_interactions: bool = True,
                                force_ai_generation: bool = True) -> FlexSendMessage:
        """
        Create a Rich Message using smart image selection and AI-aware content generation.
        
        This is the new recommended method for creating Rich Messages that automatically:
        1. Selects the best background image based on current context
        2. Generates content that's aware of the selected image
        3. Uses Bourdain's persona matched to the visual context
        
        Args:
            theme: Content theme (productivity, wellness, motivation, inspiration)
            user_context: Optional user context for personalization
            content_id: Unique identifier for this content (auto-generated if not provided)
            user_id: Current user ID (for personalized interactions)
            action_buttons: Optional list of custom action buttons
            include_interactions: Whether to include conversation trigger buttons
            force_ai_generation: Whether to force AI generation vs using fallbacks
            
        Returns:
            FlexSendMessage object with smart content and image selection
        """
        import uuid
        
        # Generate content ID if not provided
        if not content_id:
            content_id = f"smart_{theme}_{int(datetime.now().timestamp())}"
        
        logger.info(f"Creating smart Rich Message for theme: {theme}, user_context: {user_context}")
        
        # Generate image-aware content using smart selection
        result = self.generate_image_aware_content(
            theme=theme,
            user_context=user_context,
            force_ai_generation=force_ai_generation
        )
        
        # Extract content and image from result
        title = result.get('title', '🎯 Real Talk')
        content = result.get('content', 'Something went wrong, but the conversation continues.')
        image_path = result.get('image_path')
        generation_tier = result.get('generation_tier', 'unknown')
        
        logger.info(f"Smart Rich Message generated - Tier: {generation_tier}, Image: {os.path.basename(image_path) if image_path else 'none'}")
        
        # Create the Flex Message using the existing method with theme context
        return self.create_flex_message(
            title=title,
            content=content,
            image_path=image_path,
            content_id=content_id,
            user_id=user_id,
            action_buttons=action_buttons,
            include_interactions=include_interactions,
            theme=theme,  # Pass theme for rich context
            user_context=user_context  # Pass user context
        )

    def create_flex_message(self, 
                          title: str, 
                          content: str, 
                          image_url: Optional[str] = None,
                          image_path: Optional[str] = None,
                          content_id: Optional[str] = None,
                          user_id: Optional[str] = None,
                          action_buttons: Optional[List[Dict[str, str]]] = None,
                          include_interactions: bool = True,
                          use_smart_selection: bool = False,
                          theme: Optional[str] = None,
                          user_context: Optional[str] = None) -> FlexSendMessage:
        """
        Create a Flex Message for rich content display with interactive features.
        
        Args:
            title: Message title
            content: Message content text
            image_url: URL of the header image (optional)
            image_path: Local path to image (optional, for upload)
            content_id: Unique identifier for this content (for interactions)
            user_id: Current user ID (for personalized interactions)
            action_buttons: Optional list of custom action buttons
            include_interactions: Whether to include interaction buttons
            use_smart_selection: Whether to use smart image selection if no image provided
            theme: Theme for smart selection (required if use_smart_selection=True)
            user_context: User context for smart selection
            
        Returns:
            FlexSendMessage object
        """
        from src.utils.interaction_handler import get_interaction_handler
        import uuid
        
        # Generate content ID if not provided
        if not content_id:
            content_id = str(uuid.uuid4())
        
        # Handle smart image selection if enabled and no explicit image provided
        if use_smart_selection and not image_url and not image_path and theme:
            try:
                logger.info(f"Using smart image selection for theme: {theme}")
                selected_image_path = self.select_contextual_image(theme, user_context)
                if selected_image_path:
                    image_path = selected_image_path
                    logger.info(f"Smart selection chose: {os.path.basename(image_path)}")
            except Exception as e:
                logger.warning(f"Smart selection failed, proceeding without image: {str(e)}")
        
        # Prepare image component
        hero_component = None
        if image_url:
            hero_component = ImageComponent(
                url=image_url,
                size="full",
                aspect_ratio="20:13",
                aspect_mode="cover"
            )
        elif image_path:
            # Convert local image path to public URL using our static route
            try:
                # Extract filename from path
                filename = os.path.basename(image_path)
                
                # Generate public URL using the static route we added
                base_url = self._get_base_url()
                public_image_url = f"{base_url}/static/backgrounds/{filename}"
                
                hero_component = ImageComponent(
                    url=public_image_url,
                    size="full",
                    aspect_ratio="20:13", 
                    aspect_mode="cover"
                )
                logger.info(f"Generated image URL for {filename}: {public_image_url}")
                
            except Exception as e:
                logger.error(f"Failed to generate image URL for {image_path}: {str(e)}")
                hero_component = None
        
        # Create body content
        body_contents = [
            TextComponent(
                text=title,
                weight="bold",
                size="xl",
                wrap=True,
                color="#333333"
            ),
            TextComponent(text=" ", size="xs"),  # Spacer replacement
            TextComponent(
                text=content,
                size="md",
                wrap=True,
                color="#666666"
            )
        ]
        
        # Add interaction buttons if enabled
        if include_interactions and content_id:
            try:
                # Pass OpenAI service to interaction handler for conversation triggers
                interaction_handler = get_interaction_handler(self.openai_service)
                
                # Build rich message context for enhanced button responses
                rich_message_context = {
                    'title': title,
                    'content': content,
                    'theme': theme if theme else 'general',  # Use provided theme or default
                    'image_context': self._extract_image_context(os.path.basename(image_path)) if image_path else {}
                }
                
                interactive_buttons = interaction_handler.create_interactive_buttons(
                    content_id=content_id,
                    current_user_id=user_id,
                    include_stats=True,
                    rich_message_context=rich_message_context,
                    rich_message_service=self
                )
                
                if interactive_buttons:
                    body_contents.append(TextComponent(text=" ", size="sm"))  # Spacer replacement
                    
                    # Create button components in rows of 2
                    button_rows = []
                    for i in range(0, len(interactive_buttons), 2):
                        row_buttons = interactive_buttons[i:i+2]
                        
                        button_components = []
                        for button in row_buttons:
                            if button.get("type") == "uri":
                                action = URIAction(label=button["label"], uri=button["uri"])
                            elif button.get("type") == "postback":
                                action = PostbackAction(label=button["label"], data=button["data"])
                            else:
                                action = MessageAction(label=button["label"], text=button.get("text", button["label"]))
                            
                            button_components.append(
                                ButtonComponent(
                                    action=action,
                                    style=button.get("style", "secondary"),
                                    height="sm",
                                    flex=1
                                )
                            )
                        
                        # Create horizontal box for button row
                        button_row = BoxComponent(
                            layout="horizontal",
                            contents=button_components,
                            spacing="sm"
                        )
                        button_rows.append(button_row)
                    
                    # Add button rows to body
                    for row in button_rows:
                        body_contents.append(row)
                        if row != button_rows[-1]:  # Add spacing between rows
                            body_contents.append(TextComponent(text=" ", size="xs"))  # Spacer replacement
                            
            except Exception as e:
                logger.error(f"Failed to create interactive buttons: {str(e)}")
        
        # Add custom action buttons if provided
        if action_buttons:
            if not (include_interactions and content_id):  # Only add spacer if no interaction buttons
                body_contents.append(TextComponent(text=" ", size="sm"))  # Spacer replacement
            
            custom_button_components = []
            for button in action_buttons:
                if button.get("type") == "uri":
                    action = URIAction(label=button["label"], uri=button["uri"])
                elif button.get("type") == "postback":
                    action = PostbackAction(label=button["label"], data=button["data"])
                else:
                    action = MessageAction(label=button["label"], text=button.get("text", button["label"]))
                
                custom_button_components.append(
                    ButtonComponent(
                        action=action,
                        style="primary" if button.get("primary") else "secondary",
                        height="sm"
                    )
                )
            
            # Add custom buttons
            for button in custom_button_components:
                body_contents.append(TextComponent(text=" ", size="xs"))  # Spacer replacement
                body_contents.append(button)
        
        # Create bubble container
        bubble_kwargs = {
            "body": BoxComponent(
                layout="vertical",
                contents=body_contents,
                spacing="none",
                margin="lg"
            )
        }
        
        # Add hero image if available
        if hero_component:
            bubble_kwargs["hero"] = hero_component
        
        bubble = BubbleContainer(**bubble_kwargs)
        
        # Safe alt text generation
        if content and len(content) > 50:
            alt_text = f"{title}: {content[:50]}..."
        elif content:
            alt_text = f"{title}: {content}"
        else:
            alt_text = title or "Rich Message"
        
        return FlexSendMessage(
            alt_text=alt_text,
            contents=bubble
        )
    
    def send_rich_message(self,
                        flex_message: FlexSendMessage, 
                        user_id: str,
                        bypass_rate_limit: bool = False,
                        dry_run: bool = False) -> Dict[str, Any]:
        """
        Send a Rich Message to a specific user with rate limiting and safety checks.
        
        Args:
            flex_message: The Flex Message to send
            user_id: Target user ID
            bypass_rate_limit: If True, bypasses rate limiting (for admin/testing)
            dry_run: If True, validates but doesn't actually send the message
            
        Returns:
            Result dictionary with success status and details
        """
        try:
            # Check environment safety
            is_production = os.environ.get('FLASK_ENV', 'development') == 'production'
            if not is_production and not bypass_rate_limit:
                logger.info("Non-production environment detected - consider using dry_run=True for testing")
            
            # Check rate limits
            rate_check = self.check_send_rate_limit(user_id, bypass_rate_limit)
            if not rate_check["allowed"]:
                logger.warning(f"Rich Message send blocked for user {user_id[:8]}...: {rate_check['reason']}")
                return {
                    "success": False,
                    "blocked": True,
                    "reason": rate_check["reason"],
                    "rate_limit_info": rate_check,
                    "timestamp": datetime.now().isoformat()
                }
            
            # Dry run mode - validate but don't send
            if dry_run:
                logger.info(f"DRY RUN: Would send Rich Message to user {user_id[:8]}...")
                return {
                    "success": True,
                    "dry_run": True,
                    "message": "Rich Message validated but not sent (dry run mode)",
                    "rate_limit_info": rate_check,
                    "timestamp": datetime.now().isoformat()
                }
            
            # Actually send the message
            self.line_bot_api.push_message(user_id, flex_message)
            
            # Record the send for rate limiting
            self.record_message_sent(user_id)
            
            logger.info(f"Rich Message sent successfully to user {user_id[:8]}...")
            return {
                "success": True,
                "sent": True,
                "user_id": user_id[:8] + "...",
                "rate_limit_info": rate_check,
                "timestamp": datetime.now().isoformat()
            }
            
        except LineBotApiError as e:
            error_message = e.error.message if e.error else "Unknown error"
            error_msg = f"Failed to send Rich Message: {e.status_code} - {error_message}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            error_msg = f"Unexpected error sending Rich Message: {str(e)}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "timestamp": datetime.now().isoformat()
            }

    def broadcast_rich_message(self, 
                             flex_message: FlexSendMessage,
                             target_audience: Optional[str] = None) -> Dict[str, Any]:
        """
        Broadcast a Rich Message to users
        
        Args:
            flex_message: The Flex Message to broadcast
            target_audience: Optional audience ID for targeted broadcasting
            
        Returns:
            Result dictionary with success status and details
        """
        try:
            if target_audience:
                # Narrowcast to specific audience
                self.line_bot_api.narrowcast(
                    messages=[flex_message],
                    recipient={"type": "audience", "audienceGroupId": target_audience}
                )
                logger.info(f"Narrowcast Rich Message to audience {target_audience}")
            else:
                # Broadcast to all users
                self.line_bot_api.broadcast(messages=[flex_message])
                logger.info("Broadcast Rich Message to all users")
            
            return {
                "success": True,
                "timestamp": datetime.now().isoformat(),
                "audience": target_audience or "all"
            }
            
        except LineBotApiError as e:
            error_message = e.error.message if e.error else "Unknown error"
            error_msg = f"Failed to broadcast Rich Message: {e.status_code} - {error_message}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            error_msg = f"Unexpected error broadcasting Rich Message: {str(e)}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "timestamp": datetime.now().isoformat()
            }
    
    def delete_rich_menu(self, rich_menu_id: str) -> bool:
        """
        Delete a Rich Menu
        
        Args:
            rich_menu_id: ID of the Rich Menu to delete
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.line_bot_api.delete_rich_menu(rich_menu_id)
            logger.info(f"Deleted Rich Menu {rich_menu_id}")
            return True
            
        except LineBotApiError as e:
            error_message = e.error.message if e.error else "Unknown error"
            logger.error(f"Failed to delete Rich Menu: {e.status_code} - {error_message}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error deleting Rich Menu: {str(e)}")
            return False
    
    def list_rich_menus(self) -> List[Dict[str, Any]]:
        """
        List all Rich Menus
        
        Returns:
            List of Rich Menu information dictionaries
        """
        try:
            rich_menus = self.line_bot_api.get_rich_menu_list()
            menu_list = []
            
            for menu in rich_menus:
                menu_list.append({
                    "richMenuId": menu.rich_menu_id,
                    "name": menu.name,
                    "size": {
                        "width": menu.size.width,
                        "height": menu.size.height
                    },
                    "selected": menu.selected,
                    "chatBarText": menu.chat_bar_text
                })
            
            logger.info(f"Listed {len(menu_list)} Rich Menus")
            return menu_list
            
        except LineBotApiError as e:
            error_message = e.error.message if e.error else "Unknown error"
            logger.error(f"Failed to list Rich Menus: {e.status_code} - {error_message}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error listing Rich Menus: {str(e)}")
            return []
    
    def store_button_context(self, content_id: str, rich_context: Dict[str, Any]) -> None:
        """
        Store rich context for button interactions with Redis fallback
        
        Args:
            content_id: Unique identifier for the content
            rich_context: Full context including title, content, theme, image_context
        """
        try:
            # Add timestamp for cleanup
            context_with_timestamp = {
                **rich_context,
                'stored_at': datetime.now().timestamp()
            }
            
            # Try Redis first if available
            if self._redis_available:
                try:
                    success = self.redis_cache.set(
                        content_id,
                        context_with_timestamp,
                        ttl=24 * 3600,  # 24 hours
                        prefix="button_context"
                    )
                    if success:
                        logger.debug(f"Stored button context in Redis for content_id: {content_id}")
                        return
                except Exception as e:
                    logger.warning(f"Redis button context store failed for {content_id}, falling back to memory: {str(e)}")
                    self._redis_available = False
            
            # Fallback to in-memory storage
            self._button_context_storage[content_id] = context_with_timestamp
            
            # Clean old entries (older than 24 hours)
            self._clean_old_button_contexts()
            
            logger.debug(f"Stored button context in memory for content_id: {content_id}")
            
        except Exception as e:
            logger.error(f"Error storing button context: {str(e)}")
    
    def get_button_context(self, content_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve stored button context with Redis fallback
        
        Args:
            content_id: Unique identifier for the content
            
        Returns:
            Rich context dictionary or None if not found
        """
        try:
            context = None
            
            # Try Redis first if available
            if self._redis_available:
                try:
                    context = self.redis_cache.get(content_id, prefix="button_context")
                    if context:
                        logger.debug(f"Retrieved button context from Redis for content_id: {content_id}")
                except Exception as e:
                    logger.warning(f"Redis button context read failed for {content_id}, falling back to memory: {str(e)}")
                    self._redis_available = False
            
            # Fallback to in-memory storage
            if not context:
                context = self._button_context_storage.get(content_id)
                if context:
                    logger.debug(f"Retrieved button context from memory for content_id: {content_id}")
            
            if context:
                # Remove timestamp before returning
                context_copy = dict(context)
                context_copy.pop('stored_at', None)
                return context_copy
            else:
                logger.warning(f"Button context not found for content_id: {content_id}")
                return None
                
        except Exception as e:
            logger.error(f"Error retrieving button context: {str(e)}")
            return None
    
    def _get_rate_limit_data(self, user_id: str, data_type: str, date_key: Optional[str] = None) -> Optional[Any]:
        """Get rate limit data with Redis fallback."""
        try:
            # Try Redis first if available
            if self._check_redis_health():
                def redis_operation(client):
                    if data_type == "send_history":
                        full_key = f"rate_limit_history:{user_id}"
                        data = client.get(full_key)
                        return float(data.decode('utf-8')) if data else None
                    elif data_type == "daily_limits" and date_key:
                        daily_key = f"{user_id}:{date_key}"
                        full_key = f"rate_limit_daily:{daily_key}"
                        data = client.get(full_key)
                        return int(data.decode('utf-8')) if data else None
                    return None
                
                def fallback():
                    return None
                
                result = self.redis_manager.execute_with_fallback(
                    redis_operation, fallback, f"get_rate_limit_{data_type}_{user_id}"
                )
                
                if result is not None:
                    return result
            
            # Fallback to in-memory storage
            if data_type == "send_history":
                return self._send_history.get(user_id)
            elif data_type == "daily_limits" and date_key:
                daily_key = f"{user_id}:{date_key}"
                return self._daily_send_limits.get(daily_key)
                
        except Exception as e:
            logger.error(f"Error getting rate limit data for {user_id}: {str(e)}")
            return None
    
    def _set_rate_limit_data(self, user_id: str, data_type: str, value: Any, date_key: Optional[str] = None) -> None:
        """Set rate limit data with Redis fallback."""
        try:
            # Try Redis first if available
            if self._check_redis_health():
                def redis_operation(client):
                    if data_type == "send_history":
                        full_key = f"rate_limit_history:{user_id}"
                        ttl = self._send_cooldown + 60
                        return client.setex(full_key, ttl, str(value))
                    elif data_type == "daily_limits" and date_key:
                        daily_key = f"{user_id}:{date_key}"
                        full_key = f"rate_limit_daily:{daily_key}"
                        ttl = 25 * 3600  # 25 hours for timezone differences
                        return client.setex(full_key, ttl, str(value))
                    return False
                
                def fallback():
                    return False
                
                success = self.redis_manager.execute_with_fallback(
                    redis_operation, fallback, f"set_rate_limit_{data_type}_{user_id}"
                )
                
                if success:
                    return
            
            # Fallback to in-memory storage
            if data_type == "send_history":
                self._send_history[user_id] = value
            elif data_type == "daily_limits" and date_key:
                daily_key = f"{user_id}:{date_key}"
                self._daily_send_limits[daily_key] = value
                
        except Exception as e:
            logger.error(f"Error setting rate limit data for {user_id}: {str(e)}")
    
    def _get_mood_cache(self, template_name: str) -> Optional[str]:
        """Get mood cache with LRU -> Redis -> in-memory fallback hierarchy."""
        try:
            # Try LRU cache first (fastest)
            lru_result = self.mood_cache.get(template_name)
            if lru_result is not None:
                logger.debug(f"LRU mood cache hit for template: {template_name}")
                return lru_result
            
            # Try Redis if available
            if self._check_redis_health():
                def redis_operation(client):
                    full_key = f"mood_cache:{template_name}"
                    data = client.get(full_key)
                    if data:
                        mood = data.decode('utf-8')
                        # Cache in LRU for future requests
                        self.mood_cache.put(template_name, mood, cache_type=CacheType.MOOD)
                        return mood
                    return None
                
                def fallback():
                    return None
                
                result = self.redis_manager.execute_with_fallback(
                    redis_operation, fallback, f"get_mood_cache_{template_name}"
                )
                
                if result is not None:
                    logger.debug(f"Redis mood cache hit for template: {template_name}")
                    return result
            
            # Fallback to legacy in-memory cache
            legacy_result = self._mood_cache.get(template_name)
            if legacy_result is not None:
                logger.debug(f"Legacy mood cache hit for template: {template_name}")
                # Migrate to LRU cache
                self.mood_cache.put(template_name, legacy_result, cache_type=CacheType.MOOD)
                return legacy_result
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting mood cache for {template_name}: {str(e)}")
            return None
    
    def _set_mood_cache(self, template_name: str, mood: str) -> None:
        """Set mood cache with LRU -> Redis -> in-memory hierarchy."""
        try:
            # Cache in LRU first (most efficient)
            lru_success = self.mood_cache.put(template_name, mood, cache_type=CacheType.MOOD)
            if lru_success:
                logger.debug(f"Cached mood in LRU cache for template: {template_name}")
            
            # Also cache in Redis for persistence
            if self._check_redis_health():
                def redis_operation(client):
                    full_key = f"mood_cache:{template_name}"
                    # Mood cache has longer TTL since templates don't change often
                    ttl = 24 * 3600  # 24 hours
                    return client.setex(full_key, ttl, mood)
                
                def fallback():
                    return False
                
                success = self.redis_manager.execute_with_fallback(
                    redis_operation, fallback, f"set_mood_cache_{template_name}"
                )
                
                if success:
                    logger.debug(f"Cached mood in Redis for template: {template_name}")
                    return
            
            # Fallback to legacy in-memory cache only if LRU failed
            if not lru_success:
                self._mood_cache[template_name] = mood
                logger.debug(f"Cached mood in legacy memory for template: {template_name}")
            
        except Exception as e:
            logger.error(f"Error setting mood cache for {template_name}: {str(e)}")
    
    def _cleanup_old_daily_records(self) -> None:
        """Cleanup old daily records from in-memory storage (only when Redis is not available)."""
        try:
            current_date = datetime.now()
            keys_to_remove = []
            for key in self._daily_send_limits.keys():
                if ':' in key:
                    date_str = key.split(':', 1)[1]
                    try:
                        record_date = datetime.strptime(date_str, '%Y-%m-%d')
                        if (current_date - record_date).days > 7:
                            keys_to_remove.append(key)
                    except ValueError:
                        keys_to_remove.append(key)  # Invalid format, remove it
            
            for key in keys_to_remove:
                del self._daily_send_limits[key]
                
            if keys_to_remove:
                logger.debug(f"Cleaned {len(keys_to_remove)} old daily limit records from memory")
                
        except Exception as e:
            logger.error(f"Error cleaning old daily records: {str(e)}")
    
    def _clean_old_button_contexts(self) -> None:
        """Clean button contexts older than 24 hours from in-memory storage"""
        try:
            current_time = datetime.now().timestamp()
            cutoff_time = current_time - (24 * 60 * 60)  # 24 hours ago
            
            # Find old entries
            old_keys = [
                content_id for content_id, context in self._button_context_storage.items()
                if context.get('stored_at', 0) < cutoff_time
            ]
            
            # Remove old entries
            for key in old_keys:
                del self._button_context_storage[key]
            
            if old_keys:
                logger.debug(f"Cleaned {len(old_keys)} old button contexts from memory")
                
        except Exception as e:
            logger.error(f"Error cleaning old button contexts: {str(e)}")
    
    def health_check(self) -> Dict[str, Any]:
        """Get health status of RichMessageService including Redis connectivity and LRU cache stats."""
        try:
            # Get LRU cache statistics
            content_cache_stats = self.content_cache.get_health_status()
            mood_cache_stats = self.mood_cache.get_health_status()
            
            health_status = {
                'service': 'RichMessageService',
                'status': 'healthy',
                'cache_backend': 'Redis+LRU' if self._redis_available else 'LRU+in-memory',
                'redis_available': self._redis_available,
                'lru_caches': {
                    'content_cache': content_cache_stats,
                    'mood_cache': mood_cache_stats
                },
                'legacy_cache_sizes': {
                    'memory_cache_size': len(self._content_cache),
                    'mood_cache_size': len(self._mood_cache),
                    'button_contexts': len(self._button_context_storage),
                    'send_history_size': len(self._send_history),
                    'daily_limits_size': len(self._daily_send_limits)
                }
            }
            
            # Update overall status based on cache health
            if (content_cache_stats['status'] in ['critical', 'warning'] or 
                mood_cache_stats['status'] in ['critical', 'warning']):
                health_status['status'] = 'warning'
            
            # Add Redis health information if available
            if self.redis_manager and self.enable_redis:
                try:
                    redis_health = self.redis_manager.health_check()
                    health_status['redis_health'] = redis_health
                    
                    redis_stats = self.redis_manager.get_statistics()
                    health_status['redis_statistics'] = redis_stats
                    
                    # Update availability based on current health
                    current_redis_health = redis_health.get('is_healthy', False)
                    if current_redis_health != self._redis_available:
                        self._redis_available = current_redis_health
                        health_status['redis_available'] = current_redis_health
                        health_status['cache_backend'] = 'Redis' if current_redis_health else 'in-memory'
                        
                        if current_redis_health:
                            logger.info("Redis connection restored for RichMessageService")
                        else:
                            logger.warning("Redis connection lost for RichMessageService")
                            
                except Exception as e:
                    logger.debug(f"Redis health check failed for RichMessageService: {str(e)}")
                    health_status['redis_error'] = str(e)
            
            return health_status
            
        except Exception as e:
            logger.error(f"Error performing RichMessageService health check: {str(e)}")
            return {
                'service': 'RichMessageService',
                'status': 'error',
                'error': str(e)
            }