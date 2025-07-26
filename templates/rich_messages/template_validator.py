#!/usr/bin/env python3
"""
Template Validator for Rich Message Templates

This script validates that template files and metadata meet all requirements
for the Rich Message automation system.
"""

import os
import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from PIL import Image
import jsonschema
from dataclasses import dataclass


@dataclass
class ValidationResult:
    """Represents the result of a template validation"""
    template_id: str
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    file_size: Optional[int] = None
    dimensions: Optional[Tuple[int, int]] = None


class TemplateValidator:
    """Validates Rich Message templates and metadata"""
    
    def __init__(self, templates_dir: str = None):
        if templates_dir is None:
            templates_dir = os.path.join(os.path.dirname(__file__), "backgrounds")
        
        self.templates_dir = Path(templates_dir)
        self.schema_path = Path(__file__).parent / "template_metadata_schema.json"
        
        # Load JSON schema
        try:
            with open(self.schema_path, 'r') as f:
                self.metadata_schema = json.load(f)
        except FileNotFoundError:
            print(f"Warning: Schema file not found at {self.schema_path}")
            self.metadata_schema = None
    
    def validate_all_templates(self) -> List[ValidationResult]:
        """Validate all templates in the templates directory"""
        results = []
        
        # Find all metadata files
        for metadata_file in self.templates_dir.glob("*.json"):
            try:
                template_id = metadata_file.stem
                result = self.validate_template(template_id)
                results.append(result)
            except Exception as e:
                results.append(ValidationResult(
                    template_id=metadata_file.stem,
                    is_valid=False,
                    errors=[f"Validation failed: {str(e)}"],
                    warnings=[]
                ))
        
        return results
    
    def validate_template(self, template_id: str) -> ValidationResult:
        """Validate a single template by ID"""
        errors = []
        warnings = []
        file_size = None
        dimensions = None
        
        # Check metadata file exists
        metadata_path = self.templates_dir / f"{template_id}.json"
        if not metadata_path.exists():
            errors.append(f"Metadata file not found: {metadata_path}")
            return ValidationResult(template_id, False, errors, warnings)
        
        # Load and validate metadata
        try:
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
        except json.JSONDecodeError as e:
            errors.append(f"Invalid JSON in metadata file: {str(e)}")
            return ValidationResult(template_id, False, errors, warnings)
        
        # Validate against schema
        if self.metadata_schema:
            try:
                jsonschema.validate(metadata, self.metadata_schema)
            except jsonschema.ValidationError as e:
                errors.append(f"Metadata schema validation failed: {e.message}")
        
        # Check template image file exists
        image_filename = metadata.get('file_info', {}).get('filename')
        if not image_filename:
            errors.append("No filename specified in metadata")
        else:
            image_path = self.templates_dir / image_filename
            if not image_path.exists():
                errors.append(f"Template image file not found: {image_path}")
            else:
                # Validate image file
                image_errors, image_warnings, file_size, dimensions = self._validate_image_file(
                    image_path, metadata
                )
                errors.extend(image_errors)
                warnings.extend(image_warnings)
        
        # Validate metadata content
        content_errors, content_warnings = self._validate_metadata_content(metadata)
        errors.extend(content_errors)
        warnings.extend(content_warnings)
        
        is_valid = len(errors) == 0
        return ValidationResult(template_id, is_valid, errors, warnings, file_size, dimensions)
    
    def _validate_image_file(self, image_path: Path, metadata: Dict) -> Tuple[List[str], List[str], int, Tuple[int, int]]:
        """Validate image file specifications"""
        errors = []
        warnings = []
        
        try:
            # Check file size
            file_size = image_path.stat().st_size
            max_size = 1024 * 1024  # 1MB
            
            if file_size > max_size:
                errors.append(f"File size {file_size} bytes exceeds maximum {max_size} bytes")
            elif file_size > max_size * 0.9:  # Warning at 90% of limit
                warnings.append(f"File size {file_size} bytes is close to maximum limit")
            
            # Open and validate image
            with Image.open(image_path) as img:
                width, height = img.size
                
                # Check dimensions
                expected_width = 2500
                expected_height = 1686
                
                if width != expected_width or height != expected_height:
                    errors.append(f"Image dimensions {width}×{height} do not match required {expected_width}×{expected_height}")
                
                # Check format
                format_from_metadata = metadata.get('file_info', {}).get('format', '').upper()
                actual_format = img.format.upper() if img.format else 'UNKNOWN'
                
                if format_from_metadata and format_from_metadata != actual_format:
                    errors.append(f"Image format {actual_format} does not match metadata format {format_from_metadata}")
                
                # Check if format is supported
                if actual_format not in ['PNG', 'JPEG']:
                    errors.append(f"Unsupported image format: {actual_format}")
                
                # Validate color mode
                if img.mode not in ['RGB', 'RGBA']:
                    warnings.append(f"Image color mode {img.mode} may not be optimal (RGB/RGBA recommended)")
                
                return errors, warnings, file_size, (width, height)
                
        except Exception as e:
            errors.append(f"Error reading image file: {str(e)}")
            return errors, warnings, 0, (0, 0)
    
    def _validate_metadata_content(self, metadata: Dict) -> Tuple[List[str], List[str]]:
        """Validate metadata content and logic"""
        errors = []
        warnings = []
        
        # Check required fields are present and valid
        template_id = metadata.get('template_id')
        if not template_id:
            errors.append("Missing template_id")
        
        theme = metadata.get('theme')
        valid_themes = ['morning_energy', 'evening_calm', 'productivity', 'wellness', 'general_motivation']
        if theme not in valid_themes:
            errors.append(f"Invalid theme '{theme}'. Must be one of: {valid_themes}")
        
        # Validate text areas
        text_areas = metadata.get('text_areas', {})
        
        for area_name in ['title', 'content']:
            area = text_areas.get(area_name, {})
            
            # Check position
            position = area.get('position', {})
            x, y = position.get('x', 0), position.get('y', 0)
            
            if x < 0 or x > 2500:
                errors.append(f"{area_name} X position {x} is out of bounds (0-2500)")
            if y < 0 or y > 1686:
                errors.append(f"{area_name} Y position {y} is out of bounds (0-1686)")
            
            # Check dimensions
            dimensions = area.get('dimensions', {})
            width, height = dimensions.get('width', 0), dimensions.get('height', 0)
            
            if x + width > 2500:
                errors.append(f"{area_name} extends beyond image width ({x + width} > 2500)")
            if y + height > 1686:
                errors.append(f"{area_name} extends beyond image height ({y + height} > 1686)")
            
            # Check safe zones
            safe_margin = 100
            if x < safe_margin or y < safe_margin:
                warnings.append(f"{area_name} may be too close to edge (less than {safe_margin}px margin)")
            
            # Check font size ranges
            font_range = area.get('font_size_range', {})
            min_size, max_size = font_range.get('min', 0), font_range.get('max', 0)
            
            if min_size >= max_size:
                errors.append(f"{area_name} font size range invalid (min >= max)")
        
        # Validate color palette
        color_palette = metadata.get('color_palette', {})
        required_colors = ['primary', 'secondary', 'accent']
        
        for color_name in required_colors:
            color_value = color_palette.get(color_name)
            if not color_value:
                errors.append(f"Missing {color_name} color in palette")
            elif not self._is_valid_hex_color(color_value):
                errors.append(f"Invalid hex color format for {color_name}: {color_value}")
        
        # Check accessibility
        accessibility = metadata.get('accessibility', {})
        contrast_ratio = accessibility.get('color_contrast_ratio', 0)
        
        if contrast_ratio < 4.5:
            errors.append(f"Color contrast ratio {contrast_ratio} does not meet accessibility standards (minimum 4.5)")
        elif contrast_ratio < 7:
            warnings.append(f"Color contrast ratio {contrast_ratio} meets minimum but could be improved for better accessibility")
        
        return errors, warnings
    
    def _is_valid_hex_color(self, color: str) -> bool:
        """Validate hex color format"""
        if not isinstance(color, str):
            return False
        
        if not color.startswith('#'):
            return False
        
        if len(color) != 7:
            return False
        
        try:
            int(color[1:], 16)
            return True
        except ValueError:
            return False
    
    def generate_validation_report(self, results: List[ValidationResult]) -> str:
        """Generate a comprehensive validation report"""
        total_templates = len(results)
        valid_templates = sum(1 for r in results if r.is_valid)
        invalid_templates = total_templates - valid_templates
        
        report = f"""
# Template Validation Report

## Summary
- **Total Templates**: {total_templates}
- **Valid Templates**: {valid_templates}
- **Invalid Templates**: {invalid_templates}
- **Success Rate**: {(valid_templates/total_templates*100):.1f}%

## Template Details

"""
        
        for result in results:
            status = "✅ VALID" if result.is_valid else "❌ INVALID"
            report += f"### {result.template_id} - {status}\n\n"
            
            if result.file_size:
                report += f"- **File Size**: {result.file_size:,} bytes ({result.file_size/1024/1024:.2f} MB)\n"
            
            if result.dimensions:
                report += f"- **Dimensions**: {result.dimensions[0]}×{result.dimensions[1]} pixels\n"
            
            if result.errors:
                report += f"- **Errors**: {len(result.errors)}\n"
                for error in result.errors:
                    report += f"  - ❌ {error}\n"
            
            if result.warnings:
                report += f"- **Warnings**: {len(result.warnings)}\n"
                for warning in result.warnings:
                    report += f"  - ⚠️ {warning}\n"
            
            report += "\n"
        
        return report


def main():
    """Command line interface for template validation"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Validate Rich Message templates")
    parser.add_argument("--templates-dir", help="Directory containing templates")
    parser.add_argument("--template-id", help="Validate specific template by ID")
    parser.add_argument("--output", help="Output report to file")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    
    args = parser.parse_args()
    
    validator = TemplateValidator(args.templates_dir)
    
    if args.template_id:
        results = [validator.validate_template(args.template_id)]
    else:
        results = validator.validate_all_templates()
    
    if args.json:
        # Output JSON format
        json_results = []
        for result in results:
            json_results.append({
                'template_id': result.template_id,
                'is_valid': result.is_valid,
                'errors': result.errors,
                'warnings': result.warnings,
                'file_size': result.file_size,
                'dimensions': result.dimensions
            })
        
        output = json.dumps(json_results, indent=2)
    else:
        # Output text report
        output = validator.generate_validation_report(results)
    
    if args.output:
        with open(args.output, 'w') as f:
            f.write(output)
        print(f"Report saved to {args.output}")
    else:
        print(output)
    
    # Exit with error code if any templates are invalid
    if any(not r.is_valid for r in results):
        sys.exit(1)


if __name__ == "__main__":
    main()