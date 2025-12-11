import asyncio
from playwright.async_api import async_playwright, Page, Browser, Playwright
from bs4 import BeautifulSoup
import html2text

class BrowserManager:
    """
    Singleton-style wrapper for Playwright to manage the browser instance 
    outside of the LangGraph state.
    """
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(BrowserManager, cls).__new__(cls)
            cls._instance.playwright = None
            cls._instance.browser = None
            cls._instance.page = None
        return cls._instance

    async def initialize(self):
        """Initializes Playwright and launches a headed browser."""
        if not self.playwright:
            self.playwright = await async_playwright().start()
            # Headless=False so we can watch it work
            self.browser = await self.playwright.chromium.launch(headless=False)
            self.page = await self.browser.new_page()
            # Set a realistic viewport
            await self.page.set_viewport_size({"width": 1280, "height": 720})

    async def go_to(self, url: str):
        """Navigates to the URL and waits for network idle."""
        if not self.page:
            await self.initialize()
        
        try:
            await self.page.goto(url)
            await self.page.wait_for_load_state("networkidle", timeout=10000)
        except Exception as e:
            print(f"Navigation warning: {e}")

    async def get_clean_content(self) -> str:
        """
        Returns a clean Markdown representation of the page content,
        ENHANCED with a list of interactive elements (inputs, buttons) 
        so the LLM can identify selectors.
        """
        if not self.page:
            return ""
            
        content = await self.page.content()
        soup = BeautifulSoup(content, 'html.parser')
        
        # Extract interactive elements buffer BEFORE cleaning
        interactive_buffer = ["### INTERACTIVE ELEMENTS (Use these selectors):"]
        for el in soup.find_all(['input', 'button', 'a', 'select'])[:50]:  # Limit to first 50
            tag_name = el.name
            el_type = el.get('type', '').lower()
            
            # Skip hidden inputs
            if tag_name == 'input' and el_type == 'hidden':
                continue
                
            el_id = el.get('id')
            el_class = " ".join(el.get('class', []))
            el_name = el.get('name')
            el_text = el.get_text(strip=True)[:50]
            
            # Construct a robust selector hint
            selector_parts = [tag_name]
            if el_id: selector_parts.append(f"#{el_id}")
            if el_class: selector_parts.append(f".{'.'.join(el_class.split())}")
            if el_name: selector_parts.append(f"[name='{el_name}']")
            
            hint = f"- <{tag_name}> Text='{el_text}' ID='{el_id}' Name='{el_name}'"
            if el_id:
                hint += f" -> Suggest: #{el_id}"
            elif el_name:
                hint += f" -> Suggest: [name='{el_name}']"
            
            interactive_buffer.append(hint)
        
        # IMPORTANT: Extract tables FIRST before removing them
        tables_buffer = await self.get_tables_content()
            
        # Remove noise
        for tag in soup(['script', 'style', 'svg', 'footer', 'header']):
            tag.decompose()
            
        # Convert to text/markdown
        converter = html2text.HTML2Text()
        converter.ignore_links = False
        converter.ignore_images = True
        markdown = converter.handle(str(soup))
        
        # Combine - put tables FIRST so they don't get truncated
        full_summary = "\n".join(interactive_buffer[:60]) + "\n\n"
        full_summary += tables_buffer + "\n\n"
        full_summary += "### PAGE CONTENT:\n" + markdown
        
        # Increased limit to 32k chars
        return full_summary[:32000]

    async def get_tables_content(self) -> str:
        """
        Directly extracts all tables from the page with their IDs and content.
        This is important because tables often contain the search results.
        """
        if not self.page:
            return ""
        
        try:
            # JavaScript to extract all table data
            tables_data = await self.page.evaluate('''() => {
                const tables = document.querySelectorAll('table');
                const result = [];
                
                tables.forEach((table, tableIndex) => {
                    const tableInfo = {
                        id: table.id || `table_${tableIndex}`,
                        className: table.className,
                        rows: []
                    };
                    
                    const rows = table.querySelectorAll('tr');
                    rows.forEach((row, rowIndex) => {
                        const cells = row.querySelectorAll('td, th');
                        const cellTexts = [];
                        cells.forEach(cell => {
                            cellTexts.push(cell.innerText.trim().substring(0, 100));
                        });
                        if (cellTexts.length > 0) {
                            tableInfo.rows.push(cellTexts);
                        }
                    });
                    
                    if (tableInfo.rows.length > 0) {
                        result.push(tableInfo);
                    }
                });
                
                return result;
            }''')
            
            # Format tables for LLM
            buffer = ["### TABLES FOUND ON PAGE:"]
            for table in tables_data:
                table_id = table.get('id', 'unknown')
                table_class = table.get('className', '')
                rows = table.get('rows', [])
                
                buffer.append(f"\n#### TABLE ID='{table_id}' CLASS='{table_class}' ({len(rows)} rows)")
                buffer.append(f"Suggested row selector: #{table_id} tbody tr" if table_id != 'unknown' else "Suggested row selector: table tbody tr")
                
                # Show first 20 rows max
                for i, row in enumerate(rows[:20]):
                    buffer.append(f"  Row {i}: {' | '.join(row)}")
                
                if len(rows) > 20:
                    buffer.append(f"  ... and {len(rows) - 20} more rows")
            
            return "\n".join(buffer) if len(buffer) > 1 else "### NO TABLES FOUND"
            
        except Exception as e:
            print(f"Error extracting tables: {e}")
            return "### ERROR EXTRACTING TABLES"

    async def click_element(self, selector: str):
        """Reliably clicks an element with multiple fallback strategies."""
        if not self.page:
            return
            
        print(f"BrowserManager: Clicking {selector}")
        
        # Strategy 1: Wait for visible and click normally
        try:
            await self.page.wait_for_selector(selector, state="visible", timeout=3000)
            await self.page.click(selector)
            await self.page.wait_for_load_state("networkidle", timeout=5000)
            print(f"Click succeeded (visible strategy)")
            return
        except Exception as e:
            print(f"Visible click failed: {e}")
        
        # Strategy 2: Element exists but hidden - try scrolling into view first
        try:
            element = await self.page.query_selector(selector)
            if element:
                await element.scroll_into_view_if_needed()
                await asyncio.sleep(0.5)  # Wait for scroll/animation
                await element.click()
                await self.page.wait_for_load_state("networkidle", timeout=5000)
                print(f"Click succeeded (scroll into view strategy)")
                return
        except Exception as e:
            print(f"Scroll+click failed: {e}")
        
        # Strategy 3: Force click (ignores visibility checks)
        try:
            await self.page.click(selector, force=True)
            await self.page.wait_for_load_state("networkidle", timeout=5000)
            print(f"Click succeeded (force click strategy)")
            return
        except Exception as e:
            print(f"Force click failed: {e}")
        
        # Strategy 4: JavaScript click (works for elements hidden by CSS)
        try:
            await self.page.evaluate(f'''() => {{
                const el = document.querySelector("{selector}");
                if (el) {{
                    el.click();
                    return true;
                }}
                return false;
            }}''')
            await self.page.wait_for_load_state("networkidle", timeout=5000)
            print(f"Click succeeded (JavaScript strategy)")
            return
        except Exception as e:
            print(f"JavaScript click failed: {e}")
        
        # Strategy 5: Try triggering any onclick handler directly
        try:
            await self.page.evaluate(f'''() => {{
                const el = document.querySelector("{selector}");
                if (el && el.onclick) {{
                    el.onclick();
                    return true;
                }}
                return false;
            }}''')
            await self.page.wait_for_load_state("networkidle", timeout=5000)
            print(f"Click succeeded (onclick trigger strategy)")
            return
        except Exception as e:
            print(f"Onclick trigger failed: {e}")
            raise Exception(f"All click strategies failed for {selector}")

    async def fill_form(self, selector: str, value: str):
        """Fills a form field thoroughly (clear, fill, press Tab)."""
        if not self.page:
            return
            
        print(f"BrowserManager: Filling {selector} with '{value}'")
        try:
            await self.page.wait_for_selector(selector, state="visible", timeout=5000)
            await self.page.fill(selector, "") # Clear first
            await self.page.fill(selector, value)
            await self.page.press(selector, "Tab") # Trigger validation
        except Exception as e:
            print(f"Fill failed for {selector}: {e}")
            raise e

    async def get_page(self) -> Page:
        """Returns the raw Page object if needed."""
        if not self.page:
            await self.initialize()
        return self.page
            
    async def close(self):
        """Closes the browser."""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        self.playwright = None
        self.browser = None
        self.page = None
