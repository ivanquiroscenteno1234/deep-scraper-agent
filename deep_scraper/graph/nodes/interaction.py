"""
Interaction nodes - User interaction handling.

Contains:
- node_click_link_mcp: Click accept/disclaimer buttons
- node_perform_search_mcp: Fill and submit search forms, handle popups
"""

import asyncio
import datetime
from typing import Any, Dict

from langchain_core.messages import SystemMessage, HumanMessage

from deep_scraper.core.state import AgentState
from deep_scraper.graph.nodes.config import (
    llm,
    get_mcp_browser,
    PostClickAnalysis,
    PopupAnalysis,
    PostPopupAnalysis,
    clean_html_for_llm,
    StructuredLogger,
    RESULTS_GRID_SELECTORS,
    POPUP_HTML_LIMIT,
    DEFAULT_HTML_LIMIT,
)


async def node_click_link_mcp(state: AgentState) -> Dict[str, Any]:
    """
    Click the accept/continue button using MCP.
    
    Includes memory of past attempts to prevent infinite loops:
    - Tracks disclaimer_click_attempts
    - Remembers clicked_selectors to avoid repeating
    - After 3 attempts, tries alternative strategies (link-based navigation)
    
    Records step: {"action": "click", "selector": selector}
    """
    log = StructuredLogger("ClickLink")
    log.info("Handling disclaimer/accept click")
    
    browser = await get_mcp_browser()
    
    selectors = state.get("search_selectors", {})
    accept_button = selectors.get("accept_button", "")
    
    # Get memory from state
    click_attempts = state.get("disclaimer_click_attempts", 0)
    clicked_selectors = state.get("clicked_selectors", [])
    
    log.info(f"Click attempt #{click_attempts + 1}, previously tried: {clicked_selectors}")
    
    clicked = False
    clicked_selector = None
    alternative_strategy = False
    
    # Check if we've tried this selector too many times
    if accept_button and clicked_selectors.count(accept_button) >= 2:
        log.warning(f"Already tried '{accept_button}' {clicked_selectors.count(accept_button)} times - trying alternative approach")
        alternative_strategy = True
    
    # After 3 overall attempts, try alternative navigation strategies
    if click_attempts >= 3 or alternative_strategy:
        log.warning(f"Trying alternative navigation (click_attempts={click_attempts})")
        
        # Get page snapshot to find alternative links
        snapshot = await browser.get_snapshot()
        html = snapshot.get("html", str(snapshot))
        html_lower = html.lower()
        
        # Look for common navigation links on clerk homepages
        alternative_selectors = []
        
        # Landmark Web specific patterns (Flagler, etc.) - these are portal icons
        # Look for specific IDs first (most reliable)
        if 'id="namessearch"' in html_lower or 'id="namesearch"' in html_lower:
            alternative_selectors.append("#NamesSearch")
            alternative_selectors.append("#nameSearch")
        if 'class="portal-icon"' in html_lower or 'class="search-icon"' in html_lower:
            alternative_selectors.append(".portal-icon:has-text('Name')")
            alternative_selectors.append(".search-icon:has-text('Name')")
        # Look for onclick handlers that open name search modal
        if "namesearchmodal" in html_lower or "openmodal" in html_lower:
            alternative_selectors.append("[onclick*='NameSearch']")
            alternative_selectors.append("[onclick*='nameSearch']")
            alternative_selectors.append("[data-target='#nameSearchModal']")
            alternative_selectors.append("[data-toggle='modal'][href*='name']")
        
        # Common link patterns to look for
        if "name search" in html_lower:
            alternative_selectors.append("a:has-text('Name Search')")
            alternative_selectors.append("div:has-text('name search') >> visible=true")
            alternative_selectors.append("[href*='name']")
            # Also try clicking the icon container if it exists
            alternative_selectors.append("a[title='Name Search']")
            alternative_selectors.append("img[alt*='Name Search']")
        if "official records" in html_lower:
            alternative_selectors.append("a:has-text('Official Records')")
        if "document search" in html_lower:
            alternative_selectors.append("a:has-text('Document Search')")
        if "search records" in html_lower:
            alternative_selectors.append("a:has-text('Search Records')")
            
        # Try each alternative
        for alt_selector in alternative_selectors:
            if alt_selector not in clicked_selectors:
                try:
                    log.info(f"Trying alternative: {alt_selector}")
                    if await browser.click_element(alt_selector, "Alternative navigation link"):
                        clicked = True
                        clicked_selector = alt_selector
                        log.success(f"Alternative click worked: {alt_selector}")
                        # Wait a bit longer for modal to appear
                        await asyncio.sleep(2)
                        break
                except Exception as e:
                    log.debug(f"Alternative {alt_selector} failed: {e}")
        
        if not clicked:
            log.error("All alternative approaches exhausted - escalating")
            return {
                "status": "FAILED",
                "disclaimer_click_attempts": click_attempts + 1,
                "clicked_selectors": clicked_selectors,
                "logs": (state.get("logs") or []) + log.get_logs()
            }
    else:
        # Normal flow: try the LLM-provided selector
        if accept_button:
            try:
                # IMPORTANT: First check if the accept button is actually VISIBLE
                # Some sites (like Flagler) have hidden disclaimers that only appear after navigation
                is_visible_raw = await browser.evaluate(
                    f"(() => {{ const el = document.querySelector('{accept_button}'); return el && el.offsetParent !== null && getComputedStyle(el).display !== 'none' && getComputedStyle(el).visibility !== 'hidden'; }})()"
                )
                is_visible = str(is_visible_raw).lower() == "true"
                
                if is_visible:
                    if await browser.click_element(accept_button, "Accept button"):
                        clicked = True
                        clicked_selector = accept_button
                        log.success(f"Clicked: {accept_button}")
                else:
                    log.warning(f"Accept button {accept_button} exists but is HIDDEN - need to navigate first")
                    # Don't count this as a failed attempt since the button is hidden
                    # Instead, we should try navigation to trigger the disclaimer
                    alternative_strategy = True
            except Exception as e:
                log.error(f"LLM selector failed: {e}")
        else:
            log.warning("No accept button selector provided by LLM")
        
        # If button was hidden, try navigation to trigger disclaimer popup
        if alternative_strategy and not clicked:
            log.info("Attempting navigation to trigger hidden disclaimer...")
            snapshot = await browser.get_snapshot()
            html = snapshot.get("html", str(snapshot))
            html_lower = html.lower()
            
            nav_selectors = []
            if "name search" in html_lower:
                nav_selectors.extend([
                    "a[title='Name Search']",
                    "a:has-text('Name Search')",
                    "#NamesSearch",
                ])
            
            for nav_sel in nav_selectors:
                if nav_sel not in clicked_selectors:
                    try:
                        if await browser.click_element(nav_sel, "Navigation to trigger disclaimer"):
                            clicked = True
                            clicked_selector = nav_sel
                            log.success(f"Clicked navigation: {nav_sel}")
                            break
                    except Exception as e:
                        log.debug(f"Nav selector {nav_sel} failed: {e}")
    
    await asyncio.sleep(3)
    
    # Update clicked history
    if clicked_selector:
        clicked_selectors.append(clicked_selector)
    
    # Analyze page after clicking to verify state change
    post_analysis = None
    detected_search_selectors = None  # Will be set if we detect a search modal
    
    if clicked:
        log.info("Analyzing page after accept click")
        try:
            post_click_snapshot = await browser.get_snapshot()
            full_html = post_click_snapshot.get("html", str(post_click_snapshot))
            post_click_html = clean_html_for_llm(full_html, max_length=15000)
            
            # HEURISTIC CHECK: Look for Landmark Web search modal selectors FIRST
            # These modals appear after clicking "Name Search" icon on portal pages
            html_lower = full_html.lower()
            
            # Landmark Web patterns (Flagler, etc.)
            landmark_patterns = {
                "input": [('id="name-name"', "#name-Name"), ('id="namesearchname"', "#NameSearchName")],
                "submit": [('id="namesearchmodalsubmit"', "#nameSearchModalSubmit"), ('id="btnnamesearch"', "#btnNameSearch")],
                "start_date": [('id="begindate-name"', "#beginDate-Name"), ('id="fromdate"', "#fromDate")],
                "end_date": [('id="enddate-name"', "#endDate-Name"), ('id="todate"', "#toDate")],
            }
            
            found_input = None
            found_submit = None
            found_start = None
            found_end = None
            
            for pattern, selector in landmark_patterns["input"]:
                if pattern in html_lower:
                    found_input = selector
                    break
            for pattern, selector in landmark_patterns["submit"]:
                if pattern in html_lower:
                    found_submit = selector
                    break
            for pattern, selector in landmark_patterns["start_date"]:
                if pattern in html_lower:
                    found_start = selector
                    break
            for pattern, selector in landmark_patterns["end_date"]:
                if pattern in html_lower:
                    found_end = selector
                    break
            
            # If we found Landmark Web search modal elements, we're on a search page!
            if found_input and found_submit:
                log.success(f"Detected Landmark Web search modal: input={found_input}, submit={found_submit}")
                detected_search_selectors = {
                    "input": found_input,
                    "submit": found_submit,
                    "start_date": found_start or "",
                    "end_date": found_end or "",
                }
                # Create a fake post_analysis that indicates search page
                class FakePostAnalysis:
                    page_changed = True
                    is_search_page = True
                    still_on_disclaimer = False
                    description = "Landmark Web search modal detected"
                post_analysis = FakePostAnalysis()
            else:
                # Fall back to LLM analysis
                post_click_llm = llm.with_structured_output(PostClickAnalysis)
                post_analysis = await post_click_llm.ainvoke([
                    SystemMessage(content="Analyze the page state after an accept button was clicked."),
                    HumanMessage(content=f"HTML after clicking accept:\n{post_click_html}")
                ])
            
            log.info(f"Post-click: changed={post_analysis.page_changed}, search_page={post_analysis.is_search_page}")
            
            # CRITICAL: Check if clicking a navigation link caused a VISIBLE disclaimer to appear
            # This happens on sites like Flagler where disclaimer is hidden until you try to navigate
            if post_analysis.still_on_disclaimer and post_analysis.page_changed:
                log.warning("Disclaimer became VISIBLE after navigation click - need to accept it now!")
                
                # Look for common accept button selectors
                accept_selectors = [
                    "#idAcceptYes",  # Landmark Web (Flagler)
                    "#btnAccept",
                    "#acceptButton", 
                    "button:has-text('Accept')",
                    "button:has-text('I Accept')",
                    "button:has-text('Yes')",
                    "a:has-text('Accept')",
                ]
                
                for accept_sel in accept_selectors:
                    try:
                        # Check if this element is actually visible/clickable now
                        is_visible_raw = await browser.evaluate(
                            f"(() => {{ const el = document.querySelector('{accept_sel}'); return el && el.offsetParent !== null; }})()"
                        )
                        is_visible = str(is_visible_raw).lower() == "true"
                        if is_visible:
                            log.info(f"Found visible accept button: {accept_sel}")
                            if await browser.click_element(accept_sel, "Accept button (now visible)"):
                                log.success(f"Clicked newly visible accept button: {accept_sel}")
                                await asyncio.sleep(2)
                                
                                # Re-analyze after clicking accept
                                post_click_snapshot = await browser.get_snapshot()
                                full_html_3 = post_click_snapshot.get("html", str(post_click_snapshot))
                                html_lower_3 = full_html_3.lower()
                                
                                # Check if we now have search form
                                for pattern, selector in landmark_patterns["input"]:
                                    if pattern in html_lower_3:
                                        found_input = selector
                                        break
                                for pattern, selector in landmark_patterns["submit"]:
                                    if pattern in html_lower_3:
                                        found_submit = selector
                                        break
                                for pattern, selector in landmark_patterns["start_date"]:
                                    if pattern in html_lower_3:
                                        found_start = selector
                                        break
                                for pattern, selector in landmark_patterns["end_date"]:
                                    if pattern in html_lower_3:
                                        found_end = selector
                                        break
                                
                                if found_input and found_submit:
                                    log.success(f"Search form now visible after accepting disclaimer!")
                                    detected_search_selectors = {
                                        "input": found_input,
                                        "submit": found_submit,
                                        "start_date": found_start or "",
                                        "end_date": found_end or "",
                                    }
                                    class FakePostAnalysis3:
                                        page_changed = True
                                        is_search_page = True
                                        still_on_disclaimer = False
                                        description = "Search form visible after accepting disclaimer"
                                    post_analysis = FakePostAnalysis3()
                                break
                    except Exception as e:
                        log.debug(f"Accept selector {accept_sel} check failed: {e}")
                        continue
            
            # If still on disclaimer/portal, try JS-based approaches to open search modal
            if not post_analysis.is_search_page and (post_analysis.still_on_disclaimer or not post_analysis.page_changed):
                log.warning("Still on disclaimer/portal - attempting JS fallback approaches...")
                
                # Try multiple JS approaches to open search modal
                js_approaches = []
                
                # If we have an accept button, try clicking it via JS
                if accept_button:
                    js_approaches.append(f"document.querySelector('{accept_button}')?.click()")
                
                # Landmark Web specific: Try to trigger name search modal directly
                js_approaches.extend([
                    # Try clicking name search links/icons
                    "document.querySelector('a[title=\"Name Search\"]')?.click()",
                    "document.querySelector('[onclick*=\"NameSearch\"]')?.click()",
                    "document.querySelector('#NamesSearch')?.click()",
                    # Try triggering Bootstrap modal directly if it exists
                    "$('#nameSearchModal')?.modal?.('show')",
                    "document.querySelector('#nameSearchModal')?.classList?.add('show')",
                    # Try finding and clicking any visible name search element
                    "Array.from(document.querySelectorAll('a, button, div')).find(el => el.textContent?.includes('Name Search') && el.offsetParent !== null)?.click()",
                ])
                
                for js_script in js_approaches:
                    try:
                        await browser.evaluate(js_script)
                        await asyncio.sleep(2.0)
                        
                        # Re-check for Landmark search modal
                        post_click_snapshot = await browser.get_snapshot()
                        full_html_2 = post_click_snapshot.get("html", str(post_click_snapshot))
                        html_lower_2 = full_html_2.lower()
                        
                        # Check if search modal appeared
                        if 'id="name-name"' in html_lower_2 or 'id="namesearchmodalsubmit"' in html_lower_2:
                            log.success(f"JS approach worked: {js_script[:50]}...")
                            # Re-detect selectors
                            for pattern, selector in landmark_patterns["input"]:
                                if pattern in html_lower_2:
                                    found_input = selector
                                    break
                            for pattern, selector in landmark_patterns["submit"]:
                                if pattern in html_lower_2:
                                    found_submit = selector
                                    break
                            for pattern, selector in landmark_patterns["start_date"]:
                                if pattern in html_lower_2:
                                    found_start = selector
                                    break
                            for pattern, selector in landmark_patterns["end_date"]:
                                if pattern in html_lower_2:
                                    found_end = selector
                                    break
                            
                            if found_input and found_submit:
                                detected_search_selectors = {
                                    "input": found_input,
                                    "submit": found_submit,
                                    "start_date": found_start or "",
                                    "end_date": found_end or "",
                                }
                                class FakePostAnalysis2:
                                    page_changed = True
                                    is_search_page = True
                                    still_on_disclaimer = False
                                    description = "Landmark Web search modal detected via JS"
                                post_analysis = FakePostAnalysis2()
                                break
                    except Exception as js_e:
                        log.debug(f"JS approach failed: {js_e}")
                        continue
                
                log.info(f"Post-JS-fallback: search_page={post_analysis.is_search_page}")
        except Exception as e:
            log.warning(f"Post-click analysis failed: {e}")
    
    # Track step
    recorded_steps = state.get("recorded_steps", [])
    if clicked_selector:
        recorded_steps.append({
            "action": "click",
            "selector": clicked_selector,
            "purpose": "accept_disclaimer",
            "description": "Click accept/continue button"
        })
    
    # Determine status based on analysis
    status = "CLICK_EXECUTED"
    result_selectors = state.get("search_selectors", {})
    
    if clicked and post_analysis:
        if post_analysis.is_search_page:
            log.success("Search page detected after click!")
            status = "SEARCH_PAGE_FOUND"
            # If we detected search selectors via heuristic, use them
            if detected_search_selectors:
                result_selectors = detected_search_selectors
            
    return {
        "status": status,
        "recorded_steps": recorded_steps,
        "disclaimer_click_attempts": click_attempts + 1,
        "clicked_selectors": clicked_selectors,
        "search_selectors": result_selectors,
        "logs": (state.get("logs") or []) + log.get_logs()
    }


