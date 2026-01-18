---
name: selector-validator
description: Validates CSS selectors exist in actual DOM before using them, preventing hallucinated selectors that cause timeouts.
---
# Selector Validator

## When to Use
Before trusting any selector from LLM output or recorded steps. Prevents timeout errors from non-existent selectors.

## Validation Methods

### 1. Via MCP (During Agent Run)
```python
async def validate_selector(browser, selector: str) -> bool:
    """Check if selector exists in current page."""
    try:
        result = await browser.evaluate(f"""
            (() => {{
                const el = document.querySelector('{selector}');
                return {{
                    exists: !!el,
                    visible: el ? el.offsetParent !== null : false,
                    tagName: el ? el.tagName : null
                }};
            }})()
        """)
        return result.get('exists', False)
    except:
        return False
```

### 2. Via Playwright (In Generated Scripts)
```python
def safe_wait_for_selector(page, selector: str, timeout: int = 5000) -> bool:
    """Wait for selector with graceful fallback."""
    try:
        page.wait_for_selector(selector, timeout=timeout)
        return True
    except:
        return False
```

### 3. Multiple Selector Fallback
```python
def wait_for_any_selector(page, selectors: list, timeout: int = 8000) -> str:
    """Try multiple selectors, return first match."""
    for selector in selectors:
        try:
            el = page.locator(selector)
            el.wait_for(state="visible", timeout=timeout // len(selectors))
            return selector  # Found it
        except:
            continue
    return None  # None matched
```

## Common Hallucinated Selectors

These are often invented by LLMs but rarely exist:

| Hallucinated | Real Pattern |
|--------------|--------------|
| `#ctl00_ContentPlaceHolder1_GridView1` | Use discovered ID patterns |
| `#MainContent_SearchResults` | Check actual page source |
| `.results-table` | Site-specific: `#RsltsGrid`, `#resultsTable` |
| `#btnSearch` | More likely: `#submit-Name`, `input[type='submit']` |

## Selector Discovery Patterns

Add these to `extraction.py` for better discovery:
```python
GRID_ID_PATTERNS = [
    (r'id=["\']([^"\']*(?:grid|table|results|list)[^"\']*)["\']', '#{id}'),
    (r'id=["\']itemPlaceholderContainer["\']', '#itemPlaceholderContainer'),
    (r'id=["\']RsltsGrid["\']', '#RsltsGrid'),
    (r'id=["\']resultsTable["\']', '#resultsTable'),
]

GRID_CLASS_PATTERNS = [
    (r'class=["\'][^"\']*\bt-grid\b[^"\']*["\']', '.t-grid'),
    (r'class=["\'][^"\']*\bdataTable\b[^"\']*["\']', 'table.dataTable'),
]
```

## Validation Before Recording

In `node_capture_columns_mcp`, validate before saving:
```python
# Validate discovered selector exists
if discovered_selectors:
    for selector in discovered_selectors:
        exists = await validate_selector(browser, selector)
        if exists:
            log.info(f"Validated selector: {selector}")
        else:
            log.warning(f"Selector not found: {selector}")
            discovered_selectors.remove(selector)
```

## Integration with Script Template

The script template should include fallback patterns:
```python
# In generated script
grid_selectors = ["{grid_selector}", "#RsltsGrid", "#resultsTable", ".t-grid"]
grid_found = False
for selector in grid_selectors:
    if safe_wait_for_selector(page, selector):
        grid_found = True
        break
```
