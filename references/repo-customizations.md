# Repo-Specific Customizations

_Reference for the docs-screenshot skill. See [`SKILL.md`](../SKILL.md) for the trigger-time prompt and high-level usage._

The skill adapts its navigation, scrubbing, and validation behavior based on which documentation repo it's operating on. Per-repo configuration lives as YAML files under [`references/repos/`](repos/), one file per repo. `lib/repo_config.py` loads them on first use and exposes the lookup API the rest of the skill calls into.

**How it works:**

- `detect_repo_from_path(article_path)` identifies which repo an article belongs to by walking up the path components looking for a directory name that matches a config file's basename.
- `get_path_rules(repo, article_path)` returns the rules whose `glob` matches the path (and whose `exclude_globs`, if any, do not).
- `get_service_renames(repo)`, `get_nav_hints(repo, path)`, `get_portal_hints(repo, portal)` return the corresponding slices.

**Currently supported repos:**

| Repo | Config file | Key customizations |
|------|---|---|
| `azure-ai-docs-pr` | [`repos/azure-ai-docs-pr.yaml`](repos/azure-ai-docs-pr.yaml) | AI Foundry nav hints (hidden "More" button items), Cognitive Services → Azure AI Services rename, Document Intelligence (formerly Form Recognizer) |
| `fabric-docs-pr` | [`repos/fabric-docs-pr.yaml`](repos/fabric-docs-pr.yaml) | Fabric Admin privilege requirements, workload-switcher patterns, Power BI licensing notes, Real-Time Intelligence rename |
| `azure-security-docs-pr` | [`repos/azure-security-docs-pr.yaml`](repos/azure-security-docs-pr.yaml) | Key Vault, Managed HSM, Cloud HSM, Confidential Ledger portal navigation hints |
| `security-pr` | [`repos/security-pr.yaml`](repos/security-pr.yaml) | Generic security docs — defer to article frontmatter for portal selection |
| `security-benchmark-docs-pr` | [`repos/security-benchmark-docs-pr.yaml`](repos/security-benchmark-docs-pr.yaml) | Defender for Cloud compliance dashboard hints |
| `azure-monitor-docs-pr` | [`repos/azure-monitor-docs-pr.yaml`](repos/azure-monitor-docs-pr.yaml) | Log Analytics / KQL navigation |
| `reliability-docs-pr` | [`repos/reliability-docs-pr.yaml`](repos/reliability-docs-pr.yaml) | Availability zones / redundancy patterns |

**Config schema:**

```yaml
name: <repo-name>                # matches the file basename
path_rules:
  - glob: "articles/.../**"      # fnmatch glob against the doc-relative path
    exclude_globs:               # optional: skip rule if path matches any exclude
      - "articles/.../legacy/**"
    portal: "Azure portal"       # target portal for navigation
    notes: >-                    # human-readable rationale
      ...
    nav_hints:                   # bullet list of navigation tips
      - "..."
    known_hidden_nav_items:      # items hidden behind "More" buttons, optional
      - "Item Name"
service_renames:                 # old name -> new name mapping
  Old Name: New Name
portal_hints:                    # portal -> note text (e.g., privilege requirements)
  Azure portal: >-
    ...
known_hidden_nav_items: []       # repo-wide hidden nav items, optional
```

**Adding a new repo:**

1. Create `references/repos/<repo-name>.yaml` using one of the existing files as a template.
2. The file's basename (without `.yaml`) is the repo name that `detect_repo_from_path()` will return.
3. Restart any running Python process; the loader caches configs on first use.

**Note:** JSON files (`references/repos/<name>.json`) are also supported and take precedence over YAML when both exist. YAML support requires PyYAML; if it isn't installed, only JSON files are loaded.
