import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
import sys
import os

# Add root directory to path so we can import deep_scraper
sys.path.append(os.getcwd())

from deep_scraper.core.mcp_client import PlaywrightMCPClient
from deep_scraper.core.mcp_adapter import MCPBrowserAdapter

@pytest.mark.asyncio
async def test_get_full_page_content_clean():
    # Setup
    client = PlaywrightMCPClient()
    client._session = AsyncMock()

    # Mock call_tool
    mock_call_tool = AsyncMock(return_value={"result": "mock_result"})
    client.call_tool = mock_call_tool

    # Act
    # We expect this to fail initially if the signature hasn't changed
    try:
        await client.get_full_page_content(clean=True)
    except TypeError:
        # This is expected before implementation
        pytest.fail("get_full_page_content does not accept 'clean' argument yet")

    # Assert
    args, kwargs = mock_call_tool.call_args
    assert args[0] == "playwright_evaluate"

    # params can be positional or keyword
    params = kwargs.get("params")
    if not params and len(args) > 1:
        params = args[1]

    script = params["script"]

    # Check if script contains cleaning logic
    assert "cloneNode" in script, "Script should use cloneNode for cleaning"
    assert ".remove()" in script, "Script should remove elements"
    assert "JSON.stringify" in script

@pytest.mark.asyncio
async def test_get_full_page_content_default():
    # Setup
    client = PlaywrightMCPClient()
    client._session = AsyncMock()

    # Mock call_tool
    mock_call_tool = AsyncMock(return_value={"result": "mock_result"})
    client.call_tool = mock_call_tool

    # Act
    try:
        await client.get_full_page_content(clean=False)
    except TypeError:
        # Fallback for pre-implementation check
        await client.get_full_page_content()
        # If we are here, we called it without clean param, which is old behavior.
        # But we want to verify the script.

    # Assert
    args, kwargs = mock_call_tool.call_args
    assert args[0] == "playwright_evaluate"

    # params can be positional or keyword
    params = kwargs.get("params")
    if not params and len(args) > 1:
        params = args[1]

    script = params["script"]

    # Check if script is simple
    assert "cloneNode" not in script, "Default script should not clone node"
    assert "JSON.stringify" in script

@pytest.mark.asyncio
async def test_adapter_uses_clean_snapshot():
    # Setup
    adapter = MCPBrowserAdapter(use_codegen=False)
    adapter.mcp = AsyncMock()
    adapter.mcp.get_full_page_content = AsyncMock(return_value={"result": "{}"})

    # Act
    await adapter.get_snapshot()

    # Assert
    adapter.mcp.get_full_page_content.assert_called_once()
    call_args = adapter.mcp.get_full_page_content.call_args

    # Check if clean=True was passed
    kwargs_clean = call_args.kwargs.get('clean')
    args_clean = call_args.args[0] if call_args.args else None

    assert kwargs_clean is True or args_clean is True, \
           "Adapter should call get_full_page_content with clean=True"
