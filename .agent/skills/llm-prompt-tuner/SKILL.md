---
name: llm-prompt-tuner
description: Best practices for crafting and debugging LLM prompts used in navigation.py, extraction.py, and script generation.
---
# LLM Prompt Engineering Guide

## When to Use
When the agent misclassifies pages, hallucinates selectors, or makes wrong decisions. The root cause is often the LLM prompt.

## Key Prompt Locations

| File | Function | Prompt Purpose |
|------|----------|----------------|
| `navigation.py` | `node_analyze_mcp` | Classify page type (search, disclaimer, grid) |
| `extraction.py` | `node_capture_columns_mcp` | Identify grid columns and selectors |
| `script_gen.py` | `node_generate_script_mcp` | Generate Playwright script |
| `script_test.py` | `node_fix_script` | Fix failing scripts |

## Prompt Structure Best Practices

### 1. Priority Rules
Always list classification rules in priority order:
```
### 1. CAPTCHA DETECTED (check first)
### 2. LOGIN REQUIRED
### 3. RESULTS GRID (data table visible)
### 4. SEARCH PAGE (visible input fields)
### 5. DISCLAIMER / NAVIGATION PORTAL
```

### 2. Explicit Constraints
Prevent hallucination with explicit rules:
```
## CRITICAL: Use ONLY selectors that EXIST in the HTML below.
Do NOT invent selectors like #GridView1 if they don't appear in the HTML.
```

### 3. Discovered Context
Pass discovered selectors to reduce hallucination:
```python
discovered_context = ""
if discovered_selectors:
    discovered_context = f"""
## DISCOVERED SELECTORS (USE THESE):
{json.dumps(discovered_selectors, indent=2)}
"""
```

### 4. Memory Context
For multi-step flows, include previous attempts:
```python
if click_attempts > 0:
    memory_context = f"""
## PREVIOUS ATTEMPTS (DO NOT REPEAT):
Clicked: {clicked_selectors}
Try alternative selectors not in this list.
"""
```

## Common Prompt Failures

| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| Hallucinates `#ctl00_GridView1` | No discovered selectors provided | Add grid discovery before LLM call |
| Always says "Disclaimer" | Hidden modal in HTML | Filter hidden elements in `clean_html_for_llm` |
| Wrong column names | HTML too large/truncated | Increase `max_length` or focus on grid area only |
| Clicks same button repeatedly | No memory context | Add `clicked_selectors` to prompt |

## Debugging Prompts

Add logging to see what the LLM receives:
```python
log.debug(f"LLM Prompt:\n{prompt[:500]}...")
log.debug(f"LLM Response: {response}")
```

Check if HTML is properly cleaned:
```python
log.info(f"Raw HTML: {len(raw_html)} chars, Cleaned: {len(cleaned_html)} chars")
```

## Structured Output
Always use Pydantic models for reliable parsing:
```python
class NavigationDecision(BaseModel):
    is_search_page: bool
    is_disclaimer: bool
    is_results_grid: bool
    accept_button_ref: str = ""
    reasoning: str

structured_llm = llm.with_structured_output(NavigationDecision)
```
