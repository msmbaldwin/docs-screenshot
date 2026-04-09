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

  /* GitHub token input */
  .token-section {{ text-align: center; margin: 20px 0; padding: 16px; background: #fff8e1; border: 1px solid #ffe082; border-radius: 6px; }}
  .token-input {{ padding: 8px 12px; width: 400px; max-width: 90%; border: 1px solid #ccc; border-radius: 4px; font-family: monospace; }}

  @media (max-width: 900px) {{ .pair-container {{ grid-template-columns: 1fr; }} }}
</style>
</head>
<body>

<h1>{html.escape(title)}</h1>
<p class="subtitle">{html.escape(subtitle)}</p>

{"".join(screenshot_rows)}

<div class="token-section">
  <p style="margin-bottom: 8px; font-weight: 600;">GitHub Personal Access Token (required for submission)</p>
  <p style="margin-bottom: 8px; font-size: 13px; color: #666;">Token needs <code>repo</code> scope. It is only sent to GitHub's API, never stored.</p>
  <input type="password" class="token-input" id="gh-token" placeholder="ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx">
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

async function submitFeedback() {{
  const btn = document.getElementById('submit-feedback');
  const status = document.getElementById('submit-status');
  const token = document.getElementById('gh-token').value.trim();

  if (!token) {{
    status.className = 'submit-status error';
    status.textContent = 'Please enter a GitHub token above.';
    return;
  }}

  // Collect feedback from all textboxes
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

    const resp = await fetch(`https://api.github.com/repos/${{REPO}}/issues`, {{
      method: 'POST',
      headers: {{
        'Authorization': `token ${{token}}`,
        'Accept': 'application/vnd.github.v3+json',
        'Content-Type': 'application/json',
      }},
      body: JSON.stringify({{
        title,
        body,
        labels: [LABEL],
      }}),
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
