"""
Repo-specific customization system for the docs-screenshot skill.

Per-repo customizations (path rules, service renames, portal hints, known
hidden nav items) live as YAML files under ``references/repos/<name>.yaml``.
This module loads them on first use and exposes the same public API the
rest of the skill has always used.

To add a new repo:

  1. Create ``references/repos/<repo-name>.yaml`` (use an existing file as
     a template).
  2. The file's basename (without ``.yaml``) is the repo name used by
     ``detect_repo_from_path()``.
  3. Restart any running Python process so the cache is refreshed.

JSON files (``references/repos/<name>.json``) are also supported and take
precedence over YAML when both exist. YAML support requires PyYAML; if it
isn't installed and only YAML files exist, those repos are skipped.
"""

from __future__ import annotations

import fnmatch
import json
import os
from pathlib import Path
from typing import Any

_REPOS_DIR = Path(__file__).parent.parent / "references" / "repos"
_CACHE: dict[str, dict[str, Any]] | None = None


def _load_one(path: Path) -> dict[str, Any] | None:
    """Load a single repo-config file (YAML or JSON)."""
    try:
        text = path.read_text(encoding="utf-8")
        if path.suffix.lower() == ".json":
            return json.loads(text)
        try:
            import yaml  # type: ignore[import-untyped]
        except ImportError:
            print(
                f"Warning: cannot load {path}: PyYAML not installed. "
                "Install it with `pip install pyyaml` or convert the file to JSON."
            )
            return None
        return yaml.safe_load(text)
    except Exception as e:
        print(f"Warning: failed to load {path}: {e}")
        return None


def _load_all(refresh: bool = False) -> dict[str, dict[str, Any]]:
    """Load every config file in references/repos/."""
    global _CACHE
    if _CACHE is not None and not refresh:
        return _CACHE
    out: dict[str, dict[str, Any]] = {}
    if _REPOS_DIR.is_dir():
        # JSON first so we can prefer it if both formats exist for a repo.
        for path in sorted(_REPOS_DIR.iterdir()):
            if path.suffix.lower() not in (".yaml", ".yml", ".json"):
                continue
            data = _load_one(path)
            if not isinstance(data, dict):
                continue
            name = data.get("name") or path.stem
            # JSON wins over YAML for the same stem.
            if name in out and path.suffix.lower() in (".yaml", ".yml"):
                continue
            out[name] = data
    _CACHE = out
    return _CACHE


# Backward-compatible attribute: existing callers and tests reference
# ``repo_config.REPO_CONFIGS``. Provide it as a module-level property-like
# dict by computing it on first access via __getattr__ below.
def __getattr__(name: str) -> Any:
    if name == "REPO_CONFIGS":
        return _load_all()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# ---------------------------------------------------------------------------
# Helper functions (public API - unchanged from previous in-code dict version)
# ---------------------------------------------------------------------------

def get_repo_config(repo_name: str) -> dict[str, Any] | None:
    """Return the full configuration dict for a repo, or None if not found."""
    return _load_all().get(repo_name)


def _path_matches_rule(doc_path: str, rule: dict[str, Any]) -> bool:
    """Check whether *doc_path* matches the rule's glob while respecting exclude_globs."""
    normalised = doc_path.replace("\\", "/")
    if not fnmatch.fnmatch(normalised, rule["glob"]):
        return False
    for exclude in rule.get("exclude_globs", []):
        if fnmatch.fnmatch(normalised, exclude):
            return False
    return True


def get_path_rules(repo_name: str, doc_path: str) -> list[dict[str, Any]]:
    """Return all path rules whose glob matches *doc_path* within the given repo.

    Rules that define ``exclude_globs`` will be skipped if *doc_path* matches
    any of the exclusion patterns. Returns an empty list when the repo is
    unknown or no rules match.
    """
    config = get_repo_config(repo_name)
    if config is None:
        return []
    return [
        rule
        for rule in config.get("path_rules", [])
        if _path_matches_rule(doc_path, rule)
    ]


def get_service_renames(repo_name: str) -> dict[str, str]:
    """Return the old-name to new-name mapping for renamed services.

    Returns an empty dict when the repo is unknown or has no renames.
    """
    config = get_repo_config(repo_name)
    if config is None:
        return {}
    return config.get("service_renames", {}) or {}


def get_nav_hints(repo_name: str, doc_path: str) -> list[str]:
    """Collect navigation hints from every matching path rule for *doc_path*.

    Hints are returned in rule-definition order and deduplicated while
    preserving that order.
    """
    seen: set[str] = set()
    hints: list[str] = []
    for rule in get_path_rules(repo_name, doc_path):
        for hint in rule.get("nav_hints", []) or []:
            if hint not in seen:
                seen.add(hint)
                hints.append(hint)
    return hints


def get_portal_hints(repo_name: str, portal: str) -> str | None:
    """Return portal-specific notes (e.g. privilege requirements), or None."""
    config = get_repo_config(repo_name)
    if config is None:
        return None
    return (config.get("portal_hints") or {}).get(portal)


def detect_repo_from_path(local_path: str) -> str | None:
    """Attempt to detect the repo name from a local filesystem path.

    Walks up the path components looking for a directory name that matches a
    known repo. Returns the repo name on the first match, or None if no match
    is found.

    This is a best-effort heuristic; it relies on the checkout directory being
    named after the repo (which is the default for ``git clone``).
    """
    normalised = os.path.normpath(local_path)
    parts = normalised.split(os.sep)
    known = _load_all()
    for part in parts:
        if part in known:
            return part
    return None


def list_known_repos() -> list[str]:
    """Return all repo names currently configured."""
    return sorted(_load_all().keys())


if __name__ == "__main__":
    print(f"Loading repo configs from: {_REPOS_DIR}")
    for name, cfg in sorted(_load_all().items()):
        n_rules = len(cfg.get("path_rules", []) or [])
        n_renames = len(cfg.get("service_renames", {}) or {})
        print(f"  - {name}: {n_rules} path rules, {n_renames} renames")
