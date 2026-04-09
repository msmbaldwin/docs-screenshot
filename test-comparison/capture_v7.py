"""
V7 Stress Test Capture Orchestrator

Processes manifest entries one by one:
1. Reads article context
2. Resolves original image path
3. Determines portal URL and navigation
4. Captures via playwright-cli
5. Post-processes (PII scrub, crop, border)
6. Classifies result
7. Updates the report HTML

Usage:
    python capture_v7.py --start 0 --count 10
    python capture_v7.py --id v7-042
"""
import json
import os
import sys
import re
import subprocess
import base64
import time
import argparse
from pathlib import Path

MANIFEST_PATH = r'F:\home\docs-screenshot\test-comparison\v7-manifest.json'
REPORT_PATH = r'F:\home\docs-screenshot\test-comparison\comparison-report-v7.html'
CAPTURED_DIR = r'F:\home\docs-screenshot\test-comparison\captured-v7'
RESULTS_PATH = r'F:\home\docs-screenshot\test-comparison\v7-results.json'

REPO_ROOTS = {
    'azure-ai-docs-pr': r'F:\git\azure-ai-docs-pr',
    'azure-docs-pr': r'F:\git\azure-docs-pr',
    'fabric-docs-pr': r'F:\git\fabric-docs-pr',
}


