---
name: script-auditor
description: Audits generated Playwright scripts for best practices, error handling, and project-specific requirements.
---
# Playwright Script Auditor

## When to Use
Review generated scripts in `backend/output/generated_scripts/` before deployment or when scripts fail during testing.

## Audit Checklist

### 1. Navigation & Waits
```python
# ✅ GOOD: Explicit wait after navigation
page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=45000)

# ❌ BAD: No wait specified
page.goto(TARGET_URL)
```

### 2. Post-Click Waits (CRITICAL)
Every `.click()` must be followed by a wait:
```python
# ✅ GOOD
element.click()
page.wait_for_load_state("networkidle", timeout=5000)

# ❌ BAD: No wait after click
button.click()
# next action immediately...
```

### 3. Grid Detection
Must use discovered selectors from `recorded_steps`, not hallucinated ones:
```python
# ✅ GOOD: Uses selector from discovery
grid_selector = "#resultsTable"  # From recorded_steps
page.wait_for_selector(grid_selector, state="visible", timeout=15000)

# ❌ BAD: Made-up selector
page.wait_for_selector("#ctl00_GridView1")  # Hallucinated
```

### 4. Popup Handling Pattern
```python
# ✅ GOOD: Try multiple selectors with fallback
popup_selectors = ["#frmSchTarget input[type='submit']", "input[value='Done']"]
for popup_sel in popup_selectors:
    try:
        popup_btn = page.locator(popup_sel)
        if popup_btn.is_visible(timeout=2000):
            popup_btn.first.click()
            break
    except:
        continue
```

### 5. Column Extraction
Must use `FIRST_DATA_COLUMN` index correctly:
```python
# ✅ GOOD: Respects column offset
FIRST_DATA_COLUMN = 1  # Skip row# column
for i, col_name in enumerate(column_names):
    cell_index = FIRST_DATA_COLUMN + i
    row_data[col_name] = cells[cell_index].text_content()
```

### 6. Error Handling
```python
# ✅ GOOD: Screenshot on failure
except Exception as e:
    print(f"CRITICAL ERROR: {e}")
    page.screenshot(path=f"error_state_{TIMESTAMP}.png")
```

### 7. Timeouts on steps
Must use a max timeout of 5 seconds always on all steps, and a minimum timeout of 2 second, never use more than 5 seconds and never do actions inmediatly without a timeout:
```python
# ✅ GOOD: Uses timeouts of 5 seconds max
page.wait_for_selector(grid_selector, state="visible", timeout=5000)

# ❌ BAD: timeouts of more than 5 seconds
page.wait_for_selector(grid_selector, state="visible", timeout=6000)
page.wait_for_selector(grid_selector, state="visible", timeout=7000)
page.wait_for_selector(grid_selector, state="visible", timeout=10000)
```

## Reference Scripts
Compare against working scripts in `backend/output/generated_scripts/`:
- Check patterns for similar site types (AcclaimWeb, Landmark Web, etc.)
- Verify popup selector patterns match site architecture

## Common Issues

| Issue | Symptom | Fix |
|-------|---------|-----|
| Timeout on grid | Script hangs after search | Add fallback grid selectors |
| Missing data columns | CSV has empty columns | Check FIRST_DATA_COLUMN value |
| Popup not handled | Stuck after search button | Add popup selector patterns |
