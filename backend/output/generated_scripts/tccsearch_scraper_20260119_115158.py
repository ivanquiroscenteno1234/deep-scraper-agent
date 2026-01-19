import sys
import os
import csv
import datetime
from playwright.sync_api import sync_playwright

# CONFIGURATION
SITE_NAME = "tccsearch"
TARGET_URL = "https://www.tccsearch.org/RealEstate/SearchEntry.aspx"
FIRST_DATA_COLUMN = 3 
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
            print(f"[STEP 1] Navigating to {TARGET_URL}...")
            page.goto(TARGET_URL, wait_until="networkidle", timeout=30000)
            
            # STEP 2: Accept Disclaimer (Ground Truth: #cph1_lnkAccept)
            print("[STEP 2] Accepting disclaimer...")
            try:
                accept_selector = "#cph1_lnkAccept"
                page.wait_for_selector(accept_selector, state="visible", timeout=10000)
                page.locator(accept_selector).click()
                # Wait for the disclaimer modal to disappear and page to settle
                page.wait_for_selector(accept_selector, state="hidden", timeout=10000)
                page.wait_for_load_state("networkidle", timeout=5000)
            except Exception as e:
                print(f"[DEBUG] Disclaimer step skipped or failed: {e}")

            # STEP 3: Fill start date (Ground Truth: #cphNoMargin_f_ddcDateFiledFrom input)
            print(f"[STEP 3] Filling start date: {start_date}")
            page.locator("#cphNoMargin_f_ddcDateFiledFrom input").fill(start_date)
            # Ground Truth wait_for_input hint: ensure party field is ready
            page.wait_for_selector("#cphNoMargin_f_txtParty", state="visible", timeout=5000)
            
            # STEP 4: Fill end date (Ground Truth: #cphNoMargin_f_ddcDateFiledTo input)
            print(f"[STEP 4] Filling end date: {end_date}")
            page.locator("#cphNoMargin_f_ddcDateFiledTo input").fill(end_date)
            
            # STEP 5: Fill search input (Ground Truth: #cphNoMargin_f_txtParty)
            print(f"[STEP 5] Filling search term: {search_term}")
            page.locator("#cphNoMargin_f_txtParty").fill(search_term)
            page.locator("#cphNoMargin_f_txtParty").press("Tab")
            
            # STEP 6: Submit search (Ground Truth: #cphNoMargin_SearchButtons1_btnSearch)
            print("[STEP 6] Submitting search...")
            search_btn_selector = "#cphNoMargin_SearchButtons1_btnSearch"
            # Wait for search button and click
            page.wait_for_selector(search_btn_selector, state="visible", timeout=10000)
            page.locator(search_btn_selector).click()
            
            # STEP 7: Combined wait for result grid or potential name selection popup
            print("[INFO] Waiting for results or name selection...")
            grid_selector = ".ig_ElectricBlueControl"
            # Combined wait: Grid, Name Selection Window, or the specific target frame/popup
            page.wait_for_selector(f"{grid_selector}, #NamesWin, #frmSchTarget, .t-window, #cphNoMargin_f_txtParty", timeout=20000)

            # Handle Name Selection Popup if it appears
            # Scoped selectors for the popup window to avoid strict mode violations
            popup_done_selectors = [
                "#NamesWin input[type='submit']", 
                "#frmSchTarget input[value='Done']", 
                "input[name$='btnDone']", 
                "#btnSelect"
            ]
            for sel in popup_done_selectors:
                try:
                    btn = page.locator(sel).first
                    if btn.is_visible(timeout=3000):
                        print(f"[INFO] Handling popup with selector: {sel}")
                        btn.click()
                        page.wait_for_load_state("networkidle", timeout=5000)
                        break
                except:
                    continue

            # STEP 8: Capture Grid
            print("[STEP 8] Ensuring grid is visible...")
            try:
                page.wait_for_selector(grid_selector, state="visible", timeout=15000)
            except:
                print("[ERROR] Grid not found. Search may have returned no results or stayed on search page.")
                return

            print("[STEP 9] Extracting data rows...")
            # Use Ground Truth grid and row selectors
            rows = page.locator(f"{grid_selector} tbody tr").all()
            
            extracted_data = []
            for row in rows:
                cells = row.locator("td").all()
                # Ground Truth says first_data_column_index is 3
                if len(cells) >= (FIRST_DATA_COLUMN + len(COLUMNS)):
                    row_dict = {}
                    for i, col_name in enumerate(COLUMNS):
                        cell_idx = FIRST_DATA_COLUMN + i
                        text = cells[cell_idx].text_content().strip()
                        row_dict[col_name] = text
                    
                    if row_dict.get("Instrument #") and row_dict["Instrument #"] != "":
                        extracted_data.append(row_dict)

            # STEP 10: Save to CSV
            script_dir = os.path.dirname(os.path.abspath(__file__))
            output_dir = os.path.join(os.path.dirname(script_dir), "data")
            os.makedirs(output_dir, exist_ok=True)
            
            safe_term = "".join([c for c in search_term if c.isalnum() or c==' ']).strip().replace(" ", "_")
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{SITE_NAME}_{safe_term}_{timestamp}.csv"
            filepath = os.path.join(output_dir, filename)
            
            if extracted_data:
                with open(filepath, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=COLUMNS)
                    writer.writeheader()
                    writer.writerows(extracted_data)
                print(f"SUCCESS: Extracted {len(extracted_data)} rows to {filepath}")
            else:
                print("SUCCESS: Search completed but 0 results found.")

        except Exception as e:
            print(f"FAILED: {str(e)}")
        finally:
            browser.close()

if __name__ == "__main__":
    main()