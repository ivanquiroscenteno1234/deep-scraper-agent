"""
Extraction nodes - Data capture from grids.

Contains:
- node_capture_columns_mcp: Capture grid structure and columns
"""

import asyncio
import json
import re
from typing import Any, Dict, List, Tuple

from langchain_core.messages import SystemMessage, HumanMessage

from deep_scraper.core.state import AgentState
from deep_scraper.graph.nodes.config import (
    llm,
    get_mcp_browser,
    extract_llm_text,
    clean_html_for_llm,
    StructuredLogger,
    KNOWN_GRID_COLUMNS,
    COLUMN_HTML_LIMIT,
)

# --- Pre-compiled Regex Patterns for Performance ---
# By compiling regexes at the module level, we avoid re-compiling them on every function call.
# This provides a significant performance boost when these functions are called frequently.

# For node_capture_columns_mcp
_JSON_PATTERN = re.compile(r'\{.*\}', re.DOTALL)
_TABLE_PATTERN = re.compile(r'<table[^>]*>.*?</table>', re.DOTALL | re.IGNORECASE)

# ID-based patterns for grid selectors (pre-compiled)
_GRID_ID_PATTERNS = [
    (re.compile(r'id=["\']RsltsGrid["\']', re.IGNORECASE), '#RsltsGrid'),
    (re.compile(r'id=["\']SearchGrid["\']', re.IGNORECASE), '#SearchGrid'),
    (re.compile(r'id=["\']gridMain["\']', re.IGNORECASE), '#gridMain'),
    (re.compile(r'id=["\']resultsTable["\']', re.IGNORECASE), '#resultsTable'),
    (re.compile(r'id=["\']grdSearchResults["\']', re.IGNORECASE), '#grdSearchResults'),
]

# BOLT ⚡: Optimized class-based selector discovery.
# This single regex finds all common grid class names in one pass,
# which is much faster than iterating and running 'in' checks on the full HTML content.
_GRID_CLASS_MAP = {
    't-grid': '.t-grid',
    'datatable': 'table.dataTable',
    'ig_electricbluecontrol': '.ig_ElectricBlueControl',
    'search-results__results-wrap': '.search-results__results-wrap',
}
_GRID_CLASS_PATTERN = re.compile(
    r'class\s*=\s*["\'][^"\']*\b(' + '|'.join(_GRID_CLASS_MAP.keys()) + r')\b[^"\']*["\']',
    re.IGNORECASE
)


