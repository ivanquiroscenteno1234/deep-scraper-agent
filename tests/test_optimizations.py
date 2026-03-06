import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
import sys

# Mocking EVERYTHING that might be imported
sys.modules['langgraph'] = MagicMock()
sys.modules['langgraph.graph'] = MagicMock()
sys.modules['langgraph.prebuilt'] = MagicMock()
sys.modules['bs4'] = MagicMock()
sys.modules['langchain'] = MagicMock()
sys.modules['langchain_core'] = MagicMock()
sys.modules['langchain_core.messages'] = MagicMock()
sys.modules['langchain_google_genai'] = MagicMock()
sys.modules['mcp'] = MagicMock()
sys.modules['mcp.client'] = MagicMock()
sys.modules['mcp.client.stdio'] = MagicMock()
sys.modules['dotenv'] = MagicMock()

# Mock deep_scraper.core.state
mock_state = MagicMock()
sys.modules['deep_scraper.core.state'] = mock_state

# Mock deep_scraper.core.mcp_adapter
mock_adapter = MagicMock()
sys.modules['deep_scraper.core.mcp_adapter'] = mock_adapter

# Mock deep_scraper.graph.nodes.config
mock_config = MagicMock()
mock_config.llm = MagicMock()
mock_config.get_mcp_browser = AsyncMock()
mock_config.clean_html_for_llm = lambda x, **kwargs: x # Passthrough for testing
sys.modules['deep_scraper.graph.nodes.config'] = mock_config

# Now import the functions to test
from deep_scraper.graph.nodes.navigation import node_analyze_mcp
from deep_scraper.graph.nodes.interaction import node_click_link_mcp, _detect_landmark_search_selectors

async def test_detect_landmark_search_selectors():
    print("Testing _detect_landmark_search_selectors...")
    html = "<html><div id=\"name-name\"></div><div id=\"namesearchmodalsubmit\"></div></html>"
    result = _detect_landmark_search_selectors(html.lower())
    assert result is not None
    assert result['input'] == "#name-Name"
    assert result['submit'] == "#nameSearchModalSubmit"
    print("test_detect_landmark_search_selectors passed!")

async def test_node_analyze_mcp_heuristic():
    print("Testing node_analyze_mcp_heuristic...")
    state = {"target_url": "http://test.com", "logs": []}
    mock_browser = AsyncMock()
    # Need both SearchOnName AND a submit button for heuristic to verify!
    mock_browser.get_snapshot.return_value = {"html": "<html><input id=\"SearchOnName\"><button id=\"btnSearch\">Search</button></html>"}

    with patch('deep_scraper.graph.nodes.navigation.get_mcp_browser', return_value=mock_browser),          patch('deep_scraper.graph.nodes.navigation.llm') as mock_llm:

        mock_decision = MagicMock()
        mock_decision.is_search_page = False
        mock_decision.is_results_grid = False
        mock_decision.requires_login = False
        mock_decision.is_disclaimer = True
        mock_decision.accept_button_ref = "button"
        mock_decision.reasoning = "test"
        mock_decision.search_input_ref = ""
        mock_decision.search_button_ref = ""
        mock_decision.start_date_input_ref = ""
        mock_decision.end_date_input_ref = ""

        mock_llm.with_structured_output.return_value.ainvoke = AsyncMock(return_value=mock_decision)

        result = await node_analyze_mcp(state)
        print(f"Result status: {result['status']}")
        assert result['status'] == "SEARCH_PAGE_FOUND"
    print("test_node_analyze_mcp_heuristic passed!")

if __name__ == "__main__":
    asyncio.run(test_detect_landmark_search_selectors())
    asyncio.run(test_node_analyze_mcp_heuristic())
    print("All tests passed!")
