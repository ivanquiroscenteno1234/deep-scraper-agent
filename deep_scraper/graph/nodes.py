import asyncio
from typing import Dict, Any, List

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage

from deep_scraper.core.state import AgentState
from deep_scraper.core.browser import BrowserManager
from deep_scraper.core.schemas import NavigationDecision, SearchFormDetails, ExtractionResult
import os
from dotenv import load_dotenv

load_dotenv()

# Initialize LLM with thinking enabled for deeper reasoning
llm = ChatGoogleGenerativeAI(
    model=os.getenv("GEMINI_MODEL"),
    temperature=0,
    google_api_key=os.getenv("GOOGLE_API_KEY"),
    model_kwargs={
        "thinking_config": {
            "include_thoughts": True,
            "thinking_level": os.getenv("THINKING_LEVEL")
        }
    }
)

browser = BrowserManager()

async def node_navigate(state: AgentState) -> Dict[str, Any]:
    """Node that handles initial or subsequent navigation."""
    print("--- Node: Navigate ---", flush=True)
    
    # Check if we need to go to a new URL or just refresh content
    if state["attempt_count"] == 0:
        print(f"Navigating to Target: {state['target_url']}")
        await browser.go_to(state["target_url"])
    
    # Always refresh summary
    summary = await browser.get_clean_content()
    return {"current_page_summary": summary}

async def node_analyze(state: AgentState) -> Dict[str, Any]:
    """Analyzes the page content to decide if we are on the search page."""
    print(f"--- Node: Analyze ---", flush=True)
    
    structured_llm = llm.with_structured_output(NavigationDecision)
    
    prompt = f"""Analyze this web page and classify it. Follow these rules STRICTLY in ORDER.

## PAGE CONTENT:
{state['current_page_summary']}

## RULE 1 (HIGHEST PRIORITY): Check for VISIBLE Text Input Search Form
A SEARCH PAGE must have an actual TEXT INPUT FIELD where you can TYPE a search term.

COUNTS AS SEARCH PAGE:
- An <input type="text"> or <input> field where you can TYPE text
- Must have a label like "Name", "Party Name", "Grantor", "Search"
- Must have a Submit/Search button nearby

DOES NOT COUNT AS SEARCH PAGE:
- A <select> dropdown menu (like "Quick Search" dropdowns) - this is NOT a text input!
- Navigation links/icons to different search types
- Home pages with options to choose

CRITICAL: A dropdown/select element is NOT a text input field!
If the only form element is a <select> dropdown, this is NOT a search page.

IF YOU SEE A VISIBLE TEXT INPUT FIELD (not select/dropdown) → is_search_page=True
(Even if there's "disclaimer" text somewhere - ignore it if the text input is visible)

## RULE 2: Check for BLOCKING Disclaimer Modal
ONLY if Rule 1 did NOT match (no visible input fields):
- Look for a MODAL or POPUP blocking the page with disclaimer text
- Text like "If you choose not to accept please exit this application"
- "Accept" or "I Agree" buttons that must be clicked to proceed

If a BLOCKING disclaimer is found → is_disclaimer_page=True, is_search_page=False
Set suggested_link_selector to: #idAcceptYes OR #btnButton OR input[value*='accept' i]

NOTE: If the disclaimer is just HTML in the background (class="hide" or not visible) but you can see
search input fields, then it's a SEARCH PAGE, not a disclaimer page!

## RULE 3: Check for Login Requirement  
If page has username AND password fields → requires_login=True, is_search_page=False

## RULE 4: Navigation Page (no search form yet)
If NO visible text input fields AND NO blocking disclaimer:
- This is a navigation/landing page with links to different search types
- Look for links like "Name Search", "Search", "Official Records"
- Set is_search_page=False, is_disclaimer_page=False
- Provide suggested_link_selector for the navigation link

## CRITICAL DISTINCTION:
- "Name Search" as a LINK/ICON = Navigation page (click to get to search)
- "Name:" label with TEXT INPUT BOX = Search page (ready to type and search)
"""
    
    decision: NavigationDecision = await structured_llm.ainvoke([
        SystemMessage(content="""You are a precise web page classifier. 
        Carefully distinguish between disclaimer pages, login pages, and actual search forms.
        CRITICAL: NEVER use ':contains()' selectors (invalid CSS). Use standard CSS or 'a:has-text()' for Playwright."""),
        HumanMessage(content=prompt)
    ])
    
    print(f"Decision: Is Search Page? {decision.is_search_page}")
    print(f"Is Disclaimer? {decision.is_disclaimer_page}")
    print(f"Requires Login? {decision.requires_login}")
    print(f"Reasoning: {decision.reasoning}")
    
    updates = {}
    
    # Handle login requirement - stop the agent
    if decision.requires_login:
        updates["status"] = "LOGIN_REQUIRED"
        updates["logs"] = (state.get("logs") or []) + [f"Page requires login. Cannot proceed."]
        return updates
    
    # FAILSAFE: Verify LLM's is_search_page decision by checking for actual text inputs
    # LLM sometimes marks navigation pages as search pages, so we verify programmatically
    page = await browser.get_page()
    has_actual_text_input = False
    
    if decision.is_search_page:
        # Check if there are actual visible text inputs on the page
        text_input_selectors = [
            "input[type='text']:visible",
            "input:not([type]):visible",  # Default type is text
            "#name-Name",  # Flagler specific
            "#Name",  # Common name field
            "input[name='name']",
        ]
        
        for sel in text_input_selectors:
            try:
                locator = page.locator(sel)
                count = await locator.count()
                if count > 0:
                    # Verify at least one is visible
                    for i in range(min(count, 3)):  # Check first 3
                        try:
                            is_visible = await locator.nth(i).is_visible()
                            if is_visible:
                                has_actual_text_input = True
                                print(f"Verified: Found visible text input with selector: {sel}")
                                break
                        except:
                            continue
                if has_actual_text_input:
                    break
            except Exception as e:
                continue
        
        if not has_actual_text_input:
            print("OVERRIDE: LLM said is_search_page=True but no visible text inputs found!")
            print("Treating as navigation page instead.")
            decision.is_search_page = False
    
    # PRIORITY ORDER: Disclaimer > Search Page > Navigation
    # If it's a disclaimer page, we MUST click accept first, even if there's also a search form
    if decision.is_disclaimer_page:
        updates["status"] = "NAVIGATING"  # Need to click accept button first
        updates["is_disclaimer_page"] = True  # Track this for click_link node
        updates["search_selectors"] = {"link": decision.suggested_link_selector}
        print("Disclaimer detected - will click accept button first")
    elif decision.is_search_page and has_actual_text_input:
        updates["status"] = "SEARCH_PAGE_FOUND"
    else:
        updates["status"] = "NAVIGATING"
        updates["search_selectors"] = {"link": decision.suggested_link_selector}
    
    log_msg = f"Analyzed page. Search page: {decision.is_search_page}, Disclaimer: {decision.is_disclaimer_page}, Login required: {decision.requires_login}. Reasoning: {decision.reasoning}"
    updates["logs"] = (state.get("logs") or []) + [log_msg]
    return updates

