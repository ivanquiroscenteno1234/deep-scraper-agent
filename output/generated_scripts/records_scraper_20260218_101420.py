import sys
import os
import csv
import datetime
import time
from playwright.sync_api import sync_playwright

SITE_NAME = "records"
TARGET_URL = "https://records.flaglerclerk.com/"
TIMESTAMP = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
FIRST_DATA_COLUMN = 1

def main():
    # USAGE: python script.py "SEARCH_TERM" "START_DATE" "END_DATE"
    search_term = sys.argv[1] if len(sys.argv) > 1 else "SMITH"
    start_date = sys.argv[2] if len(sys.argv) > 2 else "01/01/2024"
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
            page.wait_for_load_state("networkidle", timeout=5000)
            
            # STEP 2: Click Name Search (Landmark Web Navigation Pattern)
            print("[STEP 2] Clicking Name Search...")
            page.locator("a[title='Name Search']").click()
            page.wait_for_load_state("domcontentloaded", timeout=5000)
            
            # STEP 3: Accept Disclaimer
            print("[STEP 3] Accepting disclaimer...")
            try:
                disclaimer_btn = page.locator("#idAcceptYes")
                if disclaimer_btn.is_visible(timeout=5000):
                    disclaimer_btn.click()
                    page.wait_for_load_state("domcontentloaded", timeout=5000)
            except:
                print("[INFO] Disclaimer not found or already accepted.")

            # CRITICAL: Wait for the search form to be visible in the modal
            print("[INFO] Waiting for search form to render...")
            page.wait_for_selector("#name-Name", state="visible", timeout=10000)
            
            # STEP 4: Fill start date (JS required)
            print(f"[STEP 4] Filling start date: {start_date}")
            page.evaluate(f"""
                (() => {{
                    const el = document.querySelector('#beginDate-Name');
                    if (el) {{
                        el.value = '{start_date}';
                        el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    }}
                }})()
            """)
            
            # STEP 5: Fill end date (JS required)
            print(f"[STEP 5] Filling end date: {end_date}")
            page.evaluate(f"""
                (() => {{
                    const el = document.querySelector('#endDate-Name');
                    if (el) {{
                        el.value = '{end_date}';
                        el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    }}
                }})()
            """)
            
            # STEP 6: Fill search input
            print(f"[STEP 6] Filling search term: {search_term}")
            page.locator("#name-Name").fill(search_term)
            
            # STEP 7: Submit search
            print("[STEP 7] Submitting search...")
            page.locator("#submit-Name").click()
            page.wait_for_load_state("networkidle", timeout=10000)
            
            # STEP 8: Handle Name Selection Popup (Landmark Web specific)
            print("[STEP 8] Checking for name selection popup...")
            try:
                # Wait for EITHER the grid OR the popup container
                page.wait_for_selector("#resultsTable, #idAcceptYes", timeout=5000)
                popup_btn = page.locator("#idAcceptYes")
                if popup_btn.is_visible(timeout=3000):
                    print("[STEP 8] Handling popup with #idAcceptYes...")
                    popup_btn.click()
                    page.wait_for_load_state("networkidle", timeout=5000)
            except:
                pass

            # STEP 9: Wait for Grid
            print("[STEP 9] Ensuring grid is visible...")
            grid_found = False
            try:
                grid = page.locator("#resultsTable")
                grid.wait_for(state="visible", timeout=10000)
                grid_found = True
            except:
                print("[WARNING] Grid #resultsTable not visible. Checking for alternative content...")

            if not grid_found:
                if "No results found" in page.content():
                    print("SUCCESS: Extracted 0 rows (No results)")
                    return

            # EXTRACT DATA
            print("[STEP 10] Extracting rows...")
            rows = page.locator("#resultsTable tbody tr").all()
            data = []
            
            columns = [
                "Names",
                "Doc Type",
                "Rec Date",
                "Book/Page",
                "Inst #",
                "Consideration",
                "Legal Description"
            ]
            
            for row in rows:
                cells = row.locator("td").all()
                # Check if this is a data row and not a message row
                if len(cells) > FIRST_DATA_COLUMN:
                    row_data = {}
                    for i, col_name in enumerate(columns):
                        cell_index = FIRST_DATA_COLUMN + i
                        if cell_index < len(cells):
                            row_data[col_name] = cells[cell_index].text_content().strip()
                    if any(row_data.values()): # Only add if not empty
                        data.append(row_data)
            
            # SAVE TO CSV
            script_dir = os.path.dirname(os.path.abspath(__file__))
            output_dir = os.path.join(os.path.dirname(script_dir), "data")
            os.makedirs(output_dir, exist_ok=True)
            
            filename = f"flagler_results_{search_term}_{TIMESTAMP}.csv"
            filepath = os.path.join(output_dir, filename)
            
            if data:
                with open(filepath, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=columns)
                    writer.writeheader()
                    writer.writerows(data)
                print(f"SUCCESS: Extracted {len(data)} rows to {filepath}")
            else:
                print("SUCCESS: No data rows found matching search criteria.")
            
        except Exception as e:
            print(f"FAILED: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    main()