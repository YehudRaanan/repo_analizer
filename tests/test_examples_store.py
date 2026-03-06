"""
tests/test_examples_store.py

Unit tests for examples_store.py — all local filesystem, no API calls.
"""

import os
import pytest
from examples_store import (
    list_examples,
    get_examples,
    save_example,
    all_type_dirs_exist,
    VALID_TYPES,
)


# ────────────────────────────────────────────────────────────────────────────
# all_type_dirs_exist
# ────────────────────────────────────────────────────────────────────────────

def test_all_type_dirs_exist():
    """All 6 type directories should be present (created by organize_examples.py)."""
    assert all_type_dirs_exist()


# ────────────────────────────────────────────────────────────────────────────
# list_examples
# ────────────────────────────────────────────────────────────────────────────

class TestListExamples:
    def test_library_has_examples(self):
        files = list_examples("library")
        assert len(files) >= 1

    def test_returns_only_txt_files(self):
        for t in VALID_TYPES:
            files = list_examples(t)
            for f in files:
                assert f.endswith(".txt")
                assert "_classify" not in f

    def test_unknown_type_returns_empty(self):
        assert list_examples("unknown_type_xyz") == []

    def test_all_types_have_examples(self):
        for t in VALID_TYPES:
            files = list_examples(t)
            assert len(files) >= 1, f"No examples found for type: {t}"

    def test_returns_sorted_list(self):
        files = list_examples("library")
        assert files == sorted(files)


# ────────────────────────────────────────────────────────────────────────────
# get_examples
# ────────────────────────────────────────────────────────────────────────────

class TestGetExamples:
    def test_returns_non_empty_string(self):
        result = get_examples("cli_tool", n=1)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_n_2_returns_two_sections(self):
        result = get_examples("data_ml", n=2, strategy="first")
        assert result.count("=== EXAMPLE:") == 2

    def test_unknown_type_returns_empty(self):
        result = get_examples("not_a_type")
        assert result == ""

    def test_n_greater_than_available(self):
        # Should not crash, just return however many exist
        result = get_examples("infra", n=1000)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_strategy_first_is_deterministic(self):
        r1 = get_examples("library", n=1, strategy="first")
        r2 = get_examples("library", n=1, strategy="first")
        assert r1 == r2

    def test_content_is_readable_text(self):
        result = get_examples("web_app", n=1, strategy="first")
        # Should contain something recognizable from the collected format
        assert len(result) > 50


# ────────────────────────────────────────────────────────────────────────────
# save_example
# ────────────────────────────────────────────────────────────────────────────

class TestSaveExample:
    DUMMY_CONTENT = "=== TEST REPO ===\nDummy content for testing save_example.\n"

    def test_save_creates_file(self, tmp_path, monkeypatch):
        # Redirect EXAMPLES_DIR to tmp_path for isolation
        import examples_store
        monkeypatch.setattr(examples_store, "EXAMPLES_DIR", str(tmp_path))

        path = save_example("test_repo", "library", self.DUMMY_CONTENT)
        assert os.path.exists(path)

    def test_save_content_matches(self, tmp_path, monkeypatch):
        import examples_store
        monkeypatch.setattr(examples_store, "EXAMPLES_DIR", str(tmp_path))

        path = save_example("test_repo", "library", self.DUMMY_CONTENT)
        with open(path, encoding="utf-8") as f:
            assert f.read() == self.DUMMY_CONTENT

    def test_save_adds_txt_extension(self, tmp_path, monkeypatch):
        import examples_store
        monkeypatch.setattr(examples_store, "EXAMPLES_DIR", str(tmp_path))

        path = save_example("myrepo", "cli_tool", "content")
        assert path.endswith(".txt")

    def test_save_unknown_type_raises(self):
        with pytest.raises(ValueError):
            save_example("repo", "not_a_valid_type", "content")

    def test_save_overwrites_existing(self, tmp_path, monkeypatch):
        import examples_store
        monkeypatch.setattr(examples_store, "EXAMPLES_DIR", str(tmp_path))

        save_example("repo", "backend", "first version")
        save_example("repo", "backend", "second version")

        path = os.path.join(str(tmp_path), "backend", "repo.txt")
        with open(path, encoding="utf-8") as f:
            assert f.read() == "second version"