async def node_click_link(state: AgentState) -> Dict[str, Any]:
    """Clicks the link suggested by the analysis node, with fallbacks for accept buttons and nav links."""
    print(f"--- Node: Click Link ---", flush=True)
    
    # Retrieve the selector stored in the previous step
    selectors = state.get("search_selectors", {})
    link_selector = selectors.get("link")
    is_disclaimer = state.get("is_disclaimer_page", False)
    
    page = await browser.get_page()
    
    # Common accept/disclaimer button selectors as fallback
    accept_button_fallbacks = [
        "#btnButton",
        "#idAcceptYes",  # Flagler site specific
        "input[value*='accept' i]",
        "input[value*='Accept' i]",
        "input[value*='I accept' i]",
        "input[value*='agree' i]",
        "button:has-text('Accept')",
        "button:has-text('I Accept')",
        "button:has-text('I Agree')",
        "button:has-text('Continue')",
        "a.btn:has-text('Accept')",  # Bootstrap styled accept
        "input[type='submit'][value*='accept' i]",
        "a:has-text('Accept')",
    ]
    
    # Navigation link fallbacks for home/landing pages
    navigation_link_fallbacks = [
        "a[title*='Name Search' i]",
        "a:has-text('Name Search')",
        "a:has-text('name search')",
        ".divInside a[title*='Name' i]",  # Flagler specific icon container
        "a[onclick*='searchCriteriaName']",  # Flagler specific onclick
        "a:has-text('Official Records')",
        "a:has-text('Search Records')",
        "a[href*='search' i]:has-text('Name')",
        "#topNavLinksSearch a",  # Flagler nav bar search link
    ]
    
    clicked = False
    
    # First try the LLM-provided selector
    if link_selector:
        print(f"Trying LLM selector: {link_selector}")
        try:
            await browser.click_element(link_selector)
            clicked = True
            print(f"Clicked LLM selector: {link_selector}")
        except Exception as e:
            print(f"LLM selector failed: {e}")
    
    # If LLM selector failed or wasn't provided, try fallbacks
    if not clicked:
        # First try accept button fallbacks (for disclaimer pages)
        print("Trying fallback accept button selectors...")
        for fallback in accept_button_fallbacks:
            try:
                locator = page.locator(fallback)
                if await locator.count() > 0:
                    is_visible = await locator.first.is_visible()
                    if is_visible:
                        await locator.first.click()
                        clicked = True
                        print(f"Clicked accept fallback: {fallback}")
                        break
            except Exception as e:
                continue
    
    # If still not clicked, try navigation link fallbacks (for landing pages)
    if not clicked:
        print("Trying fallback navigation link selectors...")
        for fallback in navigation_link_fallbacks:
            try:
                locator = page.locator(fallback)
                if await locator.count() > 0:
                    is_visible = await locator.first.is_visible()
                    if is_visible:
                        await locator.first.click()
                        clicked = True
                        print(f"Clicked nav link fallback: {fallback}")
                        break
            except Exception as e:
                continue
    
    if clicked:
        # Wait for page transition
        await asyncio.sleep(1)
        return {
            "attempt_count": state["attempt_count"] + 1, 
            "logs": (state.get("logs") or []) + [f"Clicked: {link_selector or 'fallback selector'}"]
        }
    else:
        print("No clickable element found.")
        return {
            "attempt_count": state["attempt_count"] + 1,
            "logs": (state.get("logs") or []) + ["No clickable element found."]
        }

