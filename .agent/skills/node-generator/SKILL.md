---
name: node-generator
description: Generates boilerplate code for new LangGraph nodes in the Deep Scraper Agent, following project conventions for state, logging, and MCP integration.
---
# LangGraph Node Generator

## When to Use
Use when adding a new workflow step (node) to the agent. All nodes live in `deep_scraper/graph/nodes/`.

## Node Template

```python
from typing import Any, Dict
from deep_scraper.core.state import AgentState
from deep_scraper.graph.nodes.config import (
    llm,
    get_mcp_browser,
    StructuredLogger,
)

async def node_example_mcp(state: AgentState) -> Dict[str, Any]:
    """
    Node description - what this step accomplishes.
    
    Records step: {"action": "example", "selector": "..."}
    """
    log = StructuredLogger("Example")
    
    try:
        browser = await get_mcp_browser()
        log.info("Performing action...")
        
        # Use browser methods
        await browser.click_element("#selector", "Description")
        
        log.success("Action completed")
        return {
            "status": "EXAMPLE_DONE",
            "logs": (state.get("logs") or []) + log.get_logs()
        }
    except Exception as e:
        log.error(f"Failed: {e}")
        return {
            "status": "FAILED",
            "logs": (state.get("logs") or []) + log.get_logs()
        }
```

## Conventions

### 1. State Fields (from `core/state.py`)
```python
class AgentState(TypedDict):
    target_url: str
    search_query: str
    start_date: str
    end_date: str
    status: str  # NAVIGATING, SEARCH_PAGE_FOUND, SEARCH_EXECUTED, etc.
    recorded_steps: List[Dict[str, Any]]
    column_mapping: Dict[str, str]
    generated_script_path: Optional[str]
    logs: List[str]
    disclaimer_click_attempts: int
    clicked_selectors: List[str]
```

### 2. Logging
Use `StructuredLogger` for consistent output:
```python
log = StructuredLogger("NodeName")
log.info("Message")      # [INFO] NodeName: Message
log.success("Message")   # ✅ [OK] NodeName: Message
log.warning("Message")   # ⚠️ [WARN] NodeName: Message
log.error("Message")     # ❌ [ERROR] NodeName: Message
```

### 3. Existing Nodes
Reference these for patterns:
- `navigation.py`: `node_navigate_mcp`, `node_analyze_mcp`
- `interaction.py`: `node_click_link_mcp`, `node_perform_search_mcp`
- `extraction.py`: `node_capture_columns_mcp`
- `script_gen.py`: `node_generate_script_mcp`
- `script_test.py`: `node_test_script`, `node_fix_script`

### 4. Registration
Add node to `graph/nodes/__init__.py` and wire into graph in `graph/builder.py`.
