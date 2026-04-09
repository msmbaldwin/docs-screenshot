"""
Gist-hosted comparison page generator.

Creates a self-contained HTML page showing before/after screenshots for a PR,
with feedback textboxes and a Submit button that creates a new GitHub issue,
enabling iterative refinement of the screenshot skill.
"""

from __future__ import annotations

import base64
import html
import json
import os
from pathlib import Path
from typing import Any

from . import github_integration as gh


GITHUB_REPO = os.environ.get("SCREENSHOT_REPO", "jonburchel/docs-screenshot")
FEEDBACK_LABEL = "screenshot-feedback"


def _encode_image(path: str) -> str:
    """Read an image file and return its base64 encoding."""
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


def generate_gist_comparison(
    fixes: list[dict],
    issue_number: int,
    pr_url: str = "",
) -> str:
    """
    Generate a self-contained HTML comparison page for a PR.

    Args:
        fixes: List of dicts with keys:
            - image: str (filename)
            - article: str (article name)
            - suggestion: str (original feedback)
            - before_path: str (path to before image)
            - after_path: str (path to after image)
            - changes_made: str (description of skill changes)
        issue_number: The GitHub issue this addresses
        pr_url: URL of the PR

    Returns:
        The HTML string
    """
    fix_rows = []
    for i, fix in enumerate(fixes):
        before_src = f"data:image/png;base64,{_encode_image(fix['before_path'])}" if os.path.exists(fix.get("before_path", "")) else ""
        after_src = f"data:image/png;base64,{_encode_image(fix['after_path'])}" if os.path.exists(fix.get("after_path", "")) else ""

        name = html.escape(fix.get("image", f"screenshot-{i+1}"))
        article = html.escape(fix.get("article", ""))
        suggestion = html.escape(fix.get("suggestion", ""))
        changes = html.escape(fix.get("changes_made", ""))

        before_img = f'<img src="{before_src}" alt="Before: {name}">' if before_src else '<p style="color:#999;">Before image not available</p>'
        after_img = f'<img src="{after_src}" alt="After: {name}">' if after_src else '<p style="color:#999;">After image not available</p>'

        fix_rows.append(f"""
    <div class="fix-card" data-image="{name}" data-article="{article}">
      <div class="fix-header">
        <span class="fix-number">#{i+1}</span>
        <code>{name}</code>
        {f'<span class="fix-article">{article}</span>' if article else ''}
      </div>
      <div class="fix-feedback">
        <strong>Original feedback:</strong> {suggestion}
      </div>
      <div class="fix-changes">
        <strong>Changes made:</strong> {changes}
      </div>
      <div class="pair-container">
        <div class="pair-side">
          <div class="pair-label before-label">Before Fix</div><br>
          {before_img}
        </div>
        <div class="pair-side">
          <div class="pair-label after-label">After Fix</div><br>
          {after_img}
        </div>
      </div>
      <div class="iteration-section">
        <label class="iter-label">Still not right? Describe what needs further fixing:</label>
        <textarea class="iter-input" data-image="{name}" data-article="{article}"
                  placeholder="Leave blank if this fix looks good..."
                  rows="2"></textarea>
      </div>
    </div>""")

    page_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>PR Review: Screenshot Fixes (Issue #{issue_number})</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f5f5f5; color: #333; padding: 24px; max-width: 1400px; margin: 0 auto; }}
  h1 {{ text-align: center; margin-bottom: 8px; color: #0078d4; }}
  .subtitle {{ text-align: center; color: #666; margin-bottom: 32px; font-size: 14px; }}
  .subtitle a {{ color: #0078d4; }}

  .fix-card {{ background: #fff; border: 1px solid #ddd; border-radius: 6px; padding: 20px; margin-bottom: 32px; }}
  .fix-header {{ font-size: 16px; font-weight: 600; margin-bottom: 8px; }}
  .fix-number {{ background: #0078d4; color: #fff; padding: 2px 8px; border-radius: 3px; margin-right: 8px; font-size: 13px; }}
  .fix-article {{ color: #888; font-size: 13px; margin-left: 12px; }}
  .fix-feedback {{ font-size: 13px; color: #555; margin-bottom: 4px; padding: 8px; background: #fff3cd; border-radius: 4px; }}
  .fix-changes {{ font-size: 13px; color: #155724; margin-bottom: 12px; padding: 8px; background: #d4edda; border-radius: 4px; }}

  .pair-container {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 12px; }}
  .pair-side {{ text-align: center; }}
  .pair-label {{ font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 1px; padding: 4px 12px; border-radius: 3px; display: inline-block; }}
  .before-label {{ background: #f8d7da; color: #721c24; }}
  .after-label {{ background: #d4edda; color: #155724; }}
  .pair-side img {{ max-width: 100%; height: auto; border: 1px solid #ccc; border-radius: 3px; }}

  .iteration-section {{ margin-top: 12px; padding-top: 12px; border-top: 1px dashed #ddd; }}
  .iter-label {{ font-size: 13px; color: #555; font-weight: 600; display: block; margin-bottom: 4px; }}
  .iter-input {{ width: 100%; padding: 8px 10px; border: 1px solid #ccc; border-radius: 4px; font-family: inherit; font-size: 13px; resize: vertical; }}
  .iter-input:focus {{ border-color: #0078d4; outline: none; box-shadow: 0 0 0 2px rgba(0,120,212,0.2); }}

  .submit-section {{ text-align: center; margin: 40px 0; }}
  .submit-btn {{ background: #d83b01; color: #fff; border: none; padding: 14px 40px; font-size: 16px; font-weight: 600; border-radius: 6px; cursor: pointer; }}
  .submit-btn:hover {{ background: #c23200; }}
  .submit-btn:disabled {{ background: #999; cursor: not-allowed; }}
  .submit-status {{ margin-top: 12px; font-size: 14px; }}
  .submit-status.success {{ color: #155724; }}
  .submit-status.error {{ color: #721c24; }}

  .token-section {{ text-align: center; margin: 20px 0; padding: 16px; background: #fff8e1; border: 1px solid #ffe082; border-radius: 6px; }}
  .token-input {{ padding: 8px 12px; width: 400px; max-width: 90%; border: 1px solid #ccc; border-radius: 4px; font-family: monospace; }}

  @media (max-width: 900px) {{ .pair-container {{ grid-template-columns: 1fr; }} }}
</style>
</head>
<body>

<h1>PR Review: Screenshot Fixes</h1>
<p class="subtitle">
  Addressing <a href="https://github.com/{GITHUB_REPO}/issues/{issue_number}" target="_blank">Issue #{issue_number}</a>
  {f' | <a href="{pr_url}" target="_blank">View PR</a>' if pr_url else ''}
  | Submit further feedback below to continue iterating
</p>

{"".join(fix_rows)}

<div class="token-section">
  <p style="margin-bottom: 8px; font-weight: 600;">GitHub Token (required for submitting further feedback)</p>
  <input type="password" class="token-input" id="gh-token" placeholder="ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx">
</div>

<div class="submit-section">
  <button class="submit-btn" id="submit-iter" onclick="submitIteration()">
    Submit Further Feedback (New Issue)
  </button>
  <div class="submit-status" id="submit-status"></div>
</div>

<script>
const REPO = "{GITHUB_REPO}";
const LABEL = "{FEEDBACK_LABEL}";
const PARENT_ISSUE = {issue_number};

async function submitIteration() {{
  const btn = document.getElementById('submit-iter');
  const status = document.getElementById('submit-status');
  const token = document.getElementById('gh-token').value.trim();

  if (!token) {{
    status.className = 'submit-status error';
    status.textContent = 'Please enter a GitHub token.';
    return;
  }}

  const items = [];
  document.querySelectorAll('.iter-input').forEach(ta => {{
    const text = ta.value.trim();
    if (text) {{
      items.push({{
        image: ta.dataset.image,
        article: ta.dataset.article,
        suggestion: text,
      }});
    }}
  }});

  if (items.length === 0) {{
    status.className = 'submit-status error';
    status.textContent = 'No further feedback entered.';
    return;
  }}

  btn.disabled = true;
  status.textContent = 'Submitting...';

  try {{
    const title = `Screenshot feedback (iteration from #${{PARENT_ISSUE}}): ${{items.length}} item(s)`;
    const body = [
      '## Screenshot Feedback (Iteration)',
      '',
      `Follow-up from Issue #${{PARENT_ISSUE}}. ${{items.length}} screenshot(s) still need improvement.`,
      '',
      '### Issues',
      '',
      ...items.map((item, i) => [
        `#### ${{i+1}}. \\`${{item.image}}\\``,
        item.article ? `Article: \\`${{item.article}}\\`` : '',
        `**Problem:** ${{item.suggestion}}`,
        '',
      ].filter(Boolean).join('\\n')),
      '',
      '### Structured Data',
      '',
      '```json',
      JSON.stringify(items, null, 2),
      '```',
    ].join('\\n');

    const resp = await fetch(`https://api.github.com/repos/${{REPO}}/issues`, {{
      method: 'POST',
      headers: {{
        'Authorization': `token ${{token}}`,
        'Accept': 'application/vnd.github.v3+json',
        'Content-Type': 'application/json',
      }},
      body: JSON.stringify({{ title, body, labels: [LABEL] }}),
    }});

    if (!resp.ok) throw new Error((await resp.json()).message || `HTTP ${{resp.status}}`);

    const issue = await resp.json();
    status.className = 'submit-status success';
    status.innerHTML = `Submitted as <a href="${{issue.html_url}}" target="_blank">Issue #${{issue.number}}</a>. The feedback service will pick this up automatically.`;
  }} catch (e) {{
    status.className = 'submit-status error';
    status.textContent = `Error: ${{e.message}}`;
    btn.disabled = false;
  }}
}}
</script>

</body>
</html>"""

    return page_html


def publish_gist_comparison(
    fixes: list[dict],
    issue_number: int,
    pr_url: str = "",
) -> str:
    """Generate and publish a gist comparison page. Returns the gist URL."""
    page_html = generate_gist_comparison(fixes, issue_number, pr_url)
    gist_url = gh.create_gist(
        filename=f"pr-review-issue-{issue_number}.html",
        content=page_html,
        description=f"Screenshot fix review for Issue #{issue_number}",
    )
    return gist_url
