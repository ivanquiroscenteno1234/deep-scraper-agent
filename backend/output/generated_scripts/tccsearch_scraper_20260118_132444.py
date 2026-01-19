import sys
import os
import csv
import datetime
from playwright.sync_api import sync_playwright

SITE_NAME = "tccsearch"
TARGET_URL = "https://www.tccsearch.org/RealEstate/SearchEntry.aspx"
FIRST_DATA_COLUMN = 3

def main():
    # USAGE: python script.py "SEARCH_TERM" "START_DATE" "END_DATE"
    search_term = sys.argv[1] if len(sys.argv) > 1 else "SMITH"
    start_date = sys.argv[2] if len(sys.argv) > 2 else "01/01/2024"
    end_date = sys.argv[3] if len(sys.argv) > 3 else datetime.datetime.now().strftime('%m/%d/%Y')
    
    print(f"[INFO] Starting scraper for '{search_term}' ({start_date} - {end_date})")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/119.0.0.0"
        )
        page = context.new_page()
        
        try:
            # STEP 1: Navigate
            print(f"[STEP 1] Navigating to {TARGET_URL}...")
            page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=30000)
            
            # Handle potential Disclaimer/Acceptance page
            try:
                accept_selectors = ["input[name*='btnAccept']", "input[value*='Accept']", "input[value*='Search as Guest']", "#cphNoMargin_btnAccept"]
                for sel in accept_selectors:
                    btn = page.locator(sel)
                    if btn.is_visible(timeout=5000):
                        print(f"[INFO] Clicking acceptance button: {sel}")
                        btn.click()
                        page.wait_for_load_state("networkidle", timeout=10000)
                        break
            except Exception:
                pass

            # STEP 2: Wait for form and fill start date
            print("[STEP 2] Filling start date...")
            # Using specific selectors from Ground Truth
            start_date_locator = page.locator("#cphNoMargin_f_ddcDateFiledFrom input")
            start_date_locator.wait_for(state="visible", timeout=15000)
            start_date_locator.fill(start_date)
            
            # Ground Truth wait requirement
            page.wait_for_selector("#cphNoMargin_f_txtParty", state="visible", timeout=10000)
            
            # STEP 3: Fill end date
            print("[STEP 3] Filling end date...")
            page.locator("#cphNoMargin_f_ddcDateFiledTo input").fill(end_date)
            
            # STEP 4: Fill search input
            print("[STEP 4] Filling search term...")
            page.locator("#cphNoMargin_f_txtParty").fill(search_term)
            
            # STEP 5: Submit Search
            print("[STEP 5] Submitting search...")
            search_btn = page.locator("#cphNoMargin_SearchButtons1_btnSearch")
            search_btn.click()
            
            # STEP 6: Handle intermediate states (Popups/Lists/Results)
            print("[STEP 6] Waiting for results or name list...")
            # Combined wait for grid OR common popups (NamesWin, frmSchTarget)
            page.wait_for_selector(".ig_ElectricBlueControl, #NamesWin, #frmSchTarget, .t-window", timeout=20000)

            # Handle common name selection popups if they appear
            popup_selectors = ["input[name*='btnDone']", "input[value='Done']", "#cphNoMargin_btnDone", "#btnDone"]
            for sel in popup_selectors:
                btn = page.locator(sel)
                if btn.is_visible(timeout=3000):
                    print(f"[INFO] Dismissing name selection popup with {sel}")
                    btn.first.click()
                    page.wait_for_load_state("networkidle", timeout=10000)
                    break

            # STEP 7: Extract Data
            print("[STEP 7] Extracting data from grid...")
            grid_selector = ".ig_ElectricBlueControl"
            try:
                page.wait_for_selector(grid_selector, timeout=15000)
            except:
                print("[ERROR] Results grid not found. Check if search returned 0 results.")
                return

            columns = [
                "Instrument #", "Book", "Page", "Date Filed", "Document Type", 
                "Name", "Associated Name", "Legal Description", "Status"
            ]
            
            # Get all rows in the results grid
            rows = page.locator(f"{grid_selector} tr").all()
            results = []
            
            for row in rows:
                cells = row.locator("td").all()
                # Skip rows that don't have enough cells based on FIRST_DATA_COLUMN
                if len(cells) > FIRST_DATA_COLUMN:
                    row_data = {}
                    valid_row = False
                    for i, col_name in enumerate(columns):
                        cell_idx = FIRST_DATA_COLUMN + i
                        if cell_idx < len(cells):
                            text = cells[cell_idx].text_content().strip()
                            row_data[col_name] = text
                            if text: valid_row = True
                    
                    if valid_row:
                        results.append(row_data)

            # STEP 8: Save to CSV
            script_dir = os.path.dirname(os.path.abspath(__file__))
            output_dir = os.path.join(os.path.dirname(script_dir), "data")
            os.makedirs(output_dir, exist_ok=True)
            
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"results_{SITE_NAME}_{timestamp}.csv"
            filepath = os.path.join(output_dir, filename)
            
            if results:
                keys = results[0].keys()
                with open(filepath, 'w', newline='', encoding='utf-8') as f:
                    dict_writer = csv.DictWriter(f, fieldnames=keys)
                    dict_writer.writeheader()
                    dict_writer.writerows(results)
                print(f"SUCCESS: Extracted {len(results)} rows to {filepath}")
            else:
                print("SUCCESS: No data found for search criteria (0 rows)")

        except Exception as e:
            print(f"FAILED: {str(e)}")
        finally:
            browser.close()

if __name__ == "__main__":
    main()