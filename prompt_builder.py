"""
prompt_builder.py — Build the ReAct agent system prompt.

Combines:
  1. Role + task description
  2. Available tools with signatures
  3. Per-type heuristics (what to look for per repo type)
  4. Few-shot examples from the examples store
  5. ReAct format instructions
"""

from examples_store import get_examples, VALID_TYPES

# ── Per-type heuristics (distilled from the 7 collector scripts) ──────────────

TYPE_HEURISTICS = {
    "library": """
  - Look for package manifest at root: setup.py, pyproject.toml, Cargo.toml, go.mod, package.json, pom.xml
  - Expect src/ and tests/ (or test/) directories
  - README typically describes the API surface, installation, and usage examples
  - May have examples/ or benchmarks/ directories
  - No server entrypoints (no manage.py, no Procfile, no routes/ directory)
""",

    "web_app": """
  - Look for framework config files: next.config.*, nuxt.config.*, vite.config.*, angular.json, svelte.config.js, astro.config.mjs
  - Expect pages/ or app/ directory (Next.js/Nuxt page routing)
  - Expect components/ directory for UI components
  - Look for .env.example to understand required services
  - Route/page files reveal application structure (routes.js, urls.py, pages/)
  - Heavy use of .tsx, .jsx, .vue, or .svelte file extensions
  - May include tailwind.config.js, postcss.config.js
""",

    "cli_tool": """
  - Look for: .goreleaser.yml, Makefile, Justfile, snap/snapcraft.yaml
  - Expect cmd/, bin/, or cli/ directory (Go / Rust / general CLI layout)
  - Look for src/main.rs, src/main.go, __main__.py, or cli.py as entry points
  - Shell completion files (.bash, .zsh, .fish) and man pages (.1) indicate a mature CLI
  - Cargo.toml with [[bin]] section = Rust CLI; go.mod with cmd/ = Go CLI
  - README usually has a "Usage" section with command examples and flags
""",

    "backend": """
  - Look for: manage.py (Django), alembic.ini (SQLAlchemy), Procfile (Heroku), ormconfig.* (TypeORM)
  - Expect routes/, controllers/, middleware/, api/, routers/, or endpoints/ directories
  - DB migration files in migrations/ or alembic/ indicate a server with a database
  - openapi.yaml or swagger.json describes the API contract
  - .proto files = gRPC service; .graphql files = GraphQL API
  - May have Dockerfile and docker-compose.yml for deployment
""",

    "data_ml": """
  - Look for: environment.yml, dvc.yaml, dvc.lock (DVC pipeline), MLproject (MLflow)
  - Expect notebooks/, data/, training/, models/, inference/, experiments/ directories
  - Jupyter notebooks (.ipynb) indicate exploratory or research work
  - Model/training files: modeling_*.py, trainer.py, train_*.py, run_*.py
  - Config files: config.yaml, hparams.yaml, training_config.yaml
  - Multiple requirements files (requirements.txt, requirements-dev.txt) are common
  - wandb/settings or .dvc/config indicate experiment tracking
""",

    "infra": """
  - Look for: main.tf, variables.tf, outputs.tf (Terraform); Chart.yaml, values.yaml (Helm)
  - Look for: Pulumi.yaml, ansible.cfg, Vagrantfile, kustomization.yaml
  - Expect terraform/, modules/, charts/, k8s/, kubernetes/, manifests/, playbooks/ directories
  - .tf and .hcl file extensions = Terraform/HCL infrastructure code
  - Kubernetes manifest files: deployment.yaml, service.yaml, ingress.yaml
  - Ansible roles: roles/, playbooks/, tasks/main.yml
""",
}

# ── Tool descriptions ──────────────────────────────────────────────────────────

