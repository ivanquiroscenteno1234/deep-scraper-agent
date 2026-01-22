import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from deep_scraper.core.mcp_client import PlaywrightMCPClient

@pytest.mark.asyncio
async def test_script_generation():
    """
    Test the JS generation logic specifically.
    Verifies that get_full_page_content(clean=True) generates the correct
    JavaScript to clean the DOM on the browser side.
    """
    client = PlaywrightMCPClient()
    client.call_tool = AsyncMock(return_value={"result": "{}"})

    # Call with clean=True
    await client.get_full_page_content(clean=True)

    # Verify the script sent to call_tool
    call_args = client.call_tool.call_args
    assert call_args is not None
    tool_name, params = call_args[0], call_args[1]

    assert tool_name[0] == "playwright_evaluate"
    script = params.get("script") or tool_name[1].get("script")

    # Verify script content
    assert "cloneNode(true)" in script
    assert "script" in script
    assert "style" in script
    assert "svg" in script
    assert "JSON.stringify" in script
