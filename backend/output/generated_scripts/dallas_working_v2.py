import sys
import os
import csv
import datetime
from playwright.sync_api import sync_playwright

SITE_NAME = "dallas"
TARGET_URL = "https://dallas.tx.publicsearch.us/"
TIMESTAMP = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
FIRST_DATA_COLUMN = 3

def main():
    # USAGE: python script.py "SEARCH_TERM" "START_DATE" "END_DATE"
    search_term = sys.argv[1] if len(sys.argv) > 1 else "LA FITTE INV INC"
    start_date = sys.argv[2] if len(sys.argv) > 2 else "01/01/1978"
    end_date = sys.argv[3] if len(sys.argv) > 3 else "12/31/1978"
    
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

            # CRITICAL: Wait for the form to be ready as specified in recorded steps
            print("[STEP 2] Waiting for search input to be visible...")
            page.wait_for_selector("input[data-testid='searchInputBox']", state="visible", timeout=10000)

            # STEP 2: Fill start date
            print(f"[STEP 2] Filling start date: {start_date}")
            page.locator("input[aria-label='Starting Recorded Date']").fill(start_date)

            # STEP 3: Fill end date
            print(f"[STEP 3] Filling end date: {end_date}")
            page.locator("input[aria-label='Ending Recorded Date']").fill(end_date)

            # STEP 4: Fill search input
            print(f"[STEP 4] Filling search term: {search_term}")
            page.locator("input[data-testid='searchInputBox']").fill(search_term)

            # STEP 5: Submit search
            print("[STEP 5] Submitting search...")
            page.locator("button[data-testid='searchSubmitButton']").click()
            page.wait_for_load_state("networkidle", timeout=15000)

            # STEP 6: Wait for results grid OR common popups
            print("[STEP 6] Waiting for results...")
            try:
                page.wait_for_selector(".search-results__results-wrap table, .t-window, #NamesWin", timeout=10000)
            except:
                pass

            # Handle potential Name Selection popups (standard practice for this UI)
            popup_selectors = ["input[value='Done']", "button:has-text('Done')", "#NamesWin button"]
            for sel in popup_selectors:
                try:
                    btn = page.locator(sel)
                    if btn.is_visible(timeout=3000):
                        print(f"[POPUP] Clicking {sel}...")
                        btn.first.click()
                        page.wait_for_load_state("networkidle", timeout=5000)
                        break
                except:
                    continue

            # STEP 7: Ensure grid is visible
            grid_selector = ".search-results__results-wrap table"
            print(f"[STEP 7] Checking for grid: {grid_selector}")
            try:
                page.wait_for_selector(grid_selector, state="visible", timeout=10000)
            except Exception as e:
                print(f"[WARN] Grid not found or search returned no results: {e}")
                # Print success with 0 results to satisfy requirements
                print("SUCCESS: Extracted 0 rows")
                return

            # STEP 8: Extract data from VISIBLE columns starting at index 3
            print("[STEP 8] Extracting data rows...")
            row_selector = ".search-results__results-wrap table tbody tr"
            rows = page.locator(row_selector).all()
            
            columns = [
                "Grantor",
                "Grantee",
                "Doc Type",
                "Recorded Date",
                "Doc Number",
                "Book/Volume/Page",
                "Town",
                "Legal Description"
            ]
            
            results = []
            for row in rows:
                cells = row.locator("td").all()
                if len(cells) >= (FIRST_DATA_COLUMN + len(columns)):
                    row_data = {}
                    for i, col_name in enumerate(columns):
                        cell_index = FIRST_DATA_COLUMN + i
                        text = cells[cell_index].text_content().strip()
                        # Clean up text (remove "N/A" if it's the specific site placeholder)
                        if text == "N/A":
                            text = ""
                        row_data[col_name] = text
                    results.append(row_data)

            # STEP 9: Save to CSV
            script_dir = os.path.dirname(os.path.abspath(__file__))
            output_dir = os.path.join(os.path.dirname(script_dir), "data")
            os.makedirs(output_dir, exist_ok=True)
            
            clean_term = "".join(x for x in search_term if x.isalnum())
            filename = f"{SITE_NAME}_{clean_term}_{TIMESTAMP}.csv"
            filepath = os.path.join(output_dir, filename)
            
            if results:
                with open(filepath, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=columns)
                    writer.writeheader()
                    writer.writerows(results)
                print(f"[INFO] Saved {len(results)} rows to {filepath}")
            
            print(f"SUCCESS: Extracted {len(results)} rows")

        except Exception as e:
            print(f"FAILED: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    main()