def load_manifest():
    with open(MANIFEST_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_results():
    if os.path.exists(RESULTS_PATH):
        with open(RESULTS_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_results(results):
    with open(RESULTS_PATH, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)


def resolve_image_path(item):
    """Resolve the full filesystem path to the original image."""
    repo_root = REPO_ROOTS.get(item['repo'], '')
    article_path = item['article'].replace('/', '\\')
    article_dir = os.path.dirname(os.path.join(repo_root, article_path))
    source = item['source']
    
    # Handle ~/reusable-content/ paths
    if source.startswith('~/'):
        source = source[2:]
        full_path = os.path.join(repo_root, source)
        if os.path.exists(full_path):
            return full_path
        # Try without reusable-content prefix
        if 'reusable-content/' in source:
            alt = source.split('reusable-content/')[-1]
            alt_path = os.path.join(repo_root, 'reusable-content', alt)
            if os.path.exists(alt_path):
                return alt_path
    
    # Handle ./ prefix
    if source.startswith('./'):
        source = source[2:]
    
    # Handle ../ paths
    full_path = os.path.normpath(os.path.join(article_dir, source))
    if os.path.exists(full_path):
        return full_path
    
    # Try direct from repo root
    full_path = os.path.join(repo_root, source.replace('/', '\\'))
    if os.path.exists(full_path):
        return full_path
    
    return None


def read_article_context(item):
    """Read the full article for capture context."""
    repo_root = REPO_ROOTS.get(item['repo'], '')
    article_path = os.path.join(repo_root, item['article'].replace('/', '\\'))
    try:
        with open(article_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    except Exception:
        return ''


def determine_portal_url(item, article_content):
    """Determine what portal URL to navigate to based on context."""
    alt = item['alt_text'].lower()
    ctx = item['context'].lower()
    portal = item['portal']
    article = article_content.lower()
    
    # Extract any explicit URLs from context
    url_match = re.search(r'https?://[^\s\)]+', item['context'])
    if url_match:
        return url_match.group(0)
    
    # Portal-specific URL bases
    if portal == 'fabric':
        return 'https://app.fabric.microsoft.com'
    elif portal == 'entra':
        return 'https://entra.microsoft.com'
    elif portal == 'ai-foundry':
        if 'foundry' in alt or 'ai studio' in alt:
            return 'https://ai.azure.com'
        return 'https://portal.azure.com'
    elif portal == 'defender':
        return 'https://security.microsoft.com'
    elif portal == 'devops':
        return 'https://dev.azure.com'
    else:
        return 'https://portal.azure.com'


def get_capture_instructions(item, article_content):
    """Generate capture instructions from article context and alt-text."""
    instructions = {
        'id': item['id'],
        'portal_url': determine_portal_url(item, article_content),
        'alt_text': item['alt_text'],
        'context': item['context'],
        'service_area': item['service_area'],
        'portal': item['portal'],
        'steps': [],
    }
    
    # Parse numbered steps from context
    steps = re.findall(r'\d+\.\s+(.+?)(?=\d+\.|$)', item['context'], re.DOTALL)
    if steps:
        instructions['steps'] = [s.strip()[:200] for s in steps]
    
    return instructions


def image_to_base64(path):
    """Convert an image file to base64 string."""
    with open(path, 'rb') as f:
        data = f.read()
    return base64.b64encode(data).decode('utf-8')


def classify_result(captured_path, item, error=None):
    """Classify the capture result."""
    if error:
        if 'privilege' in str(error).lower() or 'access denied' in str(error).lower():
            return 'PRIVILEGE_FAILURE', str(error)
        if 'navigate' in str(error).lower() or 'timeout' in str(error).lower():
            return 'NAVIGATION_FAILURE', str(error)
        return 'DATA_SETUP_FAILURE', str(error)
    
    if captured_path and os.path.exists(captured_path):
        size = os.path.getsize(captured_path)
        if size < 5000:  # Too small, probably blank
            return 'NAVIGATION_FAILURE', 'Captured image too small (likely blank page)'
        return 'CAPTURE_SUCCESS', 'Screenshot captured successfully'
    
    return 'NAVIGATION_FAILURE', 'No image produced'


def safe_print(text):
    """Print text safely, replacing unencodable chars."""
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode('ascii', errors='replace').decode('ascii'))


def print_entry(item, idx, total):
    """Print a summary line for the current capture."""
    safe_print(f"\n{'='*70}")
    safe_print(f"[{idx+1}/{total}] {item['id']} | {item['repo']} | {item['portal']}")
    safe_print(f"  Alt: {item['alt_text'][:100]}")
    safe_print(f"  Article: {item['article']}")
    safe_print(f"{'='*70}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--start', type=int, default=0)
    parser.add_argument('--count', type=int, default=10)
    parser.add_argument('--id', type=str, default=None)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    
    manifest = load_manifest()
    results = load_results()
    
    os.makedirs(CAPTURED_DIR, exist_ok=True)
    
    if args.id:
        entries = [m for m in manifest if m['id'] == args.id]
        if not entries:
            print(f"ERROR: {args.id} not found in manifest")
            sys.exit(1)
    else:
        entries = manifest[args.start:args.start + args.count]
    
    print(f"Processing {len(entries)} entries (start={args.start})")
    
    for idx, item in enumerate(entries):
        print_entry(item, args.start + idx, len(manifest))
        
        # Check if already captured
        if item['id'] in results and results[item['id']].get('status') == 'CAPTURE_SUCCESS':
            print(f"  SKIP: Already captured successfully")
            continue
        
        # Resolve original image
        orig_path = resolve_image_path(item)
        if orig_path:
            safe_print(f"  Original: {orig_path} ({os.path.getsize(orig_path)//1024}KB)")
        else:
            safe_print(f"  Original: NOT FOUND")
        
        # Read article
        article = read_article_context(item)
        if article:
            safe_print(f"  Article: {len(article)} chars loaded")
        
        # Get capture instructions
        instructions = get_capture_instructions(item, article)
        safe_print(f"  Portal URL: {instructions['portal_url']}")
        if instructions['steps']:
            for i, step in enumerate(instructions['steps'][:3]):
                safe_print(f"  Step {i+1}: {step[:100]}")
        
        if args.dry_run:
            safe_print(f"  DRY RUN: Would capture here")
            results[item['id']] = {
                'status': 'PENDING',
                'portal_url': instructions['portal_url'],
                'original_path': orig_path,
            }
            continue
        
        # Save instructions for this capture (used by the actual capture process)
        instr_path = os.path.join(CAPTURED_DIR, f"{item['id']}-instructions.json")
        with open(instr_path, 'w', encoding='utf-8') as f:
            json.dump({
                **instructions,
                'original_path': orig_path,
                'repo': item['repo'],
                'article_path': item['article'],
                'image_source': item['source'],
            }, f, indent=2)
        
        safe_print(f"  Instructions saved: {instr_path}")
        
        results[item['id']] = {
            'status': 'READY',
            'instructions_path': instr_path,
            'portal_url': instructions['portal_url'],
            'original_path': orig_path,
            'repo': item['repo'],
            'article_path': item['article'],
        }
    
    save_results(results)
    print(f"\nResults saved: {RESULTS_PATH}")
    print(f"Entries processed: {len(entries)}")
    
    # Summary
    statuses = {}
    for r in results.values():
        s = r.get('status', 'UNKNOWN')
        statuses[s] = statuses.get(s, 0) + 1
    print(f"\nStatus summary: {statuses}")


if __name__ == '__main__':
    main()
