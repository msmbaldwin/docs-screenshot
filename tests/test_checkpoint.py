"""Tests for lib/checkpoint.py."""
import json
from pathlib import Path

from checkpoint import Checkpoint, _article_hash, list_checkpoints


def test_article_hash_stable():
    assert _article_hash("articles/foo.md") == _article_hash("articles/foo.md")
    assert _article_hash("articles/foo.md") != _article_hash("articles/bar.md")


def test_article_hash_normalizes_separators():
    assert _article_hash("articles\\foo.md") == _article_hash("articles/foo.md")


def test_checkpoint_creates_file_on_save(tmp_path):
    cp = Checkpoint.for_article("articles/x.md", repo="my-repo", state_dir=tmp_path)
    cp.mark_done("img-1.png", notes="captured")
    files = list(tmp_path.glob("*.json"))
    assert len(files) == 1
    data = json.loads(files[0].read_text())
    assert data["article_path"] == "articles/x.md"
    assert data["repo_name"] == "my-repo"
    assert data["completed"]["img-1.png"]["status"] == "done"


def test_is_complete_after_mark_done(tmp_path):
    cp = Checkpoint.for_article("articles/x.md", state_dir=tmp_path)
    assert not cp.is_complete("img-1.png")
    cp.mark_done("img-1.png")
    assert cp.is_complete("img-1.png")


def test_resume_reloads_state(tmp_path):
    cp1 = Checkpoint.for_article("articles/x.md", state_dir=tmp_path)
    cp1.mark_done("a.png")
    cp1.mark_done("b.png")
    cp1.mark_failed("c.png", reason="timeout")

    # New instance picks up where the previous left off
    cp2 = Checkpoint.for_article("articles/x.md", state_dir=tmp_path)
    assert cp2.is_complete("a.png")
    assert cp2.is_complete("b.png")
    assert not cp2.is_complete("c.png")
    assert "c.png" in cp2.data["completed"]
    assert cp2.data["completed"]["c.png"]["status"] == "failed"


def test_pending_from_skips_completed(tmp_path):
    cp = Checkpoint.for_article("articles/x.md", state_dir=tmp_path)
    cp.mark_done("a.png")
    cp.mark_done("c.png")
    pending = cp.pending_from(["a.png", "b.png", "c.png", "d.png"])
    assert pending == ["b.png", "d.png"]


def test_completed_ids_excludes_failed(tmp_path):
    cp = Checkpoint.for_article("articles/x.md", state_dir=tmp_path)
    cp.mark_done("a.png")
    cp.mark_failed("b.png")
    assert cp.completed_ids() == ["a.png"]


def test_reset_clears_state(tmp_path):
    cp = Checkpoint.for_article("articles/x.md", state_dir=tmp_path)
    cp.mark_done("a.png")
    assert cp.path.exists()
    cp.reset()
    assert not cp.path.exists()
    assert cp.completed_ids() == []


def test_corrupt_file_does_not_crash(tmp_path):
    """A corrupt JSON file should start fresh, not raise."""
    article = "articles/x.md"
    fake = tmp_path / f"{_article_hash(article)}.json"
    fake.write_text("{not json at all")
    cp = Checkpoint.for_article(article, state_dir=tmp_path)
    assert cp.completed_ids() == []
    # And saving should succeed
    cp.mark_done("a.png")
    assert cp.is_complete("a.png")


def test_list_checkpoints_summarizes(tmp_path):
    cp1 = Checkpoint.for_article("articles/a.md", repo="r1", state_dir=tmp_path)
    cp1.mark_done("x.png")
    cp1.mark_done("y.png")
    cp2 = Checkpoint.for_article("articles/b.md", repo="r2", state_dir=tmp_path)
    cp2.mark_done("z.png")

    summaries = list_checkpoints(state_dir=tmp_path)
    assert len(summaries) == 2
    by_article = {s["article_path"]: s for s in summaries}
    assert by_article["articles/a.md"]["done_count"] == 2
    assert by_article["articles/a.md"]["repo_name"] == "r1"
    assert by_article["articles/b.md"]["done_count"] == 1


def test_list_checkpoints_empty_dir_returns_empty(tmp_path):
    assert list_checkpoints(state_dir=tmp_path) == []


def test_env_var_overrides_state_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("DOCS_SCREENSHOT_STATE_DIR", str(tmp_path))
    cp = Checkpoint.for_article("articles/x.md")
    cp.mark_done("img-1.png")
    assert (tmp_path / cp.path.name).exists()


def test_save_is_atomic_no_leftover_temp(tmp_path):
    cp = Checkpoint.for_article("articles/x.md", state_dir=tmp_path)
    cp.mark_done("a.png")
    cp.mark_done("b.png")
    leftover = list(tmp_path.glob("*.tmp"))
    assert leftover == [], f"Atomic write left tmp files: {leftover}"
