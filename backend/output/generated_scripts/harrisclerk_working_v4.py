import sys
import os
import csv
import datetime
import time
from playwright.sync_api import sync_playwright

SITE_NAME = "cclerk"
TARGET_URL = "https://www.cclerk.hctx.net/Applications/WebSearch/RP.aspx"
TIMESTAMP = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
FIRST_DATA_COLUMN = 1  # Skip row#, icon columns

def main():
    # USAGE: python script.py "SEARCH_TERM" "START_DATE" "END_DATE"
    search_term = sys.argv[1] if len(sys.argv) > 1 else "SMITH"
    start_date = sys.argv[2] if len(sys.argv) > 2 else "01/01/1980"
    end_date = sys.argv[3] if len(sys.argv) > 3 else datetime.datetime.now().strftime('%m/%d/%Y')
    
    print(f"[INFO] Starting scraper for '{search_term}' (Range: {start_date} - {end_date})")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Fresh context with no storage state
        context = browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/119.0.0.0"
        )
        page = context.new_page()
        
        try:
            # STEP 1: Navigate
            print("[STEP 1] Navigating to URL...")
            page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=10000)
            page.wait_for_load_state("networkidle", timeout=10000)
            time.sleep(1)  # MANDATORY wait
            
            # STEP 2: Fill start date
            print(f"[STEP 2] Filling start date: {start_date}")
            page.locator("#ctl00_ContentPlaceHolder1_txtFrom").fill(start_date)
            time.sleep(1)  # MANDATORY wait
            
            # STEP 3: Fill end date
            print(f"[STEP 3] Filling end date: {end_date}")
            page.locator("#ctl00_ContentPlaceHolder1_txtTo").fill(end_date)
            time.sleep(1)  # MANDATORY wait
            
            # STEP 4: Fill search input
            print(f"[STEP 4] Filling search term: {search_term}")
            page.locator("#ctl00_ContentPlaceHolder1_txtOR").fill(search_term)
            time.sleep(1)  # MANDATORY wait
            
            # STEP 5: Submit search
            print("[STEP 5] Submitting search...")
            page.locator("#ctl00_ContentPlaceHolder1_btnSearch").click()
            page.wait_for_load_state("domcontentloaded", timeout=10000)
            time.sleep(5)  # MANDATORY: Wait 5 seconds - expecting grid results
            
            # STEP 6: Robust Wait for results or popups
            print("[STEP 6] Waiting for results OR popup...")
            try:
                page.wait_for_selector("#itemPlaceholderContainer, #NamesWin, #frmSchTarget, .t-window", timeout=5000)
            except:
                pass

            # Handle Intermediate Popups (e.g., Name Selection)
            popup_selectors = [
                "#frmSchTarget input[type='submit']",
                "input[value='Done']",
                "input[name='btnDone']"
            ]
            for popup_sel in popup_selectors:
                try:
                    popup_btn = page.locator(popup_sel)
                    if popup_btn.is_visible(timeout=3000):
                        print(f"[STEP 6b] Handling popup with {popup_sel}...")
                        popup_btn.first.click()
                        page.wait_for_load_state("networkidle", timeout=10000)
                        time.sleep(5)  # Grid should load after popup
                        break
                except:
                    continue

            # STEP 7: Ensure grid is visible
            print("[STEP 7] Ensuring grid is visible...")
            grid_selector = "#itemPlaceholderContainer"
            try:
                page.locator(grid_selector).wait_for(state="visible", timeout=10000)
                print(f"[STEP 7] Grid found: {grid_selector}")
            except:
                print("[WARNING] Grid not found with primary selector. Checking for table rows.")

            # STEP 8: Extract data
            print("[STEP 8] Extracting rows...")
            # Use tbody tr to skip header rows as per instructions
            rows = page.locator("#itemPlaceholderContainer tbody tr").all()
            
            columns = [
                "File Number",
                "File Date",
                "Type / Vol Page",
                "Names",
                "Legal Description",
                "Pgs",
                "Film Code"
            ]
            
            data = []
            for row in rows:
                cells = row.locator("td").all()
                # Ensure it's a data row and has enough cells
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
            
            # STEP 9: Save to CSV
            script_dir = os.path.dirname(os.path.abspath(__file__))
            output_dir = os.path.join(os.path.dirname(script_dir), "data")
            os.makedirs(output_dir, exist_ok=True)
            
            filename = f"hctx_results_{TIMESTAMP}.csv"
            output_path = os.path.join(output_dir, filename)
            
            if data:
                with open(output_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=columns)
                    writer.writeheader()
                    writer.writerows(data)
                print(f"SUCCESS: Extracted {len(data)} rows to {output_path}")
            else:
                print("SUCCESS: No data found for the given parameters")
            
        except Exception as e:
            print(f"FAILED: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    main()