async def node_perform_search(state: AgentState) -> Dict[str, Any]:
    """Identifies form elements and executes the search."""
    print(f"--- Node: Perform Search ---", flush=True)
    
    structured_llm = llm.with_structured_output(SearchFormDetails)
    
    prompt = f"""We are on the Search Page. Find the NAME/PARTY search input field and submit button.

CRITICAL RULES:
1. The input field MUST be a TEXT INPUT (type="text"), NOT a button or submit
2. Look for input fields with labels like "Name", "Party Name", "Grantor", "Search"
3. The submit button should be labeled "Search", "Submit", or similar
4. Do NOT select disclaimer/accept buttons

LOOK FOR ID-BASED SELECTORS:
- Name input: #name-Name, #txtName, #PartyName, #searchName, #Name
- Submit button: #btnSearch, #searchButton, input[value="Search"]

PAGE SUMMARY:
{state['current_page_summary']}
"""
    
    form_details: SearchFormDetails = await structured_llm.ainvoke([
        SystemMessage(content="You are a form field identifier. Find TEXT input fields for search, not buttons."),
        HumanMessage(content=prompt)
    ])
    
    print(f"Form Details: Input={form_details.input_selector}, Submit={form_details.submit_button_selector}")
    
    # Fallback input selectors - MUST be text inputs
    input_fallbacks = [
        # Dallas County PublicSearch
        "input[data-testid='searchInputBox']",
        "input[placeholder*='grantor/grantee' i]",
        "input.clearable-input__input",
        ".clearable-input input",
        # Flagler/Brevard style
        "#name-Name",
        "#Name",
        "#txtName", 
        "#PartyName",
        "#searchName",
        "input[type='text'][id*='name' i]",
        "input[type='text'][id*='Name']",
        "input[type='text'][name*='name' i]",
        "input#name",
        "input[id*='Name']:not([type='submit']):not([type='button']):not([type='radio']):not([type='checkbox'])",
        "input[id*='name']:not([type='submit']):not([type='button']):not([type='radio']):not([type='checkbox'])",
        # Generic text inputs
        "input[type='text']:visible",
        "input:not([type]):not([hidden])"
    ]
    
    # Fallback submit button selectors
    submit_fallbacks = [
        # Dallas County PublicSearch
        "button[data-testid='searchSubmitButton']",
        "button[type='submit'][aria-label*='search' i]",
        # Flagler/Brevard style
        "input[value='Search']",
        "#btnSearch",
        "#searchButton",
        "#submit-Name",
        "#nameSearchModalSubmit",
        "button:has-text('Search')",
        "input[type='submit'][value*='Search' i]",
        "button[type='submit']",
        "input[type='submit']"
    ]
    
    page = await browser.get_page()
    
    # Try to find a working input field
    input_selector = form_details.input_selector
    input_found = False
    
    # First try the LLM's suggestion, but validate it's a text input
    if input_selector:
        try:
            element = await page.query_selector(input_selector)
            if element:
                # Validate it's actually a text input
                input_type = await element.get_attribute("type")
                tag_name = await element.evaluate("el => el.tagName.toLowerCase()")
                
                if tag_name == "input" and input_type in ["text", "search", None, ""]:
                    input_found = True
                    print(f"LLM selector works and is text input: {input_selector}")
                else:
                    print(f"LLM selector {input_selector} is not a text input (type={input_type}, tag={tag_name})")
        except Exception as e:
            print(f"LLM selector check failed: {e}")
    
    # If LLM selector didn't work, try fallbacks
    if not input_found:
        print("LLM input selector failed, trying fallbacks...")
        for fallback in input_fallbacks:
            try:
                element = await page.query_selector(fallback)
                if element:
                    # Validate it's a text input
                    input_type = await element.get_attribute("type")
                    tag_name = await element.evaluate("el => el.tagName.toLowerCase()")
                    
                    if tag_name == "input" and input_type in ["text", "search", None, ""]:
                        input_selector = fallback
                        input_found = True
                        print(f"Found text input with fallback: {fallback}")
                        break
                    else:
                        print(f"Fallback {fallback} is not a text input, skipping")
            except:
                continue
    
    if not input_found:
        print("Error: No text input selector found. Aborting search.")
        return {
            "status": "FAILED",
            "logs": (state.get("logs") or []) + ["Search failed: No text input selector found."]
        }
    
    # Try to find a working submit button
    submit_selector = form_details.submit_button_selector
    submit_found = False
    
    if submit_selector:
        try:
            element = await page.query_selector(submit_selector)
            if element:
                submit_found = True
                print(f"LLM submit selector works: {submit_selector}")
        except:
            pass
    
    if not submit_found:
        print("LLM submit selector failed, trying fallbacks...")
        for fallback in submit_fallbacks:
            try:
                element = await page.query_selector(fallback)
                if element:
                    submit_selector = fallback
                    submit_found = True
                    print(f"Found submit with fallback: {fallback}")
                    break
            except:
                continue
    
    if not submit_found:
        print("Warning: No submit button found, will try to press Enter.")
        submit_selector = None
    
    # Execute Actions
    try:
        await browser.fill_form(input_selector, state["search_query"])
        
        if submit_selector:
            await browser.click_element(submit_selector)
        else:
            # Try pressing Enter on the input field
            await page.press(input_selector, "Enter")
        
        # Wait for page to respond
        print("Waiting for results...")
        await asyncio.sleep(2)
        
        # NORMAL FLOW: Check if results grid appeared immediately
        results_found = await check_for_results_grid(page)
        
        if results_found:
            print("Results grid found immediately - normal flow")
        else:
            # EDGE CASE: No results visible - check for popup that needs handling
            print("No results grid - checking for popup...")
            popup_handled = await handle_search_popups(page)
            if popup_handled:
                print("Handled popup modal - waiting for results")
                await asyncio.sleep(2)
        
        # Refresh content to see results
        summary = await browser.get_clean_content()
        
        return {
            "status": "SEARCH_EXECUTED",
            "current_page_summary": summary,
            "search_selectors": {
                "input": input_selector,
                "submit": submit_selector
            },
            "logs": (state.get("logs") or []) + [f"Executed search for '{state['search_query']}'"]
        }
    except Exception as e:
        return {
            "status": "FAILED",
            "logs": (state.get("logs") or []) + [f"Search execution failed: {str(e)}"]
        }


