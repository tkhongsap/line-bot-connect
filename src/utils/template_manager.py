"""
Template Manager for Rich Message automation system.

This module handles loading, caching, and managing Canva template files
along with their metadata for automated Rich Message generation.
"""

import os
import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, time
from pathlib import Path
import hashlib
from PIL import Image
from dataclasses import dataclass

from src.models.rich_message_models import RichMessageTemplate, ContentCategory, ValidationError
from src.config.rich_message_config import get_rich_message_config
from src.utils.lru_cache_manager import get_lru_cache, CacheType

logger = logging.getLogger(__name__)


@dataclass
class TemplateCache:
    """Cache entry for template data"""
    template: RichMessageTemplate
    image_path: str
    image_size: Tuple[int, int]
    cached_at: datetime
    file_hash: str


class TemplateManager:
    """
    Manages Canva templates for Rich Message automation.
    
    Handles loading template metadata, caching templates, and providing
    intelligent template selection based on content themes, time of day,
    and user preferences.
    """
    
    def __init__(self, config=None):
        """
        Initialize the TemplateManager.
        
        Args:
            config: Optional configuration object. If None, uses global config.
        """
        self.config = config or get_rich_message_config()
        
        # Initialize LRU cache for templates with memory monitoring
        self.template_lru_cache = get_lru_cache(
            name=f"template_manager_{id(self)}",
            max_size=100,  # Max templates to cache
            max_memory_mb=200.0,  # Templates can be large with image data
            default_ttl=self.config.template.cache_duration_hours * 3600 if hasattr(self.config.template, 'cache_duration_hours') else 12*3600,
            enable_memory_monitoring=True
        )
        
        # Legacy cache for backward compatibility and fallback
        self.template_cache: Dict[str, TemplateCache] = {}
        self.metadata_cache: Optional[Dict[str, Any]] = None
        self.metadata_loaded_at: Optional[datetime] = None
        
        # Validate template directory exists
        if not os.path.exists(self.config.template.template_directory):
            logger.warning(f"Template directory not found: {self.config.template.template_directory}")
        
        # Load initial metadata
        self._load_metadata()
    
    def _load_metadata(self) -> None:
        """Load template metadata from the metadata file."""
        try:
            metadata_path = self.config.template.metadata_file
            if not os.path.exists(metadata_path):
                logger.warning(f"Metadata file not found: {metadata_path}")
                self.metadata_cache = {}
                return
            
            with open(metadata_path, 'r', encoding='utf-8') as f:
                self.metadata_cache = json.load(f)
            
            self.metadata_loaded_at = datetime.now()
            logger.info(f"Loaded metadata for {len(self.metadata_cache)} templates")
            
        except Exception as e:
            logger.error(f"Failed to load template metadata: {str(e)}")
            self.metadata_cache = {}
    
    def _should_reload_metadata(self) -> bool:
        """Check if metadata should be reloaded based on cache duration."""
        if self.metadata_loaded_at is None:
            return True
        
        cache_duration_hours = self.config.template.cache_duration_hours
        time_since_load = datetime.now() - self.metadata_loaded_at
        return time_since_load.total_seconds() > (cache_duration_hours * 3600)
    
    def _get_file_hash(self, file_path: str) -> str:
        """Calculate SHA256 hash of a file for cache validation."""
        try:
            with open(file_path, 'rb') as f:
                return hashlib.sha256(f.read()).hexdigest()
        except Exception as e:
            logger.error(f"Failed to calculate hash for {file_path}: {str(e)}")
            return ""
    
    def _validate_template_file(self, file_path: str) -> Tuple[bool, Optional[Tuple[int, int]]]:
        """
        Validate a template image file.
        
        Args:
            file_path: Path to the template image file
            
        Returns:
            Tuple of (is_valid, image_size)
        """
        try:
            if not os.path.exists(file_path):
                logger.error(f"Template file not found: {file_path}")
                return False, None
            
            # Check file size
            file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
            max_size_mb = self.config.template.max_template_size_mb
            if file_size_mb > max_size_mb:
                logger.error(f"Template file too large: {file_size_mb:.2f}MB > {max_size_mb}MB")
                return False, None
            
            # Validate image with PIL
            with Image.open(file_path) as img:
                image_size = img.size
                
                # Check if dimensions meet LINE Rich Message requirements
                # LINE Rich Messages should be 2500x1686px or compatible ratios
                min_width, min_height = 800, 600  # Minimum reasonable dimensions
                max_width, max_height = 3000, 2000  # Maximum reasonable dimensions
                
                if (image_size[0] < min_width or image_size[1] < min_height or
                    image_size[0] > max_width or image_size[1] > max_height):
                    logger.warning(f"Template {file_path} has unusual dimensions: {image_size}")
                
                return True, image_size
                
        except Exception as e:
            logger.error(f"Failed to validate template file {file_path}: {str(e)}")
            return False, None
    
    def load_template(self, template_id: str, force_reload: bool = False) -> Optional[RichMessageTemplate]:
        """
        Load a specific template by ID with LRU caching.
        
        Args:
            template_id: Unique identifier for the template
            force_reload: Force reload even if cached
            
        Returns:
            RichMessageTemplate object or None if not found
        """
        try:
            # Check LRU cache first (unless force reload)
            if not force_reload:
                lru_template = self.template_lru_cache.get(template_id)
                if lru_template is not None:
                    logger.debug(f"LRU cache hit for template: {template_id}")
                    return lru_template
                
                # Check legacy cache
                if template_id in self.template_cache:
                    cache_entry = self.template_cache[template_id]
                    
                    # Validate cache freshness
                    cache_duration_hours = getattr(self.config.template, 'cache_duration_hours', 12)
                    cache_age_hours = (datetime.now() - cache_entry.cached_at).total_seconds() / 3600
                    if cache_age_hours < cache_duration_hours:
                        # Check if file hasn't changed
                        current_hash = self._get_file_hash(cache_entry.image_path)
                        if current_hash == cache_entry.file_hash:
                            logger.debug(f"Legacy cache hit for template: {template_id}")
                            # Migrate to LRU cache
                            self.template_lru_cache.put(template_id, cache_entry.template, cache_type=CacheType.TEMPLATE)
                            return cache_entry.template
            
            # Reload metadata if necessary
            if self._should_reload_metadata():
                self._load_metadata()
            
            # Check if template exists in metadata
            if not self.metadata_cache or template_id not in self.metadata_cache:
                logger.error(f"Template not found in metadata: {template_id}")
                return None
            
            template_data = self.metadata_cache[template_id]
            
            # Construct file path
            filename = template_data.get('filename', f"{template_id}.png")
            file_path = os.path.join(self.config.template.template_directory, filename)
            
            # Validate template file
            is_valid, image_size = self._validate_template_file(file_path)
            if not is_valid:
                return None
            
            # Create template object
            template = RichMessageTemplate.from_metadata(template_id, template_data)
            
            # Cache the template in LRU cache
            lru_success = self.template_lru_cache.put(template_id, template, cache_type=CacheType.TEMPLATE)
            if lru_success:
                logger.debug(f"Cached template in LRU for: {template_id}")
            
            # Also cache in legacy cache if enabled for backward compatibility
            cache_templates = getattr(self.config.template, 'cache_templates', True)
            if cache_templates and not lru_success:  # Only use legacy if LRU failed
                file_hash = self._get_file_hash(file_path)
                cache_entry = TemplateCache(
                    template=template,
                    image_path=file_path,
                    image_size=image_size,
                    cached_at=datetime.now(),
                    file_hash=file_hash
                )
                self.template_cache[template_id] = cache_entry
                logger.debug(f"Cached template in legacy cache for: {template_id}")
            
            logger.info(f"Loaded template: {template_id}")
            return template
            
        except Exception as e:
            logger.error(f"Failed to load template {template_id}: {str(e)}")
            return None
    
    def get_available_templates(self) -> List[str]:
        """
        Get list of all available template IDs.
        
        Returns:
            List of template IDs
        """
        if self._should_reload_metadata():
            self._load_metadata()
        
        return list(self.metadata_cache.keys()) if self.metadata_cache else []
    
    def get_templates_by_category(self, category: ContentCategory) -> List[RichMessageTemplate]:
        """
        Get all templates matching a specific category.
        
        Args:
            category: Content category to filter by
            
        Returns:
            List of matching templates
        """
        templates = []
        for template_id in self.get_available_templates():
            template = self.load_template(template_id)
            if template and template.category == category:
                templates.append(template)
        
        return templates
    
    def select_template_for_time(self, category: ContentCategory, 
                                current_time: Optional[time] = None,
                                energy_level: str = "medium") -> Optional[RichMessageTemplate]:
        """
        Select the most appropriate template for a given time and energy level.
        
        Args:
            category: Content category
            current_time: Time to select for (defaults to current time)
            energy_level: Desired energy level ("low", "medium", "high")
            
        Returns:
            Most suitable template or None
        """
        if current_time is None:
            current_time = datetime.now().time()
        
        # Get all templates for the category
        candidates = self.get_templates_by_category(category)
        if not candidates:
            logger.warning(f"No templates found for category: {category}")
            return None
        
        # Score templates based on time and energy suitability
        scored_templates = []
        for template in candidates:
            score = 0
            
            # Time-based scoring
            if template.is_suitable_for_time(current_time):
                score += 10
            
            # Energy level scoring
            if template.matches_energy_level(energy_level):
                score += 5
            
            # Prefer templates with better positioning for text
            if template.text_areas and len(template.text_areas) > 0:
                score += 3
            
            scored_templates.append((template, score))
        
        # Sort by score and return the best match
        scored_templates.sort(key=lambda x: x[1], reverse=True)
        
        if scored_templates:
            best_template = scored_templates[0][0]
            logger.info(f"Selected template {best_template.template_id} for {category} at {current_time}")
            return best_template
        
        return None
    
    def get_template_file_path(self, template_id: str) -> Optional[str]:
        """
        Get the file path for a template.
        
        Args:
            template_id: Template identifier
            
        Returns:
            File path string or None if not found
        """
        template = self.load_template(template_id)
        if not template:
            return None
        
        # Check cache first
        if template_id in self.template_cache:
            return self.template_cache[template_id].image_path
        
        # Fallback to metadata
        if self.metadata_cache and template_id in self.metadata_cache:
            template_data = self.metadata_cache[template_id]
            filename = template_data.get('filename', f"{template_id}.png")
            return os.path.join(self.config.template.template_directory, filename)
        
        return None
    
    def validate_all_templates(self) -> Dict[str, bool]:
        """
        Validate all templates in the metadata.
        
        Returns:
            Dictionary mapping template_id to validation status
        """
        validation_results = {}
        
        for template_id in self.get_available_templates():
            try:
                template = self.load_template(template_id)
                file_path = self.get_template_file_path(template_id)
                
                if template and file_path:
                    is_valid, _ = self._validate_template_file(file_path)
                    validation_results[template_id] = is_valid
                else:
                    validation_results[template_id] = False
                    
            except Exception as e:
                logger.error(f"Error validating template {template_id}: {str(e)}")
                validation_results[template_id] = False
        
        # Log summary
        total_templates = len(validation_results)
        valid_templates = sum(validation_results.values())
        logger.info(f"Template validation: {valid_templates}/{total_templates} templates valid")
        
        return validation_results
    
    def clear_cache(self) -> None:
        """Clear all cached templates and metadata."""
        self.template_lru_cache.clear()
        self.template_cache.clear()
        self.metadata_cache = None
        self.metadata_loaded_at = None
        logger.info("Template cache cleared (both LRU and legacy)")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive cache statistics for both LRU and legacy caches.
        
        Returns:
            Dictionary with cache statistics
        """
        lru_stats = self.template_lru_cache.get_statistics()
        cache_templates = getattr(self.config.template, 'cache_templates', True)
        
        return {
            "lru_cache": lru_stats,
            "legacy_cached_templates": len(self.template_cache),
            "metadata_loaded": self.metadata_loaded_at is not None,
            "metadata_age_hours": (
                (datetime.now() - self.metadata_loaded_at).total_seconds() / 3600
                if self.metadata_loaded_at else None
            ),
            "cache_enabled": cache_templates,
            "total_templates_cached": lru_stats['size'] + len(self.template_cache),
            "lru_hit_rate": lru_stats['hit_rate'],
            "lru_memory_usage_mb": lru_stats['memory_usage_mb']
        }