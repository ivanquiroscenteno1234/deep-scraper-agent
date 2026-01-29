
import pytest
import asyncio
import sys
from unittest.mock import AsyncMock, MagicMock, patch

# Only mock what we don't want to run or don't have creds for.
# We have installed langgraph/langchain_core so we can use them.
# But deep_scraper.graph.nodes.config initializes LLM with API keys.
# We must ensure we don't trigger that if possible.

# However, deep_scraper.__init__ imports graph.mcp_engine -> imports nodes.config
# deep_scraper.graph.nodes.config does:
# gemini_model = os.getenv("GEMINI_MODEL")
# if google_api_key: ...
# llm = ChatGoogleGenerativeAI(...)

# So we need to mock ChatGoogleGenerativeAI or set dummy env vars.

import os
os.environ["GOOGLE_API_KEY"] = "dummy"
os.environ["GEMINI_MODEL"] = "dummy"

from deep_scraper.core.mcp_adapter import MCPBrowserAdapter

@pytest.mark.asyncio
async def test_get_cleaned_html_logic():
    # Setup
    adapter = MCPBrowserAdapter()
    adapter.mcp = AsyncMock()
    # Mock evaluate to return a specific string
    adapter.evaluate = AsyncMock(return_value="<html>cleaned</html>")

    # Act
    # We expect this method to be added
    if not hasattr(adapter, "get_cleaned_html"):
        pytest.fail("MCPBrowserAdapter.get_cleaned_html method not implemented yet")

    result = await adapter.get_cleaned_html(max_length=500)

    # Assert
    assert result == "<html>cleaned</html>"

    # Verify the script passed to evaluate
    call_args = adapter.evaluate.call_args
    assert call_args is not None
    script = call_args[0][0]

    # Check for key JS components
    assert "document.documentElement.cloneNode(true)" in script
    assert "script" in script
    assert "style" in script
    assert "svg" in script
    assert "TreeWalker" in script # For comments
    assert "outerHTML" in script
    assert "substring(0, 500)" in script or "slice(0, 500)" in script # Truncation logic

@pytest.mark.asyncio
async def test_node_analyze_mcp_uses_get_cleaned_html():
    # Mock node_analyze_mcp and its dependencies
    # This is trickier because of the imports in navigation.py

    # We'll mock the whole module deep_scraper.graph.nodes.config
    with patch("deep_scraper.graph.nodes.navigation.get_mcp_browser") as mock_get_browser, \
         patch("deep_scraper.graph.nodes.navigation.clean_html_for_llm") as mock_clean, \
         patch("deep_scraper.graph.nodes.navigation.llm") as mock_llm:

        from deep_scraper.graph.nodes.navigation import node_analyze_mcp

        # Setup mock browser
        mock_browser = AsyncMock()
        mock_get_browser.return_value = mock_browser
        mock_browser.get_cleaned_html.return_value = "<html>cleaned input</html>"

        # Setup state
        state = {"target_url": "http://example.com", "logs": []}

        # Setup LLM response
        mock_decision = MagicMock()
        mock_decision.is_search_page = False
        mock_decision.is_results_grid = False
        mock_decision.requires_login = False
        mock_decision.is_disclaimer = True

        # Mock the structured output chain
        mock_chain = AsyncMock()
        mock_chain.ainvoke.return_value = mock_decision
        mock_llm.with_structured_output.return_value = mock_chain

        # Act
        await node_analyze_mcp(state)

        # Assert
        # Verify get_cleaned_html was called
        mock_browser.get_cleaned_html.assert_called_once()

        # Verify clean_html_for_llm was NOT called (or at least we rely on browser)
        # Actually, we replaced it. So it should not be called.
        mock_clean.assert_not_called()
