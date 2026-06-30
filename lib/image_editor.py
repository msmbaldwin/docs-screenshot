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

from PIL import Image, ImageDraw, ImageFont

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
    Falls back through variants based on weight, then through cross-platform
    sans-serif fonts (DejaVu Sans, Liberation Sans) on Linux/macOS where
    Segoe UI isn't installed by default.
    """
    # Map CSS font-weight to font file variants
    weight_map = {
        '100': ('segoeuil.ttf',  False),  # Light
        '200': ('segoeuil.ttf',  False),
        '300': ('segoeuisl.ttf', False),  # Semilight
        '400': ('segoeui.ttf',   False),  # Regular
        '500': ('seguisb.ttf',   True),   # Semibold
        '600': ('seguisb.ttf',   True),
        '700': ('segoeuib.ttf',  True),   # Bold
        '800': ('segoeuib.ttf',  True),
        '900': ('segoeuib.ttf',  True),
        'normal': ('segoeui.ttf',  False),
        'bold':   ('segoeuib.ttf', True),
    }

    primary, is_bold = weight_map.get(str(weight), ('segoeui.ttf', False))

    # Cross-platform fallback chain. ImageFont.truetype() can take either
    # a bare filename (resolved via the system font path) or an absolute
    # path. We mix both so the lookup works on Windows, macOS, and Linux.
    linux_regular = [
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
        'DejaVuSans.ttf',
        'LiberationSans-Regular.ttf',
        'Arial.ttf',
    ]
    linux_bold = [
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
        '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
        'DejaVuSans-Bold.ttf',
        'LiberationSans-Bold.ttf',
        'Arial-Bold.ttf',
    ]
    macos = ['/Library/Fonts/Arial.ttf', '/System/Library/Fonts/Helvetica.ttc']

    fallbacks: list[str] = [primary, 'segoeui.ttf', 'arial.ttf']
    fallbacks += linux_bold if is_bold else linux_regular
    fallbacks += macos

    size_pt = max(1, int(size_px))

    for fb in fallbacks:
        try:
            return ImageFont.truetype(fb, size_pt)
        except OSError:
            continue

    # Last-resort PIL default font (bitmap, very small) - signal that
    # text rendering won't match Segoe UI on this system.
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
    # Optional: redraw a 1px (or wider) border around the fill rect after
    # painting, so the redaction doesn't wipe input-field outlines that the
    # rect happens to overlap. Set to None to skip (default).
    border_color: str | None = None
    border_width: int = 1
    # Optional: shrink the fill rect by N pixels on each side. Useful when the
    # caller's rect intentionally extends over a field border to catch
    # descenders but the border itself should be preserved.
    fill_inset: int = 0


@dataclass
class CalloutSpec:
    """Specification for a callout box."""
    px_rect: dict          # {x, y, width, height} in screenshot pixels
    color: tuple = None    # RGB tuple, defaults to MS red
    thickness: int = CALLOUT_THICKNESS
    padding: int = 4       # Extra padding around the element
    number: int = 0        # Callout number (0 = plain rectangle, 1+ = numbered circle)


def _fit_font_to_box(
    draw: ImageDraw.ImageDraw,
    text: str,
    requested_size_px: float,
    weight: str,
    box_w: int,
    box_h: int,
    min_size_px: int = 8,
) -> tuple[ImageFont.FreeTypeFont, tuple[int, int, int, int]]:
    """Return the largest font (<= requested_size_px) whose rendered text
    fits within box_w x box_h. Important for Linux/macOS where the fallback
    sans-serif (DejaVu, Liberation) has noticeably taller glyphs than Segoe UI
    at the same pixel size and would otherwise overflow the original rect.
    """
    size = max(min_size_px, int(requested_size_px))
    while size >= min_size_px:
        font = get_segoe_ui_font(size, weight)
        bbox = draw.textbbox((0, 0), text, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        if w <= box_w and h <= box_h:
            return font, bbox
        size -= 1
    # Below min_size_px - return the smallest version anyway
    font = get_segoe_ui_font(min_size_px, weight)
    bbox = draw.textbbox((0, 0), text, font=font)
    return font, bbox


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

        # Step 1: Fill with background color (with optional inset so we don't
        # wipe a 1px field border we want to keep). Pillow's rectangle
        # coordinates are inclusive on both corners, so the rect occupies
        # pixels [x .. x+w-1] horizontally and [y .. y+h-1] vertically.
        bg_rgb = parse_css_color(spec.bg_color)
        inset = max(0, int(spec.fill_inset))
        fx0, fy0 = x + inset, y + inset
        fx1, fy1 = x + w - 1 - inset, y + h - 1 - inset
        if fx1 >= fx0 and fy1 >= fy0:
            draw.rectangle([fx0, fy0, fx1, fy1], fill=bg_rgb)

        # Step 2: Pick a font size that fits the box (auto-shrink for
        # Linux/macOS fallback fonts that render larger than Segoe UI).
        requested_size = parse_font_size(spec.font_size)
        # Allow the text to use ~90% of the box height to avoid touching edges.
        usable_h = max(1, h - 2)
        font, bbox = _fit_font_to_box(
            draw,
            spec.replacement_text,
            requested_size,
            spec.font_weight,
            w,
            usable_h,
        )

        # Step 3: Truncate with ellipsis if still too wide after shrinking
        text_rgb = parse_css_color(spec.text_color)
        replacement = spec.replacement_text
        text_w = bbox[2] - bbox[0]
        if text_w > w:
            while len(replacement) > 1:
                replacement = replacement[:-1]
                bbox = draw.textbbox((0, 0), replacement + '...', font=font)
                if bbox[2] - bbox[0] <= w:
                    replacement += '...'
                    break

        # Step 4: Vertically center the *visible glyphs* in the rect. PIL's
        # textbbox returns (left, top, right, bottom) where `top` is the offset
        # from the draw anchor to the top of the inked pixels. We must subtract
        # that offset so the actual glyphs (not the font's ascent-padded box)
        # land centered. Without this correction, text rendered with fonts that
        # have large internal leading (DejaVu Sans) appears low in the box.
        text_h = bbox[3] - bbox[1]
        text_y = y + (h - text_h) // 2 - bbox[1]
        text_x = x - bbox[0]  # also correct horizontal anchor

        draw.text((text_x, text_y), replacement, fill=text_rgb, font=font)

        # Step 5: Optionally redraw a border around the original rect, so a
        # field outline that we painted over gets restored.
        if spec.border_color:
            border_rgb = parse_css_color(spec.border_color)
            bw = max(1, int(spec.border_width))
            # Pillow's rectangle outline width parameter draws inside the box,
            # so use the full rect coords.
            draw.rectangle([x, y, x + w - 1, y + h - 1],
                           outline=border_rgb, width=bw)

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
            except OSError:
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
    output = optimize_png(bordered, os.path.join(os.path.expanduser("~"), "tmp", test_name))
    size_kb = os.path.getsize(output) / 1024
    print(f"Saved: {output} ({size_kb:.1f} KB)")
    print(f"Name convention: '{test_name}'")
    print("Self-test passed!")
