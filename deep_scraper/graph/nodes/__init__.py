"""
Graph nodes package — Modular node implementations for the Deep Scraper Agent.

Node sources:
  navigation  → node_navigate_mcp, node_analyze_mcp
  disclaimer  → node_click_link_mcp       (split from interaction.py)
  search      → node_perform_search_mcp   (split from interaction.py)
  extraction  → node_capture_columns_mcp
  script_gen  → node_generate_script_mcp
  script_test → node_test_script, node_fix_script, node_escalate
"""

from deep_scraper.graph.nodes.navigation import (
    node_navigate_mcp,
    node_analyze_mcp,
)
from deep_scraper.graph.nodes.disclaimer import node_click_link_mcp
from deep_scraper.graph.nodes.search import node_perform_search_mcp
from deep_scraper.graph.nodes.extraction import node_capture_columns_mcp
from deep_scraper.graph.nodes.script_gen import node_generate_script_mcp
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
