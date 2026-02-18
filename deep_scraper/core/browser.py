"""
browser.py — Re-export of MCPBrowserAdapter under a cleaner name.

Renamed from deep_scraper/core/mcp_adapter.py for clarity.
All other code can import from here or directly from mcp_adapter.
"""

from deep_scraper.core.mcp_adapter import (  # noqa: F401
    MCPBrowserAdapter,
    get_mcp_adapter,
    reset_mcp_adapter,
)
