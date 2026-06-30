# Full Workflow: Phases 0-10.5

_Reference for the docs-screenshot skill. See [`SKILL.md`](../SKILL.md) for the trigger-time prompt and high-level usage._


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

**Prerequisite auto-detection:** Before doing anything else, check for required tools and install any that are missing. Do NOT ask the user to install prerequisites manually. If something is missing, install it automatically and inform the user what was installed.

1. **Python 3.10+**: Check if `python --version` returns 3.10 or higher. Python is the only prerequisite that cannot be reliably auto-installed. If missing, tell the user: *"Python 3.10+ is required but not found. Please install it from https://www.python.org/downloads/ and restart Copilot CLI."* Then stop.

2. **Azure CLI**: Check if `az` is available. If not, install it:
   ```bash
   winget install --id Microsoft.AzureCLI --accept-source-agreements --accept-package-agreements
   ```
   Then prompt the user to run `az login` if not already authenticated.

3. **GitHub CLI**: Check if `gh` is available. If not, install it:
   ```bash
   winget install --id GitHub.cli --accept-source-agreements --accept-package-agreements
   ```
   Then check `gh auth status`; if not authenticated, prompt the user to run `gh auth login`.

4. **Node.js 18+**: Check if `node --version` returns 18 or higher. If not, install it:
   ```bash
   winget install --id OpenJS.NodeJS.LTS --accept-source-agreements --accept-package-agreements
   ```
   Note: a new terminal may be needed for `node` to appear on PATH after install.

5. **Python Pillow**: Verify Pillow is installed (needed for image processing):
   ```bash
   python -c "from PIL import Image; print('Pillow OK')" || pip install Pillow
   ```


> **WSL2 / Linux users:** Steps 2–4 above use `winget`, which is Windows-only. On Linux or WSL2, install the same tools with your system package manager instead:
>
> ```bash
> # Azure CLI
> curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
>
> # GitHub CLI
> (type -p wget >/dev/null || sudo apt install wget -y) \
>   && sudo mkdir -p -m 755 /etc/apt/keyrings \
>   && out=$(mktemp) && wget -nv -O$out https://cli.github.com/packages/githubcli-archive-keyring.gpg \
>   && cat $out | sudo tee /etc/apt/keyrings/githubcli-archive-keyring.gpg > /dev/null \
>   && sudo chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg \
>   && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null \
>   && sudo apt update && sudo apt install gh -y
>
> # Node.js 18+ (via NodeSource)
> curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -
> sudo apt install -y nodejs
>
> # Edge for Linux (headless — no display server needed)
> curl https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor > microsoft.gpg
> sudo install -o root -g root -m 644 microsoft.gpg /etc/apt/trusted.gpg.d/
> echo "deb [arch=amd64] https://packages.microsoft.com/repos/edge stable main" | sudo tee /etc/apt/sources.list.d/microsoft-edge.list
> sudo apt update && sudo apt install -y microsoft-edge-stable
> rm microsoft.gpg
>
> # GIMP (optional)
> sudo apt install -y gimp
> ```
>
> Edge for Linux runs headless without X11/Wayland. Sign in to Edge once (`microsoft-edge --no-sandbox https://portal.azure.com`) to establish your SSO session, then the skill's headless browser will pick it up.

6. **Playwright MCP tools already loaded**: Check if tools like `playwright-browser_navigate`, `playwright-browser_snapshot`, `playwright-browser_click` are in the available tool list. If so, use them directly. No installation needed.

7. **Playwright MCP server installable**: If Playwright MCP tools are not available, install and configure the Playwright MCP server automatically:
   ```bash
   npx @playwright/mcp@latest --headless --browser msedge
   ```
   Then use the `configure-copilot` agent (or equivalent) to add the MCP server configuration so the tools become available.

The bash examples throughout this guide use the `playwright-cli` command-line interface. If the Playwright MCP server is loaded into the agent (tools named `playwright-browser_navigate`, `playwright-browser_snapshot`, `playwright-browser_click`, `playwright-browser_evaluate`, etc.), call those tools directly instead of shelling out to `playwright-cli` — each MCP tool maps 1:1 to a `playwright-cli` subcommand. The examples here favor `playwright-cli` because they're copy-pasteable into a shell and unambiguous about arguments.

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

**Pre-capture viewport expansion:** Before taking the screenshot, verify that ALL elements you plan to highlight with callouts are within the viewport. If any element is below the fold (e.g., a copy button pushed below the visible area by a tall dialog), **expand the viewport height** to accommodate it. Never accept a screenshot where a callout target is invisible.

