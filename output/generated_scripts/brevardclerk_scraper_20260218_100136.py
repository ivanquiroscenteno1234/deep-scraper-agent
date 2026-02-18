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
            # STEP 1: Navigate to target URL
            print("[STEP 1] Navigating to URL...")
            page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_load_state("networkidle", timeout=10000)
            
            # STEP 2: Accept Disclaimer
            print("[STEP 2] Accepting disclaimer...")
            try:
                disclaimer_btn = page.locator("#btnButton")
                if disclaimer_btn.is_visible(timeout=5000):
                    disclaimer_btn.click()
                    page.wait_for_load_state("domcontentloaded", timeout=5000)
            except Exception as e:
                print(f"[DEBUG] Disclaimer step skipped or not found: {e}")

            # CRITICAL: Wait for the search form to be visible before filling
            print("[STEP 3] Waiting for search form...")
            page.wait_for_selector("#SearchOnName", state="visible", timeout=10000)

            # STEP 3: Fill start date
            print(f"[STEP 3] Filling start date: {start_date}")
            page.locator("#RecordDateFrom").fill(start_date)

            # STEP 4: Fill end date
            print(f"[STEP 4] Filling end date: {end_date}")
            page.locator("#RecordDateTo").fill(end_date)

            # STEP 5: Fill search input
            print(f"[STEP 5] Filling search term: {search_term}")
            page.locator("#SearchOnName").fill(search_term)

            # STEP 6: Submit search
            print("[STEP 6] Submitting search...")
            page.locator("#btnSearch").click()
            page.wait_for_load_state("domcontentloaded", timeout=10000)

            # Wait for results or intermediate name selection popup
            print("[STEP 6.1] Waiting for results OR popup...")
            try:
                page.wait_for_selector("#RsltsGrid, #NamesWin, #frmSchTarget, .t-window", timeout=10000)
            except:
                pass

            # STEP 7: Handle name selection popup (if it appears)
            print("[STEP 7] Checking for name selection popup...")
            try:
                popup_submit = page.locator("#frmSchTarget input[type='submit']")
                if popup_submit.is_visible(timeout=5000):
                    print("[STEP 7] Clicking popup submit button...")
                    popup_submit.click()
                    page.wait_for_load_state("networkidle", timeout=10000)
            except Exception as e:
                print(f"[DEBUG] No popup handled: {e}")

            # Wait for grid to be visible
            print("[STEP 8] Ensuring results grid is visible...")
            try:
                page.wait_for_selector("#RsltsGrid", state="visible", timeout=15000)
            except:
                print("[ERROR] Results grid #RsltsGrid not found.")
                # Fallback check for any grid-like structure
                if not page.locator(".t-grid-content").is_visible():
                    raise Exception("Results grid never appeared.")

            # STEP 8: Capture visible grid columns only
            print("[STEP 8] Extracting data from grid...")
            # For AcclaimWeb sites, rows are in .t-grid-content tbody tr
            rows = page.locator("#RsltsGrid .t-grid-content tbody tr").all()
            
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
            
            results = []
            for row in rows:
                cells = row.locator("td").all()
                if len(cells) > FIRST_DATA_COLUMN:
                    row_data = {}
                    for i, col_name in enumerate(columns):
                        cell_index = FIRST_DATA_COLUMN + i
                        if cell_index < len(cells):
                            row_data[col_name] = cells[cell_index].text_content().strip()
                    results.append(row_data)

            # Save to CSV
            if results:
                script_dir = os.path.dirname(os.path.abspath(__file__))
                output_dir = os.path.join(os.path.dirname(script_dir), "data")
                os.makedirs(output_dir, exist_ok=True)
                
                filename = f"{SITE_NAME}_results_{TIMESTAMP}.csv"
                filepath = os.path.join(output_dir, filename)
                
                with open(filepath, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=columns)
                    writer.writeheader()
                    writer.writerows(results)
                
                print(f"SUCCESS: Extracted {len(results)} rows to {filepath}")
            else:
                print("SUCCESS: Search completed but no data rows found.")

        except Exception as e:
            print(f"FAILED: {str(e)}")
        finally:
            browser.close()

if __name__ == "__main__":
    main()