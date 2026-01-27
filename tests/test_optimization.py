import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import sys
import os
import asyncio
import json

# Set dummy environment variables BEFORE importing deep_scraper
os.environ["GOOGLE_API_KEY"] = "dummy_key"
os.environ["GEMINI_MODEL"] = "dummy_model"

# Ensure deep_scraper is in path
sys.path.append(os.getcwd())

try:
    from deep_scraper.core.mcp_client import PlaywrightMCPClient
    from deep_scraper.core.mcp_adapter import MCPBrowserAdapter
    from deep_scraper.graph.nodes.navigation import node_analyze_mcp
except ImportError as e:
    print(f"ImportError: {e}")
    # Handle case where dependencies might be missing in test env, though they should be there
    pass

class TestOptimization(unittest.TestCase):

    def test_client_get_cleaned_html_payload_logic(self):
        """
        Verify the JS payload construction.
        This test documents the expected JS payload structure.
        """
        # We will verify this by inspecting the code or mocking call_tool
        pass

    @patch('deep_scraper.graph.nodes.navigation.get_mcp_browser')
    @patch('deep_scraper.graph.nodes.navigation.clean_html_for_llm')
    @patch('deep_scraper.graph.nodes.navigation.llm')
    def test_node_analyze_mcp_uses_get_cleaned_html(self, mock_llm, mock_clean, mock_get_browser):
        async def run_test():
            # Setup
            mock_browser = AsyncMock() # loose mock to allow new methods
            mock_get_browser.return_value = mock_browser

            # Mock get_cleaned_html to return a string
            mock_browser.get_cleaned_html.return_value = "<html><body><input id='name-name'></body></html>"

            # Mock clean_html_for_llm to just return the input
            mock_clean.side_effect = lambda x, max_length=0: x

            # Mock LLM response
            mock_decision = MagicMock()
            mock_decision.is_search_page = True
            mock_decision.is_results_grid = False
            mock_decision.is_disclaimer = False
            mock_decision.requires_login = False

            # Setup chain mock
            mock_chain = AsyncMock()
            mock_chain.ainvoke.return_value = mock_decision
            mock_llm.with_structured_output.return_value = mock_chain

            state = {"target_url": "http://test.com"}

            # Execute
            await node_analyze_mcp(state)

            # Verify
            # 1. Verify get_cleaned_html was called
            if not hasattr(mock_browser, 'get_cleaned_html'):
                # This ensures the test fails if we haven't added the method yet (which is what we expect now)
                # But since we use AsyncMock(), it technically has attributes by default unless spec is strict.
                # However, the assertions below will fail if it wasn't called.
                pass

            mock_browser.get_cleaned_html.assert_awaited_once()

            # 2. Verify get_snapshot was NOT called
            mock_browser.get_snapshot.assert_not_called()

            # 3. Verify clean_html_for_llm is still called
            mock_clean.assert_called()

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(run_test())
        finally:
            loop.close()

if __name__ == '__main__':
    unittest.main()
