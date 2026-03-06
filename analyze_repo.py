"""
analyze_repo.py — Main orchestrator for the ReAct repo analyzer.

Pipeline:
  Step 1: collect_classify_signals(url)  → initial signals text (2 GitHub API calls)
  Step 2: build_system_prompt(repo_type) → enriched system prompt (local, no API)
  Step 3: LLM call #1                   → classify repo type
  Step 4: run_react_loop()              → ReAct agent gathers details (up to 8 tool calls)
  Step 5: get_final_answer()            → LLM call #2 → structured answer
  Step 5: save_example()               → persist to examples/{type}/ for future runs

Usage:
  python analyze_repo.py https://github.com/lodash/lodash
"""

import os
import re
import sys

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

from github_tools import (
    parse_repo_url,
    get_metadata,
    get_file_tree,
    collect_classify_signals,
    build_dir_tree_text,
)
from prompt_builder import build_system_prompt, build_final_prompt
from react_agent import run_react_loop, get_final_answer, build_tool_dispatcher
from examples_store import save_example, VALID_TYPES

NEBIUS_API_KEY = os.environ.get("NEBIUS_API_KEY", "")
NEBIUS_BASE_URL = "https://api.tokenfactory.nebius.com/v1/"
MODEL = "meta-llama/Llama-3.3-70B-Instruct"

VALID_TYPES_WITH_OTHER = VALID_TYPES | {"other"}


# ── LLM helpers ───────────────────────────────────────────────────────────────

def _make_llm_caller():
    """Create a reusable LLM caller backed by the Nebius Token Factory API."""
    if not NEBIUS_API_KEY:
        raise EnvironmentError(
            "NEBIUS_API_KEY is not set. Add it to your .env file."
        )
    # Add explicit timeout so we don't hang forever on slow API tests
    client = OpenAI(api_key=NEBIUS_API_KEY, base_url=NEBIUS_BASE_URL, timeout=30.0)

    def caller(messages: list[dict], max_tokens: int = 512) -> str:
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            temperature=0.2,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content

    return caller


# ── Step 3: classify repo type via LLM ───────────────────────────────────────

CLASSIFY_SYSTEM = """You are a code repository classifier.
Given structural signals about a GitHub repository, determine its primary type.

Reply with EXACTLY one word from this list:
  library | web_app | cli_tool | backend | data_ml | infra | other

No explanation. Just the type word."""


def classify_repo(signals_text: str, llm_caller) -> str:
    """
    LLM call #1 — classify the repo type from its structural signals.
    Returns one of: library, web_app, cli_tool, backend, data_ml, infra, other
    """
    messages = [
        {"role": "system", "content": CLASSIFY_SYSTEM},
        {"role": "user",   "content": signals_text},
    ]
    raw = llm_caller(messages, max_tokens=10)
    # Extract the type word (be robust to extra whitespace/punctuation)
    for candidate in VALID_TYPES_WITH_OTHER:
        if candidate in raw.lower():
            return candidate
    return "other"


# ── Step 5: parse structured answer ──────────────────────────────────────────

def parse_final_answer(raw_text: str) -> dict:
    """
    Parse the LLM's final answer into {summary, technologies, structure}.
    Handles multiple LLM output formats:
      - **1. Summary** ... **2. Technologies** ... **3. Structure** ...
      - ## Summary ... ## Technologies ... ## Structure ...
    Falls back gracefully if the LLM doesn't follow any format exactly.
    """
    summary = ""
    technologies = []
    structure = ""

    # Pattern A: **1. Summary** / **2. Technologies** / **3. Structure**
    m = re.search(r'\*\*1\.\s*Summary\*\*[:\s]*(.+?)(?=\*\*2\.|\Z)', raw_text, re.DOTALL | re.IGNORECASE)
    if m:
        summary = m.group(1).strip()

    m = re.search(r'\*\*2\.\s*Technologies\*\*[:\s]*(.+?)(?=\*\*3\.|\Z)', raw_text, re.DOTALL | re.IGNORECASE)
    if m:
        tech_text = m.group(1).strip()
        raw_techs = re.split(r'[,\n•\-\*]+', tech_text)
        technologies = [t.strip() for t in raw_techs if t.strip()]

    m = re.search(r'\*\*3\.\s*Structure\*\*[:\s]*(.+?)(?=\*\*|\Z)', raw_text, re.DOTALL | re.IGNORECASE)
    if m:
        structure = m.group(1).strip()

    # Pattern B: ## Summary / ## Technologies / ## Structure
    if not summary:
        m = re.search(r'##\s*Summary[:\s]*\n(.+?)(?=##\s*Technolog|\Z)', raw_text, re.DOTALL | re.IGNORECASE)
        if m:
            summary = m.group(1).strip()

    if not technologies:
        m = re.search(r'##\s*Technolog\w*[:\s]*\n(.+?)(?=##\s*Structure|\Z)', raw_text, re.DOTALL | re.IGNORECASE)
        if m:
            tech_text = m.group(1).strip()
            raw_techs = re.split(r'[,\n•\-\*]+', tech_text)
            technologies = [t.strip() for t in raw_techs if t.strip()]

    if not structure:
        m = re.search(r'##\s*Structure[:\s]*\n(.+?)(?=##|\Z)', raw_text, re.DOTALL | re.IGNORECASE)
        if m:
            structure = m.group(1).strip()

    # Fallback: if parsing failed put everything in summary
    if not summary and not technologies and not structure:
        summary = raw_text.strip()

    return {
        "summary":      summary or raw_text.strip(),
        "technologies": technologies,
        "structure":    structure or "",
    }