async def check_for_results_grid(page) -> bool:
    """Check if a results grid/table is visible on the page."""
    result_grid_selectors = [
        "#searchResultsGrid",
        "#resultsTable",
        ".searchGridDiv .t-grid",
        ".gridHolder .t-grid",
        "[class*='result'] table",
        ".t-grid:visible",
        ".grid-canvas",
        "table[class*='result']"
    ]
    
    for selector in result_grid_selectors:
        try:
            locator = page.locator(selector)
            if await locator.count() > 0:
                is_visible = await locator.first.is_visible()
                if is_visible:
                    # Also check it has actual rows (not just headers)
                    rows = await page.query_selector_all(f"{selector} tbody tr")
                    if len(rows) > 0:
                        print(f"Found results grid: {selector} with {len(rows)} rows")
                        return True
        except:
            continue
    
    return False


async def handle_search_popups(page) -> bool:
    """Handles common popup modals that appear after search (e.g., name selection dialogs)."""
    
    # First, check if there's a visible popup window (like the Names selection window)
    # The Brevard site uses #NamesWin for the name selection popup
    popup_window_selectors = [
        "#NamesWin",
        "#frmSchTarget",
        ".t-window:visible",
        "[class*='window']:visible",
    ]
    
    # Check if a popup window is visible
    popup_visible = False
    for window_sel in popup_window_selectors:
        try:
            locator = page.locator(window_sel)
            if await locator.count() > 0:
                # Check if it's actually visible
                is_visible = await locator.first.is_visible()
                if is_visible:
                    popup_visible = True
                    print(f"Popup window found: {window_sel}")
                    break
        except:
            continue
    
    if not popup_visible:
        print("No popup window visible")
        return False
    
    # Look for Done button INSIDE the popup, prioritizing the Names form
    # The submit button for the names form specifically
    popup_done_selectors = [
        "#frmSchTarget input[type='submit']",  # The form submit in Names popup
        "#frmSchTarget input[value='Done']",
        "#NamesWin input[value='Done']",
        "#NamesWin button:has-text('Done')",
        ".t-window:visible input[value='Done']",
        ".t-window:visible button:has-text('Done')",
        "input[value='Done']:visible",
    ]
    
    for selector in popup_done_selectors:
        try:
            locator = page.locator(selector)
            count = await locator.count()
            if count > 0:
                # Make sure the button is visible
                is_visible = await locator.first.is_visible()
                if is_visible:
                    print(f"Clicking popup Done button: {selector}")
                    await locator.first.click()
                    # Wait for popup to close and results to load
                    await asyncio.sleep(2)
                    return True
        except Exception as e:
            print(f"Failed to click {selector}: {e}")
            continue
    
    print("No Done button found in popup")
    return False


