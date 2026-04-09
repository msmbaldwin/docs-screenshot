#!/usr/bin/env python3
"""Build the v7 stress-test comparison report HTML from the manifest."""

import json
import base64
import os
import sys
from pathlib import Path, PureWindowsPath
from datetime import datetime, timezone

MANIFEST = Path(__file__).parent / "v7-manifest.json"
OUTPUT   = Path(__file__).parent / "comparison-report-v7.html"
REPO_ROOT = Path(r"F:\git")

REPO_COLORS = {
    "azure-ai-docs-pr": ("#3b82f6", "blue"),
    "azure-docs-pr":    ("#22c55e", "green"),
    "fabric-docs-pr":   ("#a855f7", "purple"),
}

CATEGORIES = [
    ("perfect",              "🎯 Perfect",              "#16a34a"),
    ("correct",              "✅ Correct",               "#4ade80"),
    ("minor_issues",         "🔧 Minor Issues",         "#facc15"),
    ("wrong_content",        "⚠️ Wrong Content",        "#f97316"),
    ("failed",               "❌ Failed",                "#ef4444"),
    ("privilege_issue",      "🔒 Privilege Issue",       "#a855f7"),
    ("doc_insufficient",     "📄 Doc Insufficient",     "#9ca3af"),
    ("missing_elements",     "🔍 Missing Elements",     "#3b82f6"),
    ("pii_leak",             "🚨 PII Leak",             "#991b1b"),
    ("service_restructured", "⚠️ Service Restructured", "#d97706"),
    ("pending",              "⏳ Pending",               "#d1d5db"),
]


def resolve_image_path(repo: str, article: str, source: str) -> Path:
    """Resolve the image path from manifest entry fields."""
    repo_dir = REPO_ROOT / repo

    if source.startswith("~/"):
        # Reusable content: path after ~/ is relative to repo root
        rel = source[2:]  # strip ~/
        return repo_dir / rel

    # Strip leading ./
    if source.startswith("./"):
        source = source[2:]

    # Resolve relative to article's directory
    article_dir = PureWindowsPath(article).parent
    resolved = (repo_dir / article_dir / source).resolve()
    return Path(resolved)


def encode_image(path: Path) -> str | None:
    """Read an image file and return a base64 data URI, or None."""
    if not path.exists():
        return None
    suffix = path.suffix.lower()
    mime = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".svg": "image/svg+xml",
        ".webp": "image/webp",
    }.get(suffix, "image/png")
    data = path.read_bytes()
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:{mime};base64,{b64}"


