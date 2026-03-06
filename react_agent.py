"""
react_agent.py — ReAct (Reasoning + Acting) agent loop for repo analysis.

The agent iterates through Thought → Action → Observation cycles,
calling GitHub tools to gather information, then produces a final answer.

LLM: Nebius Token Factory API (OpenAI-compatible)
Model: meta-llama/Llama-3.3-70B-Instruct
"""

import os
import re
from typing import Callable

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# ── LLM client setup ──────────────────────────────────────────────────────────

NEBIUS_API_KEY = os.environ.get("NEBIUS_API_KEY", "")
NEBIUS_BASE_URL = "https://api.tokenfactory.nebius.com/v1/"
MODEL = "meta-llama/Llama-3.3-70B-Instruct"
MAX_ITERATIONS = 8


def _llm_client() -> OpenAI:
    if not NEBIUS_API_KEY:
        raise EnvironmentError(
            "NEBIUS_API_KEY is not set. "
            "Add it to your .env file or set it as an environment variable."
        )
    return OpenAI(api_key=NEBIUS_API_KEY, base_url=NEBIUS_BASE_URL)


# ── Tool parsing ──────────────────────────────────────────────────────────────

# Matches: tool_name("arg") or tool_name(arg) or DONE
ACTION_RE = re.compile(
    r'Action:\s*'
    r'(?P<tool>[A-Za-z_]+)'
    r'(?:\((?P<arg>[^)]*)\))?',
    re.IGNORECASE,
)


def parse_action(text: str) -> tuple[str, str]:
    """
    Parse "Action: tool_name(argument)" from a ReAct response.
    Returns (tool_name, argument_string).
    Returns ("DONE", "") if DONE is found.
    Returns ("UNKNOWN", raw_text) if parsing fails.
    """
    # Check for DONE first
    if re.search(r'\bDONE\b', text, re.IGNORECASE):
        return "DONE", ""

    match = ACTION_RE.search(text)
    if not match:
        return "UNKNOWN", text

    tool = match.group("tool").strip()
    arg = (match.group("arg") or "").strip().strip('"\'')
    return tool, arg


# ── Tool dispatcher ──────────────────────────────────────────────────────────

def build_tool_dispatcher(
    owner: str,
    repo: str,
    tree: list[dict],
) -> Callable[[str, str], str]:
    """
    Returns a dispatcher function that routes (tool_name, arg) → result string.
    Closes over the repo context (owner, repo, tree).
    """
    from github_tools import get_file, get_directory, get_dependencies, get_readme
    from examples_store import get_examples

    def dispatch(tool: str, arg: str) -> str:
        tool_lower = tool.lower()

        if tool_lower == "get_file":
            if not arg:
                return "Error: get_file requires a file path argument."
            result = get_file(owner, repo, arg)
            return result if result is not None else f"(file not found: {arg!r})"

        elif tool_lower == "get_directory":
            return get_directory(owner, repo, arg)

        elif tool_lower == "get_dependencies":
            return get_dependencies(owner, repo, tree)

        elif tool_lower == "get_readme":
            return get_readme(owner, repo, tree)

        elif tool_lower == "get_type_examples":
            if arg not in {"library", "web_app", "cli_tool", "backend", "data_ml", "infra"}:
                return f"Unknown type {arg!r}. Valid: library, web_app, cli_tool, backend, data_ml, infra"
            return get_examples(arg, n=1, strategy="first") or f"(no examples found for {arg!r})"

        else:
            return (
                f"Unknown tool {tool!r}. "
                f"Available: get_file, get_directory, get_dependencies, get_readme, get_type_examples"
            )

    return dispatch


# ── ReAct loop ────────────────────────────────────────────────────────────────

def run_react_loop(
    system_prompt: str,
    initial_observation: str,
    tool_dispatcher: Callable[[str, str], str],
    llm_caller: Callable[[list[dict]], str] | None = None,
    max_iterations: int = MAX_ITERATIONS,
    on_step: Callable[[int, str, str, str, str], None] | None = None,
) -> tuple[str, str]:
    """
    Run the ReAct loop until the agent says DONE or max_iterations is reached.

    Args:
        system_prompt: The system prompt (from prompt_builder).
        initial_observation: The initial repo signals text to kick off reasoning.
        tool_dispatcher: A function (tool_name, arg) → observation string.
        llm_caller: Optional override for the LLM call (used in tests for mocking).
                    Signature: (messages: list[dict]) → str
        max_iterations: Maximum number of tool call iterations.
        on_step: Optional callback invoked after each iteration with:
                 (iteration, thought, tool, arg, observation).
                 Use for live logging or post-run trace collection.

    Returns:
        (collected_context, final_thought) tuple.
        collected_context: All observations joined together.
        final_thought: The last Thought before DONE.
    """
    if llm_caller is None:
        client = _llm_client()

        def llm_caller(messages: list[dict]) -> str:
            response = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                temperature=0.2,
                max_tokens=512,
            )
            return response.choices[0].message.content

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": f"Here are the initial repository signals:\n\n{initial_observation}\n\nBegin your analysis."},
    ]

    collected_observations = []
    final_thought = ""
    seen_actions: set[str] = set()  # prevent duplicate tool calls

    for iteration in range(max_iterations):
        # Call LLM
        response_text = llm_caller(messages)
        messages.append({"role": "assistant", "content": response_text})

        # Extract thought for later
        thought_match = re.search(r'Thought:\s*(.+?)(?=\nAction:|$)', response_text, re.DOTALL)
        if thought_match:
            final_thought = thought_match.group(1).strip()

        # Parse action
        tool, arg = parse_action(response_text)

        if tool == "DONE":
            if on_step:
                on_step(iteration, final_thought, "DONE", "", "")
            break

        if tool == "UNKNOWN":
            observation = f"Could not parse an action from your response. Please use format: Action: tool_name(argument)"
        else:
            # Deduplicate
            action_key = f"{tool}({arg})"
            if action_key in seen_actions:
                observation = f"You already called {action_key!r}. Try a different tool or argument, or say DONE."
            else:
                seen_actions.add(action_key)
                observation = tool_dispatcher(tool, arg)

        collected_observations.append(f"[{tool}({arg!r})]\n{observation}")
        messages.append({"role": "user", "content": f"Observation:\n{observation}\n\nContinue your analysis."})

        if on_step:
            on_step(iteration, final_thought, tool, arg, observation)

    collected_context = "\n\n---\n\n".join(collected_observations)
    return collected_context, final_thought


# ── Final answer ──────────────────────────────────────────────────────────────

def get_final_answer(
    final_prompt: str,
    llm_caller: Callable[[list[dict]], str] | None = None,
) -> str:
    """
    Make a single LLM call to produce the structured final answer.

    Args:
        final_prompt: The prompt from prompt_builder.build_final_prompt().
        llm_caller: Optional override for testing.

    Returns:
        Raw LLM response text (to be parsed by the caller).
    """
    if llm_caller is None:
        client = _llm_client()

        def llm_caller(messages: list[dict]) -> str:
            response = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                temperature=0.1,
                max_tokens=800,
            )
            return response.choices[0].message.content

    messages = [
        {
            "role": "system",
            "content": (
                "You are a technical writer. Given repository analysis data, "
                "produce a clear, accurate, structured summary. Be concise and factual."
            ),
        },
        {"role": "user", "content": final_prompt},
    ]
    return llm_caller(messages)
