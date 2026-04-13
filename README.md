# docs-screenshot

A Copilot CLI skill that automates screenshot capture across Microsoft web portals (Azure, M365, SharePoint, Entra ID, Power Platform, and more) for Microsoft Learn documentation. Handles browser automation, resource provisioning, PII redaction with official Microsoft-approved fictitious values, callout boxes, cropping, and GIMP handoff.

This skill was created in [this Copilot chat session](https://gist.github.com/jonburchel/2a1f0f25b064f7276a45a2aa2e544970).

## Quick Start for Testers

This section is for docs writers who want to try the skill on their own articles and help improve it. You don't need to be a developer.

### Before you start

> **Use a test or non-production Azure subscription.** The skill may provision resources (resource groups, storage accounts, etc.) to recreate what your article describes. It asks before cleaning up, but use a sandbox subscription to be safe.
>
> **Sign into Edge first.** Open Edge, sign into the Microsoft account you use for Azure portal, and close any "Welcome" tabs. The skill reuses your existing Edge profile and SSO session. If MFA or Conditional Access prompts appear, the skill will pause and ask you to complete them manually.

**You really only need two things to get started:**

| Requirement | Why |
|-------------|-----|
| **Copilot CLI** | The runtime that executes the skill. [Install guide](https://docs.github.com/en/copilot/github-copilot-in-the-cli) |
| **Microsoft Edge** | Already on Windows. Sign in with your Microsoft account before first run. |

**Everything else is auto-installed on first run.** The skill checks for each tool and installs it via `winget` or `pip` if missing, then tells you what it installed:

| Tool | What it's for | Auto-install method |
|------|--------------|---------------------|
| Node.js 18+ | Playwright browser automation | `winget install OpenJS.NodeJS.LTS` |
| Python 3.10+ | Image processing | Must be pre-installed (no reliable silent install) |
| Azure CLI | Resource provisioning | `winget install Microsoft.AzureCLI` |
| GitHub CLI | PR creation from comparison reports | `winget install GitHub.cli` |
| Playwright MCP | Browser control | `npx @playwright/mcp@latest` |
| Pillow | Image editing (crop, callouts, optimize) | `pip install Pillow` |
| GIMP | Final review (optional, skipped if absent) | Not auto-installed |

> **Note:** Python is the one dependency that can't be reliably auto-installed. If you don't have Python 3.10+, install it from [python.org](https://www.python.org/downloads/) before your first run. Check with `python --version`.

### Install the skill

```powershell
git clone https://github.com/jonburchel/docs-screenshot.git
cd docs-screenshot
cmd /c mklink /J "%USERPROFILE%\.copilot\skills\docs-screenshot" "%CD%"
```

Restart Copilot CLI after installing. Verify with `/skills`.

### Find articles to test with

Ask Copilot CLI to find articles you've authored that contain screenshots. Here's a good prompt:

> *"Search for markdown files I've recently modified using `git log --author=<my-alias>` in F:\git\azure-ai-docs-pr. Filter to articles that contain `:::image:::` or `![` references pointing to portal screenshots (not diagrams or conceptual art). Show me the top 5 candidates with their screenshot counts, and let me pick which ones to run."*

Replace `<my-alias>` with your GitHub username or email, and adjust the repo path. The skill works best today with articles in **azure-ai-docs-pr** and **fabric-docs-pr** (these repos have built-in navigation hints and service rename mappings). Other repos will work but may need manual corrections for portal-specific quirks.

### Run a comparison report

Pick an article from the candidates and run with `compare`:

> *"Refresh the screenshots in F:\git\azure-ai-docs-pr\articles\ai-services\document-intelligence\how-to-guides\create-document-intelligence-resource.md compare"*

This captures every screenshot in the article, generates a side-by-side comparison report, and opens it in your browser. See [Interactive Comparison Review](#interactive-comparison-review) for the full workflow.

### Submit improvements from the comparison report

The comparison report has two ways to provide feedback:

**1. Per-screenshot corrections (improves this run)**

Each screenshot pair in the report has a feedback textbox. Type what's wrong ("callout is on the wrong button", "page shows the old service name", "PII visible in the breadcrumb") and click **Submit Corrections**. The skill reprocesses those screenshots and refreshes the report. Repeat until all screenshots look right.

When everything looks good, leave all textboxes empty and click **Submit & Create PR**. This creates a PR in the **docs repo** (e.g., `azure-ai-docs-pr`) with the updated screenshot images and a before/after comparison for reviewers.

**2. Reusable bug reports (improves the skill itself)**

If you notice a pattern the skill consistently gets wrong (missed PII type, portal element it can't find, navigation that always fails), [file an issue](https://github.com/jonburchel/docs-screenshot/issues/new) so we can fix it for everyone. Include:

- **Article path** (e.g., `articles/ai-services/content-safety/quickstart.md`)
- **Screenshot filename** (e.g., `content-safety-overview.png`)
- **Portal/service** (e.g., Azure portal > Content Safety)
- **What went wrong** (e.g., "Callout box covers the entire sidebar instead of just the nav item")
- **Failure category** if shown (e.g., 🔒 Privilege, ❌ Navigation, 🚨 PII Leak)
- **The prompt you used**
- A screenshot or snippet from the comparison report if possible

---

## Three Usage Scenarios

### 1. New Documentation Authoring

You're writing a new article and need screenshots. Describe what you need:

> *"I need a screenshot of the Azure portal showing a VM creation blade. The VM should be named contoso-vm in resource group contoso-rg, size Standard_B2s, running Ubuntu 22.04. Highlight the 'Size' dropdown with a red callout box."*

The skill will:
- Create the resource group and VM (via `az` CLI)
- Open Azure portal in Edge, navigate to the VM creation blade
- Configure the view to match your description
- Scrub any remaining PII from the DOM (including cross-origin iframes)
- Replace user avatars with a generic silhouette
- Capture at 1200x800, add callout box, crop, optimize
- Open in GIMP for your final review
- Ask whether to clean up the provisioned resources

### 2. Existing Documentation Maintenance

You have an article with screenshots that need refreshing:

> *"Update the screenshots in /docs/azure-sql/create-database.md. The UI has changed since these were last captured."*

The skill will:
- Parse the markdown to find all `:::image:::` and `![]()` references
- Read alt text and surrounding steps to understand what each screenshot shows
- Provision any required resources
- Recapture each screenshot at the correct portal page
- Save to the correct `media/` path with the original filename
- Generate a summary report (old vs. new dimensions, changes detected)
- Open all screenshots in GIMP for final review

Add `compare` to enable an interactive side-by-side comparison review (see [Interactive Comparison Review](#interactive-comparison-review)).

### 3. Description-Only (No Existing Screenshot)

You (or another agent) describe what you need without referencing an existing article or screenshot:

> *"Take a screenshot of the Azure Storage file shares page showing a share named 'myfileshare'. Add callouts around the 'File shares' nav item and the share name."*

> *"Capture the Key Vault secrets list. nocallouts"*

The skill will:
- Parse your description to determine the portal page, resources, and interactions
- Provision resources, navigate, set up page state
- Find callout targets from your descriptions (or skip if `nocallouts` is specified)
- Expand the viewport if needed to fit all callout targets
- Scrub PII and avatars, capture, process, and open in GIMP

## Example Prompts

These examples show progressively more complex ways to use the skill, from a single screenshot to batch operations across entire doc sets.

### Single screenshot for a new article

> *"I'm writing a doc about creating an Azure AI Search resource. Take a screenshot of the 'Create Search service' form in the Azure portal, filled out with a resource named contoso-search in the contoso-rg resource group, region East US, Basic tier. Add a red callout box around the pricing tier dropdown."*

### Refresh a single article's screenshots

> *"Refresh the screenshots in F:\git\azure-ai-docs-pr\articles\ai-services\document-intelligence\how-to-guides\create-document-intelligence-resource.md. Read the article, figure out what each screenshot should show, provision any resources needed, recapture each one with PII scrubbed, and save them to the correct media paths."*

### Validate and compare: side-by-side HTML report

> *"Pick 5 articles from F:\git\azure-ai-docs-pr\articles\ai-services that have Azure portal screenshots. For each one, recreate the screenshots based on the article content and alt text. Then generate an HTML comparison page showing every original image side-by-side with your recaptured version. Include callout boxes wherever the originals have them."*

This produces a self-contained HTML report with base64-embedded images, a summary table, PII handling notes, and click-to-zoom on each image. [See an example comparison report.](test-comparison/comparison-report.html)

### Batch refresh by folder

> *"Refresh all screenshots in F:\git\azure-ai-docs-pr\articles\ai-services\content-safety\. Find every markdown file that contains :::image::: references pointing to Azure portal screenshots (not diagrams). For each article, recapture its screenshots and generate a comparison report. Create any Azure resources needed, then ask me before cleaning them up."*

### Batch refresh by topic or pattern

> *"Find all articles under F:\git\azure-ai-docs-pr\articles\ that show the 'Keys and Endpoint' page for any Azure AI service. Recapture each one with current portal UI, scrub all PII, match callout boxes from the originals, and generate a single HTML comparison report covering all of them."*

### Surgical refresh with custom PII rules

> *"Update the screenshots in the Key Vault tutorial at articles\ai-services\use-key-vault.md. The author used real resource names: replace 'my-key-vault' with 'contoso-kv', 'my-cogsvc-resource' with 'contoso-ai', and any email addresses with john@contoso.com. Create a Key Vault with two secrets named 'endpoint' and 'key', then capture the Secrets page and the Keys & Endpoint page. Add red callout boxes on the same elements the original screenshots highlight."*

### Non-Azure portals

> *"Take a screenshot of the Microsoft Entra admin center showing the 'App registrations' page with a registered app named 'Contoso Web App'. Create the app registration if it doesn't exist. Scrub all PII and add a callout box around the Application (client) ID field."*

> *"Capture a screenshot of the SharePoint admin center showing the Active sites list. Scrub any real site names and replace with contoso-*, fabrikam-*, and northwind-*."*

### Clean screenshot without callouts

> *"Take a screenshot of the Azure Key Vault overview page for a vault named contoso-kv. nocallouts"*

The `nocallouts` keyword tells the skill to skip all callout box drawing. Useful when you want a clean base image to annotate manually, or when the UI is too dynamic for reliable automated callout placement.

### Description-only (no article reference)

> *"Set up an Azure Storage account with soft delete enabled. Navigate to the file shares blade, create a share named 'myfileshare', and capture the page. Add callouts around: 1) the 'File shares' nav item, 2) the share name in the list."*

This works even without an existing article or screenshot to reference. The skill provisions resources, navigates, and captures based entirely on your description.

### Interactive comparison review (compare flag)

> *"Refresh the screenshots in F:\git\azure-docs\articles\storage\files\storage-how-to-use-files-windows.md compare"*

The `compare` flag enables an interactive review workflow:
1. The skill recaptures all screenshots and generates a side-by-side comparison report
2. A local HTTP server starts and opens the report in your browser
3. For each screenshot pair, you see the original (left) and new capture (right)
4. Type corrections in the feedback textbox under any screenshot that needs improvement
5. Click **Submit Corrections** to have the skill reprocess those screenshots
6. The page auto-refreshes with the updated comparison; iterate until satisfied
7. When all screenshots look good, leave all textboxes empty and click **Submit & Create PR**
8. A PR is created with before/after comparison images for reviewer validation

> *"Refresh the screenshots in F:\git\azure-ai-docs-pr\articles\ai-services\content-safety\. compare nogimp"*

Combines `compare` with `nogimp` to skip opening GIMP (useful for batch operations where you only want the comparison report, not per-image GIMP windows).

## Supported Portals

Works with any Microsoft portal using Microsoft SSO authentication:

| Portal | URL | Provisioning Tool |
|--------|-----|------------------|
| Azure | portal.azure.com | `az` CLI |
| M365 Admin | admin.microsoft.com | Microsoft Graph PowerShell |
| SharePoint | *.sharepoint.com | PnP PowerShell |
| Microsoft Entra | entra.microsoft.com | `az` CLI / Graph PowerShell |
| Power Platform | make.powerapps.com | `pac` CLI |
| Teams Admin | admin.teams.microsoft.com | Teams PowerShell |
| Exchange | admin.exchange.microsoft.com | Exchange PowerShell |
| Intune | intune.microsoft.com | Graph PowerShell |
| Defender | security.microsoft.com | Graph PowerShell |
| Fabric | app.fabric.microsoft.com | Fabric REST API |
| DevOps | dev.azure.com | `az devops` CLI |

## Limitations

- **Credential-scoped provisioning**: The skill can only create resources the user is authorized to create. If you lack permissions for a service, subscription, or tenant, the skill cannot provision those resources on your behalf.
- **MFA/Conditional Access**: Some portals may trigger MFA prompts requiring manual interaction. The skill pauses and asks for help when this happens.
- **Portal-specific quirks**: Azure portal is the most thoroughly tested. Other portals may have unique popup patterns or DOM structures that need additional handling. File an issue if you encounter one.
- **Canvas/SVG content**: Charts, graphs, and other canvas-rendered content cannot be scrubbed via DOM manipulation; these fall back to pixel-level image editing.
- **Closed Shadow DOM**: Rare portal components with closed Shadow DOM cannot be accessed; post-screenshot pixel-level redaction is used as fallback.
- **Dynamic content**: Real-time dashboards may show different data between captures.

## Troubleshooting

- **"I see ❌ Navigation Failed"**: The skill couldn't find the target page. Check that the resource exists and the URL is correct. For Azure OpenAI resources, ensure you're not accidentally on a generic Cognitive Services resource.
- **"I see 🔒 Privilege Issue"**: Your account lacks permissions for the target portal. For Fabric Admin, you need Fabric Administrator role. For Power BI, you need Pro or Premium license.
- **"I see ⚠️ Service Restructured"**: The Azure service has been renamed or restructured. The doc likely needs rewriting. Check the page change details in the comparison report.
- **"I see 🚨 PII Leak"**: The DOM scrubber missed some PII. Check the comparison report for details. You may need to add custom scrub rules for the specific PII pattern.
- **"Nav item not found in Foundry"**: Items like Playgrounds and Fine-tuning may be hidden behind the "More" button in the left nav. The skill tries to handle this automatically for docs in the `foundry/` folder.
- **"Callout box too wide"**: The callout finder couldn't find a tight container. This usually means the portal's DOM structure changed. File an issue with the screenshot ID.
- **"Callout clips through a border or icon"**: The never-clip rule should prevent this automatically. If it still occurs, the containing panel may not be detected. Add the panel's CSS class to the never-clip detector in `callout_finder.js`.
- **"User avatar still visible"**: The avatar scrubber matches by CSS class, Graph API URLs, and circular image heuristics. If a portal uses a non-standard avatar pattern, add the selector to the avatar detection list in `dom_scrubber.py`.
- **"Flyout not opened"**: The skill didn't click a button to open a flyout. Check that the doc text clearly describes the click action before the screenshot. The skill uses `lib/doc_analyzer.py` to parse interaction steps.

## Prerequisites

> **See [Quick Start for Testers](#quick-start-for-testers) for a streamlined setup guide.**

The skill auto-detects and installs most dependencies on first run. The only things you truly need pre-installed are:

- **Windows** with [Microsoft Edge](https://www.microsoft.com/edge) (pre-installed on Windows)
- **Python 3.10+** (check with `python --version`; [download](https://www.python.org/downloads/) if missing)
- **Copilot CLI** ([install guide](https://docs.github.com/en/copilot/github-copilot-in-the-cli))
- **Your own Microsoft credentials**: The skill uses your logged-in identity. It will never hardcode or share credentials. If MFA is triggered, you will be asked to complete it manually.

**Auto-installed on first run** (the skill handles these for you):
- **Node.js 18+**: installed via `winget install OpenJS.NodeJS.LTS` if missing
- **Azure CLI**: installed via `winget install Microsoft.AzureCLI` if missing
- **GitHub CLI**: installed via `winget install GitHub.cli` if missing
- **Playwright MCP server** (`@playwright/mcp`): detected and configured automatically
- **Pillow** (Python imaging library): installed via `pip install Pillow` if missing
- **GIMP** (optional): If not installed, the skill skips the GIMP review step gracefully

## Install

### Option A: Clone and symlink (recommended)

```powershell
# Clone to wherever you keep tools
git clone https://github.com/jonburchel/docs-screenshot.git
cd docs-screenshot

# Create a junction so Copilot CLI discovers the skill
cmd /c mklink /J "%USERPROFILE%\.copilot\skills\docs-screenshot" "%CD%"
```

### Option B: Direct copy

```powershell
# Copy the skill directory
Copy-Item -Recurse .\docs-screenshot "$env:USERPROFILE\.copilot\skills\docs-screenshot"
```

### Verify installation

After installing, restart Copilot CLI. The skill should appear when you run:
```
/skills
```

You can also just ask: *"Take an Azure screenshot of the resource groups page"* and the skill will activate automatically.

## What it does

1. **Opens Azure portal** in Edge with your existing Microsoft SSO (persistent profile)
2. **Navigates** to the target page, dismisses popups/banners
3. **Provisions Azure resources** if needed (via `az` CLI)
4. **Scrubs PII** from the live DOM before capture, including cross-origin iframes
5. **Replaces user avatars** with a generic silhouette (profile photos, persona images)
6. **Takes the screenshot** at 1200x800 (per contributor guide spec), expanding viewport height if callout targets are below the fold
7. **Post-processes**: crop, callout boxes, gray border, PNG optimization
8. **Opens in GIMP** for final human review
9. **Reports**: lists all PII found, replacements made, image dimensions/size

## Key innovation: cross-origin iframe scrubbing

Azure portal (and other Microsoft portals) renders content inside cross-origin iframes. Standard JavaScript cannot access these frames. This skill uses Playwright's `page.frames()` API to iterate *all* frames and scrub each one. Verified to produce 56+ replacements on a real Azure portal page with resource groups, subscription names, email addresses, and GUIDs all replaced in a single pass.

## PII replacement values

All replacement values come from the official Microsoft contributor guides:

| PII Type | Example Replacement |
|----------|-------------------|
| Subscription ID | `aaaa0a0a-bb1b-cc2c-dd3d-eeeeee4e4e4e` |
| Tenant ID | `aaaabbbb-0000-cccc-1111-dddd2222eeee` |
| Application ID | `00001111-aaaa-2222-bbbb-3333cccc4444` |
| Email | `john@contoso.com` |
| Tenant domain | `contoso.onmicrosoft.com` |
| Resource names | `contoso-rg`, `fabrikam-vm-01`, etc. |
| IP addresses | `192.168.1.15`, `198.51.100.101` |

Full reference: [Approved GUID and sensitive identifiers](https://learn.microsoft.com/en-us/help/platform/reference-sensitive-identifier)

## Callout boxes

Per the [Azure screenshot guide](https://learn.microsoft.com/en-us/help/get-started/add-azure-screenshot):

- Color: RGB **233, 28, 28**
- Thickness: **3px**
- Rectangles hug the target element closely

The callout finder (`lib/callout_finder.js`) enforces several quality rules:
- **Icon inclusion**: Expands bounding boxes to include icons adjacent to menu text (SVGs, images)
- **Vertical centering**: Centers the callout on the text node, not the container (avoids asymmetric margins)
- **Dropdown framing**: Encompasses full dropdown controls including the chevron indicator
- **Never-clip**: Clamps callouts to panel/popup boundaries so they never cut through borders or graphics

**To skip callouts entirely**, say `nocallouts` in your prompt or pass `--no-callouts` to `screenshot_processor.py`. This is useful when callout positions cannot be reliably determined, or when you want a clean screenshot first and plan to add callouts manually in GIMP.

## Failure Reporting

When a screenshot capture fails or produces unexpected results, the skill classifies the failure and explains *why*. Every failure report includes: what was attempted, what was expected, what actually happened, why it failed, and what the reviewer should do next.

Failure categories:

| Badge | Category | Meaning |
|-------|----------|---------|
| ✅ | Success | Screenshot captured successfully |
| 🔧 | Fixed | A known issue was corrected in this run |
| ⚠️ | UI Mismatch / Service Restructured | Page has significantly changed; doc may need updating |
| ❌ | Navigation / Data Setup Failed | Could not reach the target page or create required data |
| 🔒 | Privilege Issue | Insufficient permissions to access the portal/feature |
| 🚨 | PII Leak | PII detected in the final screenshot |
| 📄 | Doc Insufficient | Doc text lacks detail to reproduce the screenshot |
| 🔍 | Element Missing | Expected UI elements not found |

## Page Change Detection

The skill detects when a page has significantly changed from what the doc describes. A common scenario is Azure service renames, such as Form Recognizer becoming Document Intelligence, or Azure Cognitive Services splitting into individual Azure AI services.

When a page change is detected, the skill flags the screenshot with a ⚠️ badge and recommends that the doc itself may need updating, not just the screenshot. Built-in service rename mappings cover 18+ Azure service transitions.

Human reviewers should check whether the doc needs rewriting, not just a screenshot swap.

## Repo-Specific Customizations

The skill embeds repo-specific knowledge directly in `lib/repo_config.py`. This makes the skill portable: it can be run from anywhere and still understand how to handle each repo.

Currently supported repos:
- `azure-ai-docs-pr`
- `fabric-docs-pr`

Repo owners add their config via PR to the skill repo. Each repo config can include:

- **Path-based rules**: which portal to use and navigation hints per doc folder
- **Service rename mappings**: old-name-to-new-name pairs for page change detection
- **Known hidden nav items**: for portals like AI Foundry where items hide behind "More"
- **Portal privilege hints**: what roles or licenses are needed for specific features

To add your repo: add an entry to `REPO_CONFIGS` in `lib/repo_config.py`.

## Project structure

```
docs-screenshot/
├── SKILL.md                    # Copilot CLI skill definition (the brain)
├── README.md                   # This file
├── lib/
│   ├── callout_finder.js       # DOM element finder for callout box placement
│   ├── comparison_report.py    # Comparison HTML generator with interactive feedback UI
│   ├── doc_analyzer.py         # Doc-driven interaction analyzer
│   ├── dom_scrubber.py         # Frame-aware DOM PII + avatar replacement (preferred)
│   ├── extract_dom_info.js     # DOM text extraction (Shadow DOM aware)
│   ├── failure_analyzer.py     # Capture failure classification and reporting
│   ├── gimp_bridge.py          # GIMP integration
│   ├── github_integration.py   # GitHub API helpers (PRs, branches, gists via gh CLI)
│   ├── image_editor.py         # Crop, redact, callout (with numbered circles), border, optimize
│   ├── local_server.py         # Local HTTP server for interactive comparison workflow
│   ├── page_change_analyzer.py # Detects significant page/service changes
│   ├── pii_detector.py         # PII pattern matching + approved replacements
│   ├── post_process.py         # Standalone post-processing CLI (callouts, border, optimize)
│   ├── repo_config.py          # Repo-specific customization system
│   ├── screenshot_processor.py # CLI orchestrator + report generation
│   └── verify_callouts.py      # Deterministic callout count verification
└── references/
    └── screenshot-guidelines.md # Consolidated MS contributor guide reference
```

## How it works (under the hood)

1. **Browser automation** via `playwright-cli` with Edge persistent profile (inherits Microsoft SSO)
2. **Resource provisioning** via `az` CLI, Graph PowerShell, PnP PowerShell, or whatever tool matches the target portal
3. **Doc analysis** parses the markdown to extract interaction steps (clicks, selections, flyout triggers), data requirements, and expected page state using `lib/doc_analyzer.py`
4. **DOM scrubbing** iterates all frames (including cross-origin) replacing PII with approved fictitious values directly in the browser, so the screenshot renders with correct fonts natively. Also replaces user avatar images with a generic silhouette.
5. **Pixel-level fallback** via Pillow for cases where DOM scrubbing can't reach (canvas, SVG, closed shadow DOM): detects PII coordinates from DOM extraction, paints over with background color, re-renders replacement text in Segoe UI at matching size
6. **Viewport expansion**: if any callout target is below the viewport fold, the viewport height is automatically increased so all targets render at their natural positions
7. **Post-processing**: callout boxes (RGB 233,28,28 / 3px), smart crop, gray border, PNG optimization to <200KB
8. **Post-capture validation** runs a pipeline checking for PII leaks, navigation failures, privilege issues, page changes, and missing UI elements. Failures are classified and explained using `lib/failure_analyzer.py`
9. **GIMP handoff**: opens processed images in running GIMP instance for final human review
10. **Interactive comparison** (when `compare` flag is used): serves a local comparison report with feedback textboxes, processes corrections, and creates a PR when all screenshots are approved

## Interactive Comparison Review

When you add `compare` to a Scenario 2 (article refresh) invocation, the skill enters an interactive review loop that runs entirely on your local machine.

### How it works

```
┌─────────────────────────────────────────────────────────────┐
│  1. Capture & Compare                                       │
│     - Skill recaptures all screenshots for the article      │
│     - Generates side-by-side comparison report               │
│     - Starts a local HTTP server (http://localhost:PORT)     │
│     - Opens the report in your browser                       │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  2. Review & Correct (iterate until satisfied)              │
│     - Review each screenshot pair (original vs. new)        │
│     - Type corrections in the feedback textbox for any      │
│       screenshots that need improvement                     │
│     - Click "Submit Corrections"                            │
│     - Skill reprocesses flagged screenshots locally          │
│     - Report auto-refreshes with updated comparisons        │
│     - Repeat until all screenshots look good                │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  3. Finalize & Create PR                                    │
│     - All textboxes empty = all screenshots approved        │
│     - Click "Submit & Create PR"                            │
│     - PR includes before/after comparison images            │
│       (first-iteration vs. final captures)                  │
│     - Reviewers see the visual diff and merge               │
└─────────────────────────────────────────────────────────────┘
```

> **Key design:** Everything runs locally. No GitHub Issues, no polling services, no OAuth tokens needed. The person who generated the comparison report is the same person who validates it. Only the final result is pushed as a PR for team review.

### Environment variables

| Variable | Default | Description |
|---|---|---|
| `SCREENSHOT_REPO` | `jonburchel/docs-screenshot` | GitHub repo for PRs |
| `SCREENSHOT_REPO_DIR` | Auto-detected | Local path to the skill repo |

### Key files

| File | Purpose |
|---|---|
| `lib/comparison_report.py` | Generates comparison HTML with interactive feedback UI |
| `lib/local_server.py` | Local HTTP server that serves reports and accepts feedback |
| `lib/github_integration.py` | GitHub API helpers (PRs, branches, gists via `gh` CLI) |

## Supported PII patterns

- GUIDs/UUIDs (with context-aware classification: subscription, tenant, app, etc.)
- Email addresses (including `@microsoft.com` employee emails)
- Tenant domains (`*.onmicrosoft.com`)
- Public IP addresses (flags non-reserved IPs)
- Access keys, client secrets, thumbprints
- Custom text patterns (resource names, subscription names, usernames)
- **User avatars**: Profile photos, persona images, and small circular images are replaced with a generic silhouette

## Contributing

There are two ways to contribute:

### Report issues from your comparison reports

When you run the skill with `compare` and notice patterns it gets wrong (missed PII, wrong navigation, bad callout placement), [file an issue](https://github.com/jonburchel/docs-screenshot/issues/new) with the details described in [Quick Start for Testers](#submit-improvements-from-the-comparison-report). These reports directly drive skill improvements.

### Contribute code

Found a bug you can fix, or want to add support for a new portal or PII pattern? Open a PR. Key files to know:

- **`lib/callout_finder.js`**: Add CSS selectors for portal-specific UI elements
- **`lib/dom_scrubber.py`**: Add new PII scrubbing patterns or avatar detection selectors
- **`lib/pii_detector.py`**: Add new PII regex patterns and approved replacement values
- **`lib/repo_config.py`**: Add navigation hints, service renames, and path rules for your repo

### Add your repo

To get the best results for articles in your repo, add a config entry to `lib/repo_config.py`. See [Repo-Specific Customizations](#repo-specific-customizations) for details. Currently supported: `azure-ai-docs-pr`, `fabric-docs-pr`. Articles in other repos will work but may need more manual corrections.

## References

- [How to create screenshots for Azure content](https://learn.microsoft.com/en-us/help/get-started/add-azure-screenshot)
- [Create a screenshot for documentation](https://learn.microsoft.com/en-us/help/contribute/contribute-how-to-create-screenshot)
- [Approved GUID and sensitive identifiers](https://learn.microsoft.com/en-us/help/platform/reference-sensitive-identifier)
- [Legal guidelines](https://learn.microsoft.com/en-us/help/contribute/contribute-legal-guidelines)
