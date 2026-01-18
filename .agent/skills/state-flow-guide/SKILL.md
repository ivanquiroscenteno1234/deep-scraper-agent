---
name: state-flow-guide
description: Visual guide to AgentState transitions and status values to help debug stuck or failed agent runs.
---
# Agent State Flow Guide

## When to Use
When debugging agent runs that get stuck, loop, or escalate unexpectedly. Understand the expected flow.

## State Machine

```
                    ┌─────────────────┐
                    │  START (None)   │
                    └────────┬────────┘
                             │ node_navigate_mcp
                             ▼
                    ┌─────────────────┐
               ┌────│   NAVIGATING    │◄──────────────┐
               │    └────────┬────────┘               │
               │             │ node_analyze_mcp       │
               │             ▼                        │
               │    ┌─────────────────┐               │
               │    │ Page Analysis   │               │
               │    │ - Disclaimer?   │               │
               │    │ - Search Page?  │               │
               │    │ - Results Grid? │               │
               │    └────────┬────────┘               │
               │             │                        │
               │    ┌────────┼────────┐               │
               │    ▼        ▼        ▼               │
               │ DISCLAIMER  SEARCH   GRID            │
               │    │        │        │               │
               │    │        │        ▼               │
               │    │        │   COLUMNS_CAPTURED     │
               │    │        │        │               │
               │    │        ▼        ▼               │
               │    │   SEARCH_EXECUTED               │
               │    │        │                        │
               │    ▼        ▼                        │
               │  CLICK_EXECUTED                      │
               │    │                                 │
               │    └─────────────────────────────────┘
               │              (loop back)
               │
               │    ┌─────────────────┐
               └───►│ NEEDS_HUMAN_REVIEW │  (circuit breaker)
                    └─────────────────┘
```

## Status Values

| Status | Set By | Meaning | Next Action |
|--------|--------|---------|-------------|
| `None` | Initial | Agent just started | Navigate to URL |
| `NAVIGATING` | `node_navigate_mcp` | Page loaded | Analyze page |
| `SEARCH_PAGE_FOUND` | `node_analyze_mcp` | Search form detected | Fill and search |
| `SEARCH_EXECUTED` | `node_perform_search_mcp` | Search submitted | Wait for grid/popup |
| `CLICK_EXECUTED` | `node_click_link_mcp` | Clicked disclaimer/link | Re-analyze page |
| `COLUMNS_CAPTURED` | `node_capture_columns_mcp` | Grid columns identified | Generate script |
| `SCRIPT_GENERATED` | `node_generate_script_mcp` | Script created | Test script |
| `SCRIPT_FAILED` | `node_test_script` | Script test failed | Fix script |
| `SCRIPT_FIXED` | `node_fix_script` | Script patched | Re-test |
| `NEEDS_HUMAN_REVIEW` | Circuit breaker | Too many attempts | Escalate |
| `FAILED` | Any node | Unrecoverable error | Stop |

## Key State Fields

```python
state = {
    # Navigation tracking
    "disclaimer_click_attempts": int,  # Resets on page change
    "clicked_selectors": List[str],    # Prevents re-clicking same element
    "attempt_count": int,              # Overall attempts
    
    # Script testing
    "script_test_attempts": int,       # Max 3 attempts
    "script_error": str,               # Last error message
    
    # Output
    "recorded_steps": List[Dict],      # Actions for script generation
    "column_mapping": Dict[str, str],  # Grid column → selector mapping
    "generated_script_path": str,      # Final script location
}
```

## Circuit Breakers

| Condition | Threshold | Action |
|-----------|-----------|--------|
| `disclaimer_click_attempts` | >= 5 | Escalate to human |
| `script_test_attempts` | >= 3 | Stop fixing, escalate |
| `attempt_count` | >= 10 | Hard stop |
| Same selector clicked 3x | N/A | Try alternative selectors |

## Common Stuck States

### Stuck at NAVIGATING
**Cause:** Page keeps being classified as disclaimer/portal
**Debug:**
```python
# Check in logs
[Analyze] INFO: Decision: Search=False, Grid=False, Disclaimer=True
```
**Fix:** Check `clean_html_for_llm` - hidden modal may still be in HTML

### Stuck at CLICK_EXECUTED
**Cause:** Click doesn't change page state
**Debug:** Check `clicked_selectors` for repeats
**Fix:** Add selector to alternatives list in `interaction.py`

### Stuck at SCRIPT_FAILED
**Cause:** Generated script has wrong selectors
**Debug:** Check `script_error` for timeout details
**Fix:** Review `recorded_steps` and `discovered_grid_selectors`

## Debugging Commands

```python
# Print current state for debugging
def debug_state(state: AgentState):
    print(f"Status: {state.get('status')}")
    print(f"Clicks: {state.get('disclaimer_click_attempts', 0)}")
    print(f"Clicked: {state.get('clicked_selectors', [])}")
    print(f"Steps: {len(state.get('recorded_steps', []))}")
    print(f"Script attempts: {state.get('script_test_attempts', 0)}")
```
