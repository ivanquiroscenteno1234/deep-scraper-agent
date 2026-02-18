import sys
import os
import csv
import datetime
import time
from playwright.sync_api import sync_playwright

SITE_NAME = "brevardclerk"
TARGET_URL = "https://vaclmweb1.brevardclerk.us/AcclaimWeb/search/SearchTypeName"
FIRST_DATA_COLUMN = 2  # Skip Row# and icon columns

COLUMNS = [
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

def main():
    # USAGE: python script.py "SEARCH_TERM" "START_DATE" "END_DATE"
    search_term = sys.argv[1] if len(sys.argv) > 1 else "SMITH"
    start_date = sys.argv[2] if len(sys.argv) > 2 else "01/01/2023"
    end_date = sys.argv[3] if len(sys.argv) > 3 else datetime.datetime.now().strftime('%m/%d/%Y')
    
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
            page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=30000)
            
            # STEP 2: Accept Disclaimer
            print("[STEP 2] Checking for disclaimer...")
            try:
                disclaimer_btn = page.locator("#btnButton")
                if disclaimer_btn.is_visible(timeout=5000):
                    disclaimer_btn.click()
                    page.wait_for_load_state("networkidle", timeout=5000)
            except:
                pass

            # WAIT FOR FORM
            print("[STEP 3] Waiting for search form...")
            page.wait_for_selector("#SearchOnName", state="visible", timeout=10000)

            # STEP 3-5: Fill form fields
            print(f"[STEP 3-5] Filling search criteria: {search_term}")
            page.fill("#RecordDateFrom", start_date)
            page.fill("#RecordDateTo", end_date)
            page.fill("#SearchOnName", search_term)
            
            # STEP 6: Submit search
            print("[STEP 6] Submitting search...")
            page.locator("#btnSearch").click()
            page.wait_for_load_state("domcontentloaded", timeout=10000)
            
            # ROBUST WAIT: Result grid or Name Selection popup
            print("[STEP 7] Waiting for results or popup...")
            try:
                page.wait_for_selector("#RsltsGrid, #NamesWin, #frmSchTarget", timeout=10000)
            except:
                pass

            # STEP 7: Handle intermediate name selection popup if it appears
            popup_selector = "#NamesWin #frmSchTarget input[type='submit']"
            try:
                popup_btn = page.locator(popup_selector)
                if popup_btn.is_visible(timeout=3000):
                    print("[STEP 7b] Handling name selection popup...")
                    popup_btn.first.click()
                    page.wait_for_load_state("networkidle", timeout=10000)
            except:
                pass

            # STEP 8: Extract data from grid
            print("[STEP 8] Ensuring grid is visible...")
            grid_selector = "#RsltsGrid"
            page.wait_for_selector(grid_selector, state="visible", timeout=15000)
            
            # ACCLAIMWEB row selector: .t-grid-content tbody tr
            row_selector = f"{grid_selector} .t-grid-content tbody tr"
            rows = page.locator(row_selector).all()
            
            extracted_data = []
            print(f"[STEP 8] Found {len(rows)} potential rows. Extracting...")
            
            for row in rows:
                cells = row.locator("td").all()
                # Check if row has enough cells and isn't a "No records found" row
                if len(cells) > FIRST_DATA_COLUMN:
                    row_dict = {}
                    for i, col_name in enumerate(COLUMNS):
                        cell_idx = FIRST_DATA_COLUMN + i
                        if cell_idx < len(cells):
                            val = cells[cell_idx].text_content().strip()
                            row_dict[col_name] = val
                    
                    if row_dict.get("Full Name"): # Basic validation
                        extracted_data.append(row_dict)

            # STEP 9: Save to CSV
            script_dir = os.path.dirname(os.path.abspath(__file__))
            output_dir = os.path.join(os.path.dirname(script_dir), "data")
            os.makedirs(output_dir, exist_ok=True)
            
            filename = f"{SITE_NAME}_results_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            filepath = os.path.join(output_dir, filename)
            
            if extracted_data:
                with open(filepath, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=COLUMNS)
                    writer.writeheader()
                    writer.writerows(extracted_data)
                print(f"SUCCESS: Extracted {len(extracted_data)} rows to {filepath}")
            else:
                print("SUCCESS: No records found for the given criteria.")

        except Exception as e:
            print(f"FAILED: {str(e)}")
        finally:
            browser.close()

if __name__ == "__main__":
    main()