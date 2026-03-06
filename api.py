"""
api.py — FastAPI endpoint for the ReAct repo analyzer.

Exposes a single endpoint:
  POST /summarize

Accepts JSON:
  {
    "github_url": "https://github.com/owner/repo"
  }

Returns JSON:
  {
    "summary": "...",
    "technologies": ["...", "..."],
    "structure": "..."
  }
"""

import logging
from typing import List
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, HttpUrl
import requests

from analyze_repo import analyze
from github_tools import parse_repo_url

# ── Setup Logging ─────────────────────────────────────────────────────────────

logging.basicConfig(level=logging.INFO, format="%(levelname)s:\t  %(message)s")
logger = logging.getLogger(__name__)

# ── FastAPI App ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="Repo Analyzer",
    description="Analyzes a GitHub repository using a ReAct LLM Agent.",
    version="1.0.0",
)

# ── Pydantic Models ──────────────────────────────────────────────────────────

class SummarizeRequest(BaseModel):
    github_url: HttpUrl


class SummarizeResponse(BaseModel):
    summary: str
    technologies: List[str]
    structure: str


# ── Endpoints ────────────────────────────────────────────────────────────────

@app.post("/summarize", response_model=SummarizeResponse)
def summarize_repo(request: SummarizeRequest):
    """
    Analyzes a GitHub repository using the ReAct agent pipeline and returns
    a concise summary, technology stack, and structural outline.
    """
    url_str = str(request.github_url)

    # 1. Validate the URL format before doing heavy work
    try:
        parse_repo_url(url_str)
    except ValueError as e:
        logger.warning(f"Invalid URL provided: {url_str}")
        raise HTTPException(status_code=422, detail=str(e))

    # 2. Run the analysis loop
    try:
        logger.info(f"Starting analysis for: {url_str}")
        
        # The underlying process can take several minutes due to the LLM.
        # Note: A real production system might use a background task/webhook/WebSocket
        # structure, but this fulfills the assignment requirements directly.
        result = analyze(url_str, verbose=True)
        
        return SummarizeResponse(
            summary=result.get("summary", ""),
            technologies=result.get("technologies", []),
            structure=result.get("structure", "")
        )

    except requests.exceptions.HTTPError as e:
        # E.g. 404 Not Found, 403 Rate Limit, etc. from GitHub API
        status = e.response.status_code
        msg = f"GitHub API error ({status}): {e.response.reason}"
        logger.error(msg)
        raise HTTPException(status_code=status, detail=msg)
    
    except EnvironmentError as e:
        # E.g. Missing NEBIUS_API_KEY
        logger.error(str(e))
        raise HTTPException(status_code=500, detail="Server Configuration Error: Missing API keys.")
    
    except Exception as e:
        # Generic catch-all for LLM parsing errors or other unexpected crashes
        logger.exception("Unexpected error during analysis")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

# ── Entry Point (for local testing) ──────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    # Make sure to run with: uvicorn api:app --reload
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
