"""
Auto-classify v7 captures and update the HTML report with default ratings.

Compares each capture's actual page (title, URL) against what the screenshot
should show (alt-text, context) to produce an honest auto-classification.

Also updates the report JavaScript to track human overrides properly.
"""
import json
import os
import re

RESULTS_PATH = r'F:\home\docs-screenshot\test-comparison\v7-results.json'
MANIFEST_PATH = r'F:\home\docs-screenshot\test-comparison\v7-manifest.json'
REPORT_PATH = r'F:\home\docs-screenshot\test-comparison\comparison-report-v7.html'


def classify_capture(item, result):
    """
    Compare what was captured vs what should have been captured.
    Returns a category string.
    """
    alt = item.get('alt_text', '').lower()
    context = item.get('context', '').lower()
    portal = item.get('portal', 'azure')
    area = item.get('service_area', '')

    page_title = result.get('page_title', '').lower()
    page_url = result.get('page_url', '').lower()
    target_url = result.get('target_url', '').lower()
    size_kb = result.get('size_kb', 0)
    status = result.get('status', 'PENDING')

    if status != 'CAPTURE_SUCCESS':
        return 'failed'

    # Very small image = blank/error page
    if size_kb < 5:
        return 'failed'

    # Check if we landed on a generic home page when we needed a specific page
    generic_homes = [
        'home - microsoft azure',
        'microsoft foundry',
        'power bi',
        'security & compliance',
    ]

    on_generic_home = any(g in page_title for g in generic_homes)

    # Determine if the alt-text describes something specific vs generic
    # Generic descriptions that could match a home page
    generic_alt_patterns = [
        'home page', 'home screen', 'landing page', 'main page',
        'portal home', 'dashboard overview',
    ]
    alt_is_generic = any(p in alt for p in generic_alt_patterns)

    # Specific descriptions that require navigating to a particular resource/blade
    needs_specific_resource = any(kw in alt for kw in [
        'key vault', 'secret', 'endpoint', 'configuration', 'networking',
        'create ', 'form', 'blade', 'pane', 'flyout', 'dialog',
        'settings', 'properties', 'json view', 'api kind',
        'skillset', 'index', 'query', 'connector', 'pipeline',
    ])

    needs_specific_page = any(kw in alt for kw in [
        'overview', 'details', 'tab ', 'page showing', 'view of',
        'selected', 'dropdown', 'option', 'button', 'menu',
        'list', 'table', 'chart', 'graph', 'alert',
    ])

    # Check if the screenshot is actually of a non-portal thing
    # (terminal output, VS Code, local UI, web page, etc.)
    non_portal = any(kw in alt for kw in [
        'terminal', 'command line', 'output from', 'cli ',
        'visual studio', 'vs code', 'browser', 'web app',
        'line chart', 'face image', 'pdf', 'local web ui',
    ])

    # If we're on a specific page that relates to the content
    if not on_generic_home:
        # We navigated somewhere specific
        # Check if the page title/URL relates to the alt-text
        alt_words = set(re.findall(r'\w+', alt))
        title_words = set(re.findall(r'\w+', page_title))
        overlap = alt_words & title_words - {'screenshot', 'of', 'the', 'a', 'an', 'in', 'for', 'and', 'or', 'to', 'with', 'that', 'shows', 'showing'}

        if len(overlap) >= 2:
            # Good overlap between alt-text and page title
            return 'correct'
        elif len(overlap) >= 1:
            return 'minor_issues'

        # Special cases: portal-specific pages
        if portal == 'entra' and 'entra' in page_title:
            return 'correct'
        if portal == 'defender' and ('defender' in page_title or 'security' in page_title):
            return 'minor_issues'
        if portal == 'fabric' and 'power bi' in page_title:
            return 'minor_issues'

        # Landed on a specific resource page
        if 'contoso' in page_title and needs_specific_resource:
            return 'minor_issues'

        return 'minor_issues'

    # We're on a generic home page
    if alt_is_generic:
        # Alt-text describes something generic too; home page might be acceptable
        return 'minor_issues'

    if non_portal:
        # This screenshot isn't of a portal at all; we captured portal home instead
        return 'wrong_content'

    if needs_specific_resource or needs_specific_page:
        # Needed a specific page but got home
        return 'wrong_content'

    # Fabric portal home when the screenshot is supposed to be of a Fabric feature
    if portal == 'fabric' and on_generic_home:
        return 'wrong_content'

    # AI Foundry home when needing specific Foundry content
    if portal == 'ai-foundry' and 'microsoft foundry' in page_title:
        # Check if the alt-text describes something you'd see on the Foundry landing
        if any(kw in alt for kw in ['foundry', 'project', 'hub', 'model catalog']):
            return 'minor_issues'
        return 'wrong_content'

    # Default for generic home with unclear target
    return 'wrong_content'


