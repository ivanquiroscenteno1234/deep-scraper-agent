import os
import sys
import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

# Mock missing modules before any deep_scraper imports
for mod in ["mcp", "mcp.client", "mcp.client.stdio", "mcp.client.sse", "pydantic", "langchain_core", "langchain_core.messages", "langchain_core.language_models", "langchain_google_genai", "langgraph", "langgraph.graph", "langgraph.prebuilt", "bs4", "dotenv"]:
    sys.modules[mod] = MagicMock()

import pydantic
pydantic.BaseModel = MagicMock
pydantic.Field = MagicMock

# Mock environment variables for deep_scraper.graph.nodes.config
os.environ["GOOGLE_API_KEY"] = "dummy-key"
os.environ["GEMINI_MODEL"] = "gemini-pro"

# Mock the entire config module to avoid side effects
with patch("deep_scraper.graph.nodes.config.ChatGoogleGenerativeAI"), \
     patch("deep_scraper.graph.nodes.config.load_dotenv"):
    from deep_scraper.graph.nodes.script_test import node_fix_script
    from deep_scraper.graph.nodes.script_gen import node_generate_script_mcp

def test_node_fix_script_async_write(tmp_path):
    async def _run():
        script_path = tmp_path / "test_script.py"
        script_path.write_text("old code")

        state = {
            "generated_script_code": "old code",
            "generated_script_path": str(script_path),
            "script_error": "Some error",
            "recorded_steps": [],
            "script_test_attempts": 1,
            "logs": []
        }

        # Mock LLM response
        mock_result = MagicMock()
        mock_result.content = "```python\nfixed code\n```"

        with patch("deep_scraper.graph.nodes.script_test.llm_high_thinking.ainvoke", new_callable=AsyncMock) as mock_invoke:
            mock_invoke.return_value = mock_result

            result = await node_fix_script(state)

            assert result["status"] == "SCRIPT_FIXED"
            assert result["generated_script_code"] == "fixed code"
            assert script_path.read_text() == "fixed code"
    asyncio.run(_run())

def test_node_generate_script_mcp_async_write(tmp_path):
    async def _run():
        # Setup mock environment for node_generate_script_mcp
        target_url = "https://example.com"
        state = {
            "target_url": target_url,
            "recorded_steps": [{"action": "capture_grid", "grid_selector": ".grid"}],
            "column_mapping": {"col1": "Column 1"},
            "grid_html": "<table></table>",
            "logs": []
        }

        # Mock LLM response
        mock_result = MagicMock()
        mock_result.content = "```python\nnew script code\n```"

        # Mock browser and build_script_prompt
        mock_browser = AsyncMock()

        with patch("deep_scraper.graph.nodes.script_gen.llm_high_thinking.ainvoke", new_callable=AsyncMock) as mock_invoke, \
             patch("deep_scraper.graph.nodes.script_gen.get_mcp_browser", new_callable=AsyncMock) as mock_get_browser, \
             patch("deep_scraper.graph.nodes.script_gen.build_script_prompt") as mock_build_prompt, \
             patch("os.getcwd", return_value=str(tmp_path)):

            mock_invoke.return_value = mock_result
            mock_get_browser.return_value = mock_browser
            mock_build_prompt.return_value = "Prompt content"

            result = await node_generate_script_mcp(state)

            assert result["status"] == "SCRIPT_GENERATED"
            assert result["generated_script_code"] == "new script code"

            # Verify file was written
            script_path = result["generated_script_path"]
            assert os.path.exists(script_path)
            with open(script_path, 'r') as f:
                assert f.read() == "new script code"
    asyncio.run(_run())
