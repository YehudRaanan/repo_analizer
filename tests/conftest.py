"""
conftest.py — loads .env before any test runs so GITHUB_TOKEN
and NEBIUS_API_KEY are available to all test modules.
"""
from dotenv import load_dotenv
import os

# Load .env from the project root (one level up from tests/)
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))
