"""
Image Composer for Rich Message automation system.

This module handles compositing text onto template images using PIL,
creating final Rich Message images ready for LINE Bot delivery.
"""

import os
import logging
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
import tempfile
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
from dataclasses import dataclass
import textwrap
import io
import base64
from datetime import datetime

from src.models.rich_message_models import RichMessageTemplate, RichMessageContent, TextArea, ValidationError
from src.utils.content_generator import GeneratedContent
from src.config.rich_message_config import get_rich_message_config

logger = logging.getLogger(__name__)


@dataclass
class FontConfig:
    """Font configuration for text rendering"""
    font_path: str
    size: int
    color: Tuple[int, int, int, int] = (255, 255, 255, 255)  # RGBA
    stroke_width: int = 0
    stroke_color: Tuple[int, int, int, int] = (0, 0, 0, 255)  # RGBA


@dataclass
class TextStyle:
    """Text styling configuration"""
    font_config: FontConfig
    line_spacing: float = 1.2
    alignment: str = "center"  # "left", "center", "right"
    vertical_alignment: str = "center"  # "top", "center", "bottom"
    word_wrap: bool = True
    shadow: bool = False
    shadow_offset: Tuple[int, int] = (2, 2)
    shadow_color: Tuple[int, int, int, int] = (0, 0, 0, 128)


