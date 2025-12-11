import asyncio
from typing import Dict, Any, List

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage

from agent_state import AgentState
from browser_manager import BrowserManager
from schemas import NavigationDecision, SearchFormDetails, ExtractionResult
import os
from dotenv import load_dotenv

load_dotenv()

# Initialize LLM
llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash-exp",
    temperature=0,
    google_api_key=os.getenv("GOOGLE_API_KEY")
)

browser = BrowserManager()

async def node_navigate(state: AgentState) -> Dict[str, Any]:
    """Node that handles initial or subsequent navigation."""
    print("--- Node: Navigate ---")
    
    # Check if we need to go to a new URL or just refresh content
    if state["attempt_count"] == 0:
        print(f"Navigating to Target: {state['target_url']}")
        await browser.go_to(state["target_url"])
    
    # Always refresh summary
    summary = await browser.get_clean_content()
    return {"current_page_summary": summary}

async def node_analyze(state: AgentState) -> Dict[str, Any]:
    """Analyzes the page content to decide if we are on the search page."""
    print("--- Node: Analyze ---")
    
    structured_llm = llm.with_structured_output(NavigationDecision)
    
    prompt = f"""
    You are a web navigator. 
    Analyze the following page content summary to decide if this is the Search Page we are looking for.
    We are looking for a page with a *visible* form to search for "Official Records", "Deed Search", or "Grantor Index".
    
    # CRITICAL INSTRUCTIONS:
    1. If you see a DISCLAIMER, TERMS OF SERVICE, or an 'Accept' button (e.g. #btnButton), this is NOT the search page. Click that button.
    2. If you DO NOT see a specific 'Name' or 'Party' input field, this is NOT the search page.
    
    PAGE SUMMARY:
    {state['current_page_summary']}
    
    Decide: Is this the search page? If not, identify the CSS selector for the link OR button that most likely leads there (or accepts the disclaimer).
    """
    
    decision: NavigationDecision = await structured_llm.ainvoke([
        SystemMessage(content="You are a precise autonomous web agent."),
        HumanMessage(content=prompt)
    ])
    
    print(f"Decision: Is Search Page? {decision.is_search_page}")
    print(f"Reasoning: {decision.reasoning}")
    
    updates = {}
    if decision.is_search_page:
        updates["status"] = "SEARCH_PAGE_FOUND"
    else:
        updates["status"] = "NAVIGATING"
        # Store selector in search_selectors for the click_link node
        updates["search_selectors"] = {"link": decision.suggested_link_selector}
    
    updates["logs"] = state["logs"] + [f"Analyzed page. Decision: {decision.is_search_page}. Reasoning: {decision.reasoning}"]
    return updates

async def node_click_link(state: AgentState) -> Dict[str, Any]:
    """Clicks the link suggested by the analysis node."""
    print("--- Node: Click Link ---")
    
    # Retrieve the selector stored in the previous step
    selectors = state.get("search_selectors", {})
    link_selector = selectors.get("link")
    
    if link_selector:
        print(f"Clicking suggested link: {link_selector}")
        try:
            await browser.click_element(link_selector)
            return {
                "attempt_count": state["attempt_count"] + 1, 
                "logs": state["logs"] + [f"Clicked link: {link_selector}"]
            }
        except Exception as e:
            return {
                "attempt_count": state["attempt_count"] + 1,
                "logs": state["logs"] + [f"Failed to click link {link_selector}: {e}"]
            }
    else:
        print("No link selector provided.")
        return {
            "attempt_count": state["attempt_count"] + 1,
            "logs": state["logs"] + ["No link selector provided to click."]
        }

