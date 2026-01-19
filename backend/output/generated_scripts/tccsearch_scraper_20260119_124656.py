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
            page.goto(TARGET_URL, wait_until="load", timeout=30000)
            
            # Handle Disclaimer page (common for TCC sites)
            try:
                # Specific selector for TCC Disclaimer Acceptance
                accept_selector = "#cphNoMargin_btnAccept, input[name*='btnAccept'], #btnAccept"
                if page.locator(accept_selector).is_visible(timeout=5000):
                    print("[STEP 1b] Accepting disclaimer...")
                    page.locator(accept_selector).click()
                    page.wait_for_load_state("networkidle")
            except:
                pass

            # STEP 2: Fill search form
            print("[STEP 2] Waiting for search form anchor...")
            # Using ground truth wait_for_input as anchor
            page.wait_for_selector("#cphNoMargin_f_txtParty", state="visible", timeout=30000)
            
            print("[STEP 3] Filling dates...")
            # Use .first to handle potential strict mode violations with multiple inputs
            page.locator("#cphNoMargin_f_ddcDateFiledFrom input").first.fill(start_date)
            page.locator("#cphNoMargin_f_ddcDateFiledTo input").first.fill(end_date)
            
            print("[STEP 5] Filling search term...")
            page.locator("#cphNoMargin_f_txtParty").fill(search_term)
            
            # STEP 3: Submit search
            print("[STEP 6] Submitting search...")
            page.locator("#cphNoMargin_SearchButtons1_btnSearch").click()
            
            # STEP 4: Robust combined wait for Results Grid or Name Selection Popup
            print("[STEP 7] Waiting for results OR name selection...")
            result_indicators = ".ig_ElectricBlueControl, #cphNoMargin_btnSelectNames, #cphNoMargin_Names1_btnDone, #cphNoMargin_Names1_gvNames"
            page.wait_for_selector(result_indicators, timeout=30000)

            # Handle intermediate name selection if it appears
            if page.locator("#cphNoMargin_btnSelectNames").is_visible():
                print("[STEP 7b] Clicking Select Names...")
                page.locator("#cphNoMargin_btnSelectNames").click()
                page.wait_for_load_state("networkidle")
            elif page.locator("#cphNoMargin_Names1_btnDone").is_visible():
                print("[STEP 7c] Clicking Done on Name selection...")
                page.locator("#cphNoMargin_Names1_btnDone").click()
                page.wait_for_load_state("networkidle")

            # STEP 5: Ensure grid is visible
            grid_selector = ".ig_ElectricBlueControl"
            print("[STEP 8] Ensuring grid is visible...")
            page.wait_for_selector(grid_selector, state="visible", timeout=30000)
            
            # STEP 6: Extract data
            print("[STEP 9] Extracting rows...")
            # Use strict scoping for rows
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
            
            data = []
            for row in rows:
                cells = row.locator("td").all()
                # Check if row has enough cells based on FIRST_DATA_COLUMN (4) + columns length (9)
                if len(cells) >= (FIRST_DATA_COLUMN + len(columns)):
                    row_data = {}
                    has_data = False
                    for i, col_name in enumerate(columns):
                        cell_index = FIRST_DATA_COLUMN + i
                        try:
                            text = cells[cell_index].text_content()
                            val = text.strip() if text else ""
                            row_data[col_name] = val
                            if val: has_data = True
                        except:
                            row_data[col_name] = ""
                    
                    # Validate row has actual content
                    if has_data and (row_data.get("Instrument #") or row_data.get("Name")):
                        data.append(row_data)
            
            # STEP 7: Save to CSV
            script_dir = os.path.dirname(os.path.abspath(__file__))
            output_dir = os.path.join(os.path.dirname(script_dir), "data")
            os.makedirs(output_dir, exist_ok=True)
            
            filename = f"tccsearch_results_{search_term.replace(' ', '_')}_{TIMESTAMP}.csv"
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