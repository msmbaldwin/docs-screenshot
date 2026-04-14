"""
image_editor.py - Pixel-Precise Image Operations

Handles all image manipulation for Azure documentation screenshots:
- Smart cropping to minimize visible area while keeping context
- PII redaction with background-matched fill + Segoe UI replacement text
- Callout box drawing (3px red rectangles per MS contributor guide)
- DPR-aware coordinate transforms
- PNG optimization for < 200 KB target
"""

import os
import re
from dataclasses import dataclass
from typing import Optional
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np

# Microsoft contributor guide: RGB 233, 28, 28 for callout borders
CALLOUT_COLOR = (233, 28, 28)
CALLOUT_THICKNESS = 3

# Gray border for images with light/dark edges (contributor guide requirement)
GRAY_BORDER_COLOR = (200, 200, 200)
GRAY_BORDER_THICKNESS = 1

# Maximum image width per MS guidelines
MAX_WIDTH_PX = 1200

# Target file size
TARGET_SIZE_KB = 200


def parse_css_color(css_color: str) -> tuple[int, int, int]:
    """Parse CSS color string (rgb/rgba) to RGB tuple."""
    if not css_color:
        return (255, 255, 255)
    
    match = re.match(r'rgba?\((\d+),\s*(\d+),\s*(\d+)', css_color)
    if match:
        return (int(match.group(1)), int(match.group(2)), int(match.group(3)))
    
    # Hex
    if css_color.startswith('#'):
        hex_str = css_color.lstrip('#')
        if len(hex_str) == 3:
            hex_str = ''.join(c * 2 for c in hex_str)
        if len(hex_str) >= 6:
            return (int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16))
    
    return (255, 255, 255)  # default white


def parse_font_size(css_font_size: str) -> float:
    """Parse CSS font-size to points (approximate)."""
    if not css_font_size:
        return 14.0
    match = re.match(r'([\d.]+)px', css_font_size)
    if match:
        return float(match.group(1))
    return 14.0


def get_segoe_ui_font(size_px: float, weight: str = '400') -> ImageFont.FreeTypeFont:
    """
    Get Segoe UI font at the specified pixel size.
    Falls back through variants based on weight.
    """
    # Map CSS font-weight to font file variants
    weight_map = {
        '100': 'segoeuil.ttf',   # Light
        '200': 'segoeuil.ttf',
        '300': 'segoeuisl.ttf',  # Semilight
        '400': 'segoeui.ttf',    # Regular
        '500': 'seguisb.ttf',    # Semibold
        '600': 'seguisb.ttf',
        '700': 'segoeuib.ttf',   # Bold
        '800': 'segoeuib.ttf',
        '900': 'segoeuib.ttf',
        'normal': 'segoeui.ttf',
        'bold': 'segoeuib.ttf',
    }
    
    font_file = weight_map.get(str(weight), 'segoeui.ttf')
    fallbacks = [font_file, 'segoeui.ttf', 'arial.ttf']
    
    # Convert CSS px to roughly equivalent pt for PIL
    # PIL uses points; at 96 DPI, 1px ~ 0.75pt, but PIL TrueType
    # size parameter is in pixels when using size in layout mode
    size_pt = int(size_px)
    
    for fb in fallbacks:
        try:
            return ImageFont.truetype(fb, size_pt)
        except (OSError, IOError):
            continue
    
    return ImageFont.load_default()


@dataclass
class CropRegion:
    """Defines a crop region with padding."""
    x: int
    y: int
    width: int
    height: int
    padding: int = 20


@dataclass
class RedactionSpec:
    """Specification for a single PII redaction."""
    px_rect: dict          # {x, y, width, height} in screenshot pixels
    replacement_text: str
    bg_color: str          # CSS color string
    font_family: str
    font_size: str         # CSS size like "14px"
    font_weight: str       # CSS weight like "400"
    text_color: str        # CSS color string


@dataclass
class CalloutSpec:
    """Specification for a callout box."""
    px_rect: dict          # {x, y, width, height} in screenshot pixels
    color: tuple = None    # RGB tuple, defaults to MS red
    thickness: int = CALLOUT_THICKNESS
    padding: int = 4       # Extra padding around the element
    number: int = 0        # Callout number (0 = plain rectangle, 1+ = numbered circle)


