"""
Repo-specific customization system for the docs-screenshot skill.

Each repo can define path-based rules, service rename mappings, portal hints,
and known hidden nav items. This allows the screenshot pipeline to adapt its
behavior (navigation, portal selection, scrubbing, etc.) based on which repo
and doc path it is operating on.

To add a new repo config, add an entry to REPO_CONFIGS with the repo name as
the key. See existing entries for the expected structure.
"""

from __future__ import annotations

import fnmatch
import os
from typing import Any


# ---------------------------------------------------------------------------
# Repo configurations
# ---------------------------------------------------------------------------

REPO_CONFIGS: dict[str, dict[str, Any]] = {
    # -----------------------------------------------------------------------
    # azure-ai-docs-pr
    # -----------------------------------------------------------------------
    "azure-ai-docs-pr": {
        "path_rules": [
            {
                "glob": "articles/ai-services/document-intelligence/**",
                "portal": "Azure portal",
                "notes": (
                    "Formerly 'Form Recognizer'. The service was renamed to "
                    "'Document Intelligence' in 2023. Screenshots should "
                    "reflect the new branding."
                ),
                "nav_hints": [
                    "Look for 'Document Intelligence' in the portal, not 'Form Recognizer'.",
                ],
            },
            {
                "glob": "articles/ai-studio/foundry/**",
                "exclude_globs": ["articles/ai-studio/foundry-classic/**"],
                "portal": "Azure AI Foundry portal",
                "notes": (
                    "This is the NEW Azure AI Foundry portal "
                    "(https://ai.azure.com), NOT the legacy foundry-classic "
                    "experience. Left-nav items may be hidden behind a 'More' "
                    "button; you may need to click it to reveal the target item."
                ),
                "nav_hints": [
                    "Use Azure AI Foundry portal (ai.azure.com), NOT foundry-classic.",
                    "If the portal shows a 'New Foundry' vs 'Classic' toggle at the top, select 'New Foundry'.",
                    "Left-nav items may be hidden behind a '... More' button at the bottom of the nav pane.",
                    "Playgrounds, Fine-tuning, and Models+endpoints are commonly hidden behind 'More'.",
                    "After switching to New Foundry or clicking More, wait for the nav pane to refresh.",
                ],
                "known_hidden_nav_items": [
                    "Playgrounds",
                    "Fine-tuning",
                    "Models + endpoints",
                ],
            },
            {
                "glob": "articles/ai-services/**",
                "portal": "Azure portal",
                "notes": (
                    "General Azure AI Services documentation. These pages "
                    "typically reference resources in the Azure portal under "
                    "the 'Azure AI services' resource provider."
                ),
                "nav_hints": [
                    "Navigate via Azure AI services in the Azure portal.",
                ],
            },
        ],
        "service_renames": {
            "Form Recognizer": "Document Intelligence",
            "Cognitive Services": "Azure AI Services",
            "Azure AI Studio": "Azure AI Foundry",
        },
        "portal_hints": {
            "Azure AI Foundry portal": (
                "Requires an Azure AI Foundry hub and project. Some features "
                "are gated behind specific Azure role assignments."
            ),
        },
        "known_hidden_nav_items": [
            "Playgrounds",
            "Fine-tuning",
            "Models + endpoints",
        ],
    },

    # -----------------------------------------------------------------------
    # fabric-docs-pr
    # -----------------------------------------------------------------------
    "fabric-docs-pr": {
        "path_rules": [
            {
                "glob": "docs/admin/**",
                "portal": "Fabric Admin portal",
                "notes": (
                    "Fabric Admin portal pages. Requires tenant admin or "
                    "Fabric admin privileges to access most settings."
                ),
                "nav_hints": [
                    "Open the Fabric Admin portal from the gear icon in the Fabric header.",
                    "Admin privileges are required; screenshots may differ for non-admins.",
                ],
            },
            {
                "glob": "docs/data-factory/**",
                "portal": "Fabric Data Factory",
                "notes": (
                    "Data Factory experience within Microsoft Fabric. "
                    "Pipelines and dataflows are accessed from the Data "
                    "Factory workload switcher."
                ),
                "nav_hints": [
                    "Switch to the Data Factory workload in the Fabric portal.",
                ],
            },
            {
                "glob": "docs/real-time-intelligence/**",
                "portal": "Fabric Real-Time Intelligence",
                "notes": (
                    "Real-Time Intelligence (formerly Real-Time Analytics) "
                    "workload in Fabric."
                ),
                "nav_hints": [
                    "Switch to the Real-Time Intelligence workload in the Fabric portal.",
                ],
            },
            {
                "glob": "docs/power-bi/**",
                "portal": "Power BI",
                "notes": (
                    "Power BI documentation within Fabric. Some features "
                    "require Power BI Pro or Premium Per User licensing."
                ),
                "nav_hints": [
                    "Access Power BI through the Fabric portal or app.powerbi.com.",
                    "Pro or Premium licensing may be needed for certain features.",
                ],
            },
            {
                "glob": "docs/rest-api/**",
                "portal": "Fabric REST API",
                "notes": (
                    "Fabric REST API documentation. A Fabric capacity must be "
                    "provisioned before API calls will succeed."
                ),
                "nav_hints": [
                    "Ensure a Fabric capacity is provisioned before testing API calls.",
                ],
            },
        ],
        "service_renames": {
            "Real-Time Analytics": "Real-Time Intelligence",
        },
        "portal_hints": {
            "Fabric Admin portal": (
                "Requires Fabric administrator or Power Platform administrator "
                "privileges. Non-admin users will see a restricted view."
            ),
            "Power BI": (
                "Some pages require Power BI Pro or Premium Per User licensing. "
                "Free-tier users may not see all features shown in screenshots."
            ),
            "Fabric REST API": (
                "A Fabric capacity must be provisioned and active for REST API "
                "calls to succeed. Paused capacities will return errors."
            ),
        },
        "known_hidden_nav_items": [],
    },
}


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def get_repo_config(repo_name: str) -> dict[str, Any] | None:
    """Return the full configuration dict for a repo, or None if not found."""
    return REPO_CONFIGS.get(repo_name)


