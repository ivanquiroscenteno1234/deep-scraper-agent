import asyncio
import sys
import os
sys.path.insert(0, os.getcwd())
from deep_scraper.core.browser import BrowserManager

async def debug_flagler():
    browser = BrowserManager()
    try:
        url = "https://records.flaglerclerk.com/"
        print(f"Navigating to {url}...")
        await browser.go_to(url)
        
        # Wait a bit for dynamic content
        await asyncio.sleep(5)
        
        output = []
        output.append("\n--- extracting content ---")
        content = await browser.get_clean_content()
        output.append(content)
        output.append("\n--- end content ---")
        
        # Check specific selectors
        output.append("\nChecking for Search Form elements:")
        has_submit = await browser.page.evaluate("""() => {
            return !!document.querySelector("a#btnButton");
        }""")
        output.append(f"Has Submit Button (a#btnButton): {has_submit}")
        
        has_input = await browser.page.evaluate("""() => {
            return !!document.querySelector("input[name='beaux']"); 
        }""") 
        
        params = await browser.page.evaluate("""() => {
            const inputs = Array.from(document.querySelectorAll('input[type="text"]'));
            const buttons = Array.from(document.querySelectorAll('a.btn, button'));
            
            // Check visibility of accept button
            const accept = document.querySelector("#idAcceptYes");
            const acceptVisible = accept ? (accept.offsetParent !== null && window.getComputedStyle(accept).display !== 'none') : false;
            
            return {
                inputs: inputs.map(i => i.outerHTML),
                buttons: buttons.map(b => b.outerHTML),
                accept_visible: acceptVisible,
                accept_html: accept ? accept.outerHTML : null
            }
        }""")
        
        output.append(f"Visible Inputs count: {len(params['inputs'])}")
        output.append(f"Visible Buttons count: {len(params['buttons'])}")
        output.append(f"Accept Button Visible: {params['accept_visible']}")
        output.append(f"Accept Button HTML: {params['accept_html']}")
        
        with open("debug_output.txt", "w", encoding="utf-8") as f:
            f.write("\n".join(output))
        
    finally:
        await browser.close()

if __name__ == "__main__":
    asyncio.run(debug_flagler())
