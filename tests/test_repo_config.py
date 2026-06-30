"""Tests for lib/repo_config.py."""
import repo_config


def test_list_known_repos_includes_owned_repos():
    repos = repo_config.list_known_repos()
    # Spot-check: the repos shipped as references/repos/ YAML files
    assert "azure-ai-docs-pr" in repos
    assert "fabric-docs-pr" in repos
    assert "azure-security-docs-pr" in repos


def test_get_repo_config_unknown_returns_none():
    assert repo_config.get_repo_config("not-a-real-repo") is None


def test_get_repo_config_known_has_expected_keys():
    cfg = repo_config.get_repo_config("azure-ai-docs-pr")
    assert cfg is not None
    assert "path_rules" in cfg
    assert "service_renames" in cfg
    assert "portal_hints" in cfg


def test_get_path_rules_matches_glob():
    rules = repo_config.get_path_rules(
        "azure-ai-docs-pr",
        "articles/ai-services/document-intelligence/quickstart.md",
    )
    assert len(rules) >= 1
    assert any("Document Intelligence" in r.get("notes", "") for r in rules)


def test_get_path_rules_respects_exclude_globs():
    """foundry-classic paths should not match the foundry rule."""
    foundry_rules = repo_config.get_path_rules(
        "azure-ai-docs-pr", "articles/ai-studio/foundry/quickstart.md"
    )
    classic_rules = repo_config.get_path_rules(
        "azure-ai-docs-pr", "articles/ai-studio/foundry-classic/quickstart.md"
    )
    foundry_portals = [r.get("portal") for r in foundry_rules]
    classic_portals = [r.get("portal") for r in classic_rules]
    assert "Azure AI Foundry portal" in foundry_portals
    assert "Azure AI Foundry portal" not in classic_portals


def test_get_path_rules_unknown_repo_returns_empty():
    assert repo_config.get_path_rules("not-a-repo", "any/path.md") == []


def test_get_service_renames_returns_dict():
    renames = repo_config.get_service_renames("azure-ai-docs-pr")
    assert isinstance(renames, dict)
    assert renames.get("Form Recognizer") == "Document Intelligence"


def test_get_service_renames_unknown_repo_returns_empty():
    assert repo_config.get_service_renames("not-a-repo") == {}


def test_get_nav_hints_deduplicates_and_preserves_order():
    hints = repo_config.get_nav_hints(
        "azure-ai-docs-pr", "articles/ai-studio/foundry/quickstart.md"
    )
    assert hints, "Should have at least one nav hint for foundry path"
    assert len(hints) == len(set(hints)), "Hints should be deduplicated"


def test_get_portal_hints_returns_note_string():
    note = repo_config.get_portal_hints("fabric-docs-pr", "Fabric Admin portal")
    assert note is not None
    assert "Fabric" in note or "administrator" in note.lower()


def test_get_portal_hints_unknown_returns_none():
    assert repo_config.get_portal_hints("not-a-repo", "Azure portal") is None
    assert repo_config.get_portal_hints("azure-ai-docs-pr", "Nonexistent Portal") is None


def test_detect_repo_from_path_finds_known_repo():
    assert (
        repo_config.detect_repo_from_path(
            "/home/user/docs/azure-security-docs-pr/articles/key-vault/x.md"
        )
        == "azure-security-docs-pr"
    )


def test_detect_repo_from_path_unknown_returns_none():
    assert repo_config.detect_repo_from_path("/tmp/random/path.md") is None


def test_backward_compat_REPO_CONFIGS_attribute():
    # The module exposes REPO_CONFIGS via __getattr__ for back-compat
    assert isinstance(repo_config.REPO_CONFIGS, dict)
    assert "azure-ai-docs-pr" in repo_config.REPO_CONFIGS
