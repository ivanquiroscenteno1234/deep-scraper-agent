"""
search.py — Search form interaction node.

Extracted from the old monolithic interaction.py.
Handles:
- Filling search input (standard fill + Infragistics keyboard mode)
- Filling date range fields (datepicker JS, Infragistics keyboard, standard fill)
- Submitting the search form
- Post-search popup detection and handling
"""

import asyncio
import datetime
from typing import Any, Dict, List, Optional

from langchain_core.messages import SystemMessage, HumanMessage

from deep_scraper.core.state import AgentState
from deep_scraper.graph.nodes.config import (
    llm,
    get_mcp_browser,
    PopupAnalysis,
    PostPopupAnalysis,
    clean_html_for_llm,
    StructuredLogger,
    RESULTS_GRID_SELECTORS,
    POPUP_HTML_LIMIT,
    DEFAULT_HTML_LIMIT,
)


# ---------------------------------------------------------------------------
# Date-filling helper (eliminates the 4-way duplication)
# ---------------------------------------------------------------------------

async def _fill_date_field(
    browser,
    selector: str,
    value: str,
    *,
    is_infragistics: bool,
    is_datepicker: bool,
    log: StructuredLogger,
) -> bool:
    """
    Fill a single date input using the best strategy for the detected site type.

    Returns True on success.
    """
    # 1. jQuery UI datepicker — JS direct set
    if is_datepicker:
        try:
            await browser.evaluate(f"""
                (() => {{
                    const el = document.querySelector('{selector}');
                    if (el) {{
                        el.value = '';
                        el.value = '{value}';
                        el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    }}
                }})()
            """)
            log.success(f"Filled {selector} via JS (datepicker): {value}")
            return True
        except Exception as e:
            log.warning(f"JS datepicker fill failed for {selector}: {e}")

    # 2. Infragistics — keyboard typing
    if is_infragistics:
        try:
            await browser.click_element(selector, f"Focus {selector}")
            await asyncio.sleep(0.2)
            await browser.press_key("Control+a")
            await asyncio.sleep(0.1)
            for char in value:
                await browser.press_key(char)
                await asyncio.sleep(0.02)
            await browser.press_key("Tab")
            await asyncio.sleep(0.3)
            log.success(f"Filled {selector} via keyboard (Infragistics): {value}")
            return True
        except Exception as e:
            log.warning(f"Keyboard date fill failed for {selector}: {e}")

    # 3. Standard MCP fill
    try:
        await browser.fill_form(selector, value, f"Date field {selector}")
        log.success(f"Filled {selector} via standard fill: {value}")
        return True
    except Exception as e:
        log.warning(f"Standard fill failed for {selector}: {e}")

    # 4. JS fallback (last resort)
    try:
        await browser.evaluate(f"""
            (() => {{
                const el = document.querySelector('{selector}');
                if (el) {{
                    el.value = '{value}';
                    el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                }}
            }})()
        """)
        log.success(f"Filled {selector} via JS fallback: {value}")
        return True
    except Exception as e2:
        log.error(f"All fill strategies failed for {selector}: {e2}")
        return False


# ---------------------------------------------------------------------------
# Main node
# ---------------------------------------------------------------------------

