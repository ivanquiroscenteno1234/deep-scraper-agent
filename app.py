import streamlit as st
import subprocess
import sys
import os
import json
import tempfile
import time
import glob
import re

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
        font-family: 'Consolas', 'Monaco', monospace;
        font-size: 0.85rem;
        max-height: 450px;
        overflow-y: auto;
        line-height: 1.4;
    }
    .log-node { color: #00d4ff; font-weight: bold; }
    .log-success { color: #00ff88; }
    .log-warning { color: #ffaa00; }
    .log-error { color: #ff4444; }
    .log-status { color: #888888; }
    .log-info { color: #cccccc; }
</style>
""", unsafe_allow_html=True)

def format_logs(output: str) -> str:
    """Format logs with color-coded sections."""
    lines = output.split('\n')
    formatted = []
    
    for line in lines:
        escaped_line = line.replace('<', '&lt;').replace('>', '&gt;')
        
        if '--- Node:' in line or "--- Output from" in line:
            formatted.append(f'<span class="log-node">{escaped_line}</span>')
        elif '✅' in line or 'succeeded' in line.lower() or 'Success' in line:
            formatted.append(f'<span class="log-success">{escaped_line}</span>')
        elif '⚠️' in line or 'Warning' in line or 'failed' in line.lower():
            formatted.append(f'<span class="log-warning">{escaped_line}</span>')
        elif '❌' in line or 'Error' in line or 'error' in line.lower():
            formatted.append(f'<span class="log-error">{escaped_line}</span>')
        elif 'Status:' in line or 'Decision:' in line:
            formatted.append(f'<span class="log-status">{escaped_line}</span>')
        else:
            formatted.append(f'<span class="log-info">{escaped_line}</span>')
    
    return '<br>'.join(formatted)

# --- Header ---
st.markdown('<p class="main-header">🕵️ Deep Scraper Agent</p>', unsafe_allow_html=True)
st.caption("Autonomous navigation, search, and data extraction powered by LangGraph + Gemini")

# --- Sidebar Inputs ---
with st.sidebar:
    st.header("🎯 Mission Parameters")
    target_url = st.text_input(
        "Target URL",
        value="https://records.flaglerclerk.com/",
        help="The starting URL for the agent to explore."
    )
    search_query = st.text_input(
        "Search Term",
        value="Lauren",
        help="The name or term to search for."
    )
    
    st.divider()
    run_button = st.button("🚀 Launch Agent", type="primary")
    
    # --- Script Runner Section ---
    st.divider()
    st.header("🔧 Script Runner")
    
    # Find available scripts
    scripts_dir = os.path.join(os.getcwd(), "output", "generated_scripts")
    if os.path.exists(scripts_dir):
        script_files = glob.glob(os.path.join(scripts_dir, "*.py"))
        script_names = [os.path.basename(f) for f in script_files]
    else:
        script_files = []
        script_names = []
    
    if script_names:
        selected_script = st.selectbox(
            "Select Script",
            options=script_names,
            help="Choose a previously generated script to run"
        )
        runner_search = st.text_input(
            "Search Term for Script",
            value="",
            help="The search term to pass to the script"
        )
        run_script_button = st.button("▶️ Run Script")
    else:
        st.info("No scripts available yet. Run the agent to generate one!")
        selected_script = None
        runner_search = ""
        run_script_button = False

# --- Main Area ---
col_left, col_right = st.columns([1, 1])

with col_left:
    st.subheader("📜 Agent Logs")
    log_placeholder = st.empty()
    duration_placeholder = st.empty()
    
with col_right:
    st.subheader("📊 Extracted Data")
    data_placeholder = st.empty()

# --- Agent Execution via Subprocess ---
if run_button:
    start_time = time.time()
    
    agent_script = f'''
import asyncio
import json
import sys
sys.path.insert(0, r"{os.getcwd()}")

from deep_scraper.graph.engine import app as graph_app
from deep_scraper.core.state import AgentState
from deep_scraper.core.browser import BrowserManager

async def run_agent():
    initial_state = AgentState(
        target_url="{target_url}",
        search_query="{search_query}",
        current_page_summary="",
        logs=[],
        attempt_count=0,
        status="NAVIGATING",
        extracted_data=[],
        search_selectors={{}},
        generated_script_path=None,
        generated_script_code=None,
        script_test_attempts=0,
        script_error=None
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
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
        f.write(agent_script)
        temp_script_path = f.name
    
    try:
        with st.spinner("🤖 Agent is working... (check terminal for real-time logs)"):
            process = subprocess.Popen(
                [sys.executable, temp_script_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, # Merge stderr into stdout
                text=True,
                cwd=os.getcwd(),
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                bufsize=1, # Line buffered
                universal_newlines=True
            )
            
            full_output = ""
            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                if line:
                    print(line, end='', flush=True) # Stream to terminal
                    full_output += line
                    # Update logs in UI periodically or at the end
                    formatted_logs = format_logs(full_output)
                    log_placeholder.markdown(f'<div class="log-container">{formatted_logs}</div>', unsafe_allow_html=True)
            
            duration = time.time() - start_time
            output = full_output
            
            # Display final duration
            duration_placeholder.info(f"⏱️ **Execution time:** {duration:.1f} seconds")
            
            # Check for script generation
            if "Generated Playwright script:" in output or "Script saved to:" in output:
                script_match = re.search(r'Script saved to: (.+\.py)', output)
                if script_match:
                    script_path = script_match.group(1).strip()
                    st.success(f"🎉 **Script Generated Successfully!** `{script_path}`")
                else:
                    st.success("🎉 **Script Generated Successfully!**")
            elif "Script generation failed" in output:
                st.warning("⚠️ Script generation failed. Check logs for details.")
            
            # Check if CSV was saved
            if "Data saved to:" in output:
                csv_match = re.search(r'Data saved to: (.+\.csv)', output)
                if csv_match:
                    csv_path = csv_match.group(1).strip()
                    st.success(f"📁 **CSV saved to:** `{csv_path}`")
            
            # Parse extracted data
            if "---EXTRACTED_DATA_JSON---" in output:
                try:
                    parts = output.split("---EXTRACTED_DATA_JSON---")
                    if len(parts) > 1:
                        json_line = parts[1].strip().split("\n")[0]
                        extracted_data = json.loads(json_line)
                        if extracted_data:
                            import pandas as pd
                            df = pd.DataFrame(extracted_data)
                            data_placeholder.dataframe(df)
                            st.success(f"✅ Extraction complete! Found {len(extracted_data)} records.")
                            
                            csv_data = df.to_csv(index=False)
                            st.download_button(
                                label="📥 Download CSV",
                                data=csv_data,
                                file_name=f"extracted_data_{search_query.replace(' ', '_')}.csv",
                                mime="text/csv"
                            )
                        else:
                            data_placeholder.info("No data extracted. Check logs for details.")
                except Exception as e:
                    data_placeholder.warning(f"Could not parse extracted data: {e}")
            else:
                data_placeholder.info("Agent finished. Check logs for details.")
                
            if process.returncode != 0:
                st.error(f"Agent exited with code {process.returncode}")
                
    except subprocess.TimeoutExpired:
        st.error("⏰ Agent timed out after 5 minutes.")
    except Exception as e:
        st.error(f"❌ Error: {e}")
    finally:
        if os.path.exists(temp_script_path):
            os.unlink(temp_script_path)

# --- Script Runner Execution ---
if run_script_button and selected_script and runner_search:
    script_path = os.path.join(scripts_dir, selected_script)
    
    # Create a runner script that imports and calls the generated function
    county_name = selected_script.replace("_scraper.py", "")
    
    runner_script = f'''
import sys
import json
sys.path.insert(0, r"{scripts_dir}")

# Import the generated script
import importlib.util
spec = importlib.util.spec_from_file_location("script", r"{script_path}")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

# Find the scrape function
func_name = "scrape_{county_name}"
if hasattr(module, func_name):
    result = getattr(module, func_name)("{runner_search}")
    print(f"---SCRIPT_RESULT---")
    print(result if result else "No results")
else:
    # Try to find any function starting with scrape_
    for name in dir(module):
        if name.startswith("scrape_"):
            result = getattr(module, name)("{runner_search}")
            print(f"---SCRIPT_RESULT---")
            print(result if result else "No results")
            break
'''
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
        f.write(runner_script)
        temp_runner_path = f.name
    
    try:
        with st.spinner(f"🔧 Running {selected_script}..."):
            start_time = time.time()
            
            result = subprocess.run(
                [sys.executable, temp_runner_path],
                capture_output=True,
                text=True,
                timeout=180,
                cwd=os.getcwd(),
                env={**os.environ, "PYTHONIOENCODING": "utf-8"}
            )
            
            duration = time.time() - start_time
            
            output = result.stdout + result.stderr
            formatted_logs = format_logs(output)
            log_html = f'<div class="log-container">{formatted_logs}</div>'
            log_placeholder.markdown(log_html, unsafe_allow_html=True)
            
            duration_placeholder.info(f"⏱️ **Script execution time:** {duration:.1f} seconds")
            
            # Check for CSV result
            if "---SCRIPT_RESULT---" in output:
                result_line = output.split("---SCRIPT_RESULT---")[1].strip().split("\n")[0]
                if result_line and result_line != "No results" and ".csv" in result_line:
                    st.success(f"📁 **Results saved to:** `{result_line}`")
                    
                    # Try to load and display the CSV
                    if os.path.exists(result_line):
                        import pandas as pd
                        df = pd.read_csv(result_line)
                        data_placeholder.dataframe(df)
                        st.success(f"✅ Found {len(df)} records.")
                else:
                    data_placeholder.info("Script completed. Check output for details.")
            
            if result.returncode != 0:
                st.error(f"Script exited with code {result.returncode}")
                
    except subprocess.TimeoutExpired:
        st.error("⏰ Script timed out after 3 minutes.")
    except Exception as e:
        st.error(f"❌ Error: {e}")
    finally:
        if os.path.exists(temp_runner_path):
            os.unlink(temp_runner_path)

elif run_script_button and not runner_search:
    st.warning("Please enter a search term for the script.")
