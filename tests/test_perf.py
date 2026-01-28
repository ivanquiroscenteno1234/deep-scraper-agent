import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from deep_scraper.core.state import AgentState
from deep_scraper.graph.nodes.navigation import node_analyze_mcp, _SEARCH_INDICATORS

# Mock the LLM to avoid API calls
@pytest.fixture
def mock_llm():
    with patch('deep_scraper.graph.nodes.navigation.llm') as mock:
        mock_structured = AsyncMock()
        mock.with_structured_output.return_value = mock_structured

        # Default decision (not search page) so we can test heuristic override
        mock_decision = MagicMock()
        mock_decision.is_search_page = False
        mock_decision.is_results_grid = False
        mock_decision.requires_login = False
        mock_decision.is_disclaimer = False
        mock_decision.search_input_ref = ""
        mock_decision.search_button_ref = ""
        mock_decision.start_date_input_ref = ""
        mock_decision.end_date_input_ref = ""
        mock_decision.accept_button_ref = ""
        mock_decision.grid_selector = ""
        mock_decision.reasoning = "Mock reasoning"

        mock_structured.ainvoke.return_value = mock_decision

        yield mock

@pytest.mark.asyncio
async def test_analyze_mcp_search_detection(mock_llm):
    """Verify node_analyze_mcp uses optimized search detection and get_html_snapshot."""

    # Mock browser adapter
    mock_browser = AsyncMock()
    mock_browser._codegen_started = False

    # Return HTML that triggers heuristic search detection
    # We include both the input indicator (#SearchOnName) and the submit button (#btnSearch)
    html_content = """
    <html>
        <body>
            <div id="content">
                <form>
                    <label>Name Search</label>
                    <input id="SearchOnName" type="text" />
                    <input id="btnSearch" type="submit" value="Search" />
                </form>
            </div>
        </body>
    </html>
    """

    # Mock get_html_snapshot instead of get_snapshot
    mock_browser.get_html_snapshot.return_value = {"html": html_content, "result": html_content, "text": ""}

    # Also mock get_snapshot to fail if called (ensuring we use the optimized method)
    mock_browser.get_snapshot.side_effect = Exception("Should NOT call get_snapshot! Use get_html_snapshot!")

    # Mock get_mcp_browser
    with patch('deep_scraper.graph.nodes.navigation.get_mcp_browser', new=AsyncMock(return_value=mock_browser)):
        state = AgentState(
            target_url="http://example.com",
            recorded_steps=[],
            logs=[],
            search_query="Test"
        )

        result = await node_analyze_mcp(state)

        # Verify get_html_snapshot was called
        mock_browser.get_html_snapshot.assert_called_once()

        # Verify heuristic detection worked (overriding the LLM which said False)
        # The logic in node_analyze_mcp should detect #SearchOnName and #btnSearch
        assert result["status"] == "SEARCH_PAGE_FOUND"
        assert result["search_selectors"]["input"] == "#SearchOnName"
        assert result["search_selectors"]["submit"] == "#btnSearch"

@pytest.mark.asyncio
async def test_search_indicators_optimization():
    """Verify module-level constants are correct."""
    from deep_scraper.graph.nodes.navigation import _SEARCH_INDICATORS, _SEARCH_INDICATORS_LOWER

    assert len(_SEARCH_INDICATORS) > 0
    assert len(_SEARCH_INDICATORS) == len(_SEARCH_INDICATORS_LOWER)
    assert "#SearchOnName" in _SEARCH_INDICATORS
    assert "#searchonname" in _SEARCH_INDICATORS_LOWER
