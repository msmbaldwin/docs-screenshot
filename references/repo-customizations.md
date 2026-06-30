# Repo-Specific Customizations

_Reference for the docs-screenshot skill. See [`SKILL.md`](../SKILL.md) for the trigger-time prompt and high-level usage._


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
