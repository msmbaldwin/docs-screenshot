name: docs-screenshot
description: 'docs-screenshot <article-path | description> [nocallouts] [nogimp] [nopii] [help]'
allowed-tools: Bash(playwright-cli:*), Bash(python:*), Bash(az:*), Bash(pwsh:*), Bash(powershell:*), Bash(gimp:*), mcp__playwright__*
---

# Microsoft Documentation Screenshot Skill

Automates the full pipeline for creating documentation screenshots across all Microsoft web portals (Azure, M365, SharePoint, Entra ID, Power Platform, etc.) that comply with Microsoft Learn contributor guidelines: browser automation, resource provisioning, PII redaction with approved fictitious values, callout boxes, smart cropping, and GIMP handoff.

## Usage

When this skill is invoked, parse the user's arguments and proceed accordingly.
If the user says `help`, display the [Detailed Help](#detailed-help) section below and stop.

### Quick Reference

When invoked as `/docs-screenshot`, the skill prefix is stripped. Match the remaining text:

| User's argument | What to do |
|---|---|
| `help` | Display the Detailed Help section (see below) and stop |
| `<article-path>` | **Scenario 2**: Refresh all screenshots in the given markdown article |
| `<description of what to capture>` | **Scenario 1/3**: Capture a new screenshot based on the description |
| `compare` (anywhere in text) | Enable interactive comparison review with local feedback loop (Scenario 2 only) |
| `nocallouts` (anywhere in text) | Skip all callout box drawing |
| `nogimp` (anywhere in text) | Skip opening result in GIMP |
| `nopii` (anywhere in text) | Skip PII detection and redaction (use when PII is already scrubbed via DOM) |

Options can be combined with any scenario. Examples:

```
/docs-screenshot help
/docs-screenshot ~/docs/azure-docs-pr/articles/storage/files/storage-how-to-use-files-windows.md
/docs-screenshot ~/docs/azure-docs-pr/articles/storage/files/storage-how-to-use-files-windows.md compare
/docs-screenshot Take a screenshot of the Azure Key Vault secrets page. nocallouts
/docs-screenshot Capture the VM creation blade with size B2s selected. Add callouts on the Size dropdown and the Review+Create button.
/docs-screenshot ~/docs/azure-docs-pr/articles/storage/files/soft-delete.md nogimp
```

### Detailed Help

**docs-screenshot** captures, processes, and redacts screenshots for Microsoft Learn documentation.

**Scenarios:**

| Scenario | Trigger | Description |
|---|---|---|
| **New article** | Description of what to capture | Provision resources, navigate portal, capture, process |
| **Refresh article** | Path to a `.md` file | Parse article, recapture all screenshots, generate comparison report |
| **Description-only** | Description without article context | Like "New article" but can also work without any pre-existing screenshots; the skill sets up everything from your description |

**Options:**

| Option | Effect |
|---|---|
| `compare` | Enable interactive comparison review. After capturing, starts a local server with side-by-side comparison report. Submit corrections to iterate, or approve all to create a PR. Only applies to Scenario 2 (article refresh). |
| `nocallouts` | Skip callout box drawing entirely. Use when callout positions are unreliable, or when you want a clean base image to annotate manually. |
| `nogimp` | Skip opening the processed screenshot in GIMP. The image is still saved to disk. |
| `nopii` | Skip PII detection and pixel-level redaction. Use when you have already scrubbed PII from the DOM before capture (the preferred approach). |
| `help` | Display this help text and stop. |

**Callout placement rules:**
- Callouts use RGB(233, 28, 28), 3px thickness
- Icons adjacent to menu text are always included in the bounding box
- Text is vertically centered within the callout box
- Dropdown controls include the full chevron indicator
- Callout rects never clip through panel borders or graphics
- Toolbar buttons: walk up to the parent container (li, button, or div with toolbar/command classes) so the bounding box includes the icon element to the left of the text label. Scan children two levels deep to catch icons inside wrapper divs.
- Copy-to-clipboard buttons: match by proximity to the target field (Subscription ID, Tenant ID, etc.), not just the first copy icon on the page
- When smart-cropping, ensure at least 10px margin between any callout box edge and the crop boundary

**Capture interaction rules:**
- Hover cards: when a screenshot needs a hover/tooltip card (e.g., service info card in Favorites), hover over the element, wait 2s for the card to appear, then capture a region that fully includes the card
- Filtered resource lists: apply the filter (select resource groups, close the filter dropdown), THEN capture the resulting filtered list, not the filter dialog itself
- Dashboard dialogs (Edit Markdown, Share): find the dialog container element bounds to determine the crop region, never use hardcoded pixel offsets which shift when the dialog position changes
- Dashboard shared state: when capturing Access Control (IAM) for a shared dashboard, navigate to the resource's IAM page (e.g., subscription or resource group), not the dashboard toolbar

**PII scrubbing:**
- DOM scrubbing (preferred): replaces PII in the live DOM before capture, including cross-origin iframes
- Avatar replacement: user profile photos are replaced with a generic silhouette
- Pixel-level fallback: for canvas/SVG/closed Shadow DOM content
- All replacements use official Microsoft-approved fictitious values (contoso.com, etc.)

**Supported portals:** Azure, M365 Admin, SharePoint, Entra ID, Power Platform, Teams Admin, Exchange, Intune, Defender, Fabric, DevOps

**Post-processing pipeline:**
1. PII redaction (DOM or pixel-level)
2. Callout boxes (unless `nocallouts`)
3. Smart crop to area of interest
4. 1px gray border
5. PNG optimization (target < 200 KB, max 1200px width)
6. Open in GIMP (unless `nogimp`)

**Comparison reports:**
- Scenario 2 (article refresh) with the `compare` flag generates an interactive comparison report
- A local HTTP server starts and serves the report in your browser
- Each screenshot pair includes a feedback textbox for corrections
- Submit with corrections: the skill processes fixes and regenerates the report (iterate until satisfied)
- Submit with no corrections: creates a PR with before/after comparison images for reviewer validation

**Failure categories:** ✅ Success | ⚠️ UI Mismatch | ❌ Navigation Failed | 🔒 Privilege Issue | 🚨 PII Leak | 📄 Doc Gap | 🔍 Element Missing

**Prerequisites:** Windows + Edge (or Linux/WSL2 + Edge for Linux). Everything else (Node.js, Python/Pillow, Azure CLI, GitHub CLI, Playwright MCP) is auto-detected and installed on first run if missing. GIMP is optional.

---

## Three Primary Scenarios

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
2. **Filter out non-screenshot images** (diagrams, icons, conceptual art, flowcharts, architecture diagrams) using `ImageReference.is_screenshot()`. Report skipped images to the user. Only process images that are actual portal/UI screenshots.
3. For each screenshot, read its alt text and surrounding context to understand what it should show
4. Determine the portal URL, required resources, and page state for each screenshot
5. For each screenshot:
   a. Provision resources if needed
   b. Navigate to the correct page
   c. Scrub PII, capture, process
   d. Compare with the original image (dimensions, rough visual similarity)
   e. Save to the correct media/ path with the correct filename
6. Generate a report: which screenshots were updated, which matched, which differed. Include skipped non-screenshot images in the report summary.
7. Open all new screenshots in GIMP for final review

**Example prompt:** *"Update the screenshots in /docs/azure-sql/create-database.md. The article shows creating an Azure SQL database through the portal."*

### Scenario 3: Description-Only (No Existing Screenshot)

The user (or another agent) invokes the skill without an existing screenshot to reference. They describe what the screenshot should show, optionally including callout placement descriptions.

**Example prompts:**
- *"Take a screenshot of the Azure Storage account file shares page showing a file share named 'myfileshare'. Add a callout around the file share name."*
- *"Capture the Azure Key Vault secrets list with the Generate/Import button highlighted. nocallouts"*
- *"Set up a storage account with soft delete enabled, navigate to the file shares blade, and capture it. Add callouts around: 1) the 'File shares' nav item, 2) the soft delete toggle"*

**Workflow:**
1. Parse the user's description to determine:
   - Target portal and page URL
   - Resources to provision (if any)
   - Page interactions needed (clicks, selections, expansions)
   - Callout targets (if described) or `nocallouts` if specified
2. Provision resources as needed (Phase 3)
3. Navigate to the target page (Phases 1-2)
4. Perform any described interactions (click buttons, open flyouts, select tabs)
5. Scrub PII and avatars from the DOM (Phase 7)
6. If callout targets were described:
   a. Use `callout_finder.js` to find each described element's bounding box
   b. Use the callout descriptions to match UI elements (e.g., "the file share name" maps to finding the text "myfileshare" in the page)
7. If `nocallouts` was specified, skip callout detection and drawing entirely (`--no-callouts`)
8. Set viewport size, expanding height if needed (Phase 4)
9. Capture screenshot and process (Phases 5-6)
10. Open in GIMP for review (Phase 9)

**Key differences from Scenario 2:** There is no original screenshot to compare callout counts against, so `verify_callouts.py` comparison is skipped. Instead, the callout count is validated against the user's description: if they asked for 2 callouts, the final image should have exactly 2.

## Limitations

- **Credential-scoped provisioning**: The skill can only create resources the user's credentials allow. If you lack permissions for a specific Azure service, M365 feature, or SharePoint site, the skill cannot provision those resources for you.
- **MFA/Conditional Access**: Some portals may trigger MFA prompts that require manual interaction. The skill will pause and ask for help.
- **Portal-specific quirks**: Each Microsoft portal has unique popup patterns, loading behaviors, and DOM structures. Azure portal is the most thoroughly tested. Other portals may need additional popup dismissal patterns added.
- **Closed Shadow DOM**: Some portal components use closed Shadow DOM that cannot be accessed even via Playwright. In rare cases, post-screenshot pixel-level redaction is needed as a fallback.
- **Dynamic content**: Portals with real-time data (metrics, logs, dashboards) may show different values between captures. The skill scrubs PII but cannot guarantee identical content across runs.
- **Canvas/SVG content**: Charts, graphs, and other canvas/SVG-rendered content cannot be scrubbed via DOM manipulation. These require the pixel-level image editing fallback.

## Quick Start

> **HEADLESS BY DEFAULT:** All browser automation MUST run headless to avoid interfering with (or being interfered by) the user's desktop. The only exception is when MFA or Conditional Access requires manual user interaction; in that case, notify the user, switch to a visible browser temporarily, and return to headless after authentication completes. See [Phase 1 in the phase guide](references/phase-guide.md#phase-1-authentication--setup) for details.

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

## Detailed References

The detailed workflow, reference tables, and module documentation live in [`references/`](references/) to keep this trigger-time prompt small. Read the relevant reference file when you need its content; do not eagerly load all of them.

| When you're working on... | Read |
|---|---|
| Executing any phase of the capture pipeline (auth, navigation, PII scrub, callouts, image processing, validation) | [`references/phase-guide.md`](references/phase-guide.md) |
| Scenario 2 (refreshing screenshots in an existing markdown article) | [`references/scenario-2-walkthrough.md`](references/scenario-2-walkthrough.md) |
| Approved fictitious values for PII replacement (GUIDs, names, IPs) | [`references/pii-replacements.md`](references/pii-replacements.md) |
| Dismissing Azure portal popups and banners | [`references/portal-patterns.md`](references/portal-patterns.md) |
| Understanding what each Python module in `lib/` does | [`references/lib-reference.md`](references/lib-reference.md) |
| Adding or using repo-specific navigation/validation rules | [`references/repo-customizations.md`](references/repo-customizations.md) |
| Classifying or interpreting capture failures | [`references/failure-categories.md`](references/failure-categories.md) |
| Microsoft Learn screenshot contributor rules (sourced from learn.microsoft.com) | [`references/screenshot-guidelines.md`](references/screenshot-guidelines.md) |

