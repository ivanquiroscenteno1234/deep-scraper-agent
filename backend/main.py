# Deep Scraper Agent Backend (Force reload at 21:50 - Navigation Portal Fix)
import os
import sys
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
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

# Enable CORS for React frontend (Vite defaults to 5173, may use 5174 if 5173 busy)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ScrapeRequest(BaseModel):
    url: str
    search_query: str
    start_date: str = "01/01/1980"
    end_date: str = datetime.now().strftime("%m/%d/%Y")

class ExecuteRequest(BaseModel):
    script_path: str
    search_query: str
    start_date: str = "01/01/1980"
    end_date: str = datetime.now().strftime("%m/%d/%Y")

class ParallelExecuteRequest(BaseModel):
    script_paths: list[str]
    search_query: str
    start_date: str = "01/01/1980"
    end_date: str = datetime.now().strftime("%m/%d/%Y")
    max_concurrent: int = 5  # Concurrency limit

# In-memory store for agent status
runs = {}
parallel_runs = {}  # Store for parallel execution status

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/api/scripts")
async def list_scripts():
    """
    Return a list of available generated scripts.
    """
    scripts_dir = os.path.join(os.path.dirname(__file__), "output", "generated_scripts")
    scripts = []
    
    if os.path.exists(scripts_dir):
        for filename in os.listdir(scripts_dir):
            if filename.endswith(".py"):
                filepath = os.path.join(scripts_dir, filename)
                modified_time = datetime.fromtimestamp(os.path.getmtime(filepath)).isoformat()
                scripts.append({
                    "name": filename,
                    "path": filepath,
                    "modified": modified_time
                })
    
    # Sort by modified date, newest first
    scripts.sort(key=lambda x: x["modified"], reverse=True)
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
            target_url=run_data["url"],
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
    if not os.path.exists(request.script_path):
        return {"error": "Script file not found"}

    print(f"DEBUG: Executing script {request.script_path}")
    print(f"DEBUG: Query='{request.search_query}', Start='{request.start_date}', End='{request.end_date}'")
    
    import subprocess
    import re
    
    try:
        # Run the script: python script.py "QUERY" "START" "END"
        result = subprocess.run(
            [sys.executable, request.script_path, request.search_query, request.start_date, request.end_date],
            capture_output=True,
            text=True,
            timeout=180,
            cwd=os.path.dirname(__file__)  # Run from backend dir so relative paths work
        )
        
        # 1. Flexible Success Detection
        stdout_upper = result.stdout.upper()
        is_success = "SUCCESS" in stdout_upper or "[SUCCESS]" in stdout_upper or "[OK]" in stdout_upper
        
        # 2. Extract Row Count
        row_count = 0
        row_match = re.search(r'(?:Extracted|Found|Saved|Saving)\s+(\d+)\s+(?:rows|records|items)', result.stdout, re.IGNORECASE)
        if row_match:
            row_count = int(row_match.group(1))
            
        # 3. CSV File Resolution
        csv_file = None
        # Try finding path in stdout - support multiple formats
        csv_path_match = re.search(r'(?:saved to|CSV saved:|to|Saved)\s+([^\s]+\.csv)', result.stdout, re.IGNORECASE)
        if csv_path_match:
            csv_file = csv_path_match.group(1).strip()
            
        # Search for the CSV in standardized output/data/ folder
        backend_dir = os.path.dirname(__file__)
        output_data_dir = os.path.join(backend_dir, "output", "data")
        potential_paths = []
        
        if csv_file:
            potential_paths.append(csv_file)  # Absolute path from stdout
            potential_paths.append(os.path.join(output_data_dir, os.path.basename(csv_file)))
        
        # If no csv_file found in stdout, find most recent CSV in output/data/
        if not csv_file and os.path.isdir(output_data_dir):
            csv_files = [f for f in os.listdir(output_data_dir) if f.endswith('.csv')]
            if csv_files:
                csv_files.sort(key=lambda x: os.path.getmtime(os.path.join(output_data_dir, x)), reverse=True)
                potential_paths.append(os.path.join(output_data_dir, csv_files[0]))
        
        # Final Verification
        final_data = []
        found_path = None
        for path in potential_paths:
            if os.path.exists(path):
                found_path = path
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        reader = csv.DictReader(f)
                        final_data = list(reader)
                        break
                except Exception as e:
                    print(f"DEBUG: Failed to read CSV at {path}: {e}")
        
        if is_success or final_data:
            return {
                "success": True,
                "row_count": len(final_data) if final_data else row_count,
                "data": final_data,
                "stdout": result.stdout,
                "stderr": result.stderr
            }
        
        return {
            "success": False,
            "error": "Script execution failed or produced no valid data output",
            "stdout": result.stdout,
            "stderr": result.stderr
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}

# ============================================================================
# PARALLEL SCRIPT EXECUTION
# ============================================================================

