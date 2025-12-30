import streamlit as st
import subprocess
import sys
import os
import json
import tempfile
import time
import glob
import re
import socket
import signal

# --- MCP Server Management ---
# Using ExecuteAutomation MCP server with native codegen support
MCP_PORT = 8931

def is_port_in_use(port: int) -> bool:
    """Check if a port is already in use."""
    # Check IPv6 first (some servers bind to ::1)
    try:
        with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as s:
            s.settimeout(1.0)
            if s.connect_ex(('::1', port)) == 0:
                return True
    except:
        pass
    # Fallback to IPv4
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

def start_mcp_server(port: int = MCP_PORT) -> subprocess.Popen:
    """Start the ExecuteAutomation Playwright MCP server."""
    print(f"🚀 Starting ExecuteAutomation MCP server on port {port}...")
    
    # Start ExecuteAutomation MCP server as subprocess
    if os.name == 'nt':
        # Windows: use shell to find npx in PATH
        process = subprocess.Popen(
            f'npx @executeautomation/playwright-mcp-server --port {port}',
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            shell=True,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
        )
    else:
        # Unix: direct call
        process = subprocess.Popen(
            ["npx", "@executeautomation/playwright-mcp-server", "--port", str(port)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
    

    # Wait for server to be ready (max 30 seconds for first install)
    for i in range(60):
        if is_port_in_use(port):
            print(f"✅ ExecuteAutomation MCP server ready on port {port}")
            return process
        time.sleep(0.5)
    
    print("⚠️ MCP server may not be fully ready")
    return process


def stop_mcp_server(process: subprocess.Popen):
    """Stop the MCP server process."""
    if process:
        print("🛑 Stopping MCP server...")
        try:
            if os.name == 'nt':
                # Windows: use taskkill to terminate process tree
                subprocess.run(['taskkill', '/F', '/T', '/PID', str(process.pid)], 
                             capture_output=True)
            else:
                # Unix: send SIGTERM
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            process.wait(timeout=5)
        except Exception as e:
            print(f"⚠️ Error stopping MCP server: {e}")
            process.kill()
        print("✅ MCP server stopped")


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
    
    # MCP is now the only engine (non-MCP files were removed)
    use_mcp = True  # Always use MCP
    
    run_button = st.button("🚀 Launch Agent", type="primary")
    
    st.info("🔗 Using MCP Engine - Server will auto-start with agent")



    
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
    
    if use_mcp:
        # MCP Engine - Uses Playwright MCP for navigation and codegen
        agent_script = f'''
import asyncio
import json
import sys
import os
sys.path.insert(0, r"{os.getcwd()}")

# Load environment variables from .env
from dotenv import load_dotenv
load_dotenv(r"{os.path.join(os.getcwd(), '.env')}")

from deep_scraper.graph.mcp_engine import mcp_app
from deep_scraper.core.state import AgentState
from deep_scraper.core.mcp_adapter import get_mcp_adapter


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
        script_error=None,
        thought_signature=None,
        healing_attempts=0,
        needs_human_review=False,
        recorded_steps=[],
        column_mapping={{}}
    )
    
    print("🔗 Using MCP Engine with Playwright MCP...", flush=True)
    
    final_state = None
    async for output in mcp_app.astream(initial_state):
        for key, value in output.items():
            print(f"--- Output from '{{key}}' ---", flush=True)
            if isinstance(value, dict):
                if "status" in value:
                    print(f"Status: {{value['status']}}", flush=True)
                if "logs" in value:
                    for log in value.get("logs", [])[-3:]:
                        print(f"  Log: {{log}}", flush=True)
                final_state = value
    
    # Cleanup MCP
    try:
        adapter = get_mcp_adapter()
        await adapter.close()
    except:
        pass
    
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
    
    mcp_process = None
    
    try:
        # Start MCP server if using MCP mode
        if use_mcp:
            if is_port_in_use(8931):
                st.info("🔗 MCP server already running on port 8931")
            else:
                with st.spinner("🚀 Starting MCP server..."):
                    mcp_process = start_mcp_server(8931)
                    st.success("✅ MCP server started")
        
        with st.spinner("🤖 Agent is working... (check terminal for real-time logs)"):
            process = subprocess.Popen(
                [sys.executable, temp_script_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, # Merge stderr into stdout
                text=True,
                cwd=os.getcwd(),
                env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"},
                bufsize=1, # Line buffered
                encoding='utf-8',
                errors='replace'  # Replace undecodable chars instead of crashing
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
        # Stop MCP server if we started it
        if mcp_process:
            with st.spinner("🛑 Stopping MCP server..."):
                stop_mcp_server(mcp_process)
                st.info("✅ MCP server stopped")
        
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
result = None

if hasattr(module, func_name):
    result = getattr(module, func_name)("{runner_search}")
else:
    # Try to find any function starting with scrape_
    for name in dir(module):
        if name.startswith("scrape_"):
            result = getattr(module, name)("{runner_search}")
            break

# Output as JSON for parsing
print("---SCRIPT_RESULT_JSON---")
print(json.dumps(result if result else []))
'''
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
        f.write(runner_script)
        temp_runner_path = f.name
    
    try:
        with st.spinner(f"🔧 Running {selected_script} with search term '{runner_search}'..."):
            start_time = time.time()
            
            result = subprocess.run(
                [sys.executable, temp_runner_path],
                capture_output=True,
                text=True,
                timeout=180,
                cwd=os.getcwd(),
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                encoding='utf-8',
                errors='replace'
            )
            
            duration = time.time() - start_time
            
            # Display execution info
            duration_placeholder.info(f"⏱️ **Script execution time:** {duration:.1f} seconds")
            
            output = result.stdout + result.stderr
            
            # Extract script logs (stdout before the JSON marker) for display
            script_logs = result.stdout
            if "---SCRIPT_RESULT_JSON---" in script_logs:
                script_logs = script_logs.split("---SCRIPT_RESULT_JSON---")[0]
            
            # Show script logs in the log panel
            if script_logs.strip():
                formatted_logs = format_logs(script_logs)
                log_placeholder.markdown(f'<div class="log-container">{formatted_logs}</div>', unsafe_allow_html=True)
            
            # Also show stderr if any errors
            if result.stderr:
                st.error("Script Errors:")
                st.code(result.stderr)
            
            # Parse JSON result
            if "---SCRIPT_RESULT_JSON---" in output:
                try:
                    json_str = output.split("---SCRIPT_RESULT_JSON---")[1].strip().split("\n")[0]
                    extracted_data = json.loads(json_str)
                    
                    if extracted_data and len(extracted_data) > 0:
                        import pandas as pd
                        df = pd.DataFrame(extracted_data)
                        
                        # Display in data area
                        data_placeholder.dataframe(df, use_container_width=True)
                        st.success(f"✅ **{selected_script}** found **{len(extracted_data)} records** for '{runner_search}'")
                        
                        # Download button
                        csv_data = df.to_csv(index=False)
                        st.download_button(
                            label="📥 Download CSV",
                            data=csv_data,
                            file_name=f"{county_name}_{runner_search.replace(' ', '_')}.csv",
                            mime="text/csv"
                        )
                    else:
                        data_placeholder.warning(f"⚠️ No results found for '{runner_search}'")
                        
                except json.JSONDecodeError as e:
                    st.error(f"Failed to parse script output: {e}")
                    formatted_logs = format_logs(output)
                    log_placeholder.markdown(f'<div class="log-container">{formatted_logs}</div>', unsafe_allow_html=True)
            else:
                # No JSON marker found - show raw output
                formatted_logs = format_logs(output)
                log_placeholder.markdown(f'<div class="log-container">{formatted_logs}</div>', unsafe_allow_html=True)
                data_placeholder.info("Script completed. Check logs for output.")
            
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
