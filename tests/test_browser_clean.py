
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import sys
import os

# Add root directory to path to allow imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from deep_scraper.core.mcp_adapter import MCPBrowserAdapter
from deep_scraper.core.mcp_client import PlaywrightMCPClient

@pytest.mark.asyncio
async def test_get_cleaned_html_sends_correct_script():
    # Setup mocks
    mock_mcp_client = AsyncMock(spec=PlaywrightMCPClient)
    # The adapter expects call_tool to return a dict with "result" or just the result
    mock_mcp_client.call_tool.return_value = {"result": "<html>cleaned</html>"}

    # Patch get_mcp_client to return our mock
    # We patch where it is used or defined.
    with patch('deep_scraper.core.mcp_adapter.get_mcp_client', return_value=mock_mcp_client):
        adapter = MCPBrowserAdapter(use_codegen=False)
        adapter.mcp = mock_mcp_client

        # Execute
        result = await adapter.get_cleaned_html(max_length=500)

        # Verify
        assert result == "<html>cleaned</html>"

        # Verify the script sent to evaluate
        mock_mcp_client.call_tool.assert_called_once()
        args = mock_mcp_client.call_tool.call_args
        assert args[0][0] == "playwright_evaluate"
        script = args[0][1]["script"]

        # Check for key parts of the optimization in the script
        assert "document.documentElement.cloneNode(true)" in script
        assert ".remove()" in script
        assert "script" in script
        assert "style" in script
        assert "display: none" in script
