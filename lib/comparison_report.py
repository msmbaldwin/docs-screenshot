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
    pr_url: str = "",
) -> str:
    """
    Generate a comparison report HTML with local feedback UI.

    When pr_url is set, the report is generated in finalized/read-only mode:
    no textboxes, no buttons, just a link to the PR at top and bottom.

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

    interactive = server_port > 0 and not pr_url
    finalized = bool(pr_url)

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

            feedback_html = ""
            if interactive:
                feedback_html = f"""
      <div class="feedback-section">
        <label class="feedback-label" for="fb-{name_escaped}">Feedback for <code>{name_escaped}</code>:</label>
        <textarea class="feedback-input" id="fb-{name_escaped}" data-image="{name_escaped}"
                  placeholder="Describe what's wrong with this screenshot (leave blank if it looks good)..."
                  rows="2"></textarea>
      </div>"""

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
      </div>{feedback_html}
    </div>""")

        screenshot_rows.append(f"""
<div class="article">
  <div class="article-header">{html.escape(group_name)}</div>
  <div class="article-body">
    {"".join(rows)}
  </div>
</div>""")

    iteration_note= f" (Iteration {iteration})" if iteration > 0 else ""

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
  .submit-btn.dismiss {{ background: #6c757d; }}
  .submit-btn.dismiss:hover {{ background: #565e64; }}
  .submit-status {{ margin-top: 12px; font-size: 14px; }}
  .submit-status.success {{ color: #155724; }}
  .submit-status.error {{ color: #721c24; }}
  .submit-status.processing {{ color: #856404; }}

  .processing-log-wrap {{ display: none; margin: 16px auto 0; max-width: 800px; text-align: left; }}
  .processing-log-wrap .log-header {{ font-size: 12px; font-weight: 600; color: #555; margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.5px; display: flex; align-items: center; justify-content: space-between; }}
  .log-copy-btn {{ font-size: 11px; font-weight: 500; color: #0078d4; background: none; border: 1px solid #0078d4; border-radius: 3px; padding: 1px 8px; cursor: pointer; text-transform: none; letter-spacing: 0; }}
  .log-copy-btn:hover {{ background: #e8f0fb; }}
  .processing-log {{ background: #1e1e1e; color: #d4d4d4; font-family: 'Cascadia Code', 'Consolas', monospace; font-size: 12px; padding: 10px 14px; border-radius: 6px; height: 200px; overflow-y: auto; white-space: pre-wrap; word-break: break-all; }}

  .static-mode-banner {{ text-align: center; margin: 24px 0; padding: 16px 24px; background: #fff3cd; border: 1px solid #ffc107; border-radius: 6px; font-size: 14px; color: #856404; }}
  .static-mode-banner code {{ background: #f8f0d0; padding: 1px 5px; border-radius: 3px; }}

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
<div id="pr-result-top" class="pr-result" style="display:{"block" if finalized else "none"};">
  <h2>&#10003; Pull Request Created</h2>
  <p><a id="pr-link-top" href="{html.escape(pr_url) if finalized else '#'}" target="_blank">{"" if not finalized else html.escape(pr_url)}</a></p>
  <p style="margin-top: 8px; font-size: 13px; color: #155724;">
    {"This report is finalized. The PR above contains the before/after comparison images." if finalized else "The PR includes before/after comparison images for reviewer validation."}
  </p>
</div>
{"<div class='iteration-badge'><span>Iteration " + str(iteration) + "</span></div>" if iteration > 0 and not finalized else ""}

{"".join(screenshot_rows)}

{"" if interactive or finalized else '''<div class="static-mode-banner">
  <strong>&#128247; View-only mode</strong> &mdash; This report was generated without a local server.
  To submit corrections or create a PR, rerun the skill with the <code>compare</code> flag.
</div>'''}

<div id="no-corrections-banner" class="no-corrections-banner" style="display:none;">
  <p>&#10003; All screenshots look good. No corrections needed.</p>
  <p class="hint">Click <strong>Submit &amp; Create PR</strong> below to finalize and create a pull request with these results.</p>
</div>

{"" if not interactive else '''<div class="submit-section">
  <button class="submit-btn" id="submit-btn" onclick="handleSubmit()">
    Submit
  </button>
  <button class="submit-btn dismiss" id="dismiss-btn" onclick="handleDismiss()" style="margin-left: 12px;">
    No Changes Needed
  </button>
  <div class="submit-status" id="submit-status"></div>
  <div class="processing-log-wrap" id="processing-log-wrap">
    <div class="log-header">
      <span>&#128257; Processing log &mdash; this can take a while per correction</span>
      <button class="log-copy-btn" onclick="copyLog()">Copy</button>
    </div>
    <div class="processing-log" id="processing-log"></div>
  </div>
</div>'''}

<div id="pr-result" class="pr-result" style="display:none;">
  <h2>&#10003; Pull Request Created</h2>
  <p><a id="pr-link" href="#" target="_blank">View PR</a></p>
  <p style="margin-top: 8px; font-size: 13px; color: #155724;">
    The PR includes before/after comparison images for reviewer validation.
    You can close this tab.
  </p>
</div>

""" + (f'''<div class="pr-result" style="display:block;">
  <h2>&#10003; Pull Request Created</h2>
  <p><a href="{html.escape(pr_url)}" target="_blank">{html.escape(pr_url)}</a></p>
  <p style="margin-top: 8px; font-size: 13px; color: #155724;">
    This report is finalized. The PR above contains the before/after comparison images.
  </p>
</div>''' if finalized else "") + """

<script>
const SERVER_PORT = {server_port};
const ITERATION = {iteration};
const INTERACTIVE = SERVER_PORT > 0;
const SERVER_BASE = INTERACTIVE ? `http://127.0.0.1:${{SERVER_PORT}}` : '';

// Update button text/state based on iteration and whether corrections exist
function updateSubmitButton() {{
  const btn = document.getElementById('submit-btn');
  const dismissBtn = document.getElementById('dismiss-btn');
  const banner = document.getElementById('no-corrections-banner');
  const hasCorrections = checkForCorrections();

  if (ITERATION === 0) {{
    if (hasCorrections) {{
      btn.style.display = '';
      btn.disabled = false;
      btn.textContent = 'Submit feedback to improve screenshots';
      btn.className = 'submit-btn';
      dismissBtn.style.display = 'none';
    }} else {{
      btn.style.display = 'none';
      dismissBtn.style.display = '';
    }}
    banner.style.display = 'none';
  }} else if (hasCorrections) {{
    btn.style.display = '';
    btn.disabled = false;
    btn.textContent = 'Submit feedback to improve screenshots';
    btn.className = 'submit-btn';
    dismissBtn.style.display = 'none';
    banner.style.display = 'none';
  }} else {{
    btn.style.display = '';
    btn.disabled = false;
    btn.textContent = 'Submit & Create PR';
    btn.className = 'submit-btn finalize';
    dismissBtn.style.display = '';
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

  if (feedbackItems.length === 0 && ITERATION > 0) {{
    // No corrections and we've done at least one review round: finalize and create PR
    status.className = 'submit-status processing';
    status.textContent = 'All screenshots approved. Creating PR with before/after comparison images...';

    try {{
      const resp = await fetch(`${{SERVER_BASE}}/finalize`, {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: '{{}}',
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
    // Has corrections, OR iteration 0 (always submit for improvement)
    const correctionCount = feedbackItems.length;
    status.className = 'submit-status processing';
    status.textContent = correctionCount > 0
      ? `Submitting ${{correctionCount}} correction(s) for reprocessing...`
      : 'Marking all screenshots as approved for this round...';

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
  // Poll the server until the updated report is ready; show live log
  const status = document.getElementById('submit-status');
  const logWrap = document.getElementById('processing-log-wrap');
  const logEl = document.getElementById('processing-log');
  if (logWrap) logWrap.style.display = 'block';

  const interval = setInterval(async () => {{
    try {{
      const [statusResp, logResp] = await Promise.all([
        fetch(`${{SERVER_BASE}}/status`),
        fetch(`${{SERVER_BASE}}/log`),
      ]);
      const data = await statusResp.json();
      const logData = await logResp.json();

      if (logEl && logData.lines && logData.lines.length) {{
        logEl.textContent = logData.lines.join('\\n');
        logEl.scrollTop = logEl.scrollHeight;
      }}

      if (data.status === 'ready') {{
        clearInterval(interval);
        status.className = 'submit-status success';
        status.textContent = 'Updated report ready. Refreshing...';
        setTimeout(() => window.location.reload(), 800);
      }} else if (data.status === 'processing') {{
        status.className = 'submit-status processing';
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
        // Hide all feedback UI
        status.style.display = 'none';
        document.getElementById('submit-btn').style.display = 'none';
        document.getElementById('no-corrections-banner').style.display = 'none';
        const logWrap = document.getElementById('processing-log-wrap');
        if (logWrap) logWrap.style.display = 'none';
        // Hide all feedback textareas
        document.querySelectorAll('.feedback-section').forEach(el => el.style.display = 'none');

        // Show PR result at bottom
        const prResult = document.getElementById('pr-result');
        const prLink = document.getElementById('pr-link');
        prLink.href = data.pr_url;
        prLink.textContent = data.pr_url;
        prResult.style.display = 'block';

        // Show PR result at top
        const prResultTop = document.getElementById('pr-result-top');
        const prLinkTop = document.getElementById('pr-link-top');
        if (prResultTop && prLinkTop) {{
          prLinkTop.href = data.pr_url;
          prLinkTop.textContent = data.pr_url;
          prResultTop.style.display = 'block';
        }}
      }} else if (data.status === 'finalizing') {{
        status.textContent = data.message || 'Creating PR...';
      }} else if (data.status === 'error') {{
        clearInterval(interval);
        status.className = 'submit-status error';
        status.textContent = data.message || 'PR creation failed.';
        document.getElementById('submit-btn').disabled = false;
      }}
    }} catch (e) {{
      // Server may be busy; keep trying
    }}
  }}, 2000);
}}
async function handleDismiss() {{
  if (!INTERACTIVE) return;
  const btn = document.getElementById('dismiss-btn');
  const submitBtn = document.getElementById('submit-btn');
  const status = document.getElementById('submit-status');

  if (!confirm('Are you sure? This will tear down any provisioned Azure resources and close the review. No PR will be created.')) return;

  btn.disabled = true;
  submitBtn.disabled = true;
  status.className = 'submit-status processing';
  status.textContent = 'Tearing down resources...';

  try {{
    const resp = await fetch(`${{SERVER_BASE}}/dismiss`, {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json' }},
      body: '{{}}',
    }});
    const data = await resp.json();
    status.textContent = data.message || 'Tearing down...';
    pollForDismiss();
  }} catch (e) {{
    status.className = 'submit-status error';
    status.textContent = `Error: ${{e.message}}`;
    btn.disabled = false;
    submitBtn.disabled = false;
  }}
}}

function pollForDismiss() {{
  const status = document.getElementById('submit-status');
  const interval = setInterval(async () => {{
    try {{
      const resp = await fetch(`${{SERVER_BASE}}/status`);
      const data = await resp.json();
      if (data.status === 'dismissed') {{
        clearInterval(interval);
        // Hide all interactive elements
        document.getElementById('submit-btn').style.display = 'none';
        document.getElementById('dismiss-btn').style.display = 'none';
        document.getElementById('no-corrections-banner').style.display = 'none';
        const logWrap = document.getElementById('processing-log-wrap');
        if (logWrap) logWrap.style.display = 'none';
        document.querySelectorAll('.feedback-section').forEach(el => el.style.display = 'none');
        status.className = 'submit-status success';
        status.textContent = 'No changes needed. Resources have been torn down. You can close this tab.';
      }} else if (data.status === 'dismissing') {{
        status.textContent = data.message || 'Tearing down resources...';
      }}
    }} catch (e) {{
      // Server may be shutting down
    }}
  }}, 2000);
}}

function copyLog() {{
  const logEl = document.getElementById('processing-log');
  if (!logEl || !logEl.textContent.trim()) return;
  navigator.clipboard.writeText(logEl.textContent).then(() => {{
    const btn = document.querySelector('.log-copy-btn');
    btn.textContent = 'Copied!';
    setTimeout(() => {{ btn.textContent = 'Copy'; }}, 2000);
  }}).catch(() => {{
    // Fallback for browsers that block clipboard
    const ta = document.createElement('textarea');
    ta.value = logEl.textContent;
    ta.style.position = 'fixed'; ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    document.body.removeChild(ta);
  }});
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
