import sys
import os
import csv
import datetime
from playwright.sync_api import sync_playwright

SITE_NAME = "cclerk"
TARGET_URL = "https://www.cclerk.hctx.net/Applications/WebSearch/RP.aspx"
TIMESTAMP = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
FIRST_DATA_COLUMN = 1

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
            
            # STEP 2: Fill start date
            print("[STEP 2] Filling start date...")
            page.fill("#ctl00_ContentPlaceHolder1_txtFrom", start_date)
            
            # STEP 3: Fill end date
            print("[STEP 3] Filling end date...")
            page.fill("#ctl00_ContentPlaceHolder1_txtTo", end_date)
            
            # STEP 4: Fill search input
            print("[STEP 4] Filling search input...")
            page.fill("#ctl00_ContentPlaceHolder1_txtOR", search_term)
            
            # STEP 5: Click search
            print("[STEP 5] Submitting search...")
            page.locator("#ctl00_ContentPlaceHolder1_btnSearch").click()
            page.wait_for_load_state("domcontentloaded", timeout=30000)
            
            # ROBUST WAIT AFTER SEARCH
            print("[STEP 6] Waiting for results OR popup...")
            try:
                page.wait_for_selector("#itemPlaceholderContainer, #NamesWin, #frmSchTarget, .t-window", timeout=20000)
            except:
                pass

            # STEP 7: Ensure grid is visible
            print("[STEP 7] Ensuring grid is visible...")
            page.wait_for_selector("#itemPlaceholderContainer", timeout=15000)
            
            # EXTRACT DATA
            print("[STEP 8] Extracting rows...")
            # Target the tbody tr within the specific container
            rows = page.locator("#itemPlaceholderContainer tbody tr").all()
            
            columns = [
                "File Number",
                "File Date",
                "Type Vol Page",
                "Names",
                "Legal Description",
                "Pgs",
                "Film Code"
            ]
            
            data = []
            for row in rows:
                cells = row.locator("td").all()
                # Ensure it's a data row and not a header or nested row
                if len(cells) >= (FIRST_DATA_COLUMN + len(columns)):
                    # Check if the row contains actual data (e.g., File Number exists)
                    row_data = {}
                    for i, col_name in enumerate(columns):
                        cell_index = FIRST_DATA_COLUMN + i
                        if cell_index < len(cells):
                            text = cells[cell_index].text_content().strip()
                            # Clean up whitespace/newlines commonly found in these grids
                            row_data[col_name] = " ".join(text.split())
                    
                    if row_data.get("File Number"):
                        data.append(row_data)
            
            # STEP 9: Save to CSV
            script_dir = os.path.dirname(os.path.abspath(__file__))
            output_dir = os.path.join(os.path.dirname(script_dir), "data")
            os.makedirs(output_dir, exist_ok=True)
            
            filename = f"{SITE_NAME}_{search_term.replace(' ', '_')}_{TIMESTAMP}.csv"
            filepath = os.path.join(output_dir, filename)
            
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=columns)
                writer.writeheader()
                writer.writerows(data)
                
            print(f"SUCCESS: Extracted {len(data)} rows to {filepath}")
            
        except Exception as e:
            print(f"FAILED: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    main()