# ── Main orchestrator ─────────────────────────────────────────────────────────

def analyze(url: str, verbose: bool = True) -> dict:
    """
    Full pipeline: URL → structured {summary, technologies, structure}.

    Args:
        url:     GitHub repository URL
        verbose: Print progress to stdout

    Returns:
        dict with keys: summary, technologies, structure, repo_type, repo_name
    """
    def log(msg):
        if verbose:
            print(msg)

    # ── Parse URL ──────────────────────────────────────────────────────────
    owner, repo = parse_repo_url(url)
    log(f"\n=> Analyzing: {owner}/{repo}")

    # ── Step 1: Collect classification signals ──────────────────────────────
    log("  [1/5] Collecting classification signals...")
    signals_text = collect_classify_signals(owner, repo)
    tree = get_file_tree(owner, repo)

    # ── LLM client ─────────────────────────────────────────────────────────
    llm_caller = _make_llm_caller()

    # ── Step 3: Classify ────────────────────────────────────────────────────
    log("  [2/5] Classifying repo type...")
    repo_type = classify_repo(signals_text, llm_caller)
    log(f"         -> Type: {repo_type}")

    # ── Step 2: Build system prompt ─────────────────────────────────────────
    log("  [3/5] Building system prompt...")
    system_prompt = build_system_prompt(repo_type, n_examples=1)

    # ── Step 4: ReAct loop ──────────────────────────────────────────────────
    log("  [4/5] Running ReAct analysis loop...")
    tool_dispatcher = build_tool_dispatcher(owner, repo, tree)

    def react_llm(messages):
        return llm_caller(messages, max_tokens=512)

    def _on_step(iteration, thought, tool, arg, observation):
        if not verbose:
            return
        step_num = iteration + 1
        if tool == "DONE":
            print(f"         Step {step_num}: DONE")
            print(f"           Thought: {thought[:120]}{'...' if len(thought) > 120 else ''}")
        else:
            obs_preview = observation[:150].replace('\n', ' ')
            print(f"         Step {step_num}: {tool}({arg})")
            print(f"           Thought: {thought[:120]}{'...' if len(thought) > 120 else ''}")
            print(f"           Result:  {obs_preview}{'...' if len(observation) > 150 else ''}")

    collected_context, final_thought = run_react_loop(
        system_prompt=system_prompt,
        initial_observation=signals_text,
        tool_dispatcher=tool_dispatcher,
        llm_caller=react_llm,
        on_step=_on_step,
    )
    log(f"         -> Collected {len(collected_context)} chars of context")

    # ── Step 5: Final answer ────────────────────────────────────────────────
    log("  [5/5] Generating final answer...")
    final_prompt = build_final_prompt(signals_text, collected_context)

    def final_llm(messages):
        return llm_caller(messages, max_tokens=800)

    raw_answer = get_final_answer(final_prompt, llm_caller=final_llm)
    result = parse_final_answer(raw_answer)
    result["repo_type"] = repo_type
    result["repo_name"] = repo

    # ── Save to examples store ──────────────────────────────────────────────
    if repo_type in VALID_TYPES:
        full_context = f"{signals_text}\n\n{collected_context}"
        saved_path = save_example(repo, repo_type, full_context)
        log(f"         -> Saved to: {saved_path}")

    return result


# ── CLI entry point ───────────────────────────────────────────────────────────

def main():
    if len(sys.argv) != 2:
        print("Usage: python analyze_repo.py <github_repo_url>")
        print("Example: python analyze_repo.py https://github.com/lodash/lodash")
        sys.exit(1)

    url = sys.argv[1]
    result = analyze(url)

    print("\n" + "=" * 60)
    print(f"REPO ANALYSIS: {result.get('repo_name', '')} [{result.get('repo_type', '')}]")
    print("=" * 60)
    print(f"\nSUMMARY\n{result['summary']}")
    print(f"\nTECHNOLOGIES\n{', '.join(result['technologies']) if result['technologies'] else 'Not detected'}")
    print(f"\nSTRUCTURE\n{result['structure']}")
    print()


if __name__ == "__main__":
    main()
