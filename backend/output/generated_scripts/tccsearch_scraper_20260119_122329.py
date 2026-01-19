import sys
import os
import csv
import datetime
from playwright.sync_api import sync_playwright

SITE_NAME = "tccsearch"
TARGET_URL = "https://www.tccsearch.org/RealEstate/SearchEntry.aspx"
TIMESTAMP = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
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
            page.goto(TARGET_URL, wait_until="networkidle", timeout=60000)
            
            # Handle Disclaimer page - use more specific selector to ensure it clears
            try:
                disclaimer_selector = "#cphNoMargin_btnAccept"
                if page.locator(disclaimer_selector).is_visible(timeout=5000):
                    print("[INFO] Disclaimer found, clicking Accept...")
                    page.locator(disclaimer_selector).click()
                    page.wait_for_load_state("networkidle")
            except:
                pass
            
            # STEP 2-4: Fill form fields using GROUND TRUTH selectors
            print("[STEP 2] Waiting for form fields...")
            # Ensure the specific input inside the container is visible to avoid strict mode violations
            date_from_selector = "#cphNoMargin_f_ddcDateFiledFrom input"
            page.wait_for_selector(date_from_selector, timeout=20000)
            
            print(f"[STEP 2] Filling start date: {start_date}")
            page.locator(date_from_selector).first.fill(start_date)
            
            print(f"[STEP 3] Filling end date: {end_date}")
            page.locator("#cphNoMargin_f_ddcDateFiledTo input").first.fill(end_date)
            
            print(f"[STEP 4] Filling search input: {search_term}")
            page.locator("#cphNoMargin_f_txtParty").first.fill(search_term)
            
            # STEP 5: Submit search
            print("[STEP 5] Submitting search...")
            page.locator("#cphNoMargin_SearchButtons1_btnSearch").click()
            
            # STEP 6: Combined wait for results or intermediate name selection popup
            print("[STEP 6] Waiting for grid or name selection...")
            grid_selector = ".ig_ElectricBlueControl"
            popup_selector = "#frmSchTarget, #NamesWin"
            page.wait_for_selector(f"{grid_selector}, {popup_selector}", timeout=30000)

            # Handle potential Name Selection popups (intermediate state)
            if page.locator("#frmSchTarget").is_visible():
                print("[STEP 6b] Handling name selection popup (#frmSchTarget)...")
                page.locator("#frmSchTarget input[type='submit']").first.click()
                page.wait_for_selector(grid_selector, timeout=30000)
            elif page.locator("#NamesWin").is_visible():
                print("[STEP 6b] Handling name selection popup (#NamesWin)...")
                page.locator("#NamesWin input[value='Done']").first.click()
                page.wait_for_selector(grid_selector, timeout=30000)

            # STEP 7: Extract Data
            print("[STEP 7] Extracting rows...")
            page.wait_for_selector(f"{grid_selector} tr", timeout=10000)
            rows = page.locator(f"{grid_selector} tr").all()
            data = []
            
            for row in rows:
                cells = row.locator("td").all()
                # Skip rows that don't have enough cells based on FIRST_DATA_COLUMN
                if len(cells) > FIRST_DATA_COLUMN:
                    row_data = {}
                    has_content = False
                    for i, col_name in enumerate(COLUMNS):
                        cell_index = FIRST_DATA_COLUMN + i
                        if cell_index < len(cells):
                            val = cells[cell_index].text_content().strip()
                            if val:
                                has_content = True
                            row_data[col_name] = val
                    
                    if has_content:
                        data.append(row_data)
            
            # STEP 8: Save to CSV
            script_dir = os.path.dirname(os.path.abspath(__file__))
            output_dir = os.path.join(os.path.dirname(script_dir), "output", "data")
            os.makedirs(output_dir, exist_ok=True)
            
            filename = f"{SITE_NAME}_{search_term.replace(' ', '_')}_{TIMESTAMP}.csv"
            output_path = os.path.join(output_dir, filename)
            
            if data:
                with open(output_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=COLUMNS)
                    writer.writeheader()
                    writer.writerows(data)
                print(f"SUCCESS: Extracted {len(data)} rows to {output_path}")
            else:
                print("SUCCESS: No results found for the given criteria.")
                with open(output_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=COLUMNS)
                    writer.writeheader()
            
        except Exception as e:
            print(f"FAILED: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    main()