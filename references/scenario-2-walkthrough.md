# Scenario 2: Parsing an Existing Article for Screenshot Refresh

_Reference for the docs-screenshot skill. See [`SKILL.md`](../SKILL.md) for the trigger-time prompt and high-level usage._


When given an existing markdown article, follow this process:

### Step 1: Read the article and extract image references

```bash
# Read the article
cat /path/to/article.md
```

Look for image references in either format:
- `:::image type="content" source="media/article-name/image-name.png" alt-text="Description.":::`
- `![Description](media/article-name/image-name.png)`

### Step 1.5: Filter out non-screenshot images

Use `DocAnalyzer.filter_screenshots()` to separate portal screenshots from diagrams, icons, conceptual art, and other non-capturable images:

```python
from lib.doc_analyzer import DocAnalyzer

analyzer = DocAnalyzer()
all_images = analyzer.parse_markdown_images(content, doc_path, repo_root)
screenshots, skipped = analyzer.filter_screenshots(all_images, repo_root)

if skipped:
    print(f"Skipping {len(skipped)} non-screenshot images:")
    for img in skipped:
        print(f"  - {img.source_path} (alt: {img.alt_text[:60]})")
```

The filter checks `image_type` (icons are always skipped), alt text and filename keywords (diagram, architecture, flowchart, etc.), surrounding context signals ("the following diagram"), and optionally inspects the actual image file for diagram-like characteristics (few colors, mostly white background).

**Only process the `screenshots` list from this point forward.**

### Step 2: For each screenshot, determine what it shows

Read the **alt text**, the **surrounding markdown** (especially numbered steps), and the **existing image** (if available) to understand:
- Which portal and page is shown
- What state the page should be in (resources created, settings configured, etc.)
- What elements have callout boxes
- How the image is cropped (full browser frame vs. focused view)

### Step 2.5: Analyze interaction requirements

For each image, use `DocAnalyzer` to extract what must happen before capture:

```python
from lib.doc_analyzer import DocAnalyzer

analyzer = DocAnalyzer(article_path)
for img_ref in analyzer.image_references:
    steps = analyzer.get_interaction_steps(img_ref)
    flyouts = analyzer.get_flyout_requirements(img_ref)
    data = analyzer.get_data_requirements(img_ref)
```

- **Interaction steps**: What to click, select, expand, or toggle before the screenshot (extracted from action verbs in the doc text)
- **Flyout requirements**: Whether a panel, blade, or dropdown must be open
- **Data requirements**: What data must exist, distinguishing **required** (has callout or is described in doc) from **incidental** (visible but not highlighted or mentioned)

### Step 3: Plan resource provisioning

Examine all images together to build a single resource provisioning plan:
- What resources are needed across all screenshots
- Create them in dependency order
- Use fictitious names from the start (contoso-rg, etc.) so scrubbing is minimal

### Step 4: Capture each screenshot in order

Follow the full workflow (Phases 1-9) for each screenshot, saving to the correct `media/` path with the correct filename.

### Step 5: Generate comparison report

For each image, report:
- **File paths**: Full repo-root-relative path for each doc and image (never local filesystem paths)
- Original file: dimensions, size, exists?
- New file: dimensions, size
- What changed (new resources, updated UI, different crop)
- Any PII that was found and replaced
- **Failure category and explanation** for any captures that did not succeed (see [Failure Categories Reference](failure-categories.md))
- **Page change flags** when the service has been restructured or renamed since the original screenshot
- **Recommendation for human reviewer**: What action to take (approve, re-capture with different credentials, update doc text, etc.)

### Step 6: Offer cleanup

Ask the user whether to delete provisioned resources.

