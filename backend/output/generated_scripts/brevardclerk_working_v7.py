import sys
import os
import csv
import datetime
from playwright.sync_api import sync_playwright

SITE_NAME = "brevardclerk"
TARGET_URL = "https://vaclmweb1.brevardclerk.us/AcclaimWeb/search/SearchTypeName"
TIMESTAMP = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
FIRST_DATA_COLUMN = 2

def main():
    # USAGE: python script.py "SEARCH_TERM" "START_DATE" "END_DATE"
    search_term = sys.argv[1] if len(sys.argv) > 1 else "Lauren Homes"
    start_date = sys.argv[2] if len(sys.argv) > 2 else "01/01/1980"
    end_date = sys.argv[3] if len(sys.argv) > 3 else datetime.datetime.now().strftime('%m/%d/%Y')
    
    print(f"[INFO] Starting scraper for '{search_term}' (Range: {start_date} - {end_date})")
    
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
            page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=15000)
            
            # STEP 2: Accept Disclaimer
            print("[STEP 2] Accepting disclaimer...")
            try:
                page.wait_for_selector("#btnButton", timeout=5000)
                page.click("#btnButton")
            except:
                pass
            
            # STEP 3: Fill search criteria
            print("[STEP 3] Filling search form...")
            page.wait_for_selector("#SearchOnName", state="visible", timeout=10000)
            
            # Ground Truth uses specific order/wait_for_input logic
            page.fill("#RecordDateFrom", start_date)
            # wait_for_input on SearchOnName implies letting potential date-change scripts run
            page.focus("#SearchOnName")
            page.wait_for_timeout(500) 
            
            page.fill("#RecordDateTo", end_date)
            page.fill("#SearchOnName", search_term)
            
            # STEP 6: Submit search
            print("[STEP 6] Submitting search...")
            page.click("#btnSearch")
            
            # COMBINED WAIT: Popup or Grid
            # Using specific selectors from Ground Truth
            popup_sel = "#frmSchTarget input[type='submit']"
            grid_sel = "#RsltsGrid"
            
            print("[STEP 6b] Waiting for results OR name selection popup...")
            try:
                page.wait_for_selector(f"{grid_sel}, {popup_sel}", timeout=20000)
            except:
                pass

            # STEP 7: Handle name selection popup (Ground Truth specific step)
            # Use count/is_visible to check for popup presence
            if page.locator(popup_sel).count() > 0 and page.locator(popup_sel).first.is_visible():
                print("[STEP 7] Handling name selection popup...")
                # Ground Truth says click the submit button in the popup form
                page.locator(popup_sel).first.click()
                # Wait for grid to load after clicking popup (as per Ground Truth wait_for: #RsltsGrid)
                page.wait_for_selector(grid_sel, state="visible", timeout=20000)

            # STEP 8: Extract data from VISIBLE grid columns
            print("[STEP 8] Extracting rows...")
            row_selector = ".t-grid-content tbody tr"
            
            # Wait for grid content to actually populate
            try:
                page.wait_for_selector(row_selector, timeout=15000)
            except:
                print("[INFO] Row selector timeout - checking for 'No records' message.")

            # Ensure data is loaded
            page.wait_for_load_state("networkidle")
            
            rows = page.locator(row_selector).all()
            
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
                row_text = row.inner_text()
                # Skip placeholder rows or empty message rows
                if not row_text.strip() or "No records to display" in row_text:
                    continue
                    
                cells = row.locator("td").all()
                # Based on Ground Truth first_data_column_index: 2
                if len(cells) > FIRST_DATA_COLUMN:
                    row_data = {}
                    for i, col_name in enumerate(columns):
                        cell_index = FIRST_DATA_COLUMN + i
                        if cell_index < len(cells):
                            row_data[col_name] = cells[cell_index].text_content().strip()
                    
                    if any(row_data.values()):
                        data.append(row_data)
            
            # STEP 9: Save to CSV
            if data:
                script_dir = os.path.dirname(os.path.abspath(__file__))
                output_dir = os.path.join(os.path.dirname(script_dir), "data")
                os.makedirs(output_dir, exist_ok=True)
                
                filename = f"{SITE_NAME}_{search_term.replace(' ', '_')}_{TIMESTAMP}.csv"
                filepath = os.path.join(output_dir, filename)
                
                with open(filepath, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=columns)
                    writer.writeheader()
                    writer.writerows(data)
                
                print(f"SUCCESS: Extracted {len(data)} rows to {filename}")
            else:
                print("SUCCESS: No results found for the given criteria.")
                
        except Exception as e:
            print(f"FAILED: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    main()