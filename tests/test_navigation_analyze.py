import pytest
from deep_scraper.graph.nodes.navigation import node_analyze_mcp, _SEARCH_INDICATORS, _SEARCH_INDICATORS_LOWER
import asyncio

def test_search_indicators_are_lower():
    assert len(_SEARCH_INDICATORS) == len(_SEARCH_INDICATORS_LOWER)
    for ind, lower_ind in zip(_SEARCH_INDICATORS, _SEARCH_INDICATORS_LOWER):
        assert ind.lower() == lower_ind
