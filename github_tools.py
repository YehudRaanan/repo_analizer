"""
github_tools.py — Atomic GitHub API functions for the ReAct agent.

All GitHub interactions go through this module. Each function is a thin,
focused wrapper around a single GitHub API operation.
"""

import os
import re
import requests

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
API_BASE = "https://api.github.com"
RAW_BASE = "https://raw.githubusercontent.com"

# File size limits to keep context manageable
MAX_FILE_CHARS = 4000
MAX_TREE_ITEMS = 500  # truncate huge monorepos

# Binary/Generic file types to ignore to save context/API calls
BINARY_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".pdf", ".zip", ".gz",
    ".exe", ".dll", ".so", ".bin", ".pyc", ".ipynb_checkpoints", ".DS_Store"
}


# ── Auth ─────────────────────────────────────────────────────────────────────

def _headers() -> dict:
    h = {"Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN:
        h["Authorization"] = f"token {GITHUB_TOKEN}"
    return h


# ── URL parsing ───────────────────────────────────────────────────────────────

def parse_repo_url(url: str) -> tuple[str, str]:
    """
    Extract (owner, repo) from a GitHub URL.
    Accepts: https://github.com/owner/repo[.git][/]
    Raises ValueError for invalid URLs.
    """
    match = re.match(
        r"https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$", url.strip()
    )
    if not match:
        raise ValueError(f"Invalid GitHub URL: {url!r}")
    return match.group(1), match.group(2)


# ── Metadata ──────────────────────────────────────────────────────────────────

def get_metadata(owner: str, repo: str) -> dict:
    """
    Fetch basic repo metadata: name, description, language, topics, stars, license.
    """
    r = requests.get(f"{API_BASE}/repos/{owner}/{repo}", headers=_headers(), timeout=15)
    r.raise_for_status()
    data = r.json()
    return {
        "name":        data.get("name", ""),
        "description": data.get("description", "") or "",
        "language":    data.get("language", "") or "",
        "topics":      data.get("topics", []),
        "stars":       data.get("stargazers_count", 0),
        "license":     (data.get("license") or {}).get("name", "N/A"),
        "private":     data.get("private", False),
    }


# ── File tree ─────────────────────────────────────────────────────────────────

def get_file_tree(owner: str, repo: str) -> list[dict]:
    """
    Fetch the recursive file tree. Returns a list of {path, type, size} dicts.
    Truncated to MAX_TREE_ITEMS entries for very large repos.
    """
    r = requests.get(
        f"{API_BASE}/repos/{owner}/{repo}/git/trees/HEAD?recursive=1",
        headers=_headers(),
        timeout=20,
    )
    r.raise_for_status()
    tree = r.json().get("tree", [])
    return tree[:MAX_TREE_ITEMS]


def get_directory(owner: str, repo: str, path: str = "") -> str:
    """
    List the contents of a directory (non-recursive).
    Returns a formatted text block with file/dir names.
    """
    url = f"{API_BASE}/repos/{owner}/{repo}/contents/{path}"
    r = requests.get(url, headers=_headers(), timeout=15)
    if r.status_code == 404:
        return f"(directory not found: {path!r})"
    r.raise_for_status()
    items = r.json()
    if not isinstance(items, list):
        return "(not a directory)"
    lines = []
    for item in sorted(items, key=lambda x: (x["type"] != "dir", x["name"])):
        prefix = "[dir]" if item["type"] == "dir" else "[file]"
        lines.append(f"  {prefix} {item['name']}")
    header = f"Contents of /{path or '(root)'}:"
    return header + "\n" + "\n".join(lines)


# ── File content ──────────────────────────────────────────────────────────────

def get_file(owner: str, repo: str, path: str) -> str | None:
    """
    Fetch the raw content of a single file.
    Returns None if the file doesn't exist.
    Truncates at MAX_FILE_CHARS with a notice.
    Skips binary files based on extension.
    """
    ext = os.path.splitext(path)[1].lower()
    if ext in BINARY_EXTENSIONS:
        return f"(Skipping binary/unsupported file: {path})"

    url = f"{RAW_BASE}/{owner}/{repo}/HEAD/{path}"
    r = requests.get(url, headers=_headers(), timeout=15)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    text = r.text
    if len(text) > MAX_FILE_CHARS:
        text = text[:MAX_FILE_CHARS] + f"\n... [TRUNCATED — showing first {MAX_FILE_CHARS} chars]"
    return text


# ── Dependencies ──────────────────────────────────────────────────────────────

# Priority-ordered manifest files to try
MANIFEST_CANDIDATES = [
    "package.json",
    "pyproject.toml",
    "requirements.txt",
    "Cargo.toml",
    "go.mod",
    "pom.xml",
    "build.gradle",
    "Gemfile",
    "composer.json",
    "environment.yml",
]


def get_dependencies(owner: str, repo: str, tree: list[dict]) -> str:
    """
    Find and return the content of the most relevant dependency/manifest file(s).
    Checks root-level files from MANIFEST_CANDIDATES.
    """
    root_files = {
        item["path"]
        for item in tree
        if item["type"] == "blob" and "/" not in item["path"]
    }
    found = []
    for candidate in MANIFEST_CANDIDATES:
        if candidate in root_files:
            content = get_file(owner, repo, candidate)
            if content:
                found.append(f"[{candidate}]\n{content}")
    if not found:
        return "(no dependency/manifest files found at repo root)"
    return "\n\n".join(found)


# ── README ────────────────────────────────────────────────────────────────────

def get_readme(owner: str, repo: str, tree: list[dict]) -> str:
    """
    Find and return the README content (any common README filename).
    """
    readme_re = re.compile(r"^readme(\.(md|rst|txt))?$", re.IGNORECASE)
    for item in tree:
        if item["type"] == "blob" and "/" not in item["path"]:
            if readme_re.match(item["path"]):
                content = get_file(owner, repo, item["path"])
                return content or "(README found but empty)"
    return "(no README found)"


# ── Directory tree text ───────────────────────────────────────────────────────

def build_dir_tree_text(tree: list[dict], max_depth: int = 2) -> str:
    """
    Build a human-readable directory tree string (like `tree` command output).
    """
    lines = []
    entries: dict[str, list[tuple[str, int]]] = {}

    for item in tree:
        parts = item["path"].split("/")
        if len(parts) > max_depth + 1:
            continue
        depth = len(parts) - 1
        name = parts[-1] + ("/" if item["type"] == "tree" else "")
        parent = "/".join(parts[:-1]) if depth > 0 else ""
        entries.setdefault(parent, []).append((name, depth))

    def render(parent: str = "", indent: str = "") -> None:
        children = entries.get(parent, [])
        for i, (name, _) in enumerate(children):
            is_last = i == len(children) - 1
            connector = "└── " if is_last else "├── "
            lines.append(f"{indent}{connector}{name}")
            if name.endswith("/"):
                child_key = f"{parent}/{name[:-1]}" if parent else name[:-1]
                next_indent = indent + ("    " if is_last else "│   ")
                render(child_key, next_indent)

    render()
    return "\n".join(lines) if lines else "(empty)"


# ── Convenience: classify signals (wraps classify_collector logic) ─────────────

def collect_classify_signals(owner: str, repo: str) -> str:
    """
    Run the classification signal collector and return the signals as a text string.
    """
    # Import inline to avoid circular deps
    import sys, importlib, io
    from collections import Counter

    meta = get_metadata(owner, repo)
    tree = get_file_tree(owner, repo)

    # Heuristic definitions
    WEB_APP_EXTENSIONS = {".tsx", ".jsx", ".vue", ".svelte"}
    ML_EXTENSIONS = {".ipynb"}
    INFRA_EXTENSIONS = {".tf", ".hcl"}
    BACKEND_EXTENSIONS = {".proto", ".graphql"}

    WEB_APP_ROOT_FILE_WEIGHTS = {"next.config.js": 10, "nuxt.config.js": 10, "svelte.config.js": 10, "package.json": 2}
    BACKEND_ROOT_FILE_WEIGHTS = {"manage.py": 8, "alembic.ini": 9, "knexfile.js": 8, "ormconfig.json": 8, "Procfile": 5}
    CLI_ROOT_FILE_WEIGHTS = {".goreleaser.yml": 9, "CMakeLists.txt": 3, "Justfile": 2}
    ML_ROOT_FILE_WEIGHTS = {"environment.yml": 5, "dvc.yaml": 9, "MLproject": 10, "model_card.md": 6}
    INFRA_ROOT_FILE_WEIGHTS = {"main.tf": 10, "Pulumi.yaml": 10, "ansible.cfg": 9, "Playbook.yml": 8}
    GENERIC_MANIFEST_FILES = {"package.json", "pyproject.toml", "setup.py", "Cargo.toml", "go.mod", "pom.xml", "requirements.txt"}

    WEB_APP_DIR_WEIGHTS = {"pages": 5, "components": 5, "layouts": 6}
    BACKEND_DIR_WEIGHTS = {"routes": 6, "controllers": 6, "endpoints": 7}
    LIBRARY_DIR_WEIGHTS = {"benchmarks": 3}
    CLI_DIR_WEIGHTS = {"cmd": 7, "commands": 5, "cli": 4}
    ML_DIR_WEIGHTS = {"notebooks": 7, "training": 6, "models": 4}
    INFRA_DIR_WEIGHTS = {"terraform": 9, "charts": 6, "manifests": 5, "ansible": 8}

    root_files = set()
    top_dirs = set()
    ext_counter = Counter()

    # Generic boolean pattern checks
    patterns = {
        "has_pages_or_app_dir": False,
        "has_components_dir": False,
        "has_cmd_or_bin_dir": False,
        "has_run_train_scripts": False,
        "has_ipynb_files": False,
        "has_k8s_manifests": False,
        "has_route_controller_dirs": False,
        "has_dockerfile": False
    }

    for item in tree:
        path = item["path"]
        pl = path.lower()
        
        if item["type"] == "blob" and "/" not in path:
            root_files.add(path)
        if item["type"] == "tree" and "/" not in path:
            top_dirs.add(path)
        if item["type"] == "blob":
            dot = path.rfind(".")
            if dot != -1:
                ext_counter[path[dot:].lower()] += 1

        import re
        if re.match(r"^(pages|app)/", pl): patterns["has_pages_or_app_dir"] = True
        if re.match(r"^components/", pl): patterns["has_components_dir"] = True
        if re.match(r"^(cmd|bin)/", pl): patterns["has_cmd_or_bin_dir"] = True
        if re.search(r"(run_|train_)\w+\.py$", pl): patterns["has_run_train_scripts"] = True
        if pl.endswith(".ipynb"): patterns["has_ipynb_files"] = True
        if re.search(r"(deployment|service|ingress)\.(ya?ml)$", pl): patterns["has_k8s_manifests"] = True
        if re.match(r"^(routes|controllers|api)/", pl): patterns["has_route_controller_dirs"] = True
        if pl == "dockerfile" or re.match(r"^dockerfile", pl): patterns["has_dockerfile"] = True

    def fmt(s):
        return ", ".join(sorted(s)) if s else "(none)"

    web_ext  = sum(ext_counter.get(e, 0) for e in WEB_APP_EXTENSIONS)
    ml_ext   = sum(ext_counter.get(e, 0) for e in ML_EXTENSIONS)
    infra_ext = sum(ext_counter.get(e, 0) for e in INFRA_EXTENSIONS)
    be_ext   = sum(ext_counter.get(e, 0) for e in BACKEND_EXTENSIONS)
    top_exts = "\n".join(f"  {e}: {c}" for e, c in ext_counter.most_common(15))
    bool_lines = "\n".join(
        f"  {k.replace('has_', '').replace('_', ' ')}: {'yes' if v else 'no'}"
        for k, v in patterns.items()
    )

    return f"""=====================================
REPO CLASSIFICATION SIGNALS
=====================================

--- METADATA ---
Name: {meta['name']}
Description: {meta['description']}
Primary language: {meta['language']}
Topics: {', '.join(meta['topics']) if meta['topics'] else 'N/A'}

--- ROOT FILES (signal matches) ---
Web App:     {fmt(root_files & set(WEB_APP_ROOT_FILE_WEIGHTS))}
Backend:     {fmt(root_files & set(BACKEND_ROOT_FILE_WEIGHTS))}
Library:     {fmt(root_files & GENERIC_MANIFEST_FILES)}
CLI:         {fmt(root_files & set(CLI_ROOT_FILE_WEIGHTS))}
Data/ML:     {fmt(root_files & set(ML_ROOT_FILE_WEIGHTS))}
Infra:       {fmt(root_files & set(INFRA_ROOT_FILE_WEIGHTS))}

--- TOP-LEVEL DIRECTORIES (signal matches) ---
Web App:     {fmt(top_dirs & set(WEB_APP_DIR_WEIGHTS))}
Backend:     {fmt(top_dirs & set(BACKEND_DIR_WEIGHTS))}
Library:     {fmt(top_dirs & set(LIBRARY_DIR_WEIGHTS))}
CLI:         {fmt(top_dirs & set(CLI_DIR_WEIGHTS))}
Data/ML:     {fmt(top_dirs & set(ML_DIR_WEIGHTS))}
Infra:       {fmt(top_dirs & set(INFRA_DIR_WEIGHTS))}

--- ALL TOP-LEVEL DIRECTORIES ---
{fmt(top_dirs)}

--- TYPE-SPECIFIC EXTENSION COUNTS ---
Web App extensions (.tsx, .jsx, .vue, .svelte): {web_ext}
Data/ML extensions (.ipynb): {ml_ext}
Infra extensions (.tf, .hcl): {infra_ext}
Backend extensions (.proto, .graphql): {be_ext}

--- TOP FILE EXTENSIONS (by count) ---
{top_exts}

--- BOOLEAN PATTERN CHECKS ---
{bool_lines}
"""
