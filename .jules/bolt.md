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

## 2025-01-28 - Regex vs String Methods

**Learning:** In Python, `str.upper()` combined with `in` operator is approximately 20x faster than `re.search(..., re.IGNORECASE)` for large strings (1MB+), because `str.upper()` is highly optimized in C. Also, Python's internal regex cache negates the benefit of manually pre-compiling regexes for low-frequency calls.

**Action:** For simple case-insensitive substring checks, prefer `x.upper() in y.upper()` over regex. Do not waste time pre-compiling regexes unless they are used in tight loops or bypass the internal cache limit.

## 2025-01-28 - Avoid Unnecessary Reflows

**Learning:** `document.body.innerText` forces the browser to calculate layout (Reflow), which is computationally expensive. `document.documentElement.outerHTML` does not. Fetching `innerText` when only HTML is needed wastes CPU (browser) and Network bandwidth.

**Action:** Implemented `get_html()` in `MCPBrowserAdapter` to fetch only `outerHTML`. Replaced `get_snapshot()` with `get_html()` in extraction and navigation nodes where text content was unused.
