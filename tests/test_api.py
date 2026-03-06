"""
test_api.py — Unit tests for the FastAPI endpoint using TestClient.

Tests validation and HTTP status codes. Mocks the actual LLM `analyze()` call
so tests run instantly and without API keys.
"""

from fastapi.testclient import TestClient
import pytest
from unittest.mock import patch

from api import app

# ── Test Client Setup ────────────────────────────────────────────────────────

client = TestClient(app)


# ── Mocks ────────────────────────────────────────────────────────────────────

# A successfully mocked analyze_repo.analyze response
MOCK_ANALYZE_RESULT = {
    "summary": "This is a mock repository.",
    "technologies": ["Python", "Pytest", "FastAPI"],
    "structure": "A very mocky structure.",
    "repo_type": "backend",
    "repo_name": "mock-repo"
}


# ── Tests ────────────────────────────────────────────────────────────────────

@patch("api.analyze")
def test_summarize_valid_url(mock_analyze):
    """Test a valid GitHub URL returns 200 and the structured summary."""
    mock_analyze.return_value = MOCK_ANALYZE_RESULT

    response = client.post(
        "/summarize",
        json={"github_url": "https://github.com/owner/mock-repo"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["summary"] == "This is a mock repository."
    assert "Pytest" in data["technologies"]
    assert data["structure"] == "A very mocky structure."

    # Verify the mocked function was called with the correct string URL (ignoring trailing slash)
    called_url = mock_analyze.call_args[0][0]
    assert called_url.rstrip("/") == "https://github.com/owner/mock-repo"
    assert mock_analyze.call_args[1].get("verbose") is True


@patch("api.analyze")
def test_summarize_invalid_url_format(mock_analyze):
    """Test a fundamentally malformed URL returns a 422 Unprocessable Entity."""
    response = client.post(
        "/summarize",
        json={"github_url": "not-a-url"}
    )
    # Pydantic HttpUrl validation fails before our custom logic
    assert response.status_code == 422
    assert not mock_analyze.called


@patch("api.analyze")
def test_summarize_not_github_url(mock_analyze):
    """Test a valid URL that is NOT GitHub (e.g. GitLab) is rejected."""
    response = client.post(
        "/summarize",
        json={"github_url": "https://gitlab.com/owner/repo"}
    )
    # Our parse_repo_url validation raises ValueError -> 422 HTTP
    assert response.status_code == 422
    assert "Invalid GitHub URL" in response.text
    assert not mock_analyze.called


@patch("api.analyze")
def test_summarize_missing_body(mock_analyze):
    """Test an empty or missing JSON payload returns a 422 Validation Error."""
    response = client.post("/summarize")
    assert response.status_code == 422
    assert not mock_analyze.called


@patch("api.analyze")
def test_summarize_http_error(mock_analyze):
    """Test that a 404 from GitHub is properly surfaced as a 404 from our API."""
    import requests
    
    # Mock a Requests 404 HTTPError Response
    response_mock = requests.Response()
    response_mock.status_code = 404
    response_mock.reason = "Not Found"
    mock_analyze.side_effect = requests.exceptions.HTTPError(response=response_mock)

    response = client.post(
        "/summarize",
        json={"github_url": "https://github.com/this-repo/does-not-exist-xyz"}
    )
    
    # We catch the Requests HTTPError and raise an HTTPException
    assert response.status_code == 404
    assert "Not Found" in response.json()["detail"]


@patch("api.analyze")
def test_summarize_internal_server_error(mock_analyze):
    """Test that a generic unhandled exception results in a 500 error."""
    mock_analyze.side_effect = Exception("A catastrophic database failure!")

    response = client.post(
        "/summarize",
        json={"github_url": "https://github.com/owner/repo"}
    )

    assert response.status_code == 500
    assert "Internal Server Error" in response.json()["detail"]
