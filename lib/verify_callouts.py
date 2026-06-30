"""
verify_callouts.py - Deterministic callout verification.

Compares the number and approximate positions of red callout boxes in an
original screenshot vs a captured screenshot. Fails loudly if the captured
image has fewer callout boxes than the original.

Usage:
    python lib/verify_callouts.py original.png captured.png

Exit codes:
    0 = callout counts match (or captured has more)
    1 = captured image has fewer callouts than original
    2 = error reading files
"""

import os
import sys

import numpy as np
from PIL import Image

# Red callout color: RGB(233, 28, 28) with tolerance
CALLOUT_R, CALLOUT_G, CALLOUT_B = 233, 28, 28
COLOR_TOLERANCE = 30
MIN_CALLOUT_PIXELS = 200  # minimum red pixels to count as a callout box
MIN_BOX_DIMENSION = 20    # minimum width/height of a callout region


def find_callout_boxes(image_path: str) -> list[dict]:
    """Detect red callout boxes in an image.

    Returns a list of dicts with keys: x, y, width, height, pixel_count.
    Each dict represents one detected callout box region.
    """
    img = Image.open(image_path).convert("RGB")
    arr = np.array(img)

    # Create a mask of red callout pixels
    r_match = np.abs(arr[:, :, 0].astype(int) - CALLOUT_R) < COLOR_TOLERANCE
    g_match = np.abs(arr[:, :, 1].astype(int) - CALLOUT_G) < COLOR_TOLERANCE
    b_match = np.abs(arr[:, :, 2].astype(int) - CALLOUT_B) < COLOR_TOLERANCE
    red_mask = r_match & g_match & b_match

    if not red_mask.any():
        return []

    # Find connected regions of red pixels using simple flood-fill grouping.
    # For callout boxes (which are thin rectangles), we can group by proximity.
    coords = np.argwhere(red_mask)  # (y, x) pairs
    if len(coords) == 0:
        return []

    # Sort by y then x
    coords = coords[np.lexsort((coords[:, 1], coords[:, 0]))]

    # Group into boxes using a simple clustering approach:
    # Two red pixels belong to the same box if they are within 50px of each other.
    boxes = []
    visited = np.zeros(len(coords), dtype=bool)

    for i in range(len(coords)):
        if visited[i]:
            continue
        # Start a new box
        cluster_y = [coords[i][0]]
        cluster_x = [coords[i][1]]
        visited[i] = True

        # Expand cluster
        for j in range(i + 1, len(coords)):
            if visited[j]:
                continue
            cy, cx = coords[j]
            # Check if this pixel is near any pixel in the cluster
            min_y, max_y = min(cluster_y), max(cluster_y)
            min_x, max_x = min(cluster_x), max(cluster_x)
            if (min_y - 5 <= cy <= max_y + 5) and (min_x - 5 <= cx <= max_x + 5):
                cluster_y.append(cy)
                cluster_x.append(cx)
                visited[j] = True

        pixel_count = len(cluster_y)
        if pixel_count < MIN_CALLOUT_PIXELS:
            continue

        min_y, max_y = min(cluster_y), max(cluster_y)
        min_x, max_x = min(cluster_x), max(cluster_x)
        w = max_x - min_x
        h = max_y - min_y

        if w < MIN_BOX_DIMENSION and h < MIN_BOX_DIMENSION:
            continue

        boxes.append({
            "x": int(min_x),
            "y": int(min_y),
            "width": int(w),
            "height": int(h),
            "pixel_count": pixel_count,
        })

    return boxes


def verify(original_path: str, captured_path: str) -> bool:
    """Verify captured image has at least as many callout boxes as original.

    Returns True if verification passes, False if captured is missing callouts.
    Prints detailed comparison to stdout.
    """
    orig_boxes = find_callout_boxes(original_path)
    cap_boxes = find_callout_boxes(captured_path)

    print(f"Original:  {len(orig_boxes)} callout boxes in {os.path.basename(original_path)}")
    for i, b in enumerate(orig_boxes):
        print(f"  [{i+1}] x={b['x']}, y={b['y']}, {b['width']}x{b['height']} ({b['pixel_count']} red px)")

    print(f"Captured:  {len(cap_boxes)} callout boxes in {os.path.basename(captured_path)}")
    for i, b in enumerate(cap_boxes):
        print(f"  [{i+1}] x={b['x']}, y={b['y']}, {b['width']}x{b['height']} ({b['pixel_count']} red px)")

    if len(cap_boxes) < len(orig_boxes):
        diff = len(orig_boxes) - len(cap_boxes)
        print(f"\nFAIL: Captured image is missing {diff} callout box(es)!")
        print("The original has callouts that are not reproduced in the capture.")
        return False
    elif len(cap_boxes) == len(orig_boxes):
        print("\nPASS: Callout box counts match.")
        return True
    else:
        print(f"\nPASS: Captured has {len(cap_boxes) - len(orig_boxes)} extra callout box(es).")
        return True


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(f"Usage: python {sys.argv[0]} original.png captured.png")
        sys.exit(2)

    original = sys.argv[1]
    captured = sys.argv[2]

    if not os.path.exists(original):
        print(f"Error: original file not found: {original}")
        sys.exit(2)
    if not os.path.exists(captured):
        print(f"Error: captured file not found: {captured}")
        sys.exit(2)

    passed = verify(original, captured)
    sys.exit(0 if passed else 1)
