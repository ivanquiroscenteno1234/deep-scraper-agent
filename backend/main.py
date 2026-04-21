# Deep Scraper Agent Backend (Force reload at 21:50 - Navigation Portal Fix)
import os
import sys
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, HttpUrl
import asyncio
import json
import uuid
from datetime import datetime
from dotenv import load_dotenv
import csv
import io

# Load environment variables from .env
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
# Add root directory to path so we can import deep_scraper
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from deep_scraper.graph.mcp_engine import mcp_app
from deep_scraper.core.state import AgentState

app = FastAPI(title="Deep Scraper API")

# Enable CORS for React frontend (Vite defaults to 5173)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 🛡️ Sentinel: Added strict input validation constraints to prevent large payload DoS
# and malformed data injection before it reaches subprocesses.
class ScrapeRequest(BaseModel):
    url: HttpUrl
    search_query: str = Field(..., max_length=200)
    start_date: str = Field(default="01/01/1980", pattern=r"^\d{2}/\d{2}/\d{4}$")
    end_date: str = Field(default_factory=lambda: datetime.now().strftime("%m/%d/%Y"), pattern=r"^\d{2}/\d{2}/\d{4}$")

class ExecuteRequest(BaseModel):
    script_path: str
    search_query: str = Field(..., max_length=200)
    start_date: str = Field(default="01/01/1980", pattern=r"^\d{2}/\d{2}/\d{4}$")
    end_date: str = Field(default_factory=lambda: datetime.now().strftime("%m/%d/%Y"), pattern=r"^\d{2}/\d{2}/\d{4}$")

# In-memory store for agent status
runs = {}

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/api/scripts")
async def list_scripts():
    """
    Return a list of available generated scripts.
    """
    scripts_dir = os.path.join(os.path.dirname(__file__), "output", "generated_scripts")
    
    def get_scripts(d):
        scripts_list = []
        try:
            for entry in os.scandir(d):
                if entry.is_file() and entry.name.endswith(".py"):
                    modified_time = datetime.fromtimestamp(entry.stat().st_mtime).isoformat()
                    scripts_list.append({
                        "name": entry.name,
                        "path": entry.path,
                        "modified": modified_time
                    })
        except OSError:
            pass
        # Sort by modified date, newest first
        scripts_list.sort(key=lambda x: x["modified"], reverse=True)
        return scripts_list

    if os.path.exists(scripts_dir):
        scripts = await asyncio.to_thread(get_scripts, scripts_dir)
    else:
        scripts = []

    return {"scripts": scripts}

@app.post("/api/run")
async def start_run(request: ScrapeRequest):
    run_id = str(uuid.uuid4())
    runs[run_id] = {
        "status": "starting",
        "url": request.url,
        "query": request.search_query,
        "start_date": request.start_date,
        "end_date": request.end_date,
        "logs": [],
        "startTime": datetime.now().isoformat()
    }
    return {"run_id": run_id}

@app.websocket("/ws/agent/{run_id}")
async def agent_ws(websocket: WebSocket, run_id: str):
    await websocket.accept()
    
    if run_id not in runs:
        await websocket.send_json({"error": "Run not found"})
        await websocket.close()
        return

    run_data = runs[run_id]
    
    try:
        # Initial state for LangGraph
        initial_state = AgentState(
            target_url=str(run_data["url"]),
            search_query=run_data["query"],
            start_date=run_data.get("start_date", "01/01/1980"),
            end_date=run_data.get("end_date", datetime.now().strftime("%m/%d/%Y")),
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
            # Memory for click loop prevention
            disclaimer_click_attempts=0,
            clicked_selectors=[]
        )
        
        # Run agent and stream outputs
        print(f"DEBUG: Starting astream for run {run_id}")
        async for output in mcp_app.astream(initial_state):
            # output is a dict like {'navigate': {...}}
            node_name = list(output.keys())[0]
            node_data = output[node_name]
            print(f"DEBUG: Node {node_name} completed. Status: {node_data.get('status')}")
            
            # Extract logs and status updates
            current_logs = node_data.get("logs", [])
            status = node_data.get("status", "running")
            
            # Send to frontend
            message = {
                "node": node_name,
                "status": status,
                "logs": current_logs,
                "data": {
                    "script_path": node_data.get("generated_script_path"),
                    "extracted_count": len(node_data.get("extracted_data", []))
                }
            }
            print(f"DEBUG: Sending message to frontend: {node_name} ({status})")
            await websocket.send_json(message)
            
            # Update in-memory store
            run_data["status"] = status
            run_data["logs"].extend(current_logs)
            if node_data.get("generated_script_path"):
                run_data["script_path"] = node_data["generated_script_path"]

        print(f"DEBUG: astream finished for run {run_id}")
        await websocket.send_json({"status": "completed"})
        
    except WebSocketDisconnect:
        print(f"WebSocket disconnected for run {run_id}")
    except Exception as e:
        try:
            await websocket.send_json({"error": str(e)})
        except Exception:
            pass  # Connection already closed
    finally:
        try:
            await websocket.close()
        except Exception:
            pass  # Connection already closed

