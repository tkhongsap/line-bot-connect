#!/usr/bin/env python3
"""
Sample Template Creator

Creates placeholder template images that demonstrate the layout and positioning
for each theme. These serve as examples until actual Canva templates are created.
"""

from PIL import Image, ImageDraw, ImageFont
import os
from typing import Dict, Tuple
import json


class SampleTemplateCreator:
    """Creates sample template images for demonstration purposes"""
    
    def __init__(self, output_dir: str = None):
        if output_dir is None:
            output_dir = os.path.join(os.path.dirname(__file__), "backgrounds")
        
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        
        # Template dimensions
        self.width = 2500
        self.height = 1686
    
    def create_all_sample_templates(self):
        """Create sample templates for all themes"""
        themes = [
            'morning_energy_sunrise_v1',
            'evening_calm_sunset_v1', 
            'productivity_geometric_v1',
            'wellness_nature_v1',
            'motivation_general_v1'
        ]
        
        for theme in themes:
            print(f"Creating sample template: {theme}")
            self.create_sample_template(theme)
    
    def create_sample_template(self, template_id: str):
        """Create a single sample template"""
        # Load metadata
        metadata_path = os.path.join(self.output_dir, f"{template_id}.json")
        if not os.path.exists(metadata_path):
            print(f"Warning: Metadata file not found for {template_id}")
            return
        
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
        
        # Create image
        img = Image.new('RGB', (self.width, self.height), color='white')
        draw = ImageDraw.Draw(img)
        
        # Get theme colors
        colors = metadata.get('color_palette', {})
        primary = colors.get('primary', '#4169E1')
        secondary = colors.get('secondary', '#FF69B4')
        accent = colors.get('accent', '#32CD32')
        
        # Convert hex to RGB
        primary_rgb = self._hex_to_rgb(primary)
        secondary_rgb = self._hex_to_rgb(secondary)
        accent_rgb = self._hex_to_rgb(accent)
        
        # Create background based on theme
        theme = metadata.get('theme', 'general_motivation')
        self._create_theme_background(draw, theme, primary_rgb, secondary_rgb, accent_rgb)
        
        # Add text area overlays
        text_areas = metadata.get('text_areas', {})
        
        # Title area
        title_area = text_areas.get('title', {})
        self._draw_text_area(draw, title_area, "TITLE AREA", primary_rgb)
        
        # Content area
        content_area = text_areas.get('content', {})
        self._draw_text_area(draw, content_area, "CONTENT AREA", secondary_rgb)
        
        # Add sample positioning guides
        self._draw_positioning_guides(draw)
        
        # Add theme label
        self._draw_theme_label(draw, theme.replace('_', ' ').title())
        
        # Save image
        filename = metadata.get('file_info', {}).get('filename', f"{template_id}.png")
        output_path = os.path.join(self.output_dir, filename)
        
        # Ensure file size is reasonable
        img.save(output_path, 'PNG', optimize=True)
        
        # Check file size and compress if needed
        file_size = os.path.getsize(output_path)
        max_size = 1024 * 1024  # 1MB
        
        if file_size > max_size:
            # Reduce quality to meet file size requirement
            img.save(output_path, 'JPEG', quality=85, optimize=True)
            print(f"Compressed {filename} to meet size requirements")
        
        print(f"Created sample template: {filename} ({file_size:,} bytes)")
    
    def _hex_to_rgb(self, hex_color: str) -> Tuple[int, int, int]:
        """Convert hex color to RGB tuple"""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    def _create_theme_background(self, draw: ImageDraw.Draw, theme: str, 
                               primary: Tuple[int, int, int], 
                               secondary: Tuple[int, int, int], 
                               accent: Tuple[int, int, int]):
        """Create theme-specific background"""
        
        if theme == 'morning_energy':
            # Sunrise gradient
            for y in range(self.height):
                ratio = y / self.height
                if ratio < 0.3:
                    # Sky (blue to yellow)
                    color = self._blend_colors((135, 206, 235), (255, 255, 224), ratio / 0.3)
                elif ratio < 0.7:
                    # Sunrise (yellow to orange)
                    color = self._blend_colors((255, 255, 224), primary, (ratio - 0.3) / 0.4)
                else:
                    # Foreground (orange)
                    color = primary
                
                draw.line([(0, y), (self.width, y)], fill=color)
            
            # Add sun circle
            sun_x, sun_y = self.width // 3, int(self.height * 0.3)
            sun_radius = 100
            draw.ellipse([sun_x - sun_radius, sun_y - sun_radius, 
                         sun_x + sun_radius, sun_y + sun_radius], 
                        fill=(255, 255, 0, 180))
        
        elif theme == 'evening_calm':
            # Sunset gradient
            for y in range(self.height):
                ratio = y / self.height
                if ratio < 0.4:
                    # Sky (purple to pink)
                    color = self._blend_colors(primary, secondary, ratio / 0.4)
                else:
                    # Ground (darker purple)
                    darker_primary = tuple(max(0, c - 50) for c in primary)
                    color = darker_primary
                
                draw.line([(0, y), (self.width, y)], fill=color)
        
        elif theme == 'productivity':
            # Geometric pattern background
            draw.rectangle([0, 0, self.width, self.height], fill=(248, 249, 250))
            
            # Add geometric shapes
            for i in range(0, self.width, 200):
                for j in range(0, self.height, 200):
                    if (i + j) % 400 == 0:
                        draw.rectangle([i, j, i + 100, j + 100], 
                                     fill=tuple(c + 200 for c in primary if c + 200 <= 255),
                                     outline=primary)
        
        elif theme == 'wellness':
            # Natural gradient
            for y in range(self.height):
                ratio = y / self.height
                if ratio < 0.6:
                    # Sky to horizon
                    color = self._blend_colors((240, 248, 255), primary, ratio / 0.6)
                else:
                    # Ground
                    color = self._blend_colors(primary, secondary, (ratio - 0.6) / 0.4)
                
                draw.line([(0, y), (self.width, y)], fill=color)
            
            # Add simple tree shapes
            for x in range(300, self.width - 300, 400):
                tree_y = int(self.height * 0.6)
                draw.polygon([(x, tree_y), (x - 50, tree_y + 200), (x + 50, tree_y + 200)], 
                           fill=(34, 139, 34))
        
        else:  # general_motivation
            # Abstract motivational pattern
            for y in range(self.height):
                ratio = y / self.height
                color = self._blend_colors(primary, secondary, ratio)
                draw.line([(0, y), (self.width, y)], fill=color)
            
            # Add motivational geometric elements
            center_x, center_y = self.width // 2, self.height // 2
            for i in range(3):
                radius = 50 + i * 30
                draw.ellipse([center_x - radius, center_y - radius,
                            center_x + radius, center_y + radius],
                           outline=accent, width=3)
    
    def _blend_colors(self, color1: Tuple[int, int, int], 
                     color2: Tuple[int, int, int], 
                     ratio: float) -> Tuple[int, int, int]:
        """Blend two RGB colors based on ratio"""
        ratio = max(0, min(1, ratio))
        return tuple(int(c1 * (1 - ratio) + c2 * ratio) for c1, c2 in zip(color1, color2))
    
    def _draw_text_area(self, draw: ImageDraw.Draw, area_config: Dict, 
                       label: str, color: Tuple[int, int, int]):
        """Draw text area overlay"""
        position = area_config.get('position', {})
        dimensions = area_config.get('dimensions', {})
        
        x = position.get('x', 0)
        y = position.get('y', 0)
        width = dimensions.get('width', 200)
        height = dimensions.get('height', 100)
        
        # Draw semi-transparent overlay
        overlay_color = tuple(list(color) + [128])  # Add alpha
        draw.rectangle([x, y, x + width, y + height], 
                      fill=color, outline=(255, 255, 255), width=3)
        
        # Add label text
        try:
            # Try to use a reasonable font size
            font_size = min(height // 4, 48)
            text_x = x + width // 2
            text_y = y + height // 2
            
            # Draw text outline for visibility
            for dx in [-2, 0, 2]:
                for dy in [-2, 0, 2]:
                    if dx != 0 or dy != 0:
                        draw.text((text_x + dx, text_y + dy), label, 
                                fill=(0, 0, 0), anchor="mm")
            
            draw.text((text_x, text_y), label, fill=(255, 255, 255), anchor="mm")
            
        except Exception:
            # Fallback if font issues
            pass
    
    def _draw_positioning_guides(self, draw: ImageDraw.Draw):
        """Draw positioning guides for reference"""
        guide_color = (128, 128, 128)
        
        # Draw margin guides
        margin = 100
        draw.rectangle([margin, margin, self.width - margin, self.height - margin],
                      outline=guide_color, width=2)
        
        # Draw center lines
        draw.line([(self.width // 2, 0), (self.width // 2, self.height)], 
                 fill=guide_color, width=1)
        draw.line([(0, self.height // 2), (self.width, self.height // 2)], 
                 fill=guide_color, width=1)
    
    def _draw_theme_label(self, draw: ImageDraw.Draw, theme_name: str):
        """Draw theme label in corner"""
        try:
            # Position in top-right corner
            x = self.width - 300
            y = 50
            
            # Draw background
            draw.rectangle([x - 20, y - 10, x + 280, y + 40], 
                          fill=(0, 0, 0, 180), outline=(255, 255, 255))
            
            # Draw text
            draw.text((x, y), f"SAMPLE: {theme_name}", fill=(255, 255, 255))
            
        except Exception:
            pass


def main():
    """Create all sample templates"""
    creator = SampleTemplateCreator()
    creator.create_all_sample_templates()
    print("Sample template creation completed!")


if __name__ == "__main__":
    main()