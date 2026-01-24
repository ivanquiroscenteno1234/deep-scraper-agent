"""
Navigation nodes - Page navigation and analysis.

Contains:
- node_navigate_mcp: Navigate to URLs, start codegen session
- node_analyze_mcp: Classify pages (search, disclaimer, results grid)
"""

import os
import re
from typing import Any, Dict
from urllib.parse import urlparse

from langchain_core.messages import SystemMessage, HumanMessage

from deep_scraper.core.state import AgentState
from deep_scraper.graph.nodes.config import (
    llm,
    get_mcp_browser,
    reset_mcp_browser,
    NavigationDecision,
    clean_html_for_llm,
    StructuredLogger,
)

# Bolt ⚡ Optimization: Pre-compiled search indicators to avoid repeated .lower() calls
_SEARCH_INDICATORS = [
    # AcclaimWeb patterns
    "#SearchOnName", "SearchOnName", "#RecordDateFrom", "#RecordDateTo",
    # Landmark Web patterns (Flagler, etc.)
    "name-Name", "#name-Name", "beginDate-Name", "endDate-Name",
    "#nameSearchModalSubmit", "nameSearchModal",
    # Generic patterns
    'type="search"', 'name="searchTerm"', 'id="searchInput"',
    "SearchCriteria", "searchForm", "txtSearch",
]
_SEARCH_INDICATORS_LOWER = [s.lower() for s in _SEARCH_INDICATORS]


async def node_navigate_mcp(state: AgentState) -> Dict[str, Any]:
    """
    Navigate to target URL using MCP and start codegen session.
    
    Records step: {"action": "goto", "url": url}
    """
    log = StructuredLogger("Navigate")
    log.info("Starting navigation")
    
    # On first navigation (attempt 0), reset browser to ensure fresh state
    attempt_count = state.get("attempt_count", 0)
    if attempt_count == 0:
        log.info("First run - resetting browser for fresh state")
        try:
            from deep_scraper.core.mcp_client import get_mcp_client
            temp_client = get_mcp_client()
            if await temp_client.is_server_running():
                await temp_client.connect()
                await temp_client.close()
                log.success("Existing browser closed")
        except Exception as e:
            log.debug(f"No existing browser to close: {e}")
        
        await reset_mcp_browser()
    
    browser = await get_mcp_browser()
    url = state["target_url"]
    
    # Start codegen session on first navigation
    if not browser._codegen_started:
        parsed = urlparse(url)
        hostname = parsed.hostname or "unknown"
        county_match = re.search(r'(\w+)clerk', hostname, re.IGNORECASE)
        if county_match:
            county_name = county_match.group(1).lower()
        else:
            county_name = hostname.split('.')[0].replace('records', '').replace('-', '_') or "unknown"
        
        output_path = os.path.join(os.getcwd(), "output", "data")
        os.makedirs(output_path, exist_ok=True)
        
        await browser.start_codegen_session(output_path, f"{county_name}_scraper")
    
    # Navigate
    log.info(f"Navigating to: {url}")
    summary = await browser.goto(url)
    log.success("Page loaded")
    
    # Track step
    recorded_steps = state.get("recorded_steps", [])
    recorded_steps.append({
        "action": "goto",
        "url": url,
        "description": "Navigate to target URL"
    })
    
    return {
        "current_page_summary": summary,
        "attempt_count": state.get("attempt_count", 0) + 1,
        "recorded_steps": recorded_steps,
        "logs": (state.get("logs") or []) + log.get_logs()
    }


