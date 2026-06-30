"""
screenshot_processor.py - Main Orchestration Script

Ties together DOM extraction, PII detection, image editing, and GIMP handoff
into a single pipeline for processing Azure portal screenshots.

Usage (typically called by the skill, not directly):
    python screenshot_processor.py --dom-json dom_data.json --image screenshot.png --output output.png [options]
"""

import argparse
import json
import os
import sys
from datetime import datetime

# Add lib directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gimp_bridge import open_in_gimp
from image_editor import (
    CalloutSpec,
    RedactionSpec,
    add_gray_border,
    draw_callouts,
    enforce_naming_convention,
    optimize_png,
    redact_pii,
    smart_crop,
)
from pii_detector import PIIDetector
from PIL import Image


def process_screenshot(
    dom_json_path: str,
    image_path: str,
    output_path: str,
    callout_selectors: list[dict] = None,
    crop_focus: list[dict] = None,
    skip_pii_redaction: bool = False,
    skip_crop: bool = False,
    skip_gray_border: bool = False,
    skip_callouts: bool = False,
    open_gimp: bool = True,
    description: str = "",
) -> dict:
    """
    Full screenshot processing pipeline.
    
    Args:
        dom_json_path: Path to DOM extraction JSON (from extract_dom_info.js)
        image_path: Path to raw screenshot PNG
        output_path: Desired output path (name will be normalized)
        callout_selectors: List of {x, y, width, height} rects to draw callout boxes around
        crop_focus: List of {x, y, width, height} rects defining the area of interest for cropping
        skip_pii_redaction: Skip PII detection and redaction
        skip_crop: Skip smart cropping
        skip_gray_border: Skip gray border addition
        skip_callouts: Skip callout box drawing entirely (nocallouts mode)
        open_gimp: Open result in GIMP for final edits
        description: Human-readable description of what this screenshot shows
        
    Returns:
        Summary dict with processing results
    """
    summary = {
        'timestamp': datetime.now().isoformat(),
        'source_image': image_path,
        'description': description,
        'pii_detected': [],
        'callouts_drawn': 0,
        'cropped': False,
        'output_path': '',
        'output_size_kb': 0,
    }
    
    # Load DOM data
    with open(dom_json_path, encoding='utf-8') as f:
        dom_data = json.load(f)
    
    # Load image
    image = Image.open(image_path).convert('RGB')
    original_size = image.size
    
    print(f"Processing: {image_path} ({image.width}x{image.height})")
    print(f"DOM data: {len(dom_data.get('textNodes', []))} text nodes, DPR={dom_data.get('dpr', 1)}")
    
    # Step 1: PII Detection & Redaction
    if not skip_pii_redaction:
        detector = PIIDetector()
        pii_matches = detector.scan_dom_extraction(dom_data)
        
        if pii_matches:
            print(f"\nPII Detection: {len(pii_matches)} items found")
            print(detector.generate_summary(pii_matches))
            
            # Build redaction specs from PII matches
            redaction_specs = []
            for match in pii_matches:
                redaction_specs.append(RedactionSpec(
                    px_rect=match.px_rect,
                    replacement_text=match.replacement,
                    bg_color=match.style.get('backgroundColor', 'rgb(255, 255, 255)'),
                    font_family=match.style.get('fontFamily', 'Segoe UI'),
                    font_size=match.style.get('fontSize', '14px'),
                    font_weight=match.style.get('fontWeight', '400'),
                    text_color=match.style.get('color', 'rgb(0, 0, 0)'),
                ))
            
            image = redact_pii(image, redaction_specs)
            
            # Record for summary
            summary['pii_detected'] = [
                {
                    'original': m.text,
                    'type': m.pii_type,
                    'severity': m.severity,
                    'replacement': m.replacement,
                    'location': m.px_rect,
                }
                for m in pii_matches
            ]
        else:
            print("PII Detection: No PII found")
    
    # Step 2: Callout Boxes
    if not skip_callouts and callout_selectors:
        callout_specs = [
            CalloutSpec(px_rect=rect)
            for rect in callout_selectors
        ]
        image = draw_callouts(image, callout_specs)
        summary['callouts_drawn'] = len(callout_specs)
        print(f"Callouts: Drew {len(callout_specs)} red rectangle(s)")
    
    # Step 3: Smart Crop
    if not skip_crop and crop_focus:
        image = smart_crop(image, crop_focus)
        summary['cropped'] = True
        print(f"Crop: {original_size[0]}x{original_size[1]} -> {image.width}x{image.height}")
    
    # Step 4: Gray Border
    if not skip_gray_border:
        image = add_gray_border(image)
    
    # Step 5: Normalize filename and optimize
    output_dir = os.path.dirname(output_path)
    output_name = enforce_naming_convention(os.path.basename(output_path))
    final_output = os.path.join(output_dir, output_name) if output_dir else output_name
    
    # Ensure output directory exists
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    
    optimize_png(image, final_output)
    file_size_kb = os.path.getsize(final_output) / 1024
    
    summary['output_path'] = final_output
    summary['output_size_kb'] = round(file_size_kb, 1)
    summary['output_dimensions'] = f"{image.width}x{image.height}"
    
    print(f"\nOutput: {final_output} ({file_size_kb:.1f} KB, {image.width}x{image.height})")
    
    # Step 6: Open in GIMP
    if open_gimp:
        print("Opening in GIMP for final review...")
        try:
            open_in_gimp([final_output])
        except Exception as e:
            print(f"Warning: Could not open GIMP: {e}")
    
    return summary


