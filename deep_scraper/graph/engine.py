from langgraph.graph import StateGraph, END
from deep_scraper.core.state import AgentState
from deep_scraper.graph.nodes import (
    node_navigate, 
    node_analyze, 
    node_click_link, 
    node_perform_search, 
    node_extract,
    node_generate_script
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

# Build the Graph
workflow = StateGraph(AgentState)

# Add Nodes
workflow.add_node("navigate", node_navigate)
workflow.add_node("analyze", node_analyze)
workflow.add_node("click_link", node_click_link)
workflow.add_node("perform_search", node_perform_search)
workflow.add_node("extract", node_extract)
workflow.add_node("generate_script", node_generate_script)

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
# Spec said "Loop back to node_analyze", but usually we need to 
# refresh the page content first (which happens in navigate/analyze).
# Let's verify spec: "Always loop back to node_analyze (to check the new page)."
# `node_analyze` uses `state['current_page_summary']`. 
# `node_click_link` executes the click, but doesn't strictly refresh the summary 
# (although BrowserManager is stateful). 
# Safer to go back to `navigate` if navigate just gets content, OR have `click_link` return updated summary.
# Spec says: "node_navigate: Calls BrowserManager.go_to... Updates state['current_page_summary']".
# If we loop to Analyze directly, we might have stale summary.
# BUT `node_click_link` doesn't output summary.
# So we should probably loop back to a node that refreshes content.
# Since `node_navigate` calls `go_to` (reloading URL), that might be bad if we just clicked a link to a NEW URL.
# Let's modify logic: `node_navigate` calls `go_to` ONLY if we are at start (attempt=0).
# Actually, I implemented `node_navigate` to only go_to if attempt_count == 0.
# So looping back to `navigate` is safe and correct to refresh content!
workflow.add_edge("click_link", "navigate")

# Perform Search -> Extract
workflow.add_conditional_edges(
    "perform_search",
    check_search_status,
    {"extract": "extract", "end": END}
)

# Extract -> Generate Script
workflow.add_edge("extract", "generate_script")

# Generate Script -> End
workflow.add_edge("generate_script", END)

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
            search_selectors={}
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
