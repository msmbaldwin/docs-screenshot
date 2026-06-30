"""user_config.py - Per-user configuration loader.

Reads optional user-specific defaults from a config file so personal
identifiers (alias, subscription, repo locations) don't have to be
hardcoded in lib/ or passed on every invocation.

Resolution order (first match wins):
  1. $DOCS_SCREENSHOT_CONFIG
  2. ~/.config/docs-screenshot/config.yaml
  3. ~/.config/docs-screenshot/config.json
  4. (no config; defaults are returned)

YAML support is optional. If PyYAML is not installed and only a .yaml
file exists, this module falls back to JSON-only.

Example config (~/.config/docs-screenshot/config.yaml):

    username: mbaldwin
    subscription: My Subscription
    tenant_display_name: My Tenant
    repo_root: ~/docs
    custom_replacements:
      my-real-rg: contoso-rg
      MyTenantName.onmicrosoft.com: contoso.onmicrosoft.com
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


_CACHE: dict[str, Any] | None = None
_CACHE_PATH: Path | None = None


def _candidate_paths() -> list[Path]:
    """Return paths to check, in order of precedence."""
    env = os.environ.get("DOCS_SCREENSHOT_CONFIG")
    paths: list[Path] = []
    if env:
        paths.append(Path(env).expanduser())
    base = Path.home() / ".config" / "docs-screenshot"
    paths.append(base / "config.yaml")
    paths.append(base / "config.json")
    return paths


def _load_file(path: Path) -> dict[str, Any]:
    """Load a YAML or JSON config file."""
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in (".yaml", ".yml"):
        try:
            import yaml  # type: ignore[import-untyped]
        except ImportError as e:
            raise RuntimeError(
                f"Config file is YAML ({path}) but PyYAML is not installed. "
                "Install it with `pip install pyyaml` or use a .json config instead."
            ) from e
        return yaml.safe_load(text) or {}
    return json.loads(text)


def load(refresh: bool = False) -> dict[str, Any]:
    """Load the user config (cached). Returns {} if no config file exists."""
    global _CACHE, _CACHE_PATH
    if _CACHE is not None and not refresh:
        return _CACHE
    for path in _candidate_paths():
        if path.is_file():
            try:
                _CACHE = _load_file(path)
            except Exception as e:
                print(f"Warning: failed to load {path}: {e}")
                _CACHE = {}
            _CACHE_PATH = path
            return _CACHE
    _CACHE = {}
    _CACHE_PATH = None
    return _CACHE


def get(key: str, default: Any = None) -> Any:
    """Get a config value, or `default` if not set."""
    return load().get(key, default)


def source_path() -> Path | None:
    """Return the path the config was loaded from, or None."""
    load()
    return _CACHE_PATH


def username(fallback: str | None = None) -> str | None:
    """Return the configured username, or fallback."""
    val = get("username")
    if val:
        return str(val)
    if fallback is not None:
        return fallback
    return os.environ.get("USER") or os.environ.get("USERNAME")


def subscription(fallback: str | None = None) -> str | None:
    """Return the configured subscription display name, or fallback."""
    return get("subscription", fallback)


def tenant_display_name(fallback: str | None = None) -> str | None:
    """Return the configured tenant display name, or fallback."""
    return get("tenant_display_name", fallback)


def repo_root(fallback: str | None = None) -> str | None:
    """Return the configured repo root, with ~ expanded."""
    val = get("repo_root", fallback)
    if val:
        return os.path.expanduser(str(val))
    return None


def custom_replacements() -> dict[str, str]:
    """Return any user-defined PII custom_replacements."""
    val = get("custom_replacements", {})
    if not isinstance(val, dict):
        return {}
    return {str(k): str(v) for k, v in val.items()}


if __name__ == "__main__":
    cfg = load()
    src = source_path()
    if src is None:
        print("No user config found. Searched:")
        for p in _candidate_paths():
            print(f"  - {p}")
    else:
        print(f"Loaded user config from: {src}")
        print(f"  username: {username()!r}")
        print(f"  subscription: {subscription()!r}")
        print(f"  tenant_display_name: {tenant_display_name()!r}")
        print(f"  repo_root: {repo_root()!r}")
        print(f"  custom_replacements: {len(custom_replacements())} entries")
