# Rich Message Template Design Guidelines

## Overview
This document provides comprehensive guidelines for creating Rich Message templates using Canva that meet LINE Bot API specifications and user experience requirements.

## Technical Specifications

### Image Requirements
- **Dimensions**: 2500×1686 pixels (exact LINE Rich Message specification)
- **Aspect Ratio**: 3:2 (landscape orientation)
- **File Format**: PNG or JPEG
- **File Size**: Maximum 1MB per template
- **Color Space**: sRGB
- **DPI**: 72 DPI (web optimized)

### Text Area Specifications
Templates must include designated areas for dynamic text overlay:

#### Primary Text Area (Title)
- **Position**: Upper portion of template
- **Dimensions**: ~600×200 pixels
- **Coordinates**: X: 200, Y: 150 (approximate)
- **Font Size Range**: 48-72px
- **Character Limit**: 50 characters maximum
- **Background**: Semi-transparent overlay recommended for readability

#### Secondary Text Area (Content)
- **Position**: Lower-middle portion
- **Dimensions**: ~800×300 pixels  
- **Coordinates**: X: 200, Y: 600 (approximate)
- **Font Size Range**: 24-36px
- **Character Limit**: 150 characters maximum
- **Line Height**: 1.4-1.6 for readability

## Theme-Specific Design Guidelines

### 1. Morning Energy Theme
**Purpose**: Energize and motivate users to start their day

**Visual Elements**:
- Sunrise/dawn imagery
- Bright, warm colors (oranges, yellows, light blues)
- Upward movement patterns (rays, arrows, gradients)
- Fresh, clean aesthetic

**Color Palette**:
- Primary: #FF6B35 (energetic orange)
- Secondary: #F7931E (warm yellow)
- Accent: #87CEEB (sky blue)
- Text Overlay: #FFFFFF with 80% opacity background

**Typography Recommendations**:
- Bold, sans-serif fonts
- High contrast for morning visibility
- Clean, modern appearance

### 2. Evening Calm Theme
**Purpose**: Provide relaxation and peaceful closure to the day

**Visual Elements**:
- Sunset/twilight imagery
- Cool, soothing colors (purples, blues, soft pinks)
- Gentle, flowing patterns
- Minimalist, serene composition

**Color Palette**:
- Primary: #6A5ACD (slate blue)
- Secondary: #DDA0DD (plum)
- Accent: #F0E68C (khaki)
- Text Overlay: #FFFFFF with 70% opacity background

**Typography Recommendations**:
- Softer, rounded fonts
- Lower contrast for evening comfort
- Calming, readable appearance

### 3. Productivity Theme
**Purpose**: Inspire focus, efficiency, and professional growth

**Visual Elements**:
- Clean, geometric patterns
- Professional color schemes
- Minimal distractions
- Goal-oriented imagery (targets, graphs, progress bars)

**Color Palette**:
- Primary: #2E86AB (professional blue)
- Secondary: #A23B72 (accent purple)
- Accent: #F18F01 (energy orange)
- Text Overlay: #FFFFFF with 85% opacity background

**Typography Recommendations**:
- Clean, professional fonts
- High readability
- Business-appropriate styling

### 4. Wellness Theme
**Purpose**: Promote health, balance, and well-being

**Visual Elements**:
- Natural imagery (plants, water, mountains)
- Earth tones and green palettes
- Organic, flowing shapes
- Balance and harmony in composition

**Color Palette**:
- Primary: #4A7C59 (forest green)
- Secondary: #8FBC8F (sage green)
- Accent: #F0F8FF (alice blue)
- Text Overlay: #FFFFFF with 75% opacity background

**Typography Recommendations**:
- Natural, organic fonts
- Comfortable reading experience
- Health-conscious aesthetic

### 5. General Motivation Theme
**Purpose**: Versatile inspiration for various contexts and times

**Visual Elements**:
- Balanced color combinations
- Universal motivational symbols
- Adaptable design elements
- Broad appeal aesthetic

**Color Palette**:
- Primary: #4169E1 (royal blue)
- Secondary: #FF69B4 (hot pink)
- Accent: #32CD32 (lime green)
- Text Overlay: #FFFFFF with 80% opacity background

**Typography Recommendations**:
- Versatile, readable fonts
- Universal appeal
- Flexible styling options

## Text Positioning Guidelines

