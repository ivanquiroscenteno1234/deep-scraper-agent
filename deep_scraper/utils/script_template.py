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
- Site Type: {site_type}

## RECORDED STEPS (USE THESE EXACT SELECTORS)
These are the ACTUAL selectors that worked during the recording session.
YOU MUST use these exact selectors - do not invent your own:

{recorded_steps_json}

## GRID INFORMATION
- Primary grid selector: {grid_selector}
- Row selector (relative to grid): {row_selector}
- Full row selector: {grid_selector} {row_selector}
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
         page.wait_for_selector("{grid_selector}, #NamesWin, #frmSchTarget, .t-window", timeout=5000)
     except:
         pass
     ```
   - **PRIORITIZE RECORDED SELECTORS**: If `recorded_steps` contains a click on a popup button (e.g., `#NamesWin`, `#frmSchTarget`), you **MUST** use that exact selector.
   - **CRITICAL TIMEOUT**: When checking if a popup button exists, ALWAYS use `is_visible(timeout=3000)`. Popups are dynamic and take time to appear. Never use `is_visible()` without a timeout.

4. **Field Fallbacks (use_js: true or date parameterization)**:
   - If `recorded_steps` contains `{{START_DATE}}` or `{{END_DATE}}` in the `value` field:
     - You MUST use the `start_date` and `end_date` variables (from `sys.argv`) in those fill calls.
   - **IMPORTANT**: If the step has `"use_js": true`, the field is a jQuery datepicker widget.
     - Do NOT use `page.fill()` - it will timeout or not trigger form validation!
     - Instead, use JavaScript to set the value and trigger events:
     ```python
     page.evaluate(f\"\"\"
         (() => {{
             const el = document.querySelector('{{selector}}');
             if (el) {{
                 el.value = '{{date_value}}';
                 el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                 el.dispatchEvent(new Event('input', {{ bubbles: true }}));
             }}
         }})()
     \"\"\")
     ```

5. **Fresh Browser Context**: Always create a fresh context with no storage state.

6. **Wait for Grid**: After handling any popups, wait for the grid using the recorded `grid_selector`.

7. **Extract from tbody only**: Use `tbody tr` to skip header rows.

8. **Output CSV**: Save results to CSV in the `output/data/` folder relative to the script's directory parent (i.e., `../output/data/` from script location or use absolute path based on `__file__`).

9. **PAGE LOAD WAITS AFTER CLICKS (CRITICAL)**:
   - After EVERY `.click()` action, you MUST wait for the page to load:
     ```python
     element.click()
     page.wait_for_load_state("domcontentloaded", timeout=5000)
     ```
   - For actions that trigger navigation or AJAX loads, use:
     ```python
     button.click()
     page.wait_for_load_state("networkidle", timeout=5000)
     ```
   - This prevents race conditions where the script runs faster than the page loads.
   - Apply this pattern to: disclaimer accepts, form submissions, popup closes, navigation clicks.
   - **NEVER** use `page.click(\"selector\")` directly. **ALWAYS** use `page.locator(\"selector\").click()` followed by a wait.

10. **ACCLAIMWEB SITES (brevardclerk, etc.) - ROW SELECTOR**:
    - For AcclaimWeb/Telerik grid sites (URL contains `AcclaimWeb`), the data rows are inside `.t-grid-content`
    - The row selector MUST be: `{grid_selector} .t-grid-content tbody tr`
    - Example: `#RsltsGrid .t-grid-content tbody tr`
    - Do NOT use just `tbody tr` - this will select wrong rows!

11. **LANDMARK WEB NAVIGATION (flaglerclerk, etc.)**:
    - These sites show a HOME PAGE with search icons (Name Search, Document Search, etc.)
    - The disclaimer/accept button is HIDDEN on the home page
    - The flow is:
      1. Navigate to home page
      2. **Click the "Name Search" icon** (a[title='Name Search'] or similar)
      3. This opens a MODAL with the disclaimer
      4. Click Accept button to dismiss disclaimer
      5. Now the search form is visible in the modal
    - If the home page has search icons but no visible Accept button, click the Name Search icon FIRST
    - Use try/except blocks to handle the case where disclaimer is already accepted via cookies

12. **WAIT FOR FORM BEFORE FILLING (CRITICAL FOR DATES)**:
    - **BEFORE** filling ANY form field (search term, start date, end date), you MUST wait for the search input field to be visible:
      ```python
      # CRITICAL: Wait for the search form to be visible in the modal
      page.wait_for_selector("#name-Name", state="visible", timeout=5000)
      ```
    - For Landmark Web sites, the search modal takes time to fully render after accepting disclaimer
    - If you fill date fields via JavaScript BEFORE the modal is visible, the values will NOT be applied!
    - The correct order is:
      1. Accept disclaimer
      2. **Wait for search input to be visible** (e.g., `#name-Name`)
      3. Fill search term
      4. Fill start/end dates
      5. Click submit

13. **PLAYWRIGHT API - VALID METHODS ONLY (CRITICAL)**:
    - **DO NOT** use non-existent methods. The following DO NOT EXIST in Playwright:
      - `filter(has_attribute=...)` - DOES NOT EXIST
      - `filter(has_text=..., has_attribute=...)` - INVALID COMBINATION
    - **VALID filter() arguments**: `has_text`, `has_not_text`, `has`, `has_not`
    - **For attribute filtering**, use CSS selectors directly:
      ```python
      # WRONG: page.locator("input").filter(has_attribute={"type": "submit"})
      # RIGHT: page.locator("input[type='submit']")
      ```
    - **Keep locators simple**: Use direct CSS selectors instead of chained filter() calls
    - **VALID patterns**:
      ```python
      page.locator("#myButton").click()
      page.locator("input[type='submit']").first.click()
      page.locator(".btn").filter(has_text="Search").click()
      ```

