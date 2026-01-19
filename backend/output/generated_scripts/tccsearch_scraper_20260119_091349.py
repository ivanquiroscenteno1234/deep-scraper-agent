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
    search_term = sys.argv[1] if len(sys.argv) > 1 else "SMITH & ARMSTRONG INC"
    start_date = sys.argv[2] if len(sys.argv) > 2 else "01/01/2006"
    end_date = sys.argv[3] if len(sys.argv) > 3 else "12/31/2006"
    
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
            accept_selector = "#cph1_lnkAccept"
            try:
                page.wait_for_selector(accept_selector, state="visible", timeout=10000)
                page.locator(accept_selector).click()
                page.wait_for_load_state("networkidle", timeout=5000)
            except Exception as e:
                print(f"[DEBUG] Disclaimer not found or already accepted: {e}")
            
            # STEP 3-5: Fill Form
            # Ground Truth uses specific nested input selectors for dates
            print("[STEP 3] Filling start date...")
            start_date_selector = "#cphNoMargin_f_ddcDateFiledFrom input"
            page.wait_for_selector(start_date_selector, state="visible", timeout=10000)
            page.locator(start_date_selector).fill(start_date)
            page.locator(start_date_selector).press("Tab")
            
            print("[STEP 4] Filling end date...")
            end_date_selector = "#cphNoMargin_f_ddcDateFiledTo input"
            page.locator(end_date_selector).fill(end_date)
            page.locator(end_date_selector).press("Tab")
            
            print("[STEP 5] Filling search term...")
            search_input_selector = "#cphNoMargin_f_txtParty"
            page.locator(search_input_selector).fill(search_term)
            page.locator(search_input_selector).press("Enter")
            
            # STEP 6: Submit search
            print("[STEP 6] Submitting search...")
            search_btn_selector = "#cphNoMargin_SearchButtons1_btnSearch"
            # Ensure the button is visible/enabled; sometimes scrolling is needed for visibility
            search_btn = page.locator(search_btn_selector).first
            search_btn.scroll_into_view_if_needed()
            
            # If standard click fails due to visibility, dispatch event or force click
            try:
                search_btn.click(timeout=5000)
            except:
                print("[DEBUG] Standard click failed, attempting forced click...")
                search_btn.click(force=True)

            # Combined wait for Results OR Name selection popup
            print("[STEP 6b] Waiting for results OR popup...")
            grid_selector = ".ig_ElectricBlueControl"
            popup_selectors = "#NamesWin, #frmSchTarget, .t-window, input[value='Done'], input[name='btnDone']"
            
            try:
                page.wait_for_selector(f"{grid_selector}, {popup_selectors}", timeout=20000)
            except:
                pass

            # Handle intermediate name selection popup if it appears
            for popup_btn_sel in ["input[value='Done']", "input[name='btnDone']", "#btnDone"]:
                try:
                    popup_btn = page.locator(popup_btn_sel).first
                    if popup_btn.is_visible(timeout=3000):
                        print(f"[STEP 6c] Handling intermediate popup: {popup_btn_sel}")
                        popup_btn.click()
                        page.wait_for_load_state("networkidle", timeout=5000)
                        break
                except:
                    continue

            # STEP 7: Capture Grid
            print("[STEP 7] Ensuring grid is visible...")
            try:
                page.wait_for_selector(grid_selector, state="visible", timeout=15000)
            except Exception as e:
                print(f"[ERROR] Grid not found: {e}")
                page.screenshot(path="error_state.png")
                return

            # STEP 8: Extract Data
            print("[STEP 8] Extracting rows...")
            # Use specific tbody tr from Ground Truth
            rows = page.locator(f"{grid_selector} tbody tr").all()
            results = []
            
            for row in rows:
                cells = row.locator("td").all()
                # Check if row has enough cells based on FIRST_DATA_COLUMN
                if len(cells) >= FIRST_DATA_COLUMN + len(COLUMNS):
                    row_data = {}
                    valid_row = False
                    for i, col_name in enumerate(COLUMNS):
                        cell_index = FIRST_DATA_COLUMN + i
                        val = cells[cell_index].text_content().strip()
                        row_data[col_name] = val
                        if val:
                            valid_row = True
                    
                    if valid_row:
                        results.append(row_data)
            
            # STEP 9: Save to CSV
            if results:
                script_dir = os.path.dirname(os.path.abspath(__file__))
                output_dir = os.path.join(script_dir, "data")
                os.makedirs(output_dir, exist_ok=True)
                filename = f"results_{SITE_NAME}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                filepath = os.path.join(output_dir, filename)
                
                with open(filepath, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=COLUMNS)
                    writer.writeheader()
                    writer.writerows(results)
                print(f"SUCCESS: Extracted {len(results)} rows to {filepath}")
            else:
                print("SUCCESS: Search completed but no data rows found.")

        except Exception as e:
            print(f"FAILED: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    main()