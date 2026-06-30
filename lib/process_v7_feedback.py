"""
Process human feedback from the v7 comparison report.

Reads v7-feedback.json, groups changes by repo and priority,
and generates an action plan for Copilot to re-capture flagged images.

Usage:
    python process_v7_feedback.py [--feedback PATH] [--output PATH]

Or from Copilot: "process the user suggestions for the v7 report"
"""
import json
import os
import sys
from datetime import datetime

DEFAULT_FEEDBACK_PATH = os.path.join(
    os.path.dirname(__file__), '..', 'test-comparison', 'v7-feedback.json'
)
DEFAULT_OUTPUT_PATH = os.path.join(
    os.path.dirname(__file__), '..', 'test-comparison', 'v7-action-plan.json'
)

# Priority ordering for categories (highest first)
CATEGORY_PRIORITY = {
    'pii_leak': 1,
    'failed': 2,
    'privilege_issue': 3,
    'wrong_content': 4,
    'service_restructured': 5,
    'missing_elements': 6,
    'minor_issues': 7,
    'doc_insufficient': 8,
    'correct': 9,
    'perfect': 10,
    'pending': 99,
}

# Action templates per category
CATEGORY_ACTIONS = {
    'pii_leak': {
        'action': 're-capture with enhanced PII scrubbing',
        'details': 'Review DOM scrubber rules. Check for PII patterns missed by current regex. '
                   'Verify cross-origin iframe scrubbing is working. Add custom scrub rules if needed.',
        'severity': 'critical',
    },
    'failed': {
        'action': 're-capture with different navigation approach',
        'details': 'Re-examine the article context for navigation clues. Try alternative portal URLs. '
                   'Check if the resource type or service has changed.',
        'severity': 'critical',
    },
    'privilege_issue': {
        'action': 'flag for manual capture or role elevation',
        'details': 'This page requires roles/licenses the automation account lacks. '
                   'Options: elevate permissions, use a different test account, or capture manually.',
        'severity': 'high',
    },
    'wrong_content': {
        'action': 're-capture with corrected navigation',
        'details': 'The capture landed on the wrong page or showed wrong state. '
                   'Review the article steps more carefully. Check for URL changes or redirects.',
        'severity': 'high',
    },
    'service_restructured': {
        'action': 'investigate service changes and update approach',
        'details': 'The Azure service has been renamed or reorganized. '
                   'Check repo_config.py service rename mappings. The doc itself may need updating.',
        'severity': 'medium',
    },
    'missing_elements': {
        'action': 're-capture with improved element targeting',
        'details': 'Key UI elements were not found in the capture. '
                   'Check callout_finder.js selectors. May need to click flyouts or expand sections.',
        'severity': 'medium',
    },
    'minor_issues': {
        'action': 'refine capture parameters',
        'details': 'Small differences detected. May need adjustment to crop, callout placement, '
                   'or timing. Check if extra wait time or different viewport helps.',
        'severity': 'low',
    },
    'doc_insufficient': {
        'action': 'flag article for content team review',
        'details': 'The doc does not describe the screenshot well enough for automated capture. '
                   'Suggest improving alt-text and surrounding step descriptions.',
        'severity': 'info',
    },
    'correct': {
        'action': 'no action needed (human confirmed correct)',
        'details': 'Human reviewer verified this capture is correct.',
        'severity': 'none',
    },
    'perfect': {
        'action': 'no action needed (pixel-perfect)',
        'details': 'Human reviewer confirmed this is a perfect capture.',
        'severity': 'none',
    },
}


def load_feedback(path):
    """Load and validate the feedback JSON file."""
    if not os.path.exists(path):
        print(f"ERROR: Feedback file not found: {path}")
        print("Make sure to save feedback from the v7 report first.")
        sys.exit(1)

    with open(path, encoding='utf-8') as f:
        data = json.load(f)

    # Validate structure
    if 'items' not in data:
        print("ERROR: Invalid feedback file (missing 'items' key)")
        sys.exit(1)

    return data


