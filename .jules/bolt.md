## 2024-07-25 - Initializing Bolt's Journal

**Learning:** Set up the journal file. I will use this to record critical learnings about the codebase's performance characteristics.

**Action:** Begin profiling the application to identify my first optimization target.

## 2024-07-25 - Blocking IO in Async Endpoints

**Learning:** Found `subprocess.run` used synchronously inside an `async def` FastAPI endpoint (`execute_script`). This blocks the entire event loop for the duration of the script execution (up to 180s), causing the server to become unresponsive to other requests (like health checks or WebSocket pings).

**Action:** Replacing `subprocess.run` with `asyncio.create_subprocess_exec` allows the event loop to continue processing other tasks while waiting for the subprocess to complete. This is a critical pattern for async Python servers.
