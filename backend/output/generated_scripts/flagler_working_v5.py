import sys
import os
import csv
import datetime
import time
from playwright.sync_api import sync_playwright

SITE_NAME = "flagler_records"
TARGET_URL = "https://records.flaglerclerk.com/"
TIMESTAMP = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
FIRST_DATA_COLUMN = 1

def main():
    # USAGE: python script.py "SEARCH_TERM" "START_DATE" "END_DATE"
    search_term = sys.argv[1] if len(sys.argv) > 1 else "SMITH"
    start_date = sys.argv[2] if len(sys.argv) > 2 else "01/01/2023"
    end_date = sys.argv[3] if len(sys.argv) > 3 else datetime.datetime.now().strftime('%m/%d/%Y')
    
    print(f"[INFO] Starting scraper for '{search_term}' ({start_date} - {end_date})")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/119.0.0.0"
        )
        page = context.new_page()
        
        try:
            # STEP 1: Navigate
            print("[STEP 1] Navigating to URL...")
            page.goto(TARGET_URL, wait_until="networkidle", timeout=30000)
            
            # STEP 2: Click Name Search icon
            print("[STEP 2] Clicking Name Search icon...")
            page.wait_for_selector("a[title='Name Search']", state="visible")
            page.locator("a[title='Name Search']").click()
            
            # STEP 3: Accept Disclaimer (Ground Truth Step 3)
            print("[STEP 3] Accepting disclaimer...")
            try:
                page.wait_for_selector("#idAcceptYes", state="visible", timeout=10000)
                page.locator("#idAcceptYes").click()
                # Important: Wait for form to stabilize after disclaimer
                page.wait_for_load_state("networkidle")
            except:
                print("[INFO] Disclaimer not found or already accepted.")

            # STEP 4: Fill Start Date
            print("[STEP 4] Filling start date...")
            page.wait_for_selector("#beginDate-Name", state="visible", timeout=10000)
            # Ensure name field is ready as per Ground Truth suggestion
            page.wait_for_selector("#name-Name", state="attached")
            page.locator("#beginDate-Name").fill(start_date)
            
            # STEP 5: Fill End Date
            print("[STEP 5] Filling end date...")
            page.locator("#endDate-Name").fill(end_date)
            
            # STEP 6: Fill Search Term
            print("[STEP 6] Filling search term...")
            page.locator("#name-Name").fill(search_term)
            page.locator("#name-Name").press("Tab") # Trigger validation
            time.sleep(1)

            # STEP 7: Submit Search
            print("[STEP 7] Submitting search...")
            # Using dispatch_event to bypass potential visibility issues with the 'hide' class
            submit_btn = page.locator("#nameSearchModalSubmit")
            submit_btn.wait_for(state="attached")
            submit_btn.dispatch_event("click")
            
            # STEP 8: Combined Wait for Grid or Name Selection Popup
            print("[STEP 8] Waiting for results or name selection popup...")
            # Use wait_for_selector with combined pattern
            page.wait_for_selector("#RsltsGrid, #idAcceptYes", timeout=20000)
            
            # Check if name selection popup appeared
            if page.locator("#idAcceptYes").is_visible():
                print("[STEP 8] Confirming name selection popup...")
                page.locator("#idAcceptYes").click()
                page.wait_for_selector("#RsltsGrid", state="visible", timeout=15000)

            # STEP 9: Extract Grid Data
            print("[STEP 9] Extracting grid data...")
            page.wait_for_selector("table.dataTable", state="visible", timeout=10000)
            
            columns = [
                "Names",
                "Record Date",
                "Document Type",
                "Book/Page",
                "Instrument #",
                "Legal Description"
            ]
            
            rows = page.locator("table.dataTable tbody tr").all()
            data = []
            
            for row in rows:
                cells = row.locator("td").all()
                # Ground Truth specifies first_data_column_index: 1
                if len(cells) > FIRST_DATA_COLUMN:
                    row_data = {}
                    for i, col_name in enumerate(columns):
                        cell_index = FIRST_DATA_COLUMN + i
                        if cell_index < len(cells):
                            row_data[col_name] = cells[cell_index].text_content().strip()
                    if any(row_data.values()):
                        data.append(row_data)

            # Save to CSV
            if data:
                script_dir = os.path.dirname(os.path.abspath(__file__))
                output_dir = os.path.join(script_dir, "data")
                os.makedirs(output_dir, exist_ok=True)
                filename = f"{SITE_NAME}_{search_term.replace(' ', '_')}_{TIMESTAMP}.csv"
                filepath = os.path.join(output_dir, filename)
                
                with open(filepath, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=columns)
                    writer.writeheader()
                    writer.writerows(data)
                print(f"SUCCESS: Extracted {len(data)} rows to {filepath}")
            else:
                print("SUCCESS: No data found for search criteria")
            
        except Exception as e:
            print(f"FAILED: {str(e)}")
        finally:
            browser.close()

if __name__ == "__main__":
    main()