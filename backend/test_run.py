import asyncio
import os
import sys
import traceback
from datetime import datetime

# Add project root to sys.path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, root_dir)

from deep_scraper.graph.mcp_engine import mcp_app
from deep_scraper.core.state import AgentState

async def run_test():
    print(f"🚀 [{datetime.now().strftime('%H:%M:%S')}] Starting Flagler County Test Run...")
    
    # 1. Setup initial state
    initial_state = AgentState(
        target_url="https://records.flaglerclerk.com/",
        search_query="ESSEX HOME MORTGAGE SERVICING CORP",
        start_date="01/01/1992",
        end_date="12/31/1992",
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
        discovered_grid_selectors=[],
        healing_attempts=0,
        needs_human_review=False,
        recorded_steps=[],
        column_mapping={},
        thought_signature=None,
        grid_html=None,
        disclaimer_click_attempts=0,
        clicked_selectors=[]
    )

    # 2. Run agent and stream outputs
    try:
        print(f"📡 [{datetime.now().strftime('%H:%M:%S')}] Entering agent graph...")
        async for output in mcp_app.astream(initial_state):
            node_name = list(output.keys())[0]
            node_data = output[node_name]
            
            print(f"\n✅ Node '{node_name}' finished.")
            
            # Print new logs
            logs = node_data.get("logs", [])
            for log in logs:
                # Only print logs that belong to this node run
                # (logs are cumulative in state, but usually node_data['logs'] contains current run's logs)
                if isinstance(log, dict):
                    print(f"  [{log.get('node', 'Agent')}] {log.get('level', 'INFO')}: {log.get('message')}")
                else:
                    print(f"  [Log] {log}")
            
            # Print status
            status = node_data.get("status")
            if status:
                print(f"  ➡️ Status: {status}")
            
            if node_data.get("generated_script_path"):
                print(f"  ✨ Generated Script: {node_data['generated_script_path']}")
            
            # Small delay between nodes for stability
            await asyncio.sleep(0.5)

        print(f"\n🏁 [{datetime.now().strftime('%H:%M:%S')}] Test run completed!")
        
    except Exception as e:
        print(f"\n❌ [{datetime.now().strftime('%H:%M:%S')}] Test run CRASHED: {str(e)}")
        traceback.print_exc()

if __name__ == "__main__":
    try:
        asyncio.run(run_test())
    except KeyboardInterrupt:
        print("\n🛑 Test interrupted by user.")
    except Exception as e:
        print(f"\n🛑 Main loop failed: {e}")
        traceback.print_exc()