def _path_matches_rule(doc_path: str, rule: dict[str, Any]) -> bool:
    """Check whether *doc_path* matches the rule's glob while respecting exclude_globs."""
    # Normalise to forward slashes for consistent matching.
    normalised = doc_path.replace("\\", "/")

    if not fnmatch.fnmatch(normalised, rule["glob"]):
        return False

    for exclude in rule.get("exclude_globs", []):
        if fnmatch.fnmatch(normalised, exclude):
            return False

    return True


def get_path_rules(repo_name: str, doc_path: str) -> list[dict[str, Any]]:
    """Return all path rules whose glob matches *doc_path* within the given repo.

    Rules that define ``exclude_globs`` will be skipped if *doc_path* matches
    any of the exclusion patterns.  Returns an empty list when the repo is
    unknown or no rules match.
    """
    config = get_repo_config(repo_name)
    if config is None:
        return []

    return [
        rule
        for rule in config.get("path_rules", [])
        if _path_matches_rule(doc_path, rule)
    ]


def get_service_renames(repo_name: str) -> dict[str, str]:
    """Return the old-name to new-name mapping for renamed services.

    Returns an empty dict when the repo is unknown or has no renames.
    """
    config = get_repo_config(repo_name)
    if config is None:
        return {}
    return config.get("service_renames", {})


def get_nav_hints(repo_name: str, doc_path: str) -> list[str]:
    """Collect navigation hints from every matching path rule for *doc_path*.

    Hints are returned in rule-definition order and deduplicated while
    preserving that order.
    """
    seen: set[str] = set()
    hints: list[str] = []

    for rule in get_path_rules(repo_name, doc_path):
        for hint in rule.get("nav_hints", []):
            if hint not in seen:
                seen.add(hint)
                hints.append(hint)

    return hints


def get_portal_hints(repo_name: str, portal: str) -> str | None:
    """Return portal-specific notes (e.g. privilege requirements), or None."""
    config = get_repo_config(repo_name)
    if config is None:
        return None
    return config.get("portal_hints", {}).get(portal)


def detect_repo_from_path(local_path: str) -> str | None:
    """Attempt to detect the repo name from a local filesystem path.

    Walks up the path components looking for a directory name that matches a
    known repo in ``REPO_CONFIGS``.  Returns the repo name on the first match,
    or None if no match is found.

    This is a best-effort heuristic; it relies on the checkout directory being
    named after the repo (which is the default for ``git clone``).
    """
    # Normalise the path so splitting works on both Windows and POSIX.
    normalised = os.path.normpath(local_path)
    parts = normalised.split(os.sep)

    for part in parts:
        if part in REPO_CONFIGS:
            return part

    return None
