"""
post_process.py - Standalone post-capture image processing for screenshots.

Runs after a raw screenshot is captured. Applies:
1. Callout boxes (numbered circles + border rectangles)
2. Gray border (1px, per MS contributor guide)
3. PNG optimization (target <200KB, max 1200px width)

This wraps functions from image_editor.py to provide a lightweight CLI
for post-processing without the full screenshot_processor pipeline.

Usage:
    python post_process.py <screenshot_path> <output_path> [--callouts <json>] [--callouts-file <path>] [--skip-border] [--skip-optimize]
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from image_editor import (
        CalloutSpec,
        add_gray_border,
        draw_callouts,
        optimize_png,
    )
    HAS_IMAGE_EDITOR = True
except ImportError:
    HAS_IMAGE_EDITOR = False

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    sys.stderr.write(
        "Warning: Pillow is not installed. Run: pip install Pillow\n"
    )


def process_screenshot(
    screenshot_path,
    output_path,
    callouts=None,
    skip_border=False,
    skip_optimize=False,
):
    """
    Post-process a captured screenshot.

    Args:
        screenshot_path: Path to the raw screenshot PNG
        output_path: Where to save the processed image
        callouts: List of callout dicts with {number, box: {x, y, width, height}}
        skip_border: Skip adding gray border
        skip_optimize: Skip PNG optimization
    """
    if not HAS_PIL:
        print("ERROR: Pillow is not installed. Run: pip install Pillow", file=sys.stderr)
        sys.exit(1)

    image = Image.open(screenshot_path).convert('RGB')
    original_size = f"{image.width}x{image.height}"

    # Step 1: Draw callouts
    if callouts and HAS_IMAGE_EDITOR:
        specs = []
        for c in callouts:
            box = c.get('box', {})
            specs.append(CalloutSpec(
                px_rect={
                    'x': box.get('x', 0),
                    'y': box.get('y', 0),
                    'width': box.get('width', 0),
                    'height': box.get('height', 0),
                },
                number=c.get('number', 0),
            ))
        image = draw_callouts(image, specs)
        print(f"Callouts: drew {len(specs)} annotation(s)")

    # Step 2: Add gray border
    if not skip_border:
        if HAS_IMAGE_EDITOR:
            image = add_gray_border(image)
        else:
            border_color = (200, 200, 200)
            bordered = Image.new(
                'RGB',
                (image.width + 2, image.height + 2),
                border_color
            )
            bordered.paste(image, (1, 1))
            image = bordered
        print("Border: added 1px gray border")

    # Step 3: PNG optimization
    if not skip_optimize:
        if HAS_IMAGE_EDITOR:
            optimize_png(image, output_path)
        else:
            max_width = 1200
            if image.width > max_width:
                ratio = max_width / image.width
                new_height = int(image.height * ratio)
                image = image.resize((max_width, new_height), Image.LANCZOS)
                print(f"Resize: {original_size} -> {image.width}x{image.height}")
            image.save(output_path, 'PNG', optimize=True)

        file_size_kb = os.path.getsize(output_path) / 1024
        print(f"Optimize: {file_size_kb:.1f} KB")
    else:
        image.save(output_path, 'PNG')

    print(f"Output: {output_path}")
    return output_path


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Post-process a screenshot for MS Learn documentation'
    )
    parser.add_argument('screenshot', help='Path to the raw screenshot PNG')
    parser.add_argument('output', help='Output path for processed image')
    parser.add_argument('--callouts', help='JSON array of {number, box: {x,y,width,height}}')
    parser.add_argument('--callouts-file', help='Path to a JSON file with the callouts array')
    parser.add_argument('--skip-border', action='store_true', help='Skip gray border')
    parser.add_argument('--skip-optimize', action='store_true', help='Skip PNG optimization')

    args = parser.parse_args()

    callouts = None
    if args.callouts:
        callouts = json.loads(args.callouts)
    elif args.callouts_file:
        with open(args.callouts_file) as f:
            callouts = json.loads(f.read())

    process_screenshot(
        screenshot_path=args.screenshot,
        output_path=args.output,
        callouts=callouts,
        skip_border=args.skip_border,
        skip_optimize=args.skip_optimize,
    )
