---
name: mcp-helper
description: Troubleshoots connection issues between the FastAPI backend and the Chrome DevTools MCP server used for browser automation.
---
# MCP Connection Troubleshooting

## When to Use
Triggered when encountering: "MCP server not running", "Connection refused", browser automation failures, or MCP-related errors.

## Architecture Overview
```
FastAPI Backend → MCPBrowserAdapter → PlaywrightMCPClient → Chrome DevTools MCP Server
```

**Key Files:**
- `deep_scraper/core/mcp_adapter.py` - Browser adapter with `MCPBrowserAdapter` class
- `deep_scraper/core/mcp_client.py` - Low-level MCP client with `PlaywrightMCPClient`

## Diagnostic Steps

### 1. Verify MCP Server Status
The MCP server must be running before starting the backend.

### 2. Check Client Singleton
```python
# In mcp_adapter.py
from .mcp_client import PlaywrightMCPClient, get_mcp_client, reset_mcp_client
```
If connection fails, call `reset_mcp_client()` to clear stale state.

### 3. Verify Browser Launch
Check `MCPBrowserAdapter.launch()` returns True:
```python
browser = await get_mcp_adapter()
success = await browser.launch()
```

### 4. Common Fixes
- **Stale connection**: Call `reset_mcp_adapter()` then retry
- **Port conflict**: Ensure only one MCP server instance is running
- **Browser crash**: Check for zombie browser processes

## Related Functions
- `get_mcp_adapter()` - Get or create adapter singleton
- `reset_mcp_adapter()` - Reset adapter state
- `is_mcp_available()` - Check server availability