### Safe Zones
- **Top Margin**: 100px minimum
- **Bottom Margin**: 100px minimum
- **Side Margins**: 150px minimum
- **Text Area Padding**: 50px around text content

### Overlay Backgrounds
All text areas should include semi-transparent backgrounds to ensure readability:
- **Opacity**: 70-85%
- **Color**: Match theme palette
- **Border Radius**: 10-20px for modern appearance
- **Blur Effect**: Optional 5px blur for premium look

### Multi-language Considerations
- **Font Support**: Ensure fonts support Thai, English, and other required languages
- **Text Expansion**: Allow 30% extra space for language variations
- **Character Encoding**: UTF-8 compatible fonts
- **Reading Direction**: Left-to-right primary, consider right-to-left support

## Mobile Optimization

### LINE App Display Requirements
- **Preview Size**: 240×160px (thumbnail)
- **Full View**: Optimized for mobile screen ratios
- **Touch Targets**: Interactive elements minimum 44×44px
- **Readability**: Text legible at various zoom levels

### Device Compatibility
- **iOS**: Test on iPhone SE to iPhone Pro Max
- **Android**: Test on various screen densities
- **Accessibility**: Support for screen readers and high contrast modes

## Quality Assurance Checklist

### Pre-Export Verification
- [ ] Dimensions exactly 2500×1686 pixels
- [ ] File size under 1MB
- [ ] Text areas clearly defined
- [ ] Color contrast ratio >4.5:1 for accessibility
- [ ] No copyrighted elements
- [ ] Brand guidelines compliance

### Post-Export Testing
- [ ] File opens correctly in image viewers
- [ ] Maintains quality when scaled
- [ ] Text overlay positioning accurate
- [ ] Mobile display optimization
- [ ] Cross-platform compatibility

## Template Naming Convention

### File Naming Structure
```
theme_variation_version.png
```

**Examples**:
- `morning_energy_sunrise_v1.png`
- `evening_calm_sunset_v1.png`
- `productivity_geometric_v1.png`
- `wellness_nature_v1.png`
- `motivation_general_v1.png`

### Metadata Requirements
Each template requires corresponding metadata file:
```
theme_variation_version.json
```

## Canva Creation Process

### Step-by-Step Workflow

1. **Setup Canvas**
   - Create custom size: 2500×1686 pixels
   - Set background color matching theme
   - Enable ruler and guides

2. **Design Background**
   - Add primary visual elements
   - Ensure visual hierarchy
   - Maintain brand consistency

3. **Create Text Areas**
   - Add semi-transparent overlays
   - Position according to specifications
   - Test with sample text

4. **Quality Review**
   - Check alignment and spacing
   - Verify color contrast
   - Test readability

5. **Export Preparation**
   - Remove any text placeholders
   - Optimize for file size
   - Maintain quality settings

### Canva-Specific Tips
- Use "Brand Kit" for color consistency
- Leverage "Magic Resize" for variations
- Utilize "Background Remover" for clean compositions
- Apply "Effects" for professional polish

## Integration with Development System

### Template Manager Compatibility
Templates must work with the existing `TemplateManager` class:
- Metadata files in JSON format
- Coordinate systems for text positioning
- Theme classification for automatic selection
- Fallback template designation

### Content Generator Integration
Design considerations for `ContentGenerator`:
- Text length optimization
- Font selection compatibility
- Color scheme coordination
- Dynamic content adaptation

## Accessibility Standards

### WCAG 2.1 Compliance
- **Color Contrast**: Minimum 4.5:1 ratio
- **Text Size**: Scalable and readable
- **Alternative Text**: Descriptive metadata
- **Motion**: Avoid excessive animation

### Inclusive Design
- **Cultural Sensitivity**: Appropriate imagery for global audience
- **Language Support**: Multi-script font compatibility
- **Visual Clarity**: Clear information hierarchy
- **Device Flexibility**: Responsive design principles

## Maintenance and Updates

### Version Control
- Track template versions systematically
- Maintain changelog for design updates
- Archive deprecated templates
- Document design decisions

### Performance Monitoring
- Monitor file size impacts
- Track user engagement per template
- Analyze mobile performance
- Gather user feedback

### Continuous Improvement
- Regular design reviews
- A/B testing for template effectiveness
- User preference analysis
- Industry trend integration

---

**Note**: This document should be updated as new requirements emerge and user feedback is incorporated. Regular review ensures templates remain effective and compliant with both technical and user experience standards.