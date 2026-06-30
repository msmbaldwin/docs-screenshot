"""checkpoint.py - Persistent per-article progress for Scenario 2 runs.

Scenario 2 captures can take many minutes and may fail partway through
(MFA timeout, browser crash, transient network issues). Without
checkpointing, a run that fails on screenshot 15 of 20 has to start
over from scratch.

This module provides a tiny atomic JSON checkpoint keyed by a stable
hash of the article path. The agent (or any caller) records "this
image is done" after each successful capture+edit, then on resume
reads the checkpoint and skips already-completed items.

Storage layout:
    $DOCS_SCREENSHOT_STATE_DIR/  (defaults to ~/.copilot/skills/docs-screenshot/state)
        <article-hash>.json

File format (JSON):
    {
        "article_path": "articles/key-vault/quick-create-portal.md",
        "repo_name": "azure-security-docs-pr",
        "started_at": "2025-..-..T..:..:..Z",
        "updated_at": "...",
        "completed": {
            "create-key-vault-step-1.png": {
                "status": "done",
                "completed_at": "...",
                "notes": "captured and PII-scrubbed"
            }
        }
    }

Use:
    cp = Checkpoint.for_article("articles/key-vault/x.md", repo="azure-security-docs-pr")
    if cp.is_complete("create-key-vault.png"):
        continue   # already done
    ...do the work...
    cp.mark_done("create-key-vault.png", notes="captured and PII-scrubbed")
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _state_dir() -> Path:
    """Return the directory where checkpoint files live."""
    override = os.environ.get("DOCS_SCREENSHOT_STATE_DIR")
    if override:
        return Path(override).expanduser()
    # Default: relative to the skill repo if discoverable, else ~/.cache
    skill_root = Path(__file__).resolve().parent.parent
    return skill_root / "state"


def _article_hash(article_path: str) -> str:
    """Stable short hash for an article path."""
    normalized = article_path.replace("\\", "/").strip("/")
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:12]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _atomic_write(path: Path, data: str) -> None:
    """Write `data` to `path` atomically (write-temp + rename)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=str(path.parent),
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as tf:
        tf.write(data)
        tmp_name = tf.name
    os.replace(tmp_name, path)


@dataclass
class Checkpoint:
    """One checkpoint file, representing the progress of a single article."""

    article_path: str
    repo_name: str = ""
    path: Path = field(default_factory=Path)
    data: dict[str, Any] = field(default_factory=dict)

    # --- constructors ---------------------------------------------------

    @classmethod
    def for_article(
        cls,
        article_path: str,
        repo: str = "",
        state_dir: Path | None = None,
    ) -> Checkpoint:
        """Load (or create) the checkpoint for a given article path."""
        directory = state_dir or _state_dir()
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{_article_hash(article_path)}.json"
        cp = cls(article_path=article_path, repo_name=repo, path=path)
        cp._load()
        return cp

    # --- I/O ------------------------------------------------------------

    def _load(self) -> None:
        if self.path.is_file():
            try:
                self.data = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                # Corrupt checkpoint - start fresh but don't lose the file:
                # the corrupt one will be overwritten on the next save.
                self.data = {}
        if not self.data:
            self.data = {
                "article_path": self.article_path,
                "repo_name": self.repo_name,
                "started_at": _now_iso(),
                "updated_at": _now_iso(),
                "completed": {},
            }
        # Always keep these in sync with constructor args
        self.data.setdefault("completed", {})
        if self.repo_name:
            self.data["repo_name"] = self.repo_name

    def save(self) -> None:
        self.data["updated_at"] = _now_iso()
        _atomic_write(self.path, json.dumps(self.data, indent=2, sort_keys=True))

    # --- queries --------------------------------------------------------

    def is_complete(self, image_id: str) -> bool:
        entry = self.data.get("completed", {}).get(image_id)
        return bool(entry) and entry.get("status") == "done"

    def completed_ids(self) -> list[str]:
        return [
            img_id
            for img_id, entry in self.data.get("completed", {}).items()
            if entry.get("status") == "done"
        ]

    def pending_from(self, all_image_ids: list[str]) -> list[str]:
        """Return only the image_ids not yet marked done."""
        return [i for i in all_image_ids if not self.is_complete(i)]

    # --- updates --------------------------------------------------------

    def mark_done(self, image_id: str, notes: str = "") -> None:
        self.data.setdefault("completed", {})[image_id] = {
            "status": "done",
            "completed_at": _now_iso(),
            "notes": notes,
        }
        self.save()

    def mark_failed(self, image_id: str, reason: str = "") -> None:
        self.data.setdefault("completed", {})[image_id] = {
            "status": "failed",
            "completed_at": _now_iso(),
            "notes": reason,
        }
        self.save()

    def reset(self) -> None:
        """Wipe the checkpoint file so the next run starts fresh."""
        self.data = {
            "article_path": self.article_path,
            "repo_name": self.repo_name,
            "started_at": _now_iso(),
            "updated_at": _now_iso(),
            "completed": {},
        }
        if self.path.exists():
            self.path.unlink()


# ---------------------------------------------------------------------------
# Module-level convenience helpers
# ---------------------------------------------------------------------------

def list_checkpoints(state_dir: Path | None = None) -> list[dict[str, Any]]:
    """Return a summary of all checkpoint files in the state directory."""
    directory = state_dir or _state_dir()
    if not directory.is_dir():
        return []
    summaries: list[dict[str, Any]] = []
    for p in sorted(directory.glob("*.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        completed = data.get("completed", {})
        done_count = sum(1 for v in completed.values() if v.get("status") == "done")
        summaries.append({
            "path": str(p),
            "article_path": data.get("article_path", "?"),
            "repo_name": data.get("repo_name", ""),
            "updated_at": data.get("updated_at", ""),
            "done_count": done_count,
            "total_recorded": len(completed),
        })
    return summaries


if __name__ == "__main__":
    # Print a summary of all existing checkpoints
    import sys
    state = _state_dir()
    print(f"Checkpoint state directory: {state}")
    summaries = list_checkpoints()
    if not summaries:
        print("(no checkpoints found)")
        sys.exit(0)
    for s in summaries:
        print(
            f"  {s['article_path']}  "
            f"[{s['repo_name'] or 'no-repo'}]  "
            f"{s['done_count']} done  "
            f"(updated {s['updated_at']})"
        )
