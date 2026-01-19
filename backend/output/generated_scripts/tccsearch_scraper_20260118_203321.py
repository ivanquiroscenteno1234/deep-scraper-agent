import sys
import os
import csv
import datetime
from playwright.sync_api import sync_playwright

SITE_NAME = "tccsearch"
TARGET_URL = "https://www.tccsearch.org/RealEstate/SearchEntry.aspx"
FIRST_DATA_COLUMN = 4

COLUMNS = [
    "Instrument #",
    "Book",
    "Page",
    "Date Filed",
    "Document Type",
    "Name",
    "Associated Name",
    "Legal Description",
    "Status"
]

def main():
    # USAGE: python script.py "SEARCH_TERM" "START_DATE" "END_DATE"
    search_term = sys.argv[1] if len(sys.argv) > 1 else "SMITH"
    start_date = sys.argv[2] if len(sys.argv) > 2 else "01/01/2023"
    end_date = sys.argv[3] if len(sys.argv) > 3 else datetime.datetime.now().strftime('%m/%d/%Y')
    
    print(f"[INFO] Starting scraper for '{search_term}' ({start_date} - {end_date})")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        # Fresh context with no storage state as per Rule 5
        context = browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        try:
            # STEP 1: Navigate
            print("[STEP 1] Navigating to target URL...")
            page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_load_state("networkidle", timeout=10000)
            
            # STEP 2: Accept Disclaimer
            print("[STEP 2] Accepting disclaimer...")
            try:
                accept_btn = page.locator("#cph1_lnkAccept")
                if accept_btn.is_visible(timeout=5000):
                    accept_btn.click()
                    page.wait_for_load_state("domcontentloaded", timeout=5000)
            except Exception as e:
                print(f"[DEBUG] Disclaimer click skipped or failed: {e}")

            # CRITICAL: Wait for search form to be visible before filling (Rule 12)
            print("[INFO] Waiting for search form...")
            page.wait_for_selector("#cphNoMargin_f_txtParty", state="visible", timeout=10000)
            
            # STEP 3: Fill start date
            print(f"[STEP 3] Filling start date: {start_date}")
            page.locator("#cphNoMargin_f_ddcDateFiledFrom input").fill(start_date)
            
            # STEP 4: Fill end date
            print(f"[STEP 4] Filling end date: {end_date}")
            page.locator("#cphNoMargin_f_ddcDateFiledTo input").fill(end_date)
            
            # STEP 5: Fill search input
            print(f"[STEP 5] Filling search term: {search_term}")
            page.locator("#cphNoMargin_f_txtParty").fill(search_term)
            
            # STEP 6: Submit search
            print("[STEP 6] Submitting search...")
            page.locator("#cphNoMargin_SearchButtons1_btnSearch").click()
            page.wait_for_load_state("domcontentloaded", timeout=10000)
            
            # ROBUST WAIT (Rule 3): Wait for grid OR common popup indicators
            print("[STEP 6] Waiting for results OR popup...")
            try:
                page.wait_for_selector(".ig_ElectricBlueControl, #NamesWin, #frmSchTarget, .t-window", timeout=10000)
            except:
                pass

            # Handle dynamic popups (Rule 3 - Prioritize recorded logic)
            # Some searches trigger a "Name Selection" window
            popup_selectors = ["#frmSchTarget input[type='submit']", "input[value='Done']", "input[name='btnDone']", "#NamesWin .t-button"]
            for sel in popup_selectors:
                try:
                    btn = page.locator(sel)
                    if btn.is_visible(timeout=3000):
                        print(f"[STEP 6b] Closing popup with selector: {sel}")
                        btn.first.click()
                        page.wait_for_load_state("networkidle", timeout=10000)
                        break
                except:
                    continue

            # STEP 7: Wait for grid visibility
            print("[STEP 7] Ensuring grid is visible...")
            grid_selector = ".ig_ElectricBlueControl"
            try:
                page.wait_for_selector(grid_selector, state="visible", timeout=15000)
            except Exception as e:
                print(f"[ERROR] Grid not found: {e}")
                # Check for "No Results" messages
                if "No records found" in page.content() or "No results" in page.content():
                    print("SUCCESS: Search returned no results.")
                    return
                raise e

            # STEP 8: Extract Data
            print("[STEP 8] Extracting rows...")
            # Use tbody tr to skip header as per Rule 7 and 10
            row_selector = f"{grid_selector} tbody tr"
            rows = page.locator(row_selector).all()
            
            results = []
            for row in rows:
                cells = row.locator("td").all()
                # Rule 2: Skip rows without enough cells
                if len(cells) > FIRST_DATA_COLUMN:
                    row_data = {}
                    # Rule 2: Match cells[FIRST_DATA_COLUMN + i] to COLUMNS[i]
                    for i, col_name in enumerate(COLUMNS):
                        cell_index = FIRST_DATA_COLUMN + i
                        if cell_index < len(cells):
                            text = cells[cell_index].text_content() or ""
                            row_data[col_name] = text.strip()
                    
                    # Basic validation: ensure row isn't just empty strings or header noise
                    if any(row_data.values()):
                        results.append(row_data)

            # STEP 9: Save to CSV
            script_dir = os.path.dirname(os.path.abspath(__file__))
            output_dir = os.path.join(os.path.dirname(script_dir), "data")
            os.makedirs(output_dir, exist_ok=True)
            
            filename = f"{SITE_NAME}_{search_term}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            filepath = os.path.join(output_dir, filename)
            
            if results:
                with open(filepath, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=COLUMNS)
                    writer.writeheader()
                    writer.writerows(results)
                print(f"SUCCESS: Extracted {len(results)} rows to {filepath}")
            else:
                print("SUCCESS: No data rows found in grid.")

        except Exception as e:
            print(f"FAILED: {str(e)}")
        finally:
            browser.close()

if __name__ == "__main__":
    main()