@app.post("/api/execute-parallel")
async def start_parallel_execution(request: ParallelExecuteRequest):
    """
    Start parallel execution of multiple scripts.
    Returns a run_id to connect via WebSocket for progress updates.
    """
    run_id = str(uuid.uuid4())
    parallel_runs[run_id] = {
        "status": "starting",
        "scripts": request.script_paths,
        "query": request.search_query,
        "start_date": request.start_date,
        "end_date": request.end_date,
        "max_concurrent": request.max_concurrent,
        "results": {},
        "startTime": datetime.now().isoformat()
    }
    return {"run_id": run_id, "total_scripts": len(request.script_paths)}


@app.websocket("/ws/parallel/{run_id}")
async def parallel_execution_ws(websocket: WebSocket, run_id: str):
    """
    WebSocket for parallel script execution with real-time progress.
    """
    await websocket.accept()
    
    if run_id not in parallel_runs:
        await websocket.send_json({"error": "Run not found"})
        await websocket.close()
        return

    run_data = parallel_runs[run_id]
    scripts = run_data["scripts"]
    query = run_data["query"]
    start_date = run_data["start_date"]
    end_date = run_data["end_date"]
    max_concurrent = run_data["max_concurrent"]
    
    # Semaphore to limit concurrent executions (0 = no limit = run all at once)
    effective_limit = max_concurrent if max_concurrent > 0 else len(scripts)
    semaphore = asyncio.Semaphore(effective_limit)
    
    async def execute_single_script(script_path: str) -> dict:
        """Execute a single script with semaphore control."""
        async with semaphore:
            script_name = os.path.basename(script_path)
            
            # Notify: starting
            try:
                await websocket.send_json({
                    "type": "script_start",
                    "script": script_name,
                    "path": script_path
                })
            except:
                pass
            
            if not os.path.exists(script_path):
                return {
                    "script": script_name,
                    "path": script_path,
                    "success": False,
                    "error": "Script file not found",
                    "row_count": 0
                }
            
            try:
                # Use asyncio subprocess for non-blocking execution
                proc = await asyncio.create_subprocess_exec(
                    sys.executable, script_path, query, start_date, end_date,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=os.path.dirname(__file__)
                )
                
                try:
                    stdout_bytes, stderr_bytes = await asyncio.wait_for(
                        proc.communicate(),
                        timeout=180
                    )
                except asyncio.TimeoutError:
                    proc.kill()
                    return {
                        "script": script_name,
                        "path": script_path,
                        "success": False,
                        "error": "Script execution timed out (180s)",
                        "row_count": 0
                    }
                
                stdout = stdout_bytes.decode('utf-8', errors='replace')
                stderr = stderr_bytes.decode('utf-8', errors='replace')
                
                # Success detection
                stdout_upper = stdout.upper()
                is_success = "SUCCESS" in stdout_upper or "[OK]" in stdout_upper
                
                # Extract row count
                import re
                row_count = 0
                row_match = re.search(r'(?:Extracted|Found|Saved|Saving)\s+(\d+)\s+(?:rows|records|items)', stdout, re.IGNORECASE)
                if row_match:
                    row_count = int(row_match.group(1))
                
                result = {
                    "script": script_name,
                    "path": script_path,
                    "success": is_success or row_count > 0,
                    "row_count": row_count,
                    "stdout": stdout[-500:] if len(stdout) > 500 else stdout,  # Last 500 chars
                    "stderr": stderr[-200:] if len(stderr) > 200 else stderr
                }
                
                # Notify: completed
                try:
                    await websocket.send_json({
                        "type": "script_complete",
                        **result
                    })
                except:
                    pass
                
                return result
                
            except Exception as e:
                return {
                    "script": script_name,
                    "path": script_path,
                    "success": False,
                    "error": str(e),
                    "row_count": 0
                }
    
    try:
        # Send initial status
        await websocket.send_json({
            "type": "parallel_start",
            "total_scripts": len(scripts),
            "max_concurrent": max_concurrent
        })
        
        # Execute all scripts in parallel with gather
        results = await asyncio.gather(
            *[execute_single_script(script) for script in scripts],
            return_exceptions=True
        )
        
        # Process results
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                final_results.append({
                    "script": os.path.basename(scripts[i]),
                    "path": scripts[i],
                    "success": False,
                    "error": str(result),
                    "row_count": 0
                })
            else:
                final_results.append(result)
        
        # Calculate totals
        total_success = sum(1 for r in final_results if r.get("success"))
        total_rows = sum(r.get("row_count", 0) for r in final_results)
        
        # Store results
        run_data["results"] = final_results
        run_data["status"] = "completed"
        
        # Send final summary
        await websocket.send_json({
            "type": "parallel_complete",
            "total_scripts": len(scripts),
            "successful": total_success,
            "failed": len(scripts) - total_success,
            "total_rows": total_rows,
            "results": final_results
        })
        
    except WebSocketDisconnect:
        print(f"WebSocket disconnected for parallel run {run_id}")
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "error": str(e)})
        except:
            pass
    finally:
        try:
            await websocket.close()
        except:
            pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8006)