async def node_capture_columns_mcp(state: AgentState) -> Dict[str, Any]:
    """
    Capture grid columns using MCP snapshot and LLM.
    
    FILTERS OUT HIDDEN COLUMNS - only captures visible columns.
    Detects columns hidden via CSS class="hidden"/"hide" or inline style display:none.
    
    NO FALLBACK - raises error if LLM fails to identify columns.
    The test/fix loop will catch and handle any issues.
    
    Records: {"action": "capture_grid", "column_mapping": {...}, "visible_indices": [...]}
    """
    log = StructuredLogger("CaptureColumns")
    log.info("Capturing grid columns (with hidden column filtering)")
    
    browser = await get_mcp_browser()
    
    await asyncio.sleep(2)
    
    # Bolt ⚡ Optimization: Use browser-side filtering instead of fetching full HTML + Python regex
    # This reduces network payload and CPU usage significantly
    result = await browser.get_filtered_html_with_indices()
    filtered_html = result.get("html", "")
    visible_indices = result.get("visible_indices", [])

    content = clean_html_for_llm(filtered_html, max_length=COLUMN_HTML_LIMIT)
    
    log.info(f"Got filtered snapshot ({len(filtered_html)} chars)")
    if visible_indices:
        log.info(f"Detected {len(visible_indices)} visible column indices: {visible_indices[:20]}...")
    
    # Discover grid selectors from HTML
    discovered_selectors = []
    
    # ID-based patterns (using pre-compiled regex for performance)
    for pattern, selector in _GRID_ID_PATTERNS:
        if pattern.search(filtered_html):
            if selector not in discovered_selectors:
                discovered_selectors.append(selector)
                log.debug(f"Found grid ID: {selector}")
    
    # BOLT ⚡: Optimized class-based selector discovery using a single regex pass.
    for match in _GRID_CLASS_PATTERN.finditer(filtered_html):
        class_name = match.group(1).lower()
        selector = _GRID_CLASS_MAP.get(class_name)
        if selector and selector not in discovered_selectors:
            discovered_selectors.append(selector)
            log.debug(f"Found grid class via optimized regex: {selector}")
    
    log.info(f"Discovered {len(discovered_selectors)} potential grid selectors")
    
    # Use LLM to identify columns - with VISIBILITY emphasis
    prompt = f"""Analyze this HTML to identify the VISIBLE results grid columns.

IMPORTANT: Only identify columns that are VISIBLE to users.
- SKIP columns with class="hidden", class="hide", or style="display:none"
- SKIP icon/action columns (columns containing only icons like eye, plus, checkbox)
- SKIP row number columns (typically first column showing "#" or row count)
- Focus on DATA columns like: Name, Date, Status, Document Type, etc.

HTML CONTENT (hidden columns already filtered):
{content}

KNOWN COLUMN NAMES (match these if found):
{', '.join(KNOWN_GRID_COLUMNS)}

Identify:
1. Grid container selector (look for id like resultsTable, RsltsGrid, SearchGrid, or class like t-grid)
2. Row selector (e.g., "tbody tr")
3. VISIBLE column names found in the grid header (only columns user can see)
4. The starting index (0-based) of the first DATA column (skip row#, icon columns)

Return JSON ONLY:
{{"grid_selector": "...", "row_selector": "...", "columns": ["Column1", "Column2", ...], "first_data_column_index": 0}}
"""
    
    result = await llm.ainvoke([
        SystemMessage(content="Extract VISIBLE grid structure from HTML. Skip hidden columns and icon columns. Return valid JSON only."),
        HumanMessage(content=prompt)
    ])
    
    response = extract_llm_text(result.content)
    log.debug(f"LLM response: {response[:200]}...")
    
    # Parse column mapping - NO FALLBACK DEFAULTS
    column_mapping = {}
    grid_selector = discovered_selectors[0] if discovered_selectors else ""
    row_selector = "tbody tr"
    first_data_column_index = 0
    
    try:
        # Using pre-compiled regex for performance
        json_match = _JSON_PATTERN.search(response)
        if json_match:
            parsed = json.loads(json_match.group())
            llm_grid_selector = parsed.get("grid_selector", "")
            llm_row_selector = parsed.get("row_selector", "tbody tr")
            first_data_column_index = parsed.get("first_data_column_index", 0)
            
            if llm_grid_selector and llm_grid_selector not in discovered_selectors:
                discovered_selectors.insert(0, llm_grid_selector)
                grid_selector = llm_grid_selector
            
            if llm_row_selector:
                row_selector = llm_row_selector
            
            columns = parsed.get("columns", [])
            if columns:
                for i, col in enumerate(columns):
                    column_mapping[f"col_{i}"] = col
                log.success(f"Captured {len(columns)} VISIBLE columns (data starts at index {first_data_column_index})")
            else:
                raise ValueError("LLM returned empty columns list")
        else:
            raise ValueError("No JSON found in LLM response")
            
    except Exception as e:
        log.error(f"Column parse error: {e}")
        # Return FAILED status instead of raising error to allow graph to handle it
        return {
            "status": "FAILED",
            "logs": (state.get("logs") or []) + log.get_logs()
        }
    
    log.info(f"Grid selectors: {discovered_selectors}")
    
    # Track step - include visibility metadata
    recorded_steps = state.get("recorded_steps", [])
    recorded_steps.append({
        "action": "capture_grid",
        "grid_selector": grid_selector,
        "grid_selectors": discovered_selectors,
        "row_selector": row_selector,
        "column_mapping": column_mapping,
        "visible_column_indices": visible_indices,
        "first_data_column_index": first_data_column_index,
        "description": "Capture VISIBLE grid columns only"
    })
    
    # Extract grid HTML fragment (filtered version)
    grid_html = filtered_html[:20000]
    if grid_selector:
        try:
            # Simple extraction of table content (using pre-compiled regex for performance)
            table_match = _TABLE_PATTERN.search(filtered_html)
            if table_match:
                grid_html = table_match.group(0)[:30000]
        except Exception:
            pass
            
    return {
        "status": "COLUMNS_CAPTURED",
        "current_page_summary": raw_content[:5000],
        "recorded_steps": recorded_steps,
        "column_mapping": column_mapping,
        "grid_html": grid_html,
        "discovered_grid_selectors": discovered_selectors,
        "first_data_column_index": first_data_column_index,
        "search_selectors": {**state.get("search_selectors", {}), "grid": grid_selector},
        "logs": (state.get("logs") or []) + log.get_logs()
    }
