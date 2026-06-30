# AGENTS.md — docs-screenshot

Guidance for AI agents working on this skill.

## What this repo is

A GitHub Copilot CLI skill that automates the full Microsoft Learn screenshot pipeline: browser automation against Microsoft web portals (Azure, M365, Entra, etc.), PII scrubbing in the live DOM, callout-box drawing, smart cropping, and GIMP handoff.

It is installed under `~/.copilot/skills/docs-screenshot/` (junction on Windows, symlink on WSL/Linux).

## File layout

| Path | Purpose |
|------|---------|
| `SKILL.md` | Trigger-time prompt loaded by Copilot CLI when the skill activates. Keep slim (< ~300 lines). |
| `references/*.md` | Deep-dive reference material. The model should only load these when relevant to the current task. |
| `lib/*.py` | Python pipeline modules. Imported by Copilot when running phases. |
| `lib/callout_finder.js`, `lib/extract_dom_info.js` | JavaScript payloads executed via `playwright-cli run-code`. |
| `run_compare_server.py` | Standalone launcher for the interactive comparison report HTTP server. |
| `test-comparison/*.py` | Test harness for batch-capture and v7 comparison-report builds. Generated PNGs/HTML/JSON are gitignored. |
| `README.md` | Public-facing README (user-oriented, not loaded at skill trigger time). |

## Conventions

- **Slim SKILL.md, deep references/.** Whenever you add documentation, ask whether it's trigger-time content (essential for routing the request) or reference content (only needed mid-task). Put references in `references/` and link to them from `SKILL.md`'s "Detailed References" table.
- **No author identifiers.** Defaults in `lib/` and examples in markdown must use neutral placeholders (`myalias`, `My Subscription`, `~/docs/<repo>`). The skill is portable across users.
- **Cross-platform.** Code in `lib/` must work on Windows, WSL2, and native Linux. Tool discovery patterns: `shutil.which()` for executables on PATH, `platform.system()` / `_is_wsl()` for OS branching. Avoid hardcoded `C:\` or `F:\` paths.
- **Co-authored-by trailer.** Any commit or PR created by the skill (or by an agent working on the skill) must include `Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>`. The `lib/github_integration._ensure_copilot_trailer()` helper centralizes this.
- **Headless-by-default browser automation.** Visible browser only for MFA. Never start a Playwright session in headed mode for routine captures.
- **Approved fictitious values.** All PII replacements must come from Microsoft's [Sensitive Identifier Reference](https://learn.microsoft.com/en-us/help/platform/reference-sensitive-identifier). The tables in `references/pii-replacements.md` are the source of truth.

## "Where do I find X?"

| Looking for | Look in |
|---|---|
| Regex patterns for PII detection | `lib/pii_detector.py` |
| Approved replacement values (GUIDs, names, IPs) | `lib/pii_detector.py` + `references/pii-replacements.md` |
| Callout-box drawing, cropping, border, PNG optimization | `lib/image_editor.py` |
| Callout finder (JS, runs in the browser) | `lib/callout_finder.js` |
| DOM scrubber (frame-aware PII replacement) | `lib/dom_scrubber.py` |
| GIMP detection and launch (cross-platform) | `lib/gimp_bridge.py` |
| Markdown article parsing & interaction extraction | `lib/doc_analyzer.py` |
| Failure classification logic | `lib/failure_analyzer.py` |
| Repo-specific navigation/validation rules | `lib/repo_config.py` |
| Comparison report (HTML, feedback server) | `lib/comparison_report.py` + `lib/local_server.py` |
| Resource provisioning examples | `references/phase-guide.md` (Phase 3) |
| Popup dismissal selectors | `references/portal-patterns.md` |
| Capture failure categories and badges | `references/failure-categories.md` |

## When editing this skill

1. If you change `lib/*.py`, run a quick import smoke test:
   ```bash
   python -c "import sys; sys.path.insert(0, 'lib'); \
     import screenshot_processor, pii_detector, image_editor, gimp_bridge, \
       doc_analyzer, dom_scrubber, repo_config, failure_analyzer, \
       page_change_analyzer, comparison_report, local_server, \
       github_integration, post_process; print('OK')"
   ```
2. If you change `SKILL.md` structure, check internal anchor links still resolve.
3. If you change the `references/` paths, verify the pointer table in `SKILL.md` still points to existing files.
4. Don't commit generated artifacts under `test-comparison/captured*/`, `originals/`, or `comparison-report*.html` — `.gitignore` excludes them.
