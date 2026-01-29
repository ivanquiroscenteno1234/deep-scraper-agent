import sys
import os
import csv
import datetime
from playwright.sync_api import sync_playwright

SITE_NAME = "tccsearch"
TARGET_URL = "https://www.tccsearch.org/RealEstate/SearchEntry.aspx"
FIRST_DATA_COLUMN = 4
COLUMNS = [
    "Instrument #",
    "Book",
    "Page",
    "Date Filed",
    "Document Type",
    "Name",
    "Associated Name",
    "Legal Description",
    "Status"
]

def main():
    # USAGE: python script.py "SEARCH_TERM" "START_DATE" "END_DATE"
    search_term = sys.argv[1] if len(sys.argv) > 1 else "SMITH"
    start_date = sys.argv[2] if len(sys.argv) > 2 else "01/01/2023"
    end_date = sys.argv[3] if len(sys.argv) > 3 else datetime.datetime.now().strftime('%m/%d/%Y')
    
    print(f"[INFO] Starting scraper for '{search_term}' ({start_date} - {end_date})")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        try:
            # STEP 1: Navigate
            print("[STEP 1] Navigating to target URL...")
            page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=30000)
            
            # STEP 2: Accept Disclaimer
            print("[STEP 2] Accepting disclaimer...")
            try:
                accept_btn = page.locator("#cph1_lnkAccept")
                if accept_btn.is_visible(timeout=5000):
                    accept_btn.click()
                    page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:
                print("[INFO] No disclaimer found or already accepted.")

            # CRITICAL: Wait for the search form to be visible
            print("[WAIT] Waiting for search form...")
            page.wait_for_selector("#cphNoMargin_f_txtParty", state="visible", timeout=10000)

            # STEP 3: Fill start date
            print(f"[STEP 3] Filling start date: {start_date}")
            page.locator("#cphNoMargin_f_ddcDateFiledFrom input").fill(start_date)

            # STEP 4: Fill end date
            print(f"[STEP 4] Filling end date: {end_date}")
            page.locator("#cphNoMargin_f_ddcDateFiledTo input").fill(end_date)

            # STEP 5: Fill search input
            print(f"[STEP 5] Filling search term: {search_term}")
            page.locator("#cphNoMargin_f_txtParty").fill(search_term)

            # STEP 6: Submit search
            print("[STEP 6] Submitting search...")
            page.locator("#cphNoMargin_SearchButtons1_btnSearch").click()
            page.wait_for_load_state("networkidle", timeout=10000)

            # Handle intermediate "Name Selection" or popups if they appear
            print("[INFO] Checking for intermediate popups or result grid...")
            try:
                # Comma separated selectors for grid or common popup containers
                page.wait_for_selector(".ig_ElectricBlueControl, #NamesWin, #frmSchTarget, .t-window", timeout=5000)
            except:
                pass

            # If a "Done" or "Select" button appears for name matching, click it
            popup_selectors = ["input[value='Done']", "input[name*='btnDone']", "#btnDone"]
            for sel in popup_selectors:
                try:
                    btn = page.locator(sel)
                    if btn.is_visible(timeout=3000):
                        print(f"[INFO] Clicking popup button: {sel}")
                        btn.click()
                        page.wait_for_load_state("networkidle", timeout=5000)
                        break
                except:
                    continue

            # STEP 7: Capture Grid
            print("[STEP 7] Waiting for grid results...")
            grid_selector = ".ig_ElectricBlueControl"
            try:
                page.wait_for_selector(grid_selector, timeout=10000)
            except:
                print("FAILED: Results grid not found. Check search criteria.")
                return

            print("[STEP 8] Extracting data rows...")
            # Use specific row selector relative to grid
            rows = page.locator(f"{grid_selector} tbody tr").all()
            results = []
            
            for row in rows:
                cells = row.locator("td").all()
                # Check if this is a data row (must have enough cells)
                if len(cells) > FIRST_DATA_COLUMN:
                    row_data = {}
                    valid_row = False
                    for i, col_name in enumerate(COLUMNS):
                        cell_index = FIRST_DATA_COLUMN + i
                        if cell_index < len(cells):
                            text = cells[cell_index].text_content().strip()
                            row_data[col_name] = text
                            if text: valid_row = True
                    
                    if valid_row:
                        results.append(row_data)

            # Save to CSV
            script_dir = os.path.dirname(os.path.abspath(__file__))
            output_dir = os.path.join(os.path.dirname(script_dir), "data")
            os.makedirs(output_dir, exist_ok=True)
            
            safe_term = "".join([c for c in search_term if c.isalnum()]).rstrip()
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{SITE_NAME}_{safe_term}_{timestamp}.csv"
            filepath = os.path.join(output_dir, filename)

            if results:
                with open(filepath, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=COLUMNS)
                    writer.writeheader()
                    writer.writerows(results)
                print(f"SUCCESS: Extracted {len(results)} rows to {filename}")
            else:
                print("SUCCESS: Search completed but no data rows were found.")

        except Exception as e:
            print(f"FAILED: {str(e)}")
        finally:
            browser.close()

if __name__ == "__main__":
    main()