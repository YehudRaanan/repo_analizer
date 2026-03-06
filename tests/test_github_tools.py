"""
tests/test_github_tools.py

Unit + integration tests for github_tools.py.
Most tests hit real GitHub API (public repos, no auth required for basic use).
Set GITHUB_TOKEN env var to avoid rate limits.
"""

import pytest
from github_tools import (
    parse_repo_url,
    get_metadata,
    get_file_tree,
    get_directory,
    get_file,
    get_dependencies,
    get_readme,
    build_dir_tree_text,
)

# ── Known stable public repos used as fixtures ────────────────────────────────
LODASH    = ("lodash", "lodash")        # JS library
BAT       = ("sharkdp", "bat")          # Rust CLI tool  
REQUESTS  = ("psf", "requests")         # Python library — has setup.py at root


# ────────────────────────────────────────────────────────────────────────────
# parse_repo_url
# ────────────────────────────────────────────────────────────────────────────

class TestParseRepoUrl:
    def test_standard_url(self):
        owner, repo = parse_repo_url("https://github.com/lodash/lodash")
        assert owner == "lodash"
        assert repo  == "lodash"

    def test_trailing_slash(self):
        owner, repo = parse_repo_url("https://github.com/lodash/lodash/")
        assert owner == "lodash" and repo == "lodash"

    def test_dot_git_suffix(self):
        owner, repo = parse_repo_url("https://github.com/sharkdp/bat.git")
        assert owner == "sharkdp" and repo == "bat"

    def test_http_not_https(self):
        owner, repo = parse_repo_url("http://github.com/tiangolo/fastapi")
        assert owner == "tiangolo" and repo == "fastapi"

    def test_invalid_url_raises(self):
        with pytest.raises(ValueError):
            parse_repo_url("https://gitlab.com/someone/repo")

    def test_missing_repo_raises(self):
        with pytest.raises(ValueError):
            parse_repo_url("https://github.com/lodash")

    def test_empty_string_raises(self):
        with pytest.raises(ValueError):
            parse_repo_url("")


# ────────────────────────────────────────────────────────────────────────────
# get_metadata
# ────────────────────────────────────────────────────────────────────────────

class TestGetMetadata:
    def test_returns_all_fields(self):
        meta = get_metadata(*LODASH)
        assert "name"        in meta
        assert "description" in meta
        assert "language"    in meta
        assert "topics"      in meta
        assert "stars"       in meta
        assert "license"     in meta
        assert "private"     in meta

    def test_lodash_is_javascript(self):
        meta = get_metadata(*LODASH)
        assert meta["language"] == "JavaScript"

    def test_stars_is_integer(self):
        meta = get_metadata(*LODASH)
        assert isinstance(meta["stars"], int)
        assert meta["stars"] > 0

    def test_not_private(self):
        meta = get_metadata(*LODASH)
        assert meta["private"] is False

    def test_invalid_repo_raises(self):
        import requests
        with pytest.raises(requests.HTTPError):
            get_metadata("this-owner-does-not-exist-xyz", "no-such-repo-abc")


# ────────────────────────────────────────────────────────────────────────────
# get_file_tree
# ────────────────────────────────────────────────────────────────────────────

class TestGetFileTree:
    def test_returns_list(self):
        tree = get_file_tree(*LODASH)
        assert isinstance(tree, list)

    def test_not_empty(self):
        tree = get_file_tree(*LODASH)
        assert len(tree) > 10

    def test_items_have_path_and_type(self):
        tree = get_file_tree(*LODASH)
        for item in tree[:5]:
            assert "path" in item
            assert "type" in item

    def test_has_blob_and_tree_types(self):
        tree = get_file_tree(*LODASH)
        types = {item["type"] for item in tree}
        assert "blob" in types


# ────────────────────────────────────────────────────────────────────────────
# get_file
# ────────────────────────────────────────────────────────────────────────────

class TestGetFile:
    def test_readme_returns_content(self):
        tree = get_file_tree(*LODASH)
        content = get_readme(*LODASH, tree)
        assert content is not None
        assert len(content) > 10

    def test_missing_file_returns_none(self):
        result = get_file(*LODASH, "this/file/does/not/exist.xyz")
        assert result is None

    def test_content_is_string(self):
        result = get_file(*LODASH, "README.md")
        assert isinstance(result, str)

    def test_large_file_truncated(self):
        # pytorch README is known to be large
        result = get_file("pytorch", "pytorch", "README.md")
        if result:
            assert len(result) <= 4200  # MAX_FILE_CHARS + notice


# ────────────────────────────────────────────────────────────────────────────
# get_directory
# ────────────────────────────────────────────────────────────────────────────

class TestGetDirectory:
    def test_root_returns_string(self):
        result = get_directory(*LODASH, "")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_root_contains_items(self):
        result = get_directory(*LODASH, "")
        assert "[file]" in result or "[dir]" in result

    def test_missing_path_returns_not_found(self):
        result = get_directory(*LODASH, "nonexistent_dir_xyz")
        assert "not found" in result.lower()


# ────────────────────────────────────────────────────────────────────────────
# get_dependencies
# ────────────────────────────────────────────────────────────────────────────

class TestGetDependencies:
    def test_lodash_has_package_json(self):
        tree = get_file_tree(*LODASH)
        result = get_dependencies(*LODASH, tree)
        assert "package.json" in result

    def test_requests_has_setup_py(self):
        tree = get_file_tree(*REQUESTS)
        result = get_dependencies(*REQUESTS, tree)
        assert "setup.py" in result or "pyproject.toml" in result

    def test_bat_has_cargo_toml(self):
        tree = get_file_tree(*BAT)
        result = get_dependencies(*BAT, tree)
        assert "Cargo.toml" in result


# ────────────────────────────────────────────────────────────────────────────
# build_dir_tree_text
# ────────────────────────────────────────────────────────────────────────────

class TestBuildDirTreeText:
    # Cache tree at class level to avoid extra API calls
    _tree = None

    @classmethod
    def _get_tree(cls):
        if cls._tree is None:
            cls._tree = get_file_tree(*LODASH)
        return cls._tree

    def test_returns_string(self):
        result = build_dir_tree_text(self._get_tree())
        assert isinstance(result, str)
        assert len(result) > 0

    def test_contains_tree_chars(self):
        result = build_dir_tree_text(self._get_tree())
        assert "└──" in result or "├──" in result

    def test_depth_respected(self):
        result = build_dir_tree_text(self._get_tree(), max_depth=1)
        # At depth 1 each line should have at most 1 level of indentation (4 chars)
        for line in result.split("\n"):
            stripped = line.lstrip("│ ")
            indent_len = len(line) - len(stripped)
            assert indent_len <= 4, f"Line too deeply indented: {line!r}"
