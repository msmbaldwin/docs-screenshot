"""Tests for lib/user_config.py."""
import json
from pathlib import Path

import pytest
import user_config


@pytest.fixture(autouse=True)
def reset_cache():
    """Clear the module-level cache before each test."""
    user_config._CACHE = None
    user_config._CACHE_PATH = None
    yield
    user_config._CACHE = None
    user_config._CACHE_PATH = None


def test_load_returns_empty_when_no_config(monkeypatch, tmp_path):
    monkeypatch.delenv("DOCS_SCREENSHOT_CONFIG", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    # Path.home() respects HOME on Linux
    assert user_config.load() == {}
    assert user_config.source_path() is None


def test_env_var_overrides_default_location(monkeypatch, tmp_path):
    cfg_path = tmp_path / "custom.json"
    cfg_path.write_text(json.dumps({"username": "mbaldwin", "subscription": "test-sub"}))
    monkeypatch.setenv("DOCS_SCREENSHOT_CONFIG", str(cfg_path))
    cfg = user_config.load()
    assert cfg == {"username": "mbaldwin", "subscription": "test-sub"}
    assert user_config.source_path() == cfg_path


def test_get_returns_value_and_default(monkeypatch, tmp_path):
    cfg_path = tmp_path / "c.json"
    cfg_path.write_text(json.dumps({"username": "mbaldwin"}))
    monkeypatch.setenv("DOCS_SCREENSHOT_CONFIG", str(cfg_path))
    assert user_config.get("username") == "mbaldwin"
    assert user_config.get("missing_key", "fallback") == "fallback"


def test_username_helper(monkeypatch, tmp_path):
    cfg_path = tmp_path / "c.json"
    cfg_path.write_text(json.dumps({"username": "mbaldwin"}))
    monkeypatch.setenv("DOCS_SCREENSHOT_CONFIG", str(cfg_path))
    assert user_config.username() == "mbaldwin"


def test_username_falls_back(monkeypatch, tmp_path):
    monkeypatch.setenv("DOCS_SCREENSHOT_CONFIG", str(tmp_path / "nonexistent.json"))
    assert user_config.username(fallback="anon") == "anon"


def test_repo_root_expands_tilde(monkeypatch, tmp_path):
    cfg_path = tmp_path / "c.json"
    cfg_path.write_text(json.dumps({"repo_root": "~/docs"}))
    monkeypatch.setenv("DOCS_SCREENSHOT_CONFIG", str(cfg_path))
    result = user_config.repo_root()
    assert result is not None
    assert "~" not in result
    assert result.endswith("/docs")


def test_custom_replacements_returns_dict(monkeypatch, tmp_path):
    cfg_path = tmp_path / "c.json"
    cfg_path.write_text(json.dumps({
        "custom_replacements": {"my-rg": "contoso-rg"}
    }))
    monkeypatch.setenv("DOCS_SCREENSHOT_CONFIG", str(cfg_path))
    assert user_config.custom_replacements() == {"my-rg": "contoso-rg"}


def test_custom_replacements_handles_non_dict(monkeypatch, tmp_path):
    cfg_path = tmp_path / "c.json"
    cfg_path.write_text(json.dumps({"custom_replacements": "not-a-dict"}))
    monkeypatch.setenv("DOCS_SCREENSHOT_CONFIG", str(cfg_path))
    assert user_config.custom_replacements() == {}


def test_yaml_loads_when_pyyaml_available(monkeypatch, tmp_path):
    pytest.importorskip("yaml")
    cfg_path = tmp_path / "c.yaml"
    cfg_path.write_text("username: mbaldwin\nsubscription: My Sub\n")
    monkeypatch.setenv("DOCS_SCREENSHOT_CONFIG", str(cfg_path))
    cfg = user_config.load()
    assert cfg["username"] == "mbaldwin"
    assert cfg["subscription"] == "My Sub"