@dataclass
class CompositionResult:
    """Result of image composition"""
    success: bool
    image_path: Optional[str] = None
    image_data: Optional[bytes] = None
    image_size: Optional[Tuple[int, int]] = None
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class ImageComposer:
    """
    Composes text onto template images for Rich Message generation.
    
    Handles font loading, text positioning, styling, and image optimization
    for LINE Bot Rich Message delivery.
    """
    
    def __init__(self, config=None):
        """
        Initialize the ImageComposer.
        
        Args:
            config: Optional configuration object
        """
        self.config = config or get_rich_message_config()
        self.font_cache: Dict[str, ImageFont.ImageFont] = {}
        self.default_fonts = self._load_default_fonts()
        
        # Ensure output directory exists
        self.output_dir = "/tmp/rich_messages"
        os.makedirs(self.output_dir, exist_ok=True)
    
    def _load_default_fonts(self) -> Dict[str, str]:
        """Load default font paths for different languages and styles."""
        fonts = {}
        
        # Common system font paths
        font_search_paths = [
            "/usr/share/fonts/truetype/dejavu/",
            "/usr/share/fonts/truetype/liberation/",
            "/System/Library/Fonts/",
            "/usr/share/fonts/",
            "./static/fonts/"
        ]
        
        # Default font mappings
        font_names = {
            "default": ["DejaVuSans.ttf", "LiberationSans-Regular.ttf", "Arial.ttf", "Helvetica.ttf"],
            "bold": ["DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf", "Arial-Bold.ttf", "Helvetica-Bold.ttf"],
            "thai": ["NotoSansThai-Regular.ttf", "DejaVuSans.ttf"],
            "chinese": ["NotoSansCJK-Regular.ttc", "DejaVuSans.ttf"],
            "japanese": ["NotoSansCJK-Regular.ttc", "DejaVuSans.ttf"],
            "korean": ["NotoSansCJK-Regular.ttc", "DejaVuSans.ttf"]
        }
        
        # Find available fonts
        for font_type, font_list in font_names.items():
            for font_name in font_list:
                for search_path in font_search_paths:
                    font_path = os.path.join(search_path, font_name)
                    if os.path.exists(font_path):
                        fonts[font_type] = font_path
                        logger.debug(f"Found {font_type} font: {font_path}")
                        break
                if font_type in fonts:
                    break
        
        # Ensure we have at least a default font
        if "default" not in fonts:
            try:
                # Try to use PIL's default font
                fonts["default"] = None  # Will use PIL's default
                logger.warning("No system fonts found, using PIL default")
            except Exception as e:
                logger.error(f"Failed to load any fonts: {str(e)}")
        
        return fonts
    
    def _get_font(self, font_config: FontConfig) -> ImageFont.ImageFont:
        """
        Get a font object, using cache when possible.
        
        Args:
            font_config: Font configuration
            
        Returns:
            PIL ImageFont object
        """
        cache_key = f"{font_config.font_path}_{font_config.size}"
        
        if cache_key in self.font_cache:
            return self.font_cache[cache_key]
        
        try:
            if font_config.font_path and os.path.exists(font_config.font_path):
                font = ImageFont.truetype(font_config.font_path, font_config.size)
            else:
                # Fallback to default font
                default_font_path = self.default_fonts.get("default")
                if default_font_path:
                    font = ImageFont.truetype(default_font_path, font_config.size)
                else:
                    font = ImageFont.load_default()
            
            self.font_cache[cache_key] = font
            return font
            
        except Exception as e:
            logger.error(f"Failed to load font {font_config.font_path}: {str(e)}")
            # Ultimate fallback
            font = ImageFont.load_default()
            self.font_cache[cache_key] = font
            return font
    
    def _select_font_for_language(self, language: str, size: int = 36, bold: bool = False) -> FontConfig:
        """
        Select appropriate font for a given language.
        
        Args:
            language: Language code (e.g., "en", "th", "zh")
            size: Font size
            bold: Whether to use bold font
            
        Returns:
            FontConfig object
        """
        font_key = "bold" if bold else "default"
        
        # Language-specific font selection
        if language in ["th", "thai"]:
            font_key = "thai"
        elif language in ["zh", "zh-cn", "zh-tw", "chinese"]:
            font_key = "chinese"
        elif language in ["ja", "japanese"]:
            font_key = "japanese"
        elif language in ["ko", "korean"]:
            font_key = "korean"
        
        font_path = self.default_fonts.get(font_key, self.default_fonts.get("default"))
        
        return FontConfig(
            font_path=font_path or "",
            size=size,
            color=(255, 255, 255, 255),  # White with full opacity
            stroke_width=2,
            stroke_color=(0, 0, 0, 180)  # Semi-transparent black outline
        )
    
    def _calculate_text_size(self, text: str, font: ImageFont.ImageFont, 
                            max_width: int, line_spacing: float = 1.2) -> Tuple[int, int]:
        """
        Calculate the size needed for text with word wrapping.
        
        Args:
            text: Text to measure
            font: Font to use
            max_width: Maximum width for wrapping
            line_spacing: Line spacing multiplier
            
        Returns:
            Tuple of (width, height) needed for the text
        """
        lines = self._wrap_text(text, font, max_width)
        if not lines:
            return 0, 0
        
        # Calculate dimensions
        line_heights = []
        max_line_width = 0
        
        for line in lines:
            bbox = font.getbbox(line)
            line_width = bbox[2] - bbox[0]
            line_height = bbox[3] - bbox[1]
            
            max_line_width = max(max_line_width, line_width)
            line_heights.append(line_height)
        
        total_height = sum(line_heights)
        if len(line_heights) > 1:
            # Add spacing between lines
            spacing = int(max(line_heights) * (line_spacing - 1.0))
            total_height += spacing * (len(line_heights) - 1)
        
        return max_line_width, total_height
    
    def _wrap_text(self, text: str, font: ImageFont.ImageFont, max_width: int) -> List[str]:
        """
        Wrap text to fit within specified width.
        
        Args:
            text: Text to wrap
            font: Font to use for measurement
            max_width: Maximum width in pixels
            
        Returns:
            List of text lines
        """
        if not text.strip():
            return []
        
        words = text.split()
        lines = []
        current_line = []
        
        for word in words:
            test_line = " ".join(current_line + [word])
            bbox = font.getbbox(test_line)
            line_width = bbox[2] - bbox[0]
            
            if line_width <= max_width or not current_line:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(" ".join(current_line))
                current_line = [word]
        
        if current_line:
            lines.append(" ".join(current_line))
        
        return lines
    
    def _calculate_text_position(self, text_area: TextArea, text_size: Tuple[int, int], 
                                alignment: str = "center", 
                                vertical_alignment: str = "center") -> Tuple[int, int]:
        """
        Calculate the position for text within a text area.
        
        Args:
            text_area: Text area boundaries
            text_size: Size of the text (width, height)
            alignment: Horizontal alignment
            vertical_alignment: Vertical alignment
            
        Returns:
            Tuple of (x, y) position for text
        """
        text_width, text_height = text_size
        
        # Horizontal positioning
        if alignment == "left":
            x = text_area.x
        elif alignment == "right":
            x = text_area.x + text_area.width - text_width
        else:  # center
            x = text_area.x + (text_area.width - text_width) // 2
        
        # Vertical positioning
        if vertical_alignment == "top":
            y = text_area.y
        elif vertical_alignment == "bottom":
            y = text_area.y + text_area.height - text_height
        else:  # center
            y = text_area.y + (text_area.height - text_height) // 2
        
        return int(x), int(y)
    
    def _draw_text_with_style(self, draw: ImageDraw.ImageDraw, text: str, 
                             position: Tuple[int, int], text_style: TextStyle,
                             text_area: TextArea) -> None:
        """
        Draw text with specified styling.
        
        Args:
            draw: PIL ImageDraw object
            text: Text to draw
            position: Starting position (x, y)
            text_style: Text styling configuration
            text_area: Text area for boundary checking
        """
        font = self._get_font(text_style.font_config)
        lines = self._wrap_text(text, font, text_area.width) if text_style.word_wrap else [text]
        
        x, y = position
        
        for i, line in enumerate(lines):
            # Calculate line position
            bbox = font.getbbox(line)
            line_height = bbox[3] - bbox[1]
            
            line_x = x
            if text_style.alignment == "center":
                line_width = bbox[2] - bbox[0]
                line_x = x + (text_area.width - line_width) // 2 - x + text_area.x
            elif text_style.alignment == "right":
                line_width = bbox[2] - bbox[0]
                line_x = text_area.x + text_area.width - line_width
            
            line_y = y + i * int(line_height * text_style.line_spacing)
            
            # Draw shadow if enabled
            if text_style.shadow:
                shadow_x = line_x + text_style.shadow_offset[0]
                shadow_y = line_y + text_style.shadow_offset[1]
                
                draw.text(
                    (shadow_x, shadow_y),
                    line,
                    font=font,
                    fill=text_style.shadow_color
                )
            
            # Draw main text
            draw.text(
                (line_x, line_y),
                line,
                font=font,
                fill=text_style.font_config.color,
                stroke_width=text_style.font_config.stroke_width,
                stroke_fill=text_style.font_config.stroke_color
            )
    
    def _enhance_image_quality(self, image: Image.Image) -> Image.Image:
        """
        Enhance image quality for better appearance.
        
        Args:
            image: PIL Image to enhance
            
        Returns:
            Enhanced PIL Image
        """
        try:
            # Slight sharpening
            enhancer = ImageEnhance.Sharpness(image)
            image = enhancer.enhance(1.1)
            
            # Slight contrast enhancement
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(1.05)
            
            return image
            
        except Exception as e:
            logger.warning(f"Failed to enhance image quality: {str(e)}")
            return image
    
    def compose_image(self, template: RichMessageTemplate, content: GeneratedContent,
                     output_path: Optional[str] = None, 
                     template_image_path: Optional[str] = None) -> CompositionResult:
        """
        Compose text content onto a template image.
        
        Args:
            template: Template configuration
            content: Generated content to overlay
            output_path: Optional output file path
            template_image_path: Path to template image file
            
        Returns:
            CompositionResult with success status and image data
        """
        try:
            # Load template image
            if template_image_path and os.path.exists(template_image_path):
                template_img = Image.open(template_image_path)
            else:
                logger.error(f"Template image not found: {template_image_path}")
                return CompositionResult(
                    success=False,
                    error_message="Template image not found"
                )
            
            # Convert to RGBA for transparency support
            if template_img.mode != 'RGBA':
                template_img = template_img.convert('RGBA')
            
            # Create a copy for drawing
            final_img = template_img.copy()
            draw = ImageDraw.Draw(final_img)
            
            # Get text areas from template
            text_areas = template.text_areas
            if not text_areas:
                logger.warning("No text areas defined in template")
                # Create a default text area
                img_width, img_height = final_img.size
                text_areas = [TextArea(
                    x=int(img_width * 0.1),
                    y=int(img_height * 0.3),
                    width=int(img_width * 0.8),
                    height=int(img_height * 0.4),
                    alignment="center"
                )]
            
            # Select font based on content language
            font_config = self._select_font_for_language(
                content.language, 
                size=42,  # Base size, will be adjusted
                bold=True
            )
            
            # Create text style
            text_style = TextStyle(
                font_config=font_config,
                alignment="center",
                vertical_alignment="center",
                word_wrap=True,
                shadow=True,
                shadow_offset=(3, 3),
                shadow_color=(0, 0, 0, 150)
            )
            
            # Compose title and content
            texts_to_draw = []
            
            # Title (if it fits)
            if content.title and len(text_areas) >= 1:
                title_area = text_areas[0]
                title_style = TextStyle(
                    font_config=FontConfig(
                        font_path=font_config.font_path,
                        size=48,  # Larger for title
                        color=(255, 255, 255, 255),
                        stroke_width=3,
                        stroke_color=(0, 0, 0, 200)
                    ),
                    alignment=title_area.alignment or "center",
                    vertical_alignment="center",
                    word_wrap=True,
                    shadow=True,
                    shadow_offset=(3, 3),
                    shadow_color=(0, 0, 0, 180)
                )
                texts_to_draw.append((content.title, title_area, title_style))
            
            # Content (use second area if available, otherwise share first area)
            if content.content:
                if len(text_areas) >= 2:
                    content_area = text_areas[1]
                else:
                    # Share the area, position content below title
                    content_area = TextArea(
                        x=text_areas[0].x,
                        y=text_areas[0].y + int(text_areas[0].height * 0.6),
                        width=text_areas[0].width,
                        height=int(text_areas[0].height * 0.4),
                        alignment=text_areas[0].alignment
                    )
                
                content_style = TextStyle(
                    font_config=FontConfig(
                        font_path=font_config.font_path,
                        size=32,  # Smaller for content
                        color=(255, 255, 255, 255),
                        stroke_width=2,
                        stroke_color=(0, 0, 0, 160)
                    ),
                    alignment=content_area.alignment or "center",
                    vertical_alignment="center",
                    word_wrap=True,
                    shadow=True,
                    shadow_offset=(2, 2),
                    shadow_color=(0, 0, 0, 140)
                )
                texts_to_draw.append((content.content, content_area, content_style))
            
            # Draw all texts
            for text, area, style in texts_to_draw:
                font = self._get_font(style.font_config)
                text_size = self._calculate_text_size(text, font, area.width, style.line_spacing)
                
                # Adjust font size if text doesn't fit
                original_size = style.font_config.size
                while text_size[1] > area.height and style.font_config.size > 16:
                    style.font_config.size = int(style.font_config.size * 0.9)
                    font = self._get_font(style.font_config)
                    text_size = self._calculate_text_size(text, font, area.width, style.line_spacing)
                
                if text_size[1] > area.height:
                    logger.warning(f"Text may not fit in area: {text_size[1]} > {area.height}")
                
                # Calculate position
                position = self._calculate_text_position(
                    area, text_size, 
                    style.alignment, 
                    style.vertical_alignment
                )
                
                # Draw the text
                self._draw_text_with_style(draw, text, position, style, area)
                
                # Reset font size for next text
                style.font_config.size = original_size
            
            # Enhance image quality
            final_img = self._enhance_image_quality(final_img)
            
            # Convert back to RGB for JPEG output
            if final_img.mode == 'RGBA':
                # Create white background for transparency
                rgb_img = Image.new('RGB', final_img.size, (255, 255, 255))
                rgb_img.paste(final_img, mask=final_img.split()[-1])  # Use alpha as mask
                final_img = rgb_img
            
            # Save image
            if not output_path:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"rich_message_{timestamp}_{template.template_id}.jpg"
                output_path = os.path.join(self.output_dir, filename)
            
            # Ensure output directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Save with optimization
            final_img.save(
                output_path, 
                'JPEG', 
                quality=90, 
                optimize=True,
                progressive=True
            )
            
            # Get image data for return
            img_buffer = io.BytesIO()
            final_img.save(img_buffer, format='JPEG', quality=90, optimize=True)
            image_data = img_buffer.getvalue()
            
            # Create metadata
            metadata = {
                "template_id": template.template_id,
                "content_category": content.category.value,
                "content_language": content.language,
                "image_size": final_img.size,
                "file_size_bytes": len(image_data),
                "text_areas_used": len(texts_to_draw),
                "fonts_used": list(set([style.font_config.font_path for _, _, style in texts_to_draw]))
            }
            
            logger.info(f"Successfully composed Rich Message image: {output_path}")
            
            return CompositionResult(
                success=True,
                image_path=output_path,
                image_data=image_data,
                image_size=final_img.size,
                metadata=metadata
            )
            
        except Exception as e:
            logger.error(f"Image composition failed: {str(e)}")
            return CompositionResult(
                success=False,
                error_message=str(e)
            )
    
    def create_rich_message_image(self, template: RichMessageTemplate, 
                                 content: GeneratedContent,
                                 template_image_path: str) -> Optional[str]:
        """
        Create a Rich Message image and return the file path.
        
        Args:
            template: Template configuration
            content: Generated content
            template_image_path: Path to template image
            
        Returns:
            Path to composed image file or None if failed
        """
        result = self.compose_image(template, content, template_image_path=template_image_path)
        
        if result.success:
            return result.image_path
        else:
            logger.error(f"Failed to create Rich Message image: {result.error_message}")
            return None
    
    def get_image_as_base64(self, image_path: str) -> Optional[str]:
        """
        Convert image file to base64 string for API transmission.
        
        Args:
            image_path: Path to image file
            
        Returns:
            Base64 encoded image string or None if failed
        """
        try:
            with open(image_path, 'rb') as f:
                image_data = f.read()
            
            return base64.b64encode(image_data).decode('utf-8')
            
        except Exception as e:
            logger.error(f"Failed to encode image as base64: {str(e)}")
            return None
    
    def validate_image_for_line(self, image_path: str) -> Dict[str, Any]:
        """
        Validate image meets LINE Rich Message requirements.
        
        Args:
            image_path: Path to image file
            
        Returns:
            Validation results
        """
        validation_result = {
            "valid": False,
            "issues": [],
            "recommendations": [],
            "image_info": {}
        }
        
        try:
            if not os.path.exists(image_path):
                validation_result["issues"].append("Image file not found")
                return validation_result
            
            # Check file size
            file_size_mb = os.path.getsize(image_path) / (1024 * 1024)
            validation_result["image_info"]["file_size_mb"] = file_size_mb
            
            if file_size_mb > 1.0:  # LINE limit is 1MB for Rich Menu images
                validation_result["issues"].append(f"File size too large: {file_size_mb:.2f}MB > 1.0MB")
                validation_result["recommendations"].append("Reduce image quality or dimensions")
            
            # Check image dimensions
            with Image.open(image_path) as img:
                width, height = img.size
                validation_result["image_info"]["dimensions"] = {"width": width, "height": height}
                validation_result["image_info"]["format"] = img.format
                
                # LINE Rich Message optimal size is 2500x1686px
                if width != 2500 or height != 1686:
                    validation_result["issues"].append(f"Non-optimal dimensions: {width}x{height} (recommended: 2500x1686)")
                    validation_result["recommendations"].append("Resize to 2500x1686 for optimal display")
                
                # Check aspect ratio
                aspect_ratio = width / height
                optimal_ratio = 2500 / 1686
                if abs(aspect_ratio - optimal_ratio) > 0.1:
                    validation_result["issues"].append(f"Aspect ratio may cause distortion: {aspect_ratio:.2f}")
            
            # If no critical issues, mark as valid
            validation_result["valid"] = len([issue for issue in validation_result["issues"] 
                                           if "file size" in issue.lower()]) == 0
            
        except Exception as e:
            validation_result["issues"].append(f"Validation error: {str(e)}")
        
        return validation_result
    
    def clear_font_cache(self) -> None:
        """Clear the font cache."""
        self.font_cache.clear()
        logger.info("Font cache cleared")
    
    def get_composition_stats(self) -> Dict[str, Any]:
        """
        Get composition statistics.
        
        Returns:
            Dictionary with statistics
        """
        return {
            "cached_fonts": len(self.font_cache),
            "available_fonts": len(self.default_fonts),
            "output_directory": self.output_dir,
            "font_types": list(self.default_fonts.keys())
        }