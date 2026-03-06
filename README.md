# GitHub Repository Analyzer (ReAct Agent)

This application uses a ReAct (Reasoning and Acting) LLM Agent to autonomously explore and analyze GitHub repositories. It determines the repository's purpose, the technologies it uses, and its architectural structure. 

Powered by the **Nebius Token Factory API** (via `meta-llama/Llama-3.3-70B-Instruct`) and **FastAPI**, this system interacts dynamically with the GitHub API to read files, examine directories, and extract key dependencies.

## Architecture & Features

This project abandons static cloning in favor of an active **ReAct Loop**:
1. **Initial Signals**: Fetches basic GitHub metadata and root file types to establish constraints.
2. **Classification**: Uses the LLM to classify the repo as a `library`, `web_app`, `backend`, `cli_tool`, `data_ml`, or `infra`.
3. **Dynamic Prompting**: Loads previous few-shot `examples/{type}/` from disk and explicitly advises the model on what files to look for based on the repository type.
4. **ReAct Loop**: The LLM autonomously uses tools (`get_file`, `get_directory`, `get_dependencies`, etc.) up to 8 times to explore the repository structure until it has enough context.
5. **Final Extraction**: Generates a structured JSON response (Summary, Technologies, Structure).
6. **Self-Improving Memory**: Saves the generated analysis back to the `examples/{type}/` directory so future runs on similar repos become faster and more accurate.

---

## 🧠 Design Decisions

### Model Selection
I chose **Llama-3.3-70B-Instruct** via the Nebius Token Factory. It provides the high reasoning capability required for a multi-step ReAct agent (handling code exploration and logic branching) while remaining significantly more cost-effective and faster than equivalent closed-source models for this specific utility.

### Repository Processing Strategy
To handle large repositories within the LLM context window, this project uses a **dynamic exploration strategy**:
- **Filtering**: Files like binaries (`.png`, `.exe`), lock files, and massive directory deeper than 500 items are automatically skipped or truncated.
- **Signal-First Analysis**: We first fetch a non-recursive root tree and metadata to classify the repo type.
- **Autonomous Tooling**: Instead of guessing which files to send, the LLM uses a `get_file` and `get_directory` toolset to "walk" the repo. It only reads what it needs to understand the architecture (e.g., if it sees a `src/`, it explores it; if it sees `package.json`, it reads it).
- **Truncation**: Every file read is capped at 4,000 characters to prevent a single file from consuming the entire context.

---

## 🚀 Setup & Installation

### 1. Requirements

- Python 3.10+
- A [GitHub Personal Access Token](https://github.com/settings/tokens) (for higher rate limits)
- A [Nebius API Key](https://nebius.com/)

### 2. Install Dependencies

Clone this repository and install the standard requirements:

```bash
pip install -r requirements.txt
```

*(Ensure you have `fastapi`, `uvicorn`, `pydantic`, `requests`, `openai`, `python-dotenv`, and `pytest` installed.)*

### 3. Environment Variables

Create a `.env` file at the root of the project:

```env
GITHUB_TOKEN=github_pat_your_token_here
NEBIUS_API_KEY=your_nebius_api_key_here
```

---

## 💻 Usage

### 1. Run the FastAPI Server

Start the REST API endpoint:

```bash
uvicorn api:app --reload
```

The API will be available at: `http://localhost:8000/summarize` (You can also view the Swagger UI at `http://localhost:8000/docs`).

### 2. Make an API Request

You can summarize a repository by sending a `POST` request with a JSON body containing the `github_url`.

Using `curl`:

```bash
curl -X POST http://localhost:8000/summarize \
     -H "Content-Type: application/json" \
     -d '{"github_url": "https://github.com/supabase/supabase"}'
```

**Expected JSON Response:**
```json
{
  "summary": "Supabase is an open-source Postgres development platform offering real-time databases and authentication.",
  "technologies": [
    "TypeScript",
    "PostgreSQL",
    "Next.js"
  ],
  "structure": "The repository uses a monorepo architecture leveraging Turbo, organized heavily within the `apps/` and `packages/` directories."
}
```

### 3. Command-Line Usage (Testing)

You can bypass the API and orchestrate the analysis directly from the terminal. This provides verbose, real-time logging of the agent's "Thought -> Action" steps.

```bash
python analyze_repo.py https://github.com/lodash/lodash
```

---

## 🧪 Testing

This project includes a comprehensive, multi-layered test suite (100+ tests).

```bash
# Run the full suite (Local Unit Tests + API Mocks + Integration)
pytest tests/ -v
```

- `tests/test_github_tools.py`: Tests individual, atomic GitHub API parsing functions.
- `tests/test_examples_store.py`: Tests the local file storage and retrieval mechanism.
- `tests/test_prompt_builder.py`: Validates the correct heuristic system prompt generation for different repository types.
- `tests/test_react_agent.py`: Uses heavily mocked LLM inputs and outputs to test the `Thought -> Action` dispatch loop offline.
- `tests/test_api.py`: Validates the `FastAPI` endpoint, proper `pydantic` URL parsing, and HTTP mapping.
- `tests/test_e2e.py`: Live integration tests against real GitHub repos spanning all 5 system categories (Requires `.env` tokens).

---

## 📁 Repository Map

- `analyze_repo.py` - Core Orchestrator
- `api.py` - FastAPI application and routes
- `react_agent.py` - Contains the LLM connection and the ReAct looping logic
- `github_tools.py` - API wrappers to `api.github.com` and `raw.githubusercontent.com`
- `prompt_builder.py` - Dynamic LLM system prompt generator
- `examples_store.py` - Manages the `examples/` context database
- `tests/` - The comprehensive test suite
- `archive/` - Contains the earliest iterations of the procedural collectors, kept for historical reference.
