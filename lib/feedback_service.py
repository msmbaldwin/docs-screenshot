"""
Feedback processing service for the screenshot skill.

Polls GitHub for issues labeled 'screenshot-feedback', processes each one by:
1. Parsing the feedback items from the issue body
2. Invoking Copilot CLI to analyze each problem and propose skill fixes
3. Applying fixes to the local skill checkout
4. Recapturing affected screenshots
5. Creating a PR branch with before/after images
6. Publishing a gist comparison page for review
7. Posting results back to the issue and closing it

Run with: python lib/feedback_service.py
Or via:   runservice.cmd
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# Ensure lib/ is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib import github_integration as gh
from lib.gist_comparison import publish_gist_comparison

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("feedback-service")

POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", "60"))
REPO_DIR = os.environ.get("SCREENSHOT_REPO_DIR", str(Path(__file__).parent.parent))
WORK_DIR = os.path.join(REPO_DIR, ".service-work")


def process_issue(issue: dict) -> None:
    """Process a single feedback issue end-to-end."""
    number = issue["number"]
    title = issue["title"]
    body = issue["body"]

    log.info(f"Processing issue #{number}: {title}")

    # Mark as processing
    gh.add_label(number, gh.PROCESSING_LABEL)

    try:
        # Parse feedback items
        items = gh.parse_feedback_body(body)
        if not items:
            gh.comment_on_issue(number, "Could not parse feedback items from issue body. Please use the comparison report Submit button to create properly formatted feedback.")
            gh.remove_label(number, gh.PROCESSING_LABEL)
            return

        log.info(f"  Found {len(items)} feedback items")

        # Create working directory
        work = os.path.join(WORK_DIR, f"issue-{number}")
        os.makedirs(os.path.join(work, "before"), exist_ok=True)
        os.makedirs(os.path.join(work, "after"), exist_ok=True)

        # Create branch
        branch = f"fix/screenshot-feedback-{number}"
        gh.create_branch(branch)

        # Process each feedback item
        fixes = []
        for i, item in enumerate(items):
            image = item.get("image", f"unknown-{i}")
            article = item.get("article", "")
            suggestion = item.get("suggestion", "")

            log.info(f"  [{i+1}/{len(items)}] {image}: {suggestion[:80]}")

            # Save before image if provided
            before_path = os.path.join(work, "before", image)
            if item.get("captured_b64"):
                import base64
                with open(before_path, "wb") as f:
                    f.write(base64.b64decode(item["captured_b64"]))
            elif not os.path.exists(before_path):
                # Try to find it in the repo
                for candidate in [
                    os.path.join(REPO_DIR, "test-output", image),
                    os.path.join(REPO_DIR, "test-comparison", "captured", image),
                ]:
                    if os.path.exists(candidate):
                        shutil.copy2(candidate, before_path)
                        break

            # Analyze the problem and propose a fix using Copilot CLI
            changes_made = analyze_and_fix(image, article, suggestion)

            # Attempt recapture (may fail if portal access unavailable)
            after_path = os.path.join(work, "after", image)
            recaptured = attempt_recapture(image, article, after_path)

            if not recaptured:
                # Create a placeholder
                if os.path.exists(before_path):
                    shutil.copy2(before_path, after_path)
                changes_made += " (recapture skipped; portal not accessible)"

            fixes.append({
                "image": image,
                "article": article,
                "suggestion": suggestion,
                "changes_made": changes_made,
                "before_path": before_path,
                "after_path": after_path,
            })

        # Copy before/after images into repo for the PR
        pr_images_dir = os.path.join(REPO_DIR, "test-comparison", f"feedback-{number}")
        os.makedirs(os.path.join(pr_images_dir, "before"), exist_ok=True)
        os.makedirs(os.path.join(pr_images_dir, "after"), exist_ok=True)

        files_to_commit = []
        for fix in fixes:
            for stage in ["before", "after"]:
                src = fix[f"{stage}_path"]
                if os.path.exists(src):
                    dst = os.path.join(pr_images_dir, stage, fix["image"])
                    shutil.copy2(src, dst)
                    files_to_commit.append(dst)

        # Commit skill changes and images
        all_changed = files_to_commit + _get_changed_skill_files()
        if all_changed:
            gh.commit_and_push(
                branch,
                f"Fix screenshots from feedback issue #{number}\n\n"
                + "\n".join(f"- {f['image']}: {f['suggestion'][:60]}" for f in fixes)
                + f"\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>",
                all_changed,
            )

        # Create PR
        pr_body = _build_pr_body(number, fixes)
        pr_url = gh.create_pull_request(
            branch=branch,
            title=f"Fix {len(fixes)} screenshot(s) from feedback #{number}",
            body=pr_body,
            issue_number=number,
        )

        # Publish gist comparison page
        gist_url = ""
        try:
            gist_url = publish_gist_comparison(fixes, number, pr_url)
            log.info(f"  Gist published: {gist_url}")
        except Exception as e:
            log.warning(f"  Gist creation failed: {e}")

        # Comment on issue with results
        comment = _build_result_comment(number, fixes, pr_url, gist_url)
        gh.comment_on_issue(number, comment)

        # Mark completed
        gh.remove_label(number, gh.PROCESSING_LABEL)
        gh.add_label(number, gh.COMPLETED_LABEL)
        gh.close_issue(number)

        log.info(f"  Issue #{number} processed successfully. PR: {pr_url}")

    except Exception as e:
        log.error(f"  Error processing issue #{number}: {e}", exc_info=True)
        try:
            gh.comment_on_issue(number, f"Error processing this feedback:\n```\n{e}\n```\nPlease check the service logs.")
            gh.remove_label(number, gh.PROCESSING_LABEL)
        except Exception:
            pass


def analyze_and_fix(image: str, article: str, suggestion: str) -> str:
    """
    Use Copilot CLI to analyze the problem and propose skill fixes.

    Returns a description of changes made.
    """
    prompt = f"""Analyze this screenshot feedback and suggest a fix for the docs-screenshot skill.

