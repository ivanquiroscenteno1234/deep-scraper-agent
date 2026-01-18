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
    search_term = sys.argv[1] if len(sys.argv) > 1 else "SMITH"
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
            page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=15000)
            
            # STEP 2: Accept Disclaimer
            print("[STEP 2] Accepting disclaimer...")
            disclaimer_btn = page.locator("#cph1_lnkAccept")
            if disclaimer_btn.is_visible(timeout=5000):
                disclaimer_btn.click()
                page.wait_for_load_state("networkidle", timeout=5000)
            
            # Wait for search form
            page.wait_for_selector("#cphNoMargin_f_txtParty", state="visible", timeout=10000)

            # STEP 3: Fill start date
            print(f"[STEP 3] Filling start date: {start_date}")
            start_date_input = page.locator("#cphNoMargin_f_ddcDateFiledFrom input")
            start_date_input.fill(start_date)
            # Ground Truth wait_for_input condition
            page.wait_for_selector("#cphNoMargin_f_txtParty", state="visible")
            
            # STEP 4: Fill end date
            print(f"[STEP 4] Filling end date: {end_date}")
            page.locator("#cphNoMargin_f_ddcDateFiledTo input").fill(end_date)
            
            # STEP 5: Fill search input
            print(f"[STEP 5] Filling search term: {search_term}")
            page.locator("#cphNoMargin_f_txtParty").fill(search_term)
            
            # STEP 6: Submit search
            print("[STEP 6] Submitting search...")
            search_btn = page.locator("#cphNoMargin_SearchButtons1_btnSearch")
            search_btn.scroll_into_view_if_needed()
            # Use dispatch_event to bypass viewport issues in legacy ASP.NET layouts
            search_btn.dispatch_event("click")
            
            # ROBUST WAIT: Result grid or Name Selection popup (Combined Wait Pattern)
            print("[STEP 6] Waiting for results OR popup...")
            try:
                page.wait_for_selector(".ig_ElectricBlueControl, #NamesWin, #frmSchTarget, .t-window", timeout=20000)
            except:
                pass

            # Handle potential name selection popups
            popup_submit_selectors = [
                "#NamesWin input[type='submit']", 
                "#frmSchTarget input[type='submit']", 
                "input[value='Done']", 
                "input[name*='btnDone']"
            ]
            for popup_sel in popup_submit_selectors:
                try:
                    btn = page.locator(popup_sel).first
                    if btn.is_visible(timeout=3000):
                        print(f"[STEP 6b] Handling popup/list selection...")
                        btn.click()
                        page.wait_for_load_state("networkidle", timeout=10000)
                        break
                except:
                    continue

            # STEP 7: Wait for Grid
            print("[STEP 7] Waiting for results grid...")
            grid_selector = ".ig_ElectricBlueControl"
            grid_found = False
            try:
                page.wait_for_selector(grid_selector, timeout=10000)
                grid_found = True
            except:
                print("[WARNING] Grid not found within timeout. No results or slow load.")
            
            data = []
            if grid_found:
                # STEP 8: Extract Data
                print("[STEP 8] Extracting rows...")
                # Using Ground Truth row selector pattern
                rows = page.locator(f"{grid_selector} tbody tr").all()
                
                columns = [
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

                for row in rows:
                    cells = row.locator("td").all()
                    # Skip header/padding rows (Instrument # mapping begins at col index 4)
                    if len(cells) > FIRST_DATA_COLUMN:
                        row_data = {}
                        has_content = False
                        for i, col_name in enumerate(columns):
                            cell_index = FIRST_DATA_COLUMN + i
                            if cell_index < len(cells):
                                text = cells[cell_index].text_content().strip()
                                row_data[col_name] = text
                                if text: has_content = True
                        
                        if has_content and row_data.get("Instrument #"):
                            data.append(row_data)

            # STEP 9: Save to CSV
            script_dir = os.path.dirname(os.path.abspath(__file__))
            output_dir = os.path.join(os.path.dirname(script_dir), "data")
            os.makedirs(output_dir, exist_ok=True)
            
            safe_term = "".join([c for c in search_term if c.isalnum() or c in (' ', '_')]).strip().replace(' ', '_')
            filename = f"{SITE_NAME}_{safe_term}_{TIMESTAMP}.csv"
            filepath = os.path.join(output_dir, filename)
            
            if data:
                with open(filepath, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=columns)
                    writer.writeheader()
                    writer.writerows(data)
                print(f"SUCCESS: Extracted {len(data)} rows to {filepath}")
            else:
                print("SUCCESS: No data found for the given criteria.")
                
        except Exception as e:
            print(f"FAILED: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    main()