#!/usr/bin/env python3
"""
Template Converter for LINE Rich Message Specifications

Converts existing template images to meet LINE Rich Message API requirements:
- Resize to 2500×1686 pixels
- Optimize file size to under 1MB
- Remove text overlays (manual step guidance)
- Generate metadata files
"""

import os
import json
from datetime import datetime, timezone
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from typing import Dict, List, Tuple, Optional
import re


class TemplateConverter:
    """Converts templates to LINE Rich Message specifications"""
    
    def __init__(self, input_dir: str = None, output_dir: str = None):
        if input_dir is None:
            input_dir = "backgrounds"
        if output_dir is None:
            output_dir = "backgrounds"
            
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # LINE Rich Message specifications
        self.target_width = 2500
        self.target_height = 1686
        self.max_file_size = 1024 * 1024  # 1MB
        
        # Theme categorization patterns
        self.theme_patterns = {
            'morning_energy': ['morning', 'sunrise', 'bright', 'energy', 'uplifting'],
            'evening_calm': ['evening', 'sunset', 'calm', 'peaceful', 'serene'],
            'productivity': ['productivity', 'clean', 'focus', 'digital', 'overhead'],
            'wellness': ['wellness', 'nature', 'mindful', 'peaceful', 'cats', 'walking'],
            'general_motivation': ['motivation', 'inspiration', 'abstract', 'bright', 'launch', 'running', 'lion', 'gorilla']
        }
    
    def convert_all_templates(self) -> Dict[str, any]:
        """Convert all templates in the input directory"""
        results = {
            'converted': [],
            'skipped': [],
            'errors': []
        }
        
        # Find all PNG files that aren't already converted
        existing_converted = {
            'morning_energy_sunrise_v1.png',
            'evening_calm_sunset_v1.png', 
            'productivity_geometric_v1.png',
            'wellness_nature_v1.png',
            'motivation_general_v1.png'
        }
        
        for image_file in self.input_dir.glob("*.png"):
            if image_file.name in existing_converted:
                results['skipped'].append(f"Already converted: {image_file.name}")
                continue
                
            try:
                print(f"Converting: {image_file.name}")
                converted_info = self.convert_template(image_file)
                results['converted'].append(converted_info)
            except Exception as e:
                error_msg = f"Error converting {image_file.name}: {str(e)}"
                print(f"❌ {error_msg}")
                results['errors'].append(error_msg)
        
        return results
    
    def convert_template(self, image_path: Path) -> Dict[str, any]:
        """Convert a single template"""
        # Determine theme from filename
        theme = self._categorize_theme(image_path.name)
        
        # Generate new filename
        base_name = image_path.stem
        new_filename = f"{theme}_{base_name}_v1.png"
        new_path = self.output_dir / new_filename
        
        # Load and convert image
        with Image.open(image_path) as img:
            # Convert to RGB if necessary
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Resize to target dimensions
            resized_img = img.resize((self.target_width, self.target_height), Image.Resampling.LANCZOS)
            
            # Save with optimization
            quality = 95
            while quality > 50:
                resized_img.save(new_path, 'PNG', optimize=True)
                
                file_size = new_path.stat().st_size
                if file_size <= self.max_file_size:
                    break
                    
                # If still too large, try JPEG with reducing quality
                if quality > 85:
                    quality -= 5
                    resized_img.save(new_path.with_suffix('.jpg'), 'JPEG', quality=quality, optimize=True)
                    if new_path.with_suffix('.jpg').stat().st_size <= self.max_file_size:
                        new_path.unlink()  # Remove PNG
                        new_path = new_path.with_suffix('.jpg')
                        new_filename = new_filename.replace('.png', '.jpg')
                        break
                else:
                    break
                    
            # Generate metadata
            metadata = self._generate_metadata(new_filename, theme, new_path)
            metadata_path = self.output_dir / f"{new_filename.rsplit('.', 1)[0]}.json"
            
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2)
            
            file_size = new_path.stat().st_size
            
            return {
                'original': image_path.name,
                'converted': new_filename,
                'theme': theme,
                'dimensions': f"{self.target_width}×{self.target_height}",
                'file_size': file_size,
                'under_limit': file_size <= self.max_file_size,
                'metadata_created': True
            }
    
    def _categorize_theme(self, filename: str) -> str:
        """Categorize template into theme based on filename"""
        filename_lower = filename.lower()
        
        for theme, keywords in self.theme_patterns.items():
            for keyword in keywords:
                if keyword in filename_lower:
                    return theme
        
        # Default to general motivation if no match
        return 'general_motivation'
    
    def _generate_metadata(self, filename: str, theme: str, image_path: Path) -> Dict:
        """Generate metadata for the converted template"""
        file_size = image_path.stat().st_size
        file_format = 'PNG' if filename.endswith('.png') else 'JPEG'
        
        # Template ID from filename (without extension)
        template_id = filename.rsplit('.', 1)[0]
        
        # Theme-specific configurations
        theme_configs = {
            'morning_energy': {
                'colors': {'primary': '#FF6B35', 'secondary': '#F7931E', 'accent': '#87CEEB'},
                'title_pos': {'x': 200, 'y': 150},
                'content_pos': {'x': 200, 'y': 600},
                'description': 'Energetic morning theme'
            },
            'evening_calm': {
                'colors': {'primary': '#6A5ACD', 'secondary': '#DDA0DD', 'accent': '#F0E68C'},
                'title_pos': {'x': 250, 'y': 200},
                'content_pos': {'x': 250, 'y': 650},
                'description': 'Calming evening theme'
            },
            'productivity': {
                'colors': {'primary': '#2E86AB', 'secondary': '#A23B72', 'accent': '#F18F01'},
                'title_pos': {'x': 300, 'y': 180},
                'content_pos': {'x': 300, 'y': 580},
                'description': 'Professional productivity theme'
            },
            'wellness': {
                'colors': {'primary': '#4A7C59', 'secondary': '#8FBC8F', 'accent': '#F0F8FF'},
                'title_pos': {'x': 220, 'y': 160},
                'content_pos': {'x': 220, 'y': 620},
                'description': 'Natural wellness theme'
            },
            'general_motivation': {
                'colors': {'primary': '#4169E1', 'secondary': '#FF69B4', 'accent': '#32CD32'},
                'title_pos': {'x': 260, 'y': 170},
                'content_pos': {'x': 260, 'y': 600},
                'description': 'Universal motivation theme'
            }
        }
        
        config = theme_configs.get(theme, theme_configs['general_motivation'])
        
        return {
            "template_id": template_id,
            "template_name": f"{theme.replace('_', ' ').title()} - {template_id.split('_', 2)[-1].title()}",
            "theme": theme,
            "file_info": {
                "filename": filename,
                "file_size": file_size,
                "dimensions": {
                    "width": self.target_width,
                    "height": self.target_height
                },
                "format": file_format
            },
            "text_areas": {
                "title": {
                    "position": config['title_pos'],
                    "dimensions": {"width": 600, "height": 200},
                    "font_size_range": {"min": 48, "max": 72},
                    "max_characters": 50,
                    "text_color": "#FFFFFF",
                    "background_overlay": {
                        "enabled": True,
                        "color": config['colors']['primary'],
                        "opacity": 0.8
                    }
                },
                "content": {
                    "position": config['content_pos'],
                    "dimensions": {"width": 800, "height": 300},
                    "font_size_range": {"min": 24, "max": 36},
                    "max_characters": 150,
                    "line_height": 1.5,
                    "text_color": "#FFFFFF",
                    "background_overlay": {
                        "enabled": True,
                        "color": config['colors']['secondary'],
                        "opacity": 0.75
                    }
                }
            },
            "color_palette": {
                "primary": config['colors']['primary'],
                "secondary": config['colors']['secondary'],
                "accent": config['colors']['accent'],
                "background": "#F8F9FA",
                "text_overlay": "#FFFFFF"
            },
            "design_elements": {
                "style": config['description'],
                "mood": theme.replace('_', ' '),
                "keywords": [theme, "converted", "optimized"],
                "imagery_type": "converted from original design",
                "complexity_level": "moderate"
            },
            "usage_guidelines": {
                "best_times": ["any time"] if theme == 'general_motivation' else 
                             ["06:00-10:00"] if theme == 'morning_energy' else
                             ["18:00-22:00"] if theme == 'evening_calm' else
                             ["09:00-17:00"] if theme == 'productivity' else
                             ["07:00-19:00"],
                "target_audience": "general users",
                "content_types": ["motivational content", "daily messages"],
                "avoid_content": ["inappropriate content"]
            },
            "accessibility": {
                "color_contrast_ratio": 4.5,
                "text_readability": "good",
                "mobile_optimized": True,
                "screen_reader_friendly": True
            },
            "created_date": datetime.now(timezone.utc).isoformat(),
            "last_modified": datetime.now(timezone.utc).isoformat(),
            "version": "v1.0.0",
            "created_by": "Template Converter",
            "approved_by": "System",
            "status": "draft"
        }
    
    def generate_conversion_report(self, results: Dict) -> str:
        """Generate a detailed conversion report"""
        total_processed = len(results['converted']) + len(results['skipped']) + len(results['errors'])
        success_rate = len(results['converted']) / total_processed * 100 if total_processed > 0 else 0
        
        report = f"""
# Template Conversion Report

## Summary
- **Total Templates Processed**: {total_processed}
- **Successfully Converted**: {len(results['converted'])}
- **Skipped (Already Converted)**: {len(results['skipped'])}
- **Errors**: {len(results['errors'])}
- **Success Rate**: {success_rate:.1f}%

## Converted Templates

"""
        
        for template in results['converted']:
            status = "✅ COMPLIANT" if template['under_limit'] else "⚠️ SIZE WARNING"
            
            report += f"### {template['converted']} - {status}\n\n"
            report += f"- **Original**: {template['original']}\n"
            report += f"- **Theme**: {template['theme']}\n"
            report += f"- **Dimensions**: {template['dimensions']}\n"
            report += f"- **File Size**: {template['file_size']:,} bytes ({template['file_size']/1024/1024:.2f} MB)\n"
            report += f"- **Metadata Created**: {'✅' if template['metadata_created'] else '❌'}\n\n"
        
        if results['skipped']:
            report += "## Skipped Templates\n\n"
            for skip_msg in results['skipped']:
                report += f"- {skip_msg}\n"
            report += "\n"
        
        if results['errors']:
            report += "## Conversion Errors\n\n"
            for error_msg in results['errors']:
                report += f"- ❌ {error_msg}\n"
            report += "\n"
        
        report += """
## Next Steps

1. **Review Converted Templates**: Check visual quality and positioning
2. **Text Overlay Testing**: Use ImageComposer to test text positioning
3. **Manual Cleanup**: Some templates may need manual text removal
4. **Validation**: Run template_validator.py to verify compliance
5. **Integration Testing**: Test with Rich Message service

## Notes

- All templates have been resized to 2500×1686 pixels
- File sizes optimized to meet 1MB limit where possible
- Metadata files generated with positioning specifications
- Templates may need manual text removal for clean backgrounds
"""
        
        return report


def main():
    """Command line interface for template conversion"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Convert templates to LINE Rich Message specifications")
    parser.add_argument("--input-dir", default="backgrounds", help="Input directory with templates")
    parser.add_argument("--output-dir", default="backgrounds", help="Output directory for converted templates")
    parser.add_argument("--report", help="Output conversion report to file")
    
    args = parser.parse_args()
    
    converter = TemplateConverter(args.input_dir, args.output_dir)
    
    print("Starting template conversion...")
    results = converter.convert_all_templates()
    
    print(f"\nConversion completed!")
    print(f"✅ Converted: {len(results['converted'])}")
    print(f"⏭️ Skipped: {len(results['skipped'])}")
    print(f"❌ Errors: {len(results['errors'])}")
    
    # Generate report
    report = converter.generate_conversion_report(results)
    
    if args.report:
        with open(args.report, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"📄 Report saved to: {args.report}")
    else:
        print("\n" + "="*50)
        print(report)


if __name__ == "__main__":
    main()