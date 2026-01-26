import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import sys
import os

from deep_scraper.core.state import AgentState
from deep_scraper.graph.nodes.config import NavigationDecision

# Import the function to test
from deep_scraper.graph.nodes.navigation import node_analyze_mcp

@pytest.mark.asyncio
async def test_node_analyze_mcp_heuristic_detection():
    # Setup state
    state = AgentState(
        target_url="http://example.com",
        search_query="test",
        logs=[],
        attempt_count=0
    )

    # Mock Browser
    mock_browser = AsyncMock()
    # Content with search indicators
    # We use valid indicators from the list: "SearchOnName"
    html_content = """
    <html>
        <body>
            <div id="SearchOnName">
                <input type="text" id="SearchOnName" />
            </div>
            <button id="btnSearch">Search</button>
        </body>
    </html>
    """
    mock_browser.get_snapshot.return_value = {
        "html": html_content,
        "text": "Search Page"
    }

    # Mock LLM
    # We simulate LLM failing to detect it, so the heuristic logic kicks in
    mock_llm_response = NavigationDecision(
        is_search_page=False,
        is_results_grid=False,
        is_disclaimer=False,
        requires_login=False,
        reasoning="LLM missed it"
    )

    mock_llm_chain = AsyncMock()
    mock_llm_chain.ainvoke.return_value = mock_llm_response

    mock_llm = MagicMock()
    mock_llm.with_structured_output.return_value = mock_llm_chain

    # Patch dependencies
    # We need to match where they are imported in navigation.py
    with patch('deep_scraper.graph.nodes.navigation.get_mcp_browser', return_value=mock_browser), \
         patch('deep_scraper.graph.nodes.navigation.llm', mock_llm):

        result = await node_analyze_mcp(state)

        # logic:
        # has_search_inputs = True (because <input and SearchOnName)
        # if has_search_inputs and not decision.is_search_page ...
        #   verifies potential inputs...
        #   if found, override decision.is_search_page = True

        # Check logs to see if heuristic kicked in
        print("Result Logs:", result.get("logs", []))

        assert result["status"] == "SEARCH_PAGE_FOUND"
        assert result["search_selectors"]["input"] == "#SearchOnName"
