import sys
import os
import csv
import datetime
from playwright.sync_api import sync_playwright

SITE_NAME = "tccsearch"
TARGET_URL = "https://www.tccsearch.org/RealEstate/SearchEntry.aspx"
TIMESTAMP = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
FIRST_DATA_COLUMN = 4

def main():
    # USAGE: python script.py "SEARCH_TERM" "START_DATE" "END_DATE"
    search_term = sys.argv[1] if len(sys.argv) > 1 else "SMITH & ARMSTRONG INC"
    start_date = sys.argv[2] if len(sys.argv) > 2 else "01/01/2006"
    end_date = sys.argv[3] if len(sys.argv) > 3 else "12/31/2006"
    
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
            page.goto(TARGET_URL, wait_until="networkidle", timeout=30000)
            
            # STEP 2: Accept Disclaimer (GROUND TRUTH)
            print("[STEP 2] Accepting disclaimer...")
            disclaimer_selector = "#cph1_lnkAccept"
            try:
                page.wait_for_selector(disclaimer_selector, state="visible", timeout=5000)
                page.click(disclaimer_selector)
                page.wait_for_load_state("networkidle")
            except:
                print("[INFO] Disclaimer already accepted or not visible.")
            
            # STEP 3: Fill Form Fields (GROUND TRUTH)
            print("[STEP 3] Filling search parameters...")
            # Fill start date
            start_date_input = "#cphNoMargin_f_ddcDateFiledFrom input"
            page.wait_for_selector(start_date_input, state="visible", timeout=10000)
            page.locator(start_date_input).fill(start_date)
            
            # GROUND TRUTH "wait_for_input" requirement
            page.wait_for_selector("#cphNoMargin_f_txtParty", state="visible", timeout=10000)
            
            # Fill end date
            page.locator("#cphNoMargin_f_ddcDateFiledTo input").fill(end_date)
            # Fill search input
            page.locator("#cphNoMargin_f_txtParty").fill(search_term)
            
            # STEP 4: Submit Search (GROUND TRUTH)
            print("[STEP 4] Submitting search...")
            search_btn_selector = "#cphNoMargin_SearchButtons1_btnSearch"
            # Using first() and force=True to handle hidden state violations seen in logs
            page.wait_for_selector(search_btn_selector, state="attached", timeout=10000)
            page.locator(search_btn_selector).first.click(force=True)
            
            # STEP 5: Handle Results OR Name Selection Popup
            print("[STEP 5] Waiting for results or popup...")
            grid_selector = ".ig_ElectricBlueControl"
            popup_indicator = "#NamesWin, #frmSchTarget, .t-window, #cphNoMargin_f_txtNameList"
            
            # Combined wait pattern as per instructions
            try:
                page.wait_for_selector(f"{grid_selector}, {popup_indicator}", timeout=15000)
            except:
                pass

            # Handle Name Selection Popup if it exists
            popup_submit_selectors = [
                "#btnDone", 
                "input[value='Done']", 
                "#NamesWin input[type='submit']",
                "input[name*='btnDone']"
            ]
            for selector in popup_submit_selectors:
                btn = page.locator(selector)
                if btn.count() > 0 and btn.first.is_visible(timeout=3000):
                    print(f"[STEP 5b] Handling popup with {selector}...")
                    btn.first.click()
                    page.wait_for_load_state("networkidle", timeout=10000)
                    break

            # STEP 6: Capture Grid
            print("[STEP 6] Extracting grid data...")
            try:
                page.wait_for_selector(grid_selector, state="visible", timeout=15000)
            except Exception as e:
                if page.locator("text=No records found").is_visible():
                    print("SUCCESS: Search completed but no records were found.")
                    return
                print(f"FAILED: Results grid '{grid_selector}' not found. {e}")
                return

            rows = page.locator(f"{grid_selector} tbody tr").all()
            columns = [
                "Instrument # / Book-Page",
                "Date Filed",
                "Document Type",
                "Name / Associated Name",
                "Legal Description",
                "Status"
            ]
            
            data = []
            for row in rows:
                cells = row.locator("td").all()
                # Use GROUND TRUTH first_data_column_index
                if len(cells) > FIRST_DATA_COLUMN:
                    row_data = {}
                    has_content = False
                    for i, col_name in enumerate(columns):
                        cell_index = FIRST_DATA_COLUMN + i
                        if cell_index < len(cells):
                            val = cells[cell_index].text_content().strip()
                            row_data[col_name] = val
                            if val: has_content = True
                    
                    if has_content:
                        data.append(row_data)
            
            # STEP 7: Save to CSV
            script_dir = os.path.dirname(os.path.abspath(__file__))
            output_dir = os.path.join(os.path.dirname(script_dir), "data")
            os.makedirs(output_dir, exist_ok=True)
            
            filename = f"results_{SITE_NAME}_{TIMESTAMP}.csv"
            filepath = os.path.join(output_dir, filename)
            
            if data:
                with open(filepath, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=columns)
                    writer.writeheader()
                    writer.writerows(data)
                print(f"SUCCESS: Extracted {len(data)} rows to {filepath}")
            else:
                print("SUCCESS: Search completed but no data rows were extracted.")
            
        except Exception as e:
            print(f"FAILED: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    main()