from langgraph.graph import StateGraph, END
from deep_scraper.core.state import AgentState
from deep_scraper.graph.nodes import (
    node_navigate, 
    node_analyze, 
    node_click_link, 
    node_perform_search, 
    node_extract,
    node_generate_script,
    node_test_script,
    node_fix_script
)
from deep_scraper.core.browser import BrowserManager

# Define conditional logic for edges
def should_search_or_click(state: AgentState):
    """
    Decides the next node based on the analysis of the current page.
    """
    status = state.get("status")
    attempt_count = state.get("attempt_count", 0)
    
    # Circuit Breaker
    if attempt_count > 5:
        print("Circuit Breaker Tripped!")
        return "end" # Map to END
    
    # Handle login required - stop the agent
    if status == "LOGIN_REQUIRED":
        print("🔐 Login required - cannot proceed")
        return "end"
        
    if status == "SEARCH_PAGE_FOUND":
        return "perform_search"
    else:
        return "click_link"

def check_search_status(state: AgentState):
    """
    Decides next step after search attempt.
    """
    status = state.get("status")
    if status == "SEARCH_EXECUTED":
        return "extract"
    else:
        return "end" # Failed search


def check_test_result(state: AgentState):
    """
    Decides what to do after testing the script.
    - If passed: end (success!)
    - If failed and attempts < 3: fix and retry
    - If failed and attempts >= 3: end (give up)
    """
    status = state.get("status")
    attempts = state.get("script_test_attempts", 0)
    
    if status == "TEST_PASSED":
        print("✅ Script test passed! Workflow complete.")
        return "end"
    elif attempts >= 3:
        print("❌ Max retries reached. Giving up.")
        return "end"
    else:
        print(f"🔄 Test failed, attempting fix (attempt {attempts}/3)")
        return "fix_script"


def after_fix(state: AgentState):
    """After fixing, always go back to test."""
    return "test_script"


# Build the Graph
workflow = StateGraph(AgentState)

# Add Nodes
workflow.add_node("navigate", node_navigate)
workflow.add_node("analyze", node_analyze)
workflow.add_node("click_link", node_click_link)
workflow.add_node("perform_search", node_perform_search)
workflow.add_node("extract", node_extract)
workflow.add_node("generate_script", node_generate_script)
workflow.add_node("test_script", node_test_script)
workflow.add_node("fix_script", node_fix_script)

# Add Edges
# Start -> Navigate
workflow.set_entry_point("navigate")

# Navigate -> Analyze
workflow.add_edge("navigate", "analyze")

# Analyze -> [Perform Search OR Click Link]
workflow.add_conditional_edges(
    "analyze",
    should_search_or_click,
    {
        "perform_search": "perform_search",
        "click_link": "click_link",
        "end": END
    }
)

# Click Link -> Navigate (Loop back to re-analyze new page)
workflow.add_edge("click_link", "navigate")

# Perform Search -> Extract
workflow.add_conditional_edges(
    "perform_search",
    check_search_status,
    {"extract": "extract", "end": END}
)

# Extract -> End (Script generation disabled for now)
workflow.add_edge("extract", END)

# --- SCRIPT GENERATION DISABLED ---
# To re-enable, uncomment below and comment out the line above
# 
# # Generate Script -> Test Script
# workflow.add_edge("generate_script", "test_script")
# 
# # Test Script -> [End OR Fix Script]
# workflow.add_conditional_edges(
#     "test_script",
#     check_test_result,
#     {
#         "end": END,
#         "fix_script": "fix_script"
#     }
# )
# 
# # Fix Script -> Test Script (retry loop)
# workflow.add_edge("fix_script", "test_script")

# Compile
app = workflow.compile()

if __name__ == "__main__":
    import asyncio
    
    async def main():
        print("Starting Deep Scraper Engine...")
        
        # Initial State
        initial_state = AgentState(
            target_url="https://vaclmweb1.brevardclerk.us/AcclaimWeb/search/SearchTypeName",
            search_query="Lauren Homes",
            current_page_summary="",
            logs=[],
            attempt_count=0,
            status="NAVIGATING",
            extracted_data=[],
            search_selectors={},
            generated_script_path=None,
            generated_script_code=None,
            script_test_attempts=0,
            script_error=None
        )
        
        # Run the graph
        # Using ainvoke for async execution
        async for output in app.astream(initial_state):
            for key, value in output.items():
                print(f"Output from node '{key}':")
                print("------------------")
                # print(value) # Verbose
                
        print("Graph execution finished.")
        
        # Clean up
        browser_manager = BrowserManager()
        await browser_manager.close()

    asyncio.run(main())