async def node_perform_search(state: AgentState) -> Dict[str, Any]:
    """Identifies form elements and executes the search."""
    print("--- Node: Perform Search ---")
    
    structured_llm = llm.with_structured_output(SearchFormDetails)
    
    prompt = f"""
    We are on the Search Page. Find the NAME/PARTY search input field and submit button.
    
    IMPORTANT - LOOK FOR ID-BASED SELECTORS in the INTERACTIVE ELEMENTS section:
    - The Name input field typically has an ID like 'name-Name', 'txtName', 'PartyName', 'searchName'
    - Use the ID selector format: #elementId (e.g., #name-Name)
    - The Submit button typically has an ID like 'submit-Name', 'btnSearch', 'searchButton'
    
    DO NOT use complex table-based selectors. Prefer simple ID selectors like:
    - #name-Name (for input)
    - #submit-Name or #nameSearchModalSubmit (for submit)
    
    PAGE SUMMARY:
    {state['current_page_summary']}
    """
    
    form_details: SearchFormDetails = await structured_llm.ainvoke([
        SystemMessage(content="You are a form field identifier. Always prefer simple ID-based selectors (#id) over complex CSS selectors."),
        HumanMessage(content=prompt)
    ])
    
    print(f"Form Details: Input={form_details.input_selector}, Submit={form_details.submit_button_selector}")
    
    # Fallback input selectors for name search
    input_fallbacks = [
        "#name-Name",
        "#txtName",
        "#PartyName",
        "#searchName",
        "input[name='Name']",
        "input[name='name']",
        "input[id*='Name']",
        "input[id*='name']"
    ]
    
    # Fallback submit button selectors
    submit_fallbacks = [
        "#submit-Name",
        "#nameSearchModalSubmit",
        "#btnSearch",
        "#searchButton",
        "button[type='submit']",
        "a.btn-primary[id*='submit']",
        "input[type='submit']"
    ]
    
    page = await browser.get_page()
    
    # Try to find a working input field
    input_selector = form_details.input_selector
    input_found = False
    
    # First try the LLM's suggestion
    if input_selector:
        try:
            element = await page.query_selector(input_selector)
            if element:
                input_found = True
                print(f"LLM selector works: {input_selector}")
        except:
            pass
    
    # If LLM selector didn't work, try fallbacks
    if not input_found:
        print("LLM input selector failed, trying fallbacks...")
        for fallback in input_fallbacks:
            try:
                element = await page.query_selector(fallback)
                if element:
                    input_selector = fallback
                    input_found = True
                    print(f"Found input with fallback: {fallback}")
                    break
            except:
                continue
    
    if not input_found:
        print("Error: No input selector found. Aborting search.")
        return {
            "status": "FAILED",
            "logs": state["logs"] + ["Search failed: No input selector found."]
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
        await asyncio.sleep(1)
        
        if submit_selector:
            await browser.click_element(submit_selector)
        else:
            # Try pressing Enter on the input field
            await page.press(input_selector, "Enter")
        
        # Explicit wait for results
        print("Waiting for results...")
        await asyncio.sleep(3)
        # Refresh content to see results
        summary = await browser.get_clean_content()
        
        return {
            "status": "SEARCH_EXECUTED",
            "current_page_summary": summary,
            "search_selectors": {
                "input": input_selector,
                "submit": submit_selector
            },
            "logs": state["logs"] + [f"Executed search for '{state['search_query']}'"]
        }
    except Exception as e:
        return {
            "status": "FAILED",
            "logs": state["logs"] + [f"Search execution failed: {str(e)}"]
        }


async def node_extract(state: AgentState) -> Dict[str, Any]:
    """Analyzes results and extracts data, then saves to CSV."""
    print("--- Node: Extract ---")
    
    # Step 1: Wait longer for results to fully load (dynamic content)
    print("Waiting for results to load...")
    await asyncio.sleep(5)  # Increased to 5 seconds for dynamic content
    
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
        fallback_selectors = [
            "#resultsTable tbody tr",  # Flagler site specific
            "#resultsTable tr",
            "table#resultsTable tbody tr",
            "table tbody tr",
            ".results-table tr",
            ".data-grid tr",
            "[class*='result'] tr",
            "table tr:not(:first-child)",
            "#gridResults tr",
            ".grid-canvas .slick-row"
        ]
        for fallback in fallback_selectors:
            try:
                rows = await page.query_selector_all(fallback)
                if len(rows) > 0:
                    print(f"Found {len(rows)} rows with fallback selector: {fallback}")
                    break
            except Exception as e:
                print(f"Fallback selector {fallback} failed: {e}")
    
    # Extract data from rows (runs for both primary and fallback selectors)
    if len(rows) > 0:
        print(f"Extracting data from {len(rows)} rows...")
        for i, row in enumerate(rows[:50]):  # Limit to 50 rows
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
            output_dir = os.path.join(os.getcwd(), "extracted_data")
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
        "status": "COMPLETED",
        "extracted_data": extracted_data,
        "current_page_summary": fresh_content,
        "logs": state["logs"] + [f"Extraction complete. Found {len(extracted_data)} records."]
    }
