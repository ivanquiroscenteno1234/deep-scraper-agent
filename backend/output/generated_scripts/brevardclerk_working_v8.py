import sys
import os
import csv
import datetime
import time
from playwright.sync_api import sync_playwright

SITE_NAME = "brevardclerk"
TARGET_URL = "https://vaclmweb1.brevardclerk.us/AcclaimWeb/search/SearchTypeName"
TIMESTAMP = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
FIRST_DATA_COLUMN = 2

COLUMNS = [
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
            page.goto(TARGET_URL, wait_until="domcontentloaded")
            page.wait_for_load_state("networkidle")
            time.sleep(1)

            # STEP 2: Accept Disclaimer
            print("[STEP 2] Accepting disclaimer...")
            try:
                disclaimer_btn = page.locator("#btnButton")
                if disclaimer_btn.is_visible(timeout=5000):
                    disclaimer_btn.click()
                    page.wait_for_load_state("domcontentloaded")
                    time.sleep(1)
            except:
                pass

            # CRITICAL: Wait for search form
            print("[STEP 3] Waiting for search form...")
            page.wait_for_selector("#SearchOnName", state="visible", timeout=10000)
            time.sleep(1)

            # STEP 3-5: Fill form fields
            print(f"[STEP 3-5] Filling search criteria: {search_term}...")
            page.locator("#RecordDateFrom").fill(start_date)
            time.sleep(1)
            page.locator("#RecordDateTo").fill(end_date)
            time.sleep(1)
            page.locator("#SearchOnName").fill(search_term)
            time.sleep(1)

            # STEP 6: Submit search
            print("[STEP 6] Submitting search...")
            page.locator("#btnSearch").click()
            page.wait_for_load_state("domcontentloaded")
            time.sleep(5)

            # Handle intermediate Name Selection popup
            print("[STEP 6b] Checking for name selection popup...")
            try:
                page.wait_for_selector("#RsltsGrid, #NamesWin, #frmSchTarget", timeout=5000)
                popup_btn = page.locator("#frmSchTarget input[type='submit']")
                if popup_btn.is_visible(timeout=3000):
                    print("[STEP 7] Handling name selection popup...")
                    popup_btn.click()
                    page.wait_for_load_state("networkidle")
                    time.sleep(5)
            except:
                pass

            # STEP 7: Wait for Grid
            print("[STEP 7] Waiting for results grid...")
            grid_found = False
            for selector in ["#RsltsGrid", ".t-grid"]:
                try:
                    page.wait_for_selector(selector, state="visible", timeout=10000)
                    grid_found = True
                    break
                except:
                    continue
            
            if not grid_found:
                print("FAILED: Grid not found after search.")
                return

            # STEP 8: Extract Data
            print("[STEP 8] Extracting grid data...")
            # Use specific AcclaimWeb row selector
            rows = page.locator("#RsltsGrid .t-grid-content tbody tr").all()
            results = []

            for row in rows:
                cells = row.locator("td").all()
                if len(cells) > FIRST_DATA_COLUMN:
                    row_data = {}
                    for i, col_name in enumerate(COLUMNS):
                        cell_idx = FIRST_DATA_COLUMN + i
                        if cell_idx < len(cells):
                            row_data[col_name] = cells[cell_idx].text_content().strip()
                    results.append(row_data)

            # STEP 9: Save to CSV
            script_dir = os.path.dirname(os.path.abspath(__file__))
            output_dir = os.path.join(os.path.dirname(script_dir), "data")
            os.makedirs(output_dir, exist_ok=True)
            
            filename = f"{SITE_NAME}_{search_term.replace(' ', '_')}_{TIMESTAMP}.csv"
            filepath = os.path.join(output_dir, filename)

            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=COLUMNS)
                writer.writeheader()
                writer.writerows(results)

            print(f"SUCCESS: Extracted {len(results)} rows to {filename}")

        except Exception as e:
            print(f"FAILED: {str(e)}")
        finally:
            browser.close()

if __name__ == "__main__":
    main()