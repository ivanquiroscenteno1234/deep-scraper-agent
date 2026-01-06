"""
Script template for LLM-generated Playwright scrapers.

This template is much simpler - it emphasizes using the RECORDED STEPS
rather than generic fallback patterns.
"""

SCRIPT_TEMPLATE = '''
Generate a Python Playwright script for extracting data from a county clerk website.

## TARGET
- Site: {site_name}
- URL: {target_url}

## RECORDED STEPS (USE THESE EXACT SELECTORS)
These are the ACTUAL selectors that worked during the recording session.
YOU MUST use these exact selectors - do not invent your own:

{recorded_steps_json}

## GRID INFORMATION
- Primary grid selector: {grid_selector}
- Row selector: {row_selector}
- First DATA column index: {first_data_column_index} (skip columns before this index - they are row numbers or icons)

## COLUMNS TO EXTRACT (VISIBLE COLUMNS ONLY)
These are the VISIBLE data columns. Hidden columns and icon columns have been filtered out.
{columns_json}

## CRITICAL RULES (FOLLOW STRICTLY)

1. **USE RECORDED SELECTORS ONLY**: The `recorded_steps` contain the exact CSS selectors that worked.
   Do NOT use generic selectors like `input[value='Done']` - they match multiple elements.

2. **COLUMN EXTRACTION - CRITICAL**:
   - Start extracting from column index {first_data_column_index} (skip row#, icons, etc.)
   - The columns list above contains ONLY the visible data columns
   - Match cells[{first_data_column_index}] to columns[0], cells[{first_data_column_index}+1] to columns[1], etc.
   - Example: if first_data_column_index=3 and columns=["Status","Name","Date"], then:
     - cells[3].text_content() → "Status"
     - cells[4].text_content() → "Name"
     - cells[5].text_content() → "Date"
   
3. **Handle Intermediate States (Popups/Lists)**: 
   - After clicking search, many sites show a "Name Selection" popup or an intermediate list.
   - **ROBUST WAIT**: You MUST wait for EITHER the results grid OR the popup container simultaneously using a comma-separated selector:
     ```python
     # Wait for EITHER the grid OR the popup container
     print("[STEP 6] Waiting for results OR popup...")
     try:
         page.wait_for_selector("{grid_selector}, #NamesWin, #frmSchTarget, .t-window", timeout=20000)
     except:
         pass
     ```
   - **PRIORITIZE RECORDED SELECTORS**: If `recorded_steps` contains a click on a popup button (e.g., `#NamesWin`, `#frmSchTarget`), you **MUST** use that exact selector.

4. **Date Parameterization**:
   - If `recorded_steps` contains `{{START_DATE}}` or `{{END_DATE}}` in the `value` field:
     - You MUST use the `start_date` and `end_date` variables (from `sys.argv`) in those `page.fill()` calls.

5. **Fresh Browser Context**: Always create a fresh context with no storage state.

6. **Wait for Grid**: After handling any popups, wait for the grid using the recorded `grid_selector`.

7. **Extract from tbody only**: Use `tbody tr` to skip header rows.

8. **Output CSV**: Save results to CSV in the `output/data/` folder relative to the script's directory parent (i.e., `../output/data/` from script location or use absolute path based on `__file__`).

## SCRIPT STRUCTURE

```python
import sys
import os
import csv
import datetime
from playwright.sync_api import sync_playwright

SITE_NAME = "{site_name}"
TARGET_URL = "{target_url}"
TIMESTAMP = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
FIRST_DATA_COLUMN = {first_data_column_index}  # Skip row#, icon columns

def main():
    # USAGE: python script.py "SEARCH_TERM" "START_DATE" "END_DATE"
    search_term = sys.argv[1] if len(sys.argv) > 1 else "SMITH"
    start_date = sys.argv[2] if len(sys.argv) > 2 else "01/01/1980"
    end_date = sys.argv[3] if len(sys.argv) > 3 else datetime.datetime.now().strftime('%m/%d/%Y')
    
    print(f"[INFO] Starting scraper for '{{search_term}}' (Range: {{start_date}} - {{end_date}})")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            viewport={{'width': 1280, 'height': 800}},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/119.0.0.0"
        )
        page = context.new_page()
        
        try:
            # STEP 1: Navigate
            print("[STEP 1] Navigating to URL...")
            page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=45000)
            
            # FOLLOW ALL RECORDED STEPS IN ORDER...
            # Use the EXACT selectors from recorded_steps.
            # Replace {{SEARCH_TERM}}, {{START_DATE}}, {{END_DATE}} with main() variables.
            
            # ROBUST WAIT AFTER SEARCH:
            print("[STEP 6] Waiting for results OR popup...")
            try:
                page.wait_for_selector("{grid_selector}, #NamesWin, #frmSchTarget, .t-window", timeout=20000)
            except:
                pass

            # HANDLE POPUPS IF RECORDED (Use recorded selectors)
            # ...

            # WAIT FOR GRID (RECORDED GRID SELECTOR)
            print("[STEP 7] Ensuring grid is visible...")
            page.wait_for_selector("{grid_selector}", timeout=15000)
            
            # EXTRACT DATA - START FROM FIRST_DATA_COLUMN
            print("[STEP 8] Extracting rows...")
            rows = page.locator("{row_selector}").all()
            data = []
            for row in rows:
                cells = row.locator("td").all()
                if len(cells) > FIRST_DATA_COLUMN:
                    row_data = {{}}
                    # Extract starting from FIRST_DATA_COLUMN
                    # columns[0] = cells[FIRST_DATA_COLUMN], columns[1] = cells[FIRST_DATA_COLUMN+1], etc.
                    for i, col_name in enumerate({columns_json}):
                        cell_index = FIRST_DATA_COLUMN + i
                        if cell_index < len(cells):
                            row_data[col_name] = cells[cell_index].text_content().strip()
                    data.append(row_data)
            
            # STEP 9: Save to CSV in output/data/ folder
            script_dir = os.path.dirname(os.path.abspath(__file__))
            # Scripts are in output/generated_scripts/, data goes to output/data/
            output_dir = os.path.join(os.path.dirname(script_dir), "data")
            os.makedirs(output_dir, exist_ok=True)
            # Save CSV to output_dir...
            
            print(f"SUCCESS: Extracted {{len(data)}} rows")
            
        except Exception as e:
            print(f"FAILED: {{e}}")
        finally:
            browser.close()

if __name__ == "__main__":
    main()
```

## OUTPUT FORMAT
Return ONLY clean Python code. No markdown fences. No explanations.
'''


