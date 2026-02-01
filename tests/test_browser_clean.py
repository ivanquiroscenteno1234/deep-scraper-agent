
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from deep_scraper.core.mcp_adapter import MCPBrowserAdapter

@pytest.mark.asyncio
async def test_get_cleaned_html_sends_correct_script():
    # Setup
    adapter = MCPBrowserAdapter(use_codegen=False)
    mock_mcp = AsyncMock()
    adapter.mcp = mock_mcp

    # Mock evaluate response
    # When mcp.call_tool("playwright_evaluate", ...) is called
    mock_mcp.call_tool.return_value = {"result": "<html>CLEANED</html>"}

    # Execute
    result = await adapter.get_cleaned_html(max_length=1000)

    # Verify result
    assert result == "<html>CLEANED</html>"

    # Verify call arguments
    assert mock_mcp.call_tool.called
    call_args = mock_mcp.call_tool.call_args
    tool_name = call_args[0][0]
    params = call_args[0][1]

    assert tool_name == "playwright_evaluate"
    script = params["script"]

    # Verify script content
    assert "document.documentElement.cloneNode(true)" in script
    assert "tagsToRemove" in script
    assert "'script'" in script
    assert "'style'" in script
    assert "NodeFilter.SHOW_COMMENT" in script
    assert "display: none" in script
    assert "visibility: hidden" in script
    assert "hidden" in script
    assert "clone.outerHTML" in script

@pytest.mark.asyncio
async def test_get_cleaned_html_handles_truncation():
    # Setup
    adapter = MCPBrowserAdapter(use_codegen=False)
    mock_mcp = AsyncMock()
    adapter.mcp = mock_mcp

    long_html = "a" * 200
    mock_mcp.call_tool.return_value = {"result": long_html}

    # Execute with max_length=100
    result = await adapter.get_cleaned_html(max_length=100)

    # Verify truncation
    assert len(result) > 100 # Because of suffix
    assert result.startswith("a" * 100)
    assert result.endswith("... [TRUNCATED]")

@pytest.mark.asyncio
async def test_get_cleaned_html_handles_error():
    # Setup
    adapter = MCPBrowserAdapter(use_codegen=False)
    mock_mcp = AsyncMock()
    adapter.mcp = mock_mcp

    mock_mcp.call_tool.side_effect = Exception("MCP Error")

    # Execute
    result = await adapter.get_cleaned_html()

    # Verify safe handling
    assert result == ""
