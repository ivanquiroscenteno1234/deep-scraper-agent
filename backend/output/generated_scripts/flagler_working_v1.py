import sys
import os
import csv
import datetime
from playwright.sync_api import sync_playwright

SITE_NAME = "records"
TARGET_URL = "https://records.flaglerclerk.com/"
TIMESTAMP = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
FIRST_DATA_COLUMN = 3  # Skip row#, icon columns
COLUMNS = [
    "Names",
    "Record Date",
    "Type",
    "Book",
    "Page",
    "Instrument #",
    "Case #",
    "Consideration",
    "Legal Description"
]

def main():
    # USAGE: python script.py "SEARCH_TERM" "START_DATE" "END_DATE"
    search_term = sys.argv[1] if len(sys.argv) > 1 else "SMITH"
    start_date = sys.argv[2] if len(sys.argv) > 2 else "01/01/1980"
    end_date = sys.argv[3] if len(sys.argv) > 3 else datetime.datetime.now().strftime('%m/%d/%Y')
    
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
            page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=45000)
            
            # STEP 2: Click search criteria name
            print("[STEP 2] Selecting Search Criteria...")
            page.click("a[onclick*='searchCriteriaName']")
            
            # STEP 3: Accept disclaimer
            print("[STEP 3] Accepting disclaimer...")
            page.wait_for_selector("#idAcceptYes", timeout=10000)
            page.click("#idAcceptYes")
            
            # STEP 4: Fill start date
            print(f"[STEP 4] Filling start date: {start_date}")
            page.wait_for_selector("#beginDate-Name", timeout=10000)
            page.fill("#beginDate-Name", start_date)
            
            # STEP 5: Fill end date
            print(f"[STEP 5] Filling end date: {end_date}")
            page.fill("#endDate-Name", end_date)
            
            # STEP 6: Fill search term
            print(f"[STEP 6] Filling search term: {search_term}")
            page.fill("#name-Name", search_term)
            
            # STEP 7: Submit search
            print("[STEP 7] Submitting search...")
            page.click("#submit-Name")
            
            # STEP 8: Robust wait for results or intermediate popup
            print("[STEP 8] Waiting for results or name selection popup...")
            try:
                page.wait_for_selector("#resultsTable, #idAcceptYes, #NamesWin, #frmSchTarget, .t-window", timeout=20000)
                
                # Check if the "Accept Yes" button for name selection popup appeared
                if page.is_visible("#idAcceptYes"):
                    print("[INFO] Handling name selection popup...")
                    page.click("#idAcceptYes")
            except Exception as e:
                print(f"[DEBUG] Transition wait notice: {e}")

            # WAIT FOR GRID
            print("[STEP 9] Ensuring grid is visible...")
            page.wait_for_selector("#resultsTable", timeout=20000)
            
            # Wait a moment for rows to render fully
            page.wait_for_timeout(2000)
            
            # EXTRACT DATA
            print("[STEP 10] Extracting rows...")
            rows = page.locator("#resultsTable tbody tr").all()
            results_data = []
            
            for row in rows:
                cells = row.locator("td").all()
                if len(cells) > FIRST_DATA_COLUMN:
                    row_data = {}
                    for i, col_name in enumerate(COLUMNS):
                        cell_index = FIRST_DATA_COLUMN + i
                        if cell_index < len(cells):
                            text = cells[cell_index].inner_text().strip()
                            row_data[col_name] = text
                    
                    if any(row_data.values()):
                        results_data.append(row_data)
            
            # SAVE TO CSV in standardized output/data/ folder
            if results_data:
                script_dir = os.path.dirname(os.path.abspath(__file__))
                # script_dir is backend/output/generated_scripts, go up to backend/output/data
                output_dir = os.path.join(os.path.dirname(script_dir), "data")
                os.makedirs(output_dir, exist_ok=True)
                filename = os.path.join(output_dir, f"{SITE_NAME}_{search_term.replace(' ', '_')}_{TIMESTAMP}.csv")
                with open(filename, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=COLUMNS)
                    writer.writeheader()
                    writer.writerows(results_data)
                print(f"SUCCESS: Extracted {len(results_data)} rows to {filename}")
            else:
                print("No data found for the given search criteria.")
            
        except Exception as e:
            print(f"FAILED: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    main()