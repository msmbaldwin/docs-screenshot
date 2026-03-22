---
name: docs-screenshot
description: Capture, process, and redact screenshots for Microsoft Learn documentation. Use when the user needs screenshots of Azure, M365, SharePoint, Entra, or any Microsoft web portal. Also use when updating existing docs, validating screenshots, or creating screenshots for new documentation.
allowed-tools: Bash(playwright-cli:*), Bash(python:*), Bash(az:*), Bash(pwsh:*), Bash(powershell:*)
---

# Microsoft Documentation Screenshot Skill

Automates the full pipeline for creating documentation screenshots across all Microsoft web portals (Azure, M365, SharePoint, Entra ID, Power Platform, etc.) that comply with Microsoft Learn contributor guidelines: browser automation, resource provisioning, PII redaction with approved fictitious values, callout boxes, smart cropping, and GIMP handoff.

## Two Primary Usage Scenarios

### Scenario 1: New Documentation Authoring

The user is writing a new article and needs screenshots. They describe what the screenshot should show, including:
- Which portal/service (Azure, M365 Admin, SharePoint, etc.)
- What the user should see (e.g., "the VM creation blade with size B2s selected")
- What resources must exist (e.g., "a resource group named contoso-rg with a VM")
- What elements to highlight with callout boxes
- How to crop the image

**Workflow:**
1. Parse the user's description to determine required resources and portal page
2. Provision any resources needed (using `az`, `m365`, Graph API, PowerShell, etc.)
3. Open the correct portal and navigate to the target page
4. Configure the view (expand panes, select items, scroll to correct position)
5. Scrub all PII from the DOM across all frames
6. Capture screenshot at 1200x800
7. Post-process: callouts, crop, border, optimize
8. Open in GIMP for final review
9. Ask user whether to clean up provisioned resources

### Scenario 2: Existing Documentation Maintenance

The user has an existing markdown article with screenshots that need to be validated or refreshed. They provide the article file path or URL.

**Workflow:**
1. Read the markdown article and parse all image references
2. For each image, read its alt text and surrounding context to understand what it should show
3. Determine the portal URL, required resources, and page state for each screenshot
4. For each screenshot:
   a. Provision resources if needed
   b. Navigate to the correct page
   c. Scrub PII, capture, process
   d. Compare with the original image (dimensions, rough visual similarity)
   e. Save to the correct media/ path with the correct filename
5. Generate a report: which screenshots were updated, which matched, which differed
6. Open all new screenshots in GIMP for final review

**Example prompt:** *"Update the screenshots in /docs/azure-sql/create-database.md. The article shows creating an Azure SQL database through the portal."*

## Limitations

- **Credential-scoped provisioning**: The skill can only create resources the user's credentials allow. If you lack permissions for a specific Azure service, M365 feature, or SharePoint site, the skill cannot provision those resources for you.
- **MFA/Conditional Access**: Some portals may trigger MFA prompts that require manual interaction. The skill will pause and ask for help.
- **Portal-specific quirks**: Each Microsoft portal has unique popup patterns, loading behaviors, and DOM structures. Azure portal is the most thoroughly tested. Other portals may need additional popup dismissal patterns added.
- **Closed Shadow DOM**: Some portal components use closed Shadow DOM that cannot be accessed even via Playwright. In rare cases, post-screenshot pixel-level redaction is needed as a fallback.
- **Dynamic content**: Portals with real-time data (metrics, logs, dashboards) may show different values between captures. The skill scrubs PII but cannot guarantee identical content across runs.
- **Canvas/SVG content**: Charts, graphs, and other canvas/SVG-rendered content cannot be scrubbed via DOM manipulation. These require the pixel-level image editing fallback.

## Quick Start

> **HEADLESS BY DEFAULT:** All browser automation MUST run headless to avoid interfering with (or being interfered by) the user's desktop. The only exception is when MFA or Conditional Access requires manual user interaction; in that case, notify the user, switch to a visible browser temporarily, and return to headless after authentication completes. See [Phase 1](#phase-1-authentication--setup) for details.

```bash
# 1. Open Azure portal in Edge with persistent profile (inherits your SSO)
playwright-cli open --browser=msedge --persistent "https://portal.azure.com/?feature.customportal=false"

# 2. Navigate to the target page
playwright-cli goto "https://portal.azure.com/#view/HubsExtension/BrowseResource/resourceType/Microsoft.Compute%2FVirtualMachines"

# 3. Wait for page to load, dismiss any popups
playwright-cli run-code "async page => { await page.waitForTimeout(3000); }"

# 4. Take screenshot + extract DOM info simultaneously
playwright-cli screenshot --filename=raw-screenshot.png
# Then run the DOM extraction (see "Extract DOM Info" section below)

# 5. Process the image (PII redaction, callouts, crop, optimize)
python <skill-install-path>/lib/screenshot_processor.py \
  --dom-json dom_data.json --image raw-screenshot.png \
  --output processed-screenshot.png \
  --description "Virtual machines list in Azure portal"
```

## Full Workflow

### Phase 0: Determine the Target Portal

This skill works with ANY Microsoft web portal that uses Microsoft SSO. Choose the correct base URL:

