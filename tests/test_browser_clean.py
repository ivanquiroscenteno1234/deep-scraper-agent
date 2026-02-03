import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import sys
import os

# Ensure deep_scraper is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from deep_scraper.core.mcp_adapter import MCPBrowserAdapter

@pytest.mark.asyncio
async def test_get_cleaned_html_calls_evaluate():
    # Setup
    adapter = MCPBrowserAdapter()
    adapter.mcp = AsyncMock()
    adapter.evaluate = AsyncMock(return_value="<html>cleaned</html>")

    # Execute
    result = await adapter.get_cleaned_html(max_length=5000)

    # Verify
    assert result == "<html>cleaned</html>"
    adapter.evaluate.assert_called_once()

    # Check script content
    args, _ = adapter.evaluate.call_args
    script = args[0]

    assert "const maxLength = 5000;" in script
    assert "clone.querySelectorAll('script, style, link, svg, noscript, iframe, meta');" in script
    assert "clone.outerHTML;" in script
    assert "html.substring(0, maxLength)" in script

@pytest.mark.asyncio
async def test_get_cleaned_html_handles_error():
    # Setup
    adapter = MCPBrowserAdapter()
    adapter.mcp = AsyncMock()
    adapter.evaluate = AsyncMock(side_effect=Exception("MCP Error"))

    # Execute
    result = await adapter.get_cleaned_html()

    # Verify
    assert result == ""
