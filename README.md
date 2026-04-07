# docs-screenshot

A Copilot CLI skill that automates screenshot capture across Microsoft web portals (Azure, M365, SharePoint, Entra ID, Power Platform, and more) for Microsoft Learn documentation. Handles browser automation, resource provisioning, PII redaction with official Microsoft-approved fictitious values, callout boxes, cropping, and GIMP handoff.

This skill was created in [this Copilot chat session](https://gist.github.com/jonburchel/2a1f0f25b064f7276a45a2aa2e544970).

## Two Usage Scenarios

### 1. New Documentation Authoring

You're writing a new article and need screenshots. Describe what you need:

> *"I need a screenshot of the Azure portal showing a VM creation blade. The VM should be named contoso-vm in resource group contoso-rg, size Standard_B2s, running Ubuntu 22.04. Highlight the 'Size' dropdown with a red callout box."*

The skill will:
- Create the resource group and VM (via `az` CLI)
- Open Azure portal in Edge, navigate to the VM creation blade
- Configure the view to match your description
- Scrub any remaining PII from the DOM (including cross-origin iframes)
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
- Generate a comparison report (old vs. new dimensions, changes detected)
- Open all screenshots in GIMP for final review

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

## Prerequisites

- **Windows** with [Microsoft Edge](https://www.microsoft.com/edge)
- **Browser automation** (one of the following):
  - **Copilot CLI users**: Install the [playwright-cli skill](https://github.com/microsoft/playwright-cli/blob/main/skills/playwright-cli/SKILL.md) (`playwright-cli install --skills`)
  - **VS Code users**: Install the [Playwright MCP server](https://github.com/microsoft/playwright-mcp) (`npx @playwright/mcp@latest --headless --browser=msedge`)
- **Python 3.10+** with Pillow: `pip install Pillow`
- **Azure CLI**: `winget install Microsoft.AzureCLI` (for resource provisioning)
- **GIMP 2.10+** (optional, for final review): `winget install GIMP.GIMP`
- **Your own Microsoft credentials**: The skill uses your logged-in identity. It will never hardcode or share credentials. If MFA is triggered, you will be asked to complete it manually.

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
5. **Takes the screenshot** at 1200x800 (per contributor guide spec)
6. **Post-processes**: crop, callout boxes, gray border, PNG optimization
7. **Opens in GIMP** for final human review
8. **Reports**: lists all PII found, replacements made, image dimensions/size

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

## Project structure

```
docs-screenshot/
├── SKILL.md                    # Copilot CLI skill definition (the brain)
├── README.md                   # This file
├── lib/
│   ├── dom_scrubber.py         # Frame-aware DOM PII replacement (preferred)
│   ├── pii_detector.py         # PII pattern matching + approved replacements
│   ├── image_editor.py         # Crop, redact, callout, border, optimize
│   ├── screenshot_processor.py # CLI orchestrator + report generation
│   ├── gimp_bridge.py          # GIMP integration
│   └── extract_dom_info.js     # DOM text extraction (Shadow DOM aware)
└── references/
    └── screenshot-guidelines.md # Consolidated MS contributor guide reference
```

## How it works (under the hood)

1. **Browser automation** via `playwright-cli` with Edge persistent profile (inherits Microsoft SSO)
2. **Resource provisioning** via `az` CLI, Graph PowerShell, PnP PowerShell, or whatever tool matches the target portal
3. **DOM scrubbing** iterates all frames (including cross-origin) replacing PII with approved fictitious values directly in the browser, so the screenshot renders with correct fonts natively
4. **Pixel-level fallback** via Pillow for cases where DOM scrubbing can't reach (canvas, SVG, closed shadow DOM): detects PII coordinates from DOM extraction, paints over with background color, re-renders replacement text in Segoe UI at matching size
5. **Post-processing**: callout boxes (RGB 233,28,28 / 3px), smart crop, gray border, PNG optimization to <200KB
6. **GIMP handoff**: opens processed images in running GIMP instance for final human review

## Supported PII patterns

- GUIDs/UUIDs (with context-aware classification: subscription, tenant, app, etc.)
- Email addresses (including `@microsoft.com` employee emails)
- Tenant domains (`*.onmicrosoft.com`)
- Public IP addresses (flags non-reserved IPs)
- Access keys, client secrets, thumbprints
- Custom text patterns (resource names, subscription names, usernames)

## Contributing

Found a bug or want to improve detection patterns? Open an issue or PR.

## References

- [How to create screenshots for Azure content](https://learn.microsoft.com/en-us/help/get-started/add-azure-screenshot)
- [Create a screenshot for documentation](https://learn.microsoft.com/en-us/help/contribute/contribute-how-to-create-screenshot)
- [Approved GUID and sensitive identifiers](https://learn.microsoft.com/en-us/help/platform/reference-sensitive-identifier)
- [Legal guidelines](https://learn.microsoft.com/en-us/help/contribute/contribute-legal-guidelines)
