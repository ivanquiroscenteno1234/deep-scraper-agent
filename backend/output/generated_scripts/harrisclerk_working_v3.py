import sys
import os
import csv
import datetime
from playwright.sync_api import sync_playwright

SITE_NAME = "cclerk"
TARGET_URL = "https://www.cclerk.hctx.net/Applications/WebSearch/RP.aspx"
FIRST_DATA_COLUMN = 1

def main():
    # USAGE: python script.py "SEARCH_TERM" "START_DATE" "END_DATE"
    search_term = sys.argv[1] if len(sys.argv) > 1 else "SMITH"
    start_date = sys.argv[2] if len(sys.argv) > 2 else "01/01/2023"
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
            page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_load_state("networkidle", timeout=10000)
            
            # Harris County specific disclaimer/start button usually appears
            try:
                disclaimer_btn = page.locator("#btnButton")
                if disclaimer_btn.is_visible(timeout=3000):
                    print("[INFO] Clicking disclaimer/start button...")
                    disclaimer_btn.click()
                    page.wait_for_load_state("networkidle", timeout=5000)
            except:
                pass

            # STEP 2-3: Fill Dates
            print(f"[STEP 2-3] Filling dates: {start_date} to {end_date}")
            page.wait_for_selector("#ctl00_ContentPlaceHolder1_txtFrom", state="visible", timeout=10000)
            page.fill("#ctl00_ContentPlaceHolder1_txtFrom", start_date)
            page.fill("#ctl00_ContentPlaceHolder1_txtTo", end_date)
            
            # STEP 4: Fill Search Term
            print(f"[STEP 4] Filling search term: {search_term}")
            page.fill("#ctl00_ContentPlaceHolder1_txtOR", search_term)
            
            # STEP 5: Submit Search
            print("[STEP 5] Submitting search...")
            search_btn = page.locator("#ctl00_ContentPlaceHolder1_btnSearch")
            search_btn.click()
            page.wait_for_load_state("domcontentloaded", timeout=10000)
            
            # STEP 6: Robust Wait for Results or Popup
            print("[STEP 6] Waiting for results OR popup...")
            try:
                page.wait_for_selector("#itemPlaceholderContainer, #NamesWin, #frmSchTarget, .t-window", timeout=10000)
            except:
                pass

            # Handle Intermediate Popups (e.g., Name Selection)
            popup_selectors = [
                "#frmSchTarget input[type='submit']",
                "input[value='Done']",
                "input[name='btnDone']"
            ]
            for popup_sel in popup_selectors:
                try:
                    popup_btn = page.locator(popup_sel)
                    if popup_btn.is_visible(timeout=3000):
                        print(f"[INFO] Handling intermediate popup with {popup_sel}...")
                        popup_btn.first.click()
                        page.wait_for_load_state("networkidle", timeout=10000)
                        break
                except:
                    continue

            # STEP 7: Wait for Grid
            print("[STEP 7] Ensuring grid is visible...")
            grid_selector = "#itemPlaceholderContainer"
            page.wait_for_selector(grid_selector, state="visible", timeout=10000)
            
            # STEP 8: Extract Rows
            print("[STEP 8] Extracting rows...")
            # Use specific row selector relative to grid
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
                # Check if this is a data row (not a header or empty row)
                if len(cells) > FIRST_DATA_COLUMN:
                    row_data = {}
                    for i, col_name in enumerate(columns):
                        cell_index = FIRST_DATA_COLUMN + i
                        if cell_index < len(cells):
                            # Harris County "Names" column contains a nested table
                            text = cells[cell_index].text_content().strip()
                            # Clean up excessive whitespace/newlines from nested tables
                            text = " ".join(text.split())
                            row_data[col_name] = text
                    
                    if row_data.get("File Number"):
                        data.append(row_data)

            # STEP 9: Save to CSV
            script_dir = os.path.dirname(os.path.abspath(__file__))
            output_dir = os.path.join(os.path.dirname(script_dir), "data")
            os.makedirs(output_dir, exist_ok=True)
            
            filename = f"{SITE_NAME}_{search_term}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            output_path = os.path.join(output_dir, filename)
            
            if data:
                with open(output_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=columns)
                    writer.writeheader()
                    writer.writerows(data)
                print(f"SUCCESS: Extracted {len(data)} rows to {output_path}")
            else:
                print("SUCCESS: No results found for the given criteria.")
                
        except Exception as e:
            print(f"FAILED: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    main()