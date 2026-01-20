import sys
import os
import csv
import datetime
import time
from playwright.sync_api import sync_playwright

SITE_NAME = "records"
TARGET_URL = "https://records.flaglerclerk.com/"
FIRST_DATA_COLUMN = 1
COLUMNS = [
    "Names",
    "Record Date",
    "Doc Type",
    "Book/Page",
    "Instrument #",
    "Legal Description",
    "Consideration"
]

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
            # STEP 1: Navigate to target URL
            print("[STEP 1] Navigating to URL...")
            page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_load_state("networkidle", timeout=10000)
            time.sleep(1)

            # STEP 2: Click Name Search icon
            print("[STEP 2] Clicking Name Search...")
            page.locator("a[title='Name Search']").click()
            page.wait_for_load_state("domcontentloaded")
            time.sleep(1)

            # STEP 3: Accept Disclaimer
            print("[STEP 3] Accepting disclaimer...")
            try:
                disclaimer_btn = page.locator("#idAcceptYes")
                if disclaimer_btn.is_visible(timeout=5000):
                    disclaimer_btn.click()
                    page.wait_for_load_state("domcontentloaded")
                    time.sleep(1)
            except:
                pass

            # CRITICAL: Wait for the search form to be visible
            print("[INFO] Waiting for search form to appear...")
            page.wait_for_selector("#name-Name", state="visible", timeout=10000)

            # STEP 4: Fill start date
            print(f"[STEP 4] Filling start date: {start_date}")
            page.locator("#beginDate-Name").fill(start_date)
            time.sleep(1)

            # STEP 5: Fill end date
            print(f"[STEP 5] Filling end date: {end_date}")
            page.locator("#endDate-Name").fill(end_date)
            time.sleep(1)

            # STEP 6: Fill search input
            print(f"[STEP 6] Filling search term: {search_term}")
            page.locator("#name-Name").fill(search_term)
            time.sleep(1)

            # STEP 7: Submit search
            print("[STEP 7] Submitting search...")
            page.locator("#submit-Name").click()
            page.wait_for_load_state("domcontentloaded")
            time.sleep(5)

            # STEP 8: Handle Intermediate Name Selection Popup
            print("[STEP 8] Waiting for results OR name selection popup...")
            try:
                # Simultaneous wait for grid or popup
                page.wait_for_selector("#resultsTable, #idAcceptYes", timeout=5000)
                
                popup_btn = page.locator("#idAcceptYes")
                if popup_btn.is_visible(timeout=3000):
                    print("[STEP 8b] Handling name selection popup...")
                    popup_btn.click()
                    page.wait_for_load_state("networkidle")
                    time.sleep(5)
            except:
                pass

            # STEP 9: Extract Grid Data
            print("[STEP 9] Ensuring grid is visible...")
            try:
                grid_selector = "#resultsTable"
                page.wait_for_selector(grid_selector, state="visible", timeout=10000)
                
                rows = page.locator("#resultsTable tbody tr").all()
                data = []
                
                print(f"[STEP 9] Extracting {len(rows)} potential rows...")
                for row in rows:
                    cells = row.locator("td").all()
                    # Skip if not enough cells or if it's a "No records found" row
                    if len(cells) > FIRST_DATA_COLUMN:
                        row_data = {}
                        for i, col_name in enumerate(COLUMNS):
                            cell_index = FIRST_DATA_COLUMN + i
                            if cell_index < len(cells):
                                text = cells[cell_index].text_content().strip()
                                row_data[col_name] = text
                        
                        if any(row_data.values()):
                            data.append(row_data)

                # Save to CSV
                script_dir = os.path.dirname(os.path.abspath(__file__))
                output_dir = os.path.join(os.path.dirname(script_dir), "data")
                os.makedirs(output_dir, exist_ok=True)
                
                filename = f"flagler_results_{TIMESTAMP}.csv" if 'TIMESTAMP' in globals() else f"flagler_{int(time.time())}.csv"
                output_path = os.path.join(output_dir, filename)
                
                if data:
                    with open(output_path, 'w', newline='', encoding='utf-8') as f:
                        writer = csv.DictWriter(f, fieldnames=COLUMNS)
                        writer.writeheader()
                        writer.writerows(data)
                    print(f"SUCCESS: Extracted {len(data)} rows to {output_path}")
                else:
                    print("SUCCESS: No rows found for the given criteria.")

            except Exception as e:
                print(f"FAILED: Could not find or parse results grid. {e}")

        except Exception as e:
            print(f"FAILED: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    main()