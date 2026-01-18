import sys
import os
import csv
import datetime
from playwright.sync_api import sync_playwright

SITE_NAME = "dallas"
TARGET_URL = "https://dallas.tx.publicsearch.us/"
TIMESTAMP = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
FIRST_DATA_COLUMN = 3

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
            # STEP 1: Navigate to target URL
            print("[STEP 1] Navigating to URL...")
            page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=45000)
            
            # STEP 2: Fill start date
            print(f"[STEP 2] Filling start date: {start_date}")
            page.fill("input[aria-label=\"Starting Recorded Date\"]", start_date)
            
            # STEP 3: Fill end date
            print(f"[STEP 3] Filling end date: {end_date}")
            page.fill("input[aria-label=\"Ending Recorded Date\"]", end_date)
            
            # STEP 4: Fill search input
            print(f"[STEP 4] Filling search term: {search_term}")
            page.fill("input[data-testid=\"searchInputBox\"]", search_term)
            
            # STEP 5: Submit search
            print("[STEP 5] Clicking search button...")
            page.click("button[data-testid=\"searchSubmitButton\"]")
            
            # STEP 6: Robust wait for results OR popup
            print("[STEP 6] Waiting for results OR popup...")
            try:
                page.wait_for_selector(".a11y-table table, #NamesWin, #frmSchTarget, .t-window", timeout=20000)
            except:
                pass

            # STEP 7: Ensuring grid is visible
            print("[STEP 7] Ensuring grid is visible...")
            page.wait_for_selector(".a11y-table table", timeout=15000)
            
            # STEP 8: Extracting rows
            print("[STEP 8] Extracting rows...")
            # Give a small buffer for the grid to populate after visibility
            page.wait_for_timeout(2000)
            
            rows = page.locator(".a11y-table table tbody tr").all()
            data = []
            
            columns = [
                "Grantor",
                "Grantee",
                "Doc Type",
                "Recorded Date",
                "Doc Number",
                "Book/Volume/Page",
                "Town",
                "Legal Description"
            ]
            
            for row in rows:
                cells = row.locator("td").all()
                if len(cells) > FIRST_DATA_COLUMN:
                    row_data = {}
                    for i, col_name in enumerate(columns):
                        cell_index = FIRST_DATA_COLUMN + i
                        if cell_index < len(cells):
                            # Handle nested spans or direct text
                            text = cells[cell_index].text_content()
                            row_data[col_name] = text.strip() if text else ""
                    data.append(row_data)
            
            # STEP 9: Save to CSV in output/data/ folder
            script_dir = os.path.dirname(os.path.abspath(__file__))
            output_dir = os.path.join(os.path.dirname(script_dir), "data")
            os.makedirs(output_dir, exist_ok=True)
            
            filename = f"{SITE_NAME}_{search_term.replace(' ', '_')}_{TIMESTAMP}.csv"
            filepath = os.path.join(output_dir, filename)
            
            if data:
                with open(filepath, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=columns)
                    writer.writeheader()
                    writer.writerows(data)
                print(f"SUCCESS: Extracted {len(data)} rows to {filepath}")
            else:
                print("No data found to extract.")
            
        except Exception as e:
            print(f"FAILED: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    main()