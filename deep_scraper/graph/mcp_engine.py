"""
MCP-enabled Engine - Runs the scraper workflow using Playwright MCP.

Uses MCP for navigation and LLM for script generation with test/fix loop.

Now imports from modular nodes/ package for better maintainability.
"""

from langgraph.graph import StateGraph, END
from deep_scraper.core.state import AgentState

# Import from modular nodes package
from deep_scraper.graph.nodes import (
    node_navigate_mcp,
    node_analyze_mcp,
    node_click_link_mcp,
    node_perform_search_mcp,
    node_capture_columns_mcp,
    node_generate_script_mcp,
    node_test_script,
    node_fix_script,
    node_escalate
)


def should_search_or_click(state: AgentState):
    """Decides the next node based on the analysis of the current page."""
    status = state.get("status")
    attempt_count = state.get("attempt_count", 0)
    disclaimer_click_attempts = state.get("disclaimer_click_attempts", 0)
    
    # Circuit breakers
    if attempt_count > 5:
        print("⚡ Circuit Breaker: Too many navigation attempts")
        return "end"
    
    if disclaimer_click_attempts >= 5:
        print("⚡ Circuit Breaker: Too many disclaimer click attempts")
        return "escalate"
    
    if status == "FAILED":
        print("❌ Node returned FAILED status - escalating")
        return "escalate"
    
    if status == "LOGIN_REQUIRED":
        print("🔐 Login required - cannot proceed")
        return "end"

    if state.get("healing_attempts", 0) >= 2:
        print("🚨 AI Healing Budget Exceeded!")
        return "escalate"
    
    # Results grid found - go directly to capture columns
    if status == "RESULTS_GRID_FOUND":
        print("📊 Results grid found - capturing columns")
        return "capture_columns"
        
    if status == "SEARCH_PAGE_FOUND":
        return "perform_search"
    else:
        return "click_link"


def check_search_status(state: AgentState):
    """Decides next step after search attempt."""
    status = state.get("status")
    if status == "SEARCH_EXECUTED":
        return "capture_columns"
    elif status == "FAILED":
        # If search failed (e.g. no grid found), go back to analyze 
        # to see where we are and try again.
        print("🔍 Search failed to find results - re-analyzing page...")
        return "analyze"
    else:
        return "end"


def check_test_result(state: AgentState):
    """Decides next step after script test."""
    status = state.get("status")
    attempts = state.get("script_test_attempts", 0)
    
    # Script passed test
    if status == "SCRIPT_TESTED":
        print("✅ Script test passed!")
        return "end"
    
    # Too many attempts
    if attempts >= 3:
        print(f"❌ Max test attempts ({attempts}) reached")
        return "escalate"
    
    # Script failed - try to fix it
    if status in ("SCRIPT_FAILED", "SCRIPT_ERROR"):
        print(f"🔧 Script failed, attempting fix (attempt {attempts})")
        return "fix_script"
    
    return "end"


# Build the MCP-enabled Graph
mcp_workflow = StateGraph(AgentState)

# Add Nodes
mcp_workflow.add_node("navigate", node_navigate_mcp)
mcp_workflow.add_node("analyze", node_analyze_mcp)
mcp_workflow.add_node("click_link", node_click_link_mcp)
mcp_workflow.add_node("perform_search", node_perform_search_mcp)
mcp_workflow.add_node("capture_columns", node_capture_columns_mcp)
mcp_workflow.add_node("generate_script", node_generate_script_mcp)
mcp_workflow.add_node("test_script", node_test_script)
mcp_workflow.add_node("fix_script", node_fix_script)
mcp_workflow.add_node("escalate", node_escalate)

# Add Edges
mcp_workflow.set_entry_point("navigate")
mcp_workflow.add_edge("navigate", "analyze")

mcp_workflow.add_conditional_edges(
    "analyze",
    should_search_or_click,
    {
        "perform_search": "perform_search",
        "capture_columns": "capture_columns",
        "click_link": "click_link",
        "escalate": "escalate",
        "end": END
    }
)

mcp_workflow.add_edge("click_link", "analyze")

mcp_workflow.add_conditional_edges(
    "perform_search",
    check_search_status,
    {
        "capture_columns": "capture_columns", 
        "analyze": "analyze",
        "escalate": "escalate", 
        "end": END
    }
)

mcp_workflow.add_edge("capture_columns", "generate_script")

# LLM generates script -> Test it -> Fix if needed
mcp_workflow.add_edge("generate_script", "test_script")

mcp_workflow.add_conditional_edges(
    "test_script",
    check_test_result,
    {
        "fix_script": "fix_script",
        "escalate": "escalate",
        "end": END
    }
)

# Fix script -> Test again
mcp_workflow.add_edge("fix_script", "test_script")

mcp_workflow.add_edge("escalate", END)

# Compile
mcp_app = mcp_workflow.compile()


async def run_mcp_scraper(url: str, search_query: str):
    """
    Run the MCP-enabled scraper.
    
    Args:
        url: Target URL to scrape
        search_query: Search term to use
        
    Returns:
        Final state after workflow completion
    """
    from deep_scraper.core.mcp_adapter import get_mcp_adapter, is_mcp_available
    
    # Check MCP availability
    if not await is_mcp_available():
        raise Exception(
            "MCP server not running. Start with:\n"
            "npx @executeautomation/playwright-mcp-server"
        )
    
    initial_state = AgentState(
        target_url=url,
        search_query=search_query,
        current_page_summary="",
        logs=[],
        attempt_count=0,
        status="NAVIGATING",
        extracted_data=[],
        search_selectors={},
        generated_script_path=None,
        generated_script_code=None,
        script_test_attempts=0,
        script_error=None,
        thought_signature=None,
        healing_attempts=0,
        needs_human_review=False,
        recorded_steps=[],
        column_mapping={},
        # Memory for click loop prevention
        disclaimer_click_attempts=0,
        clicked_selectors=[]
    )
    
    final_state = None
    async for output in mcp_app.astream(initial_state):
        for key, value in output.items():
            print(f"--- Output from '{key}' ---")
            final_state = value
    
    return final_state
