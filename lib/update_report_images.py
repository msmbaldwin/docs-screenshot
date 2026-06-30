"""Update base64 images in the comparison report HTML."""
import base64
import os
import re
import sys


def update_report(report_path, image_ids):
    with open(report_path, encoding='utf-8') as f:
        html = f.read()

    report_dir = os.path.dirname(report_path)

    for img_id in image_ids:
        img_path = os.path.join(report_dir, 'captured', f'{img_id}.png')
        if not os.path.exists(img_path):
            print(f'{img_id}: file not found at {img_path}')
            continue

        with open(img_path, 'rb') as f:
            new_b64 = base64.b64encode(f.read()).decode('ascii')

        # Find the detail entry by its id attribute
        id_pattern = f'id="{img_id}"'
        idx = html.find(id_pattern)
        if idx == -1:
            print(f'{img_id}: NOT FOUND in report (looking for {id_pattern})')
            continue

        # From the entry, find "Captured" in the heading, then the img src after it
        entry_html = html[idx:]
        # The captured image is the SECOND img in the entry (first is Original)
        # Find both img tags
        img_positions = list(re.finditer(r'<img\s+src="data:image/png;base64,', entry_html))
        if len(img_positions) < 2:
            print(f'{img_id}: Could not find 2 img tags (found {len(img_positions)})')
            continue

        # The second img is the captured one
        cap_img_match = img_positions[1]
        b64_start_rel = cap_img_match.end()

        # Find the closing quote
        b64_end_rel = entry_html.find('"', b64_start_rel)
        if b64_end_rel == -1:
            print(f'{img_id}: Could not find closing quote for base64 data')
            continue

        abs_start = idx + b64_start_rel
        abs_end = idx + b64_end_rel
        old_b64 = html[abs_start:abs_end]
        html = html[:abs_start] + new_b64 + html[abs_end:]

        old_kb = len(old_b64) * 3 / 4 / 1024
        new_kb = len(new_b64) * 3 / 4 / 1024
        print(f'{img_id}: replaced captured image ({old_kb:.1f}KB -> {new_kb:.1f}KB)')

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print('Report updated successfully.')

if __name__ == '__main__':
    report = sys.argv[1]
    ids = sys.argv[2:]
    update_report(report, ids)
