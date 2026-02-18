"""
disclaimer.py — Disclaimer / accept-button handling node.

Extracted from the old monolithic interaction.py.
Handles:
- Clicking accept/continue buttons
- Detecting hidden disclaimers that appear after navigation
- Alternative navigation fallbacks (portal icons, Name Search links)
- JS-based modal-trigger fallbacks
"""

import asyncio
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from langchain_core.messages import SystemMessage, HumanMessage

from deep_scraper.core.state import AgentState
from deep_scraper.graph.nodes.config import (
    llm,
    get_mcp_browser,
    PostClickAnalysis,
    clean_html_for_llm,
    StructuredLogger,
)


# ---------------------------------------------------------------------------
# PageState: replaces the per-function FakePostAnalysis* duck-type classes
# ---------------------------------------------------------------------------

@dataclass
class PageState:
    """Represents the analysed state of the page after a browser interaction."""
    page_changed: bool = False
    is_search_page: bool = False
    still_on_disclaimer: bool = False
    description: str = ""


# ---------------------------------------------------------------------------
# Landmark Web selector patterns (single source of truth — fixes #6 in plan)
# ---------------------------------------------------------------------------

LANDMARK_PATTERNS = {
    "input":      [('id="name-name"', "#name-Name"), ('id="namesearchname"', "#NameSearchName")],
    "submit":     [('id="namesearchmodalsubmit"', "#nameSearchModalSubmit"), ('id="btnnamesearch"', "#btnNameSearch")],
    "start_date": [('id="begindate-name"', "#beginDate-Name"), ('id="fromdate"', "#fromDate")],
    "end_date":   [('id="enddate-name"', "#endDate-Name"), ('id="todate"', "#toDate")],
}


def _detect_landmark_selectors(html: str) -> Optional[Dict[str, str]]:
    """
    Detect Landmark Web search-modal selectors from raw HTML.

    Returns a selector dict if the modal's input + submit are found, else None.
    """
    html_lower = html.lower()
    found: Dict[str, Optional[str]] = {"input": None, "submit": None, "start_date": None, "end_date": None}

    for field, patterns in LANDMARK_PATTERNS.items():
        for pattern, selector in patterns:
            if pattern in html_lower:
                found[field] = selector
                break

    if found["input"] and found["submit"]:
        return {
            "input": found["input"],
            "submit": found["submit"],
            "start_date": found["start_date"] or "",
            "end_date": found["end_date"] or "",
        }
    return None


