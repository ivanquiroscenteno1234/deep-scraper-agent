import sys
import os
import csv
import datetime
from playwright.sync_api import sync_playwright

SITE_NAME = "brevardclerk"
TARGET_URL = "https://vaclmweb1.brevardclerk.us/AcclaimWeb/search/SearchTypeName"
TIMESTAMP = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
FIRST_DATA_COLUMN = 2  # Skip row#, icon columns

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
            
            # STEP 2: Accept Disclaimer
            print("[STEP 2] Accepting disclaimer...")
            page.wait_for_selector("#btnButton", timeout=15000)
            page.click("#btnButton")
            page.wait_for_timeout(1000)
            
            # STEP 3: Fill Start Date
            print(f"[STEP 3] Filling start date: {start_date}")
            page.wait_for_selector("#RecordDateFrom", timeout=15000)
            page.fill("#RecordDateFrom", start_date)
            
            # STEP 4: Fill End Date
            print(f"[STEP 4] Filling end date: {end_date}")
            page.fill("#RecordDateTo", end_date)
            
            # STEP 5: Fill Search Term
            print(f"[STEP 5] Filling search name: {search_term}")
            page.fill("#SearchOnName", search_term)
            
            # STEP 6: Submit Search
            print("[STEP 6] Submitting search...")
            page.click("#btnSearch")
            
            # ROBUST WAIT AFTER SEARCH:
            print("[WAIT] Waiting for results OR name selection popup...")
            try:
                page.wait_for_selector("#RsltsGrid, #NamesWin, #frmSchTarget, .t-window", timeout=5000)
            except:
                pass

            # STEP 7: Handle Name Selection Popup (if present)
            if page.locator("#NamesWin input[type='submit']").is_visible():
                print("[STEP 7] Handling name selection popup...")
                page.click("#NamesWin input[type='submit']")
                page.wait_for_timeout(1000)

            # WAIT FOR GRID (RECORDED GRID SELECTOR)
            print("[STEP 8] Ensuring grid is visible...")
            page.wait_for_selector("#RsltsGrid", timeout=5000)
            
            # CHECK FOR CARD/TABLE VIEW TOGGLE
            toggle = page.locator(".toggle-container, [title='Card View'], [aria-label*='Toggle View']").first
            if toggle.count() > 0 and toggle.is_visible():
                print("[INFO] Found Card/Table view toggle - switching to Table View...")
                toggle.click()
                page.wait_for_timeout(1000)
            
            # EXTRACT DATA - START FROM FIRST_DATA_COLUMN
            print("[STEP 9] Extracting rows...")
            rows = page.locator(".t-grid-content tbody tr").all()
            data = []
            columns = [
                "Party Type",
                "Full Name",
                "Cross Party Name",
                "Record Date",
                "Type",
                "Book Type",
                "Book/Page",
                "Clerk File Number",
                "Consideration",
                "First Legal Description",
                "Description",
                "Case #"
            ]
            
            for row in rows:
                # Check for "No records found"
                if "no records to display" in row.text_content().lower():
                    continue
                    
                row_data = {}
                # Try table cells first
                cells = row.locator("td").all()
                
                if cells and len(cells) > FIRST_DATA_COLUMN:
                    for i, col_name in enumerate(columns):
                        cell_index = FIRST_DATA_COLUMN + i
                        if cell_index < len(cells):
                            row_data[col_name] = cells[cell_index].text_content().strip()
                else:
                    # Card-based extraction - fallback if site switches layout
                    for col_name in columns:
                        cell = row.locator(f'[data-id="{col_name}"] p:last-child, [data-id="{col_name}"]:not(:has(p))').first
                        if cell.count() > 0:
                            row_data[col_name] = cell.text_content().strip()
                
                if any(row_data.values()):
                    data.append(row_data)
            
            # STEP 10: Save to CSV in ROOT-LEVEL output/data/ folder
            if data:
                script_dir = os.path.dirname(os.path.abspath(__file__))
                # Scripts are in output/generated_scripts/, go up to output/, then to data/
                output_dir = os.path.join(os.path.dirname(script_dir), "data")
                os.makedirs(output_dir, exist_ok=True)
                
                filename = f"{SITE_NAME}_{search_term.replace(' ', '_')}_{TIMESTAMP}.csv"
                filepath = os.path.join(output_dir, filename)
                
                with open(filepath, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=columns)
                    writer.writeheader()
                    writer.writerows(data)
                
                print(f"SUCCESS: Extracted {len(data)} rows to {filepath}")
            else:
                print("No data found for the given search criteria.")
            
        except Exception as e:
            print(f"FAILED: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    main()