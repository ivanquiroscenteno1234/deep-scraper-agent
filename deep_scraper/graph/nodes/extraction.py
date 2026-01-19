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
from deep_scraper.utils.constants import AUMENTUM_STACKED_COLUMNS


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
    
    # Pattern to find <th> tags with their attributes
    th_pattern = re.compile(r'<th([^>]*)>(.*?)</th>', re.IGNORECASE | re.DOTALL)
    
    # Patterns indicating a hidden column
    hidden_patterns = [
        r'class\s*=\s*["\'][^"\']*\b(hidden|hide)\b[^"\']*["\']',  # class="hidden", class="hide col"
        r'style\s*=\s*["\'][^"\']*display\s*:\s*none[^"\']*["\']',  # style="display:none"
        r'style\s*=\s*["\'][^"\']*visibility\s*:\s*hidden[^"\']*["\']',  # style="visibility:hidden"
    ]
    
    def is_hidden(attrs: str) -> bool:
        for pattern in hidden_patterns:
            if re.search(pattern, attrs, re.IGNORECASE):
                return True
        return False
    
    # Process table headers to find visible column indices
    all_ths = th_pattern.findall(html)
    for i, (attrs, content) in enumerate(all_ths):
        if not is_hidden(attrs):
            visible_indices.append(i)
    
    # Also filter <td> elements with hidden class to clean up the sample data shown to LLM
    # This helps LLM understand which columns actually contain visible data
    filtered_html = html
    
    # Remove entire hidden <th> and <td> elements from sample HTML for cleaner LLM analysis
    # Match th/td with hidden class and remove them
    hidden_cell_pattern = re.compile(
        r'<(th|td)\s+[^>]*class\s*=\s*["\'][^"\']*\b(hidden|hide)\b[^"\']*["\'][^>]*>.*?</\1>',
        re.IGNORECASE | re.DOTALL
    )
    filtered_html = hidden_cell_pattern.sub('', filtered_html)
    
    # Also remove cells with inline display:none
    hidden_style_pattern = re.compile(
        r'<(th|td)\s+[^>]*style\s*=\s*["\'][^"\']*display\s*:\s*none[^"\']*["\'][^>]*>.*?</\1>',
        re.IGNORECASE | re.DOTALL
    )
    filtered_html = hidden_style_pattern.sub('', filtered_html)
    
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
    
    # NEW: Get ONLY visible tables via JavaScript
    # This prevents analyzing hidden tables (like browser compatibility tables) that exist in HTML
    visible_tables = []
    try:
        visible_tables_data = await browser.evaluate("""
            (() => {
                const tables = document.querySelectorAll('table');
                const result = [];
                for (const table of tables) {
                    // offsetParent is null for hidden elements, check offsetHeight as backup
                    if (table.offsetParent !== null || table.offsetHeight > 0) {
                        const headers = Array.from(table.querySelectorAll('th'))
                            .map(th => th.textContent.trim())
                            .filter(h => h.length > 0 && h.length < 100);
                        const rowCount = table.querySelectorAll('tbody tr, tr').length;
                        // Only include tables that look like data grids (have headers or multiple rows)
                        if (headers.length > 2 || rowCount > 3) {
                            result.push({
                                id: table.id || null,
                                className: table.className || null,
                                headers: headers.slice(0, 20),
                                rowCount: rowCount,
                                html: table.outerHTML.substring(0, 15000)
                            });
                        }
                    }
                }
                return JSON.stringify(result);
            })()
        """)
        
        # Handle JSON string response from MCP evaluate
        if isinstance(visible_tables_data, str):
            try:
                # Strip potential quotes if the server double-stringifies
                cleaned_data = visible_tables_data.strip()
                if cleaned_data.startswith('"') and cleaned_data.endswith('"'):
                    import ast
                    try:
                        cleaned_data = ast.literal_eval(cleaned_data)
                    except:
                        pass
                visible_tables = json.loads(cleaned_data)
            except Exception as parse_err:
                log.warning(f"Failed to parse visible_tables JSON: {parse_err}")
                visible_tables = []
        else:
            visible_tables = visible_tables_data or []
            
    except Exception as e:
        log.warning(f"JavaScript table visibility check failed: {e}")
    
    # Detect Aumentum/Infragistics grids (Travis County, etc.) - these have stacked column labels
    is_aumentum = 'ig_ElectricBlue' in raw_content or any(
        isinstance(t, dict) and 'ig_ElectricBlue' in (t.get('className') or '')
        for t in visible_tables
    )
    if is_aumentum:
        log.info("Detected Aumentum/Infragistics grid - will handle stacked column labels")
    
    # Use visible table HTML if available, otherwise fall back to filtered full HTML
    if isinstance(visible_tables, list) and len(visible_tables) > 0:
        log.info(f"Found {len(visible_tables)} VISIBLE tables via JS")
        for i, t in enumerate(visible_tables[:3]):
            if isinstance(t, dict):
                log.debug(f"  Table {i}: id={t.get('id')}, rows={t.get('rowCount')}, headers={t.get('headers', [])[:5]}")
        
        # Combine visible table HTML for LLM analysis
        visible_table_html = "\n".join([t.get("html", "") for t in visible_tables if isinstance(t, dict)])
        filtered_html, visible_indices = filter_hidden_columns_from_html(visible_table_html)
        content = clean_html_for_llm(filtered_html, max_length=COLUMN_HTML_LIMIT)
    else:
        log.warning("No visible tables found via JS or parsing failed - falling back to full HTML filtering")
        # Fall back to original behavior
        filtered_html, visible_indices = filter_hidden_columns_from_html(raw_content)
        content = clean_html_for_llm(filtered_html, max_length=COLUMN_HTML_LIMIT)
    
    log.info(f"Got snapshot ({len(raw_content)} chars, filtered to {len(content)} chars)")
    
    # Discover grid selectors from HTML
    discovered_selectors = []
    
    # ID-based patterns - expanded for more site variations
    grid_id_patterns = [
        # AcclaimWeb / Telerik
        (r'id=["\']RsltsGrid["\']', '#RsltsGrid'),
        (r'id=["\']SearchGrid["\']', '#SearchGrid'),
        (r'id=["\']gridMain["\']', '#gridMain'),
        (r'id=["\']resultsTable["\']', '#resultsTable'),
        (r'id=["\']grdSearchResults["\']', '#grdSearchResults'),
        # ASP.NET ListView patterns (Harris County, etc.)
        (r'id=["\']itemPlaceholderContainer["\']', '#itemPlaceholderContainer'),
        (r'id=["\']itemPlaceHolderContainer["\']', '#itemPlaceHolderContainer'),
        # ASP.NET GridView patterns (partial match)
        (r'id=["\'][^"\']*gvSearch[^"\']*["\']', '[id*="gvSearch"]'),
        (r'id=["\'][^"\']*GridView[^"\']*["\']', '[id*="GridView"]'),
        (r'id=["\'][^"\']*grdResults[^"\']*["\']', '[id*="grdResults"]'),
    ]
    
    for pattern, selector in grid_id_patterns:
        match = re.search(pattern, raw_content, re.IGNORECASE)
        if match:
            # For partial matches, extract the actual ID and use it
            if '[id*=' in selector:
                id_match = re.search(r'id=["\']([^"\']+)["\']', match.group(0), re.IGNORECASE)
                if id_match:
                    actual_selector = f'#{id_match.group(1)}'
                    if actual_selector not in discovered_selectors:
                        discovered_selectors.append(actual_selector)
                        log.debug(f"Found grid ID (partial match): {actual_selector}")
            elif selector not in discovered_selectors:
                discovered_selectors.append(selector)
                log.debug(f"Found grid ID: {selector}")
    
    # Class-based patterns - expanded for Bootstrap tables
    class_patterns = [
        ('t-grid', '.t-grid'),
        ('dataTable', 'table.dataTable'),
        ('ig_ElectricBlueControl', '.ig_ElectricBlueControl'),
        ('search-results__results-wrap', '.search-results__results-wrap'),
        # Bootstrap table patterns
        ('table-condensed', 'table.table-condensed'),
        ('table-striped', 'table.table-striped'),
        ('table-hover', 'table.table-hover'),
    ]
    
    for class_name, selector in class_patterns:
        if class_name in raw_content:
            if selector not in discovered_selectors:
                discovered_selectors.append(selector)
                log.debug(f"Found grid class: {selector}")
    
    # JavaScript fallback: If no patterns found, try to find visible tables with data
    if not discovered_selectors:
        log.warning("No grid patterns matched - attempting JavaScript fallback discovery")
        try:
            # Find the first visible table with more than 5 rows (likely a data grid)
            js_result = await browser.evaluate("""
                (() => {
                    const tables = document.querySelectorAll('table');
                    for (const table of tables) {
                        const rows = table.querySelectorAll('tbody tr, tr');
                        if (rows.length > 5 && table.offsetParent !== null) {
                            if (table.id) return '#' + table.id;
                            if (table.className) return 'table.' + table.className.split(' ')[0];
                            return 'table';
                        }
                    }
                    return null;
                })()
            """)
            if js_result:
                discovered_selectors.append(js_result)
                log.success(f"JavaScript fallback found grid: {js_result}")
        except Exception as js_err:
            log.debug(f"JavaScript fallback failed: {js_err}")
    
    log.info(f"Discovered {len(discovered_selectors)} potential grid selectors")
    
    # Build discovered selectors context for LLM
    discovered_context = ""
    if discovered_selectors:
        discovered_context = f"""
## DISCOVERED GRID SELECTORS (USE THESE - CONFIRMED TO EXIST):
{', '.join(discovered_selectors)}

IMPORTANT: Prefer using one of the DISCOVERED selectors above. They were confirmed to exist in the DOM.
"""
    
    # Use LLM to identify columns - with VISIBILITY emphasis and selector validation
    prompt = f"""Analyze this HTML to identify the VISIBLE results grid columns.

## CRITICAL RULES FOR grid_selector:
1. The grid_selector MUST be an element that ACTUALLY EXISTS in the HTML below
2. Look for `id="..."` or `class="..."` attributes in <table> elements
3. DO NOT invent selectors that aren't in the HTML - this will cause the script to fail!
4. Common patterns to look for:
   - `id="itemPlaceholderContainer"` → use "#itemPlaceholderContainer"
   - `id="RsltsGrid"` → use "#RsltsGrid"  
   - `class="table-condensed ..."` → use "table.table-condensed"
   - `class="t-grid"` → use ".t-grid"
{discovered_context}
## COLUMN IDENTIFICATION RULES:
- SKIP columns with class="hidden", style="display:none"
- SKIP icon/action columns (columns with only images/buttons)
- SKIP row number columns (first column showing "#" or count)
- Focus on DATA columns: Name, Date, Type, Description, etc.

## HTML CONTENT:
{content}

## KNOWN COLUMN NAMES (match these if found):
{', '.join(KNOWN_GRID_COLUMNS)}

## WHAT TO IDENTIFY:
1. grid_selector: CSS selector for the TABLE element (MUST exist in HTML above)
2. row_selector: Selector for data rows RELATIVE to grid. IMPORTANT:
   - For AcclaimWeb/Telerik grids (class contains "t-grid"), use ".t-grid-content tbody tr"
   - For standard tables, use "tbody tr"
   - For ASP.NET, use "tr.GridRow, tr.GridAltRow"
3. columns: Array of VISIBLE column names from the table header
4. first_data_column_index: 0-based index of first DATA column (skip row#, icons)

## STACKED COLUMN LABELS (CRITICAL FOR INFRAGISTICS/AUMENTUM):
Some grids have TWO labels stacked vertically in ONE column cell. Examples:
- "Name / Associated Name" in one cell -> split into SEPARATE columns: "Name", "Associated Name"
- "Instrument # / Book-Page" in one cell -> split into: "Instrument #", "Book", "Page"
IMPORTANT: If you see stacked/combined labels, split them into their component column names!

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
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
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
                # POST-PROCESSING: Expand stacked column labels for Aumentum/Infragistics grids
                # If LLM returned combined labels like "Name / Associated Name", split them
                expanded_columns = []
                for col in columns:
                    # Check if this is a known stacked column pattern
                    if col in AUMENTUM_STACKED_COLUMNS:
                        expanded = AUMENTUM_STACKED_COLUMNS[col]
                        log.info(f"Expanding stacked column '{col}' -> {expanded}")
                        expanded_columns.extend(expanded)
                    else:
                        expanded_columns.append(col)
                
                # Use expanded columns if we actually expanded any
                if len(expanded_columns) > len(columns):
                    log.success(f"Expanded {len(columns)} columns to {len(expanded_columns)} columns")
                    columns = expanded_columns
                
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
            # Simple extraction of table content
            table_match = re.search(r'<table[^>]*>.*?</table>', filtered_html, re.DOTALL | re.IGNORECASE)
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
