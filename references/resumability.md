# Resumability and Checkpointing (Scenario 2)

Scenario 2 captures (capturing every screenshot referenced by an
article) can take many minutes. A single MFA prompt, browser crash, or
transient network failure shouldn't force you to restart from
screenshot 1.

The `lib/checkpoint.py` module persists per-article progress so the
agent can pick up where it left off.

## How it works

1. At the start of a Scenario 2 run, the caller asks
   `Checkpoint.for_article(article_path, repo=...)` for a checkpoint
   object. This loads the existing checkpoint file (if any) from
   `~/.copilot/skills/docs-screenshot/state/<article-hash>.json` or
   creates a new one.

2. Before processing each image, the caller checks
   `cp.is_complete(image_id)` and skips items that have already been
   marked done.

3. After successfully capturing + scrubbing + editing each image, the
   caller calls `cp.mark_done(image_id, notes="...")`. The file is
   re-written atomically (write-temp + rename) so a crash mid-write
   can't corrupt it.

4. On the next invocation against the same article, only the pending
   images are processed.

## State directory

By default, checkpoints live in
`~/.copilot/skills/docs-screenshot/state/`. Override with the
`DOCS_SCREENSHOT_STATE_DIR` environment variable, e.g.:

```bash
export DOCS_SCREENSHOT_STATE_DIR=~/ai-scratch/docs-screenshot/state
```

## File format

```json
{
  "article_path": "articles/key-vault/quick-create-portal.md",
  "repo_name": "azure-security-docs-pr",
  "started_at": "2025-11-20T14:23:01+00:00",
  "updated_at": "2025-11-20T14:31:45+00:00",
  "completed": {
    "create-key-vault-step-1.png": {
      "status": "done",
      "completed_at": "2025-11-20T14:24:12+00:00",
      "notes": "captured and PII-scrubbed"
    },
    "create-key-vault-step-2.png": {
      "status": "failed",
      "completed_at": "2025-11-20T14:25:03+00:00",
      "notes": "MFA prompt timed out; retry needed"
    }
  }
}
```

## Caller pattern

```python
from lib.checkpoint import Checkpoint

cp = Checkpoint.for_article(
    "articles/key-vault/quick-create-portal.md",
    repo="azure-security-docs-pr",
)

all_images = [...]   # discovered by doc_analyzer.py
pending = cp.pending_from(all_images)

for image_id in pending:
    try:
        # ...capture + scrub + edit...
        cp.mark_done(image_id, notes="captured and PII-scrubbed")
    except Exception as e:
        cp.mark_failed(image_id, reason=str(e))
        raise
```

## Inspecting checkpoints

```bash
python -m lib.checkpoint        # lists all checkpoints + counts
```

To start an article fresh, delete its checkpoint file or call
`cp.reset()` in code.

## When NOT to checkpoint

- Scenario 1 (capturing a single image) doesn't benefit — checkpointing
  one image is overhead with no upside.
- Iterative re-runs to refine callouts or test new prompts — you want
  the work to redo. Call `cp.reset()` first or delete the file.