async def node_extract(state: AgentState) -> Dict[str, Any]:
    """Analyzes results and extracts data, then saves to CSV."""
    print(f"--- Node: Extract ---", flush=True)
    
    # Brief wait for dynamic content to load
    print("Waiting for results to load...")
    await asyncio.sleep(2)  # Reduced from 5s
    
    # Get fresh page content after search
    fresh_content = await browser.get_clean_content()
    print(f"Fresh content length: {len(fresh_content)} chars")
    
    # Debug: Print first part of content to see what we got
    print("=" * 50)
    print("CONTENT PREVIEW (first 2000 chars):")
    print(fresh_content[:2000])
    print("=" * 50)
    
    structured_llm = llm.with_structured_output(ExtractionResult)
    
    prompt = f"""
    You are analyzing a search results page AFTER a search was executed.
    Your task is to find and identify the search results data.
    
    CRITICAL SELECTOR RULES FOR `row_selector`:
    1. NEVER use the ':contains()' selector (it is not valid CSS).
    2. Use ':has-text()' for Playwright text matching if needed.
    3. Prefer standard CSS: #id, .class, [name='value'], or a[title*='value'].
    
    LOOK FOR:
    1. A table or grid displaying results (rows of data)
    2. Each row likely contains: Name, Date, Document Type, Book/Page numbers, etc.
    3. The main results container - look for TABLE elements with IDs like 'resultsTable'
    
    IMPORTANT - CHECK THE "TABLES FOUND ON PAGE" SECTION:
    - If you see a table with ID 'resultsTable' and rows of data, set has_data to True
    - The row selector should be '#resultsTable tbody tr' or similar
    - Look at the actual row data shown - if there are names, dates, document info, that's the data!
    
    Column names for this type of data usually include:
    - Status, Name, Direct Name, Reverse Name, Record Date, Doc Type, Book Type, Book, Page, Instrument #
    
    If you see a message like "No records found" or "0 results", set has_data to False.
    
    PAGE CONTENT AFTER SEARCH:
    {fresh_content}
    """
    
    result: ExtractionResult = await structured_llm.ainvoke([
        SystemMessage(content="You are a precise data extraction specialist. Look carefully at the TABLES FOUND section."),
        HumanMessage(content=prompt)
    ])
    
    print(f"Extraction Analysis:")
    print(f"  Has Data: {result.has_data}")
    print(f"  Structure: {result.data_structure_type}")
    print(f"  Row Selector: {result.row_selector}")
    print(f"  Column Names: {result.column_names}")
    
    extracted_data = []
    
    # Even if LLM says no data, try fallback selectors anyway
    page = await browser.get_page()
    
    if result.has_data and result.row_selector:
        print(f"Attempting to extract data using selector: {result.row_selector}")
        rows = await page.query_selector_all(result.row_selector)
        print(f"Found {len(rows)} rows with primary selector.")
    else:
        rows = []
    
    # If no rows found, try fallback selectors regardless of LLM decision
    if len(rows) == 0:
        print("Trying fallback selectors...")
        # IMPORTANT: Avoid calendar tables (.t-calendar, .t-content, .t-datepicker-calendar)
        fallback_selectors = [
            "#searchResultsGrid tr",  # Common result grid
            "#resultsTable tbody tr",  # Flagler site specific
            "#resultsTable tr",
            ".searchGridDiv table tbody tr",  # Brevard site - results are in searchGridDiv
            ".gridHolder table tbody tr",
            ".t-grid tbody tr",  # Telerik grid
            "table.t-grid tbody tr",
            "#gridResults tr",
            "[class*='result'] table tbody tr",
            ".results-table tr",
            ".data-grid tr",
            ".grid-canvas .slick-row"
        ]
        
        # Selectors to AVOID (calendars, popups, etc.)
        exclude_containers = [
            ".t-calendar",
            ".t-datepicker",
            "#DocTypesWin",
            "#NamesWin",
            ".t-animation-container"
        ]
        
        for fallback in fallback_selectors:
            try:
                rows = await page.query_selector_all(fallback)
                if len(rows) > 0:
                    # Check if these rows are inside a calendar or popup - skip them
                    first_row = rows[0]
                    is_in_excluded = False
                    for exclude_sel in exclude_containers:
                        parent = await first_row.evaluate(f"el => el.closest('{exclude_sel}') !== null")
                        if parent:
                            print(f"Skipping {fallback} - inside excluded container {exclude_sel}")
                            is_in_excluded = True
                            break
                    
                    if not is_in_excluded:
                        print(f"Found {len(rows)} rows with fallback selector: {fallback}")
                        break
                    else:
                        rows = []  # Reset and try next
            except Exception as e:
                print(f"Fallback selector {fallback} failed: {e}")
    
    # Extract data from rows (runs for both primary and fallback selectors)
    if len(rows) > 0:
        print(f"Extracting data from {len(rows)} rows...")
        first_row_only = True # User requested limit to 1 record
    
        for i, row in enumerate(rows):
            if first_row_only and i >= 1:
                print("Limit reached: stopping after 1st record.")
                break
            
            try:
                # Get all cell data from the row
                cells = await row.query_selector_all("td, th")
                cell_texts = []
                for cell in cells:
                    text = await cell.inner_text()
                    cell_texts.append(text.strip())
                
                # Skip empty rows or header-looking rows
                if not cell_texts or all(t == "" for t in cell_texts):
                    continue
                
                # Create record with column names if available
                if result.column_names and len(result.column_names) > 0:
                    record = {}
                    for j, col_name in enumerate(result.column_names):
                        if j < len(cell_texts):
                            record[col_name] = cell_texts[j]
                    record["_raw"] = " | ".join(cell_texts)
                else:
                    # Just use generic column names
                    record = {f"col_{j}": val for j, val in enumerate(cell_texts)}
                    record["_raw"] = " | ".join(cell_texts)
                
                record["row_index"] = i
                extracted_data.append(record)
                
            except Exception as e:
                print(f"Error extracting row {i}: {e}")
                continue
        
        print(f"Successfully extracted {len(extracted_data)} records.")
        
        # Save to CSV if we have data
        if extracted_data:
            import csv
            import os
            from datetime import datetime
            
            # Create output directory if it doesn't exist
            output_dir = os.path.join(os.getcwd(), "output", "extracted_data")
            os.makedirs(output_dir, exist_ok=True)
            
            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            search_term_clean = state.get("search_query", "unknown").replace(" ", "_").replace(",", "")[:30]
            csv_filename = os.path.join(output_dir, f"results_{search_term_clean}_{timestamp}.csv")
            
            # Write to CSV
            try:
                # Get all unique keys from all records
                all_keys = set()
                for record in extracted_data:
                    all_keys.update(record.keys())
                all_keys = sorted(list(all_keys))
                
                with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.DictWriter(csvfile, fieldnames=all_keys)
                    writer.writeheader()
                    writer.writerows(extracted_data)
                
                print(f"✅ Data saved to: {csv_filename}")
                
            except Exception as e:
                print(f"Error saving to CSV: {e}")
    else:
        print("No data rows found with any selector.")
        if result.no_results_message:
            print(f"No results message: {result.no_results_message}")
    
    return {
        "status": "EXTRACTED",
        "extracted_data": extracted_data,
        "current_page_summary": fresh_content,
        "logs": (state.get("logs") or []) + [f"Extraction complete. Found {len(extracted_data)} records."]
    }


