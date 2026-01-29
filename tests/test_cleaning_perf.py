
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import sys
import os

# Ensure we can import from deep_scraper
sys.path.append(os.getcwd())

# Mock dependencies that might be missing or require env vars
mock_langgraph = MagicMock()
mock_langgraph.graph = MagicMock()
mock_langgraph.prebuilt = MagicMock()

mock_langchain_core = MagicMock()
mock_langchain_core.messages = MagicMock()
mock_langchain_core.runnables = MagicMock()

with patch.dict(sys.modules, {
    "langgraph": mock_langgraph,
    "langgraph.graph": mock_langgraph.graph,
    "langgraph.prebuilt": mock_langgraph.prebuilt,
    "langchain_core": mock_langchain_core,
    "langchain_core.messages": mock_langchain_core.messages,
    "langchain_core.runnables": mock_langchain_core.runnables,
    "langchain_google_genai": MagicMock(),
    "mcp": MagicMock(),
    "deep_scraper.core.mcp_client": MagicMock(),
}):
    # Set dummy env vars to satisfy config.py import
    os.environ["GOOGLE_API_KEY"] = "dummy"
    os.environ["GEMINI_MODEL"] = "dummy"

    from deep_scraper.core.mcp_adapter import MCPBrowserAdapter
    # Import the module itself so we can patch globals
    import deep_scraper.graph.nodes.navigation as navigation_node
    from deep_scraper.graph.nodes.navigation import node_analyze_mcp

@pytest.mark.asyncio
async def test_get_cleaned_html_payload():
    """Verify that get_cleaned_html constructs the correct JS payload."""
    adapter = MCPBrowserAdapter()
    adapter.mcp = AsyncMock()
    adapter.mcp.call_tool = AsyncMock(return_value={"result": "<html>cleaned</html>"})

    # Run the method
    result = await adapter.get_cleaned_html(max_length=100)

    # Check result
    assert result == "<html>cleaned</html>"

    # Verify the JS script was passed
    call_args = adapter.mcp.call_tool.call_args
    assert call_args is not None
    tool_name, params = call_args[0], call_args[1]

    assert tool_name[0] == "playwright_evaluate" or tool_name == ("playwright_evaluate",)

    # Check that script contains key cleaning steps
    script = params.get("script") or call_args[0][1]["script"]
    assert "cloneNode(true)" in script
    assert "script" in script
    assert "style" in script
    assert "display:\\s*none" in script  # Escaped backslash in python string

@pytest.mark.asyncio
async def test_node_analyze_mcp_uses_cleaned_html():
    """Verify that node_analyze_mcp uses the optimized method."""

    # Mock state
    state = {"target_url": "http://example.com"}

    # Mock browser
    mock_browser = AsyncMock()
    mock_browser.get_cleaned_html.return_value = "<html><input id='name-Name'></html>"
    # Ensure get_snapshot is not present or mocked to fail if called
    mock_browser.get_snapshot = MagicMock(side_effect=Exception("Should not call get_snapshot"))

    # Manual patch of the function in the module
    original_get_browser = navigation_node.get_mcp_browser
    navigation_node.get_mcp_browser = AsyncMock(return_value=mock_browser)

    # Manual patch of llm
    original_llm = navigation_node.llm
    mock_llm = MagicMock()
    mock_structured_llm = MagicMock()
    mock_structured_llm.ainvoke = AsyncMock(return_value=MagicMock(
        is_search_page=True,
        is_results_grid=False,
        is_disclaimer=False,
        requires_login=False,
        search_input_ref="#name-Name",
        search_button_ref="#btn",
        start_date_input_ref="",
        end_date_input_ref="",
        grid_selector="",
        reasoning="Found input"
    ))
    mock_llm.with_structured_output.return_value = mock_structured_llm
    navigation_node.llm = mock_llm

    try:
        # Run the node
        result = await node_analyze_mcp(state)

        # Verify get_cleaned_html was called instead of get_snapshot
        mock_browser.get_cleaned_html.assert_called_once()

        # Verify result status
        assert result["status"] == "SEARCH_PAGE_FOUND"
    finally:
        # Restore
        navigation_node.get_mcp_browser = original_get_browser
        navigation_node.llm = original_llm