| Portal | Base URL | Customer View Flag |
|--------|----------|-------------------|
| **Azure** | `https://portal.azure.com/` | `?feature.customportal=false` |
| **M365 Admin** | `https://admin.microsoft.com/` | none |
| **SharePoint Admin** | `https://admin.microsoft.com/sharepoint` | none |
| **SharePoint Site** | `https://<tenant>.sharepoint.com/` | none |
| **Microsoft Entra** | `https://entra.microsoft.com/` | none |
| **Power Platform** | `https://make.powerapps.com/` | none |
| **Teams Admin** | `https://admin.teams.microsoft.com/` | none |
| **Exchange Admin** | `https://admin.exchange.microsoft.com/` | none |
| **Intune** | `https://intune.microsoft.com/` | none |
| **Defender** | `https://security.microsoft.com/` | none |
| **Purview** | `https://compliance.microsoft.com/` | none |
| **Fabric** | `https://app.fabric.microsoft.com/` | none |
| **DevOps** | `https://dev.azure.com/` | none |

**Resource provisioning tools by portal:**

| Portal | Provisioning Tool | Example |
|--------|------------------|---------|
| Azure | `az` CLI | `az group create --name contoso-rg --location eastus` |
| M365 / Entra | Microsoft Graph PowerShell | `New-MgUser`, `New-MgGroup` |
| SharePoint | PnP PowerShell | `New-PnPSite`, `Add-PnPListItem` |
| Power Platform | Power Apps CLI (`pac`) | `pac solution create` |
| Exchange | Exchange Online PowerShell | `New-Mailbox`, `New-DistributionGroup` |
| DevOps | `az devops` CLI | `az devops project create` |

### Phase 1: Authentication & Setup