14. **INFRAGISTICS / AUMENTUM SITES (CRITICAL)**:
    - If the URL or HTML contains `ig_ElectricBlue`, `Infragistics`, or `Aumentum`:
    - **DO NOT USE `.fill()`** for search inputs or date fields! These controls ignore JavaScript-based value assignment.
    - **YOU MUST USE KEYBOARD TYPING**:
      ```python
      # Correct pattern for Infragistics/Aumentum fields:
      field = page.locator("#exact-selector")
      field.click()
      page.keyboard.press("Control+A")
      page.keyboard.press("Backspace")
      field.type(value, delay=50) # Use type() with delay
      page.keyboard.press("Tab")
      ```
    - Apply this to: Search term input, Start Date, End Date.

15. **ENFORCE GROUND TRUTH (STRICT)**:
    - The `recorded_steps` contain the ONLY selectors that are guaranteed to work.
    - If `recorded_steps` says a selector is `#cph1_lnkAccept`, do NOT "guess" and use `#cphNoMargin_btnAccept`.
    - Always use the selector exactly as it appears in the `recorded_steps`.

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
            page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=5000)
            page.wait_for_load_state("networkidle", timeout=5000)
            
            # STEP 2: Accept Disclaimer (if present)
            # CRITICAL: Always wait after clicks!
            print("[STEP 2] Accepting disclaimer...")
            try:
                page.locator("#btnButton").click()  # Use recorded selector
                page.wait_for_load_state("domcontentloaded", timeout=5000)
            except:
                pass  # Disclaimer may not appear
            
            # STEP 3-5: Fill form fields using recorded selectors
            # page.fill("#SearchOnName", search_term)
            # page.fill("#RecordDateFrom", start_date)
            # page.fill("#RecordDateTo", end_date)
            
            # STEP 6: Submit search
            # CRITICAL: Always wait after search click!
            print("[STEP 6] Submitting search...")
            page.locator("#btnSearch").click()  # Use recorded selector
            page.wait_for_load_state("domcontentloaded", timeout=5000)
            
            # ROBUST WAIT AFTER SEARCH:
            # Many sites show a "Name Selection" popup after search.
            # Use short timeout and handle gracefully - either popup OR grid may appear.
            print("[STEP 6] Waiting for results OR popup...")
            try:
                page.wait_for_selector("{grid_selector}, #NamesWin, #frmSchTarget, .t-window", timeout=5000)
            except:
                pass  # Continue anyway - popup or grid may still appear

            # HANDLE POPUPS IF RECORDED (Use try/except for robustness)
            # Try multiple popup button selectors in order of specificity
            popup_selectors = [
                "#frmSchTarget input[type='submit']",  # Recorded popup button
                "input[value='Done']",
                "input[name='btnDone']"
            ]
            for popup_sel in popup_selectors:
                try:
                    popup_btn = page.locator(popup_sel)
                    # CRITICAL: Always use timeout=3000 for dynamic popups
                    if popup_btn.is_visible(timeout=3000):
                        print(f"[STEP 6b] Handling popup with {{popup_sel}}...")
                        popup_btn.first.click()
                        page.wait_for_load_state("networkidle", timeout=5000)
                        break  # Exit loop once popup is handled
                except:
                    continue  # Try next selector

            # WAIT FOR GRID (TRY MULTIPLE SELECTORS FOR ROBUSTNESS)
            print("[STEP 7] Ensuring grid is visible...")
            grid_selectors = ["{grid_selector}", "#RsltsGrid", "#SearchGrid", ".t-grid", "#itemPlaceholderContainer", "table.table-condensed"]
            grid_found = False
            for selector in grid_selectors:
                try:
                    grid = page.locator(selector)
                    grid.wait_for(state="visible", timeout=5000)
                    print(f"[STEP 7] Found grid: {{selector}}")
                    grid_found = True
                    break
                except:
                    continue
            
            if not grid_found:
                # Last resort: wait a bit more and check for any visible table with data
                page.wait_for_timeout(3000)
                if page.locator("{grid_selector}").is_visible():
                    grid_found = True
            
            # EXTRACT DATA - START FROM FIRST_DATA_COLUMN
            print("[STEP 8] Extracting rows...")
            # CRITICAL: Combine grid_selector with row_selector for correct row location
            rows = page.locator("{grid_selector} {row_selector}").all()
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
            
            # CRITICAL: Always print SUCCESS (even with 0 rows)
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
    first_data_column_index: int = 0,
    site_type: str = "UNKNOWN"
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
        # Include use_js flag for datepicker fields
        if step.get("use_js"):
            step_info["use_js"] = True
        # Include wait_for_input hint for date fields
        if step.get("wait_for_input"):
            step_info["wait_for_input"] = step.get("wait_for_input")
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
        first_data_column_index=first_data_column_index,
        site_type=site_type
    )
    
    # Add grid HTML context if provided
    if grid_html:
        prompt += f"\n\n## GRID HTML CONTEXT (for understanding table structure - hidden columns already filtered)\n{grid_html[:20000]}"
    
    return prompt
