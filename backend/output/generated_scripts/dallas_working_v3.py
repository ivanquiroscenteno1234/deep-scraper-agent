import sys
import os
import csv
import datetime
import time
from playwright.sync_api import sync_playwright

SITE_NAME = "dallas"
TARGET_URL = "https://dallas.tx.publicsearch.us/"
TIMESTAMP = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
FIRST_DATA_COLUMN = 3

COLUMNS = [
    "Grantor",
    "Grantee",
    "Doc Type",
    "Recorded Date",
    "Doc Number",
    "Book/Volume/Page",
    "Town",
    "Legal Description"
]

def main():
    search_term = sys.argv[1] if len(sys.argv) > 1 else "LA FITTE INV INC"
    start_date = sys.argv[2] if len(sys.argv) > 2 else "01/01/1978"
    end_date = sys.argv[3] if len(sys.argv) > 3 else "12/31/1978"
    
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
            time.sleep(1)

            # CRITICAL: Wait for the search form to be visible before filling
            print("[STEP 2] Waiting for search form...")
            page.wait_for_selector("input[data-testid=\"searchInputBox\"]", state="visible", timeout=10000)

            # STEP 2: Fill start date
            print(f"[STEP 3] Filling start date: {start_date}")
            start_date_input = page.locator("input[aria-label=\"Starting Recorded Date\"]")
            start_date_input.fill(start_date)
            time.sleep(1)

            # STEP 3: Fill end date
            print(f"[STEP 4] Filling end date: {end_date}")
            end_date_input = page.locator("input[aria-label=\"Ending Recorded Date\"]")
            end_date_input.fill(end_date)
            time.sleep(1)

            # STEP 4: Fill search input
            print(f"[STEP 5] Filling search term: {search_term}")
            search_input = page.locator("input[data-testid=\"searchInputBox\"]")
            search_input.fill(search_term)
            time.sleep(1)

            # STEP 5: Submit search
            print("[STEP 6] Submitting search...")
            search_button = page.locator("button[data-testid=\"searchSubmitButton\"]")
            search_button.click()
            page.wait_for_load_state("networkidle", timeout=15000)
            time.sleep(5)

            # Handle Intermediate Popups/Name Selection
            print("[STEP 7] Checking for results or intermediate popups...")
            try:
                page.wait_for_selector(".search-results__results-wrap table, #NamesWin, .t-window", timeout=5000)
            except:
                pass

            popup_selectors = [
                "input[value='Done']",
                "button:has-text('Done')",
                ".t-window input[type='submit']"
            ]
            for popup_sel in popup_selectors:
                try:
                    popup_btn = page.locator(popup_sel)
                    if popup_btn.is_visible(timeout=3000):
                        print(f"[STEP 7b] Handling popup with {popup_sel}...")
                        popup_btn.first.click()
                        page.wait_for_load_state("networkidle", timeout=10000)
                        time.sleep(5)
                        break
                except:
                    continue

            # STEP 8: Extract Data
            print("[STEP 8] Ensuring grid is visible...")
            grid_selector = ".search-results__results-wrap table"
            try:
                page.wait_for_selector(grid_selector, state="visible", timeout=10000)
            except:
                print("FAILED: Grid not found after search.")
                return

            print("[STEP 9] Extracting rows...")
            rows = page.locator(f"{grid_selector} tbody tr").all()
            data = []
            
            for row in rows:
                cells = row.locator("td").all()
                if len(cells) > FIRST_DATA_COLUMN:
                    row_data = {}
                    for i, col_name in enumerate(COLUMNS):
                        cell_index = FIRST_DATA_COLUMN + i
                        if cell_index < len(cells):
                            row_data[col_name] = cells[cell_index].text_content().strip()
                    data.append(row_data)
            
            # STEP 10: Save to CSV
            script_dir = os.path.dirname(os.path.abspath(__file__))
            output_dir = os.path.join(os.path.dirname(script_dir), "data")
            os.makedirs(output_dir, exist_ok=True)
            
            clean_term = "".join([c if c.isalnum() else "_" for c in search_term])
            filename = f"{SITE_NAME}_{clean_term}_{TIMESTAMP}.csv"
            filepath = os.path.join(output_dir, filename)
            
            if data:
                with open(filepath, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=COLUMNS)
                    writer.writeheader()
                    writer.writerows(data)
                print(f"SUCCESS: Extracted {len(data)} rows to {filename}")
            else:
                print("SUCCESS: Search completed but 0 results found.")
            
        except Exception as e:
            print(f"FAILED: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    main()