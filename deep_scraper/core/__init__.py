"""Core components: state, MCP browser adapter, and schemas."""

from deep_scraper.core.state import AgentState
from deep_scraper.core.mcp_adapter import MCPBrowserAdapter, get_mcp_adapter
from deep_scraper.core.mcp_client import PlaywrightMCPClient
from deep_scraper.core.schemas import NavigationDecision, SearchFormDetails, ExtractionResult

__all__ = [
    "AgentState", 
    "MCPBrowserAdapter", 
    "get_mcp_adapter",
    "PlaywrightMCPClient",
    "NavigationDecision", 
    "SearchFormDetails", 
    "ExtractionResult"
]