def redact_pii(image: Image.Image, specs: list[RedactionSpec]) -> Image.Image:
    """
    Redact PII from an image by painting over with background color
    and rendering replacement text in matching font.
    
    Args:
        image: PIL Image to modify (modified in-place and returned)
        specs: List of RedactionSpec objects
        
    Returns:
        Modified image
    """
    draw = ImageDraw.Draw(image)
    
    for spec in specs:
        rect = spec.px_rect
        x = rect.get('x', 0)
        y = rect.get('y', 0)
        w = rect.get('width', 0)
        h = rect.get('height', 0)
        
        if w <= 0 or h <= 0:
            continue
        
        # Step 1: Fill with background color
        bg_rgb = parse_css_color(spec.bg_color)
        draw.rectangle([x, y, x + w, y + h], fill=bg_rgb)
        
        # Step 2: Render replacement text
        font_size = parse_font_size(spec.font_size)
        font = get_segoe_ui_font(font_size, spec.font_weight)
        text_rgb = parse_css_color(spec.text_color)
        
        # Truncate or pad replacement text to fit the available width
        replacement = spec.replacement_text
        text_bbox = draw.textbbox((0, 0), replacement, font=font)
        text_w = text_bbox[2] - text_bbox[0]
        
        # If replacement is wider than the box, truncate with ellipsis
        if text_w > w:
            while len(replacement) > 1:
                replacement = replacement[:-1]
                text_bbox = draw.textbbox((0, 0), replacement + '...', font=font)
                if text_bbox[2] - text_bbox[0] <= w:
                    replacement += '...'
                    break
        
        # Center vertically in the rect
        text_h = text_bbox[3] - text_bbox[1]
        text_y = y + (h - text_h) // 2
        
        draw.text((x, text_y), replacement, fill=text_rgb, font=font)
    
    return image


