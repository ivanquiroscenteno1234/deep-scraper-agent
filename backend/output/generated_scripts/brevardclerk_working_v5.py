import sys
import os
import csv
import datetime
from playwright.sync_api import sync_playwright

SITE_NAME = "brevardclerk"
TARGET_URL = "https://vaclmweb1.brevardclerk.us/AcclaimWeb/search/SearchTypeName"
TIMESTAMP = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
FIRST_DATA_COLUMN = 1

COLUMNS = [
    "U",
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
    search_term = sys.argv[1] if len(sys.argv) > 1 else "SMITH"
    start_date = sys.argv[2] if len(sys.argv) > 2 else "01/01/2024"
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
            print("[STEP 2] Accepting disclaimer...")
            try:
                disclaimer_btn = page.locator("#btnButton")
                if disclaimer_btn.is_visible(timeout=5000):
                    disclaimer_btn.click()
                    page.wait_for_load_state("domcontentloaded", timeout=5000)
            except:
                pass

            # STEP 3-5: Fill Form
            print("[STEP 3-5] Filling search parameters...")
            page.wait_for_selector("#RecordDateFrom", state="visible", timeout=10000)
            page.locator("#RecordDateFrom").fill(start_date)
            # wait_for_input condition from Ground Truth
            page.wait_for_selector("#SearchOnName", state="visible")
            
            page.locator("#RecordDateTo").fill(end_date)
            page.locator("#SearchOnName").fill(search_term)
            
            # STEP 6: Submit Search
            print("[STEP 6] Submitting search...")
            page.locator("#btnSearch").click()
            
            # Combined wait for Results Grid OR Name Selection Popup
            print("[STEP 6] Waiting for results OR popup...")
            try:
                page.wait_for_selector("#RsltsGrid, #NamesWin, .t-window", timeout=20000)
            except:
                pass

            # STEP 7: Handle Name Selection Popup
            print("[STEP 7] Checking for popup...")
            if page.locator("#NamesWin").is_visible(timeout=3000):
                print("[STEP 7] Clicking popup submit (Done)...")
                # Using .first to avoid strict mode violations if multiple buttons exist
                page.locator("#NamesWin input[type='submit']").first.click()
                # Wait for results grid after popup selection
                page.wait_for_selector("#RsltsGrid", timeout=20000)

            # STEP 8: Extract Data
            print("[STEP 8] Extracting grid data...")
            page.wait_for_selector("#RsltsGrid", state="visible", timeout=15000)
            
            # Wait for rows to be populated (or "No records" to appear)
            try:
                page.wait_for_selector("#RsltsGrid .t-grid-content tbody tr", timeout=10000)
                # Small sleep to allow grid DOM to settle
                page.wait_for_timeout(1000)
            except:
                pass

            rows_locator = page.locator("#RsltsGrid .t-grid-content tbody tr")
            rows = rows_locator.all()
            
            extracted_data = []
            for row in rows:
                cells = row.locator("td").all()
                # Ensure we have enough cells and it's not a "No records" row
                if len(cells) > FIRST_DATA_COLUMN + len(COLUMNS) - 1:
                    row_dict = {}
                    for i, col_name in enumerate(COLUMNS):
                        cell_idx = FIRST_DATA_COLUMN + i
                        if cell_idx < len(cells):
                            row_dict[col_name] = cells[cell_idx].inner_text().strip()
                    if any(row_dict.values()):
                        extracted_data.append(row_dict)

            if not extracted_data:
                # Secondary check for "No records" text
                if "no records" in page.locator("#RsltsGrid").inner_text().lower():
                    print("SUCCESS: No records found for this search.")
                    return

            # STEP 9: Save Results
            script_dir = os.path.dirname(os.path.abspath(__file__))
            output_dir = os.path.join(os.path.dirname(script_dir), "data")
            os.makedirs(output_dir, exist_ok=True)
            
            filename = f"{SITE_NAME}_{TIMESTAMP}.csv"
            filepath = os.path.join(output_dir, filename)
            
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=COLUMNS)
                writer.writeheader()
                writer.writerows(extracted_data)
                
            print(f"SUCCESS: Extracted {len(extracted_data)} rows to {filepath}")
            
        except Exception as e:
            print(f"FAILED: {str(e)}")
        finally:
            browser.close()

if __name__ == "__main__":
    main()