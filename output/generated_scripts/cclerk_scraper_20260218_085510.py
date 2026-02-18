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
            # STEP 1: Navigate to target URL
            print("[STEP 1] Navigating to URL...")
            page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_load_state("networkidle", timeout=10000)
            
            # STEP 2: Fill start date
            print(f"[STEP 2] Filling start date: {start_date}")
            page.wait_for_selector("#ctl00_ContentPlaceHolder1_txtFrom", state="visible", timeout=10000)
            page.locator("#ctl00_ContentPlaceHolder1_txtFrom").fill(start_date)
            
            # wait_for_input specified in recorded steps
            page.wait_for_selector("#ctl00_ContentPlaceHolder1_txtOR", state="visible", timeout=5000)
            
            # STEP 3: Fill end date
            print(f"[STEP 3] Filling end date: {end_date}")
            page.locator("#ctl00_ContentPlaceHolder1_txtTo").fill(end_date)
            
            # STEP 4: Fill search input
            print(f"[STEP 4] Filling search term: {search_term}")
            page.locator("#ctl00_ContentPlaceHolder1_txtOR").fill(search_term)
            
            # STEP 5: Submit search
            print("[STEP 5] Clicking search button...")
            search_btn = page.locator("#ctl00_ContentPlaceHolder1_btnSearch")
            search_btn.click()
            page.wait_for_load_state("domcontentloaded", timeout=10000)
            
            # STEP 6: Handle Intermediate States
            print("[STEP 6] Waiting for results OR popup...")
            try:
                # Comma-separated list of potential results or intermediate popups
                page.wait_for_selector("#itemPlaceholderContainer, #NamesWin, #frmSchTarget, .t-window", timeout=10000)
            except:
                pass

            # Check for popup buttons if they appear
            popup_selectors = ["#frmSchTarget input[type='submit']", "input[value='Done']", "input[name='btnDone']"]
            for popup_sel in popup_selectors:
                try:
                    popup_btn = page.locator(popup_sel)
                    if popup_btn.is_visible(timeout=3000):
                        print(f"[INFO] Handling popup with {popup_sel}...")
                        popup_btn.first.click()
                        page.wait_for_load_state("networkidle", timeout=10000)
                        break
                except:
                    continue

            # STEP 7: Wait for Grid Visibility
            print("[STEP 7] Ensuring grid is visible...")
            grid_selector = "#itemPlaceholderContainer"
            try:
                page.wait_for_selector(grid_selector, state="visible", timeout=15000)
            except Exception as e:
                print(f"[WARN] Grid selector {grid_selector} not found within timeout. Attempting to proceed.")

            # STEP 8: Extract Data
            print("[STEP 8] Extracting rows...")
            # Use exact row selector: Primary grid + tbody tr
            row_selector = f"{grid_selector} tbody tr"
            rows = page.locator(row_selector).all()
            
            columns = [
                "File Number",
                "File Date",
                "Type",
                "Vol",
                "Page",
                "Names",
                "Legal Description",
                "Pgs",
                "Film Code"
            ]
            
            data = []
            for row in rows:
                cells = row.locator("td").all()
                # Skip rows that don't have enough cells (like spacers or headers)
                if len(cells) > FIRST_DATA_COLUMN:
                    row_data = {}
                    for i, col_name in enumerate(columns):
                        cell_index = FIRST_DATA_COLUMN + i
                        if cell_index < len(cells):
                            # Extract text and strip whitespace
                            text = cells[cell_index].text_content().strip()
                            # Clean up internal whitespace for multi-line cells (like Names)
                            row_data[col_name] = " ".join(text.split())
                    
                    if any(row_data.values()): # Only add if row is not entirely empty
                        data.append(row_data)
            
            # STEP 9: Save to CSV
            if data:
                script_dir = os.path.dirname(os.path.abspath(__file__))
                output_dir = os.path.join(os.path.dirname(script_dir), "data")
                os.makedirs(output_dir, exist_ok=True)
                
                filename = f"{SITE_NAME}_results_{TIMESTAMP}.csv"
                filepath = os.path.join(output_dir, filename)
                
                with open(filepath, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=columns)
                    writer.writeheader()
                    writer.writerows(data)
                
                print(f"SUCCESS: Extracted {len(data)} rows to {filepath}")
            else:
                print("SUCCESS: No data found for the given criteria.")
                
        except Exception as e:
            print(f"FAILED: {str(e)}")
        finally:
            browser.close()

if __name__ == "__main__":
    main()