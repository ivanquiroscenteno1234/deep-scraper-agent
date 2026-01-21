import pytest
import sys
import os
from unittest.mock import AsyncMock, MagicMock, patch

# Ensure deep_scraper can be imported
sys.path.append(os.getcwd())

from deep_scraper.graph.nodes.extraction import node_capture_columns_mcp
from deep_scraper.core.state import AgentState

@pytest.mark.asyncio
async def test_node_capture_columns_mcp_optimization():
    print("\n🧪 Testing extraction optimization...")

    # Mock state
    state = {
        "logs": [],
        "recorded_steps": [],
        "search_selectors": {}
    }

    # Mock browser
    mock_browser = AsyncMock()
    # Return filtered HTML directly (optimization check)
    mock_browser.get_filtered_html_with_indices.return_value = {
        "html": "<html><body><table id='resultsTable'><thead><tr><th>Visible Col1</th><th class='hidden'>Hidden Col</th><th>Visible Col2</th></tr></thead><tbody><tr><td>Val1</td><td class='hidden'>Hidden</td><td>Val2</td></tr></tbody></table></body></html>",
        "visible_indices": [0, 2]
    }

    # Mock LLM response
    mock_llm_response = MagicMock()
    mock_llm_response.content = json_str = '{"grid_selector": "#resultsTable", "row_selector": "tbody tr", "columns": ["Visible Col1", "Visible Col2"], "first_data_column_index": 0}'

    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = mock_llm_response

    # Patch dependencies
    # Note: We need to patch where they are imported in the extraction module
    with patch('deep_scraper.graph.nodes.extraction.get_mcp_browser', new=AsyncMock(return_value=mock_browser)), \
         patch('deep_scraper.graph.nodes.extraction.llm', mock_llm), \
         patch('deep_scraper.graph.nodes.extraction.asyncio.sleep', AsyncMock()):

        # Run function
        result = await node_capture_columns_mcp(state)

        # Verify optimization - MUST call get_filtered_html_with_indices
        mock_browser.get_filtered_html_with_indices.assert_called_once()
        print("✅ Called get_filtered_html_with_indices() instead of get_snapshot()")

        # Verify result
        assert result["status"] == "COLUMNS_CAPTURED"
        assert result["column_mapping"] == {"col_0": "Visible Col1", "col_1": "Visible Col2"}
        assert len(result["recorded_steps"]) == 1

        # Verify visible indices are passed through
        step_data = result["recorded_steps"][0]
        assert step_data["visible_column_indices"] == [0, 2]
        print(f"✅ Correctly captured visible indices: {step_data['visible_column_indices']}")

        print("✅ Optimization verification passed!")

if __name__ == "__main__":
    # Allow running directly
    import asyncio
    asyncio.run(test_node_capture_columns_mcp_optimization())
