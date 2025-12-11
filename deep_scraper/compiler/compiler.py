import json

def compile_steps_to_script(steps: list, county_name: str, search_variable: str = None) -> str:
    """
    Compiles a list of recorded VisualAction steps into a robust Python Playwright script.
    
    Args:
        steps: List of recorded steps
        county_name: Name of the county (for function naming)
        search_variable: The specific value (e.g. "Lauren Smith") that should be replaced with the 'builder_name' variable
    """
    
    script_body = ""
    
    for step in steps:
        action_type = step.get('action_type')
        selector = step.get('selector')
        value = step.get('value')
        reasoning = step.get('reasoning', '')
        
        script_body += f"\n        # {reasoning}\n"
        
        if action_type == 'navigate':
            script_body += f'        page.goto("{value}")\n'
            script_body += '        page.wait_for_load_state("networkidle")\n'
            
        elif action_type == 'click':
            # Add strict error handling for clicks
            script_body += f'        page.wait_for_selector("{selector}", timeout=5000)\n'
            script_body += f'        page.click("{selector}")\n'
            script_body += '        page.wait_for_load_state("networkidle")\n'
            
        elif action_type == 'fill':
            # Add strict error handling for fills
            script_body += f'        page.wait_for_selector("{selector}", timeout=5000)\n'
            
            # Smart Variable Replacement
            if search_variable and value and search_variable.lower() in value.lower():
                # If the filled value contains the search variable, use the python variable
                script_body += f'        page.fill("{selector}", builder_name)\n'
                script_body += f'        # Note: Replaced hardcoded "{value}" with variable\n'
            else:
                script_body += f'        page.fill("{selector}", "{value}")\n'
            
        elif action_type == 'wait':
            script_body += '        page.wait_for_timeout(2000)\n'

    # Template
    template = f'''
from playwright.sync_api import sync_playwright, Page
import typing
import pandas as pd
import datetime

def scrape_{county_name.replace(' ', '_').lower()}(builder_name: str) -> str:
    """
    Scrapes {county_name} records for a builder and saves results to CSV.
    """
    results = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.set_default_timeout(60000)
        
        try:
{script_body}
            
            # --- DATA EXTRACTION LOGIC (Generic Table Scraper) ---
            print("Extacting data...")
            
            # Wait for any table
            page.wait_for_selector("table", timeout=5000)
            
            # Try to find the results table
            tables = page.locator("table")
            count = tables.count()
            
            if count > 0:
                # Assume the largest table (by rows) is the results table
                target_table = tables.nth(0) 
                
                # Extract headers
                headers = []
                header_cells = target_table.locator("th")
                if header_cells.count() > 0:
                    for i in range(header_cells.count()):
                        headers.append(header_cells.nth(i).inner_text().strip())
                
                # Extract rows
                rows = target_table.locator("tr")
                for i in range(1, rows.count()): # Skip header usually
                    cells = rows.nth(i).locator("td")
                    row_data = {{}}
                    
                    if cells.count() > 0:
                        for j in range(cells.count()):
                            header = headers[j] if j < len(headers) else f"col_{{j}}"
                            row_data[header] = cells.nth(j).inner_text().strip()
                        results.append(row_data)
                        
            # Save to CSV
            if results:
                df = pd.DataFrame(results)
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                # Use the actual builder_name in filename
                safe_name = "".join([c for c in builder_name if c.isalnum() or c in (' ', '_')]).strip().replace(' ', '_')
                filename = f"results_{{safe_name}}_{{timestamp}}.csv"
                df.to_csv(filename, index=False)
                print(f"Successfully scraped {{len(results)}} records. Saved to {{filename}}")
                return filename
            else:
                print("No results found.")
                return None
                
        except Exception as e:
            print(f"Error during execution: {{e}}")
            page.screenshot(path="error.png")
            raise e
        finally:
            browser.close()

if __name__ == "__main__":
    # Test with default name from recording
    scrape_{county_name.replace(' ', '_').lower()}("{search_variable if search_variable else 'Test Name'}")
'''
    return template
