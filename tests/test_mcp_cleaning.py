import pytest
import sys
import os
from unittest.mock import AsyncMock, patch

# Ensure deep_scraper is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from deep_scraper.core.mcp_client import PlaywrightMCPClient
except ImportError:
    # If mcp is not installed, we can mock the import or skip the test
    # But for this environment, we assume dependencies are there or we mock them
    pass

@pytest.mark.asyncio
async def test_get_full_page_content_cleaning():
    """Verify that get_full_page_content generates correct JS script based on clean param."""

    # Mock mcp.ClientSession and others if import fails, but let's try to patch the class
    with patch('deep_scraper.core.mcp_client.PlaywrightMCPClient.call_tool', new_callable=AsyncMock) as mock_call_tool:
        # We instantiate without connecting, which is fine as we mock call_tool
        client = PlaywrightMCPClient()
        mock_call_tool.return_value = {"result": "{}"}

        # 1. Test clean=True
        await client.get_full_page_content(clean=True)

        assert mock_call_tool.called
        args, kwargs = mock_call_tool.call_args
        assert args[0] == "playwright_evaluate"
        script = kwargs.get('params', {}).get('script') or args[1]['script']

        # Verify cleaning logic is present
        assert "cloneNode(true)" in script
        assert "querySelectorAll('script, style, svg, noscript')" in script
        assert "createTreeWalker" in script
        assert "JSON.stringify" in script

        print("\n✅ Verified clean=True script generation")

        # 2. Test clean=False (default)
        await client.get_full_page_content(clean=False)

        args, kwargs = mock_call_tool.call_args
        script = kwargs.get('params', {}).get('script') or args[1]['script']

        # Verify it's the simple script
        assert script == "JSON.stringify({html: document.documentElement.outerHTML, text: document.body.innerText})"

        print("✅ Verified clean=False script generation")
