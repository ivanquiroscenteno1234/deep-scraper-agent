---
name: scraper-debugger
description: Debugs stuck or failed scraper runs by analyzing AgentState logs, status transitions, and node execution flow.
---
# Scraper Agent Debugger

## When to Use
- Agent escalates to `NEEDS_HUMAN_REVIEW`
- Status stuck at `NAVIGATING` or `CLICK_EXECUTED` for multiple attempts
- `disclaimer_click_attempts >= 5` (circuit breaker triggered)
- Script generation/testing fails repeatedly

## Key State Fields to Inspect

```python
state = {
    "status": str,                    # Current workflow state
    "disclaimer_click_attempts": int, # Click loop counter
    "clicked_selectors": List[str],   # Selectors already tried
    "attempt_count": int,             # Overall attempt counter
    "script_test_attempts": int,      # Script fix attempts
    "script_error": str,              # Last test error message
    "logs": List[str],                # Execution log trail
}
```

## Diagnostic Checklist

### 1. Loop Detection
Check `clicked_selectors` for repeating patterns:
```python
# In interaction.py, click_link tracks this:
clicked_selectors = state.get("clicked_selectors", [])
```
**Fix:** If same selector clicked 3+ times, the LLM is hallucinating. Check HTML snapshot quality.

### 2. Page Classification Errors
The `node_analyze_mcp` in `navigation.py` classifies pages. Check logs for:
```
[Analyze] INFO: Decision: Search=False, Grid=False, Disclaimer=True
```
**Fix:** If classification is wrong, review the LLM prompt or `clean_html_for_llm` filtering.

### 3. Hidden Element Issues
Agent may try clicking hidden elements. Check in `helpers.py`:
```python
clean_html_for_llm()  # Should filter elements with class="modal hide", display:none
```

### 4. Script Generation Failures
In `script_test.py`, check:
- Does generated script have correct selectors from `recorded_steps`?
- Are popup handling patterns correct for the site type?

### 5. Circuit Breakers
Located in `interaction.py`:
- `disclaimer_click_attempts >= 5` → Escalates to human review
- Check logs for: `Circuit Breaker: Too many disclaimer click attempts`

## Common Fixes

| Symptom | Likely Cause | Fix Location |
|---------|--------------|--------------|
| Stuck on home page | Hidden modal in DOM | `helpers.py` - add class to hidden filter |
| Wrong page classification | Bad LLM prompt | `navigation.py` - refine classification rules |
| Script timeout on grid | Grid selector hallucinated | `extraction.py` - improve grid discovery |
| Loop on same selector | Selector not updating state | `interaction.py` - track more selectors |
