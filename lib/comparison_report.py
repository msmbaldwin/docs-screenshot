"""
Comparison report generator with feedback UI.

Generates self-contained HTML comparison reports that show before/after
screenshot pairs with per-image feedback textboxes and a Submit button
that creates a GitHub issue via the GitHub API.
"""

from __future__ import annotations

import base64
import html
import json
import os
from pathlib import Path
from typing import Any


GITHUB_REPO = os.environ.get("SCREENSHOT_REPO", "jonburchel/docs-screenshot")
FEEDBACK_LABEL = "screenshot-feedback"


def _encode_image(path: str) -> str:
    """Read an image file and return its base64 encoding."""
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


def generate_comparison_report(
    pairs: list[dict],
    title: str = "Screenshot Comparison",
    subtitle: str = "",
    output_path: str | None = None,
    embed_images: bool = True,
    github_client_id: str = "",
    github_base_url: str = "https://github.com",
) -> str:
    """
    Generate a comparison report HTML with feedback UI.

    Args:
        pairs: List of dicts with keys:
            - name: str (image filename)
            - alt: str (alt text / description)
            - article: str (article name / path)
            - article_group: str (article display name)
            - left_path: str (path to left/original image)
            - left_label: str (label for left column)
            - right_path: str (path to right/recaptured image)
            - right_label: str (label for right column)
            - callout_note: str | None (callout description)
        title: Report title
        subtitle: Report subtitle
        output_path: If provided, write HTML to this file
        embed_images: If True, embed images as base64

    Returns:
        The HTML string
    """
    # Resolve OAuth config
    client_id = github_client_id or os.environ.get("GITHUB_OAUTH_CLIENT_ID", "")
    gh_base = github_base_url or os.environ.get("GITHUB_BASE_URL", "https://github.com")

    # Embed skill version so the service can check staleness
    from . import github_integration as _gh_mod
    skill_version = _gh_mod.get_skill_version()

    articles: dict[str, list[dict]] = {}
    for p in pairs:
        group = p.get("article_group", "Ungrouped")
        articles.setdefault(group, []).append(p)

    screenshot_rows = []
    for group_name, group_pairs in articles.items():
        rows = []
        for p in group_pairs:
            left_src = f"data:image/png;base64,{_encode_image(p['left_path'])}" if embed_images else p["left_path"]
            right_src = f"data:image/png;base64,{_encode_image(p['right_path'])}" if embed_images else p["right_path"]

            callout_html = ""
            if p.get("callout_note"):
                callout_html = f'<div class="callout-note">&#9632; {html.escape(p["callout_note"])}</div>'

            name_escaped = html.escape(p["name"])
            alt_escaped = html.escape(p.get("alt", ""))
            left_label = html.escape(p.get("left_label", "Before"))
            right_label = html.escape(p.get("right_label", "After"))

            # Small images (icons) get pixelated rendering
            img_style = ""
            if p.get("small"):
                img_style = ' style="image-rendering: pixelated; width: 60px;"'

            rows.append(f"""
    <div class="screenshot-pair" data-image="{name_escaped}" data-article="{html.escape(p.get('article', ''))}">
      <div class="screenshot-name">{name_escaped}</div>
      <div class="screenshot-alt">{alt_escaped}</div>
      <div class="pair-container">
        <div class="pair-side">
          <div class="pair-label left-label">{left_label}</div><br>
          <img src="{left_src}" alt="{left_label}: {name_escaped}"{img_style}>
          {callout_html}
        </div>
        <div class="pair-side">
          <div class="pair-label right-label">{right_label}</div><br>
          <img src="{right_src}" alt="{right_label}: {name_escaped}"{img_style}>
        </div>
      </div>
      <div class="feedback-section">
        <label class="feedback-label" for="fb-{name_escaped}">Feedback for <code>{name_escaped}</code>:</label>
        <textarea class="feedback-input" id="fb-{name_escaped}" data-image="{name_escaped}"
                  placeholder="Describe what's wrong with this screenshot (leave blank if it looks good)..."
                  rows="2"></textarea>
      </div>
    </div>""")

        screenshot_rows.append(f"""
<div class="article">
  <div class="article-header">{html.escape(group_name)}</div>
  <div class="article-body">
    {"".join(rows)}
  </div>
</div>""")

    report_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html.escape(title)}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f5f5f5; color: #333; padding: 24px; }}
  h1 {{ text-align: center; margin-bottom: 8px; color: #0078d4; }}
  .subtitle {{ text-align: center; color: #666; margin-bottom: 32px; font-size: 14px; }}
  .article {{ margin-bottom: 48px; }}
  .article-header {{ background: #0078d4; color: #fff; padding: 12px 20px; border-radius: 6px 6px 0 0; font-size: 18px; font-weight: 600; }}
  .article-body {{ background: #fff; border: 1px solid #ddd; border-top: none; border-radius: 0 0 6px 6px; padding: 20px; }}
  .screenshot-pair {{ margin-bottom: 32px; padding-bottom: 32px; border-bottom: 1px solid #eee; }}
  .screenshot-pair:last-child {{ margin-bottom: 0; padding-bottom: 0; border-bottom: none; }}
  .screenshot-name {{ font-weight: 600; font-size: 14px; color: #444; margin-bottom: 4px; font-family: 'Cascadia Code', 'Consolas', monospace; }}
  .screenshot-alt {{ font-size: 13px; color: #888; margin-bottom: 12px; font-style: italic; }}
  .pair-container {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
  .pair-side {{ text-align: center; }}
  .pair-label {{ font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px; padding: 4px 12px; border-radius: 3px; display: inline-block; }}
  .left-label {{ background: #d4edda; color: #155724; }}
  .right-label {{ background: #cce5ff; color: #004085; }}
  .pair-side img {{ max-width: 100%; height: auto; border: 1px solid #ccc; border-radius: 3px; background: #fff; }}
  .callout-note {{ font-size: 12px; color: #e91e1e; margin-top: 4px; }}
  .stats {{ text-align: center; margin-bottom: 24px; font-size: 13px; color: #666; }}
  .stats span {{ background: #e8f4fd; padding: 4px 10px; border-radius: 12px; margin: 0 4px; }}

  /* Feedback UI */
  .feedback-section {{ margin-top: 12px; padding-top: 12px; border-top: 1px dashed #ddd; }}
  .feedback-label {{ font-size: 13px; color: #555; font-weight: 600; display: block; margin-bottom: 4px; }}
  .feedback-input {{ width: 100%; padding: 8px 10px; border: 1px solid #ccc; border-radius: 4px; font-family: inherit; font-size: 13px; resize: vertical; }}
  .feedback-input:focus {{ border-color: #0078d4; outline: none; box-shadow: 0 0 0 2px rgba(0,120,212,0.2); }}

  .submit-section {{ text-align: center; margin: 40px 0; }}
  .submit-btn {{ background: #0078d4; color: #fff; border: none; padding: 14px 40px; font-size: 16px; font-weight: 600; border-radius: 6px; cursor: pointer; }}
  .submit-btn:hover {{ background: #106ebe; }}
  .submit-btn:disabled {{ background: #999; cursor: not-allowed; }}
  .submit-status {{ margin-top: 12px; font-size: 14px; }}
  .submit-status.success {{ color: #155724; }}
  .submit-status.error {{ color: #721c24; }}

  /* GitHub auth */
  .auth-section {{ text-align: center; margin: 20px 0; padding: 16px; background: #f0f6fc; border: 1px solid #d0d7de; border-radius: 6px; }}
  .auth-btn {{ background: #24292f; color: #fff; border: none; padding: 10px 24px; font-size: 14px; font-weight: 600; border-radius: 6px; cursor: pointer; display: inline-flex; align-items: center; gap: 8px; }}
  .auth-btn:hover {{ background: #32383f; }}
  .auth-btn:disabled {{ background: #999; cursor: not-allowed; }}
  .auth-status {{ margin-top: 8px; font-size: 13px; color: #555; }}
  .auth-status.authed {{ color: #155724; }}
  .auth-code-display {{ font-family: monospace; font-size: 28px; font-weight: 700; letter-spacing: 4px; color: #0078d4; margin: 12px 0; }}

  @media (max-width: 900px) {{ .pair-container {{ grid-template-columns: 1fr; }} }}
</style>
</head>
<body>

<h1>{html.escape(title)}</h1>
<p class="subtitle">{html.escape(subtitle)}</p>

{"".join(screenshot_rows)}

<div class="auth-section" id="auth-section">
  <div id="auth-initial">
    <p style="margin-bottom: 8px; font-weight: 600;">Sign in to GitHub to submit feedback</p>
    <button class="auth-btn" id="auth-btn" onclick="startAuth()">
      <svg height="20" width="20" viewBox="0 0 16 16" fill="currentColor"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"></path></svg>
      Sign in with GitHub
    </button>
    <p style="margin-top: 8px; font-size: 12px; color: #888;">Uses GitHub's secure device flow. No passwords or tokens needed.</p>
  </div>
  <div id="auth-pending" style="display:none;">
    <p style="margin-bottom: 4px;">Enter this code on GitHub:</p>
    <div class="auth-code-display" id="auth-code"></div>
    <p><a id="auth-link" href="#" target="_blank" style="font-size: 14px;">Click here to open GitHub</a></p>
    <p class="auth-status" id="auth-poll-status">Waiting for authorization...</p>
  </div>
  <div id="auth-done" style="display:none;">
    <p class="auth-status authed">&#10003; Signed in to GitHub. Ready to submit feedback.</p>
  </div>
</div>

<div class="submit-section">
  <button class="submit-btn" id="submit-feedback" onclick="submitFeedback()">
    Submit Feedback as GitHub Issue
  </button>
  <div class="submit-status" id="submit-status"></div>
</div>

<script>
const REPO = "{GITHUB_REPO}";
const LABEL = "{FEEDBACK_LABEL}";
const SKILL_VERSION = "{skill_version}";
// OAuth App client ID. Register at https://github.com/settings/applications/new
// or set via environment when generating the report.
const CLIENT_ID = "{client_id}";
const GH_BASE = "{gh_base}";  // e.g. https://github.com or GHE URL

let ghToken = sessionStorage.getItem('gh_oauth_token') || '';

// Show correct auth state on load
if (ghToken) {{
  document.getElementById('auth-initial').style.display = 'none';
  document.getElementById('auth-done').style.display = 'block';
}}

async function startAuth() {{
  const btn = document.getElementById('auth-btn');
  btn.disabled = true;

  try {{
    // Step 1: Request device code
    const codeResp = await fetch(`${{GH_BASE}}/login/device/code`, {{
      method: 'POST',
      headers: {{ 'Accept': 'application/json', 'Content-Type': 'application/json' }},
      body: JSON.stringify({{ client_id: CLIENT_ID, scope: 'repo' }}),
    }});
    if (!codeResp.ok) throw new Error('Failed to start device flow. Is the OAuth App Client ID configured?');
    const codeData = await codeResp.json();

    // Step 2: Show the user code
    document.getElementById('auth-initial').style.display = 'none';
    document.getElementById('auth-pending').style.display = 'block';
    document.getElementById('auth-code').textContent = codeData.user_code;
    const link = document.getElementById('auth-link');
    link.href = codeData.verification_uri;
    link.textContent = codeData.verification_uri;
    window.open(codeData.verification_uri, '_blank');

    // Step 3: Poll for token
    const interval = (codeData.interval || 5) * 1000;
    const expires = Date.now() + (codeData.expires_in || 900) * 1000;

    while (Date.now() < expires) {{
      await new Promise(r => setTimeout(r, interval));
      const tokenResp = await fetch(`${{GH_BASE}}/login/oauth/access_token`, {{
        method: 'POST',
        headers: {{ 'Accept': 'application/json', 'Content-Type': 'application/json' }},
        body: JSON.stringify({{
          client_id: CLIENT_ID,
          device_code: codeData.device_code,
          grant_type: 'urn:ietf:params:oauth:grant-type:device_code',
        }}),
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
      throw new Error(tokenData.error_description || tokenData.error || 'Auth failed');
    }}
    throw new Error('Authorization timed out. Please try again.');
  }} catch (e) {{
    document.getElementById('auth-pending').style.display = 'none';
    document.getElementById('auth-initial').style.display = 'block';
    btn.disabled = false;
    alert('Auth error: ' + e.message);
  }}
}}

async function submitFeedback() {{
  const btn = document.getElementById('submit-feedback');
  const status = document.getElementById('submit-status');

  if (!ghToken) {{
    status.className = 'submit-status error';
    status.textContent = 'Please sign in to GitHub first.';
    return;
  }}

  const feedbackItems = [];
  document.querySelectorAll('.feedback-input').forEach(ta => {{
    const text = ta.value.trim();
    if (text) {{
      const pair = ta.closest('.screenshot-pair');
      feedbackItems.push({{
        image: pair.dataset.image,
        article: pair.dataset.article,
        suggestion: text,
      }});
    }}
  }});

  if (feedbackItems.length === 0) {{
    status.className = 'submit-status error';
    status.textContent = 'No feedback entered. Please add suggestions to at least one screenshot.';
    return;
  }}

  btn.disabled = true;
  status.className = 'submit-status';
  status.textContent = 'Submitting...';

  try {{
    const title = `Screenshot feedback: ${{feedbackItems.length}} item(s)`;
    const body = [
      '## Screenshot Feedback',
      '',
      `Submitted from comparison report. ${{feedbackItems.length}} screenshot(s) flagged for improvement.`,
      '',
      '### Skill Version',
      '',
      '```',
      `skill_version: ${{SKILL_VERSION}}`,
      '```',
      '',
      '### Issues',
      '',
      ...feedbackItems.map((item, i) => [
        `#### ${{i+1}}. \\`${{item.image}}\\``,
        item.article ? `Article: \\`${{item.article}}\\`` : '',
        `**Problem:** ${{item.suggestion}}`,
        '',
      ].filter(Boolean).join('\\n')),
      '',
      '### Structured Data',
      '',
      '```json',
      JSON.stringify(feedbackItems, null, 2),
      '```',
    ].join('\\n');

    const apiBase = GH_BASE.replace('github.com', 'api.github.com');
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

    if (!resp.ok) {{
      const err = await resp.json();
      throw new Error(err.message || `HTTP ${{resp.status}}`);
    }}

    const issue = await resp.json();
    status.className = 'submit-status success';
    status.innerHTML = `Feedback submitted as <a href="${{issue.html_url}}" target="_blank">Issue #${{issue.number}}</a>`;
  }} catch (e) {{
    status.className = 'submit-status error';
    status.textContent = `Error: ${{e.message}}`;
    btn.disabled = false;
  }}
}}
</script>

</body>
</html>"""

    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(report_html)

    return report_html


def generate_and_publish(
    pairs: list[dict],
    title: str = "Screenshot Comparison",
    subtitle: str = "",
    output_path: str | None = None,
    embed_images: bool = True,
    github_client_id: str = "",
    github_base_url: str = "https://github.com",
    public_gist: bool = True,
) -> tuple[str, str]:
    """
    Generate a comparison report and publish it as a GitHub Gist.

    This is the standard entry point for comparison workflows. It produces
    a self-contained HTML file, saves it locally (if output_path given),
    and uploads it as a gist viewable via htmlpreview.github.io.

    Returns:
        (gist_url, preview_url) tuple
    """
    from . import github_integration as gh

    report_html = generate_comparison_report(
        pairs=pairs,
        title=title,
        subtitle=subtitle,
        output_path=output_path,
        embed_images=embed_images,
        github_client_id=github_client_id,
        github_base_url=github_base_url,
    )

    # Derive a filename from the title
    safe_name = "".join(c if c.isalnum() or c in "-_ " else "" for c in title)
    safe_name = safe_name.strip().replace(" ", "-").lower()[:60] or "comparison"
    filename = f"{safe_name}.html"

    gist_url = gh.create_gist(
        filename=filename,
        content=report_html,
        description=title,
        public=public_gist,
    )

    # Build the htmlpreview URL for direct browser viewing
    # Gist URL format: https://gist.github.com/USER/HASH
    # Raw URL: https://gist.github.com/USER/HASH/raw/FILENAME
    preview_url = ""
    if gist_url and "gist.github.com" in gist_url:
        raw_url = f"{gist_url}/raw/{filename}"
        preview_url = f"https://htmlpreview.github.io/?{raw_url}"

    return gist_url, preview_url