def generate_report(summaries: list[dict], output_path: str = None) -> str:
    """
    Generate a summary report of all processed screenshots.
    
    Args:
        summaries: List of summary dicts from process_screenshot
        output_path: Optional path to save the report
        
    Returns:
        Report text
    """
    lines = [
        "# Azure Screenshot Processing Report",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Images processed: {len(summaries)}",
        "",
    ]
    
    total_pii = 0
    for i, s in enumerate(summaries, 1):
        lines.append(f"## Image {i}: {os.path.basename(s.get('output_path', 'unknown'))}")
        lines.append(f"- **Description**: {s.get('description', 'N/A')}")
        lines.append(f"- **Output**: `{s.get('output_path', 'N/A')}`")
        lines.append(f"- **Size**: {s.get('output_size_kb', 0)} KB ({s.get('output_dimensions', 'N/A')})")
        lines.append(f"- **Callouts**: {s.get('callouts_drawn', 0)}")
        lines.append(f"- **Cropped**: {'Yes' if s.get('cropped') else 'No'}")
        
        pii = s.get('pii_detected', [])
        if pii:
            total_pii += len(pii)
            lines.append(f"- **PII Redacted**: {len(pii)} items")
            for p in pii:
                loc = p.get('location', {})
                lines.append(
                    f"  - [{p['type']}] SEV {p['severity']}: "
                    f"`{p['original'][:30]}...` -> `{p['replacement'][:30]}...` "
                    f"at ({loc.get('x', '?')}, {loc.get('y', '?')})"
                )
        else:
            lines.append("- **PII Redacted**: None detected")
        
        lines.append("")
    
    lines.append("---")
    lines.append(f"**Total PII instances redacted: {total_pii}**")
    
    report = "\n".join(lines)
    
    if output_path:
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"Report saved to: {output_path}")
    
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Process Azure screenshot for documentation')
    parser.add_argument('--dom-json', required=True, help='Path to DOM extraction JSON')
    parser.add_argument('--image', required=True, help='Path to screenshot PNG')
    parser.add_argument('--output', required=True, help='Output path for processed image')
    parser.add_argument('--description', default='', help='Description of the screenshot')
    parser.add_argument('--skip-pii', action='store_true', help='Skip PII redaction')
    parser.add_argument('--skip-crop', action='store_true', help='Skip smart cropping')
    parser.add_argument('--skip-border', action='store_true', help='Skip gray border')
    parser.add_argument('--no-callouts', action='store_true', help='Skip callout box drawing entirely')
    parser.add_argument('--no-gimp', action='store_true', help='Do not open in GIMP')
    parser.add_argument('--callouts', help='JSON array of {x,y,width,height} rects for callout boxes')
    parser.add_argument('--crop-focus', help='JSON array of {x,y,width,height} rects for crop focus')
    
    args = parser.parse_args()
    
    callouts = json.loads(args.callouts) if args.callouts else None
    crop_focus = json.loads(args.crop_focus) if args.crop_focus else None
    
    summary = process_screenshot(
        dom_json_path=args.dom_json,
        image_path=args.image,
        output_path=args.output,
        callout_selectors=callouts,
        crop_focus=crop_focus,
        skip_pii_redaction=args.skip_pii,
        skip_crop=args.skip_crop,
        skip_gray_border=args.skip_border,
        skip_callouts=args.no_callouts,
        open_gimp=not args.no_gimp,
        description=args.description,
    )
    
    print("\n" + generate_report([summary]))