def build_script_prompt(
    site_name: str,
    target_url: str,
    recorded_steps: list,
    grid_selector: str,
    row_selector: str,
    columns: list,
    grid_html: str = "",
    first_data_column_index: int = 0
) -> str:
    """
    Build the prompt for script generation.
    
    Args:
        site_name: Name of the site (e.g., 'brevardclerk')
        target_url: Target URL to scrape
        recorded_steps: List of recorded step dicts
        grid_selector: CSS selector for the grid
        row_selector: CSS selector for data rows
        columns: List of column names (VISIBLE columns only)
        grid_html: Optional HTML of the grid for context
        first_data_column_index: Index of first DATA column (skip row#, icons before this)
        
    Returns:
        Complete prompt string for LLM
    """
    import json
    
    # Format recorded steps with emphasis on selectors
    steps_formatted = []
    for i, step in enumerate(recorded_steps, 1):
        step_info = {
            "step": i,
            "action": step.get("action"),
            "selector": step.get("selector"),
            "purpose": step.get("purpose", step.get("description", "")),
        }
        if step.get("value"):
            step_info["value"] = step.get("value")
        # Include first_data_column_index if this is a capture_grid step
        if step.get("action") == "capture_grid" and step.get("first_data_column_index") is not None:
            step_info["first_data_column_index"] = step.get("first_data_column_index")
        steps_formatted.append(step_info)
    
    prompt = SCRIPT_TEMPLATE.format(
        site_name=site_name,
        target_url=target_url,
        recorded_steps_json=json.dumps(steps_formatted, indent=2),
        grid_selector=grid_selector,
        row_selector=row_selector,
        columns_json=json.dumps(columns, indent=2),
        first_data_column_index=first_data_column_index
    )
    
    # Add grid HTML context if provided
    if grid_html:
        prompt += f"\n\n## GRID HTML CONTEXT (for understanding table structure - hidden columns already filtered)\n{grid_html[:20000]}"
    
    return prompt