def main():
    manifest = json.load(open(MANIFEST_PATH, 'r', encoding='utf-8'))
    results = json.load(open(RESULTS_PATH, 'r', encoding='utf-8'))

    # Build classification map
    classifications = {}
    summary = {}

    for item in manifest:
        image_id = item['id']
        result = results.get(image_id, {'status': 'PENDING'})
        cat = classify_capture(item, result)
        classifications[image_id] = cat
        summary[cat] = summary.get(cat, 0) + 1

    print("Auto-classification summary:")
    for cat, count in sorted(summary.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {count}")
    print(f"  Total: {sum(summary.values())}")

    # Save classifications
    class_path = os.path.join(os.path.dirname(RESULTS_PATH), 'v7-auto-classifications.json')
    with open(class_path, 'w', encoding='utf-8') as f:
        json.dump(classifications, f, indent=2)
    print(f"\nSaved to: {class_path}")

    # Now update the HTML report
    print("\nUpdating report HTML...")
    with open(REPORT_PATH, 'r', encoding='utf-8') as f:
        html = f.read()

    # 1. For each dropdown, set the auto-classification as the default selected option
    updates = 0
    for image_id, cat in classifications.items():
        # Find the select element for this image and change which option is selected
        # Current: <option value="pending" selected>⏳ Pending</option>
        # Need: remove "selected" from pending, add it to the correct category

        # Pattern for the select with this data-id
        select_pattern = re.compile(
            rf'(<select class="human-category" data-id="{re.escape(image_id)}"[^>]*>)(.*?)(</select>)',
            re.DOTALL
        )
        match = select_pattern.search(html)
        if match:
            options_html = match.group(2)
            # Remove all existing "selected" attributes
            options_html = options_html.replace(' selected', '')
            # Add "selected" to the correct option
            options_html = options_html.replace(
                f'value="{cat}">',
                f'value="{cat}" selected>'
            )
            html = select_pattern.sub(
                match.group(1) + options_html + match.group(3),
                html, count=1
            )
            updates += 1

    print(f"  Updated {updates} dropdowns with auto-defaults")

    # 2. Add a data-auto-default attribute to each select so JS knows the original classification
    for image_id, cat in classifications.items():
        html = html.replace(
            f'<select class="human-category" data-id="{image_id}"',
            f'<select class="human-category" data-id="{image_id}" data-auto-default="{cat}"'
        )

    # 3. Update the JavaScript to track human overrides properly
    # Replace onCategoryChange to detect changes from auto-default
    old_on_change = 'function onCategoryChange() {\n  renderDashboard();\n  applyFilters();\n}'
    new_on_change = """function onCategoryChange() {
  renderDashboard();
  applyFilters();
  updateChangeIndicators();
}

function updateChangeIndicators() {
  document.querySelectorAll('.human-category').forEach(sel => {
    const autoDefault = sel.dataset.autoDefault || 'pending';
    const current = sel.value;
    const card = sel.closest('.entry-card');
    if (current !== autoDefault) {
      sel.classList.add('human-changed');
      if (card) card.classList.add('has-change');
    } else {
      sel.classList.remove('human-changed');
      if (card) card.classList.remove('has-change');
    }
  });
}"""
    html = html.replace(old_on_change, new_on_change)

    # 4. Update saveFeedback to properly track changes from auto-default (not from "pending")
    old_save_changed = "    const changed = humanCat !== 'pending';\n    if (changed) { totalReviewed++; totalChanged++; }"
    new_save_changed = """    const autoDefault = sel ? (sel.dataset.autoDefault || 'pending') : 'pending';
    const changed = humanCat !== autoDefault;
    const hasNotes = humanNotes.length > 0;
    if (changed || hasNotes) { totalReviewed++; }
    if (changed) { totalChanged++; }"""
    html = html.replace(old_save_changed, new_save_changed)

    # 5. Update the feedback item to include auto_category properly
    old_push = """    items.push({
      id: entry.id,
      repo: entry.repo,
      article_path: entry.article,
      image_path: entry.source,
      auto_category: "CAPTURE_PENDING",
      human_category: humanCat,
      human_notes: humanNotes,
      changed: changed
    });"""
    new_push = """    items.push({
      id: entry.id,
      repo: entry.repo,
      article_path: entry.article,
      image_path: entry.source,
      auto_category: autoDefault,
      human_category: humanCat,
      human_notes: humanNotes,
      changed: changed,
      has_notes: hasNotes
    });"""
    html = html.replace(old_push, new_push)

    # 6. Update the "Only changed" filter to use auto-default comparison
    old_filter = "if (onlyChanged && selVal === 'pending') visible = false;"
    new_filter = "if (onlyChanged && selVal === (sel ? (sel.dataset.autoDefault || 'pending') : 'pending') && !(card.querySelector('.human-notes') && card.querySelector('.human-notes').value.trim())) visible = false;"
    html = html.replace(old_filter, new_filter)

    # 7. Add CSS for changed indicators
    change_css = """
.human-changed{outline:2px solid #f97316;outline-offset:1px;border-radius:3px}
.has-change .card-header{border-left:3px solid #f97316}
"""
    html = html.replace('</style>', change_css + '</style>')

    # Save updated report
    with open(REPORT_PATH, 'w', encoding='utf-8') as f:
        f.write(html)

    report_size = os.path.getsize(REPORT_PATH) / (1024 * 1024)
    print(f"  Report saved: {report_size:.1f} MB")
    print("\nDone! Report now shows auto-classifications as defaults.")
    print("Human raters can override any classification; changes are tracked and highlighted.")


if __name__ == '__main__':
    main()
