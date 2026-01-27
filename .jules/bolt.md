## 2024-07-25 - Initializing Bolt's Journal

**Learning:** Set up the journal file. I will use this to record critical learnings about the codebase's performance characteristics.

**Action:** Begin profiling the application to identify my first optimization target.

## 2024-07-25 - Blocking IO in Async Endpoints

**Learning:** Found `subprocess.run` used synchronously inside an `async def` FastAPI endpoint (`execute_script`). This blocks the entire event loop for the duration of the script execution (up to 180s), causing the server to become unresponsive to other requests (like health checks or WebSocket pings).

**Action:** Replacing `subprocess.run` with `asyncio.create_subprocess_exec` allows the event loop to continue processing other tasks while waiting for the subprocess to complete. This is a critical pattern for async Python servers.

## 2024-05-23 - Browser-Side DOM Checking

**Learning:** Replacing server-side HTML polling (fetching >100KB strings) with browser-side JS execution (`!!document.querySelector(...)`) reduces network overhead by ~99% and CPU usage significantly.

**Action:** Look for other places where `get_snapshot()` or `get_html()` is used just to check for the existence of an element, and replace with `evaluate()`.

## 2024-05-24 - Atomic Page Snapshots

**Learning:** Fetching HTML and Text separately (even with `asyncio.gather`) requires two network roundtrips to the MCP server. This is inefficient for large pages and can lead to inconsistent state if the page updates between calls.

**Action:** Implemented `get_full_page_content()` using `JSON.stringify` to fetch both DOM and Text in a single JS execution. This reduces MCP calls by 50% for snapshots and ensures atomic data capture.

## 2025-02-18 - Browser-Side HTML Cleaning

**Learning:** Fetching full HTML snapshots (~2MB) and cleaning them with Python regex consumes significant bandwidth and CPU.

**Action:** Implemented `get_cleaned_html()` which uses a browser-side JS script to clone the DOM and remove scripts, styles, and hidden elements *before* transfer. This reduces payload size by >90% for LLM analysis steps.

## 2025-02-18 - Missing Core Dependencies

**Learning:** The `requirements.txt` file is missing `mcp` and `langgraph`, which are core dependencies. Additionally, `deep_scraper/graph/nodes/config.py` enforces `GOOGLE_API_KEY` presence at import time.

**Action:** Always install `mcp` manually (`pip install mcp`) and set `GOOGLE_API_KEY=dummy` before running tests.
