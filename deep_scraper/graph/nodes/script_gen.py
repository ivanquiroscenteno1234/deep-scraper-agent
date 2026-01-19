"""
Script generation node - LLM-based script creation.

Contains:
- node_generate_script_mcp: Generate Playwright scripts using LLM
"""

import json
import os
import datetime
from typing import Any, Dict

from langchain_core.messages import SystemMessage, HumanMessage

from deep_scraper.core.state import AgentState
from deep_scraper.graph.nodes.config import (
    llm_high_thinking,
    get_mcp_browser,
    extract_llm_text,
    extract_code_from_markdown,
    get_site_name_from_url,
    clean_html_for_llm,
    StructuredLogger,
    build_script_prompt,
)


async def node_generate_script_mcp(state: AgentState) -> Dict[str, Any]:
    """
    Generate script using LLM based on recorded steps, columns, and selectors.
    
    Uses build_script_prompt for clean prompt construction.
    Uses extract_code_from_markdown for cleaning LLM response.
    """
    log = StructuredLogger("GenerateScript")
    log.info("Generating script via LLM")
    
    # Extract state data
    target_url = state.get("target_url", "")
    recorded_steps = state.get("recorded_steps", [])
    column_mapping = state.get("column_mapping", {})
    grid_html = state.get("grid_html", "")
    columns_list = list(column_mapping.values()) if column_mapping else []
    discovered_selectors = state.get("discovered_grid_selectors", [])
    
    site_name = get_site_name_from_url(target_url)
    
    # Get grid selector from recorded steps
    grid_selector = ""
    row_selector = "tbody tr"
    first_data_column_index = 0
    for step in recorded_steps:
        if step.get("action") == "capture_grid":
            grid_selector = step.get("grid_selector", "")
            row_selector = step.get("row_selector", "tbody tr")
            first_data_column_index = step.get("first_data_column_index", 0)
            if step.get("grid_selectors"):
                discovered_selectors = step.get("grid_selectors")
            break
    
    # Also check state for first_data_column_index
    if first_data_column_index == 0:
        first_data_column_index = state.get("first_data_column_index", 0)
    
    if not grid_selector and discovered_selectors:
        grid_selector = discovered_selectors[0]
    
    # End MCP codegen session
    browser = await get_mcp_browser()
    try:
        await browser.end_codegen_session()
    except Exception:
        pass

    # Detect site type for specialized rules
    site_type = "UNKNOWN"
    if 'ig_ElectricBlue' in grid_html or 'Infragistics' in grid_html or 'Aumentum' in grid_html:
        site_type = "INFRAGISTICS"
    elif "AcclaimWeb" in target_url:
        site_type = "ACCLAIMWEB"
    elif "flaglerclerk" in target_url or "Landmark" in grid_html:
        site_type = "LANDMARK_WEB"
    
    log.info(f"Site: {site_name}, Type: {site_type}, Steps: {len(recorded_steps)}")
    
    # Build prompt using helper
    prompt = build_script_prompt(
        site_name=site_name,
        target_url=target_url,
        recorded_steps=recorded_steps,
        grid_selector=grid_selector,
        row_selector=row_selector,
        columns=columns_list,
        grid_html=clean_html_for_llm(grid_html, max_length=30000),
        first_data_column_index=first_data_column_index,
        site_type=site_type  # Pass site type to builder
    )
    
    log.info(f"Sending to LLM for script generation (first_data_column={first_data_column_index})")
    
    try:
        result = await llm_high_thinking.ainvoke([
            SystemMessage(content="You are an expert Python/Playwright developer. Generate clean, working code only. Use the EXACT selectors from recorded_steps."),
            HumanMessage(content=prompt)
        ])
        
        script_code = extract_code_from_markdown(extract_llm_text(result.content))
        log.success(f"Generated {len(script_code)} chars of code")
        
    except Exception as e:
        log.error(f"Script generation failed: {e}")
        return {
            "status": "SCRIPT_ERROR",
            "script_error": str(e),
            "logs": (state.get("logs") or []) + log.get_logs()
        }
    
    # Save the generated script
    output_dir = os.path.join(os.getcwd(), "output", "generated_scripts")
    data_dir = os.path.join(os.getcwd(), "output", "data")
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(data_dir, exist_ok=True)
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    script_path = os.path.join(output_dir, f"{site_name}_scraper_{timestamp}.py")
    
    with open(script_path, 'w', encoding='utf-8') as f:
        f.write(script_code)
    
    log.success(f"Script saved: {script_path}")
    
    return {
        "status": "SCRIPT_GENERATED",
        "generated_script_path": script_path,
        "generated_script_code": script_code,
        "recorded_steps": recorded_steps,
        "column_mapping": column_mapping,
        "site_type": site_type,
        "script_test_attempts": 0,
        "extracted_data": [],
        "logs": (state.get("logs") or []) + log.get_logs()
    }
