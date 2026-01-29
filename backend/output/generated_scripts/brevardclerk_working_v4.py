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
            print("[STEP 1] Navigating to target URL...")
            page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_load_state("networkidle", timeout=5000)
            
            # STEP 2: Accept Disclaimer
            print("[STEP 2] Accepting disclaimer...")
            try:
                disclaimer_btn = page.locator("#btnButton")
                if disclaimer_btn.is_visible(timeout=5000):
                    disclaimer_btn.click()
                    page.wait_for_load_state("domcontentloaded", timeout=5000)
            except:
                pass

            # WAIT FOR FORM
            page.wait_for_selector("#SearchOnName", state="visible", timeout=10000)
            
            # STEP 3-5: Fill form fields
            print("[STEP 3-5] Filling search parameters...")
            page.locator("#RecordDateFrom").fill(start_date)
            page.locator("#RecordDateTo").fill(end_date)
            page.locator("#SearchOnName").fill(search_term)
            
            # STEP 6: Submit search
            print("[STEP 6] Submitting search...")
            page.locator("#btnSearch").click()
            page.wait_for_load_state("domcontentloaded", timeout=5000)
            
            # ROBUST WAIT FOR RESULTS OR POPUP
            print("[STEP 6] Waiting for results OR name selection popup...")
            try:
                page.wait_for_selector("#RsltsGrid, #NamesWin, #frmSchTarget, .t-window", timeout=10000)
            except:
                pass

            # STEP 7: Handle Name Selection Popup if it appears
            popup_selector = "#frmSchTarget input[type='submit']"
            try:
                popup_btn = page.locator(popup_selector)
                if popup_btn.is_visible(timeout=3000):
                    print("[STEP 7] Handling name selection popup...")
                    popup_btn.first.click()
                    page.wait_for_load_state("networkidle", timeout=5000)
            except:
                pass

            # STEP 8: Extract Data
            print("[STEP 8] Ensuring results grid is visible...")
            grid_selector = "#RsltsGrid"
            try:
                page.wait_for_selector(grid_selector, state="visible", timeout=10000)
            except Exception as e:
                print(f"[ERROR] Grid not found: {e}")
                return

            print("[STEP 8] Extracting data rows...")
            # For AcclaimWeb/Telerik sites, rows are in .t-grid-content
            row_selector = "#RsltsGrid .t-grid-content tbody tr"
            rows = page.locator(row_selector).all()
            
            columns = [
                "Party Type", "Full Name", "Cross Party Name", "Record Date",
                "Type", "Book Type", "Book/Page", "Clerk File Number",
                "Consideration", "First Legal Description", "Description", "Case #"
            ]
            
            extracted_data = []
            for row in rows:
                cells = row.locator("td").all()
                if len(cells) > FIRST_DATA_COLUMN:
                    row_dict = {}
                    for i, col_name in enumerate(columns):
                        cell_index = FIRST_DATA_COLUMN + i
                        if cell_index < len(cells):
                            row_dict[col_name] = cells[cell_index].text_content().strip()
                    extracted_data.append(row_dict)
            
            # Save to CSV
            script_dir = os.path.dirname(os.path.abspath(__file__))
            output_dir = os.path.join(os.path.dirname(script_dir), "data")
            os.makedirs(output_dir, exist_ok=True)
            
            filename = f"{SITE_NAME}_{search_term}_{TIMESTAMP}.csv"
            filepath = os.path.join(output_dir, filename)
            
            if extracted_data:
                with open(filepath, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=columns)
                    writer.writeheader()
                    writer.writerows(extracted_data)
                print(f"SUCCESS: Extracted {len(extracted_data)} rows to {filepath}")
            else:
                print("SUCCESS: No results found matching criteria.")
                
        except Exception as e:
            print(f"FAILED: {str(e)}")
        finally:
            browser.close()

if __name__ == "__main__":
    main()