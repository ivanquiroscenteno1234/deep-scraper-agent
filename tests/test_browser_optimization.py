import pytest
import sys
import os
from unittest.mock import AsyncMock, MagicMock

# Ensure we can import deep_scraper
sys.path.append(os.getcwd())

from deep_scraper.core.mcp_client import PlaywrightMCPClient

@pytest.mark.asyncio
async def test_get_full_page_content_clean():
    """Test that clean=True generates a cleaning script."""
    client = PlaywrightMCPClient()
    client.call_tool = AsyncMock(return_value={"result": '{"html": "<html></html>", "text": "text"}'})

    # Check if the method accepts the argument (it won't initially, so we might need to update the file first
    # OR we are writing the test TDD style and expecting it to fail if run now)

    # Since I cannot run a test that crashes due to TypeError, I will assume I modify the code next.
    # But for TDD, I should write the test first. However, Python will raise TypeError at runtime if I call with unexpected arg.
    # I will proceed to write the test, but I won't run it until I modify the code,
    # OR I will inspect the failure to confirm it fails as expected.

    await client.get_full_page_content(clean=True)

    name = client.call_tool.call_args[0][0]
    params = client.call_tool.call_args[0][1]

    assert name == "playwright_evaluate"
    script = params["script"]

    # Check for key cleaning operations
    assert "cloneNode(true)" in script
    assert "script" in script
    assert "style" in script
    assert "svg" in script
    assert "remove()" in script

    # Check that it returns the expected structure
    assert "JSON.stringify" in script
    assert "html:" in script
    assert "text:" in script

@pytest.mark.asyncio
async def test_get_full_page_content_no_clean():
    """Test that clean=False uses the simple script."""
    client = PlaywrightMCPClient()
    client.call_tool = AsyncMock(return_value={"result": '{"html": "<html></html>", "text": "text"}'})

    # This might fail if I haven't updated the signature yet, but valid python allows calling without args
    await client.get_full_page_content(clean=False)

    name = client.call_tool.call_args[0][0]
    params = client.call_tool.call_args[0][1]

    assert name == "playwright_evaluate"
    script = params["script"]

    # Should NOT have the complex cleaning logic
    assert "cloneNode" not in script
    assert "remove()" not in script
    assert "JSON.stringify({html: document.documentElement.outerHTML" in script
