import sys
import os
import csv
import datetime
from playwright.sync_api import sync_playwright

SITE_NAME = "records"
TARGET_URL = "https://records.flaglerclerk.com/"
TIMESTAMP = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
FIRST_DATA_COLUMN = 1  # Skip row#, icon columns
COLUMNS = [
    "Names",
    "Rec Date",
    "Doc Type",
    "Book/Page",
    "Instrument #",
    "Legal Description",
    "Consideration"
]

def main():
    # USAGE: python script.py "SEARCH_TERM" "START_DATE" "END_DATE"
    search_term = sys.argv[1] if len(sys.argv) > 1 else "SMITH"
    start_date = sys.argv[2] if len(sys.argv) > 2 else "01/01/1980"
    end_date = sys.argv[3] if len(sys.argv) > 3 else datetime.datetime.now().strftime('%m/%d/%Y')
    
    print(f"[INFO] Starting scraper for '{search_term}' (Range: {start_date} - {end_date})")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/119.0.0.0"
        )
        page = context.new_page()
        
        try:
            # STEP 1: Navigate
            print("[STEP 1] Navigating to URL...")
            page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_load_state("networkidle", timeout=30000)
            
            # STEP 2: Click Name Search
            print("[STEP 2] Clicking Name Search icon...")
            page.click("a[title='Name Search']")
            page.wait_for_load_state("domcontentloaded", timeout=30000)

            # STEP 3: Accept Disclaimer
            print("[STEP 3] Accepting disclaimer...")
            try:
                btn_accept = page.locator("#idAcceptYes")
                btn_accept.wait_for(state="visible", timeout=10000)
                btn_accept.click()
                page.wait_for_load_state("domcontentloaded", timeout=30000)
            except Exception as e:
                print(f"[WARN] Disclaimer button not found or already accepted: {e}")

            # CRITICAL: Wait for form visibility
            print("[INFO] Waiting for search form to be visible...")
            page.wait_for_selector("#name-Name", state="visible", timeout=10000)

            # STEP 4: Fill Start Date
            print(f"[STEP 4] Filling start date: {start_date}")
            page.fill("#beginDate-Name", start_date)

            # STEP 5: Fill End Date
            print(f"[STEP 5] Filling end date: {end_date}")
            page.fill("#endDate-Name", end_date)

            # STEP 6: Fill Search Term
            print(f"[STEP 6] Filling search term: {search_term}")
            page.fill("#name-Name", search_term)

            # STEP 7: Submit Search
            print("[STEP 7] Submitting search...")
            page.click("#submit-Name")
            page.wait_for_load_state("networkidle", timeout=30000)

            # ROBUST WAIT AFTER SEARCH
            print("[STEP 8] Waiting for results OR name selection popup...")
            try:
                page.wait_for_selector("#resultsTable, #idAcceptYes, #NamesWin, .t-window", timeout=15000)
            except:
                pass

            # STEP 8 (Recorded): Handle name selection popup if it appears
            try:
                popup_btn = page.locator("#idAcceptYes")
                if popup_btn.is_visible(timeout=5000):
                    print("[STEP 8] Handling Name Selection popup...")
                    popup_btn.click()
                    page.wait_for_load_state("networkidle", timeout=30000)
            except:
                pass

            # WAIT FOR GRID
            print("[STEP 9] Ensuring grid is visible...")
            grid_selector = "#resultsTable"
            try:
                page.wait_for_selector(grid_selector, state="visible", timeout=20000)
            except Exception as e:
                print(f"[ERROR] Grid not found: {e}")
                return

            # STEP 10: Extract Data
            print("[STEP 10] Extracting rows...")
            rows = page.locator("#resultsTable tbody tr").all()
            results = []
            
            for row in rows:
                cells = row.locator("td").all()
                if len(cells) > FIRST_DATA_COLUMN:
                    row_data = {}
                    for i, col_name in enumerate(COLUMNS):
                        cell_index = FIRST_DATA_COLUMN + i
                        if cell_index < len(cells):
                            row_data[col_name] = cells[cell_index].text_content().strip()
                    if row_data:
                        results.append(row_data)

            # STEP 11: Save to CSV
            script_dir = os.path.dirname(os.path.abspath(__file__))
            output_dir = os.path.join(os.path.dirname(script_dir), "data")
            os.makedirs(output_dir, exist_ok=True)
            
            safe_term = "".join(x for x in search_term if x.isalnum())
            filename = f"flagler_{safe_term}_{TIMESTAMP}.csv"
            output_path = os.path.join(output_dir, filename)
            
            if results:
                with open(output_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=COLUMNS)
                    writer.writeheader()
                    writer.writerows(results)
                print(f"SUCCESS: Extracted {len(results)} rows to {output_path}")
            else:
                print("No data found to extract.")
            
        except Exception as e:
            print(f"FAILED: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    main()