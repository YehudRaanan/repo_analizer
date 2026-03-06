"""
tests/test_prompt_builder.py

Unit tests for prompt_builder.py — all local, no API calls.
"""

import pytest
from prompt_builder import (
    build_system_prompt,
    build_final_prompt,
    TOOL_DESCRIPTIONS,
    VALID_TYPES,
    TYPE_HEURISTICS,
)


# ────────────────────────────────────────────────────────────────────────────
# build_system_prompt
# ────────────────────────────────────────────────────────────────────────────

class TestBuildSystemPrompt:
    def test_runs_for_all_types(self):
        """build_system_prompt should not raise for any valid type."""
        for t in VALID_TYPES:
            prompt = build_system_prompt(t)
            assert isinstance(prompt, str)
            assert len(prompt) > 100

    def test_contains_type_heuristics_library(self):
        prompt = build_system_prompt("library")
        assert "setup.py" in prompt or "pyproject.toml" in prompt

    def test_contains_type_heuristics_cli(self):
        prompt = build_system_prompt("cli_tool")
        assert "cmd/" in prompt or "bin/" in prompt or "Cargo.toml" in prompt

    def test_contains_type_heuristics_web_app(self):
        prompt = build_system_prompt("web_app")
        assert "next.config" in prompt or "components/" in prompt

    def test_contains_type_heuristics_backend(self):
        prompt = build_system_prompt("backend")
        assert "routes/" in prompt or "manage.py" in prompt

    def test_contains_type_heuristics_data_ml(self):
        prompt = build_system_prompt("data_ml")
        assert ".ipynb" in prompt or "training/" in prompt

    def test_contains_type_heuristics_infra(self):
        prompt = build_system_prompt("infra")
        assert ".tf" in prompt or "Chart.yaml" in prompt

    def test_contains_tool_descriptions(self):
        prompt = build_system_prompt("library")
        assert "get_file" in prompt
        assert "get_directory" in prompt
        assert "get_type_examples" in prompt
        assert "get_dependencies" in prompt

    def test_contains_done_instruction(self):
        prompt = build_system_prompt("library")
        assert "DONE" in prompt

    def test_contains_few_shot_example(self):
        """Prompt should include at least one reference example from the store."""
        prompt = build_system_prompt("library", n_examples=1)
        assert "EXAMPLE:" in prompt or "Reference Example" in prompt

    def test_prompt_length_reasonable(self):
        """Prompt should fit well within LLM context limits (~16k chars ≈ 4k tokens)."""
        for t in VALID_TYPES:
            prompt = build_system_prompt(t, n_examples=1)
            assert len(prompt) < 20_000, f"Prompt for {t!r} is too long: {len(prompt)} chars"

    def test_unknown_type_does_not_crash(self):
        """'other' type has no heuristics but should still produce a valid prompt."""
        prompt = build_system_prompt("other")
        assert isinstance(prompt, str)
        assert "get_file" in prompt  # tools always included

    def test_react_format_included(self):
        prompt = build_system_prompt("backend")
        assert "Thought:" in prompt
        assert "Action:" in prompt


# ────────────────────────────────────────────────────────────────────────────
# build_final_prompt
# ────────────────────────────────────────────────────────────────────────────

class TestBuildFinalPrompt:
    def test_returns_string(self):
        result = build_final_prompt("signals text", "collected context")
        assert isinstance(result, str)

    def test_contains_signals(self):
        result = build_final_prompt("SIGNAL_DATA_HERE", "ctx")
        assert "SIGNAL_DATA_HERE" in result

    def test_contains_collected_context(self):
        result = build_final_prompt("signals", "COLLECTED_CONTEXT_HERE")
        assert "COLLECTED_CONTEXT_HERE" in result

    def test_contains_three_questions(self):
        result = build_final_prompt("s", "c")
        assert "Summary" in result
        assert "Technologies" in result
        assert "Structure" in result
