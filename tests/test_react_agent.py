"""
tests/test_react_agent.py

Unit tests for react_agent.py using mocked LLM responses and tool dispatchers.
No real API calls are made.
"""

import pytest
from react_agent import parse_action, run_react_loop, get_final_answer


# ────────────────────────────────────────────────────────────────────────────
# parse_action
# ────────────────────────────────────────────────────────────────────────────

class TestParseAction:
    def test_parse_get_file(self):
        tool, arg = parse_action('Thought: I need the README.\nAction: get_file("README.md")')
        assert tool == "get_file"
        assert arg == "README.md"

    def test_parse_get_directory(self):
        tool, arg = parse_action("Action: get_directory(src)")
        assert tool == "get_directory"
        assert arg == "src"

    def test_parse_done(self):
        tool, arg = parse_action("Thought: I have enough info.\nAction: DONE")
        assert tool == "DONE"
        assert arg == ""

    def test_parse_done_case_insensitive(self):
        tool, arg = parse_action("Action: done")
        assert tool == "DONE"

    def test_parse_get_type_examples(self):
        tool, arg = parse_action('Action: get_type_examples("library")')
        assert tool == "get_type_examples"
        assert arg == "library"

    def test_parse_no_arg(self):
        tool, arg = parse_action("Action: get_dependencies()")
        assert tool == "get_dependencies"
        assert arg == ""

    def test_parse_unknown_returns_unknown(self):
        tool, arg = parse_action("I don't know what to do.")
        assert tool == "UNKNOWN"


# ────────────────────────────────────────────────────────────────────────────
# run_react_loop
# ────────────────────────────────────────────────────────────────────────────

class TestRunReactLoop:
    """All tests use mocked LLM and tool dispatchers — no API calls."""

    @staticmethod
    def _mock_dispatcher(responses: dict):
        """Returns a dispatcher that returns canned responses per tool."""
        def dispatcher(tool, arg):
            key = f"{tool}({arg})"
            return responses.get(key, f"(mock observation for {key})")
        return dispatcher

    @staticmethod
    def _mock_llm(responses: list[str]):
        """Returns a LLM caller that yields responses in sequence."""
        state = {"idx": 0}
        def caller(messages):
            idx = state["idx"]
            text = responses[idx] if idx < len(responses) else "Action: DONE"
            state["idx"] += 1
            return text
        return caller

    def test_stops_on_done(self):
        llm = self._mock_llm([
            "Thought: I know enough.\nAction: DONE"
        ])
        ctx, thought = run_react_loop(
            system_prompt="system",
            initial_observation="signals",
            tool_dispatcher=lambda t, a: "obs",
            llm_caller=llm,
        )
        assert "DONE" not in ctx  # DONE shouldn't be in the collected context
        assert "enough" in thought

    def test_single_tool_call_then_done(self):
        llm = self._mock_llm([
            'Thought: Check README.\nAction: get_file("README.md")',
            "Thought: Got README.\nAction: DONE",
        ])
        dispatcher = self._mock_dispatcher({
            "get_file(README.md)": "# LodashREADME content here"
        })
        ctx, _ = run_react_loop("sys", "signals", dispatcher, llm)
        assert "get_file" in ctx
        assert "README" in ctx

    def test_correct_tool_called(self):
        called = []
        def dispatcher(tool, arg):
            called.append((tool, arg))
            return "result"

        llm = self._mock_llm([
            'Action: get_file("Cargo.toml")',
            "Action: DONE",
        ])
        run_react_loop("sys", "signals", dispatcher, llm)
        assert ("get_file", "Cargo.toml") in called

    def test_get_type_examples_called(self):
        called = []
        def dispatcher(tool, arg):
            called.append(tool)
            return "example content"

        llm = self._mock_llm([
            'Action: get_type_examples("library")',
            "Action: DONE",
        ])
        run_react_loop("sys", "signals", dispatcher, llm)
        assert "get_type_examples" in called

    def test_max_iterations_respected(self):
        # LLM never says DONE — loop should stop at max_iterations
        llm = self._mock_llm(
            ['Action: get_file("README.md")'] * 20
        )
        dispatcher = lambda t, a: "observation"
        ctx, _ = run_react_loop("sys", "signals", dispatcher, llm, max_iterations=3)
        # Should have at most 3 observations
        assert ctx.count("[get_file(") <= 3

    def test_duplicate_action_blocked(self):
        """Same action called twice should be blocked on second call."""
        llm = self._mock_llm([
            'Action: get_file("README.md")',
            'Action: get_file("README.md")',   # duplicate
            "Action: DONE",
        ])
        observations = []
        def dispatcher(tool, arg):
            observations.append((tool, arg))
            return "content"

        run_react_loop("sys", "signals", dispatcher, llm)
        # Dispatcher should only be called once for the same action
        assert observations.count(("get_file", "README.md")) == 1

    def test_unknown_tool_does_not_crash(self):
        llm = self._mock_llm([
            "Action: nonexistent_tool(arg)",
            "Action: DONE",
        ])
        dispatcher = lambda t, a: "should not be called for unknown"
        ctx, _ = run_react_loop("sys", "signals", dispatcher, llm)
        assert isinstance(ctx, str)

    def test_collected_context_grows(self):
        llm = self._mock_llm([
            'Action: get_file("README.md")',
            'Action: get_directory("src")',
            "Action: DONE",
        ])
        dispatcher = lambda t, a: f"result of {t}({a})"
        ctx, _ = run_react_loop("sys", "signals", dispatcher, llm)
        assert "get_file" in ctx
        assert "get_directory" in ctx

    def test_final_thought_extracted(self):
        llm = self._mock_llm([
            "Thought: This is clearly a CLI tool.\nAction: DONE"
        ])
        _, thought = run_react_loop("sys", "signals", lambda t, a: "obs", llm)
        assert "CLI" in thought or "clearly" in thought


# ────────────────────────────────────────────────────────────────────────────
# get_final_answer
# ────────────────────────────────────────────────────────────────────────────

class TestGetFinalAnswer:
    def test_returns_string(self):
        mock_llm = lambda msgs: "Mock final answer with summary, technologies, structure."
        result = get_final_answer("some prompt", llm_caller=mock_llm)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_passes_prompt_to_llm(self):
        received = []
        def mock_llm(msgs):
            received.extend(msgs)
            return "answer"
        get_final_answer("MY_UNIQUE_PROMPT_TOKEN", llm_caller=mock_llm)
        content = " ".join(m["content"] for m in received)
        assert "MY_UNIQUE_PROMPT_TOKEN" in content
