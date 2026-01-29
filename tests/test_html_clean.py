import pytest
import sys
import os
from unittest.mock import AsyncMock, MagicMock, patch

# Add root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Set dummy env vars
os.environ["GOOGLE_API_KEY"] = "dummy_key"
os.environ["GEMINI_MODEL"] = "dummy_model"

# Mock modules that might be missing in the test environment
sys.modules['langgraph'] = MagicMock()
sys.modules['langgraph.graph'] = MagicMock()
sys.modules['langchain_core'] = MagicMock()
sys.modules['langchain_core.messages'] = MagicMock()
sys.modules['langchain_google_genai'] = MagicMock()
sys.modules['bs4'] = MagicMock()

from deep_scraper.core.mcp_adapter import MCPBrowserAdapter

@pytest.mark.asyncio
async def test_get_cleaned_html_logic():
    # Arrange
    adapter = MCPBrowserAdapter(use_codegen=False)

    # Mock the MCP client
    mock_mcp = AsyncMock()
    adapter.mcp = mock_mcp

    # Mock evaluate response
    expected_html = "<html><body><div>Cleaned Content</div></body></html>"
    # We mock evaluate directly on the adapter because get_cleaned_html calls self.evaluate
    adapter.evaluate = AsyncMock(return_value=expected_html)

    # Act
    result = await adapter.get_cleaned_html()

    # Assert
    assert result == expected_html

    # Verify the script passed to evaluate contains key logic
    call_args = adapter.evaluate.call_args
    assert call_args is not None
    script = call_args[0][0]

    # Verify critical parts of the JS script are present
    assert "function clean(node)" in script
    assert "isHidden(el)" in script
    assert "window.getComputedStyle(el)" in script
    assert "display === 'none'" in script
    assert "script" in script
    assert "style" in script
    assert "iframe" in script
    assert "cleanedBody.outerHTML" in script
