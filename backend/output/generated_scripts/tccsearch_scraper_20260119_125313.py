import sys
import os
import csv
import datetime
from playwright.sync_api import sync_playwright

# Configuration from Target Info
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
    search_term = sys.argv[1] if len(sys.argv) > 1 else "SMITH & ARMSTRONG INC"
    start_date = sys.argv[2] if len(sys.argv) > 2 else "01/01/2006"
    end_date = sys.argv[3] if len(sys.argv) > 3 else "12/31/2006"
    
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
            print("[STEP 1] Navigating to URL...")
            page.goto(TARGET_URL, wait_until="networkidle")
            
            # STEP 2: Accept Disclaimer
            print("[STEP 2] Accepting disclaimer...")
            disclaimer_btn = page.locator("#cph1_lnkAccept")
            if disclaimer_btn.is_visible(timeout=5000):
                disclaimer_btn.click()
                page.wait_for_load_state("networkidle")

            # STEP 3: Fill start date
            print(f"[STEP 3] Filling start date: {start_date}")
            start_input = page.locator("#cphNoMargin_f_ddcDateFiledFrom input")
            start_input.wait_for(state="visible", timeout=10000)
            start_input.fill(start_date)
            
            # Wait for AJAX or dependency as noted in ground truth
            page.wait_for_selector("#cphNoMargin_f_txtParty", state="visible")
            
            # STEP 4: Fill end date
            print(f"[STEP 4] Filling end date: {end_date}")
            page.locator("#cphNoMargin_f_ddcDateFiledTo input").fill(end_date)
            
            # STEP 5: Fill search term
            print(f"[STEP 5] Filling search term: {search_term}")
            page.locator("#cphNoMargin_f_txtParty").fill(search_term)
            
            # STEP 6: Submit search
            print("[STEP 6] Submitting search...")
            search_btn = page.locator("#cphNoMargin_SearchButtons1_btnSearch")
            search_btn.wait_for(state="attached", timeout=10000)
            # Use dispatch_event to bypass "Element is outside of viewport" errors common in ASP.NET layouts
            search_btn.scroll_into_view_if_needed()
            search_btn.dispatch_event("click")
            
            # Combined wait for results grid or intermediate name selection popup
            print("[WAIT] Waiting for grid or popup...")
            page.wait_for_selector(".ig_ElectricBlueControl, #frmSchTarget, #NamesWin, .t-window", timeout=20000)

            # Handle common intermediate "Name selection" popups
            popup_selectors = ["#frmSchTarget input[type='submit']", "#NamesWin input[value='Done']", "#btnDone", "input[name*='btnDone']"]
            for selector in popup_selectors:
                try:
                    btn = page.locator(selector).first
                    if btn.is_visible(timeout=3000):
                        print(f"[INFO] Handling intermediate popup: {selector}")
                        btn.click()
                        page.wait_for_load_state("networkidle")
                        break
                except:
                    continue

            # STEP 7: Capture Grid
            print("[STEP 7] Extracting data from grid...")
            page.wait_for_selector(".ig_ElectricBlueControl", timeout=20000)
            
            # According to ground truth: Grid is .ig_ElectricBlueControl and rows are tbody tr
            rows = page.locator(".ig_ElectricBlueControl tbody tr").all()
            results = []
            
            for row in rows:
                cells = row.locator("td").all()
                # Use FIRST_DATA_COLUMN (4) to offset extraction
                if len(cells) > (FIRST_DATA_COLUMN + len(COLUMNS) - 1):
                    row_dict = {}
                    has_content = False
                    for i, col_name in enumerate(COLUMNS):
                        target_index = FIRST_DATA_COLUMN + i
                        val = cells[target_index].text_content().strip()
                        row_dict[col_name] = val
                        if val:
                            has_content = True
                    
                    if has_content:
                        results.append(row_dict)

            # STEP 8: Save to CSV
            if results:
                script_dir = os.path.dirname(os.path.abspath(__file__))
                output_dir = os.path.join(os.path.dirname(script_dir), "data")
                os.makedirs(output_dir, exist_ok=True)
                
                filename = f"{SITE_NAME}_{search_term.replace(' ', '_')}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                filepath = os.path.join(output_dir, filename)
                
                with open(filepath, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=COLUMNS)
                    writer.writeheader()
                    writer.writerows(results)
                print(f"SUCCESS: Extracted {len(results)} rows to {filepath}")
            else:
                print("SUCCESS: Search completed but no data rows were found.")

        except Exception as e:
            print(f"FAILED: {str(e)}")
        finally:
            browser.close()

if __name__ == "__main__":
    main()