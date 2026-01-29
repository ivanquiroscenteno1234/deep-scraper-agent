import sys
import os
import csv
import datetime
import time
from playwright.sync_api import sync_playwright

SITE_NAME = "records"
TARGET_URL = "https://records.flaglerclerk.com/"
TIMESTAMP = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
FIRST_DATA_COLUMN = 1  # Skip row#, icons

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
            page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_load_state("networkidle", timeout=10000)
            time.sleep(3)

            # STEP 2: Click Name Search icon (Landmark Navigation)
            print("[STEP 2] Clicking Name Search icon...")
            page.locator("a[title='Name Search']").click()
            page.wait_for_load_state("domcontentloaded", timeout=10000)
            time.sleep(3)

            # STEP 3: Accept Disclaimer
            print("[STEP 3] Accepting disclaimer...")
            try:
                disclaimer_btn = page.locator("#idAcceptYes")
                if disclaimer_btn.is_visible(timeout=5000):
                    disclaimer_btn.click()
                    page.wait_for_load_state("domcontentloaded", timeout=10000)
                    time.sleep(3)
            except:
                pass

            # CRITICAL: Wait for the search form to be visible in the modal before filling
            print("[WAIT] Waiting for search form...")
            page.wait_for_selector("#name-Name", state="visible", timeout=10000)

            # STEP 4: Fill start date
            print(f"[STEP 4] Filling start date: {start_date}")
            page.locator("#beginDate-Name").fill(start_date)
            time.sleep(3)

            # STEP 5: Fill end date
            print(f"[STEP 5] Filling end date: {end_date}")
            page.locator("#endDate-Name").fill(end_date)
            time.sleep(3)

            # STEP 6: Fill search input
            print(f"[STEP 6] Filling search term: {search_term}")
            page.locator("#name-Name").fill(search_term)
            time.sleep(3)

            # STEP 7: Submit search
            print("[STEP 7] Submitting search...")
            page.locator("#submit-Name").click()
            page.wait_for_load_state("domcontentloaded", timeout=10000)
            time.sleep(3)

            # STEP 8: Handle intermediate popup (Name Selection)
            print("[STEP 8] Checking for name selection popup...")
            try:
                popup_btn = page.locator("#idAcceptYes")
                if popup_btn.is_visible(timeout=5000):
                    print("[STEP 8] Clicking popup accept...")
                    popup_btn.click()
                    page.wait_for_load_state("networkidle", timeout=10000)
                    time.sleep(3)
            except:
                pass

            # WAIT FOR GRID
            print("[STEP 9] Ensuring grid is visible...")
            try:
                page.wait_for_selector("#resultsTable", state="visible", timeout=15000)
            except:
                print("[ERROR] Results grid not found.")
                return

            # EXTRACT DATA
            print("[STEP 10] Extracting data rows...")
            rows = page.locator("#resultsTable tbody tr").all()
            data = []
            columns = [
                "Names",
                "Recorded",
                "Document Type",
                "Book/Page",
                "Instrument #",
                "Case #",
                "Description"
            ]

            for row in rows:
                cells = row.locator("td").all()
                if len(cells) > FIRST_DATA_COLUMN:
                    row_data = {}
                    for i, col_name in enumerate(columns):
                        cell_index = FIRST_DATA_COLUMN + i
                        if cell_index < len(cells):
                            row_data[col_name] = cells[cell_index].text_content().strip()
                    if row_data:
                        data.append(row_data)

            # SAVE TO CSV
            script_dir = os.path.dirname(os.path.abspath(__file__))
            output_dir = os.path.join(os.path.dirname(script_dir), "data")
            os.makedirs(output_dir, exist_ok=True)
            
            filename = f"flagler_results_{TIMESTAMP}.csv"
            filepath = os.path.join(output_dir, filename)
            
            if data:
                with open(filepath, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=columns)
                    writer.writeheader()
                    writer.writerows(data)
                print(f"SUCCESS: Extracted {len(data)} rows to {filepath}")
            else:
                print("SUCCESS: No results found for the given criteria.")

        except Exception as e:
            print(f"FAILED: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    main()