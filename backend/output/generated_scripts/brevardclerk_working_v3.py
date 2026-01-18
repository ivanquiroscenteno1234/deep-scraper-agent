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
            page.wait_for_load_state("networkidle", timeout=30000)
            
            # STEP 2: Accept Disclaimer
            print("[STEP 2] Accepting disclaimer...")
            page.locator("#btnButton").click()
            page.wait_for_load_state("domcontentloaded", timeout=30000)
            
            # STEP 3: Fill start date
            print("[STEP 3] Filling start date...")
            page.locator("#RecordDateFrom").fill(start_date)
            
            # STEP 4: Fill end date
            print("[STEP 4] Filling end date...")
            page.locator("#RecordDateTo").fill(end_date)
            
            # STEP 5: Fill search name
            print("[STEP 5] Filling search term...")
            page.locator("#SearchOnName").fill(search_term)
            
            # STEP 6: Submit search
            print("[STEP 6] Submitting search...")
            page.locator("#btnSearch").click()
            page.wait_for_load_state("domcontentloaded", timeout=30000)

            # ROBUST WAIT AFTER SEARCH:
            print("[STEP 6] Waiting for results OR popup...")
            try:
                page.wait_for_selector("#RsltsGrid, #NamesWin, #frmSchTarget, .t-window", timeout=15000)
            except:
                pass

            # STEP 7: Handle intermediate name selection popup if it appears
            popup_selectors = ["#frmSchTarget input[type='submit']", "input[value='Done']", "input[name='btnDone']"]
            for popup_sel in popup_selectors:
                try:
                    popup_btn = page.locator(popup_sel)
                    if popup_btn.is_visible(timeout=3000):
                        print(f"[STEP 7] Handling popup with {popup_sel}...")
                        popup_btn.first.click()
                        page.wait_for_load_state("networkidle", timeout=30000)
                        break
                except:
                    continue

            # STEP 8: Ensure grid is visible
            print("[STEP 8] Ensuring grid is visible...")
            grid_found = False
            for selector in ["#RsltsGrid", ".t-grid", "table.table-condensed"]:
                try:
                    grid = page.locator(selector)
                    grid.wait_for(state="visible", timeout=10000)
                    print(f"[STEP 8] Found grid: {selector}")
                    grid_found = True
                    break
                except:
                    continue
            
            if not grid_found:
                print("[ERROR] Grid not found.")
                return

            # EXTRACT DATA
            print("[STEP 9] Extracting rows...")
            columns = [
                "Party Type", "Full Name", "Cross Party Name", "Record Date", 
                "Type", "Book Type", "Book/Page", "Clerk File Number", 
                "Consideration", "First Legal Description", "Description", "Case #"
            ]
            
            rows = page.locator("#RsltsGrid .t-grid-content tbody tr").all()
            data_rows = []
            
            for row in rows:
                cells = row.locator("td").all()
                if len(cells) > FIRST_DATA_COLUMN:
                    row_data = {}
                    for i, col_name in enumerate(columns):
                        cell_index = FIRST_DATA_COLUMN + i
                        if cell_index < len(cells):
                            row_data[col_name] = cells[cell_index].text_content().strip()
                    if any(row_data.values()):
                        data_rows.append(row_data)
            
            # STEP 10: Save to CSV
            script_dir = os.path.dirname(os.path.abspath(__file__))
            output_dir = os.path.join(os.path.dirname(script_dir), "data")
            os.makedirs(output_dir, exist_ok=True)
            
            filename = f"{SITE_NAME}_{search_term.replace(' ', '_')}_{TIMESTAMP}.csv"
            filepath = os.path.join(output_dir, filename)
            
            if data_rows:
                with open(filepath, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=columns)
                    writer.writeheader()
                    writer.writerows(data_rows)
                print(f"SUCCESS: Extracted {len(data_rows)} rows to {filepath}")
            else:
                print("No data found to extract.")
                
        except Exception as e:
            print(f"FAILED: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    main()