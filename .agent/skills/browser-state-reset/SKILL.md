---
name: browser-state-reset
description: Ensures the Discovery Agent always starts with a fresh browser context (no cookies/cache) to properly record all navigation steps including disclaimers.
---
# Browser State Reset for Discovery Agent

## Critical Rule

> [!CAUTION]
> The **Discovery Agent MUST start with a fresh browser context** (no cookies, no localStorage, no cache) before recording navigation steps. Failure to do so causes generated scripts to miss disclaimer/acceptance popups.

## Why This Matters

County clerk websites (Landmark Web, AcclaimWeb, etc.) show disclaimer popups **only on first visit**. If the browser has cached cookies from a previous session:
1. The disclaimer is **not shown** during agent recording
2. The generated script is **missing** the disclaimer acceptance step
3. When the script runs with a fresh browser, it **fails** because it can't handle the unexpected popup

## Implementation

### How Fresh Context Works

Playwright's `browser.newContext()` creates **isolated, incognito-like sessions by default**. This means:
- Each new browser context has NO cookies, localStorage, or cache
- Closing the browser and launching a new one = fresh session

### In `navigation.py` - `node_navigate_mcp()`

On `attempt_count == 0` (first navigation of each agent run):

```python
# Step 1: Close any existing browser to force fresh context
await temp_client.close()  # Calls playwright_close

# Step 2: Reset adapter state for clean connection  
await reset_mcp_browser()
```

That's it! The next time the MCP server opens a browser, it will be a completely fresh context.

## Verification Checklist

When debugging script failures related to disclaimers:

- [ ] Check if `reset_mcp_browser()` is called before navigation
- [ ] Verify logs show: `First run - resetting browser for fresh state`
- [ ] Compare generated script to working reference in `output/generated_scripts/flagler_working.py`
- [ ] Ensure the script has disclaimer acceptance step **before** filling search form

## Related Skills

- `scraper-debugger` - For analyzing stuck agent runs
- `mcp-helper` - For MCP connection issues
- `working-script-reference` - Reference scripts with correct disclaimer handling
