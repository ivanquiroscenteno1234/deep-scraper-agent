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
    search_term = sys.argv[1] if len(sys.argv) > 1 else "LA FITTE"
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
            # STEP 1: Navigate
            print("[STEP 1] Navigating to URL...")
            page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_load_state("networkidle", timeout=10000)

            # CRITICAL: Wait for the search form to be visible before interacting
            print("[INFO] Waiting for search form...")
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
            search_button = page.locator("button[data-testid='searchSubmitButton']")
            search_button.click()
            page.wait_for_load_state("domcontentloaded", timeout=10000)
            
            # STEP 6: Handle intermediate states / popups
            print("[STEP 6] Waiting for results OR popup...")
            try:
                # Wait for EITHER the grid OR common popup containers
                page.wait_for_selector(".search-results__results-wrap table, #NamesWin, #frmSchTarget, .t-window", timeout=10000)
            except:
                pass

            # Handle dynamic popups if they appear (Name selection etc)
            popup_selectors = ["input[value='Done']", "input[name='btnDone']", "#frmSchTarget input[type='submit']"]
            for sel in popup_selectors:
                try:
                    btn = page.locator(sel)
                    if btn.is_visible(timeout=3000):
                        print(f"[INFO] Handling popup with {sel}...")
                        btn.first.click()
                        page.wait_for_load_state("networkidle", timeout=10000)
                        break
                except:
                    continue

            # STEP 7: Ensure grid is visible
            print("[STEP 7] Ensuring grid is visible...")
            grid_selector = ".search-results__results-wrap table"
            try:
                page.wait_for_selector(grid_selector, state="visible", timeout=15000)
            except Exception as e:
                print(f"[ERROR] Grid not found: {e}")
                # Take screenshot for debugging if failed
                page.screenshot(path="error_grid_not_found.png")
                return

            # STEP 8: Extract data
            print("[STEP 8] Extracting rows...")
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
            
            # Row selector as defined in rules
            rows = page.locator(".search-results__results-wrap table tbody tr").all()
            data = []
            
            for row in rows:
                cells = row.locator("td").all()
                if len(cells) > FIRST_DATA_COLUMN:
                    row_data = {}
                    for i, col_name in enumerate(columns):
                        cell_index = FIRST_DATA_COLUMN + i
                        if cell_index < len(cells):
                            # Extract text and clean it
                            text = cells[cell_index].text_content().strip()
                            # Handle 'N/A' or empty spans often found in these grids
                            if text == "N/A" or not text:
                                text = ""
                            row_data[col_name] = text
                    data.append(row_data)
            
            # STEP 9: Save to CSV
            script_dir = os.path.dirname(os.path.abspath(__file__))
            output_dir = os.path.join(os.path.dirname(script_dir), "data")
            os.makedirs(output_dir, exist_ok=True)
            
            filename = f"{SITE_NAME}_results_{TIMESTAMP}.csv"
            output_path = os.path.join(output_dir, filename)
            
            with open(output_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=columns)
                writer.writeheader()
                writer.writerows(data)
                
            print(f"SUCCESS: Extracted {len(data)} rows to {output_path}")
            
        except Exception as e:
            print(f"FAILED: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    main()