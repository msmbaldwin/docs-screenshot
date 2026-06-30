# Lib Module Reference

_Reference for the docs-screenshot skill. See [`SKILL.md`](../SKILL.md) for the trigger-time prompt and high-level usage._


All Python modules are at `lib/` (relative to the skill root):

- **`screenshot_processor.py`**: Main orchestrator. CLI interface for full pipeline.
- **`pii_detector.py`**: Regex-based PII detection with context-aware GUID classification. All approved replacement values built in.
- **`image_editor.py`**: Pillow/OpenCV operations: crop, redact, callout, border, optimize.
- **`dom_scrubber.py`**: Frame-aware DOM PII replacement. Generates JS that uses `page.frames()` to scrub ALL frames including cross-origin Azure portal iframes. **This is the preferred pre-screenshot approach.**
- **`gimp_bridge.py`**: GIMP integration (detect running instance, open images).
- **`extract_dom_info.js`**: JavaScript payload for `playwright-cli run-code` DOM extraction (Shadow DOM aware).
- **`comparison_report.py`**: Generates comparison HTML with interactive feedback UI. In `compare` mode, posts corrections to a local HTTP server for iterative review.
- **`local_server.py`**: Lightweight HTTP server for the interactive comparison workflow. Serves reports, accepts feedback submissions, and coordinates PR creation.
- **`github_integration.py`**: GitHub API helpers (PRs, branches, gists via `gh` CLI). Includes `create_comparison_pr()` for building PRs with before/after images.
- **`repo_config.py`**: Repo-specific customization system. Embeds knowledge about supported repos (path rules, service renames, nav hints, portal privilege notes). Use `detect_repo_from_path()` to auto-detect the repo and `get_path_rules()` for doc-specific behavior.
- **`doc_analyzer.py`**: Doc-driven interaction analyzer. Parses markdown to extract image references, interaction steps, flyout requirements, and data requirements. Used in Phase 2.5 to understand what each screenshot should show.
- **`page_change_analyzer.py`**: Detects significant page changes by comparing titles, service names, and layout. Flags cases where docs need updating beyond screenshot replacement.
- **`failure_analyzer.py`**: Classifies capture failures into actionable categories (`PRIVILEGE_FAILURE`, `PII_LEAK`, `NAVIGATION_FAILURE`, etc.) with severity, explanation, and recommendation. Generates HTML badges for the comparison report.
- **`post_process.py`**: Standalone post-capture CLI for image post-processing without the full screenshot pipeline. Applies callout boxes (with optional numbered circles), gray border, and PNG optimization. Useful for re-processing existing screenshots: `python lib/post_process.py input.png output.png --callouts '[{"number":1,"box":{"x":50,"y":50,"width":100,"height":40}}]'`