async def node_generate_script(state: AgentState) -> Dict[str, Any]:
    """Generates a Playwright script based on execution logs - NO TEMPLATE, AI decides everything."""
    print("--- Node: Generate Script ---")
    
    # Extract county name from URL
    import re
    from urllib.parse import urlparse
    
    url = state["target_url"]
    parsed = urlparse(url)
    hostname = parsed.hostname or "unknown"
    
    # Try to extract county name from hostname
    county_match = re.search(r'(\w+)clerk', hostname, re.IGNORECASE)
    if county_match:
        county_name = county_match.group(1).lower()
    else:
        county_name = hostname.split('.')[0].replace('records', '').replace('-', '_') or "unknown"
    
    print(f"County name extracted: {county_name}")
    
    # Gather ALL execution info - this is what the AI will use
    logs = state.get("logs", [])
    selectors = state.get("search_selectors", {})
    search_query = state.get("search_query", "")
    extracted_data = state.get("extracted_data", [])
    page_summary = state.get("current_page_summary", "")
    
    # Build prompt with raw execution data - NO TEMPLATE
    prompt = f"""You are an expert Playwright automation developer. 

I just ran an autonomous web scraping agent that successfully navigated a website and extracted data.
Your job is to analyze the execution logs below and generate a COMPLETE, WORKING Playwright script that replicates this workflow.

## EXECUTION SESSION DATA

**Target URL:** {url}
**County/Site Name:** {county_name}
**Search Term Used:** {search_query}

**Execution Logs (in order):**
{chr(10).join(logs)}

**Selectors That Worked:**
- Input field selector: {selectors.get('input', 'Not found')}
- Submit button selector: {selectors.get('submit', 'Not found')}
- Any link clicked: {selectors.get('link', 'None')}

**Final Page Content After Search:**
{page_summary[:3000] if page_summary else 'Not available'}

**Sample of Extracted Data ({len(extracted_data)} total records):**
{extracted_data[:3] if extracted_data else 'No data extracted'}

## YOUR TASK

Generate a complete Python script that:
1. Takes a search_term as a command-line argument
2. Navigates to the URL: {url}
3. Handles any disclaimers/popups based on what the logs show happened
4. Fills the search form and submits
5. Waits for results and extracts data from the results table
6. Saves the data to a CSV file
7. Returns the path to the CSV file

## REQUIREMENTS

- Use `playwright.sync_api` (synchronous API)
- Function name should be: `scrape_{county_name}(search_term: str) -> str`
- Include proper error handling with try/except
- Add timeouts and waits where appropriate
- Close the browser properly in all cases
- Save CSV to: `output/extracted_data/{{county_name}}_{{timestamp}}.csv`
- Include a `if __name__ == "__main__":` block that reads search_term from sys.argv

Generate ONLY the Python code. No explanations, no markdown code blocks. Just raw Python code.
"""

    try:
        # Call AI to generate the script
        result = await llm.ainvoke([
            SystemMessage(content="You are an expert Playwright developer. Generate clean, working Python code only. No markdown, no explanations."),
            HumanMessage(content=prompt)
        ])
        
        generated_code = result.content
        
        # Clean up the code (remove markdown if AI added it anyway)
        if "```python" in generated_code:
            generated_code = generated_code.split("```python")[1].split("```")[0]
        elif "```" in generated_code:
            generated_code = generated_code.split("```")[1].split("```")[0]
        
        generated_code = generated_code.strip()
        
        # Save the script
        output_dir = os.path.join(os.getcwd(), "output", "generated_scripts")
        os.makedirs(output_dir, exist_ok=True)
        
        script_filename = os.path.join(output_dir, f"{county_name}_scraper.py")
        
        with open(script_filename, 'w', encoding='utf-8') as f:
            f.write(generated_code)
        
        print(f"✅ Script generated: {script_filename}")
        
        return {
            "status": "SCRIPT_GENERATED",
            "generated_script_path": script_filename,
            "generated_script_code": generated_code,
            "script_test_attempts": 0,
            "script_error": None,
            "logs": (state.get("logs") or []) + [f"Generated Playwright script: {script_filename}"]
        }
        
    except Exception as e:
        print(f"❌ Script generation failed: {e}")
        return {
            "status": "FAILED",
            "generated_script_path": None,
            "generated_script_code": None,
            "logs": (state.get("logs") or []) + [f"Script generation failed: {str(e)}"]
        }


