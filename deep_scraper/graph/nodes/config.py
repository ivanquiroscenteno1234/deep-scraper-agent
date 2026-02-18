"""
Shared configuration and re-exports for all graph nodes.

Each concern lives in its own module:
  LLM clients      → deep_scraper.core.llm
  Browser adapter  → deep_scraper.core.browser  (or mcp_adapter)
  Pydantic models  → deep_scraper.core.schemas
  Text utils       → deep_scraper.utils.text
  HTML utils       → deep_scraper.utils.html
  Logging          → deep_scraper.utils.logging
  Constants        → deep_scraper.utils.constants
  Script template  → deep_scraper.utils.script_template
"""

import asyncio

from deep_scraper.core.state import AgentState  # noqa: F401
from deep_scraper.core.llm import llm, llm_high_thinking  # noqa: F401
from deep_scraper.core.mcp_adapter import get_mcp_adapter, MCPBrowserAdapter, reset_mcp_adapter  # noqa: F401

from deep_scraper.core.schemas import (  # noqa: F401
    NavigationDecision,
    PopupAnalysis,
    PostClickAnalysis,
    PostPopupAnalysis,
    ColumnAnalysis,
)
from deep_scraper.utils.text import (  # noqa: F401
    extract_llm_text,
    extract_code_from_markdown,
    get_site_name_from_url,
)
from deep_scraper.utils.html import clean_html_for_llm  # noqa: F401
from deep_scraper.utils.logging import StructuredLogger  # noqa: F401
from deep_scraper.utils.constants import (  # noqa: F401
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
from deep_scraper.utils.script_template import build_script_prompt  # noqa: F401


# ---------------------------------------------------------------------------
# Browser adapter singleton (managed here for backward-compat)
# ---------------------------------------------------------------------------

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
            raise Exception(
                "Timeout (30s) while connecting to MCP server — please ensure the MCP server is running"
            )
        except Exception as e:
            raise Exception(f"Failed to connect to MCP server: {str(e)}")
    return mcp_browser


async def reset_mcp_browser() -> None:
    """Reset the global MCP browser adapter and close browser."""
    global mcp_browser
    if mcp_browser:
        try:
            await mcp_browser.reset()
        except Exception as e:
            print(f"⚠️ Browser reset warning: {e}")
    mcp_browser = None
    reset_mcp_adapter()