```bash
# Check if all callout targets are visible. If the farthest target's bottom
# edge exceeds the viewport, increase the viewport height.
playwright-cli run-code "async page => {
  // Find the lowest callout target element (adapt selectors to your targets)
  const targets = ['button:has-text(\"Copy\")', '.copy-button', '[aria-label=\"Copy\"]'];
  let maxBottom = 0;
  for (const sel of targets) {
    const el = await page.locator(sel).first();
    if (await el.isVisible({ timeout: 1000 }).catch(() => false)) {
      const box = await el.boundingBox();
      if (box) maxBottom = Math.max(maxBottom, box.y + box.height);
    }
  }
  const viewport = page.viewportSize();
  if (maxBottom > viewport.height - 20) {
    const newHeight = Math.ceil(maxBottom + 60); // 60px padding below target
    await page.setViewportSize({ width: viewport.width, height: newHeight });
    await page.waitForTimeout(500); // let layout settle
    return { expanded: true, oldHeight: viewport.height, newHeight };
  }
  return { expanded: false, height: viewport.height };
}"
```

**IMPORTANT:** After expanding the viewport height, you MUST retake the screenshot at the new size. The wider viewport ensures all elements render at their natural positions rather than being pushed off-screen. After capture, you can crop back to the relevant area using `--crop-focus`.

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
- `--no-callouts`: Skip callout box drawing entirely (useful when callout positions cannot be reliably determined, or when the user wants a clean screenshot without annotations)
- `--no-gimp`: Don't open in GIMP
- `--callouts`: JSON array of rectangles for red callout boxes
- `--crop-focus`: JSON array of rectangles defining area of interest

### Phase 7: Pre-Screenshot DOM Scrubbing (PREFERRED Method)

The most reliable approach is to replace PII directly in the DOM BEFORE taking the screenshot. This is the same approach as Microsoft's Screenshot Scrubber extension.

**CRITICAL: Azure portal uses cross-origin iframes** (`sandbox-*.reactblade.portal.azure.net`) for grid/table content. Standard `document.querySelectorAll` CANNOT reach them. You MUST use `page.frames()` to iterate all frames.

