import sys
import os
import csv
import datetime
from playwright.sync_api import sync_playwright

SITE_NAME = "dallas"
TARGET_URL = "https://dallas.tx.publicsearch.us/"
TIMESTAMP = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
FIRST_DATA_COLUMN = 3

def main():
    search_term = sys.argv[1] if len(sys.argv) > 1 else "SMITH"
    start_date = sys.argv[2] if len(sys.argv) > 2 else "01/01/2023"
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
            
            # CRITICAL: Wait for search form elements to be visible as per recorded requirements
            print("[STEP 2] Waiting for search form...")
            page.wait_for_selector("input[data-testid='searchInputBox']", state="visible", timeout=10000)

            # STEP 2: Fill start date
            print(f"[STEP 2] Filling start date: {start_date}")
            page.locator("input[aria-label='Starting Recorded Date']").fill(start_date)
            
            # STEP 3: Fill end date
            print(f"[STEP 3] Filling end date: {end_date}")
            page.locator("input[aria-label='Ending Recorded Date']").fill(end_date)
            
            # STEP 4: Fill search input
            print(f"[STEP 4] Filling search term: {search_term}")
            page.locator("input[data-testid='searchInputBox']").fill(search_term)
            
            # STEP 5: Submit search
            print("[STEP 5] Submitting search...")
            submit_btn = page.locator("button[data-testid='searchSubmitButton']")
            submit_btn.click()
            page.wait_for_load_state("domcontentloaded", timeout=10000)
            
            # STEP 6: Handle Intermediate States / Wait for Results
            print("[STEP 6] Waiting for results or popup...")
            try:
                # Common popup containers for this site type
                page.wait_for_selector(".search-results__results-wrap table, #NamesWin, .t-window", timeout=10000)
            except:
                pass

            # Check for name selection popup
            popup_selectors = ["input[value='Done']", "#frmSchTarget input[type='submit']", "button:has-text('Accept')"]
            for sel in popup_selectors:
                try:
                    btn = page.locator(sel)
                    if btn.is_visible(timeout=3000):
                        print(f"[INFO] Handling popup with selector: {sel}")
                        btn.click()
                        page.wait_for_load_state("networkidle", timeout=5000)
                        break
                except:
                    continue

            # STEP 7: Ensure grid is visible
            print("[STEP 7] Locating results grid...")
            grid_selector = ".search-results__results-wrap table"
            try:
                page.wait_for_selector(grid_selector, state="visible", timeout=15000)
            except Exception as e:
                print(f"[ERROR] Grid not found: {e}")
                # Check if "No results" message exists
                if "no results" in page.content().lower():
                    print("SUCCESS: No results found for criteria.")
                    return
                raise e

            # STEP 8: Extract Data
            print("[STEP 8] Extracting data from rows...")
            # Use specific row selector relative to the recorded grid
            row_selector = ".search-results__results-wrap table tbody tr"
            rows = page.locator(row_selector).all()
            
            columns = [
                "Grantor",
                "Grantee",
                "Doc Type",
                "Recorded Date",
                "Doc Number",
                "Book/Volume/Page",
                "Town",
                "Legal Description"
            ]
            
            data = []
            for row in rows:
                cells = row.locator("td").all()
                if len(cells) > FIRST_DATA_COLUMN:
                    row_data = {}
                    for i, col_name in enumerate(columns):
                        cell_index = FIRST_DATA_COLUMN + i
                        if cell_index < len(cells):
                            # Extract text and clean up whitespace/newlines
                            text = cells[cell_index].text_content().strip()
                            # Handle multiple spaces or internal newlines often found in legal descriptions
                            row_data[col_name] = " ".join(text.split())
                    data.append(row_data)
            
            # STEP 9: Save to CSV
            script_dir = os.path.dirname(os.path.abspath(__file__))
            output_dir = os.path.join(os.path.dirname(script_dir), "data")
            os.makedirs(output_dir, exist_ok=True)
            
            filename = f"{SITE_NAME}_results_{TIMESTAMP}.csv"
            filepath = os.path.join(output_dir, filename)
            
            if data:
                with open(filepath, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=columns)
                    writer.writeheader()
                    writer.writerows(data)
                print(f"SUCCESS: Extracted {len(data)} rows to {filepath}")
            else:
                print("SUCCESS: No data rows found in grid.")
                
        except Exception as e:
            print(f"FAILED: {e}")
            # Optional: page.screenshot(path="error.png")
        finally:
            browser.close()

if __name__ == "__main__":
    main()