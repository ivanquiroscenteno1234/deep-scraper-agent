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

# For filter_hidden_columns_from_html
_TH_PATTERN = re.compile(r'<th([^>]*)>(.*?)</th>', re.IGNORECASE | re.DOTALL)
_HIDDEN_PATTERNS = [
    re.compile(r'class\s*=\s*["\'][^"\']*\b(hidden|hide)\b[^"\']*["\']', re.IGNORECASE),
    re.compile(r'style\s*=\s*["\'][^"\']*display\s*:\s*none[^"\']*["\']', re.IGNORECASE),
    re.compile(r'style\s*=\s*["\'][^"\']*visibility\s*:\s*hidden[^"\']*["\']', re.IGNORECASE),
]
_HIDDEN_CELL_PATTERN = re.compile(
    r'<(th|td)\s+[^>]*class\s*=\s*["\'][^"\']*\b(hidden|hide)\b[^"\']*["\'][^>]*>.*?</\1>',
    re.IGNORECASE | re.DOTALL
)
_HIDDEN_STYLE_PATTERN = re.compile(
    r'<(th|td)\s+[^>]*style\s*=\s*["\'][^"\']*display\s*:\s*none[^"\']*["\'][^>]*>.*?</\1>',
    re.IGNORECASE | re.DOTALL
)

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


def filter_hidden_columns_from_html(html: str) -> Tuple[str, List[int]]:
    """
    Filter out hidden table columns from HTML and return visible column indices.
    
    Detects columns hidden via:
    - CSS class="hidden", class="hide", or class containing "hidden"
    - Inline style display:none or visibility:hidden
    
    Returns:
        Tuple of (filtered_html, visible_column_indices)
    """
    # Find all table header cells and track which are visible
    visible_indices = []

    def is_hidden(attrs: str) -> bool:
        for pattern in _HIDDEN_PATTERNS:
            if pattern.search(attrs):
                return True
        return False
    
    # Process table headers to find visible column indices
    all_ths = _TH_PATTERN.findall(html)
    for i, (attrs, content) in enumerate(all_ths):
        if not is_hidden(attrs):
            visible_indices.append(i)
    
    # Also filter <td> elements with hidden class to clean up the sample data shown to LLM
    # This helps LLM understand which columns actually contain visible data
    filtered_html = html
    
    # Remove entire hidden <th> and <td> elements from sample HTML for cleaner LLM analysis
    # Match th/td with hidden class and remove them
    filtered_html = _HIDDEN_CELL_PATTERN.sub('', filtered_html)
    
    # Also remove cells with inline display:none
    filtered_html = _HIDDEN_STYLE_PATTERN.sub('', filtered_html)
    
    return filtered_html, visible_indices


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
    snapshot = await browser.get_snapshot()
    raw_content = snapshot.get("html", str(snapshot))
    
    # Filter hidden columns BEFORE sending to LLM
    filtered_html, visible_indices = filter_hidden_columns_from_html(raw_content)
    content = clean_html_for_llm(filtered_html, max_length=COLUMN_HTML_LIMIT)
    
    log.info(f"Got snapshot ({len(raw_content)} chars, filtered to {len(filtered_html)} chars)")
    if visible_indices:
        log.info(f"Detected {len(visible_indices)} visible column indices: {visible_indices[:20]}...")
    
    # Discover grid selectors from HTML
    discovered_selectors = []
    
    # ID-based patterns (using pre-compiled regex for performance)
    for pattern, selector in _GRID_ID_PATTERNS:
        if pattern.search(raw_content):
            if selector not in discovered_selectors:
                discovered_selectors.append(selector)
                log.debug(f"Found grid ID: {selector}")
    
    # Class-based patterns
    class_patterns = [
        ('t-grid', '.t-grid'),
        ('dataTable', 'table.dataTable'),
        ('ig_ElectricBlueControl', '.ig_ElectricBlueControl'),
        ('search-results__results-wrap', '.search-results__results-wrap'),
    ]
    
    for class_name, selector in class_patterns:
        if class_name in raw_content:
            if selector not in discovered_selectors:
                discovered_selectors.append(selector)
                log.debug(f"Found grid class: {selector}")
    
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