async def node_analyze_mcp(state: AgentState) -> Dict[str, Any]:
    """
    Analyze the page using MCP snapshot and LLM classification.
    
    Determines if page is: SEARCH_PAGE, DISCLAIMER, RESULTS_GRID, or LOGIN_REQUIRED
    """
    log = StructuredLogger("Analyze")
    log.info("Analyzing page")
    
    browser = await get_mcp_browser()
    
    # Get page snapshot and clean it for LLM
    snapshot = await browser.get_snapshot()
    raw_html = snapshot.get("html", str(snapshot))
    page_content = clean_html_for_llm(raw_html, max_length=100000)
    
    # Heuristic check: If we see search inputs, it's likely a search page
    # even if LLM gets distracted by persistent disclaimer text.
    # Expanded patterns for various clerk systems

    # Bolt ⚡ Optimization: Pre-lowercased indicators are defined at module level
    # Use page_content (cleaned) instead of raw_html to avoid hidden elements
    # Also require actual <input elements to be present - not just search keywords

    page_content_lower = page_content.lower()
    has_input_elements = '<input' in page_content_lower
    has_search_indicators = any(indicator in page_content_lower for indicator in _SEARCH_INDICATORS_LOWER)
    has_search_inputs = has_input_elements and has_search_indicators
    
    log.info(f"Got snapshot ({len(raw_html)} chars, cleaned to {len(page_content)}). Has inputs: {has_input_elements}, Has indicators: {has_search_indicators}")

    
    structured_llm = llm.with_structured_output(NavigationDecision)
    # Get memory context from state for smarter analysis
    click_attempts = state.get("disclaimer_click_attempts", 0)
    clicked_selectors = state.get("clicked_selectors", [])
    
    memory_context = ""
    if click_attempts > 0:
        memory_context = f"""
## IMPORTANT: PREVIOUS ATTEMPTS CONTEXT
You have already tried clicking these selectors {click_attempts} times: {clicked_selectors}
The page STILL shows a disclaimer modal, which means:
1. The modal might be a PERSISTENT overlay that doesn't block the search form
2. Click the search link/icon DIRECTLY - it might dismiss the modal automatically
3. Look for clickable search icons or links IN THE PAGE (not in the modal)

DO NOT keep suggesting the same accept button. Look for ALTERNATIVE ways to access search.
"""

    prompt = f"""Analyze this web page to determine the next action needed.

## YOUR GOAL
Help navigate to a NAME SEARCH results grid on this county clerk / official records website.
The goal is to find and record the grid/column selectors once search results are displayed.

## CLASSIFICATION RULES (IN ORDER OF PRIORITY)

### 1. CAPTCHA DETECTED
If you see a CAPTCHA challenge (reCAPTCHA, image verification, "I'm not a robot"):
- Set requires_login=True (we use this flag to escalate)
- This cannot be automated

### 2. LOGIN REQUIRED  
If the page requires authentication/login to proceed:
- Set requires_login=True

### 3. RESULTS GRID
If you see a DATA TABLE with search results containing columns like:
- Grantor, Grantee, Book/Page, Recording Date, Instrument, Document Type
- Set is_results_grid=True and provide grid_selector

### 4. SEARCH PAGE (with VISIBLE INPUT FIELDS)
ONLY classify as search page if you find ACTUAL <input> elements:
- <input type="text"> or <input type="search"> for entering a name
- A submit/search button to execute the search
- These must be VISIBLE form fields, not just links or icons
- Set is_search_page=True and provide search_input_ref, search_button_ref

### 5. DISCLAIMER / NAVIGATION PORTAL
If the page shows:
- A modal/overlay with Accept/Yes/OK button
- A home portal with ICONS or LINKS to different search types (Name Search, Document Search, etc.)
- NO actual <input> text fields visible
- Set is_disclaimer=True and provide accept_button_ref (the button/link to click next)

{memory_context}
## PAGE HTML:
{page_content}

## IMPORTANT DISTINCTIONS:
- ICONS/LINKS to "Name Search" are NOT search pages - they are NAVIGATION elements
- A search page has <input> fields where you TYPE a query
- If you see a modal blocking the page, that's a DISCLAIMER even if there are icons behind it

## WHAT TO RETURN:
- For search form: is_search_page=True, search_input_ref, search_button_ref, start_date_input_ref, end_date_input_ref
- For disclaimer/portal: is_disclaimer=True, accept_button_ref (selector for Accept button OR next navigation link)
- For results: is_results_grid=True, grid_selector
- For login/captcha: requires_login=True

Provide CSS selectors (not XPath).
"""
    
    try:
        decision = await structured_llm.ainvoke(prompt)
        
        # Override if heuristic found search inputs but LLM missed it
        if has_search_inputs and not decision.is_search_page and not decision.is_results_grid:
            log.warning("Heuristic detected search form indicators, verifying selectors...")
            
            # Fill in selectors based on what we find in the HTML
            # Check for id attributes (not CSS selectors) in HTML
            html_lower = raw_html.lower()
            
            potential_input = ""
            potential_submit = ""
            potential_start = ""
            potential_end = ""

            if 'id="name-name"' in html_lower or 'id="name-Name"' in raw_html:
                potential_input = "#name-Name"
            elif 'id="searchonname"' in html_lower:
                potential_input = "#SearchOnName"
            elif 'name="searchterm"' in html_lower:
                potential_input = "[name='searchTerm']"
                
            if 'id="namesearchmodalsubmit"' in html_lower or 'id="nameSearchModalSubmit"' in raw_html:
                potential_submit = "#nameSearchModalSubmit"
            elif 'id="btnsearch"' in html_lower:
                potential_submit = "#btnSearch"
            elif 'type="submit"' in html_lower:
                potential_submit = "button[type='submit']"
                
            if 'id="begindate-name"' in html_lower or 'id="beginDate-Name"' in raw_html:
                potential_start = "#beginDate-Name"
            elif 'id="recorddatefrom"' in html_lower:
                potential_start = "#RecordDateFrom"
                
            if 'id="enddate-name"' in html_lower or 'id="endDate-Name"' in raw_html:
                potential_end = "#endDate-Name"
            elif 'id="recorddateto"' in html_lower:
                potential_end = "#RecordDateTo"

            # VERIFICATION: Only override if we actually found a valid input AND submit button
            # This prevents Home Pages (with icons/links that use these names but aren't inputs) 
            # from being misclassified as search forms.
            if potential_input and potential_submit:
                log.warning(f"Heuristic verified search form: {potential_input}, {potential_submit}")
                decision.is_search_page = True
                decision.is_disclaimer = False
                if not decision.search_input_ref: decision.search_input_ref = potential_input
                if not decision.search_button_ref: decision.search_button_ref = potential_submit
                if not decision.start_date_input_ref: decision.start_date_input_ref = potential_start
                if not decision.end_date_input_ref: decision.end_date_input_ref = potential_end
            else:
                log.info("Heuristic search indicators found but no valid input/submit pair detected. Keeping LLM decision.")

        log.info(f"Decision: Search={decision.is_search_page}, Grid={decision.is_results_grid}, Disclaimer={decision.is_disclaimer}")
        log.debug(f"Reasoning: {decision.reasoning}")
        
        if decision.requires_login:
            log.error("Login required - cannot proceed")
            return {
                "status": "LOGIN_REQUIRED",
                "logs": (state.get("logs") or []) + log.get_logs()
            }
        
        # Results grid detected - go to capture columns
        if decision.is_results_grid:
            log.success(f"Results grid found: {decision.grid_selector}")
            return {
                "status": "RESULTS_GRID_FOUND",
                "search_selectors": {
                    **state.get("search_selectors", {}),
                    "grid": decision.grid_selector or "#RsltsGrid table"
                },
                "logs": (state.get("logs") or []) + log.get_logs()
            }
        
        if decision.is_search_page:
            log.success(f"Search page found. Input: {decision.search_input_ref}, Dates: {decision.start_date_input_ref}/{decision.end_date_input_ref}")
            return {
                "status": "SEARCH_PAGE_FOUND",
                "search_selectors": {
                    "input": decision.search_input_ref,
                    "submit": decision.search_button_ref,
                    "start_date": decision.start_date_input_ref,
                    "end_date": decision.end_date_input_ref
                },
                "logs": (state.get("logs") or []) + log.get_logs()
            }
        
        # Disclaimer or unknown - need to click something
        log.info(f"Disclaimer page detected: {decision.is_disclaimer}")
        return {
            "status": "NAVIGATING",
            "search_selectors": {
                "accept_button": decision.accept_button_ref
            },
            "logs": (state.get("logs") or []) + log.get_logs()
        }
        
    except Exception as e:
        log.error(f"Analysis error: {e}")
        return {
            "status": "NAVIGATING",
            "logs": (state.get("logs") or []) + log.get_logs()
        }
