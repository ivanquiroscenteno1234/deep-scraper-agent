import pytest
from unittest.mock import patch, MagicMock, AsyncMock

# Mock out mcp package dependencies for deep_scraper imports to work
import sys
sys.modules['mcp'] = MagicMock()
sys.modules['mcp.client'] = MagicMock()
sys.modules['mcp.client.stdio'] = MagicMock()
sys.modules['mcp.client.sse'] = MagicMock()
sys.modules['pydantic'] = MagicMock()
sys.modules['langchain_core'] = MagicMock()
sys.modules['langchain_core.messages'] = MagicMock()
sys.modules['langchain_google_genai'] = MagicMock()
sys.modules['langgraph'] = MagicMock()
sys.modules['langgraph.graph'] = MagicMock()
sys.modules['bs4'] = MagicMock()
sys.modules['dotenv'] = MagicMock()

from deep_scraper.core.mcp_adapter import MCPBrowserAdapter
from deep_scraper.core.mcp_client import PlaywrightMCPClient

@pytest.mark.asyncio
async def test_get_cleaned_html():
    adapter = MCPBrowserAdapter(use_codegen=False)
    adapter.mcp = MagicMock(spec=PlaywrightMCPClient)

    # Mock evaluate to return a cleaned HTML string
    expected_html = "<html><body><div>Cleaned</div></body></html>"
    adapter.evaluate = AsyncMock(return_value=expected_html)

    result = await adapter.get_cleaned_html(max_length=100)

    # Verify evaluate was called
    adapter.evaluate.assert_called_once()

    # Verify the JS payload structure
    script_arg = adapter.evaluate.call_args[0][0]
    assert "document.documentElement.cloneNode(true)" in script_arg
    assert "selectorsToRemove.forEach" in script_arg
    assert "<!--" in script_arg

    # Verify the result is exactly what we expect
    assert result == expected_html

@pytest.mark.asyncio
async def test_get_cleaned_html_truncation():
    adapter = MCPBrowserAdapter(use_codegen=False)
    adapter.mcp = MagicMock(spec=PlaywrightMCPClient)

    expected_html = "<html><body><div>" + "A" * 150 + "</div></body></html>"
    adapter.evaluate = AsyncMock(return_value=expected_html)

    # Note: get_cleaned_html truncation logic is executed IN BROWSER,
    # so we're just testing that the Python wrapper correctly formats the max_length parameter
    # and returns what the mock evaluate provides.
    result = await adapter.get_cleaned_html(max_length=100)

    script_arg = adapter.evaluate.call_args[0][0]
    assert "if (html.length > 100)" in script_arg
    assert "return html.substring(0, 100) + '\\n... [TRUNCATED]';" in script_arg

    assert result == expected_html