def build_html(entries: list[dict]) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Repo distribution
    repo_counts: dict[str, int] = {}
    for e in entries:
        repo_counts[e["repo"]] = repo_counts.get(e["repo"], 0) + 1

    # Build per-entry HTML cards
    cards_html = []
    for idx, e in enumerate(entries):
        eid = e["id"]
        repo = e["repo"]
        article = e.get("article", "")
        source = e.get("source", "")
        alt_text = e.get("alt_text", "")
        context = e.get("context", "")
        portal = e.get("portal", "")
        service_area = e.get("service_area", "")

        repo_color, repo_label = REPO_COLORS.get(repo, ("#6b7280", "gray"))

        # Resolve and encode original image
        img_path = resolve_image_path(repo, article, source)
        data_uri = encode_image(img_path)
        if data_uri:
            orig_img_tag = (
                f'<img src="{data_uri}" alt="{esc(alt_text)}" '
                f'class="compare-img original-img" data-image-id="{eid}-original" '
                f'onclick="openLightbox(this)" loading="lazy">'
            )
        else:
            orig_img_tag = (
                f'<div class="img-placeholder">'
                f'<span>Original not found</span>'
                f'<small>{esc(str(img_path))}</small></div>'
            )

        ctx_short = context[:300] + ("…" if len(context) > 300 else "")

        card = f'''
<div class="entry-card" id="entry-{eid}" data-repo="{esc(repo)}" data-id="{eid}">
  <div class="entry-header" onclick="toggleCard(this)">
    <span class="id-badge">{esc(eid)}</span>
    <span class="repo-tag" style="background:{repo_color}">{esc(repo)}</span>
    <span class="auto-badge">CAPTURE_PENDING</span>
    <span class="portal-badge">{esc(portal)}</span>
    <span class="collapse-icon">&#9660;</span>
  </div>
  <div class="entry-body">
    <div class="image-compare">
      <div class="img-col">
        <h4>Original</h4>
        {orig_img_tag}
      </div>
      <div class="img-col">
        <h4>Captured</h4>
        <div class="img-placeholder captured-slot" id="captured-{eid}">
          <span>Capture pending&hellip;</span>
        </div>
      </div>
    </div>
    <div class="meta-row">
      <div><strong>Article:</strong> <code>{esc(article)}</code></div>
      <div><strong>Image source:</strong> <code>{esc(source)}</code></div>
      <div><strong>Alt text:</strong> {esc(alt_text)}</div>
      <div><strong>Context:</strong> <span class="context-text">{esc(ctx_short)}</span></div>
      <div><strong>Service area:</strong> {esc(service_area)}</div>
    </div>
    <div class="rater-row">
      <label>Human rating:
        <select class="human-category" data-id="{eid}" onchange="onCategoryChange()">
          {"".join(f'<option value="{cid}"{" selected" if cid=="pending" else ""}>{lbl}</option>' for cid, lbl, _ in CATEGORIES)}
        </select>
      </label>
      <label class="notes-label">Notes:
        <textarea class="human-notes" data-id="{eid}" rows="2" placeholder="Reviewer notes…"></textarea>
      </label>
    </div>
    <div class="capture-details" id="details-{eid}">
      <em>Capture details will appear here after processing.</em>
    </div>
  </div>
</div>'''
        cards_html.append(card)

    cards_block = "\n".join(cards_html)

    # Quick-nav list
    nav_items = "".join(
        f'<a href="#entry-{e["id"]}" class="nav-id" data-repo="{e["repo"]}">{e["id"]}</a>'
        for e in entries
    )

    # Manifest JSON embedded for JS use
    manifest_json = json.dumps(entries)

    repo_dist_summary = ", ".join(f"{r}: {c}" for r, c in sorted(repo_counts.items()))

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Grand Stress Test Report v7</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
*,*::before,*::after{{box-sizing:border-box}}
body{{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;background:#f1f5f9;color:#1e293b}}
a{{color:#2563eb;text-decoration:none}}
/* Header */
.top-header{{background:#0f172a;color:#f8fafc;padding:1.2rem 2rem;position:relative;z-index:100}}
.top-header h1{{margin:0 0 .3rem;font-size:1.5rem}}
.top-header .meta{{font-size:.85rem;color:#94a3b8}}
/* Dashboard */
.dashboard{{background:#fff;border-bottom:1px solid #e2e8f0;padding:1rem 2rem;display:flex;gap:2rem;align-items:flex-start;position:sticky;top:0;z-index:90;box-shadow:0 2px 6px rgba(0,0,0,.08)}}
.chart-wrap{{width:220px;min-width:220px;height:220px}}
.summary-cards{{display:flex;flex-wrap:wrap;gap:.5rem;flex:1}}
.summary-card{{display:inline-flex;align-items:center;gap:.4rem;padding:.3rem .7rem;border-radius:6px;font-size:.82rem;font-weight:600;color:#fff;min-width:140px}}
.summary-card .cnt{{background:rgba(255,255,255,.3);border-radius:4px;padding:0 6px;margin-left:auto}}
/* Filters */
.filter-bar{{background:#fff;border-bottom:1px solid #e2e8f0;padding:.6rem 2rem;display:flex;gap:1rem;align-items:center;flex-wrap:wrap;position:sticky;top:calc(220px + 2rem + 2px);z-index:80}}
.filter-bar label{{font-weight:600;font-size:.85rem}}
.filter-bar select,.filter-bar input{{padding:.3rem .5rem;border:1px solid #cbd5e1;border-radius:4px;font-size:.85rem}}
.filter-count{{margin-left:auto;font-size:.82rem;color:#64748b}}
/* Quick nav */
.quick-nav{{background:#fff;border-bottom:1px solid #e2e8f0;padding:.5rem 2rem;display:flex;flex-wrap:wrap;gap:4px;max-height:5rem;overflow-y:auto}}
.nav-id{{font-size:.72rem;padding:2px 5px;border-radius:3px;background:#e2e8f0;color:#334155;font-family:monospace}}
.nav-id:hover{{background:#3b82f6;color:#fff}}
/* Entry cards */
.entries{{padding:1rem 2rem 6rem}}
.entry-card{{background:#fff;border-radius:8px;margin-bottom:.8rem;box-shadow:0 1px 3px rgba(0,0,0,.06);overflow:hidden}}
.entry-card.hidden{{display:none}}
.entry-header{{display:flex;align-items:center;gap:.6rem;padding:.7rem 1rem;cursor:pointer;user-select:none;background:#f8fafc;border-bottom:1px solid #e2e8f0}}
.entry-header:hover{{background:#f1f5f9}}
.id-badge{{font-family:monospace;font-weight:700;font-size:.85rem;background:#1e293b;color:#f8fafc;padding:2px 8px;border-radius:4px}}
.repo-tag{{color:#fff;padding:2px 8px;border-radius:4px;font-size:.75rem;font-weight:600}}
.auto-badge{{font-size:.75rem;background:#e2e8f0;padding:2px 6px;border-radius:4px}}
.portal-badge{{font-size:.75rem;background:#dbeafe;color:#1e40af;padding:2px 6px;border-radius:4px}}
.collapse-icon{{margin-left:auto;font-size:.7rem;transition:transform .2s}}
.entry-card.collapsed .collapse-icon{{transform:rotate(-90deg)}}
.entry-card.collapsed .entry-body{{display:none}}
.entry-body{{padding:1rem}}
.image-compare{{display:grid;grid-template-columns:1fr 1fr;gap:1rem;margin-bottom:1rem}}
.img-col h4{{margin:0 0 .5rem;font-size:.9rem;color:#475569}}
.compare-img{{max-width:100%;border:1px solid #e2e8f0;border-radius:4px;cursor:zoom-in}}
.img-placeholder{{border:2px dashed #cbd5e1;border-radius:4px;padding:2rem;text-align:center;color:#94a3b8;min-height:120px;display:flex;flex-direction:column;align-items:center;justify-content:center}}
.img-placeholder small{{word-break:break-all;font-size:.7rem;margin-top:.4rem;max-width:100%}}
.meta-row{{font-size:.82rem;margin-bottom:.8rem;display:grid;gap:.3rem}}
.meta-row code{{background:#f1f5f9;padding:1px 4px;border-radius:3px;font-size:.78rem}}
.context-text{{color:#64748b}}
.rater-row{{display:flex;gap:1.5rem;align-items:flex-start;flex-wrap:wrap;margin-bottom:.8rem}}
.rater-row label{{font-size:.85rem;font-weight:600}}
.human-category{{padding:.3rem;font-size:.85rem}}
.notes-label{{flex:1;min-width:250px}}
.human-notes{{width:100%;font-size:.82rem;padding:.3rem;border:1px solid #cbd5e1;border-radius:4px;resize:vertical}}
.capture-details{{font-size:.8rem;color:#64748b;padding:.5rem;background:#f8fafc;border-radius:4px}}
/* Lightbox */
.lightbox-overlay{{display:none;position:fixed;inset:0;background:rgba(0,0,0,.85);z-index:9999;align-items:center;justify-content:center;cursor:zoom-out}}
.lightbox-overlay.active{{display:flex}}
.lightbox-overlay img{{max-width:95vw;max-height:95vh;border-radius:4px}}
/* Floating save button */
.save-float{{position:fixed;bottom:2rem;right:2rem;z-index:200;display:flex;flex-direction:column;align-items:flex-end;gap:.5rem}}
.save-btn{{background:#2563eb;color:#fff;border:none;padding:.7rem 1.4rem;border-radius:8px;font-size:1rem;font-weight:700;cursor:pointer;box-shadow:0 4px 12px rgba(37,99,235,.4);transition:background .15s}}
.save-btn:hover{{background:#1d4ed8}}
.save-hint{{font-size:.7rem;color:#64748b;background:#fff;padding:.3rem .6rem;border-radius:4px;box-shadow:0 1px 4px rgba(0,0,0,.1);max-width:280px;text-align:right}}
/* Toast */
.toast{{position:fixed;bottom:6rem;right:2rem;background:#16a34a;color:#fff;padding:.6rem 1.2rem;border-radius:6px;font-weight:600;font-size:.9rem;z-index:300;opacity:0;transition:opacity .3s;pointer-events:none}}
.toast.show{{opacity:1}}
@media(max-width:900px){{
  .image-compare{{grid-template-columns:1fr}}
  .dashboard{{flex-direction:column}}
}}
</style>
</head>
<body>

<div class="top-header">
  <h1>Grand Stress Test Report v7 &mdash; 100 Screenshots</h1>
  <div class="meta">
    Generated: {now} &bull; Total images: {len(entries)} &bull; Repos: {repo_dist_summary}
  </div>
</div>

<!-- Dashboard -->
<div class="dashboard" id="dashboard">
  <div class="chart-wrap"><canvas id="pieChart"></canvas></div>
  <div class="summary-cards" id="summaryCards"></div>
</div>

<!-- Filter bar -->
<div class="filter-bar">
  <label>Filter:</label>
  <select id="filterRepo" onchange="applyFilters()">
    <option value="">All repos</option>
    {"".join(f'<option value="{r}">{r} ({c})</option>' for r, c in sorted(repo_counts.items()))}
  </select>
  <select id="filterCategory" onchange="applyFilters()">
    <option value="">All categories</option>
    {"".join(f'<option value="{cid}">{lbl}</option>' for cid, lbl, _ in CATEGORIES)}
  </select>
  <label><input type="checkbox" id="filterChanged" onchange="applyFilters()"> Only changed</label>
  <span class="filter-count" id="filterCount"></span>
</div>

<!-- Quick nav -->
<div class="quick-nav" id="quickNav">{nav_items}</div>

<!-- Lightbox -->
<div class="lightbox-overlay" id="lightbox" onclick="closeLightbox()">
  <img id="lightboxImg" src="" alt="Zoomed image">
</div>

<!-- Entries -->
<div class="entries" id="entriesContainer">
{cards_block}
</div>

<!-- Floating save -->
<div class="save-float">
  <div class="save-hint">After saving, place <code>v7-feedback.json</code> in <code>test-comparison/</code> and tell Copilot: &ldquo;process the user suggestions for the v7 report&rdquo;</div>
  <button class="save-btn" onclick="saveFeedback()">&#128190; Save Feedback</button>
</div>
<div class="toast" id="toast">Feedback saved!</div>

<script>
// Manifest data
const MANIFEST = {manifest_json};

const CATEGORIES = {json.dumps([[c[0], c[1], c[2]] for c in CATEGORIES])};

// Chart.js pie chart
let pieChart = null;

function getCategoryCounts() {{
  const counts = {{}};
  CATEGORIES.forEach(c => counts[c[0]] = 0);
  document.querySelectorAll('.human-category').forEach(sel => {{
    counts[sel.value] = (counts[sel.value] || 0) + 1;
  }});
  return counts;
}}

function renderDashboard() {{
  const counts = getCategoryCounts();

  // Summary cards
  const container = document.getElementById('summaryCards');
  container.innerHTML = CATEGORIES.map(([id, label, color]) => {{
    const c = counts[id] || 0;
    return `<div class="summary-card" style="background:${{color}}"><span>${{label}}</span><span class="cnt">${{c}}</span></div>`;
  }}).join('');

  // Pie chart
  const labels = CATEGORIES.map(c => c[1]);
  const data = CATEGORIES.map(c => counts[c[0]] || 0);
  const colors = CATEGORIES.map(c => c[2]);

  if (pieChart) {{
    pieChart.data.datasets[0].data = data;
    pieChart.update();
  }} else {{
    const ctx = document.getElementById('pieChart').getContext('2d');
    pieChart = new Chart(ctx, {{
      type: 'pie',
      data: {{
        labels: labels,
        datasets: [{{ data: data, backgroundColor: colors, borderWidth: 1, borderColor: '#fff' }}]
      }},
      options: {{
        responsive: true,
        maintainAspectRatio: false,
        plugins: {{
          legend: {{ display: false }}
        }}
      }}
    }});
  }}
}}

function onCategoryChange() {{
  renderDashboard();
  applyFilters();
}}

// Collapse/expand
function toggleCard(header) {{
  header.closest('.entry-card').classList.toggle('collapsed');
}}

// Lightbox
function openLightbox(img) {{
  document.getElementById('lightboxImg').src = img.src;
  document.getElementById('lightbox').classList.add('active');
}}
function closeLightbox() {{
  document.getElementById('lightbox').classList.remove('active');
}}
document.addEventListener('keydown', e => {{ if (e.key === 'Escape') closeLightbox(); }});

// Filters
function applyFilters() {{
  const repo = document.getElementById('filterRepo').value;
  const cat = document.getElementById('filterCategory').value;
  const onlyChanged = document.getElementById('filterChanged').checked;
  let shown = 0;
  document.querySelectorAll('.entry-card').forEach(card => {{
    const cId = card.dataset.id;
    const cRepo = card.dataset.repo;
    const sel = card.querySelector('.human-category');
    const selVal = sel ? sel.value : 'pending';
    let visible = true;
    if (repo && cRepo !== repo) visible = false;
    if (cat && selVal !== cat) visible = false;
    if (onlyChanged && selVal === 'pending') visible = false;
    card.classList.toggle('hidden', !visible);
    if (visible) shown++;
  }});
  document.getElementById('filterCount').textContent = shown + ' / {len(entries)} shown';

  // Update quick nav visibility
  document.querySelectorAll('.nav-id').forEach(a => {{
    const href = a.getAttribute('href');
    const target = document.querySelector(href);
    a.style.display = (target && !target.classList.contains('hidden')) ? '' : 'none';
  }});
}}

// Save feedback
function saveFeedback() {{
  const items = [];
  let totalReviewed = 0, totalChanged = 0;
  const catCounts = {{}};

  MANIFEST.forEach(entry => {{
    const sel = document.querySelector(`.human-category[data-id="${{entry.id}}"]`);
    const notes = document.querySelector(`.human-notes[data-id="${{entry.id}}"]`);
    const humanCat = sel ? sel.value : 'pending';
    const humanNotes = notes ? notes.value.trim() : '';
    const changed = humanCat !== 'pending';
    if (changed) {{ totalReviewed++; totalChanged++; }}
    catCounts[humanCat] = (catCounts[humanCat] || 0) + 1;

    items.push({{
      id: entry.id,
      repo: entry.repo,
      article_path: entry.article,
      image_path: entry.source,
      auto_category: "CAPTURE_PENDING",
      human_category: humanCat,
      human_notes: humanNotes,
      changed: changed
    }});
  }});

  const feedback = {{
    report_version: "v7",
    generated_at: "{now}",
    reviewed_at: new Date().toISOString(),
    items: items,
    summary: {{
      total_reviewed: totalReviewed,
      total_changed: totalChanged,
      categories: catCounts
    }}
  }};

  const blob = new Blob([JSON.stringify(feedback, null, 2)], {{ type: 'application/json' }});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'v7-feedback.json';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);

  const toast = document.getElementById('toast');
  toast.classList.add('show');
  setTimeout(() => toast.classList.remove('show'), 2500);
}}

// Init
document.addEventListener('DOMContentLoaded', () => {{
  renderDashboard();
  applyFilters();
  // Start all collapsed
  document.querySelectorAll('.entry-card').forEach(c => c.classList.add('collapsed'));
}});
</script>
</body>
</html>'''
    return html


def esc(s: str) -> str:
    """HTML-escape a string."""
    return (s
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;"))


def main():
    with open(MANIFEST, "r", encoding="utf-8") as f:
        entries = json.load(f)

    print(f"Loaded {len(entries)} entries from manifest")

    # Tally image resolution results
    found = 0
    missing = 0
    for e in entries:
        p = resolve_image_path(e["repo"], e["article"], e["source"])
        if p.exists():
            found += 1
        else:
            missing += 1
            print(f"  MISSING: {e['id']} -> {p}")

    print(f"Images found: {found}, missing: {missing}")

    html = build_html(entries)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(html)

    size_mb = os.path.getsize(OUTPUT) / (1024 * 1024)
    print(f"Report written to {OUTPUT} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