async def node_test_script(state: AgentState) -> Dict[str, Any]:
    """Tests the generated script by actually running it."""
    print("--- Node: Test Script ---")
    
    script_path = state.get("generated_script_path")
    search_query = state.get("search_query", "Test")
    attempts = state.get("script_test_attempts", 0)
    
    if not script_path or not os.path.exists(script_path):
        return {
            "status": "TEST_FAILED",
            "script_error": "Script file not found",
            "script_test_attempts": attempts + 1,
            "logs": (state.get("logs") or []) + ["Test failed: Script file not found"]
        }
    
    print(f"Testing script: {script_path}")
    print(f"Test attempt: {attempts + 1}")
    
    import subprocess
    import sys
    
    try:
        # Run the script as a subprocess with a timeout
        result = subprocess.run(
            [sys.executable, script_path, search_query],
            capture_output=True,
            text=True,
            timeout=120,  # 2 minute timeout
            cwd=os.getcwd(),
            encoding='utf-8',
            errors='replace'  # Replace undecodable characters instead of crashing
        )
        
        stdout = result.stdout
        stderr = result.stderr
        return_code = result.returncode
        
        print(f"Return code: {return_code}")
        print(f"Stdout: {stdout[:500] if stdout else 'None'}")
        print(f"Stderr: {stderr[:500] if stderr else 'None'}")
        
        # Check if script succeeded
        if return_code == 0 and ("saved" in stdout.lower() or "csv" in stdout.lower()):
            print("✅ Script test PASSED!")
            return {
                "status": "TEST_PASSED",
                "script_error": None,
                "script_test_attempts": attempts + 1,
                "logs": (state.get("logs") or []) + [f"Script test PASSED on attempt {attempts + 1}"]
            }
        else:
            error_msg = stderr if stderr else f"Script returned code {return_code}. Output: {stdout}"
            print(f"❌ Script test FAILED: {error_msg[:200]}")
            return {
                "status": "TEST_FAILED",
                "script_error": error_msg,
                "script_test_attempts": attempts + 1,
                "logs": (state.get("logs") or []) + [f"Script test FAILED on attempt {attempts + 1}: {error_msg[:100]}"]
            }
            
    except subprocess.TimeoutExpired:
        error_msg = "Script execution timed out after 120 seconds"
        print(f"❌ {error_msg}")
        return {
            "status": "TEST_FAILED",
            "script_error": error_msg,
            "script_test_attempts": attempts + 1,
            "logs": (state.get("logs") or []) + [f"Script test FAILED: {error_msg}"]
        }
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Script test error: {error_msg}")
        return {
            "status": "TEST_FAILED",
            "script_error": error_msg,
            "script_test_attempts": attempts + 1,
            "logs": (state.get("logs") or []) + [f"Script test error: {error_msg}"]
        }