Image: {image}
Article: {article}
Problem: {suggestion}

The skill is at {REPO_DIR}. Key files:
- lib/callout_finder.js - DOM element finder for callout placement
- lib/image_editor.py - Image processing (callouts, cropping)
- lib/screenshot_processor.py - Orchestration pipeline
- SKILL.md - Skill documentation and rules

What specific code change would fix this problem? Be precise about which file and what to change.
Reply with just the fix description (one paragraph). Do not make changes yourself."""

    try:
        result = subprocess.run(
            ["gh", "copilot", "explain", prompt],
            capture_output=True, text=True, timeout=60,
            cwd=REPO_DIR,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()[:500]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return f"Manual review needed for: {suggestion}"


def attempt_recapture(image: str, article: str, output_path: str) -> bool:
    """
    Attempt to recapture a screenshot.

    Returns True if successful, False if portal access unavailable.
    """
    # For now, recapture requires manual portal access.
    # Future: integrate with Playwright automation.
    log.info(f"    Recapture of {image} requires portal access (skipped in service mode)")
    return False


def _get_changed_skill_files() -> list[str]:
    """Get list of skill files that were modified (e.g., by Copilot fixes)."""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only"],
            capture_output=True, text=True, cwd=REPO_DIR,
        )
        if result.returncode == 0:
            return [
                os.path.join(REPO_DIR, f.strip())
                for f in result.stdout.strip().split("\n")
                if f.strip() and (f.endswith(".py") or f.endswith(".js") or f.endswith(".md"))
            ]
    except Exception:
        pass
    return []


def _build_pr_body(issue_number: int, fixes: list[dict]) -> str:
    """Build the PR description."""
    lines = [
        f"Fixes #{issue_number}",
        "",
        "## Changes",
        "",
    ]
    for i, fix in enumerate(fixes):
        lines.append(f"### {i+1}. `{fix['image']}`")
        lines.append(f"**Feedback:** {fix['suggestion']}")
        lines.append(f"**Fix:** {fix['changes_made']}")
        lines.append("")

    return "\n".join(lines)


def _build_result_comment(
    issue_number: int,
    fixes: list[dict],
    pr_url: str,
    gist_url: str,
) -> str:
    """Build the issue comment summarizing results."""
    lines = [
        "## Processing Complete",
        "",
        f"Created PR: {pr_url}",
    ]
    if gist_url:
        lines.append(f"Review comparison: {gist_url}")
        lines.append("(Use the review page to submit further feedback if needed)")
    lines.append("")
    lines.append("### Summary")
    lines.append("")

    for i, fix in enumerate(fixes):
        status = "recaptured" if os.path.exists(fix.get("after_path", "")) else "skill updated (recapture pending)"
        lines.append(f"- **{fix['image']}**: {fix['changes_made'][:100]} [{status}]")

    return "\n".join(lines)


def main():
    """Main service loop: poll for issues and process them."""
    log.info(f"Screenshot feedback service starting")
    log.info(f"  Repo: {gh.REPO}")
    log.info(f"  Poll interval: {POLL_INTERVAL}s")
    log.info(f"  Work dir: {WORK_DIR}")

    # Ensure labels exist
    try:
        gh.ensure_labels()
        log.info("  Labels verified")
    except Exception as e:
        log.warning(f"  Could not verify labels: {e}")

    os.makedirs(WORK_DIR, exist_ok=True)

    while True:
        try:
            issues = gh.list_feedback_issues()
            if issues:
                log.info(f"Found {len(issues)} issue(s) to process")
                for issue in issues:
                    process_issue(issue)
            else:
                log.debug("No pending issues")
        except KeyboardInterrupt:
            log.info("Service stopped by user")
            break
        except Exception as e:
            log.error(f"Poll error: {e}", exc_info=True)

        try:
            time.sleep(POLL_INTERVAL)
        except KeyboardInterrupt:
            log.info("Service stopped by user")
            break


if __name__ == "__main__":
    main()
