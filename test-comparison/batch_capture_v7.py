"""
V7 Batch Capture - processes all 100 manifest entries systematically.

Reads each entry's article context, determines the portal URL to navigate to,
captures the screenshot, and tracks results.

Usage:
    python batch_capture_v7.py [--start N] [--count N] [--skip-existing]
"""
import json
import os
import sys
import subprocess
import time
import re
import base64
from pathlib import Path

MANIFEST_PATH = r'F:\home\docs-screenshot\test-comparison\v7-manifest.json'
RESULTS_PATH = r'F:\home\docs-screenshot\test-comparison\v7-results.json'
CAPTURED_DIR = r'F:\home\docs-screenshot\test-comparison\captured-v7'
SUB_ID = '7c80f223-75b8-44d1-a155-09bd30bd62bd'

REPO_ROOTS = {
    'azure-ai-docs-pr': r'F:\git\azure-ai-docs-pr',
    'azure-docs-pr': r'F:\git\azure-docs-pr',
    'fabric-docs-pr': r'F:\git\fabric-docs-pr',
}

# Known resource mappings for efficient navigation
KNOWN_RESOURCES = {
    'contoso-ai-services': f'/subscriptions/{SUB_ID}/resourceGroups/contoso-screenshot-rg/providers/Microsoft.CognitiveServices/accounts/contoso-ai-services',
    'contoso-doc-intelligence': f'/subscriptions/{SUB_ID}/resourceGroups/contoso-screenshot-rg/providers/Microsoft.CognitiveServices/accounts/contoso-doc-intelligence',
    'contoso-kv-demo': f'/subscriptions/{SUB_ID}/resourceGroups/contoso-screenshot-rg/providers/Microsoft.KeyVault/vaults/contoso-kv-demo',
    'contoso-openai': f'/subscriptions/{SUB_ID}/resourceGroups/contoso-screenshot-rg/providers/Microsoft.CognitiveServices/accounts/contoso-openai',
}

PORTAL_BASE = 'https://portal.azure.com?feature.customportal=false'


def run_pw(cmd, timeout=30):
    """Run playwright-cli command."""
    try:
        result = subprocess.run(
            f'playwright-cli {cmd}', shell=True, capture_output=True,
            text=True, timeout=timeout, encoding='utf-8', errors='replace'
        )
        return result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return 'TIMEOUT'
    except Exception as e:
        return f'ERROR: {e}'


def navigate(url, wait=8):
    """Navigate and wait."""
    output = run_pw(f'goto "{url}"', timeout=60)
    time.sleep(wait)
    # Dismiss popups
    run_pw('eval "document.querySelectorAll(\'button[aria-label=\\\"Dismiss\\\"],button[aria-label=\\\"Close\\\"],[data-testid=\\\"portal-dismiss-btn\\\"],.fxs-portal-dismiss\').forEach(e=>e.offsetParent&&e.click())"', timeout=10)
    time.sleep(1)
    return output


def capture(image_id):
    """Take screenshot and return path."""
    path = os.path.join(CAPTURED_DIR, f'{image_id}.png')
    run_pw(f'screenshot --filename="{path}"', timeout=30)
    return path


def get_page_info():
    """Get page URL and title from snapshot."""
    output = run_pw('snapshot', timeout=15)
    url_match = re.search(r'Page URL: (.+)', output)
    title_match = re.search(r'Page Title: (.+)', output)
    return {
        'url': (url_match.group(1).strip() if url_match else 'unknown')[:200],
        'title': (title_match.group(1).strip() if title_match else 'unknown')[:200],
    }


def read_article(item):
    """Read the full article content."""
    repo_root = REPO_ROOTS.get(item['repo'], '')
    path = os.path.join(repo_root, item['article'].replace('/', '\\'))
    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    except Exception:
        return ''