async def node_fix_script(state: AgentState) -> Dict[str, Any]:
    """Asks AI to fix the script based on the error message."""
    print("--- Node: Fix Script ---")
    
    script_code = state.get("generated_script_code", "")
    script_error = state.get("script_error", "Unknown error")
    script_path = state.get("generated_script_path", "")
    attempts = state.get("script_test_attempts", 0)
    
    print(f"Fixing script after attempt {attempts}")
    print(f"Error: {script_error[:200]}")
    
    prompt = f"""The following Playwright script failed with an error. Fix it.

## CURRENT SCRIPT
```python
{script_code}
```

## ERROR MESSAGE
{script_error}

## INSTRUCTIONS
1. Analyze the error message
2. Fix the issue in the script
3. Return the COMPLETE fixed script
4. Make sure all imports are correct
5. Ensure proper error handling

Return ONLY the fixed Python code. No explanations, no markdown code blocks.
"""

    try:
        result = await llm.ainvoke([
            SystemMessage(content="You are an expert Python debugger. Fix the script and return only working Python code."),
            HumanMessage(content=prompt)
        ])
        
        fixed_code = result.content
        
        # Clean up
        if "```python" in fixed_code:
            fixed_code = fixed_code.split("```python")[1].split("```")[0]
        elif "```" in fixed_code:
            fixed_code = fixed_code.split("```")[1].split("```")[0]
        
        fixed_code = fixed_code.strip()
        
        # Save the fixed script
        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(fixed_code)
        
        print(f"✅ Script fixed and saved")
        
        return {
            "status": "SCRIPT_FIXED",
            "generated_script_code": fixed_code,
            "logs": (state.get("logs") or []) + [f"Script fixed after attempt {attempts}"]
        }
        
    except Exception as e:
        print(f"❌ Script fix failed: {e}")
        return {
            "status": "FIX_FAILED",
            "logs": (state.get("logs") or []) + [f"Script fix failed: {str(e)}"]
        }


