import sys
import os
import csv
import datetime
from playwright.sync_api import sync_playwright

# Configuration
SITE_NAME = "brevardclerk"
TARGET_URL = "https://vaclmweb1.brevardclerk.us/AcclaimWeb/search/SearchTypeName"
TIMESTAMP = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')

def main():
    # USAGE: python script.py "SEARCH_TERM" "START_DATE" "END_DATE"
    search_term = sys.argv[1] if len(sys.argv) > 1 else "SMITH"
    start_date = sys.argv[2] if len(sys.argv) > 2 else "01/01/1980"
    end_date = sys.argv[3] if len(sys.argv) > 3 else datetime.datetime.now().strftime('%m/%d/%Y')
    
    print(f"[INFO] Starting scraper for '{search_term}' (Range: {start_date} - {end_date})")
    print(f"[INFO] Target URL: {TARGET_URL}")
    
    with sync_playwright() as p:
        print("[STEP 1] Launching browser...")
        browser = p.chromium.launch(headless=True)
        # Fresh context with NO storage state to ensure disclaimer appears
        context = browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        print("[STEP 1] Browser launched")
        
        try:
            # STEP 2: Navigate to URL
            print(f"[STEP 2] Navigating to {TARGET_URL}...")
            page.goto(TARGET_URL, wait_until="domcontentloaded")
            print("[STEP 2] Page loaded")
            
            # STEP 3: Handle disclaimer if present
            print("[STEP 3] Checking for disclaimer...")
            try:
                disclaimer_btn = page.locator("#btnButton")
                if disclaimer_btn.is_visible(timeout=5000):
                    print("[STEP 3] Found disclaimer, clicking accept...")
                    disclaimer_btn.click()
                    page.wait_for_load_state("networkidle")
                    # Re-navigate to search page after clearing disclaimer if needed
                    page.goto(TARGET_URL, wait_until="networkidle")
                else:
                    print("[STEP 3] No disclaimer found, continuing...")
            except Exception:
                print("[STEP 3] Disclaimer check skipped")
            
            # STEP 4: Fill search form
            print(f"[STEP 4] Filling search form with '{search_term}'...")
            search_input = page.locator("#SearchOnName")
            search_input.wait_for(state="visible", timeout=10000)
            search_input.fill(search_term)
            
            # STEP 4b: Explicitly set date range (Ensures Search button is enabled)
            # Using defaults if not provided, but explicitly typing them
            print(f"[STEP 4b] Filling dates: {start_date} to {end_date}")
            page.fill("#RecordDateFrom", start_date)
            page.fill("#RecordDateTo", end_date)
            page.wait_for_timeout(500) # Small delay to trigger UI validation
            
            # STEP 5: Submit search
            print("[STEP 5] Clicking search button...")
            page.click("#btnSearch")
            
            # STEP 6: Handle Name Selection Popup or Results
            print("[STEP 6] Waiting for results or Name Selection popup...")
            
            # ROBUST WAIT AFTER SEARCH:
            print("[WAIT] Waiting for results OR name selection popup...")
            try:
                page.wait_for_selector("#RsltsGrid, #NamesWin, #frmSchTarget, .t-window", timeout=5000)
            except:
                pass

            popup_selectors = [
                "#frmSchTarget input[type='submit']",
                "input[name='btnDone']",
                "input[value='Done']"
            ]
            
            for popup_sel in popup_selectors:
                popup_btn = page.locator(popup_sel)
                if popup_btn.is_visible(timeout=2000):
                    print(f"[STEP 6] Name Selection popup detected, clicking '{popup_sel}'")
                    popup_btn.first.click()
                    # After clicking Done, wait for the actual results grid
                    break
            
            # STEP 7: Wait for results grid to be visible
            print("[STEP 7] Waiting for results grid...")
            grid_selectors = ["#RsltsGrid", "#SearchGrid", ".t-grid"]
            grid_selector = None
            
            # Crucial: Wait until the grid specifically is visible and data is likely loaded
            for selector in grid_selectors:
                try:
                    target_grid = page.locator(selector)
                    target_grid.wait_for(state="visible", timeout=10000)
                    grid_selector = selector
                    print(f"[STEP 7] Found active grid: {grid_selector}")
                    break
                except:
                    continue
            
            if not grid_selector:
                if "no records" in page.content().lower() or "no results" in page.content().lower():
                    print("No results found for this search term.")
                else:
                    print("FAILED: Results grid did not appear after search.")
                    # Take a screenshot for debugging if needed: page.screenshot(path="error.png")
                return
            
            # STEP 8: Extract data
            print(f"[STEP 8] Extracting data from grid...")
            # Telerik grids often have data in .t-grid-content
            row_locator = page.locator(f"{grid_selector} tbody tr").filter(has_not=page.locator(".t-no-data"))
            
            # Ensure rows are loaded
            page.wait_for_timeout(1000) 
            rows = row_locator.all()
            print(f"[STEP 8] Found {len(rows)} data rows")
            
            column_mapping = [
                "Row", "U", "Party Type", "Full Name", "Cross Party Name", 
                "Record Date", "Type", "Book Type", "Book/Page", 
                "Clerk File Number", "Consideration", "First Legal Description", 
                "Description", "Case #"
            ]
            
            extracted_data = []
            for row in rows:
                cells = row.locator("td").all()
                if len(cells) < 5:
                    continue
                
                row_data = {}
                for idx, col_name in enumerate(column_mapping):
                    if idx < len(cells):
                        row_data[col_name] = cells[idx].inner_text().strip()
                    else:
                        row_data[col_name] = ""
                extracted_data.append(row_data)
            
            if not extracted_data:
                print("No valid records extracted from the grid.")
                return
            
            # STEP 9: Save to CSV
            print("[STEP 9] Saving to CSV...")
            script_dir = os.path.dirname(os.path.abspath(__file__))
            data_dir = os.path.join(script_dir, 'data') # Simplified path for stability
            os.makedirs(data_dir, exist_ok=True)
            csv_filename = f"{SITE_NAME}_results_{TIMESTAMP}.csv"
            csv_path = os.path.join(data_dir, csv_filename)
            
            with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=column_mapping)
                writer.writeheader()
                writer.writerows(extracted_data)
            
            print(f"SUCCESS: Extracted {len(extracted_data)} rows. Saved to {csv_path}")
            
        except Exception as e:
            print(f"FAILED: {str(e)}")
            import traceback
            traceback.print_exc()
        finally:
            print("[CLEANUP] Closing browser...")
            browser.close()
            print("[CLEANUP] Done")

if __name__ == "__main__":
    main()