def draw_callouts(image: Image.Image, specs: list[CalloutSpec]) -> Image.Image:
    """
    Draw callout rectangles around specified regions, with optional numbered circles.
    
    Per MS contributor guide: 3px red (#E91C1C) border that hugs the element.
    When a spec has number > 0, a filled red circle with a white number is drawn
    centered above the callout rectangle.
    
    Args:
        image: PIL Image to modify
        specs: List of CalloutSpec objects
        
    Returns:
        Modified image
    """
    # Use RGBA overlay for clean alpha compositing (prevents artifacts
    # when callout borders overlap)
    image = image.convert('RGBA')
    overlay = Image.new('RGBA', image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Numbered circle parameters
    circle_diameter = 24
    radius = circle_diameter // 2
    circle_gap = 4

    # Load a font for numbered circles (only if any spec has a number)
    has_numbers = any(spec.number > 0 for spec in specs)
    font = None
    if has_numbers:
        for font_name in ['segoeuib.ttf', 'segoeui.ttf', 'arialbd.ttf', 'arial.ttf']:
            try:
                font = ImageFont.truetype(font_name, 14)
                break
            except (OSError, IOError):
                continue
        if font is None:
            font = ImageFont.load_default()
    
    for spec in specs:
        rect = spec.px_rect
        x = rect.get('x', 0) - spec.padding
        y = rect.get('y', 0) - spec.padding
        w = rect.get('width', 0) + 2 * spec.padding
        h = rect.get('height', 0) + 2 * spec.padding
        
        color = spec.color or CALLOUT_COLOR
        thickness = spec.thickness
        
        # Clamp to image bounds
        x = max(0, x)
        y = max(0, y)
        x2 = min(image.width - 1, x + w)
        y2 = min(image.height - 1, y + h)
        
        # Draw rectangle with specified thickness
        for i in range(thickness):
            draw.rectangle(
                [x + i, y + i, x2 - i, y2 - i],
                outline=color
            )

        # Draw numbered circle above the rectangle if number > 0
        if spec.number > 0 and font is not None:
            cx = x + (x2 - x) // 2
            cy = y - circle_gap - radius

            # Clamp circle position to image bounds
            cx = max(radius + 1, min(image.width - radius - 1, cx))
            cy = max(radius + 1, min(image.height - radius - 1, cy))

            # Filled circle
            draw.ellipse(
                [cx - radius, cy - radius, cx + radius, cy + radius],
                fill=color
            )

            # White number text centered in circle
            text = str(spec.number)
            try:
                draw.text((cx, cy), text, fill=(255, 255, 255), font=font, anchor='mm')
            except TypeError:
                text_bbox = draw.textbbox((0, 0), text, font=font)
                text_w = text_bbox[2] - text_bbox[0]
                text_h = text_bbox[3] - text_bbox[1]
                draw.text(
                    (cx - text_w // 2, cy - text_h // 2),
                    text, fill=(255, 255, 255), font=font
                )

    result = Image.alpha_composite(image, overlay).convert('RGB')
    return result


def smart_crop(
    image: Image.Image,
    focus_rects: list[dict],
    padding: int = 40,
    min_width: int = 400,
    min_height: int = 200,
) -> Image.Image:
    """
    Smart crop to show only the minimum area needed.
    
    Computes a bounding box that contains all focus_rects with padding,
    then crops the image. If no focus_rects, returns the full image.
    
    Args:
        image: Source image
        focus_rects: List of {x, y, width, height} dicts defining areas of interest
        padding: Pixels of padding around the combined bounding box
        min_width: Minimum crop width
        min_height: Minimum crop height
        
    Returns:
        Cropped image
    """
    if not focus_rects:
        return image
    
    # Compute combined bounding box
    min_x = min(r.get('x', 0) for r in focus_rects)
    min_y = min(r.get('y', 0) for r in focus_rects)
    max_x = max(r.get('x', 0) + r.get('width', 0) for r in focus_rects)
    max_y = max(r.get('y', 0) + r.get('height', 0) for r in focus_rects)
    
    # Add padding
    crop_x = max(0, min_x - padding)
    crop_y = max(0, min_y - padding)
    crop_x2 = min(image.width, max_x + padding)
    crop_y2 = min(image.height, max_y + padding)
    
    # Enforce minimums
    crop_w = crop_x2 - crop_x
    crop_h = crop_y2 - crop_y
    if crop_w < min_width:
        expand = (min_width - crop_w) // 2
        crop_x = max(0, crop_x - expand)
        crop_x2 = min(image.width, crop_x2 + expand)
    if crop_h < min_height:
        expand = (min_height - crop_h) // 2
        crop_y = max(0, crop_y - expand)
        crop_y2 = min(image.height, crop_y2 + expand)
    
    return image.crop((int(crop_x), int(crop_y), int(crop_x2), int(crop_y2)))


def add_gray_border(image: Image.Image) -> Image.Image:
    """
    Add a 1px gray border for accessibility on light/dark themes.
    Per contributor guide, this is required for screenshots with light or dark edges.
    """
    bordered = Image.new(
        'RGB',
        (image.width + 2 * GRAY_BORDER_THICKNESS, image.height + 2 * GRAY_BORDER_THICKNESS),
        GRAY_BORDER_COLOR
    )
    bordered.paste(image, (GRAY_BORDER_THICKNESS, GRAY_BORDER_THICKNESS))
    return bordered


def optimize_png(image: Image.Image, output_path: str, target_kb: int = TARGET_SIZE_KB) -> str:
    """
    Save as optimized PNG, attempting to stay under target file size.
    
    If the image is too large, it will be progressively scaled down.
    
    Args:
        image: PIL Image
        output_path: Destination file path
        target_kb: Target maximum file size in KB
        
    Returns:
        Path to saved file
    """
    # Ensure max width
    if image.width > MAX_WIDTH_PX:
        ratio = MAX_WIDTH_PX / image.width
        new_height = int(image.height * ratio)
        image = image.resize((MAX_WIDTH_PX, new_height), Image.LANCZOS)
    
    # Save with optimization
    image.save(output_path, 'PNG', optimize=True)
    
    # Check size and progressively reduce if needed
    file_size_kb = os.path.getsize(output_path) / 1024
    scale = 0.9
    while file_size_kb > target_kb and scale > 0.3:
        new_w = int(image.width * scale)
        new_h = int(image.height * scale)
        scaled = image.resize((new_w, new_h), Image.LANCZOS)
        scaled.save(output_path, 'PNG', optimize=True)
        file_size_kb = os.path.getsize(output_path) / 1024
        scale -= 0.1
    
    return output_path


def enforce_naming_convention(filename: str) -> str:
    """
    Enforce MS Learn image naming: lowercase, only letters/numbers/hyphens, .png.
    """
    # Strip extension
    name = os.path.splitext(filename)[0]
    # Lowercase
    name = name.lower()
    # Replace spaces and underscores with hyphens
    name = name.replace(' ', '-').replace('_', '-')
    # Remove anything that isn't alphanumeric or hyphen
    name = re.sub(r'[^a-z0-9-]', '', name)
    # Collapse multiple hyphens
    name = re.sub(r'-+', '-', name).strip('-')
    return f"{name}.png"


if __name__ == '__main__':
    # Quick self-test
    print("Creating test image...")
    img = Image.new('RGB', (1400, 900), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    
    # Draw some fake Azure UI elements
    draw.rectangle([0, 0, 1400, 50], fill=(0, 52, 120))  # Azure nav bar
    draw.rectangle([0, 50, 250, 900], fill=(36, 36, 36))  # Sidebar
    
    font = get_segoe_ui_font(14)
    draw.text((300, 100), "Subscription ID: 72f988bf-86f1-41af-91ab-2d7cd011db47", fill=(0, 0, 0), font=font)
    draw.text((300, 130), "Resource Group: my-real-rg-prod", fill=(0, 0, 0), font=font)
    
    # Test redaction
    redacted = redact_pii(img, [
        RedactionSpec(
            px_rect={'x': 420, 'y': 95, 'width': 300, 'height': 20},
            replacement_text='aaaa0a0a-bb1b-cc2c-dd3d-eeeeee4e4e4e',
            bg_color='rgb(255, 255, 255)',
            font_family='Segoe UI',
            font_size='14px',
            font_weight='400',
            text_color='rgb(0, 0, 0)',
        ),
    ])
    
    # Test callout
    with_callouts = draw_callouts(redacted, [
        CalloutSpec(px_rect={'x': 290, 'y': 85, 'width': 500, 'height': 30}),
    ])
    
    # Test border
    bordered = add_gray_border(with_callouts)
    
    # Test optimize + naming
    test_name = enforce_naming_convention("My Test Screenshot 01!")
    output = optimize_png(bordered, f"F:\\home\\azure-screenshot\\{test_name}")
    size_kb = os.path.getsize(output) / 1024
    print(f"Saved: {output} ({size_kb:.1f} KB)")
    print(f"Name convention: '{test_name}'")
    print("Self-test passed!")
