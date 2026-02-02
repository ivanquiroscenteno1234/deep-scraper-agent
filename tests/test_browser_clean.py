import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import sys

# Mock mcp module if it doesn't exist to allow imports
try:
    import mcp
except ImportError:
    mcp = MagicMock()
    sys.modules["mcp"] = mcp
    sys.modules["mcp.client"] = MagicMock()
    sys.modules["mcp.client.sse"] = MagicMock()

from deep_scraper.core.mcp_adapter import MCPBrowserAdapter
from deep_scraper.graph.nodes.navigation import node_analyze_mcp

@pytest.mark.asyncio
async def test_get_cleaned_html_script_generation():
    """Test that get_cleaned_html generates correct JS and handles result."""
    adapter = MCPBrowserAdapter(use_codegen=False)
    adapter.mcp = AsyncMock()

    # Mock evaluate to return a specific string
    mock_html_result = "<html><body><div>Visible</div></body></html>"
    adapter.evaluate = AsyncMock(return_value=mock_html_result)

    result = await adapter.get_cleaned_html(max_length=100)

    # Check result
    assert result == mock_html_result

    # Check the script passed to evaluate
    call_args = adapter.evaluate.call_args
    script_arg = call_args[0][0]

    assert "document.documentElement.cloneNode(true)" in script_arg
    assert "toRemove.length" in script_arg
    assert "display: none" in script_arg
    assert "return html.replace" in script_arg

@pytest.mark.asyncio
async def test_get_cleaned_html_truncation():
    """Test that get_cleaned_html truncates long output."""
    adapter = MCPBrowserAdapter(use_codegen=False)
    adapter.mcp = AsyncMock()

    long_html = "a" * 200
    adapter.evaluate = AsyncMock(return_value=long_html)

    result = await adapter.get_cleaned_html(max_length=50)

    # Original string is 200 chars.
    # Logic: return clean_html[:max_length] + "\\n... [TRUNCATED]"
    # So length should be 50 + len("\n... [TRUNCATED]")

    assert len(result) < 200
    assert "... [TRUNCATED]" in result
    assert len(result) == 50 + len("\n... [TRUNCATED]")

@pytest.mark.asyncio
async def test_node_analyze_mcp_uses_cleaned_html():
    """Test that node_analyze_mcp calls get_cleaned_html."""

    # Mock state
    state = {
        "disclaimer_click_attempts": 0,
        "clicked_selectors": [],
        "logs": []
    }

    # Mock browser
    mock_browser = AsyncMock()
    # Return HTML that has inputs so heuristic is happy
    mock_browser.get_cleaned_html.return_value = '<html><input id="name-Name" type="text"></html>'

    # Mock dependencies
    # We patch the imports in navigation.py
    with patch("deep_scraper.graph.nodes.navigation.get_mcp_browser", new=AsyncMock(return_value=mock_browser)), \
         patch("deep_scraper.graph.nodes.navigation.llm") as mock_llm:

        # Mock LLM response
        mock_llm_response = MagicMock()
        mock_llm_response.is_search_page = True
        mock_llm_response.is_results_grid = False
        mock_llm_response.is_disclaimer = False
        mock_llm_response.requires_login = False
        mock_llm_response.reasoning = "Test"
        mock_llm_response.search_input_ref = "#name-Name"
        mock_llm_response.search_button_ref = "#btn"

        # Setup ainvoke chain
        mock_llm.with_structured_output.return_value.ainvoke.return_value = mock_llm_response

        result = await node_analyze_mcp(state)

        # Verify get_cleaned_html was called
        mock_browser.get_cleaned_html.assert_called_once_with(max_length=100000)

        # Verify snapshot was NOT called (we replaced it)
        # Note: 'get_snapshot' might not exist on the mock unless we speicfied it,
        # but if the code called it, it would be recorded.
        # However, AsyncMock auto-creates children.
        # But since we replaced the call in the code, it should NOT be called.
        # To be sure, we check if it was called.
        if hasattr(mock_browser, "get_snapshot"):
             mock_browser.get_snapshot.assert_not_called()
