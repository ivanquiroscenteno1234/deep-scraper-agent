import sys
import os
import csv
import datetime
import time
from playwright.sync_api import sync_playwright

SITE_NAME = "records"
TARGET_URL = "https://records.flaglerclerk.com/"
FIRST_DATA_COLUMN = 2
COLUMNS = [
    "Rec Date",
    "Doc Type",
    "Instrument #",
    "Book/Page",
    "Direct Name",
    "Reverse Name",
    "Legal Description"
]

def main():
    # USAGE: python script.py "SEARCH_TERM" "START_DATE" "END_DATE"
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
            # STEP 1: Navigate to target URL
            print("[STEP 1] Navigating to URL...")
            page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_load_state("networkidle", timeout=10000)

            # STEP 2: Navigate to Name Search
            print("[STEP 2] Clicking Name Search icon...")
            page.locator("a[title='Name Search']").click()
            page.wait_for_load_state("domcontentloaded", timeout=5000)

            # STEP 3: Accept Disclaimer
            print("[STEP 3] Accepting disclaimer...")
            try:
                accept_btn = page.locator("#idAcceptYes")
                if accept_btn.is_visible(timeout=5000):
                    accept_btn.click()
                    page.wait_for_load_state("domcontentloaded", timeout=5000)
            except:
                print("[INFO] Disclaimer not found or already accepted.")

            # CRITICAL: Wait for the search form to be visible after modal transition
            print("[WAIT] Waiting for search form visibility...")
            page.wait_for_selector("#name-Name", state="visible", timeout=10000)

            # STEP 4: Fill Start Date using JS (as recorded)
            print(f"[STEP 4] Filling start date: {start_date}")
            page.evaluate(f"""
                (() => {{
                    const el = document.querySelector('#beginDate-Name');
                    if (el) {{
                        el.value = '{start_date}';
                        el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    }}
                }})()
            """)

            # STEP 5: Fill End Date using JS (as recorded)
            print(f"[STEP 5] Filling end date: {end_date}")
            page.evaluate(f"""
                (() => {{
                    const el = document.querySelector('#endDate-Name');
                    if (el) {{
                        el.value = '{end_date}';
                        el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    }}
                }})()
            """)

            # STEP 6: Fill Search Term
            print(f"[STEP 6] Filling search term: {search_term}")
            page.locator("#name-Name").fill(search_term)

            # STEP 7: Submit Search
            print("[STEP 7] Submitting search...")
            page.locator("#submit-Name").click()
            page.wait_for_load_state("networkidle", timeout=10000)

            # STEP 8: Handle Name Selection popup (if it appears)
            print("[STEP 8] Checking for Name Selection popup...")
            try:
                # Wait for grid OR popup
                page.wait_for_selector("#resultsTable, #idAcceptYes", timeout=5000)
                popup_btn = page.locator("#idAcceptYes")
                if popup_btn.is_visible(timeout=3000):
                    print("[INFO] Clicking popup confirmation...")
                    popup_btn.click()
                    page.wait_for_load_state("networkidle", timeout=5000)
            except:
                pass

            # STEP 9: Wait for results grid
            print("[STEP 9] Waiting for results grid...")
            page.wait_for_selector("#resultsTable", state="visible", timeout=10000)

            # Capture Grid Data
            print("[INFO] Extracting data from grid...")
            rows = page.locator("#resultsTable tbody tr").all()
            results = []

            for row in rows:
                cells = row.locator("td").all()
                if len(cells) > FIRST_DATA_COLUMN:
                    row_data = {}
                    for i, col_name in enumerate(COLUMNS):
                        cell_index = FIRST_DATA_COLUMN + i
                        if cell_index < len(cells):
                            row_data[col_name] = cells[cell_index].text_content().strip()
                    results.append(row_data)

            # Save to CSV
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
                print("SUCCESS: No results found for search criteria.")

        except Exception as e:
            print(f"FAILED: {str(e)}")
        finally:
            browser.close()

if __name__ == "__main__":
    main()