async def node_perform_search_mcp(state: AgentState) -> Dict[str, Any]:
    """
    Perform search using MCP.

    Records steps:
    - {"action": "fill", "selector": input, "value": "{{SEARCH_TERM}}"}
    - {"action": "fill", "selector": start_date, "value": "{{START_DATE}}"}  (if applicable)
    - {"action": "fill", "selector": end_date,   "value": "{{END_DATE}}"}    (if applicable)
    - {"action": "click", "selector": submit}
    - {"action": "click", "selector": popup_btn} (if popup detected)
    """
    log = StructuredLogger("Search")
    log.info("Performing search")

    browser = await get_mcp_browser()
    selectors = state.get("search_selectors", {})

    input_ref = selectors.get("input")
    submit_ref = selectors.get("submit")
    search_query = state["search_query"]

    if not input_ref or not submit_ref:
        log.error(f"Missing search selectors: Input='{input_ref}', Submit='{submit_ref}'")
        return {"status": "FAILED", "logs": (state.get("logs") or []) + log.get_logs()}

    log.info(f"Input={input_ref}, Submit={submit_ref}")

    # Detect Infragistics / Aumentum sites
    snapshot = await browser.get_snapshot()
    page_html = snapshot.get("html", "")
    is_infragistics = (
        "ig_ElectricBlue" in page_html
        or "Infragistics" in page_html
        or "Aumentum" in page_html
    )

    # ------------------------------------------------------------------
    # Fill search input
    # ------------------------------------------------------------------
    try:
        if is_infragistics:
            log.info("Detected Infragistics — using keyboard typing for search input")
            await browser.click_element(input_ref, "Focus search input")
            await asyncio.sleep(0.3)
            await browser.press_key("Control+a")
            await asyncio.sleep(0.1)
            await browser.press_key("Delete")
            await asyncio.sleep(0.1)
            for char in search_query:
                await browser.press_key(char)
                await asyncio.sleep(0.02)
            await browser.press_key("Tab")
            await asyncio.sleep(0.3)
            log.success(f"Typed search input via keyboard: {search_query}")
        else:
            await browser.fill_form(input_ref, search_query, "Search input")
            log.success("Filled search input")
    except Exception as e:
        log.error(f"Failed to fill search input: {e}")
        return {"status": "FAILED", "logs": (state.get("logs") or []) + log.get_logs()}

    # ------------------------------------------------------------------
    # Fill date range (if available)
    # ------------------------------------------------------------------
    date_steps: List[Dict[str, Any]] = []
    start_date_ref: Optional[str] = selectors.get("start_date")
    end_date_ref: Optional[str] = selectors.get("end_date")

    # Fallback pattern detection
    if not start_date_ref or not end_date_ref:
        snap2 = await browser.get_snapshot()
        html2 = snap2.get("html", "")
        if "RecordDateFrom" in html2:
            start_date_ref, end_date_ref = "#RecordDateFrom", "#RecordDateTo"
        elif "beginDate-Name" in html2:
            start_date_ref, end_date_ref = "#beginDate-Name", "#endDate-Name"

    if start_date_ref and end_date_ref:
        log.info(f"Filling dates using {start_date_ref}/{end_date_ref}")
        start_val = state.get("start_date", "01/01/1980")
        end_val = state.get("end_date", datetime.datetime.now().strftime("%m/%d/%Y"))

        # Detect datepicker
        is_datepicker = False
        try:
            is_datepicker = str(await browser.evaluate(f"""
                (() => {{
                    const el = document.querySelector('{start_date_ref}');
                    return el && (el.classList.contains('hasDatepicker') || el.classList.contains('datepicker'));
                }})()
            """)).lower() == "true"
        except Exception:
            pass

        start_ok = await _fill_date_field(
            browser, start_date_ref, start_val,
            is_infragistics=is_infragistics, is_datepicker=is_datepicker, log=log,
        )
        end_ok = await _fill_date_field(
            browser, end_date_ref, end_val,
            is_infragistics=is_infragistics, is_datepicker=is_datepicker, log=log,
        )

        if start_ok and end_ok:
            use_js = is_infragistics or is_datepicker
            date_steps = [
                {
                    "action": "fill",
                    "selector": start_date_ref,
                    "value": "{{START_DATE}}",
                    "use_js": use_js,
                    "description": "Fill start date",
                    "wait_for_input": input_ref,
                },
                {
                    "action": "fill",
                    "selector": end_date_ref,
                    "value": "{{END_DATE}}",
                    "use_js": use_js,
                    "description": "Fill end date",
                },
            ]
        await asyncio.sleep(1)

    # ------------------------------------------------------------------
    # Click submit
    # ------------------------------------------------------------------
    try:
        await browser.click_element(submit_ref, "Search button")
        log.success("Clicked search button")
    except Exception as e:
        log.error(f"Failed to click search button: {e}")
        return {"status": "FAILED", "logs": (state.get("logs") or []) + log.get_logs()}

    await asyncio.sleep(3)

    # ------------------------------------------------------------------
    # Post-search popup analysis
    # ------------------------------------------------------------------
    log.info("Analysing page after search for popups")
    snap3 = await browser.get_snapshot()
    full_snap_html = snap3.get("html", str(snap3))
    snap_html = clean_html_for_llm(full_snap_html, max_length=POPUP_HTML_LIMIT)

    popup_prompt = f"""Analyse this page HTML after a search was submitted.

Determine if there is a popup, modal, or intermediate selection dialog that requires
clicking a button before the actual results appear.

Common patterns on clerk websites:
- Name selection popups (user must select which names to include then click "Done")
- Confirmation dialogs
- Intermediate grids where user must make a selection

Look for:
- Visible modal windows (.t-window, #NamesWin, etc.)
- Submit/Done buttons inside popups
- Selection checkboxes with confirmation buttons

IMPORTANT: For the action_button_selector, provide a SPECIFIC selector that matches only ONE button.
Do NOT use generic selectors like input[value='Done'] — they match multiple buttons!
Use specific selectors like #NamesWin input[type='submit'] or #frmSchTarget input[type='submit'].

HTML:
{snap_html}

Return the analysis as JSON."""

    try:
        popup_llm = llm.with_structured_output(PopupAnalysis)
        popup_analysis = await popup_llm.ainvoke([
            SystemMessage(
                content="You analyse web pages to detect popups and modals. Always provide SPECIFIC selectors that match exactly ONE element."
            ),
            HumanMessage(content=popup_prompt),
        ])
        log.info(f"Popup analysis: has_popup={popup_analysis.has_popup}")
        if popup_analysis.has_popup:
            log.debug(f"Popup: {popup_analysis.popup_selector}")
            log.debug(f"Button: {popup_analysis.action_button_selector}")
    except Exception as e:
        log.error(f"Popup analysis failed: {e}")
        popup_analysis = PopupAnalysis(
            has_popup=False, popup_selector="", action_button_selector="",
            description=f"Analysis failed: {e}",
        )

    # ------------------------------------------------------------------
    # Handle popup
    # ------------------------------------------------------------------
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
            log.warning("Will be caught by the test/fix loop")
    elif popup_analysis.has_popup:
        log.warning("Popup detected but no button selector provided")

    if popup_handled:
        log.info("Analysing page after popup action")
        snap4 = await browser.get_snapshot()
        post_popup_html = clean_html_for_llm(snap4.get("html", str(snap4)), max_length=DEFAULT_HTML_LIMIT)
        try:
            post_popup_llm = llm.with_structured_output(PostPopupAnalysis)
            post_analysis = await post_popup_llm.ainvoke([
                SystemMessage(content="Analyse if the results grid is now visible after clicking the popup button."),
                HumanMessage(content=f"HTML after popup action:\n{post_popup_html}"),
            ])
            log.info(f"Post-popup: grid_visible={post_analysis.has_results_grid}")
            if post_analysis.needs_more_action:
                log.warning(f"Additional action needed: {post_analysis.next_action}")
        except Exception as e:
            log.warning(f"Post-popup analysis failed: {e}")

    # ------------------------------------------------------------------
    # Verify grid appeared
    # ------------------------------------------------------------------
    log.info("Verifying search success (waiting for results grid)...")
    grid_found = await browser.wait_for_grid(RESULTS_GRID_SELECTORS, timeout=10000)

    if grid_found:
        log.success("Results grid detected — search successful!")
        await asyncio.sleep(2)
    else:
        log.error("Results grid NOT detected after search attempt.")
        return {"status": "FAILED", "logs": (state.get("logs") or []) + log.get_logs()}

    summary = await browser.get_clean_content()

    # ------------------------------------------------------------------
    # Build recorded steps
    # ------------------------------------------------------------------
    recorded_steps = state.get("recorded_steps", [])

    if date_steps:
        recorded_steps.extend(date_steps)

    recorded_steps.extend([
        {
            "action": "fill",
            "selector": input_ref,
            "value": "{{SEARCH_TERM}}",
            "use_js": is_infragistics,
            "description": "Fill search input",
        },
        {
            "action": "click",
            "selector": submit_ref,
            "purpose": "submit_search",
            "description": "Click search button",
        },
    ])

    if popup_handled:
        recorded_steps.append({
            "action": "click",
            "selector": done_btn,
            "purpose": "handle_name_selection_popup",
            "description": "Click Done button on name selection popup",
            "wait_for": "#RsltsGrid",
        })

    return {
        "status": "SEARCH_EXECUTED",
        "current_page_summary": summary,
        "recorded_steps": recorded_steps,
        "search_selectors": {
            **selectors,
            "grid": RESULTS_GRID_SELECTORS[0] if RESULTS_GRID_SELECTORS else "#RsltsGrid",
        },
        "logs": (state.get("logs") or []) + log.get_logs(),
    }
