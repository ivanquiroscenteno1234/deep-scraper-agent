"""
Graph nodes package - Modular node implementations for the Deep Scraper Agent.

This package provides the node functions used by the LangGraph workflow:
- navigation: Navigate to URLs and analyze pages
- interaction: Click buttons and perform searches
- extraction: Capture grid columns and data
- script_gen: Generate Playwright scripts via LLM
- script_test: Test and fix generated scripts
"""

# Re-export all node functions for backward compatibility
from deep_scraper.graph.nodes.navigation import (
    node_navigate_mcp,
    node_analyze_mcp,
)
from deep_scraper.graph.nodes.interaction import (
    node_click_link_mcp,
    node_perform_search_mcp,
)
from deep_scraper.graph.nodes.extraction import (
    node_capture_columns_mcp,
)
from deep_scraper.graph.nodes.script_gen import (
    node_generate_script_mcp,
)
from deep_scraper.graph.nodes.script_test import (
    node_test_script,
    node_fix_script,
    node_escalate,
)

__all__ = [
    "node_navigate_mcp",
    "node_analyze_mcp",
    "node_click_link_mcp",
    "node_perform_search_mcp",
    "node_capture_columns_mcp",
    "node_generate_script_mcp",
    "node_test_script",
    "node_fix_script",
    "node_escalate",
]
