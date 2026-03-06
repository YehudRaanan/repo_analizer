"""
examples_store.py — Save and load collected repo context per type.

Directory structure:
  examples/
    library/      ← .txt files for known library repos
    cli_tool/
    web_app/
    backend/
    data_ml/
    infra/

Every successful analysis appends a new file here so the prompt builder
can load richer few-shot examples over time.
"""

import os
import random

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EXAMPLES_DIR = os.path.join(BASE_DIR, "examples")

VALID_TYPES = {"library", "cli_tool", "web_app", "backend", "data_ml", "infra"}


def _type_dir(repo_type: str) -> str:
    """Return the directory path for a given repo type."""
    return os.path.join(EXAMPLES_DIR, repo_type)


def all_type_dirs_exist() -> bool:
    """Check that all 6 type directories exist under examples/."""
    return all(os.path.isdir(_type_dir(t)) for t in VALID_TYPES)


def list_examples(repo_type: str) -> list[str]:
    """
    Return sorted list of .txt filenames available for a given type.
    Returns empty list if type is unknown or directory is empty.
    """
    if repo_type not in VALID_TYPES:
        return []
    type_dir = _type_dir(repo_type)
    if not os.path.isdir(type_dir):
        return []
    return sorted(
        f for f in os.listdir(type_dir)
        if f.endswith(".txt") and not f.endswith("_classify.txt")
    )


def get_examples(repo_type: str, n: int = 2, strategy: str = "random") -> str:
    """
    Return the content of up to `n` example files for the given repo type,
    concatenated as a single string.

    strategy: "random" (default) | "first"
      - "random": picks n random examples (good for variety)
      - "first":  picks the first n alphabetically (good for determinism in tests)

    Returns empty string if no examples found.
    """
    files = list_examples(repo_type)
    if not files:
        return ""

    if strategy == "random":
        chosen = random.sample(files, min(n, len(files)))
    else:
        chosen = files[:n]

    parts = []
    type_dir = _type_dir(repo_type)
    for fname in chosen:
        path = os.path.join(type_dir, fname)
        try:
            with open(path, encoding="utf-8") as f:
                content = f.read()
            parts.append(f"=== EXAMPLE: {fname} ===\n{content}")
        except OSError:
            continue

    return "\n\n".join(parts)


def save_example(repo_name: str, repo_type: str, content: str) -> str:
    """
    Save a collected context string to examples/{repo_type}/{repo_name}.txt.

    If the file already exists, it is overwritten (fresh analysis always wins).
    Returns the path of the saved file.

    Raises ValueError for unknown repo types.
    """
    if repo_type not in VALID_TYPES:
        raise ValueError(
            f"Unknown repo type {repo_type!r}. Must be one of: {sorted(VALID_TYPES)}"
        )

    type_dir = _type_dir(repo_type)
    os.makedirs(type_dir, exist_ok=True)

    # Sanitize repo_name to be a safe filename
    safe_name = repo_name.replace("/", "_").replace("\\", "_")
    if not safe_name.endswith(".txt"):
        safe_name += ".txt"

    out_path = os.path.join(type_dir, safe_name)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)

    return out_path