TOOL_DESCRIPTIONS = """
## Available Tools

You can call these tools during your analysis. Use them to gather information.

- **get_file(path)** → returns the raw content of a file at the given path in the repo.
  Example: get_file("README.md"), get_file("Cargo.toml"), get_file("src/main.py")

- **get_directory(path)** → lists files and folders at the given path.
  Use "" for the repo root. Example: get_directory("src"), get_directory("")

- **get_dependencies()** → returns the content of the main dependency/manifest file(s) found at the repo root.
  Use this early to identify technologies.

- **get_type_examples(type)** → returns 1-2 example analyses for repos of the given type.
  Use this when uncertain about a type or what to look for.
  Valid types: library, web_app, cli_tool, backend, data_ml, infra
"""

# ── ReAct format instructions ─────────────────────────────────────────────────

REACT_FORMAT = """
## ReAct Format

Respond in this exact format on every turn:

Thought: [your reasoning about what you know and what you need to find out]
Action: tool_name(argument)

When you have gathered enough information to answer all 3 questions, respond with:

Thought: I have enough information to answer the questions.
Action: DONE

Do not include the final answer yet — it will be requested separately after you say DONE.
Rules:
- Call ONE tool per turn.
- Do not repeat a tool call with the same arguments.
- Maximum 8 tool calls total. Stop and say DONE before reaching the limit.
"""


# ── Main builder function ─────────────────────────────────────────────────────

def build_system_prompt(repo_type: str, n_examples: int = 1) -> str:
    """
    Build the full system prompt for the ReAct agent.

    Args:
        repo_type: The classified type of the repo (from VALID_TYPES or "other").
        n_examples: How many few-shot examples to include from the store.

    Returns:
        A string to use as the system prompt for the LLM.
    """
    # Heuristics section
    heuristics = TYPE_HEURISTICS.get(repo_type, "")
    heuristics_section = ""
    if heuristics:
        heuristics_section = f"""
## What to Look For: {repo_type.replace("_", " ").title()} Repos
{heuristics}"""

    # Few-shot examples section — truncated to keep prompt within context limits
    MAX_EXAMPLE_CHARS = 3000
    examples_text = get_examples(repo_type, n=n_examples, strategy="first")
    if len(examples_text) > MAX_EXAMPLE_CHARS:
        examples_text = examples_text[:MAX_EXAMPLE_CHARS] + "\n... [example truncated for brevity]"
    examples_section = ""
    if examples_text:
        examples_section = f"""
## Reference Example(s) for {repo_type.replace("_", " ").title()} Repos

Below is what a previously collected analysis looks like for this type.
Use this as a reference for what information is typically relevant.

{examples_text}
"""

    return f"""You are an expert code repository analyst. Your job is to analyze a GitHub repository
and gather enough information to answer these 3 questions:

1. **What does this project do?** (1-2 sentences, clear and concrete)
2. **What technologies does it use?** (languages, frameworks, key libraries)
3. **How is it structured?** (main directories, architecture pattern, key files)

You will analyze a **{repo_type.replace("_", " ")}** repository.
{heuristics_section}
{TOOL_DESCRIPTIONS}
{examples_section}
{REACT_FORMAT}
""".strip()


def build_final_prompt(signals: str, collected_context: str) -> str:
    """
    Build the prompt for the final LLM call that produces the structured answer.

    Args:
        signals: The initial classification signals text.
        collected_context: Everything gathered during the ReAct loop.

    Returns:
        A user message prompt for the final answer LLM call.
    """
    return f"""Based on your analysis of the repository, provide a structured summary.

## Repository Signals (initial)
{signals}

## Collected Information
{collected_context}

## Required Output

Answer the following 3 questions clearly and concisely:

**1. Summary** — What does this project do? (2-3 sentences)

**2. Technologies** — List the main technologies, languages, and frameworks used.
Format as a simple list, e.g.: Python, FastAPI, PostgreSQL, Docker

**3. Structure** — How is the project structured?
Describe the key directories and overall architecture pattern (1-2 sentences).
"""
