import sys
import time
import csv
from playwright.sync_api import sync_playwright

def scrape_flagler(search_term: str) -> str:
    county_name = "flagler"
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    csv_file_path = f"output/extracted_data/{county_name}_{timestamp}.csv"

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto("https://records.flaglerclerk.com/", timeout=60000)

            # Handle disclaimer
            while True:
                try:
                    page.locator("#idAcceptYes").click(timeout=5000)
                except:
                    break

            # Fill search form and submit
            page.locator("#name-Name").fill(search_term, timeout=10000)
            page.locator("#nameSearchModalSubmit").click(timeout=10000)

            # Wait for results table
            page.wait_for_selector("table", timeout=30000)
            
            # Extract data
            data = []
            table = page.locator("table")
            rows = table.locator("tbody > tr")
            
            num_rows = rows.count()

            header_row = table.locator("thead > tr > th")
            headers = []
            for i in range(header_row.count()):
                headers.append(header_row.nth(i).inner_text().strip())

            data.append(headers)

            for i in range(num_rows):
                row = rows.nth(i)
                cells = row.locator("td")
                row_data = []
                for j in range(cells.count()):
                    row_data.append(cells.nth(j).inner_text().strip())
                data.append(row_data)
            

            # Save to CSV
            with open(csv_file_path, 'w', newline='', encoding='utf-8') as csvfile:
                csvwriter = csv.writer(csvfile)
                csvwriter.writerows(data)

            browser.close()
            return csv_file_path

    except Exception as e:
        print(f"An error occurred: {e}")
        return None

if __name__ == "__main__":
    if len(sys.argv) > 1:
        search_term = sys.argv[1]
        output_file = scrape_flagler(search_term)
        if output_file:
            print(f"Data saved to: {output_file}")
        else:
            print("Scraping failed.")
    else:
        print("Please provide a search term as a command-line argument.")