async def node_perform_search_mcp(state: AgentState) -> Dict[str, Any]:
    """
    Perform search using MCP.
    
    NO FALLBACK LOGIC for popup handling - relies on LLM analysis only.
    
    Records steps:
    - {"action": "fill", "selector": input, "value": "{{SEARCH_TERM}}"}
    - {"action": "click", "selector": submit}
    - {"action": "click", "selector": popup_button} (if popup detected)
    """
    log = StructuredLogger("Search")
    log.info("Performing search")
    
    browser = await get_mcp_browser()
    selectors = state.get("search_selectors", {})
    
    input_ref = selectors.get("input")
    submit_ref = selectors.get("submit")
    search_query = state["search_query"]
    
    # VERIFICATION: Ensure we have valid selectors before proceeding
    if not input_ref or not submit_ref:
        log.error(f"Missing search selectors: Input='{input_ref}', Submit='{submit_ref}'")
        return {
            "status": "FAILED",
            "logs": (state.get("logs") or []) + log.get_logs()
        }

    log.info(f"Input={input_ref}, Submit={submit_ref}")
    
    # Check if this is an Infragistics/Aumentum site (Travis County, etc.)
    # These controls require actual keyboard events - JS fill doesn't trigger server validation
    snapshot = await browser.get_snapshot()
    page_html = snapshot.get("html", "")
    is_infragistics = 'ig_ElectricBlue' in page_html or 'Infragistics' in page_html or 'Aumentum' in page_html
    
    # Fill search input - use keyboard typing for Infragistics sites
    try:
        if is_infragistics:
            log.info("Detected Infragistics site - using keyboard typing for search input")
            # First click to focus the field
            await browser.click_element(input_ref, "Focus search input")
            await asyncio.sleep(0.3)
            # Select all and delete existing content
            await browser.press_key("Control+a")
            await asyncio.sleep(0.1)
            await browser.press_key("Delete")
            await asyncio.sleep(0.1)
            # Type the search query using native keyboard events ONLY
            # This is required for Infragistics controls that don't recognize JS .value changes
            for char in search_query:
                await browser.press_key(char)
                await asyncio.sleep(0.02)  # Small delay between keystrokes
            # Trigger blur to ensure the control registers the value
            await browser.press_key("Tab")
            await asyncio.sleep(0.3)
            log.success(f"Typed search input via keyboard: {search_query}")
        else:
            await browser.fill_form(input_ref, search_query, "Search input")
            log.success("Filled search input")
    except Exception as e:
        log.error(f"Failed to fill search input: {e}")
        return {
            "status": "FAILED",
            "logs": (state.get("logs") or []) + log.get_logs()
        }
    
    # NEW: Fill date range fields if available
    date_steps = []
    start_date_ref = selectors.get("start_date")
    end_date_ref = selectors.get("end_date")
    
    # Fallback to pattern detection
    if not start_date_ref or not end_date_ref:
        snap = await browser.get_snapshot()
        html = snap.get("html", "")
        if "RecordDateFrom" in html:
            start_date_ref = "#RecordDateFrom"
            end_date_ref = "#RecordDateTo"
        elif "beginDate-Name" in html:
            start_date_ref = "#beginDate-Name"
            end_date_ref = "#endDate-Name"
    
    if start_date_ref and end_date_ref:
        log.info(f"Filling dates using {start_date_ref}/{end_date_ref}")
        start_val = state.get("start_date", "01/01/1980")
        end_val = state.get("end_date", datetime.datetime.now().strftime("%m/%d/%Y"))
        
        # Check if date fields are jQuery UI datepicker widgets
        # MCP fill() times out on these due to datepicker event interception
        is_datepicker = False
        try:
            is_datepicker_raw = await browser.evaluate(f"""
                (() => {{
                    const el = document.querySelector('{start_date_ref}');
                    return el && (el.classList.contains('hasDatepicker') || el.classList.contains('datepicker'));
                }})()
            """)
            is_datepicker = str(is_datepicker_raw).lower() == "true"
        except Exception:
            pass
        
        date_filled = False
        if is_datepicker:
            log.info("Detected datepicker fields - using JavaScript fallback")
            try:
                # Use JavaScript to fill datepicker fields directly
                # This bypasses the datepicker widget that blocks standard fill
                await browser.evaluate(f"""
                    (() => {{
                        const startEl = document.querySelector('{start_date_ref}');
                        const endEl = document.querySelector('{end_date_ref}');
                        if (startEl && endEl) {{
                            // Clear existing values first
                            startEl.value = '';
                            endEl.value = '';
                            // Set new values
                            startEl.value = '{start_val}';
                            endEl.value = '{end_val}';
                            // Trigger change events so form validation picks up the values
                            startEl.dispatchEvent(new Event('change', {{ bubbles: true }}));
                            endEl.dispatchEvent(new Event('change', {{ bubbles: true }}));
                            startEl.dispatchEvent(new Event('input', {{ bubbles: true }}));
                            endEl.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        }}
                    }})()
                """)
                log.success(f"Filled date range via JS: {start_val} - {end_val}")
                date_filled = True
            except Exception as e:
                log.warning(f"JS datepicker fill failed: {e}")
        
        # Standard MCP fill for normal input fields (or as fallback)
        if not date_filled:
            # For Infragistics sites, use keyboard typing for dates too
            if is_infragistics:
                log.info("Using keyboard typing for Infragistics date fields")
                try:
                    # Fill start date via keyboard
                    await browser.click_element(start_date_ref, "Focus start date")
                    await asyncio.sleep(0.2)
                    await browser.press_key("Control+a")
                    await asyncio.sleep(0.1)
                    for char in start_val:
                        await browser.press_key(char)
                        await asyncio.sleep(0.02)
                    await browser.press_key("Tab")
                    await asyncio.sleep(0.3)
                    
                    # Fill end date via keyboard
                    await browser.click_element(end_date_ref, "Focus end date")
                    await asyncio.sleep(0.2)
                    await browser.press_key("Control+a")
                    await asyncio.sleep(0.1)
                    for char in end_val:
                        await browser.press_key(char)
                        await asyncio.sleep(0.02)
                    await browser.press_key("Tab")
                    await asyncio.sleep(0.3)
                    
                    log.success(f"Filled date range via keyboard: {start_val} - {end_val}")
                    date_filled = True
                    date_steps.append({
                        "action": "fill",
                        "selector": start_date_ref,
                        "value": "{{START_DATE}}",
                        "use_js": True,
                        "description": "Fill start date (Infragistics)"
                    })
                    date_steps.append({
                        "action": "fill",
                        "selector": end_date_ref,
                        "value": "{{END_DATE}}",
                        "use_js": True,
                        "description": "Fill end date (Infragistics)"
                    })
                except Exception as e:
                    log.warning(f"Keyboard date fill failed: {e}")
            
            # Standard MCP fill for non-Infragistics sites
            if not date_filled:
                try:
                    await browser.fill_form(start_date_ref, start_val, "Start Date")
                    await browser.fill_form(end_date_ref, end_val, "End Date")
                    log.success(f"Filled date range: {start_val} - {end_val}")
                    date_filled = True
                    date_steps.extend([
                        {"action": "fill", "selector": start_date_ref, "value": "{{START_DATE}}", "description": "Fill start date"},
                        {"action": "fill", "selector": end_date_ref, "value": "{{END_DATE}}", "description": "Fill end date"}
                    ])
                except Exception as e:
                    log.warning(f"Standard fill failed: {e}, trying JS fallback...")
                # Final JS fallback on any fill failure
                try:
                    await browser.evaluate(f"""
                        (() => {{
                            const startEl = document.querySelector('{start_date_ref}');
                            const endEl = document.querySelector('{end_date_ref}');
                            if (startEl && endEl) {{
                                startEl.value = '{start_val}';
                                endEl.value = '{end_val}';
                                startEl.dispatchEvent(new Event('change', {{ bubbles: true }}));
                                endEl.dispatchEvent(new Event('change', {{ bubbles: true }}));
                            }}
                        }})()
                    """)
                    log.success(f"Filled date range via JS fallback: {start_val} - {end_val}")
                    date_filled = True
                except Exception as e2:
                    log.error(f"All date fill attempts failed: {e2}")
        
        if date_filled:
            # NOTE: Do NOT use use_js flag - page.fill() works better with datepickers
            # than JavaScript el.value = '...' which doesn't trigger proper form validation
            date_steps.extend([
                {"action": "fill", "selector": start_date_ref, "value": "{{START_DATE}}", "description": "Fill start date", "wait_for_input": input_ref},
                {"action": "fill", "selector": end_date_ref, "value": "{{END_DATE}}", "description": "Fill end date"}
            ])
            
        await asyncio.sleep(1)

    # Click submit
    try:
        await browser.click_element(submit_ref, "Search button")
        log.success("Clicked search button")
    except Exception as e:
        log.error(f"Failed to click search button: {e}")
        return {
            "status": "FAILED",
            "logs": (state.get("logs") or []) + log.get_logs()
        }
    
    # Wait for response
    await asyncio.sleep(3)
    
    # Analyze the page after search to detect popups or results
    log.info("Analyzing page after search")
    snapshot = await browser.get_snapshot()
    full_snapshot_html = snapshot.get("html", str(snapshot))
    snapshot_html = clean_html_for_llm(full_snapshot_html, max_length=POPUP_HTML_LIMIT)
    
    popup_prompt = f"""Analyze this page HTML after a search was submitted.

Determine if there is a popup, modal, or intermediate selection dialog that requires clicking a button before the actual results appear.

Common patterns on clerk websites:
- Name selection popups (user must select which names to include then click "Done")
- Confirmation dialogs
- Intermediate grids where user must make a selection

Look for:
- Visible modal windows (.t-window, #NamesWin, etc.)
- Submit/Done buttons inside popups
- Selection checkboxes with confirmation buttons

IMPORTANT: For the action_button_selector, provide a SPECIFIC selector that matches only ONE button.
Do NOT use generic selectors like input[value='Done'] - they match multiple buttons!
Use specific selectors like #NamesWin input[type='submit'] or #frmSchTarget input[type='submit'].

HTML:
{snapshot_html}

Return the analysis as JSON."""

    try:
        popup_llm = llm.with_structured_output(PopupAnalysis)
        popup_analysis = await popup_llm.ainvoke([
            SystemMessage(content="You analyze web pages to detect popups and modals. Always provide SPECIFIC selectors that match exactly ONE element."),
            HumanMessage(content=popup_prompt)
        ])
        
        log.info(f"Popup analysis: has_popup={popup_analysis.has_popup}")
        if popup_analysis.has_popup:
            log.debug(f"Popup: {popup_analysis.popup_selector}")
            log.debug(f"Button: {popup_analysis.action_button_selector}")
    except Exception as e:
        log.error(f"Popup analysis failed: {e}")
        popup_analysis = PopupAnalysis(has_popup=False, popup_selector="", action_button_selector="", description=f"Analysis failed: {e}")
    
    # Handle popup if detected by LLM (NO FALLBACKS)
    popup_handled = False
    done_btn = ""
    
    if popup_analysis.has_popup and popup_analysis.action_button_selector:
        log.info(f"Clicking popup button: {popup_analysis.action_button_selector}")
        try:
            await browser.click_element(popup_analysis.action_button_selector, "Popup action button")
            popup_handled = True
            done_btn = popup_analysis.action_button_selector
            await asyncio.sleep(2)
            log.success("Popup handled")
        except Exception as e:
            log.error(f"Popup click failed: {e}")
            log.warning("This will be caught by the test/fix loop")
    elif popup_analysis.has_popup:
        log.warning("Popup detected but no button selector provided")
    
    # Analyze page after popup action (if any)
    if popup_handled:
        log.info("Analyzing page after popup action")
        post_popup_snapshot = await browser.get_snapshot()
        full_popup_html = post_popup_snapshot.get("html", str(post_popup_snapshot))
        post_popup_html = clean_html_for_llm(full_popup_html, max_length=DEFAULT_HTML_LIMIT)
        
        try:
            post_popup_llm = llm.with_structured_output(PostPopupAnalysis)
            post_analysis = await post_popup_llm.ainvoke([
                SystemMessage(content="Analyze if the results grid is now visible after clicking the popup button."),
                HumanMessage(content=f"HTML after popup action:\n{post_popup_html}")
            ])
            log.info(f"Post-popup: grid_visible={post_analysis.has_results_grid}")
            if post_analysis.needs_more_action:
                log.warning(f"Additional action needed: {post_analysis.next_action}")
        except Exception as e:
            log.warning(f"Post-popup analysis failed: {e}")
    
    # VERIFICATION: Wait for results grid to confirm search success
    log.info("Verifying search success (waiting for results grid)...")
    grid_found = await browser.wait_for_grid(RESULTS_GRID_SELECTORS, timeout=10000)
    
    if grid_found:
        log.success("Results grid detected - search successful!")
        await asyncio.sleep(2)
    else:
        log.error("Results grid NOT detected after search attempt.")
        # If we failed to find the grid, return FAILED to trigger re-analysis or escalation
        return {
            "status": "FAILED",
            "logs": (state.get("logs") or []) + log.get_logs()
        }
    
    summary = await browser.get_clean_content()
    
    # Track steps
    recorded_steps = state.get("recorded_steps", [])
    
    # Add date steps if they were filled
    if date_steps:
        recorded_steps.extend(date_steps)
        
    recorded_steps.extend([
        {
            "action": "fill",
            "selector": input_ref,
            "value": "{{SEARCH_TERM}}",
            "use_js": is_infragistics,  # Use JS/keyboard logic if Infragistics
            "description": "Fill search input"
        },
        {
            "action": "click",
            "selector": submit_ref,
            "purpose": "submit_search",
            "description": "Click search button"
        }
    ])
    
    # Track popup handling if it occurred
    if popup_handled:
        recorded_steps.append({
            "action": "click",
            "selector": done_btn,
            "purpose": "handle_name_selection_popup",
            "description": "Click Done button on name selection popup",
            "wait_for": "#RsltsGrid"
        })
    
    return {
        "status": "SEARCH_EXECUTED",
        "current_page_summary": summary,
        "recorded_steps": recorded_steps,
        "search_selectors": {**selectors, "grid": RESULTS_GRID_SELECTORS[0] if RESULTS_GRID_SELECTORS else "#RsltsGrid"},
        "logs": (state.get("logs") or []) + log.get_logs()
    }
