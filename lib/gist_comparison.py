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
    pr_branch: str = "",
    pr_number: int | None = None,
    github_client_id: str = "",
    github_base_url: str = "https://github.com",
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
        github_client_id: OAuth App client ID for device flow
        github_base_url: GitHub base URL (for GHE support)

    Returns:
        The HTML string
    """
    client_id = github_client_id or os.environ.get("GITHUB_OAUTH_CLIENT_ID", "")
    gh_base = github_base_url or os.environ.get("GITHUB_BASE_URL", "https://github.com")
    pr_number_js = pr_number if pr_number else "null"

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

  .auth-section {{ text-align: center; margin: 20px 0; padding: 16px; background: #f0f6fc; border: 1px solid #d0d7de; border-radius: 6px; }}
  .auth-btn {{ background: #24292f; color: #fff; border: none; padding: 10px 24px; font-size: 14px; font-weight: 600; border-radius: 6px; cursor: pointer; display: inline-flex; align-items: center; gap: 8px; }}
  .auth-btn:hover {{ background: #32383f; }}
  .auth-btn:disabled {{ background: #999; cursor: not-allowed; }}
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

<div class="auth-section" id="auth-section">
  <div id="auth-initial">
    <p style="margin-bottom: 8px; font-weight: 600;">Sign in to GitHub to submit further feedback</p>
    <button class="auth-btn" id="auth-btn" onclick="startAuth()">
      <svg height="20" width="20" viewBox="0 0 16 16" fill="currentColor"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"></path></svg>
      Sign in with GitHub
    </button>
  </div>
  <div id="auth-pending" style="display:none;">
    <p>Enter this code on GitHub:</p>
    <div style="font-family:monospace;font-size:28px;font-weight:700;letter-spacing:4px;color:#0078d4;margin:12px 0;" id="auth-code"></div>
    <p><a id="auth-link" href="#" target="_blank">Open GitHub</a></p>
    <p id="auth-poll-status" style="color:#555;font-size:13px;">Waiting for authorization...</p>
  </div>
  <div id="auth-done" style="display:none;">
    <p style="color:#155724;">&#10003; Signed in to GitHub. Ready to submit feedback.</p>
  </div>
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
const PR_BRANCH = "{pr_branch}";
const PR_NUMBER = {pr_number_js};
const CLIENT_ID = "{client_id}";
const GH_BASE = "{gh_base}";

let ghToken = sessionStorage.getItem('gh_oauth_token') || '';
if (ghToken) {{
  document.getElementById('auth-initial').style.display = 'none';
  document.getElementById('auth-done').style.display = 'block';
}}

async function startAuth() {{
  const btn = document.getElementById('auth-btn');
  btn.disabled = true;
  try {{
    const codeResp = await fetch(`${{GH_BASE}}/login/device/code`, {{
      method: 'POST',
      headers: {{ 'Accept': 'application/json', 'Content-Type': 'application/json' }},
      body: JSON.stringify({{ client_id: CLIENT_ID, scope: 'repo' }}),
    }});
    if (!codeResp.ok) throw new Error('Failed to start device flow');
    const codeData = await codeResp.json();
    document.getElementById('auth-initial').style.display = 'none';
    document.getElementById('auth-pending').style.display = 'block';
    document.getElementById('auth-code').textContent = codeData.user_code;
    const link = document.getElementById('auth-link');
    link.href = codeData.verification_uri;
    window.open(codeData.verification_uri, '_blank');
    const interval = (codeData.interval || 5) * 1000;
    const expires = Date.now() + (codeData.expires_in || 900) * 1000;
    while (Date.now() < expires) {{
      await new Promise(r => setTimeout(r, interval));
      const tokenResp = await fetch(`${{GH_BASE}}/login/oauth/access_token`, {{
        method: 'POST',
        headers: {{ 'Accept': 'application/json', 'Content-Type': 'application/json' }},
        body: JSON.stringify({{ client_id: CLIENT_ID, device_code: codeData.device_code, grant_type: 'urn:ietf:params:oauth:grant-type:device_code' }}),
      }});
      const tokenData = await tokenResp.json();
      if (tokenData.access_token) {{
        ghToken = tokenData.access_token;
        sessionStorage.setItem('gh_oauth_token', ghToken);
        document.getElementById('auth-pending').style.display = 'none';
        document.getElementById('auth-done').style.display = 'block';
        return;
      }}
      if (tokenData.error === 'authorization_pending') continue;
      if (tokenData.error === 'slow_down') {{ await new Promise(r => setTimeout(r, 5000)); continue; }}
      throw new Error(tokenData.error_description || tokenData.error);
    }}
    throw new Error('Timed out');
  }} catch (e) {{
    document.getElementById('auth-pending').style.display = 'none';
    document.getElementById('auth-initial').style.display = 'block';
    btn.disabled = false;
    alert('Auth error: ' + e.message);
  }}
}}

async function submitIteration() {{
  const btn = document.getElementById('submit-iter');
  const status = document.getElementById('submit-status');

  if (!ghToken) {{
    status.className = 'submit-status error';
    status.textContent = 'Please sign in to GitHub first.';
    return;
  }}

  const items = [];
  document.querySelectorAll('.iter-input').forEach(ta => {{
    const text = ta.value.trim();
    if (text) {{
      items.push({{ image: ta.dataset.image, article: ta.dataset.article, suggestion: text }});
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
    const title = `Screenshot feedback (iteration on PR #${{PR_NUMBER}}): ${{items.length}} item(s)`;
    const body = [
      '## Screenshot Feedback (Iteration)',
      '',
      `Follow-up on PR #${{PR_NUMBER}} (branch: \\`${{PR_BRANCH}}\\`), originally from Issue #${{PARENT_ISSUE}}.`,
      `${{items.length}} screenshot(s) still need improvement.`,
      '',
      '### PR Context',
      '',
      '```',
      `pr_number: ${{PR_NUMBER}}`,
      `pr_branch: ${{PR_BRANCH}}`,
      `parent_issue: ${{PARENT_ISSUE}}`,
      '```',
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

    const apiUrl = GH_BASE.includes('github.com')
      ? `https://api.github.com/repos/${{REPO}}/issues`
      : `${{GH_BASE}}/api/v3/repos/${{REPO}}/issues`;

    const resp = await fetch(apiUrl, {{
      method: 'POST',
      headers: {{
        'Authorization': `token ${{ghToken}}`,
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
    pr_branch: str = "",
    pr_number: int | None = None,
) -> str:
    """Generate and publish a gist comparison page. Returns the gist URL."""
    page_html = generate_gist_comparison(
        fixes, issue_number, pr_url,
        pr_branch=pr_branch, pr_number=pr_number,
    )
    gist_url = gh.create_gist(
        filename=f"pr-review-issue-{issue_number}.html",
        content=page_html,
        description=f"Screenshot fix review for Issue #{issue_number}",
    )
    return gist_url