**Browser automation tool:** This skill uses browser automation via one of these approaches (adapt commands to your environment):
- **Copilot CLI**: Uses the `playwright-cli` skill (install with `playwright-cli install --skills`)
- **VS Code / other editors**: Uses the [Playwright MCP server](https://github.com/microsoft/playwright-mcp) (`npx @playwright/mcp@latest --headless --browser=msedge`)
- **Playwright MCP tools**: When available in the tool list (e.g., `playwright-browser_navigate`, `playwright-browser_snapshot`), use those directly. They handle headless mode via their server configuration.

The commands in this skill use `playwright-cli` syntax. If you are using the Playwright MCP server instead, the equivalent MCP tool calls are similar (e.g., `browser_navigate` instead of `playwright-cli goto`). Adapt as needed for your environment.

**CRITICAL: Headless-first policy.** Always run headless to avoid desktop interference:
- The browser runs in the background; the user never sees a window pop up
- This is the default for both `playwright-cli` and the Playwright MCP server
- The ONLY exception: MFA/Conditional Access prompts that require manual interaction
- If MFA is triggered: notify the user, explain what is needed, and ask them to complete it. If the headless browser cannot render the MFA prompt, temporarily switch to visible mode, then return to headless.

**Open browser with persistent Edge profile (picks up existing Microsoft SSO):**
```bash
# For Azure (with customer view flag):
playwright-cli open --browser=msedge --persistent "https://portal.azure.com/?feature.customportal=false"

# For any other portal (no special flags needed):
playwright-cli open --browser=msedge --persistent "https://entra.microsoft.com/"
```

The persistent profile shares cookies with the user's regular Edge sessions, so Microsoft SSO typically works automatically.

**For Azure specifically:** always append `?feature.customportal=false` to hide internal/preview features.

**Check if authenticated:**
```bash
playwright-cli snapshot
# Look for user avatar/name in the snapshot. If you see a sign-in button, auth is needed.
```

**If login is needed, use the current user's credentials (DO NOT hardcode any specific email):**
```bash
playwright-cli snapshot
# Find the email input field ref
# Ask the user for their email, or detect it from:
#   az account show --query "user.name" -o tsv
#   $env:USERNAME + "@microsoft.com"  (as a guess, confirm with user)
playwright-cli fill <ref> "<user's email>"
playwright-cli click <submit-ref>
# MFA may be triggered - if so:
#   1. Notify the user: "MFA required. Please complete the authentication prompt."
#   2. If headless browser can't render the MFA UI, switch to visible mode temporarily
#   3. Wait for the user to confirm completion
#   4. Resume headless operation
playwright-cli run-code "async page => { await page.waitForLoadState('networkidle'); }"
```

**IMPORTANT: Never hardcode a specific user's credentials.** Always determine the current user's identity dynamically or ask them.

**Select the user's preferred subscription (if multiple exist):**
```bash
# Check what subscription is currently active
az account show --query "{name:name, id:id}" -o table

# If the user has a preferred subscription, switch to it:
# az account set --subscription "<subscription name or ID>"

# To list all available subscriptions:
# az account list --query "[].{name:name, id:id, isDefault:isDefault}" -o table
```

### Phase 2: Dismiss Popups & Banners

Azure portal frequently shows popups, preview banners, and welcome dialogs. Dismiss them all before taking screenshots.

```bash
# Common popup dismissal patterns
playwright-cli run-code "async page => {
  // Close 'Welcome' or 'What's new' dialogs
  const closeButtons = await page.locator('[aria-label=\"Close\"], [aria-label=\"Dismiss\"], button:has-text(\"Got it\"), button:has-text(\"Maybe later\"), button:has-text(\"Skip\"), button:has-text(\"No thanks\"), button:has-text(\"OK\"), .portal-banner-close, [data-telemetryname=\"DismissButton\"]').all();
  for (const btn of closeButtons) {
    try { await btn.click({ timeout: 1000 }); } catch(e) {}
  }
  // Close preview banners
  const previewBanners = await page.locator('[class*=\"preview-banner\"] button, [class*=\"fxs-banner\"] button').all();
  for (const btn of previewBanners) {
    try { await btn.click({ timeout: 1000 }); } catch(e) {}
  }
  // Wait for animations
  await page.waitForTimeout(500);
}"
```

**For persistent notification banners:**
```bash
playwright-cli run-code "async page => {
  // Hide notification panels via CSS
  await page.addStyleTag({ content: '.fxs-toast-container, .fxs-notification-panel { display: none !important; }' });
}"
```

### Phase 2.5: Doc-Driven Interaction Analysis

Before capturing any screenshot, thoroughly read the documentation text around the image reference. This analysis determines what interactions (clicks, expansions, toggles) must be performed before capture and what data must exist in the portal.

**Use `lib/doc_analyzer.py` to parse the markdown:**

```python
from lib.doc_analyzer import DocAnalyzer

analyzer = DocAnalyzer(article_path)
for img_ref in analyzer.image_references:
    steps = analyzer.get_interaction_steps(img_ref)      # InteractionStep objects
    flyout_reqs = analyzer.get_flyout_requirements(img_ref)
    data_reqs = analyzer.get_data_requirements(img_ref)   # DataRequirement objects
```

The analyzer extracts three types of objects:
- **`ImageReference`**: The image path, alt text, and surrounding doc context
- **`InteractionStep`**: Action verbs (click, select, expand, navigate, toggle) and their UI targets, extracted from the doc text preceding the image
- **`DataRequirement`**: Data that must exist in the portal for the screenshot to be accurate

**Decision tree for flyouts and panels:**

1. Does the doc say "click X" or "select X" before this screenshot? → Perform that click/selection
2. Is a button highlighted with a callout box in the original, AND the screenshot shows a flyout/panel whose title matches that button's label? → The button was clicked to reveal the flyout. Click it before capture.
3. Does the original image show a flyout or panel open? → Open it
4. Does the doc describe specific data visible in the flyout? → Create that data first
5. Is data visible in the original but NOT described in the doc and has no callout? → Incidental data, skip creating it

**Required vs. incidental data:**
- If an element has a red callout box in the original screenshot, the data it contains is **required**. Create matching data before capture.
- If data is visible in the screenshot but has no callout and is not mentioned in the doc text, it is **incidental**. Do not spend effort creating it; whatever appears naturally is fine.

### Phase 3: Azure Resource Provisioning

If the screenshot requires specific Azure resources to exist, create them using Azure CLI:

```bash
# Example: Create a resource group
az group create --name contoso-rg --location eastus

# Example: Create a VM
az vm create --resource-group contoso-rg --name contoso-vm \
  --image Ubuntu2204 --size Standard_B1s \
  --admin-username azureuser --generate-ssh-keys

# Example: Create a storage account
az storage account create --name contosostorageacct \
  --resource-group contoso-rg --location eastus --sku Standard_LRS
```

**IMPORTANT: Use fictitious-sounding names for resources** (contoso-*, fabrikam-*, etc.) so they appear correct in screenshots without needing redaction.

**After screenshots are complete, ASK the user whether to clean up:**
```bash
# List resources created
az group show --name contoso-rg --query "{name:name, location:location}"
# Ask user before deleting
az group delete --name contoso-rg --yes --no-wait
```

### Phase 3.5: Repo-Specific Configuration Loading

Before navigating to the target page, load any repo-specific configuration that affects how the skill interacts with the portal.

```python
from lib.repo_config import detect_repo_from_path, get_path_rules

repo = detect_repo_from_path(article_path)
rules = get_path_rules(repo, article_path)
```

The config system provides:
- **Navigation hints**: Portal-specific interaction patterns (e.g., Azure AI Foundry "More" button handling for hidden nav items)
- **Service rename awareness**: Maps old service names to new ones (e.g., "Form Recognizer" → "Document Intelligence") so the skill navigates to the correct current page
- **Portal privilege notes**: Flags pages that require elevated access (e.g., Fabric admin portal requires admin role)
- **Path rules**: Doc-path-based behavior overrides (e.g., docs in `foundry/` use different navigation patterns than `foundry-classic/`)

The config is embedded directly in the skill for portability. Repo owners add their config via PR to `lib/repo_config.py`; no external config files are needed.

### Phase 4: Window Sizing & Screenshot Capture

**Set the browser to the standard documentation screenshot size (1200x800):**
```bash
playwright-cli resize 1200 800
```

**Wait for full page load:**
```bash
playwright-cli run-code "async page => {
  await page.waitForLoadState('networkidle');
  // Extra wait for Azure portal animations
  await page.waitForTimeout(2000);
}"
```

**Take the screenshot:**
```bash
playwright-cli screenshot --filename=raw-screenshot.png
```

### Phase 5: DOM Extraction for PII Detection

This is the key innovation. Instead of OCR, we extract text positions directly from the DOM, giving us pixel-perfect coordinates.

**Extract DOM info (save the output to a JSON file):**
```bash
playwright-cli run-code "async page => {
  return await page.evaluate(() => {
    const DPR = window.devicePixelRatio || 1;
    const results = [];
    function getEffectiveBgColor(el) {
      let current = el;
      while (current && current !== document.documentElement) {
        const bg = getComputedStyle(current).backgroundColor;
        if (bg && bg !== 'rgba(0, 0, 0, 0)' && bg !== 'transparent') return bg;
        current = current.parentElement;
      }
      return 'rgb(255, 255, 255)';
    }
    function isVisible(el) {
      if (!el || !el.getBoundingClientRect) return false;
      const style = getComputedStyle(el);
      if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') return false;
      const rect = el.getBoundingClientRect();
      if (rect.width === 0 || rect.height === 0) return false;
      if (rect.bottom < 0 || rect.top > window.innerHeight) return false;
      if (rect.right < 0 || rect.left > window.innerWidth) return false;
      return true;
    }
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, {
      acceptNode: function(node) {
        const text = node.textContent.trim();
        if (!text) return NodeFilter.FILTER_REJECT;
        if (!isVisible(node.parentElement)) return NodeFilter.FILTER_REJECT;
        return NodeFilter.FILTER_ACCEPT;
      }
    });
    let node;
    while (node = walker.nextNode()) {
      const el = node.parentElement;
      const range = document.createRange();
      range.selectNodeContents(node);
      const rects = range.getClientRects();
      for (const rect of rects) {
        if (rect.width === 0 || rect.height === 0) continue;
        const text = node.textContent.trim();
        if (!text) continue;
        const style = getComputedStyle(el);
        results.push({
          text: text,
          cssRect: { x: Math.round(rect.x*100)/100, y: Math.round(rect.y*100)/100, width: Math.round(rect.width*100)/100, height: Math.round(rect.height*100)/100 },
          pxRect: { x: Math.round(rect.x*DPR), y: Math.round(rect.y*DPR), width: Math.round(rect.width*DPR), height: Math.round(rect.height*DPR) },
          style: { fontFamily: style.fontFamily, fontSize: style.fontSize, fontWeight: style.fontWeight, color: style.color, backgroundColor: getEffectiveBgColor(el) },
          element: { tag: el.tagName.toLowerCase(), id: el.id || null, className: el.className || null },
          dpr: DPR,
        });
      }
    }
    return { url: window.location.href, title: document.title, viewport: { width: window.innerWidth, height: window.innerHeight }, dpr: DPR, timestamp: new Date().toISOString(), textNodes: results };
  });
}"
```

**Save the DOM extraction output** to a JSON file. The output from the run-code command contains the JSON under "### Result". Save it as `dom_data.json`.

### Phase 6: Image Processing

Use the screenshot processor to apply all transformations:

```bash
python lib/screenshot_processor.py \
  --dom-json dom_data.json \
  --image raw-screenshot.png \
  --output my-final-screenshot.png \
  --description "Description of what this screenshot shows" \
  --callouts '[{"x": 100, "y": 200, "width": 300, "height": 50}]' \
  --crop-focus '[{"x": 50, "y": 150, "width": 400, "height": 300}]'
```

**Options:**
- `--skip-pii`: Skip PII detection/redaction
- `--skip-crop`: Skip smart cropping
- `--skip-border`: Skip gray border
- `--no-gimp`: Don't open in GIMP
- `--callouts`: JSON array of rectangles for red callout boxes
- `--crop-focus`: JSON array of rectangles defining area of interest

### Phase 7: Pre-Screenshot DOM Scrubbing (PREFERRED Method)

The most reliable approach is to replace PII directly in the DOM BEFORE taking the screenshot. This is the same approach as Microsoft's Screenshot Scrubber extension.

**CRITICAL: Azure portal uses cross-origin iframes** (`sandbox-*.reactblade.portal.azure.net`) for grid/table content. Standard `document.querySelectorAll` CANNOT reach them. You MUST use `page.frames()` to iterate all frames.

**Use the dom_scrubber.py module to generate the scrub script:**
```bash
python -c "
from F_home_azure_screenshot.lib.dom_scrubber import generate_scrub_js
js = generate_scrub_js(
    username='jburchel',
    subscription_name='jburchel BAMI subscription',
    tenant_display_name='Microsoft Customer Led',
    custom_replacements={
        'my-real-rg': 'contoso-rg',
        'DefaultResourceGroup-EUS': 'contoso-default-eus',
    },
)
with open('temp_scrub.js', 'w') as f:
    f.write(js)
"
playwright-cli run-code "$(cat temp_scrub.js)"
```

**Or inline, using the frame-aware pattern:**
```bash
playwright-cli run-code "async page => {
  const rules = [
    {isRegex: true, pattern: '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', flags: 'gi', replacement: 'aaaa0a0a-bb1b-cc2c-dd3d-eeeeee4e4e4e'},
    {isRegex: true, pattern: 'jburchel', flags: 'gi', replacement: 'john'},
    {isRegex: false, pattern: 'BAMI subscription', replacement: 'Contoso subscription'},
    // Add more rules as needed
  ];
  const frames = page.frames();
  let total = 0;
  for (const frame of frames) {
    try {
      const count = await frame.evaluate((r) => {
        let replaced = 0;
        function walk(root) {
          const w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT, null);
          let n; const textNodes = [];
          while (n = w.nextNode()) {
            if (n.nodeType === 1) {
              if (n.shadowRoot) walk(n.shadowRoot);
              continue;
            }
            textNodes.push(n);
          }
          for (const tn of textNodes) {
            let t = tn.textContent; let changed = false;
            for (const rule of r) {
              let nt = rule.isRegex
                ? t.replace(new RegExp(rule.pattern, rule.flags), rule.replacement)
                : t.split(rule.pattern).join(rule.replacement);
              if (nt !== t) { t = nt; changed = true; }
            }
            if (changed) { tn.textContent = t; replaced++; }
          }
        }
        walk(document.body);
        document.querySelectorAll('*').forEach(el => { if (el.shadowRoot) walk(el.shadowRoot); });
        return replaced;
      }, rules);
      total += count;
    } catch(e) {}
  }
  return { framesProcessed: frames.length, totalReplaced: total };
}"
```

**Why this approach is preferred:**
1. The browser renders replacement text natively in Segoe UI at the correct size
2. No pixel-level font matching needed
3. Handles cross-origin iframes that pixel-level approaches cannot detect
4. The screenshot is "clean" from the start
5. Verified to produce 56+ replacements on a real Azure portal page

### Phase 8: Callout Boxes

**CRITICAL: Never hardcode callout coordinates.** Always find elements via DOM inspection across all frames.

**Common mistakes to avoid:**
- DO NOT guess coordinates based on "typical layout" or approximate y positions
- DO NOT use text bounding boxes alone; buttons have icons (+, arrows) that must be included
- DO NOT assume menu items are at specific positions; portal layouts vary by subscription, screen size, and which sections are expanded
- ALWAYS inspect the actual DOM element and walk up to its interactive container (button, link, list item) to get the full visual bounds including icons
- DO NOT draw callout borders that clip through adjacent UI elements (e.g., a "copy to clipboard" button next to a text field). When highlighting a form field, expand the bounding box to include ALL sibling controls within the same form row (copy buttons, show/hide toggles, etc.)
- When the callout target is a labeled field (like "KEY 1" or "Endpoint"), find the outermost form container that includes the label, the value, AND any action buttons (copy, regenerate, show/hide). Use that full container's bounding box.

**Finding callout targets robustly:**

The correct approach is to search ALL frames for the target element, find its interactive container (the button/link/menu-item ancestor that includes icons), and use that container's bounding box:

```bash
playwright-cli run-code "async page => {
  const targets = [
    { text: 'Generate/Import', area: 'toolbar', role: 'button' },
    { text: 'Secrets', area: 'nav', role: 'menuitem' },
  ];
  const results = {};
  const frames = page.frames();
  for (const target of targets) {
    for (const frame of frames) {
      try {
        const match = await frame.evaluate((t) => {
          // Find elements containing the target text
          const candidates = [];
          for (const el of document.querySelectorAll('*')) {
            if (!el.textContent.includes(t.text)) continue;
            const r = el.getBoundingClientRect();
            if (r.width === 0 || r.height === 0 || r.top < 0 || r.top > window.innerHeight) continue;
            // Score: prefer direct text match, correct area, correct role
            let score = 0;
            const directText = Array.from(el.childNodes).filter(n => n.nodeType === 3).map(n => n.textContent.trim()).join(' ');
            if (directText === t.text) score += 30;
            else if (directText.includes(t.text)) score += 10;
            if (t.area === 'nav' && r.x < 300) score += 10;
            if (t.area === 'toolbar' && r.y < 200 && r.x > 250) score += 10;
            const role = el.getAttribute('role') || '';
            const tag = el.tagName.toLowerCase();
            if (t.role === 'button' && (tag === 'button' || role === 'button' || tag === 'a')) score += 15;
            if (t.role === 'menuitem' && (role === 'menuitem' || role === 'treeitem' || tag === 'li')) score += 15;
            candidates.push({ el, score });
          }
          if (!candidates.length) return null;
          candidates.sort((a, b) => b.score - a.score);
          // Walk up from best match to find the interactive container (includes icons)
          let el = candidates[0].el;
          for (let i = 0; i < 5 && el.parentElement; i++) {
            el = el.parentElement;
            const tag = el.tagName.toLowerCase();
            const role = el.getAttribute('role') || '';
            const cls = (el.className || '').toString().toLowerCase();
            if (tag === 'a' || tag === 'button' || tag === 'li' ||
                role === 'menuitem' || role === 'treeitem' || role === 'button' ||
                cls.includes('menu-item') || cls.includes('listview-item') ||
                cls.includes('command') || cls.includes('btn')) {
              const r = el.getBoundingClientRect();
              if (r.width > 0 && r.width < 400 && r.height < 80) break;
            }
          }
          const r = el.getBoundingClientRect();
          return { x: Math.round(r.x), y: Math.round(r.y), width: Math.round(r.width), height: Math.round(r.height) };
        }, target);
        if (match) { results[target.text] = match; break; }
      } catch(e) {}
    }
  }
  return results;
}"
```

**Then use those coordinates for callouts** (with 4px padding added by the image_editor automatically).

**Callout specifications (per Microsoft contributor guide):**
- Color: RGB **233, 28, 28** (hex #E91C1C)
- Border thickness: **3px**
- Rectangle should "hug" the element with ~4px padding
- Maximum 3-4 callouts per screenshot
- Use numbered callouts for sequential steps if needed

**When recreating callouts from original screenshots:** Study the original image carefully to identify WHICH elements have red boxes, then use the DOM finder above to locate those same elements in the recaptured page.

**Handling hidden navigation items:**

Some portal navigation panes hide items behind a "More" or "Show more" button. If an expected nav item (e.g., "Playgrounds", "Fine-tuning") is not found in the left navigation pane:

1. Look for a "More" or "Show more" button at the bottom of the nav list
2. Click it to expand the full list of nav items
3. Retry finding the target nav item

This is particularly common in Azure AI Foundry portal (docs in the `foundry/` folder, NOT `foundry-classic/`). See `lib/repo_config.py` for the list of known hidden nav items per repo.

```bash
playwright-cli run-code "async page => {
  // Example: expand hidden nav items in AI Foundry
  const moreBtn = await page.locator('button:has-text(\"More\"), button:has-text(\"Show more\")').first();
  if (await moreBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
    await moreBtn.click();
    await page.waitForTimeout(500);
  }
}"
```

### Phase 8.5: Navigation Validation Gate

After navigating to the target page, validate that you reached the correct page before capturing.

**Validation checks:**

1. **Title/breadcrumb match**: Does the page title or breadcrumb trail match the expected resource type from the doc?
2. **URL resource provider**: Does the URL contain the expected resource provider (e.g., `Microsoft.CognitiveServices` vs `Microsoft.OpenAI`)?
3. **Service identity**: If the doc mentions "Azure OpenAI", verify you are on an OpenAI resource, not a generic Cognitive Services resource
4. **JSON view validation**: When the doc shows a JSON view, verify expected JSON properties (like `networkAcls`, `sku`, `kind`) appear in the page

```bash
playwright-cli run-code "async page => {
  const url = page.url();
  const title = await page.title();
  const breadcrumb = await page.locator('[aria-label=\"Breadcrumb\"], .fxs-breadcrumb').textContent().catch(() => '');
  return { url, title, breadcrumb };
}"
```

**Self-correction on failure:**

If validation fails, attempt to navigate to the correct resource before flagging an error:
- Wrong resource type? Navigate to the correct resource via the portal search bar
- Wrong service? Check if the service has been renamed and use the current name
- Still failing? Flag as `NAVIGATION_FAILURE` using `lib/failure_analyzer.py` and continue to the next screenshot

```python
from lib.failure_analyzer import classify_failure

result = classify_failure(
    expected_url_fragment="Microsoft.OpenAI",
    actual_url=page_url,
    expected_title_keywords=["Azure OpenAI"],
    actual_title=page_title,
)
# result.category, result.severity, result.explanation, result.recommendation
```

### Phase 9: Final Review in GIMP

The processor automatically opens the result in GIMP. In GIMP, the user should:
1. Verify PII is fully redacted
2. Check callout placement
3. Adjust crop if needed
4. Verify the image looks natural and professional
5. Export as PNG (File > Export As > .png)

**GIMP location:** `C:\Program Files\GIMP 2\bin\gimp-2.10.exe`

If GIMP is already open, images open in the existing window.

### Phase 10: Summary Report

After processing, the skill outputs a summary:
- Image dimensions and file size
- Number of PII items detected and redacted
- Each PII item: original value, type, severity, replacement value, pixel location
- Number of callout boxes drawn
- Whether cropping was applied
- **Failure category and severity** for each screenshot (see [Failure Categories Reference](#failure-categories-reference))
- **Human-readable explanation** of what went wrong, if applicable
- **Recommendation** for the human reviewer (e.g., "Re-run with admin credentials", "Update doc to reflect service rename")
- **Report badge** (emoji + label) for each entry in the HTML comparison report

### Phase 10.5: Post-Capture Validation Pipeline

After each screenshot capture, run the validation pipeline before moving to the next image.

**PII post-scan:**
Run a final PII scan on the captured screenshot's DOM text. If PII remains after scrubbing, flag the capture as `PII_LEAK` and retry the scrub-and-capture cycle.

**Page change analysis:**

```python
from lib.page_change_analyzer import analyze_changes

changes = analyze_changes(
    original_title="Create a resource - Azure AI services",
    captured_title="Create a resource - Azure OpenAI",
    original_service="Azure AI services",
    captured_service="Azure OpenAI",
)
# changes.has_rename, changes.rename_details, changes.layout_changed
```

Compare original vs. captured page titles and detect service renames or significant UI restructuring. Flag cases where the documentation itself may need updating beyond just the screenshot.

**Additional checks:**
- **Privilege failures**: Search DOM text for "Access denied", "Forbidden", "You don't have permission", "Unauthorized". Flag as `PRIVILEGE_FAILURE`.
- **Callout target verification**: Confirm that all expected callout target elements were found and that callout boxes were drawn at valid positions.
- **Visual similarity**: Compare the original and captured screenshots for gross structural differences (layout changes, missing panels, completely different pages).

**Failure classification:**

```python
from lib.failure_analyzer import classify_failure, FailureReport

report = classify_failure(
    pii_scan_result=pii_result,
    page_changes=changes,
    callout_results=callout_hits,
    dom_text=captured_dom_text,
)
# report.category (e.g., "PII_LEAK", "PRIVILEGE_FAILURE")
# report.severity ("error", "warning", "info")
# report.explanation (human-readable)
# report.recommendation (what the reviewer should do)
# report.badge (emoji + label for HTML report)
```

If any check fails, generate a `FailureReport` with an actionable explanation. The report is included in the Phase 10 summary and the comparison HTML report.

---

## Scenario: Parsing an Existing Article for Screenshot Refresh

When given an existing markdown article, follow this process:

### Step 1: Read the article and extract image references

```bash
# Read the article
cat /path/to/article.md
```

Look for image references in either format:
- `:::image type="content" source="media/article-name/image-name.png" alt-text="Description.":::`
- `![Description](media/article-name/image-name.png)`

### Step 2: For each image, determine what it shows

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
- **Failure category and explanation** for any captures that did not succeed (see [Failure Categories Reference](#failure-categories-reference))
- **Page change flags** when the service has been restructured or renamed since the original screenshot
- **Recommendation for human reviewer**: What action to take (approve, re-capture with different credentials, update doc text, etc.)

### Step 6: Offer cleanup

Ask the user whether to delete provisioned resources.

---

## PII Replacement Reference

### Approved GUIDs (from MS Sensitive Identifiers Reference)

| Type | Example Approved Value |
|------|----------------------|
| Application (client) ID | `00001111-aaaa-2222-bbbb-3333cccc4444` |
| Certificate ID (SEV 0) | `0a0a0a0a-1111-bbbb-2222-3c3c3c3c3c3c` |
| Correlation ID | `aaaa0000-bb11-2222-33cc-444444dddddd` |
| Directory (tenant) ID | `aaaabbbb-0000-cccc-1111-dddd2222eeee` |
| Object ID | `aaaaaaaa-0000-1111-2222-bbbbbbbbbbbb` |
| Principal ID | `aaaaaaaa-bbbb-cccc-1111-222222222222` |
| Resource ID | `a0a0a0a0-bbbb-cccc-dddd-e1e1e1e1e1e1` |
| Secret ID/Key ID (SEV 0) | `aaaaaaaa-0b0b-1c1c-2d2d-333333333333` |
| Subscription ID | `aaaa0a0a-bb1b-cc2c-dd3d-eeeeee4e4e4e` |
| Trace ID | `0000aaaa-11bb-cccc-dd22-eeeeee333333` |

### Approved Non-GUID Values

| Type | Example |
|------|---------|
| Client Secret | `Aa1Bb~2Cc3.-Dd4Ee5Ff6Gg7Hh8Ii9_Jj0Kk1Ll2` |
| Alphanumeric | `A1bC2dE3fH4iJ5kL6mN7oP8qR9sT0u` |
| Thumbprint | `AA11BB22CC33DD44EE55FF66AA77BB88CC99DD00` |
| Signature Hash | `aB1cD2eF-3gH4iJ5kL6-mN7oP8qR=` |

### Approved Fictitious Names (CELA-approved)

| Category | Approved Values |
|----------|----------------|
| Company domains | `contoso.com`, `fabrikam.com`, `northwindtraders.com`, `adventure-works.com` |
| Generic domains | `example.com`, `example.org`, `example.net` |
| Email format | First name only: `john@contoso.com` (NOT `john.smith@contoso.com`) |
| Resource groups | `contoso-rg`, `fabrikam-rg`, `myresourcegroup` |
| VMs | `contoso-vm`, `fabrikam-vm-01`, `myVM` |
| Storage accounts | `contosostorageacct`, `fabrikamstorage` |
| Key vaults | `contoso-kv`, `fabrikam-keyvault` |

### Safe IP Ranges for Documentation

- Private: `10.x.x.x`, `172.16-31.x.x`, `192.168.x.x`
- RFC 5737: `192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`
- Azure wire server: `168.63.129.16`
- Loopback: `127.0.0.0/8`
- Link-local: `169.254.0.0/16`

---

## Image Requirements Checklist

- [ ] PNG format, lowercase `.png` extension
- [ ] Filename: lowercase, letters/numbers/hyphens only (no spaces)
- [ ] Max width: 1200px
- [ ] Target size: under 200 KB
- [ ] Gray border added (automatic with processor)
- [ ] First screenshot in article: full browser frame (URL bar + controls)
- [ ] Default Azure theme (dark blue sidebars, blue background)
- [ ] `?feature.customportal=false` in portal URL
- [ ] All PII replaced with approved fictitious values
- [ ] Callout boxes: RGB 233,28,28, 3px thickness
- [ ] Alt text prepared (descriptive, ends with period)
- [ ] Image naming follows: `service-technology-image-description.png`

---

## Common Azure Portal Popup Patterns

These are elements you'll frequently need to dismiss:

| Popup Type | Selector Pattern |
|-----------|-----------------|
| Welcome dialog | `button:has-text("Got it")`, `button:has-text("Maybe later")` |
| Preview banner | `[class*="preview-banner"] button`, `[class*="fxs-banner"] button` |
| Notification toast | `.fxs-toast-container button` |
| What's new | `button:has-text("What's new")` parent close button |
| Feature announcement | `[data-telemetryname="DismissButton"]` |
| Generic close | `[aria-label="Close"]`, `[aria-label="Dismiss"]` |
| Consent/cookie | `button:has-text("Accept")`, `button:has-text("OK")` |

---

## Lib Module Reference

All Python modules are at `lib/` (relative to the skill root):

- **`screenshot_processor.py`**: Main orchestrator. CLI interface for full pipeline.
- **`pii_detector.py`**: Regex-based PII detection with context-aware GUID classification. All approved replacement values built in.
- **`image_editor.py`**: Pillow/OpenCV operations: crop, redact, callout, border, optimize.
- **`dom_scrubber.py`**: Frame-aware DOM PII replacement. Generates JS that uses `page.frames()` to scrub ALL frames including cross-origin Azure portal iframes. **This is the preferred pre-screenshot approach.**
- **`gimp_bridge.py`**: GIMP integration (detect running instance, open images).
- **`extract_dom_info.js`**: JavaScript payload for `playwright-cli run-code` DOM extraction (Shadow DOM aware).
- **`repo_config.py`**: Repo-specific customization system. Embeds knowledge about supported repos (path rules, service renames, nav hints, portal privilege notes). Use `detect_repo_from_path()` to auto-detect the repo and `get_path_rules()` for doc-specific behavior.
- **`doc_analyzer.py`**: Doc-driven interaction analyzer. Parses markdown to extract image references, interaction steps, flyout requirements, and data requirements. Used in Phase 2.5 to understand what each screenshot should show.
- **`page_change_analyzer.py`**: Detects significant page changes by comparing titles, service names, and layout. Flags cases where docs need updating beyond screenshot replacement.
- **`failure_analyzer.py`**: Classifies capture failures into actionable categories (`PRIVILEGE_FAILURE`, `PII_LEAK`, `NAVIGATION_FAILURE`, etc.) with severity, explanation, and recommendation. Generates HTML badges for the comparison report.

---

## Repo-Specific Customizations

The skill supports repo-specific configuration through `lib/repo_config.py`, which embeds repo-specific knowledge directly in the skill code. This design is intentional: the skill can be run from anywhere and still understand how to interact with any supported repo. No external config files are needed.

**How it works:**
- `detect_repo_from_path(article_path)` identifies which repo the article belongs to based on the file path or git remote
- `get_path_rules(repo, article_path)` returns path-specific rules that affect navigation, provisioning, and validation
- Repo owners add their config via PR to `lib/repo_config.py`

**Currently supported repos:**

| Repo | Key Customizations |
|------|-------------------|
| `azure-ai-docs-pr` | AI Foundry nav hints (hidden "More" button items), Azure OpenAI vs. Cognitive Services routing, model deployment prerequisites |
| `fabric-docs-pr` | Fabric admin privilege requirements, workspace provisioning hints, capacity-dependent feature flags |

**Config includes:**
- **Path rules**: Which doc paths map to which portal sections and resource types
- **Service renames**: Old-to-new service name mappings for navigation and validation
- **Navigation hints**: Portal-specific interaction quirks (hidden nav items, expandable menus, multi-step navigation)
- **Portal privilege notes**: Pages that require specific roles or elevated access
- **Known hidden nav items**: Items behind "More" buttons, per portal and doc path

---

## Failure Categories Reference

Each capture attempt is classified into one of the following categories. The badge is shown in the HTML comparison report.

| Category | Badge | Description | Example |
|----------|-------|-------------|---------|
| `CAPTURE_SUCCESS` | ✅ Success | Screenshot matches expectations | Normal successful capture |
| `PRIVILEGE_FAILURE` | 🔒 Privilege | Insufficient permissions to access the page or resource | Cannot access Fabric Admin portal without admin role |
| `NAVIGATION_FAILURE` | ❌ Navigation | Landed on the wrong page after navigation | Went to Cognitive Services overview instead of Azure OpenAI |
| `DATA_SETUP_FAILURE` | ❌ Data Setup | Cannot create the required data for the screenshot | Doc describes a fine-tuned model deployment we cannot provision |
| `UI_MISMATCH` | ⚠️ UI Mismatch | Page looks fundamentally different from the original screenshot | Service restructured with a completely new layout |
| `PII_LEAK` | 🚨 PII Leak | PII detected in the final screenshot after scrubbing | Real email address still visible in a cross-origin iframe |
| `DOC_INSUFFICIENT` | 📄 Doc Gap | Doc text lacks sufficient detail to reproduce the screenshot | Steps do not describe how to reach the target page |
| `ELEMENT_NOT_FOUND` | 🔍 Not Found | Expected UI element is missing from the page | "Playgrounds" not in nav, "More" button also not found |
| `SERVICE_RESTRUCTURED` | ⚠️ Restructured | Service has been renamed or reorganized since the doc was written | Form Recognizer is now Document Intelligence |
