import sys
import os
import csv
import datetime
from playwright.sync_api import sync_playwright

SITE_NAME = "brevardclerk"
TARGET_URL = "https://vaclmweb1.brevardclerk.us/AcclaimWeb/search/SearchTypeName"
TIMESTAMP = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
FIRST_DATA_COLUMN = 2

def main():
    # USAGE: python script.py "SEARCH_TERM" "START_DATE" "END_DATE"
    search_term = sys.argv[1] if len(sys.argv) > 1 else "SMITH"
    start_date = sys.argv[2] if len(sys.argv) > 2 else "01/01/2023"
    end_date = sys.argv[3] if len(sys.argv) > 3 else datetime.datetime.now().strftime('%m/%d/%Y')
    
    print(f"[INFO] Starting scraper for '{search_term}' (Range: {start_date} - {end_date})")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/119.0.0.0"
        )
        page = context.new_page()
        
        try:
            # STEP 1: Navigate
            print("[STEP 1] Navigating to URL...")
            page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=30000)
            
            # STEP 2: Accept Disclaimer
            print("[STEP 2] Checking for disclaimer...")
            try:
                accept_btn = page.locator("#btnButton")
                if accept_btn.is_visible(timeout=5000):
                    accept_btn.click()
            except:
                pass
            
            # STEP 3: Fill form fields
            print(f"[STEP 3] Filling search for: {search_term}")
            page.wait_for_selector("#SearchOnName", state="visible", timeout=10000)
            page.locator("#SearchOnName").fill(search_term)
            
            # Set dates using JavaScript
            print(f"[STEP 4] Setting date range: {start_date} - {end_date}")
            for selector, date_val in [("#RecordDateFrom", start_date), ("#RecordDateTo", end_date)]:
                page.evaluate(f"""
                    (() => {{
                        const el = document.querySelector('{selector}');
                        if (el) {{
                            el.value = '{date_val}';
                            el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                            el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        }}
                    }})()
                """)
            
            # STEP 5: Submit search
            print("[STEP 5] Submitting search...")
            page.locator("#btnSearch").click()
            
            # STEP 6: Combined wait for Results Grid or Name Selection Popup
            print("[STEP 6] Waiting for results OR name selection...")
            # Fixed: Removed generic .t-window and used specific IDs to avoid multiple matches/strict mode violations
            page.wait_for_selector("#RsltsGrid, #NamesWin, #frmSchTarget", timeout=20000)

            # HANDLE INTERMEDIATE POPUP (Name selection)
            if page.locator("#NamesWin").is_visible() or page.locator("#frmSchTarget").is_visible():
                print("[STEP 6b] Handling name selection popup...")
                # Click the "Done" or Search button in the popup, scoped to the popup containers
                done_btn = page.locator("#NamesWin input[type='submit'], #frmSchTarget input[type='submit']").first
                done_btn.click()
                # Wait for the main grid to become visible after name selection
                page.wait_for_selector("#RsltsGrid", timeout=15000)

            # STEP 7: Ensure grid data is actually loaded
            print("[STEP 7] Ensuring grid is populated...")
            grid_selector = "#RsltsGrid"
            row_selector = ".t-grid-content tbody tr"
            
            try:
                # Wait for the first row's 3rd cell (index 2) to be populated per GROUND TRUTH
                page.wait_for_selector(f"{grid_selector} {row_selector} td:nth-child({FIRST_DATA_COLUMN + 1})", state="visible", timeout=15000)
            except:
                if page.locator(".t-no-data").is_visible() or page.locator(".t-grid-content tbody").is_hidden():
                    print("SUCCESS: No records found for this search.")
                    return
                print("Grid data not found or timeout waiting for cell content.")

            # STEP 8: Extract data
            print("[STEP 8] Extracting rows...")
            # Use specific scoping from GROUND TRUTH
            rows = page.locator(f"{grid_selector} {row_selector}").all()
            
            column_names = [
                "Party Type", "Full Name", "Cross Party Name", "Record Date", "Type", 
                "Book Type", "Book/Page", "Clerk File Number", "Consideration", 
                "First Legal Description", "Description", "Case #"
            ]
            
            data = []
            for row in rows:
                cells = row.locator("td").all()
                # Skip rows that don't have enough data cells (e.g. "No records found")
                if len(cells) > FIRST_DATA_COLUMN:
                    row_data = {}
                    for i, col_name in enumerate(column_names):
                        # Use FIRST_DATA_COLUMN (2) as the offset from GROUND TRUTH
                        cell_index = FIRST_DATA_COLUMN + i
                        if cell_index < len(cells):
                            row_data[col_name] = cells[cell_index].text_content().strip()
                    if any(row_data.values()): # Only add if not entirely empty
                        data.append(row_data)
            
            # STEP 9: Save to CSV
            script_dir = os.path.dirname(os.path.abspath(__file__))
            output_dir = os.path.join(os.path.dirname(script_dir), "data")
            os.makedirs(output_dir, exist_ok=True)
            
            filename = f"{SITE_NAME}_{search_term.replace(' ', '_')}_{TIMESTAMP}.csv"
            filepath = os.path.join(output_dir, filename)
            
            if data:
                with open(filepath, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=column_names)
                    writer.writeheader()
                    writer.writerows(data)
                print(f"SUCCESS: Extracted {len(data)} rows to {filepath}")
            else:
                print("SUCCESS: No data found to extract after grid load")
            
        except Exception as e:
            print(f"FAILED: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    main()