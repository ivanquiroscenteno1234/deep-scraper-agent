import sys
import os
import csv
import datetime
import time
from playwright.sync_api import sync_playwright

SITE_NAME = "cclerk"
TARGET_URL = "https://www.cclerk.hctx.net/Applications/WebSearch/RP.aspx"
TIMESTAMP = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')

def main():
    # USAGE: python script.py "SEARCH_TERM" "START_DATE" "END_DATE"
    search_term = sys.argv[1] if len(sys.argv) > 1 else "CENTEX HOMES ETAL"
    start_date = sys.argv[2] if len(sys.argv) > 2 else "07/01/2006"
    end_date = sys.argv[3] if len(sys.argv) > 3 else "07/31/2006"
    
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
            print(f"[STEP 2] Filling start date: {start_date}")
            page.wait_for_selector("#ctl00_ContentPlaceHolder1_txtFrom", timeout=10000)
            page.fill("#ctl00_ContentPlaceHolder1_txtFrom", start_date)
            
            # STEP 3: Fill end date
            print(f"[STEP 3] Filling end date: {end_date}")
            page.fill("#ctl00_ContentPlaceHolder1_txtTo", end_date)
            
            # STEP 4: Fill search input (Grantor field)
            print(f"[STEP 4] Filling search term: {search_term}")
            page.fill("#ctl00_ContentPlaceHolder1_txtOR", search_term)
            
            # STEP 5: Click search
            print("[STEP 5] Clicking search...")
            page.locator("#ctl00_ContentPlaceHolder1_btnSearch").click()
            
            # STEP 6: Wait for results to load
            print("[STEP 6] Waiting for search response...")
            page.wait_for_load_state("networkidle", timeout=30000)
            time.sleep(2)  # Extra buffer for AJAX
            
            # STEP 6.1: Check if name selection popup appeared (varies by search)
            print("[STEP 6.1] Checking for name selection popup...")
            try:
                popup_visible = page.locator("#NamesWin").is_visible()
                if popup_visible:
                    print("[STEP 6.2] Name selection popup detected. Clicking Done...")
                    page.locator("#ctl00_mainContent_btnNamesDone").click()
                    page.wait_for_load_state("networkidle", timeout=30000)
                    time.sleep(2)
            except:
                print("[STEP 6.1] No popup - results displayed directly")
            
            # STEP 7: Wait for results grid
            # The actual grid on this site is #itemPlaceholderContainer, NOT #ctl00_ContentPlaceHolder1_gvSearch
            print("[STEP 7] Waiting for results grid...")
            page.wait_for_selector("#itemPlaceholderContainer", state="visible", timeout=30000)
            
            # STEP 8: Extract data
            print("[STEP 8] Extracting rows...")
            # The grid is a table with id "itemPlaceholderContainer"
            # Columns: "", "File Number", "File Date", "Type/Vol Page", "Names", "Legal Description", "Pgs", "Film Code"
            rows = page.locator("#itemPlaceholderContainer tbody tr").all()
            
            column_names = [
                "File Number",
                "File Date",
                "Type",
                "Names",
                "Legal Description",
                "Pages",
                "Film Code"
            ]
            
            data = []
            for row in rows:
                cells = row.locator("td").all()
                # Skip header row or rows with insufficient data
                if len(cells) < 7:
                    continue
                    
                try:
                    row_data = {
                        "File Number": cells[1].inner_text().strip() if len(cells) > 1 else "",
                        "File Date": cells[2].inner_text().strip() if len(cells) > 2 else "",
                        "Type": cells[3].inner_text().strip().split('\n')[0] if len(cells) > 3 else "",  # Take first line
                        "Names": cells[4].inner_text().strip().replace('\n', ' | ') if len(cells) > 4 else "",
                        "Legal Description": cells[5].inner_text().strip().replace('\n', ' | ') if len(cells) > 5 else "",
                        "Pages": cells[6].inner_text().strip() if len(cells) > 6 else "",
                        "Film Code": cells[7].inner_text().strip() if len(cells) > 7 else ""
                    }
                    
                    # Only add rows with actual data
                    if row_data["File Number"]:
                        data.append(row_data)
                except Exception as cell_err:
                    print(f"[WARN] Error extracting row: {cell_err}")
                    continue
            
            # STEP 9: Save to CSV
            if data:
                script_dir = os.path.dirname(os.path.abspath(__file__))
                output_dir = os.path.join(os.path.dirname(script_dir), "data")
                os.makedirs(output_dir, exist_ok=True)
                
                filename = f"{SITE_NAME}_search_{TIMESTAMP}.csv"
                filepath = os.path.join(output_dir, filename)
                
                with open(filepath, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=column_names)
                    writer.writeheader()
                    writer.writerows(data)
                
                print(f"SUCCESS: Extracted {len(data)} rows to {filepath}")
            else:
                print("No data found in grid.")
            
        except Exception as e:
            print(f"FAILED: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    main()