**Use the dom_scrubber.py module to generate the scrub script:**
```bash
python -c "
from lib.dom_scrubber import generate_scrub_js
js = generate_scrub_js(
    username='myalias',
    subscription_name='My Subscription',
    tenant_display_name='My Tenant',
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
    {isRegex: true, pattern: 'myalias', flags: 'gi', replacement: 'john'},
    {isRegex: false, pattern: 'My Subscription', replacement: 'Contoso subscription'},
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

**Avatar scrubbing:** The DOM scrubber also replaces user profile avatars with a generic person icon. It detects avatar images by:
- CSS class patterns: `avatar`, `persona`, `profile`, `user-photo`
- Azure portal containers: `.fxs-avatarmenu-tenant-image`, `.fxs-avatar`
- Microsoft Graph image URLs: `graph.microsoft.com`, `graph.windows.net`
- Heuristic: small (20-80px) circular images with `border-radius: 50%`

This prevents the user's actual face from appearing in published screenshots. The replacement is a neutral gray silhouette SVG. This is handled automatically by `dom_scrubber.py`; no additional configuration is needed.

### Phase 8: Callout Boxes

**CRITICAL: Never hardcode callout coordinates.** Always find elements via DOM inspection across all frames.

**Common mistakes to avoid:**
- DO NOT guess coordinates based on "typical layout" or approximate y positions
- DO NOT use text bounding boxes alone; buttons have icons (+, arrows) that must be included
- DO NOT assume menu items are at specific positions; portal layouts vary by subscription, screen size, and which sections are expanded
- ALWAYS inspect the actual DOM element and walk up to its interactive container (button, link, list item) to get the full visual bounds including icons
- DO NOT draw callout borders that clip through adjacent UI elements (e.g., a "copy to clipboard" button next to a text field). When highlighting a form field, expand the bounding box to include ALL sibling controls within the same form row (copy buttons, show/hide toggles, etc.)
- When the callout target is a labeled field (like "KEY 1" or "Endpoint"), find the outermost form container that includes the label, the value, AND any action buttons (copy, regenerate, show/hide). Use that full container's bounding box.

**Icon inclusion rule (MANDATORY):** When a menu item, button, or list item has an icon immediately beside its text (an SVG, `<i>`, or `<img>` element), the callout box MUST include the full icon. The `callout_finder.js` script handles this automatically by computing the union bounding rect of the interactive container AND all of its visible children. However, when manually specifying callout coordinates, always verify that icons are fully enclosed. If an icon is partially outside the container's layout box (e.g., absolutely positioned), the finder expands the rect to cover it.

**Vertical centering rule (MANDATORY):** The callout box must vertically center on the target text, NOT on the container element's bounding box. Some Azure portal elements have asymmetric internal padding (e.g., more padding-top than padding-bottom). If the callout box is positioned around the container, the text may appear off-center (e.g., tight against the bottom edge but with a large gap at the top). The `callout_finder.js` detects this and re-centers the box symmetrically around the text node's vertical midpoint.

**Dropdown/select control rule:** When the callout target is inside a dropdown (`<select>`, `role="combobox"`, `.dropdown`, etc.), the bounding box MUST encompass the entire dropdown control, including the chevron/indicator arrow on the right. Never clip through the dropdown border. The `callout_finder.js` detects dropdown containers and walks up to the full control element.

**Never-clip rule (MANDATORY):** Callout rectangles MUST NOT extend beyond the visual boundary of the containing popup, flyout, context menu, or dropdown panel. If a callout target is inside a popup, the callout box is automatically clamped to the popup's bounds (with a 2px inset margin). This prevents callout lines from slashing through panel borders, dropdown indicators, or adjacent graphics. The `callout_finder.js` enforces this by walking up to the nearest panel/popup/menu ancestor and clamping the rect.

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

**When recreating callouts from original screenshots:** This is a MANDATORY step, never optional. Before saving any recaptured screenshot:

1. **Run `verify_callouts.py` on the ORIGINAL** to get the exact count and positions of callout boxes in the original image. This is the source of truth for how many callouts you need.
2. **Examine the original image** to identify WHICH element each red callout box highlights. Match each detected box to a specific UI element (e.g., "KEY 1 field", "Networking nav link"). **Do NOT add callouts for elements that have no red box in the original.** If the original has 3 callouts, the captured image must have exactly 3; not 2, not 4.
3. **Cross-reference with the doc text** to understand which elements the doc instructs the user to interact with (e.g., "Select **Playgrounds** from the left pane" means Playgrounds gets a callout). The doc text confirms your identification from step 2 but does NOT add extra callouts beyond what the original shows.
4. **Use the DOM finder WHILE THE PAGE IS STILL LIVE** to get exact bounding boxes for every callout target. NEVER estimate callout positions from pixel scans of the saved screenshot. The DOM gives pixel-perfect coordinates; manual pixel guessing does not. Capture the coordinates in the same browser session, before or immediately after taking the raw screenshot.
   - For left-nav items: search for the text, walk up to the `<a>` or `<li>` container, get `getBoundingClientRect()`
   - For radio buttons/checkboxes: search for the label text, get the parent element's rect
   - For buttons: search for button text, walk up to the `<button>` element, get its rect
   - **Center every box**: `centerY = (top + bottom) / 2`, then `box = (centerY - halfHeight, centerY + halfHeight)`
4. **Draw ALL callout boxes** that appear in the original. Never save a recaptured screenshot without matching the original's callouts.
5. **Verify tab/state selection**: If the doc says "Select the X tab", you must click that tab AND draw a callout on it. If the doc says "select X radio button", the radio button must be selected AND have a callout.
6. **Run `verify_callouts.py`** to deterministically confirm the captured image has at least as many callout boxes as the original:
   ```bash
   python lib/verify_callouts.py originals/image.png captured/image.png
   ```
   If this fails, you MUST add the missing callout(s) before proceeding. This is a hard gate; no screenshot is considered complete until it passes.
   
   **Common callout pitfalls to avoid:**
   - Callout boxes that are too close vertically (< 15px gap) may be merged by the detector. Ensure each callout is visually distinct.
   - Button callout boxes must fully enclose the button text AND icon. If the button is 36px tall, the callout must be at least 40px tall (with 2px padding each side).
   - When a radio button or tab has a callout, the box must surround the FULL text label, not just the radio circle/tab indicator.
   - **Always center the callout box on the target text.** Do NOT position the box by aligning its top edge to the element's top edge. Instead: find the text's vertical center (`center_y = (top + bottom) / 2`), then compute the box symmetrically as `(center_y - half_height, center_y + half_height)`. This prevents asymmetric margins (e.g., lots of space above the text but none below).
   - **Never clip through icons or graphics.** If the callout rect would extend beyond the edge of a popup, dropdown, or panel, clamp it to that boundary. Icons immediately adjacent to text on a menu item MUST be fully enclosed.
   - **Dropdown controls:** When highlighting a dropdown/select, the callout must frame the ENTIRE control including the chevron indicator. Do NOT let the callout border cut through the dropdown arrow or the control's right edge.

**Skipping callouts (`nocallouts` mode):** When callout positions cannot be reliably determined (e.g., complex dynamically-rendered UI, or when the user explicitly requests a clean screenshot), use the `--no-callouts` flag on `screenshot_processor.py` or simply omit the `--callouts` argument. The user or invoking agent can request `nocallouts` in their prompt to skip all callout box drawing.

**Handling hidden navigation items:**

Some portal navigation panes hide items behind a "More" or "Show more" button. If an expected nav item (e.g., "Playgrounds", "Fine-tuning") is not found in the left navigation pane:

1. Look for a "More" or "Show more" button at the bottom of the nav list
2. Click it to expand the full list of nav items
3. Retry finding the target nav item

**Azure AI Foundry specific:** The Foundry portal has two experiences: "New Foundry" and "Classic". When navigating to a Foundry project, the portal may default to one or the other. If the nav pane does not show the expected items (Playgrounds, Fine-tuning, Models + endpoints, etc.):

1. Look for a toggle or selector at the top of the page to switch between "New Foundry" and "Classic" experiences
2. Select "New Foundry" (unless the doc is specifically in the `foundry-classic/` folder)
3. After switching, the left nav items should update to show the expected items
4. If items are still hidden, check for the "... More" button and click to reveal them
5. The "More" dialog may show a message "Some capabilities are only currently supported in default projects." If so, click "Switch to the default project" to reveal items like Fine-tuning that are only available in the default project.
6. Once the target item is visible in the More dialog, **pin it** to the nav pane by clicking the pin icon next to it, then close the dialog.

When a callout target element (like a button or tab) needs to be visible in the screenshot:
- If the element is below the viewport fold, **scroll the content area** to bring it into view before capturing
- Use `element.scrollIntoView({ block: 'center' })` to center it vertically
- Verify both the nav callout target AND the content callout target are visible in the final screenshot

This applies to all docs in the `foundry/` folder of azure-ai-docs-pr (NOT `foundry-classic/`). See `lib/repo_config.py` for the list of known hidden nav items per repo.

```bash
playwright-cli run-code "async page => {
  // Step 1: Switch to New Foundry experience if toggle is available
  const newFoundryToggle = await page.locator('button:has-text(\"New Foundry\"), [aria-label*=\"New Foundry\"]').first();
  if (await newFoundryToggle.isVisible({ timeout: 2000 }).catch(() => false)) {
    await newFoundryToggle.click();
    await page.waitForTimeout(2000);
  }
  
  // Step 2: Expand hidden nav items via More button
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
3. **Service identity**: If the doc mentions "Azure OpenAI", verify you are on an OpenAI resource, not a generic Cognitive Services resource. **Always check the doc text for the specific resource type** (e.g., "Navigate to your Azure OpenAI resource" means kind=OpenAI, NOT kind=CognitiveServices).
4. **Original screenshot match**: If the original screenshot shows a specific resource type label (e.g., "Azure OpenAI" in the heading or breadcrumb), the captured screenshot MUST show the same resource type. Never substitute a generic Cognitive Services resource when the doc and original clearly show Azure OpenAI.
5. **JSON view validation**: When the doc shows a JSON view, verify expected JSON properties (like `networkAcls`, `sku`, `kind`) appear in the page

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