# ---------------------------------------------------------------------------
# Main node
# ---------------------------------------------------------------------------

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

    click_attempts = state.get("disclaimer_click_attempts", 0)
    clicked_selectors: List[str] = state.get("clicked_selectors", [])

    log.info(f"Click attempt #{click_attempts + 1}, previously tried: {clicked_selectors}")

    clicked = False
    clicked_selector: Optional[str] = None
    alternative_strategy = False

    if accept_button and clicked_selectors.count(accept_button) >= 2:
        log.warning(f"Already tried '{accept_button}' {clicked_selectors.count(accept_button)} times — trying alternative")
        alternative_strategy = True

    # ------------------------------------------------------------------
    # Alternative navigation (after 3 attempts or repeated selector)
    # ------------------------------------------------------------------
    if click_attempts >= 3 or alternative_strategy:
        log.warning(f"Trying alternative navigation (click_attempts={click_attempts})")

        snapshot = await browser.get_snapshot()
        html = snapshot.get("html", str(snapshot))
        html_lower = html.lower()

        alternative_selectors: List[str] = []

        if 'id="namessearch"' in html_lower or 'id="namesearch"' in html_lower:
            alternative_selectors += ["#NamesSearch", "#nameSearch"]
        if 'class="portal-icon"' in html_lower or 'class="search-icon"' in html_lower:
            alternative_selectors += [".portal-icon:has-text('Name')", ".search-icon:has-text('Name')"]
        if "namesearchmodal" in html_lower or "openmodal" in html_lower:
            alternative_selectors += [
                "[onclick*='NameSearch']", "[onclick*='nameSearch']",
                "[data-target='#nameSearchModal']", "[data-toggle='modal'][href*='name']",
            ]
        if "name search" in html_lower:
            alternative_selectors += [
                "a:has-text('Name Search')", "div:has-text('name search') >> visible=true",
                "[href*='name']", "a[title='Name Search']", "img[alt*='Name Search']",
            ]
        if "official records" in html_lower:
            alternative_selectors.append("a:has-text('Official Records')")
        if "document search" in html_lower:
            alternative_selectors.append("a:has-text('Document Search')")
        if "search records" in html_lower:
            alternative_selectors.append("a:has-text('Search Records')")

        for alt_sel in alternative_selectors:
            if alt_sel not in clicked_selectors:
                try:
                    log.info(f"Trying alternative: {alt_sel}")
                    if await browser.click_element(alt_sel, "Alternative navigation link"):
                        clicked = True
                        clicked_selector = alt_sel
                        log.success(f"Alternative click worked: {alt_sel}")
                        await asyncio.sleep(2)
                        break
                except Exception as e:
                    log.debug(f"Alternative {alt_sel} failed: {e}")

        if not clicked:
            log.error("All alternative approaches exhausted — escalating")
            return {
                "status": "FAILED",
                "disclaimer_click_attempts": click_attempts + 1,
                "clicked_selectors": clicked_selectors,
                "logs": (state.get("logs") or []) + log.get_logs(),
            }
    else:
        # ------------------------------------------------------------------
        # Normal flow: try the LLM-provided selector
        # ------------------------------------------------------------------
        if accept_button:
            try:
                is_visible_raw = await browser.evaluate(
                    f"(() => {{ const el = document.querySelector('{accept_button}');"
                    f" return el && el.offsetParent !== null"
                    f" && getComputedStyle(el).display !== 'none'"
                    f" && getComputedStyle(el).visibility !== 'hidden'; }})()"
                )
                is_visible = str(is_visible_raw).lower() == "true"

                if is_visible:
                    if await browser.click_element(accept_button, "Accept button"):
                        clicked = True
                        clicked_selector = accept_button
                        log.success(f"Clicked: {accept_button}")
                else:
                    log.warning(f"Accept button {accept_button} is HIDDEN — will try navigation first")
                    alternative_strategy = True
            except Exception as e:
                log.error(f"LLM selector failed: {e}")
        else:
            log.warning("No accept button selector provided by LLM")

        # Navigation to trigger hidden disclaimer
        if alternative_strategy and not clicked:
            log.info("Attempting navigation to trigger hidden disclaimer...")
            snapshot = await browser.get_snapshot()
            html = snapshot.get("html", str(snapshot))
            html_lower = html.lower()

            nav_selectors: List[str] = []
            if "name search" in html_lower:
                nav_selectors += ["a[title='Name Search']", "a:has-text('Name Search')", "#NamesSearch"]

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

    if clicked_selector:
        clicked_selectors.append(clicked_selector)

    # ------------------------------------------------------------------
    # Post-click analysis
    # ------------------------------------------------------------------
    post_analysis: PageState = PageState()
    detected_search_selectors: Optional[Dict[str, str]] = None

    if clicked:
        log.info("Analysing page after accept click")
        try:
            post_snap = await browser.get_snapshot()
            full_html = post_snap.get("html", str(post_snap))
            post_html = clean_html_for_llm(full_html, max_length=15000)

            # 1. Heuristic: Landmark Web search modal
            detected = _detect_landmark_selectors(full_html)
            if detected:
                log.success(f"Detected Landmark Web search modal: {detected}")
                detected_search_selectors = detected
                post_analysis = PageState(
                    page_changed=True, is_search_page=True,
                    description="Landmark Web search modal detected",
                )
            else:
                # 2. LLM fallback
                post_click_llm = llm.with_structured_output(PostClickAnalysis)
                llm_result = await post_click_llm.ainvoke([
                    SystemMessage(content="Analyse the page state after an accept button was clicked."),
                    HumanMessage(content=f"HTML after clicking accept:\n{post_html}"),
                ])
                post_analysis = PageState(
                    page_changed=llm_result.page_changed,
                    is_search_page=llm_result.is_search_page,
                    still_on_disclaimer=llm_result.still_on_disclaimer,
                    description=llm_result.description,
                )

            log.info(f"Post-click: changed={post_analysis.page_changed}, search_page={post_analysis.is_search_page}")

            # 3. Newly-visible disclaimer after navigation click
            if post_analysis.still_on_disclaimer and post_analysis.page_changed:
                log.warning("Disclaimer became VISIBLE after navigation — accepting it now")
                accept_selectors = [
                    "#idAcceptYes", "#btnAccept", "#acceptButton",
                    "button:has-text('Accept')", "button:has-text('I Accept')",
                    "button:has-text('Yes')", "a:has-text('Accept')",
                ]
                for acc_sel in accept_selectors:
                    try:
                        vis = str(await browser.evaluate(
                            f"(() => {{ const el = document.querySelector('{acc_sel}'); return el && el.offsetParent !== null; }})()"
                        )).lower() == "true"
                        if vis:
                            log.info(f"Found visible accept button: {acc_sel}")
                            if await browser.click_element(acc_sel, "Accept button (now visible)"):
                                log.success(f"Clicked newly visible accept: {acc_sel}")
                                await asyncio.sleep(2)
                                post_snap2 = await browser.get_snapshot()
                                html2 = post_snap2.get("html", str(post_snap2))
                                detected2 = _detect_landmark_selectors(html2)
                                if detected2:
                                    detected_search_selectors = detected2
                                    post_analysis = PageState(
                                        page_changed=True, is_search_page=True,
                                        description="Search form visible after accepting disclaimer",
                                    )
                                break
                    except Exception as e:
                        log.debug(f"Accept selector {acc_sel} check failed: {e}")

            # 4. Still on disclaimer/portal — JS fallback to open modal
            if not post_analysis.is_search_page and (post_analysis.still_on_disclaimer or not post_analysis.page_changed):
                log.warning("Still on disclaimer/portal — attempting JS fallback approaches...")
                js_approaches = []
                if accept_button:
                    js_approaches.append(f"document.querySelector('{accept_button}')?.click()")
                js_approaches += [
                    "document.querySelector('a[title=\"Name Search\"]')?.click()",
                    "document.querySelector('[onclick*=\"NameSearch\"]')?.click()",
                    "document.querySelector('#NamesSearch')?.click()",
                    "$('#nameSearchModal')?.modal?.('show')",
                    "document.querySelector('#nameSearchModal')?.classList?.add('show')",
                    "Array.from(document.querySelectorAll('a, button, div')).find(el => el.textContent?.includes('Name Search') && el.offsetParent !== null)?.click()",
                ]
                for js_script in js_approaches:
                    try:
                        await browser.evaluate(js_script)
                        await asyncio.sleep(2.0)
                        post_snap3 = await browser.get_snapshot()
                        html3 = post_snap3.get("html", str(post_snap3))
                        detected3 = _detect_landmark_selectors(html3)
                        if detected3:
                            log.success(f"JS approach worked: {js_script[:50]}...")
                            detected_search_selectors = detected3
                            post_analysis = PageState(
                                page_changed=True, is_search_page=True,
                                description="Landmark Web search modal detected via JS",
                            )
                            break
                    except Exception as js_e:
                        log.debug(f"JS approach failed: {js_e}")

                log.info(f"Post-JS-fallback: search_page={post_analysis.is_search_page}")
        except Exception as e:
            log.warning(f"Post-click analysis failed: {e}")

    # ------------------------------------------------------------------
    # Build return value
    # ------------------------------------------------------------------
    recorded_steps = state.get("recorded_steps", [])
    if clicked_selector:
        recorded_steps.append({
            "action": "click",
            "selector": clicked_selector,
            "purpose": "accept_disclaimer",
            "description": "Click accept/continue button",
        })

    status = "CLICK_EXECUTED"
    result_selectors = state.get("search_selectors", {})

    if clicked and post_analysis.is_search_page:
        log.success("Search page detected after click!")
        status = "SEARCH_PAGE_FOUND"
        if detected_search_selectors:
            result_selectors = detected_search_selectors

    return {
        "status": status,
        "recorded_steps": recorded_steps,
        "disclaimer_click_attempts": click_attempts + 1,
        "clicked_selectors": clicked_selectors,
        "search_selectors": result_selectors,
        "logs": (state.get("logs") or []) + log.get_logs(),
    }