@app.post("/api/execute-script")
async def execute_script(request: ExecuteRequest):
    """
    Run a specific generated script and return the extracted data.
    """
    # 🛡️ Sentinel: Prevent Path Traversal by validating against allowed directory
    scripts_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "output", "generated_scripts"))
    requested_path = os.path.abspath(request.script_path)

    if not requested_path.startswith(os.path.join(scripts_dir, "")):
        return {"error": "Invalid script path: Path traversal detected"}

    if not os.path.exists(requested_path):
        return {"error": "Script file not found"}

    print(f"DEBUG: Executing script {requested_path}")
    print(f"DEBUG: Query='{request.search_query}', Start='{request.start_date}', End='{request.end_date}'")
    
    import subprocess
    import re
    
    try:
        # BOLT ⚡: Replaced blocking subprocess.run with async create_subprocess_exec
        # This prevents the long-running scraper from blocking the FastAPI event loop
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            requested_path,
            request.search_query,
            request.start_date,
            request.end_date,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=os.path.dirname(__file__)
        )
        
        # Wait for the subprocess to complete with timeout
        stdout_bytes, stderr_bytes = await asyncio.wait_for(process.communicate(), timeout=180)

        stdout_text = stdout_bytes.decode()
        stderr_text = stderr_bytes.decode()

        # 1. Flexible Success Detection
        stdout_upper = stdout_text.upper()
        is_success = "SUCCESS" in stdout_upper or "[SUCCESS]" in stdout_upper or "[OK]" in stdout_upper
        
        # 2. Extract Row Count
        row_count = 0
        row_match = re.search(r'(?:Extracted|Found|Saved|Saving)\s+(\d+)\s+(?:rows|records|items)', stdout_text, re.IGNORECASE)
        if row_match:
            row_count = int(row_match.group(1))
            
        # 3. CSV File Resolution
        csv_file = None
        # Try finding path in stdout - support multiple formats
        csv_path_match = re.search(r'(?:saved to|CSV saved:|to|Saved)\s+([^\s]+\.csv)', stdout_text, re.IGNORECASE)
        if csv_path_match:
            csv_file = csv_path_match.group(1).strip()
            
        # Search for the CSV in standardized output/data/ folder
        backend_dir = os.path.dirname(__file__)
        output_data_dir = os.path.join(backend_dir, "output", "data")
        potential_paths = []
        
        if csv_file:
            # 🛡️ Sentinel: Prevent Path Traversal via stdout injection
            parsed_path = os.path.abspath(csv_file)
            allowed_dir = os.path.abspath(output_data_dir)

            # Only allow if it's within the output/data directory
            if parsed_path.startswith(os.path.join(allowed_dir, "")):
                potential_paths.append(parsed_path)

            # Always fallback to checking the basename in the allowed directory
            safe_basename_path = os.path.join(allowed_dir, os.path.basename(csv_file))
            if safe_basename_path not in potential_paths:
                potential_paths.append(safe_basename_path)
        
        # If no csv_file found in stdout, find most recent CSV in output/data/
        if not csv_file:
            def find_newest_csv(d):
                if not os.path.isdir(d):
                    return None
                newest = None
                max_mtime = -1
                try:
                    for entry in os.scandir(d):
                        if entry.is_file() and entry.name.endswith('.csv'):
                            mtime = entry.stat().st_mtime
                            if mtime > max_mtime:
                                max_mtime = mtime
                                newest = entry.path
                except OSError:
                    pass
                return newest

            newest_csv_path = await asyncio.to_thread(find_newest_csv, output_data_dir)
            if newest_csv_path:
                potential_paths.append(newest_csv_path)
        
        # Final Verification
        def read_csv_data(paths):
            """
            Synchronous helper to check paths and read the first valid CSV file found.
            """
            for path in paths:
                if os.path.exists(path):
                    try:
                        with open(path, 'r', encoding='utf-8') as f:
                            reader = csv.DictReader(f)
                            return list(reader), path
                    except Exception as e:
                        print(f"DEBUG: Failed to read CSV at {path}: {e}")
            return [], None

        # BOLT ⚡: Offload blocking file I/O and CSV parsing to a separate thread
        # This prevents the event loop from being blocked by reading potentially large CSV files
        final_data, found_path = await asyncio.to_thread(read_csv_data, potential_paths)
        
        if is_success or final_data:
            return {
                "success": True,
                "row_count": len(final_data) if final_data else row_count,
                "data": final_data,
                "stdout": stdout_text,
                "stderr": stderr_text
            }
        
        return {
            "success": False,
            "error": "Script execution failed or produced no valid data output",
            "stdout": stdout_text,
            "stderr": stderr_text
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8006)
