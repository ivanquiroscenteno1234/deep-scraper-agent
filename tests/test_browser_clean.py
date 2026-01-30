
import pytest
import sys
from unittest.mock import AsyncMock, MagicMock

# Mock dependencies that might not be present or configured
# We need to mock submodules too because 'from langgraph.graph import ...' requires it
mock_langgraph = MagicMock()
sys.modules['langgraph'] = mock_langgraph
sys.modules['langgraph.graph'] = MagicMock()
sys.modules['langgraph.prebuilt'] = MagicMock()

mock_langchain_core = MagicMock()
sys.modules['langchain_core'] = mock_langchain_core
sys.modules['langchain_core.messages'] = MagicMock()

sys.modules['langchain_google_genai'] = MagicMock()
sys.modules['bs4'] = MagicMock()

# Now we can safely import the adapter
from deep_scraper.core.mcp_adapter import MCPBrowserAdapter

@pytest.mark.asyncio
async def test_get_cleaned_html_payload():
    """
    Verify that get_cleaned_html sends the correct JS payload to the browser.
    """
    adapter = MCPBrowserAdapter(use_codegen=False)

    # Mock the internal MCP client
    mock_mcp = AsyncMock()
    adapter.mcp = mock_mcp

    # Mock evaluate response - simulated cleaner output
    mock_mcp.call_tool.return_value = {"result": "<html><body>Cleaned</body></html>"}

    # Call the method
    result = await adapter.get_cleaned_html()

    assert result == "<html><body>Cleaned</body></html>"

    # Verify the call arguments
    assert mock_mcp.call_tool.called
    args, kwargs = mock_mcp.call_tool.call_args
    tool_name = args[0]
    params = args[1]

    assert tool_name == "playwright_evaluate"
    script = params["script"]

    # Verify script content logic
    assert "document.documentElement.cloneNode" in script
    assert "remove('script')" in script
    assert "remove('style')" in script
    assert "remove('svg')" in script
    assert "remove('[hidden]')" in script
    assert "clone.outerHTML" in script

@pytest.mark.asyncio
async def test_get_cleaned_html_truncation():
    """Verify that result is truncated if too long."""
    adapter = MCPBrowserAdapter(use_codegen=False)
    mock_mcp = AsyncMock()
    adapter.mcp = mock_mcp

    # Return huge string
    huge_html = "a" * 50000
    mock_mcp.call_tool.return_value = {"result": huge_html}

    result = await adapter.get_cleaned_html(max_length=1000)

    # Check length (original + truncation marker)
    expected_max = 1000 + len("\n... [TRUNCATED]")
    assert len(result) <= expected_max
    assert result.endswith("[TRUNCATED]")
