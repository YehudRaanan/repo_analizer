import pytest
from analyze_repo import analyze


@pytest.mark.integration
class TestEndToEnd:
    """
    End-to-End integration tests for analyze_repo.py.
    Requires GITHUB_TOKEN and NEBIUS_API_KEY in .env.
    """

    def test_e2e_library(self):
        result = analyze("https://github.com/lodash/lodash", verbose=False)
        assert result["repo_type"] == "library"
        assert result["repo_name"] == "lodash"
        assert result["summary"]
        techs = [t.lower() for t in result["technologies"]]
        # Llama might say "JavaScript", "Node.js", "npm" etc.
        assert any("javascript" in t or "node" in t for t in techs)

    def test_e2e_cli_tool(self):
        result = analyze("https://github.com/sharkdp/bat", verbose=False)
        assert result["repo_type"] == "cli_tool"
        assert result["repo_name"] == "bat"
        techs = [t.lower() for t in result["technologies"]]
        assert any("rust" in t or "cargo" in t for t in techs)

    def test_e2e_infra(self):
        result = analyze("https://github.com/hashicorp/terraform-aws-consul", verbose=False)
        assert result["repo_type"] == "infra"
        techs = [t.lower() for t in result["technologies"]]
        assert any("terraform" in t for t in techs)

    def test_e2e_web_app(self):
        result = analyze("https://github.com/calcom/cal.com", verbose=False)
        assert result["repo_type"] == "web_app"
        techs = [t.lower() for t in result["technologies"]]
        assert any(t in ["typescript", "next.js", "react", "trpc", "prisma"] for t in techs)
        assert "apps" in result["structure"].lower() or "packages" in result["structure"].lower()

    def test_e2e_data_ml(self):
        result = analyze("https://github.com/huggingface/transformers", verbose=False)
        assert result["repo_type"] == "data_ml"
        techs = [t.lower() for t in result["technologies"]]
        assert any("python" in t or "pytorch" in t for t in techs)
        assert "transformer" in result["summary"].lower()
