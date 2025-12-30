"""
Deep Scraper Agent - Autonomous web scraping powered by LangGraph + Gemini + MCP

Core workflow: Navigate URL → Grid → Generate working Playwright script
See .agent/workflows/project-specification.md for details
"""

from deep_scraper.core.state import AgentState
from deep_scraper.core.mcp_adapter import MCPBrowserAdapter, get_mcp_adapter
from deep_scraper.graph.mcp_engine import mcp_app as graph_app


__version__ = "2.0.0"
__all__ = ["AgentState", "MCPBrowserAdapter", "get_mcp_adapter", "graph_app"]
