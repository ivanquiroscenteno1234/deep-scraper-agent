"""
Shared configuration and utilities for all graph nodes.

Contains:
- LLM client initialization
- Browser adapter helpers
- Common imports for all nodes
"""

import asyncio
import os
from typing import Any, Dict

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from deep_scraper.core.state import AgentState
from deep_scraper.core.mcp_adapter import get_mcp_adapter, MCPBrowserAdapter, reset_mcp_adapter

# Import helpers
from deep_scraper.utils.helpers import (
    extract_llm_text,
    extract_code_from_markdown,
    clean_html_for_llm,
    get_site_name_from_url,
    StructuredLogger,
    NavigationDecision,
    PopupAnalysis,
    PostClickAnalysis,
    PostPopupAnalysis,
    ColumnAnalysis,
)
from deep_scraper.utils.constants import (
    RESULTS_GRID_SELECTORS,
    KNOWN_GRID_COLUMNS,
    DEFAULT_NAVIGATION_TIMEOUT,
    DEFAULT_ELEMENT_TIMEOUT,
    DEFAULT_GRID_WAIT_TIMEOUT,
    MAX_SCRIPT_FIX_ATTEMPTS,
    SCRIPT_TEST_TIMEOUT_SECONDS,
    DEFAULT_HTML_LIMIT,
    POPUP_HTML_LIMIT,
    COLUMN_HTML_LIMIT,
)
from deep_scraper.utils.script_template import build_script_prompt


# ============================================================================
# LLM SETUP
# ============================================================================

load_dotenv(override=True)

gemini_model = os.getenv("GEMINI_MODEL")
google_api_key = os.getenv("GOOGLE_API_KEY")

if google_api_key:
    google_api_key = google_api_key.strip()
else:
    raise ValueError("GOOGLE_API_KEY environment variable is required")

print(f"🤖 LLM Init: Model={gemini_model}, Key={google_api_key[:8]}...{google_api_key[-4:] if google_api_key else ''}", flush=True)

# LLM with low thinking for page analysis
llm = ChatGoogleGenerativeAI(
    model=gemini_model, 
    temperature=0, 
    google_api_key=google_api_key,
    thinking_level="low"
)

# LLM with high thinking for script generation
llm_high_thinking = ChatGoogleGenerativeAI(
    model=gemini_model, 
    temperature=0, 
    google_api_key=google_api_key,
    thinking_level="high"
)


# ============================================================================
# BROWSER ADAPTER HELPERS
# ============================================================================

# Global MCP adapter
mcp_browser: MCPBrowserAdapter = None


async def get_mcp_browser() -> MCPBrowserAdapter:
    """Get or initialize the MCP browser adapter."""
    global mcp_browser
    if mcp_browser is None:
        mcp_browser = get_mcp_adapter(use_codegen=True)
        try:
            print("⏳ Launching MCP browser...")
            if not await asyncio.wait_for(mcp_browser.launch(), timeout=30.0):
                raise Exception("Failed to connect to MCP server (launch returned False)")
        except asyncio.TimeoutError:
            raise Exception("Timeout (30s) while connecting to MCP server - please ensure the MCP server is running")
        except Exception as e:
            raise Exception(f"Failed to connect to MCP server: {str(e)}")
            
    return mcp_browser


async def reset_mcp_browser():
    """Reset the global MCP browser adapter and close browser."""
    global mcp_browser
    if mcp_browser:
        try:
            await mcp_browser.reset()
        except Exception as e:
            print(f"⚠️ Browser reset warning: {e}")
    mcp_browser = None
    reset_mcp_adapter()
