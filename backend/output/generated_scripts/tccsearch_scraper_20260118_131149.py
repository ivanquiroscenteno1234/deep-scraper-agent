import sys
import os
import csv
import datetime
from playwright.sync_api import sync_playwright

SITE_NAME = "tccsearch"
TARGET_URL = "https://www.tccsearch.org/RealEstate/SearchEntry.aspx"
FIRST_DATA_COLUMN = 4  # Skip row#, icons, etc.
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
    search_term = sys.argv[1] if len(sys.argv) > 1 else "SMITH"
    start_date = sys.argv[2] if len(sys.argv) > 2 else "01/01/2023"
    end_date = sys.argv[3] if len(sys.argv) > 3 else datetime.datetime.now().strftime('%m/%d/%Y')
    
    print(f"[INFO] Starting scraper for '{search_term}' ({start_date} to {end_date})")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            viewport={'width': 1280, 'height': 1000},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/119.0.0.0"
        )
        page = context.new_page()
        
        try:
            # STEP 1: Navigate
            print("[STEP 1] Navigating to URL...")
            page.goto(TARGET_URL, wait_until="networkidle", timeout=30000)
            
            # STEP 2: Accept Disclaimer (Ground Truth selector)
            print("[STEP 2] Accepting disclaimer...")
            disclaimer_selector = "#cph1_lnkAccept"
            try:
                page.wait_for_selector(disclaimer_selector, state="visible", timeout=10000)
                page.locator(disclaimer_selector).click()
                page.wait_for_load_state("networkidle")
            except Exception:
                print("[INFO] Disclaimer not found or already bypassed.")

            # STEP 3-5: Fill search parameters (Ground Truth selectors)
            print("[STEP 3-5] Filling search parameters...")
            
            # Fill start date and wait for the search term input as per Ground Truth hints
            start_date_selector = "#cphNoMargin_f_ddcDateFiledFrom input"
            page.wait_for_selector(start_date_selector, state="visible", timeout=10000)
            page.locator(start_date_selector).fill(start_date)
            
            # Use Ground Truth wait hint
            page.wait_for_selector("#cphNoMargin_f_txtParty", state="visible", timeout=10000)
            
            # Fill end date
            page.locator("#cphNoMargin_f_ddcDateFiledTo input").fill(end_date)
            
            # Fill search term
            page.locator("#cphNoMargin_f_txtParty").fill(search_term)
            
            # STEP 6: Submit search (Handling hidden element issue)
            print("[STEP 6] Submitting search...")
            search_btn_selector = "#cphNoMargin_SearchButtons1_btnSearch"
            # Some sites have multiple hidden inputs for different views; target the visible one specifically
            search_btn = page.locator(search_btn_selector).filter(has_not_text="").first
            search_btn.scroll_into_view_if_needed()
            # If wait_for visible fails, we force the click as the button exists but might be size 0
            search_btn.click(force=True)
            
            # STEP 7: Handle Grid or Popups (Combined wait pattern)
            print("[STEP 7] Waiting for results...")
            grid_selector = ".ig_ElectricBlueControl"
            popup_selector = "#NamesWin, #frmSchTarget, .t-window"
            
            # Combined wait as per instructions
            page.wait_for_selector(f"{grid_selector}, {popup_selector}", timeout=20000)

            # Handle Name Selection popup if it appears
            if page.locator("#frmSchTarget").is_visible():
                print("[INFO] Handling Name Selection popup...")
                # Use specific scope for the popup button
                popup_btn = page.locator("#frmSchTarget input[type='submit'], #frmSchTarget input[value='Done']").first
                if popup_btn.is_visible():
                    popup_btn.click()
                    page.wait_for_load_state("networkidle")

            # STEP 8: Extract data
            print("[STEP 8] Extracting grid data...")
            page.wait_for_selector(grid_selector, state="visible", timeout=15000)
            
            # Use Ground Truth row selector: .ig_ElectricBlueControl tbody tr
            rows = page.locator(f"{grid_selector} tbody tr").all()
            data = []
            
            for row in rows:
                cells = row.locator("td").all()
                # Use FIRST_DATA_COLUMN (4) as per Ground Truth
                if len(cells) > FIRST_DATA_COLUMN:
                    row_data = {}
                    has_content = False
                    for i, col_name in enumerate(COLUMNS):
                        cell_index = FIRST_DATA_COLUMN + i
                        if cell_index < len(cells):
                            val = cells[cell_index].inner_text().strip()
                            row_data[col_name] = val
                            if val: has_content = True
                    
                    if has_content:
                        data.append(row_data)

            # STEP 9: Save to CSV
            if data:
                script_dir = os.path.dirname(os.path.abspath(__file__))
                output_dir = os.path.join(os.path.dirname(script_dir), "data")
                os.makedirs(output_dir, exist_ok=True)
                
                timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"{SITE_NAME}_{search_term.replace(' ', '_')}_{timestamp}.csv"
                filepath = os.path.join(output_dir, filename)
                
                with open(filepath, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=COLUMNS)
                    writer.writeheader()
                    writer.writerows(data)
                print(f"SUCCESS: Extracted {len(data)} rows to {filename}")
            else:
                print("SUCCESS: No data found for the given criteria.")

        except Exception as e:
            print(f"FAILED: {str(e)}")
        finally:
            browser.close()

if __name__ == "__main__":
    main()