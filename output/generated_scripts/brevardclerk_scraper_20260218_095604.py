import sys
import os
import csv
import datetime
from playwright.sync_api import sync_playwright

SITE_NAME = "brevardclerk"
TARGET_URL = "https://vaclmweb1.brevardclerk.us/AcclaimWeb/search/SearchTypeName"
FIRST_DATA_COLUMN = 2

def main():
    # USAGE: python script.py "SEARCH_TERM" "START_DATE" "END_DATE"
    search_term = sys.argv[1] if len(sys.argv) > 1 else "SMITH"
    start_date = sys.argv[2] if len(sys.argv) > 2 else "01/01/2024"
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
            page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=30000)
            
            # STEP 2: Accept disclaimer
            print("[STEP 2] Accepting disclaimer...")
            try:
                page.wait_for_selector("#btnButton", timeout=5000)
                page.locator("#btnButton").click()
            except:
                print("[INFO] Disclaimer button not found or already accepted.")

            # STEP 3-5: Fill search form
            print(f"[STEP 3-5] Filling search criteria...")
            page.wait_for_selector("#SearchOnName", state="visible", timeout=10000)
            page.locator("#RecordDateFrom").fill(start_date)
            page.locator("#RecordDateTo").fill(end_date)
            page.locator("#SearchOnName").fill(search_term)

            # STEP 6: Submit search
            print("[STEP 6] Submitting search...")
            page.locator("#btnSearch").click()

            # Wait for either the results grid or the specific name selection popup
            # FIX: Removed generic ".t-window" which caused ambiguity with other hidden windows (like DocTypesWin)
            print("[STEP 6] Waiting for results OR name selection popup...")
            page.wait_for_selector("#RsltsGrid, #NamesWin", timeout=20000)

            # STEP 7: Handle name selection popup if it appears (Ground Truth priority)
            if page.locator("#NamesWin").is_visible():
                print("[STEP 7] Handling name selection popup...")
                # Specifically use the selector from GROUND TRUTH
                popup_done_btn = page.locator("#NamesWin input[type='submit']")
                if popup_done_btn.count() > 0:
                    popup_done_btn.first.click()
                
                # After clicking Done, we MUST wait for the results grid
                page.wait_for_selector("#RsltsGrid", state="visible", timeout=20000)

            # STEP 8: Extract Grid Data
            print("[STEP 8] Extracting grid data...")
            # Wait for at least one data row to ensure grid populated
            page.wait_for_selector(".t-grid-content tbody tr", state="visible", timeout=10000)
            
            # Use specific row selector from GROUND TRUTH
            row_selector = ".t-grid-content tbody tr"
            rows = page.locator(f"#RsltsGrid {row_selector}").all()
            
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
            
            data = []
            for row in rows:
                cells = row.locator("td").all()
                # Verify it's a data row (Acclaim grids often have filler or "no results" rows)
                if len(cells) > FIRST_DATA_COLUMN:
                    row_data = {}
                    for i, col_name in enumerate(columns):
                        cell_index = FIRST_DATA_COLUMN + i
                        if cell_index < len(cells):
                            row_data[col_name] = cells[cell_index].text_content().strip()
                    if any(row_data.values()): # Ensure row isn't empty
                        data.append(row_data)

            # STEP 9: Save to CSV
            if data:
                script_dir = os.path.dirname(os.path.abspath(__file__))
                output_dir = os.path.join(os.path.dirname(script_dir), "data")
                os.makedirs(output_dir, exist_ok=True)
                
                filename = f"{SITE_NAME}_results_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                filepath = os.path.join(output_dir, filename)
                
                with open(filepath, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=columns)
                    writer.writeheader()
                    writer.writerows(data)
                
                print(f"SUCCESS: Extracted {len(data)} rows to {filepath}")
            else:
                print("SUCCESS: No rows found matching search criteria.")

        except Exception as e:
            print(f"FAILED: {str(e)}")
        finally:
            browser.close()

if __name__ == "__main__":
    main()