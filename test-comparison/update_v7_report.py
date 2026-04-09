"""
Update the v7 HTML report with captured screenshots and classification results.

Reads:
- v7-results.json (capture results)
- captured-v7/*.png (captured images)
- v7-manifest.json (original metadata)

Updates:
- comparison-report-v7.html (embeds captured images, updates status badges)
"""
import json
import os
import re
import base64
from pathlib import Path

REPORT_PATH = r'F:\home\docs-screenshot\test-comparison\comparison-report-v7.html'
RESULTS_PATH = r'F:\home\docs-screenshot\test-comparison\v7-results.json'
MANIFEST_PATH = r'F:\home\docs-screenshot\test-comparison\v7-manifest.json'
CAPTURED_DIR = r'F:\home\docs-screenshot\test-comparison\captured-v7'

# Badge mapping
STATUS_TO_BADGE = {
    'CAPTURE_SUCCESS': ('&#x2705;', 'Captured'),
    'NAVIGATION_FAILURE': ('&#x274C;', 'Nav Failed'),
    'PRIVILEGE_FAILURE': ('&#x1F512;', 'Privilege Issue'),
    'DATA_SETUP_FAILURE': ('&#x274C;', 'Setup Failed'),
    'UI_MISMATCH': ('&#x26A0;&#xFE0F;', 'UI Mismatch'),
    'PII_LEAK': ('&#x1F6A8;', 'PII Leak'),
    'SERVICE_RESTRUCTURED': ('&#x26A0;&#xFE0F;', 'Restructured'),
    'ELEMENT_NOT_FOUND': ('&#x1F50D;', 'Missing Element'),
    'DOC_INSUFFICIENT': ('&#x1F4C4;', 'Doc Insufficient'),
    'PENDING': ('&#x23F3;', 'Pending'),
}


def image_to_base64(path):
    """Convert image file to base64 data URI."""
    try:
        with open(path, 'rb') as f:
            data = f.read()
        b64 = base64.b64encode(data).decode('utf-8')
        return f'data:image/png;base64,{b64}'
    except Exception as e:
        print(f'  Error encoding {path}: {e}')
        return None


def update_report():
    """Update the HTML report with captured images."""
    # Load data
    results = json.load(open(RESULTS_PATH, 'r', encoding='utf-8'))
    manifest = json.load(open(MANIFEST_PATH, 'r', encoding='utf-8'))
    
    print(f'Loaded {len(results)} results, {len(manifest)} manifest entries')
    
    # Read current report
    with open(REPORT_PATH, 'r', encoding='utf-8') as f:
        html = f.read()
    
    updates = 0
    errors = 0
    
    for item in manifest:
        image_id = item['id']
        result = results.get(image_id, {})
        status = result.get('status', 'PENDING')
        
        # Find the captured image
        captured_path = os.path.join(CAPTURED_DIR, f'{image_id}.png')
        if not os.path.exists(captured_path):
            continue
        
        # Convert to base64
        b64_uri = image_to_base64(captured_path)
        if not b64_uri:
            errors += 1
            continue
        
        # The report uses div placeholders: <div class="img-placeholder captured-slot" id="captured-v7-XXX">
        # Replace the entire div content with an img tag
        placeholder_id = f'id="captured-{image_id}"'
        if placeholder_id in html:
            # Replace the placeholder div with an img tag
            div_pattern = re.compile(
                rf'<div\s+class="img-placeholder\s+captured-slot"\s+id="captured-{re.escape(image_id)}">\s*<span>Capture pending[^<]*</span>\s*</div>',
                re.IGNORECASE | re.DOTALL
            )
            replacement = f'<img src="{b64_uri}" alt="Captured {image_id}" class="captured-img zoomable" data-id="{image_id}" style="max-width:100%;cursor:pointer">'
            if div_pattern.search(html):
                html = div_pattern.sub(replacement, html)
                updates += 1
            else:
                # Try a more relaxed pattern
                div_pattern2 = re.compile(
                    rf'<div[^>]*id="captured-{re.escape(image_id)}"[^>]*>.*?</div>',
                    re.IGNORECASE | re.DOTALL
                )
                if div_pattern2.search(html):
                    html = div_pattern2.sub(replacement, html)
                    updates += 1
                else:
                    print(f'  Could not replace div for {image_id}')
                    errors += 1
        else:
            print(f'  No placeholder found for {image_id}')
            errors += 1
    
    # Save updated report
    with open(REPORT_PATH, 'w', encoding='utf-8') as f:
        f.write(html)
    
    report_size_mb = os.path.getsize(REPORT_PATH) / (1024 * 1024)
    print(f'\nReport updated: {updates} images embedded, {errors} errors')
    print(f'Report size: {report_size_mb:.1f} MB')
    print(f'Saved to: {REPORT_PATH}')


if __name__ == '__main__':
    update_report()