def analyze_feedback(data):
    """Analyze feedback and generate prioritized action items."""
    items = data.get('items', [])
    
    # Separate changed items from unchanged
    changed = [i for i in items if i.get('changed', False)]
    with_notes = [i for i in items if i.get('human_notes', '').strip()]
    actionable = []

    # Process changed items
    for item in items:
        cat = item.get('human_category', item.get('auto_category', 'pending'))
        cat_lower = cat.lower().replace(' ', '_')
        notes = item.get('human_notes', '').strip()
        was_changed = item.get('changed', False)
        
        # Skip items that are confirmed correct/perfect with no notes
        if cat_lower in ('correct', 'perfect') and not notes:
            continue
        
        # Skip unchanged pending items
        if not was_changed and not notes and cat_lower == 'pending':
            continue

        action_template = CATEGORY_ACTIONS.get(cat_lower, {
            'action': f'review and re-assess ({cat})',
            'details': 'Human rater assigned a non-standard category.',
            'severity': 'medium',
        })
        
        priority = CATEGORY_PRIORITY.get(cat_lower, 50)
        
        action_item = {
            'id': item['id'],
            'repo': item.get('repo', 'unknown'),
            'article_path': item.get('article_path', ''),
            'image_path': item.get('image_path', ''),
            'human_category': cat,
            'auto_category': item.get('auto_category', ''),
            'priority': priority,
            'action': action_template['action'],
            'details': action_template['details'],
            'severity': action_template['severity'],
            'human_notes': notes,
            'was_changed': was_changed,
        }
        
        # If human provided specific notes, append them to the action details
        if notes:
            action_item['details'] += f'\n\nHuman reviewer notes: {notes}'
        
        actionable.append(action_item)
    
    # Sort by priority (lower number = higher priority)
    actionable.sort(key=lambda x: x['priority'])
    
    return {
        'total_items': len(items),
        'total_changed': len(changed),
        'total_with_notes': len(with_notes),
        'total_actionable': len(actionable),
        'actions': actionable,
    }


def group_by_repo(actions):
    """Group action items by repo, with repo as a hint not a strict rule."""
    by_repo = {}
    for action in actions:
        repo = action['repo']
        by_repo.setdefault(repo, []).append(action)
    return by_repo


def group_by_severity(actions):
    """Group action items by severity."""
    by_sev = {}
    for action in actions:
        sev = action['severity']
        by_sev.setdefault(sev, []).append(action)
    return by_sev


def generate_action_plan(analysis, feedback_data):
    """Generate a structured action plan JSON."""
    actions = analysis['actions']
    by_repo = group_by_repo(actions)
    by_severity = group_by_severity(actions)
    
    plan = {
        'version': 'v7',
        'generated_at': datetime.now().isoformat(),
        'feedback_reviewed_at': feedback_data.get('reviewed_at', ''),
        'summary': {
            'total_images': analysis['total_items'],
            'total_changed_by_human': analysis['total_changed'],
            'total_with_notes': analysis['total_with_notes'],
            'total_actionable': analysis['total_actionable'],
            'by_severity': {sev: len(items) for sev, items in by_severity.items()},
            'by_repo': {repo: len(items) for repo, items in by_repo.items()},
        },
        'action_items': actions,
        'by_repo': {
            repo: [a['id'] for a in items]
            for repo, items in by_repo.items()
        },
        'instructions': (
            'Process these action items in priority order (critical first). '
            'The repo field is a HINT for context, not a strict rule. '
            'Suggestions may be generally applicable across repos. '
            'For re-captures, use the article_path and image_path to find the original context. '
            'For workflow improvements, update the relevant lib/ module.'
        ),
    }
    
    return plan


def print_summary(analysis):
    """Print a human-readable summary."""
    print(f"\n{'='*60}")
    print("V7 Feedback Analysis")
    print(f"{'='*60}")
    print(f"Total images reviewed: {analysis['total_items']}")
    print(f"Categories changed by human: {analysis['total_changed']}")
    print(f"Items with notes: {analysis['total_with_notes']}")
    print(f"Actionable items: {analysis['total_actionable']}")
    
    if analysis['actions']:
        by_sev = group_by_severity(analysis['actions'])
        print("\nBy severity:")
        for sev in ['critical', 'high', 'medium', 'low', 'info', 'none']:
            count = len(by_sev.get(sev, []))
            if count:
                print(f"  {sev}: {count}")
        
        by_repo = group_by_repo(analysis['actions'])
        print("\nBy repo:")
        for repo, items in sorted(by_repo.items()):
            print(f"  {repo}: {len(items)}")
        
        print("\nTop priority actions:")
        for action in analysis['actions'][:10]:
            notes_indicator = " [+notes]" if action['human_notes'] else ""
            print(f"  [{action['severity'].upper()}] {action['id']} ({action['repo']}): "
                  f"{action['action']}{notes_indicator}")
    else:
        print("\nNo actionable items found. All captures confirmed correct!")


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Process v7 feedback')
    parser.add_argument('--feedback', default=DEFAULT_FEEDBACK_PATH,
                        help='Path to v7-feedback.json')
    parser.add_argument('--output', default=DEFAULT_OUTPUT_PATH,
                        help='Path for output action plan')
    args = parser.parse_args()
    
    print(f"Loading feedback from: {args.feedback}")
    feedback_data = load_feedback(args.feedback)
    
    print("Analyzing feedback...")
    analysis = analyze_feedback(feedback_data)
    
    print_summary(analysis)
    
    # Generate and save action plan
    plan = generate_action_plan(analysis, feedback_data)
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(plan, f, indent=2)
    print(f"\nAction plan saved to: {args.output}")
    
    return plan


if __name__ == '__main__':
    main()