def determine_url(item, article_text):
    """Determine the best portal URL to navigate to for this screenshot."""
    alt = item['alt_text'].lower()
    ctx = (item.get('context', '') or '').lower()
    portal = item['portal']
    area = item['service_area']
    article = article_text.lower()

    # Extract explicit URLs from the article near the image context
    urls_in_ctx = re.findall(r'https?://[^\s\)\]\"\']+', item.get('context', ''))
    if urls_in_ctx:
        # Prefer portal URLs
        for u in urls_in_ctx:
            if any(p in u for p in ['portal.azure.com', 'entra.microsoft.com', 'ai.azure.com',
                                     'app.fabric.microsoft.com', 'security.microsoft.com']):
                return u

    # Non-Azure portals
    if portal == 'fabric':
        return 'https://app.fabric.microsoft.com'
    elif portal == 'entra':
        url_match = re.search(r'https://entra\.microsoft\.com[^\s\)\]\"\']*', article)
        if url_match:
            return url_match.group(0)
        return 'https://entra.microsoft.com'
    elif portal == 'defender':
        return 'https://security.microsoft.com'

    # AI Foundry
    if portal == 'ai-foundry':
        if 'ai.azure.com' in article:
            url_match = re.search(r'https://ai\.azure\.com[^\s\)\]\"\']*', article)
            if url_match:
                return url_match.group(0)
        return 'https://ai.azure.com'

    # Azure portal - try to determine the specific blade/resource
    # Key Vault
    if 'key vault' in alt or 'keyvault' in alt or 'key vault' in ctx:
        blade = 'secrets' if 'secret' in alt else 'overview'
        return f'{PORTAL_BASE}#@/resource{KNOWN_RESOURCES["contoso-kv-demo"]}/{blade}'

    # Cognitive Services / AI Services
    if any(x in alt for x in ['cognitive', 'ai service', 'api kind', 'keys and endpoint', 'key page']):
        blade = 'overview'
        if 'key' in alt:
            blade = 'cskeys'
        if 'network' in alt or 'vnet' in alt:
            blade = 'networking'
        return f'{PORTAL_BASE}#@/resource{KNOWN_RESOURCES["contoso-ai-services"]}/{blade}'

    # Search for specific Azure portal URLs in the article
    portal_urls = re.findall(r'https://portal\.azure\.com[^\s\)\]\"\']*', article)
    if portal_urls:
        return portal_urls[0]

    # Resource group pages
    if 'resource group' in alt:
        return f'{PORTAL_BASE}#@/resource/subscriptions/{SUB_ID}/resourceGroups/contoso-screenshot-rg/overview'

    # Default: try to navigate to a relevant blade based on service area keywords
    # For Azure services, go to the service's landing page
    service_blades = {
        'app-service': f'{PORTAL_BASE}#view/HubsExtension/BrowseResource/resourceType/Microsoft.Web%2Fsites',
        'virtual-machines': f'{PORTAL_BASE}#view/HubsExtension/BrowseResource/resourceType/Microsoft.Compute%2FvirtualMachines',
        'storage': f'{PORTAL_BASE}#view/HubsExtension/BrowseResource/resourceType/Microsoft.Storage%2FstorageAccounts',
        'sql': f'{PORTAL_BASE}#view/HubsExtension/BrowseResource/resourceType/Microsoft.Sql%2Fservers',
        'monitor': f'{PORTAL_BASE}#view/Microsoft_Azure_Monitoring/AzureMonitoringBrowseBlade',
        'network': f'{PORTAL_BASE}#view/HubsExtension/BrowseResource/resourceType/Microsoft.Network%2FvirtualNetworks',
        'search': f'{PORTAL_BASE}#view/HubsExtension/BrowseResource/resourceType/Microsoft.Search%2FsearchServices',
        'machine-learning': f'{PORTAL_BASE}#view/HubsExtension/BrowseResource/resourceType/Microsoft.MachineLearningServices%2Fworkspaces',
    }

    if area in service_blades:
        return service_blades[area]

    # Fallback: Azure portal home
    return f'{PORTAL_BASE}#home'


def safe_print(text):
    """Print handling encoding issues."""
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode('ascii', errors='replace').decode('ascii'))


def process_one(item, idx, total, results):
    """Process a single manifest entry."""
    image_id = item['id']
    safe_print(f"\n{'='*60}")
    safe_print(f"[{idx}/{total}] {image_id} | {item['repo']} | {item['portal']}")
    safe_print(f"  Alt: {item['alt_text'][:90]}")
    safe_print(f"  Area: {item['service_area']}")
    safe_print(f"{'='*60}")

    # Read article
    article = read_article(item)

    # Determine URL
    url = determine_url(item, article)
    safe_print(f"  URL: {url[:120]}")

    # Navigate
    safe_print(f"  Navigating...")
    navigate(url, wait=8)

    # Get page info
    info = get_page_info()
    safe_print(f"  Page: {info['title'][:60]}")

    # Capture
    safe_print(f"  Capturing...")
    cap_path = capture(image_id)

    # Check result
    if os.path.exists(cap_path):
        size_kb = os.path.getsize(cap_path) / 1024
        status = 'CAPTURE_SUCCESS' if size_kb > 5 else 'NAVIGATION_FAILURE'
        safe_print(f"  Result: {status} ({size_kb:.1f}KB)")
        results[image_id] = {
            'status': status,
            'captured_path': cap_path,
            'size_kb': round(size_kb, 1),
            'page_url': info['url'],
            'page_title': info['title'],
            'target_url': url[:200],
            'repo': item['repo'],
            'article_path': item['article'],
        }
    else:
        safe_print(f"  Result: NAVIGATION_FAILURE (no file)")
        results[image_id] = {
            'status': 'NAVIGATION_FAILURE',
            'error': 'No screenshot file produced',
            'page_url': info['url'],
            'page_title': info['title'],
            'target_url': url[:200],
            'repo': item['repo'],
            'article_path': item['article'],
        }


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--start', type=int, default=0)
    parser.add_argument('--count', type=int, default=10)
    parser.add_argument('--skip-existing', action='store_true')
    args = parser.parse_args()

    manifest = json.load(open(MANIFEST_PATH))
    results = {}
    if os.path.exists(RESULTS_PATH):
        results = json.load(open(RESULTS_PATH))

    os.makedirs(CAPTURED_DIR, exist_ok=True)

    entries = manifest[args.start:args.start + args.count]
    total = len(manifest)

    safe_print(f"Processing {len(entries)} entries (start={args.start}, total={total})")

    for i, item in enumerate(entries):
        idx = args.start + i + 1

        if args.skip_existing and item['id'] in results and results[item['id']].get('status') == 'CAPTURE_SUCCESS':
            safe_print(f"  SKIP {item['id']}: already captured")
            continue

        try:
            process_one(item, idx, total, results)
        except Exception as e:
            safe_print(f"  ERROR: {e}")
            results[item['id']] = {
                'status': 'DATA_SETUP_FAILURE',
                'error': str(e)[:200],
                'repo': item['repo'],
                'article_path': item['article'],
            }

        # Save after each capture
        with open(RESULTS_PATH, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2)

    # Print summary
    statuses = {}
    for r in results.values():
        s = r.get('status', 'UNKNOWN')
        statuses[s] = statuses.get(s, 0) + 1
    safe_print(f"\n{'='*60}")
    safe_print(f"Batch complete. Status summary: {statuses}")
    safe_print(f"Results: {RESULTS_PATH}")


if __name__ == '__main__':
    main()
