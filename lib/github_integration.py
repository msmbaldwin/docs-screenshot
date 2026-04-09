"""
GitHub API integration for the screenshot feedback loop.

Provides helpers for creating issues, managing labels, creating branches,
committing files, opening PRs, and creating gists. All operations use the
GitHub CLI (`gh`) for authentication, falling back to the REST API with
a GITHUB_TOKEN env var if gh is unavailable.
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
FEEDBACK_LABEL = "screenshot-feedback"
PROCESSING_LABEL = "processing"
COMPLETED_LABEL = "completed"


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
# Issues
# ---------------------------------------------------------------------------

def list_feedback_issues() -> list[dict]:
    """List open issues with the screenshot-feedback label (excluding processing)."""
    raw = _gh(
        "issue", "list",
        "--repo", REPO,
        "--label", FEEDBACK_LABEL,
        "--state", "open",
        "--json", "number,title,body,labels,createdAt",
        "--limit", "50",
    )
    issues = json.loads(raw) if raw else []
    # Exclude issues already being processed
    return [
        i for i in issues
        if not any(l["name"] == PROCESSING_LABEL for l in i.get("labels", []))
    ]


def create_issue(title: str, body: str, labels: list[str] | None = None) -> int:
    """Create a GitHub issue and return its number."""
    cmd = [
        "issue", "create",
        "--repo", REPO,
        "--title", title,
        "--body", body,
    ]
    if labels:
        for label in labels:
            cmd.extend(["--label", label])
    result = _gh(*cmd)
    # gh issue create prints the URL; extract issue number
    # e.g., https://github.com/owner/repo/issues/42
    return int(result.rstrip("/").split("/")[-1])


def add_label(issue_number: int, label: str) -> None:
    """Add a label to an issue."""
    _gh("issue", "edit", str(issue_number), "--repo", REPO, "--add-label", label)


def remove_label(issue_number: int, label: str) -> None:
    """Remove a label from an issue."""
    try:
        _gh("issue", "edit", str(issue_number), "--repo", REPO, "--remove-label", label)
    except RuntimeError:
        pass  # label may not exist


def close_issue(issue_number: int) -> None:
    """Close an issue."""
    _gh("issue", "close", str(issue_number), "--repo", REPO)


def comment_on_issue(issue_number: int, body: str) -> None:
    """Add a comment to an issue."""
    _gh("issue", "comment", str(issue_number), "--repo", REPO, "--body", body)


# ---------------------------------------------------------------------------
# Labels (ensure they exist)
# ---------------------------------------------------------------------------

def ensure_labels() -> None:
    """Create the required labels if they don't exist."""
    existing_raw = _gh("label", "list", "--repo", REPO, "--json", "name", "--limit", "100")
    existing = {l["name"] for l in json.loads(existing_raw)} if existing_raw else set()

    label_defs = [
        (FEEDBACK_LABEL, "Screenshot feedback from comparison report", "0075ca"),
        (PROCESSING_LABEL, "Being processed by feedback service", "fbca04"),
        (COMPLETED_LABEL, "Feedback processed and PR created", "0e8a16"),
    ]
    for name, desc, color in label_defs:
        if name not in existing:
            try:
                _gh("label", "create", name,
                     "--repo", REPO,
                     "--description", desc,
                     "--color", color)
            except RuntimeError:
                pass  # may already exist in a race


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

def _repo_dir() -> str:
    """Return the local repo directory."""
    # Check env var first, then common locations
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


def parse_feedback_body(body: str) -> list[dict]:
    """
    Parse a GitHub issue body created by the comparison report.

    Expected format:
    ```json
    [
      {
        "image": "copy-subscription-id.png",
        "article": "get-subscription-tenant-id.md",
        "suggestion": "Copy button callout is missing",
        "captured_b64": "...",
        "original_b64": "..."
      },
      ...
    ]
    ```

    Returns the parsed list of feedback items.
    """
    # Extract JSON block from the issue body
    start = body.find("```json")
    if start == -1:
        start = body.find("[")
        if start == -1:
            return []
        end = body.rfind("]") + 1
    else:
        start = body.index("\n", start) + 1
        end = body.index("```", start)

    try:
        return json.loads(body[start:end])
    except (json.JSONDecodeError, ValueError):
        return []