**Best-effort capture when service has been renamed/redirected:**

If the portal redirects you to a renamed service (e.g., "Cognitive Services" became "Azure AI Services"), do NOT simply flag the screenshot as failed and move on. Instead:

1. **Accept the redirect** and work from wherever you landed
2. **Proceed with the remaining steps** described in the doc (expand menus, click nav items, select radio buttons, etc.)
3. **Draw all callout boxes** that the original image shows, targeting the equivalent elements on the current page
4. **Flag it as ⚠️ Page Changed** in the report, but still deliver the best-effort screenshot
5. The human reviewer can then decide whether the screenshot is usable with the new service name or if the doc needs rewriting

This applies to any scenario where the underlying page is structurally the same but the service name or branding has changed. If the page structure is so different that the described steps cannot be followed, then flag as SERVICE_RESTRUCTURED.

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

**GIMP location:**
- **Windows:** `C:\Program Files\GIMP 2\bin\gimp-2.10.exe`
- **Linux/WSL2:** `gimp` (install with `sudo apt install gimp` if missing)

If GIMP is already open, images open in the existing window.

### Phase 10: Summary Report

After processing, the skill outputs a summary:
- Image dimensions and file size
- Number of PII items detected and redacted
- Each PII item: original value, type, severity, replacement value, pixel location
- Number of callout boxes drawn
- Whether cropping was applied
- **Failure category and severity** for each screenshot (see [Failure Categories Reference](failure-categories.md))
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
