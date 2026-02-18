"""
LLM factory — initialise and expose Gemini LLM clients.

Extracted from deep_scraper/graph/nodes/config.py.
Reads GOOGLE_API_KEY and GEMINI_MODEL from environment (via .env).
"""

import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv(override=True)

_gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
_google_api_key: str | None = os.getenv("GOOGLE_API_KEY")

if not _google_api_key:
    raise ValueError("GOOGLE_API_KEY environment variable is required")

_google_api_key = _google_api_key.strip()

print(
    f"LLM Init: Model={_gemini_model}, Key={_google_api_key[:4]}...{_google_api_key[-4:]}",
    flush=True,
)

# Single shared LLM instance (both use identical params — collapsed per refactoring plan)
llm = ChatGoogleGenerativeAI(
    model=_gemini_model,
    temperature=0,
    google_api_key=_google_api_key,
    thinking_level="high",
)

# Alias kept for nodes that import llm_high_thinking by name
llm_high_thinking = llm
