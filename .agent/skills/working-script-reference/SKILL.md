---
name: working-script-reference
description: Documents patterns from working scripts in output/generated_scripts/ that agents should copy instead of inventing new ones.
---
# Working Script Reference

## When to Use
When generating or fixing scripts, reference these proven patterns from working scripts.

## Script Location
```
backend/output/generated_scripts/
```

## Proven Patterns

### 1. Browser Setup
```python
with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context(
        viewport={'width': 1280, 'height': 800},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/119.0.0.0"
    )
    page = context.new_page()
```

### 2. Navigation with Wait
```python
page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=45000)
```

### 3. Disclaimer Handling (AcclaimWeb)
```python
# Wait for disclaimer if present
try:
    disclaimer = page.locator("#disclaimer")
    if disclaimer.is_visible(timeout=3000):
        page.locator("#chkAccept").check()
        page.locator("#btnContinue").click()
        page.wait_for_load_state("networkidle", timeout=5000)
except:
    pass  # No disclaimer, continue
```

### 4. Landmark Web Flow (Flagler)
```python
# Step 1: Click Name Search icon (opens modal with disclaimer)
page.locator("a[title='Name Search']").click()
page.wait_for_load_state("domcontentloaded")

# Step 2: Accept disclaimer in modal
page.locator("#idAcceptYes").click()
page.wait_for_load_state("networkidle", timeout=5000)

# Step 3: Now fill the search form (in modal)
page.locator("#name-Name").fill(search_term)
```

### 5. Popup Handling (Name Selection)
```python
# After clicking search, wait for popup OR grid
try:
    page.wait_for_selector("#NamesWin, #RsltsGrid, #frmSchTarget", timeout=20000)
except:
    pass

# Handle popup with multiple selector fallback
popup_selectors = [
    "#frmSchTarget input[type='submit']",
    "input[value='Done']",
    "#NamesWin input[name='btnDone']"
]
for sel in popup_selectors:
    try:
        btn = page.locator(sel)
        if btn.is_visible(timeout=2000):
            btn.first.click()
            page.wait_for_load_state("networkidle")
            break
    except:
        continue
```

### 6. Grid Wait with Fallback
```python
grid_selectors = ["#RsltsGrid", "#resultsTable", ".t-grid", "#itemPlaceholderContainer"]
grid_found = False
for selector in grid_selectors:
    try:
        page.wait_for_selector(selector, state="visible", timeout=8000)
        grid_found = True
        print(f"Found grid: {selector}")
        break
    except:
        continue

if not grid_found:
    page.wait_for_timeout(3000)  # Last resort delay
```

### 7. Data Extraction
```python
FIRST_DATA_COLUMN = 1  # Skip row number column

rows = page.locator(f"{grid_selector} tbody tr").all()
data_results = []

for row in rows:
    cells = row.locator("td").all()
    if len(cells) > FIRST_DATA_COLUMN:
        row_data = {}
        for i, col_name in enumerate(column_names):
            cell_idx = FIRST_DATA_COLUMN + i
            if cell_idx < len(cells):
                text = cells[cell_idx].text_content().strip()
                row_data[col_name] = text
        if row_data.get("Name"):
            data_results.append(row_data)
```

### 8. CSV Output
```python
script_dir = os.path.dirname(os.path.abspath(__file__))
output_dir = os.path.join(os.path.dirname(script_dir), "data")
os.makedirs(output_dir, exist_ok=True)

safe_term = "".join([c if c.isalnum() else "_" for c in search_term])
filename = f"{SITE_NAME}_{safe_term}_{TIMESTAMP}.csv"
filepath = os.path.join(output_dir, filename)

with open(filepath, 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=column_names)
    writer.writeheader()
    writer.writerows(data_results)

print(f"SUCCESS: Extracted {len(data_results)} rows to {filepath}")
```

## Anti-Patterns to Avoid

| Bad | Good |
|-----|------|
| `page.goto(url)` without timeout | `page.goto(url, wait_until="domcontentloaded", timeout=45000)` |
| `button.click()` without wait after | `button.click(); page.wait_for_load_state("networkidle")` |
| Single grid selector | Multiple fallback selectors |
| `page.wait_for_timeout(5000)` alone | Combine with `wait_for_selector` |
