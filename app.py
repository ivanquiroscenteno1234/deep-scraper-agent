import streamlit as st
import subprocess
import sys
import os
import json
import tempfile

st.set_page_config(page_title="Deep Scraper Agent", page_icon="🕵️", layout="wide")

# --- Custom CSS for Dark Theme ---
st.markdown("""
<style>
    .stApp { background-color: #0e1117; }
    .main-header { 
        font-size: 2.5rem; 
        font-weight: 700; 
        background: linear-gradient(90deg, #00d4ff, #7c3aed); 
        -webkit-background-clip: text; 
        -webkit-text-fill-color: transparent; 
        margin-bottom: 1rem;
    }
    .log-container {
        background-color: #1a1a2e;
        border-radius: 8px;
        padding: 1rem;
        font-family: monospace;
        max-height: 400px;
        overflow-y: auto;
    }
</style>
""", unsafe_allow_html=True)

# --- Header ---
st.markdown('<p class="main-header">🕵️ Deep Scraper Agent</p>', unsafe_allow_html=True)
st.caption("Autonomous navigation, search, and data extraction powered by LangGraph + Gemini")

# --- Sidebar Inputs ---
with st.sidebar:
    st.header("🎯 Mission Parameters")
    target_url = st.text_input(
        "Target URL",
        value="https://vaclmweb1.brevardclerk.us/AcclaimWeb/search/SearchTypeName",
        help="The starting URL for the agent to explore."
    )
    search_query = st.text_input(
        "Search Term",
        value="Lauren Homes",
        help="The name or term to search for."
    )
    
    st.divider()
    run_button = st.button("🚀 Launch Agent", type="primary", use_container_width=True)

# --- Main Area ---
col_left, col_right = st.columns([1, 1])

with col_left:
    st.subheader("📜 Agent Logs")
    log_placeholder = st.empty()
    
with col_right:
    st.subheader("📊 Extracted Data")
    data_placeholder = st.empty()

# --- Agent Execution via Subprocess ---
if run_button:
    # Create a temporary Python script to run the agent
    agent_script = f'''
import asyncio
import json
import sys
sys.path.insert(0, r"{os.getcwd()}")

from graph_engine import app as graph_app
from agent_state import AgentState
from browser_manager import BrowserManager

async def run_agent():
    initial_state = AgentState(
        target_url="{target_url}",
        search_query="{search_query}",
        current_page_summary="",
        logs=[],
        attempt_count=0,
        status="NAVIGATING",
        extracted_data=[],
        search_selectors={{}}
    )
    
    final_state = None
    async for output in graph_app.astream(initial_state):
        for key, value in output.items():
            print(f"--- Output from '{{key}}' ---", flush=True)
            if isinstance(value, dict):
                if "status" in value:
                    print(f"Status: {{value['status']}}", flush=True)
                if "logs" in value:
                    for log in value.get("logs", [])[-3:]:
                        print(f"  Log: {{log}}", flush=True)
                final_state = value
    
    # Cleanup
    browser = BrowserManager()
    await browser.close()
    
    # Output final data as JSON on last line
    if final_state:
        extracted = final_state.get("extracted_data", [])
        print("---EXTRACTED_DATA_JSON---", flush=True)
        print(json.dumps(extracted), flush=True)
    
    return final_state

if __name__ == "__main__":
    asyncio.run(run_agent())
'''
    
    # Write to temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
        f.write(agent_script)
        temp_script_path = f.name
    
    try:
        with st.spinner("🤖 Agent is working... (this may take a minute)"):
            # Run the subprocess
            result = subprocess.run(
                [sys.executable, temp_script_path],
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
                cwd=os.getcwd(),
                env={**os.environ, "PYTHONIOENCODING": "utf-8"}
            )
            
            # Display logs
            output = result.stdout + result.stderr
            log_placeholder.code(output, language="text")
            
            # Check if CSV was saved
            if "Data saved to:" in output:
                import re
                csv_match = re.search(r'Data saved to: (.+\.csv)', output)
                if csv_match:
                    csv_path = csv_match.group(1).strip()
                    st.success(f"📁 **CSV saved to:** `{csv_path}`")
            
            # Parse extracted data
            if "---EXTRACTED_DATA_JSON---" in output:
                json_line = output.split("---EXTRACTED_DATA_JSON---")[1].strip().split("\n")[0]
                try:
                    extracted_data = json.loads(json_line)
                    if extracted_data:
                        import pandas as pd
                        df = pd.DataFrame(extracted_data)
                        data_placeholder.dataframe(df, use_container_width=True)
                        st.success(f"✅ Extraction complete! Found {len(extracted_data)} records.")
                        
                        # Provide download button
                        csv_data = df.to_csv(index=False)
                        st.download_button(
                            label="📥 Download CSV",
                            data=csv_data,
                            file_name=f"extracted_data_{search_query.replace(' ', '_')}.csv",
                            mime="text/csv"
                        )
                    else:
                        data_placeholder.info("No data extracted. Check logs for details.")
                except json.JSONDecodeError:
                    data_placeholder.warning("Could not parse extracted data.")
            else:
                data_placeholder.info("Agent finished. Check logs for details.")
                
            if result.returncode != 0:
                st.error(f"Agent exited with code {result.returncode}")
                
    except subprocess.TimeoutExpired:
        st.error("⏰ Agent timed out after 5 minutes.")
    except Exception as e:
        st.error(f"❌ Error: {e}")
    finally:
        # Cleanup temp file
        if os.path.exists(temp_script_path):
            os.unlink(temp_script_path)
