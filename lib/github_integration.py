"""
GitHub API integration for the screenshot skill.

Provides helpers for creating branches, committing files, opening PRs,
and creating gists. All operations use the GitHub CLI (`gh`) for
authentication.
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO = os.environ.get("SCREENSHOT_REPO", "jonburchel/docs-screenshot")


def _gh(*args: str, input_data: str | None = None) -> str:
    """Run a gh CLI command and return stdout."""
    cmd = ["gh"] + list(args)
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        input=input_data,
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(f"gh command failed: {' '.join(cmd)}\n{result.stderr}")
    return result.stdout.strip()


# ---------------------------------------------------------------------------
# Branches and PRs
# ---------------------------------------------------------------------------

def create_branch(branch_name: str, base: str = "master") -> None:
    """Create a new branch from base (locally)."""
    subprocess.run(["git", "checkout", base], capture_output=True, cwd=_repo_dir())
    subprocess.run(["git", "pull", "origin", base], capture_output=True, cwd=_repo_dir())
    subprocess.run(["git", "checkout", "-b", branch_name], capture_output=True, cwd=_repo_dir())


def commit_and_push(branch_name: str, message: str, files: list[str]) -> None:
    """Stage files, commit, and push the branch."""
    repo = _repo_dir()
    for f in files:
        subprocess.run(["git", "add", f], capture_output=True, cwd=repo)
    subprocess.run(
        ["git", "commit", "-m", message,
         "--author", "Screenshot Feedback Bot <bot@docs-screenshot.local>"],
        capture_output=True, cwd=repo,
    )
    subprocess.run(["git", "push", "-u", "origin", branch_name], capture_output=True, cwd=repo)


def create_pull_request(
    branch: str,
    title: str,
    body: str,
    base: str = "master",
    issue_number: int | None = None,
) -> str:
    """Create a PR and return its URL."""
    cmd = [
        "pr", "create",
        "--repo", REPO,
        "--head", branch,
        "--base", base,
        "--title", title,
        "--body", body,
    ]
    return _gh(*cmd)


# ---------------------------------------------------------------------------
# Gists
# ---------------------------------------------------------------------------

def create_gist(filename: str, content: str, description: str = "", public: bool = False) -> str:
    """Create a gist and return its URL. Writes to a temp file first."""
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=f"_{filename}", delete=False, encoding="utf-8") as f:
        f.write(content)
        tmp_path = f.name

    try:
        cmd = ["gist", "create", tmp_path, "--desc", description]
        if public:
            cmd.append("--public")
        url = _gh(*cmd)
        return url.strip()
    finally:
        os.unlink(tmp_path)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_skill_version() -> str:
    """Return the current skill commit SHA (short hash)."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, cwd=_repo_dir(), timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return "unknown"


def _repo_dir() -> str:
    """Return the local repo directory."""
    env = os.environ.get("SCREENSHOT_REPO_DIR")
    if env and os.path.isdir(env):
        return env
    candidates = [
        r"F:\home\docs-screenshot",
        os.path.expanduser("~/docs-screenshot"),
        os.path.join(os.getcwd(), "docs-screenshot"),
    ]
    for c in candidates:
        if os.path.isdir(os.path.join(c, ".git")):
            return c
    return os.getcwd()


def create_comparison_pr(
    before_images: dict[str, str],
    after_images: dict[str, str],
    changed_files: list[str] | None = None,
    title: str = "Screenshot skill improvements",
    base: str = "master",
) -> str:
    """
    Create a PR with before/after comparison images and any skill changes.

    This is used at the end of an interactive compare session when the user
    approves all screenshots. The PR includes committed before/after images
    so reviewers can visually validate the changes.

    Args:
        before_images: {image_name: file_path} for first-iteration captures
        after_images: {image_name: file_path} for final captures
        changed_files: Additional files to include (skill code changes)
        title: PR title
        base: Base branch for the PR

    Returns:
        PR URL string
    """
    import shutil
    from datetime import datetime

    repo = _repo_dir()
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    branch = f"compare/screenshot-updates-{timestamp}"

    create_branch(branch, base)

    # Copy before/after images into the repo
    compare_dir = os.path.join(repo, "test-comparison", f"compare-{timestamp}")
    os.makedirs(os.path.join(compare_dir, "before"), exist_ok=True)
    os.makedirs(os.path.join(compare_dir, "after"), exist_ok=True)

    files_to_commit = []
    for name, path in before_images.items():
        if os.path.exists(path):
            dst = os.path.join(compare_dir, "before", name)
            shutil.copy2(path, dst)
            files_to_commit.append(dst)

    for name, path in after_images.items():
        if os.path.exists(path):
            dst = os.path.join(compare_dir, "after", name)
            shutil.copy2(path, dst)
            files_to_commit.append(dst)

    if changed_files:
        files_to_commit.extend(f for f in changed_files if os.path.exists(f))

    # Build PR body with before/after summary
    body_lines = [
        "## Screenshot Skill Updates",
        "",
        f"Updated {len(after_images)} screenshot(s) through interactive comparison review.",
        "",
        "### Before/After Comparison",
        "",
        "| Screenshot | Status |",
        "|---|---|",
    ]
    for name in sorted(set(list(before_images.keys()) + list(after_images.keys()))):
        has_before = name in before_images and os.path.exists(before_images.get(name, ""))
        has_after = name in after_images and os.path.exists(after_images.get(name, ""))
        if has_before and has_after:
            body_lines.append(f"| `{name}` | Updated |")
        elif has_after:
            body_lines.append(f"| `{name}` | New |")

    body_lines.extend([
        "",
        f"Before/after images are in `test-comparison/compare-{timestamp}/`.",
        "",
        "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>",
    ])

    commit_msg = (
        f"Update {len(after_images)} screenshot(s) via interactive compare\n\n"
        + "\n".join(f"- {name}" for name in sorted(after_images.keys()))
        + "\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
    )

    if files_to_commit:
        commit_and_push(branch, commit_msg, files_to_commit)

    pr_url = create_pull_request(
        branch=branch,
        title=title,
        body="\n".join(body_lines),
        base=base,
    )

    return pr_url
