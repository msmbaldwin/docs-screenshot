"""
Comparison report generator with interactive local feedback UI.

Generates self-contained HTML comparison reports that show before/after
screenshot pairs with per-image feedback textboxes. The Submit button
posts corrections to a local HTTP server (lib/local_server.py) for
processing. When all screenshots are approved (no corrections), the
final submit creates a PR with before/after comparison images.
"""

from __future__ import annotations

import base64
import html
import json
import os
from pathlib import Path
from typing import Any


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
    server_port: int = 0,
    iteration: int = 0,
) -> str:
    """
    Generate a comparison report HTML with local feedback UI.

    The report posts feedback to a local HTTP server instead of creating
    GitHub issues. When all feedback textboxes are empty, the submit
    creates a PR directly.

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
        server_port: Port of the local compare server (0 = no server, static report)
        iteration: Current iteration number (0 = first pass)

    Returns:
        The HTML string
    """
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

    # Determine if local server is available for interactive mode
    interactive = server_port > 0
    iteration_note = f" (Iteration {iteration})" if iteration > 0 else ""

    report_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html.escape(title)}{iteration_note}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f5f5f5; color: #333; padding: 24px; max-width: 1400px; margin: 0 auto; }}
  h1 {{ text-align: center; margin-bottom: 8px; color: #0078d4; }}
  .subtitle {{ text-align: center; color: #666; margin-bottom: 12px; font-size: 14px; }}
  .iteration-badge {{ text-align: center; margin-bottom: 24px; }}
  .iteration-badge span {{ background: #e8f4fd; color: #0078d4; padding: 4px 14px; border-radius: 12px; font-size: 13px; font-weight: 600; }}
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

  .feedback-section {{ margin-top: 12px; padding-top: 12px; border-top: 1px dashed #ddd; }}
  .feedback-label {{ font-size: 13px; color: #555; font-weight: 600; display: block; margin-bottom: 4px; }}
  .feedback-input {{ width: 100%; padding: 8px 10px; border: 1px solid #ccc; border-radius: 4px; font-family: inherit; font-size: 13px; resize: vertical; }}
  .feedback-input:focus {{ border-color: #0078d4; outline: none; box-shadow: 0 0 0 2px rgba(0,120,212,0.2); }}

  .submit-section {{ text-align: center; margin: 40px 0; }}
  .submit-btn {{ background: #0078d4; color: #fff; border: none; padding: 14px 40px; font-size: 16px; font-weight: 600; border-radius: 6px; cursor: pointer; }}
  .submit-btn:hover {{ background: #106ebe; }}
  .submit-btn:disabled {{ background: #999; cursor: not-allowed; }}
  .submit-btn.finalize {{ background: #107c10; }}
  .submit-btn.finalize:hover {{ background: #0b6a0b; }}
  .submit-status {{ margin-top: 12px; font-size: 14px; }}
  .submit-status.success {{ color: #155724; }}
  .submit-status.error {{ color: #721c24; }}
  .submit-status.processing {{ color: #856404; }}

  .no-corrections-banner {{ text-align: center; margin: 20px 0; padding: 20px; background: #d4edda; border: 1px solid #c3e6cb; border-radius: 6px; }}
  .no-corrections-banner p {{ font-size: 15px; color: #155724; font-weight: 600; margin-bottom: 8px; }}
  .no-corrections-banner .hint {{ font-size: 13px; color: #155724; font-weight: 400; }}

  .pr-result {{ text-align: center; margin: 30px 0; padding: 24px; background: #d4edda; border: 2px solid #28a745; border-radius: 8px; }}
  .pr-result h2 {{ color: #155724; margin-bottom: 12px; }}
  .pr-result a {{ color: #0078d4; font-size: 16px; font-weight: 600; }}

  @media (max-width: 900px) {{ .pair-container {{ grid-template-columns: 1fr; }} }}
</style>
</head>
<body>

<h1>{html.escape(title)}</h1>
<p class="subtitle">{html.escape(subtitle)}</p>
{"<div class='iteration-badge'><span>Iteration " + str(iteration) + "</span></div>" if iteration > 0 else ""}

{"".join(screenshot_rows)}

<div id="no-corrections-banner" class="no-corrections-banner" style="display:none;">
  <p>&#10003; All screenshots look good. No corrections needed.</p>
  <p class="hint">Click <strong>Submit &amp; Create PR</strong> below to finalize and create a pull request with these results.</p>
</div>

<div class="submit-section">
  <button class="submit-btn" id="submit-btn" onclick="handleSubmit()">
    Submit
  </button>
  <div class="submit-status" id="submit-status"></div>
</div>

<div id="pr-result" class="pr-result" style="display:none;">
  <h2>&#10003; Pull Request Created</h2>
  <p><a id="pr-link" href="#" target="_blank">View PR</a></p>
  <p style="margin-top: 8px; font-size: 13px; color: #155724;">
    The PR includes before/after comparison images for reviewer validation.
    You can close this tab.
  </p>
</div>

<script>
const SERVER_PORT = {server_port};
const ITERATION = {iteration};
const INTERACTIVE = SERVER_PORT > 0;
const SERVER_BASE = INTERACTIVE ? `http://127.0.0.1:${{SERVER_PORT}}` : '';

// Update button text based on whether corrections exist
function updateSubmitButton() {{
  const btn = document.getElementById('submit-btn');
  const banner = document.getElementById('no-corrections-banner');
  const hasCorrections = checkForCorrections();

  if (hasCorrections) {{
    btn.textContent = 'Submit Corrections';
    btn.className = 'submit-btn';
    banner.style.display = 'none';
  }} else {{
    btn.textContent = 'Submit & Create PR';
    btn.className = 'submit-btn finalize';
    banner.style.display = 'block';
  }}
}}

function checkForCorrections() {{
  let hasAny = false;
  document.querySelectorAll('.feedback-input').forEach(ta => {{
    if (ta.value.trim()) hasAny = true;
  }});
  return hasAny;
}}

// Listen for textarea changes to update button dynamically
document.querySelectorAll('.feedback-input').forEach(ta => {{
  ta.addEventListener('input', updateSubmitButton);
}});

// Initial button state
updateSubmitButton();

async function handleSubmit() {{
  if (!INTERACTIVE) {{
    document.getElementById('submit-status').textContent =
      'This report is in static mode (no local server). Rerun the skill with the compare flag to enable interactive review.';
    document.getElementById('submit-status').className = 'submit-status error';
    return;
  }}

  const btn = document.getElementById('submit-btn');
  const status = document.getElementById('submit-status');
  btn.disabled = true;

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
    // No corrections: finalize and create PR
    status.className = 'submit-status processing';
    status.textContent = 'All screenshots approved. Creating PR with before/after comparison images...';

    try {{
      const resp = await fetch(`${{SERVER_BASE}}/submit`, {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{ items: [] }}),
      }});
      const data = await resp.json();
      status.textContent = data.message || 'Creating PR...';
      pollForCompletion();
    }} catch (e) {{
      status.className = 'submit-status error';
      status.textContent = `Error: ${{e.message}}`;
      btn.disabled = false;
    }}
  }} else {{
    // Has corrections: submit for reprocessing
    status.className = 'submit-status processing';
    status.textContent = `Submitting ${{feedbackItems.length}} correction(s) for reprocessing...`;

    try {{
      const resp = await fetch(`${{SERVER_BASE}}/submit`, {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{ items: feedbackItems }}),
      }});
      const data = await resp.json();
      status.textContent = data.message || 'Processing corrections...';
      pollForUpdate();
    }} catch (e) {{
      status.className = 'submit-status error';
      status.textContent = `Error: ${{e.message}}`;
      btn.disabled = false;
    }}
  }}
}}

function pollForUpdate() {{
  // Poll the server until the updated report is ready
  const status = document.getElementById('submit-status');
  const interval = setInterval(async () => {{
    try {{
      const resp = await fetch(`${{SERVER_BASE}}/status`);
      const data = await resp.json();
      if (data.status === 'ready') {{
        clearInterval(interval);
        status.className = 'submit-status success';
        status.textContent = 'Updated report ready. Refreshing...';
        setTimeout(() => window.location.reload(), 500);
      }} else if (data.status === 'processing') {{
        status.textContent = data.message || 'Processing corrections...';
      }}
    }} catch (e) {{
      // Server may be busy; keep trying
    }}
  }}, 2000);
}}

function pollForCompletion() {{
  // Poll until PR is created
  const status = document.getElementById('submit-status');
  const interval = setInterval(async () => {{
    try {{
      const resp = await fetch(`${{SERVER_BASE}}/status`);
      const data = await resp.json();
      if (data.status === 'done' && data.pr_url) {{
        clearInterval(interval);
        status.style.display = 'none';
        document.getElementById('submit-btn').style.display = 'none';
        document.getElementById('no-corrections-banner').style.display = 'none';
        const prResult = document.getElementById('pr-result');
        const prLink = document.getElementById('pr-link');
        prLink.href = data.pr_url;
        prLink.textContent = data.pr_url;
        prResult.style.display = 'block';
      }} else if (data.status === 'finalizing') {{
        status.textContent = data.message || 'Creating PR...';
      }}
    }} catch (e) {{
      // Server may be busy; keep trying
    }}
  }}, 2000);
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
    public_gist: bool = True,
) -> tuple[str, str]:
    """
    Generate a comparison report and publish it as a GitHub Gist.

    This produces a self-contained HTML file (static mode, no local server),
    saves it locally (if output_path given), and uploads it as a gist
    viewable via htmlpreview.github.io.

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
        server_port=0,  # static mode
    )

    safe_name = "".join(c if c.isalnum() or c in "-_ " else "" for c in title)
    safe_name = safe_name.strip().replace(" ", "-").lower()[:60] or "comparison"
    filename = f"{safe_name}.html"

    gist_url = gh.create_gist(
        filename=filename,
        content=report_html,
        description=title,
        public=public_gist,
    )

    preview_url = ""
    if gist_url and "gist.github.com" in gist_url:
        raw_url = f"{gist_url}/raw/{filename}"
        preview_url = f"https://htmlpreview.github.io/?{raw_url}"

    return gist_url, preview_url
