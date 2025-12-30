"""
MCP Nodes - Node implementations for browser control and step recording.

These nodes use the ExecuteAutomation Playwright MCP server for:
- Browser automation
- Native codegen (step recording)
- Script generation

See .agent/workflows/project-specification.md for workflow details.
"""

import asyncio
import os
import re
import json
from typing import Any, Dict, List
from urllib.parse import urlparse

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

from deep_scraper.core.state import AgentState
from deep_scraper.core.mcp_adapter import get_mcp_adapter, MCPBrowserAdapter


# LLM Setup
from dotenv import load_dotenv
load_dotenv(override=True)

gemini_model = os.getenv("GEMINI_MODEL")
google_api_key = os.getenv("GOOGLE_API_KEY")

if google_api_key:
    google_api_key = google_api_key.strip()
else:
    raise ValueError("GOOGLE_API_KEY environment variable is required")

print(f"🤖 LLM Init: Model={gemini_model}, Key={google_api_key[:8]}...{google_api_key[-4:] if google_api_key else ''}", flush=True)

llm = ChatGoogleGenerativeAI(model=gemini_model, temperature=0, google_api_key=google_api_key)


def extract_llm_text(content) -> str:
    """Safely extract text from LLM content, handling both string and list/multimodal formats."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(item.get("text", "") if isinstance(item, dict) else str(item) for item in content)
    return str(content)



class NavigationDecision(BaseModel):
    """Decision about what the current page represents."""
    is_search_page: bool = Field(description="True if this is a search form page")
    is_results_grid: bool = Field(description="True if this page has a data grid/table with search results")
    is_disclaimer: bool = Field(description="True if this is a disclaimer/acceptance page")
    requires_login: bool = Field(description="True if login is required")
    reasoning: str = Field(description="Brief explanation of the decision")
    accept_button_ref: str = Field(default="", description="CSS selector for accept button if disclaimer")
    search_input_ref: str = Field(default="", description="CSS selector for search input if search page")
    search_button_ref: str = Field(default="", description="CSS selector for search button if search page")
    grid_selector: str = Field(default="", description="CSS selector for data grid/table if results grid")


# Grid Column Field Names (for LLM to recognize)
# See .agent/workflows/project-specification.md for full list
KNOWN_GRID_COLUMNS = [
    # Party/Name Fields
    "Party Type", "Full Name", "Party Name", "Cross Party Name", "Search Name",
    "Direct Name", "Reverse Name", "Grantor", "Grantee", "Names",
    # Date Fields
    "Record Date", "Rec Date", "File Date", "Record Date Search",
    # Document Fields
    "Type", "Doc Type", "Document Type", "Clerk File Number", "File Number",
    "Instrument #", "Doc Number", "Description", "Legal", "Legal Description",
    # Book/Page Fields
    "Book/Page", "Type Vol Page", "Rec Book", "Film Code",
    # Other
    "Consideration", "Case #", "Comments"
]

# Common results grid selectors
RESULTS_GRID_SELECTORS = [
    "#RsltsGrid",
    ".t-grid-content table",
    "#SearchGridDiv table",
    ".searchGridDiv table",
    "#grdSearchResults",
]


# Global MCP adapter
mcp_browser: MCPBrowserAdapter = None


async def get_mcp_browser() -> MCPBrowserAdapter:
    """Get or initialize the MCP browser adapter."""
    global mcp_browser
    if mcp_browser is None:
        mcp_browser = get_mcp_adapter(use_codegen=True)
        if not await mcp_browser.launch():
            raise Exception("Failed to connect to MCP server")
    return mcp_browser


async def reset_mcp_browser():
    """Reset the global MCP browser adapter."""
    global mcp_browser
    if mcp_browser:
        await mcp_browser.close()
    mcp_browser = None


async def node_navigate_mcp(state: AgentState) -> Dict[str, Any]:
    """
    Navigate to target URL using MCP and start codegen session.
    
    Records step: {"action": "goto", "url": url}
    """
    print(f"--- Node: Navigate (MCP) ---", flush=True)
    
    browser = await get_mcp_browser()
    url = state["target_url"]
    
    # Start codegen session on first navigation
    if not browser._codegen_started:
        # Extract county name from URL for script naming
        parsed = urlparse(url)
        hostname = parsed.hostname or "unknown"
        county_match = re.search(r'(\w+)clerk', hostname, re.IGNORECASE)
        if county_match:
            county_name = county_match.group(1).lower()
        else:
            county_name = hostname.split('.')[0].replace('records', '').replace('-', '_') or "unknown"
        
        output_path = os.path.join(os.getcwd(), "output", "generated_scripts")
        os.makedirs(output_path, exist_ok=True)
        
        await browser.start_codegen_session(output_path, f"{county_name}_scraper")
    
    # Navigate
    print(f"Navigating to: {url}")
    summary = await browser.goto(url)
    
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
        "recorded_steps": recorded_steps
    }


async def node_analyze_mcp(state: AgentState) -> Dict[str, Any]:
    """
    Analyze the page using MCP snapshot and LLM classification.
    
    Determines if page is: SEARCH_PAGE, DISCLAIMER, or LOGIN_REQUIRED
    """
    print(f"--- Node: Analyze (MCP) ---", flush=True)
    
    browser = await get_mcp_browser()
    
    # Get page snapshot (HTML content)
    snapshot = await browser.get_snapshot()
    page_content = snapshot.get("html", str(snapshot))
    
    print(f"📸 Got snapshot ({len(page_content)} chars)")
    
    structured_llm = llm.with_structured_output(NavigationDecision)
    
    prompt = f"""Analyze this web page and classify it.

## PAGE HTML:
{page_content[:100000]}

## CLASSIFICATION RULES (check in order):

1. **RESULTS_GRID PAGE**: Page contains a data table/grid with search results
   - Look for: <table> with data rows, grid containers like #RsltsGrid, .searchGridDiv
   - Set is_results_grid=True
   - Provide grid_selector with CSS selector for the grid (e.g., "#RsltsGrid table", ".t-grid-content table")

2. **SEARCH PAGE**: Has text input for name/party search and a search button (but no results yet)
   - Set is_search_page=True
   - Provide search_input_ref and search_button_ref as CSS selectors

3. **DISCLAIMER PAGE**: Legal text with "accept", "agree", "continue" buttons
   - Set is_disclaimer=True
   - Provide accept_button_ref with CSS selector

4. **LOGIN REQUIRED**: Requires authentication
   - Set is_login_page=True

Provide CSS selectors for elements (not XPath).
"""
    
    try:
        decision = await structured_llm.ainvoke(prompt)
        print(f"Decision: Search={decision.is_search_page}, Grid={decision.is_results_grid}, Disclaimer={decision.is_disclaimer}")
        print(f"Reasoning: {decision.reasoning}")
        
        if decision.requires_login:
            return {
                "status": "LOGIN_REQUIRED",
                "logs": (state.get("logs") or []) + ["Login required - cannot proceed"]
            }
        
        # Results grid detected - go to capture columns
        if decision.is_results_grid:
            return {
                "status": "RESULTS_GRID_FOUND",
                "search_selectors": {
                    **state.get("search_selectors", {}),
                    "grid": decision.grid_selector or "#RsltsGrid table"
                },
                "logs": (state.get("logs") or []) + [f"Results grid found: {decision.grid_selector}"]
            }
        
        if decision.is_search_page:
            return {
                "status": "SEARCH_PAGE_FOUND",
                "search_selectors": {
                    "input": decision.search_input_ref,
                    "submit": decision.search_button_ref
                },
                "logs": (state.get("logs") or []) + [f"Search page found. Input: {decision.search_input_ref}"]
            }
        
        # Disclaimer or unknown - need to click something
        return {
            "status": "NAVIGATING",
            "search_selectors": {
                "accept_button": decision.accept_button_ref
            },
            "logs": (state.get("logs") or []) + [f"Page analyzed. Disclaimer: {decision.is_disclaimer}"]
        }
        
    except Exception as e:
        print(f"Analysis error: {e}")
        return {
            "status": "NAVIGATING",
            "logs": (state.get("logs") or []) + [f"Analysis error: {str(e)}"]
        }



async def node_click_link_mcp(state: AgentState) -> Dict[str, Any]:
    """
    Click the accept/continue button using MCP.
    
    Records step: {"action": "click", "selector": selector}
    """
    print(f"--- Node: Click Link (MCP) ---", flush=True)
    
    browser = await get_mcp_browser()
    
    selectors = state.get("search_selectors", {})
    accept_button = selectors.get("accept_button", "")
    
    clicked = False
    clicked_selector = None
    
    # Try the LLM-provided selector first
    if accept_button:
        try:
            if await browser.click_element(accept_button, "Accept button"):
                clicked = True
                clicked_selector = accept_button
                print(f"✅ Clicked: {accept_button}")
        except Exception as e:
            print(f"⚠️ LLM selector failed: {e}")
    
    # Fallback: try common accept button patterns
    if not clicked:
        common_buttons = [
            "#btnButton",
            "#agreeButton",
            "input[type='submit'][value*='Accept' i]",
            "button:has-text('Accept')",
            "button:has-text('I Accept')",
            "button:has-text('Continue')",
        ]
        
        for selector in common_buttons:
            try:
                if await browser.click_element(selector, f"Accept ({selector})"):
                    clicked = True
                    clicked_selector = selector
                    print(f"✅ Clicked: {selector}")
                    # Try Enter key as backup for stubborn forms/buttons
                    try:
                        await asyncio.sleep(0.5)
                        await browser.press_key("Enter")
                    except:
                        pass
                    break
            except:
                continue
    
    await asyncio.sleep(3)
    
    # Track step
    recorded_steps = state.get("recorded_steps", [])
    if clicked_selector:
        recorded_steps.append({
            "action": "click",
            "selector": clicked_selector,
            "purpose": "accept_disclaimer",
            "description": "Click accept/continue button"
        })
    
    return {
        "recorded_steps": recorded_steps,
        "logs": (state.get("logs") or []) + [f"Clicked: {clicked_selector or 'none'}"]
    }


async def node_perform_search_mcp(state: AgentState) -> Dict[str, Any]:
    """
    Perform search using MCP.
    
    Records steps:
    - {"action": "fill", "selector": input, "value": "{{SEARCH_TERM}}"}
    - {"action": "click", "selector": submit}
    """
    print(f"--- Node: Perform Search (MCP) ---", flush=True)
    
    browser = await get_mcp_browser()
    selectors = state.get("search_selectors", {})
    
    input_ref = selectors.get("input", "#SearchOnName")
    submit_ref = selectors.get("submit", "#btnSearch")
    search_query = state["search_query"]
    
    print(f"Search: Input={input_ref}, Submit={submit_ref}")
    
    # Fill search input
    await browser.fill_form(input_ref, search_query, "Search input")
    
    # Click submit
    await browser.click_element(submit_ref, "Search button")
    
    # Wait for response
    await asyncio.sleep(2)
    
    # Handle popups (common on clerk sites)
    popup_handled = False
    popup_selectors = ["#NamesWin", "#frmSchTarget", ".t-window"]
    for popup in popup_selectors:
        snapshot = await browser.get_snapshot()
        if popup.replace("#", "") in str(snapshot):
            print(f"Popup found: {popup}")
            done_btn = f"{popup} input[type='submit']"
            await browser.click_element(done_btn, "Popup Done button")
            popup_handled = True
            await asyncio.sleep(1)
            break
    
    # Wait for results grid
    print("⏳ Waiting for results grid...")
    grid_found = await browser.wait_for_grid(RESULTS_GRID_SELECTORS, timeout=10000)
    
    if grid_found:
        print("✅ Results grid loaded")
        await asyncio.sleep(2)  # Allow full render
    else:
        print("⚠️ Results grid not detected")
    
    summary = await browser.get_clean_content()
    
    # Track steps
    recorded_steps = state.get("recorded_steps", [])
    recorded_steps.extend([
        {
            "action": "fill",
            "selector": input_ref,
            "value": "{{SEARCH_TERM}}",  # Placeholder for variable
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
            "selector": "#frmSchTarget input[type='submit']",
            "purpose": "handle_popup",
            "description": "Click popup Done button"
        })
    
    return {
        "status": "SEARCH_EXECUTED",
        "current_page_summary": summary,
        "recorded_steps": recorded_steps,
        "search_selectors": {**selectors, "grid": RESULTS_GRID_SELECTORS[0]},
        "logs": (state.get("logs") or []) + [f"Executed search for '{search_query}'"]
    }


async def node_capture_columns_mcp(state: AgentState) -> Dict[str, Any]:
    """
    Capture grid columns using MCP snapshot and LLM.
    
    Identifies column names from KNOWN_GRID_COLUMNS list.
    Records: {"action": "capture_grid", "column_mapping": {...}}
    """
    print(f"--- Node: Capture Columns (MCP) ---", flush=True)
    
    browser = await get_mcp_browser()
    
    await asyncio.sleep(2)
    snapshot = await browser.get_snapshot()
    content = snapshot.get("html", str(snapshot))
    
    # Use LLM to identify columns
    prompt = f"""Analyze this HTML to identify the results grid columns.

HTML CONTENT:
{content[:50000]}

KNOWN COLUMN NAMES (match these if found):
{', '.join(KNOWN_GRID_COLUMNS)}

Identify:
1. Grid container selector (e.g., "#RsltsGrid", ".searchGridDiv table")
2. Row selector (e.g., "tbody tr")
3. Column names found in the grid

Return JSON:
{{"grid_selector": "...", "row_selector": "...", "columns": ["Column1", "Column2", ...]}}
"""
    
    result = await llm.ainvoke([
        SystemMessage(content="Extract grid structure from HTML. Return valid JSON only."),
        HumanMessage(content=prompt)
    ])
    
    response = extract_llm_text(result.content)
    print(f"Column analysis: {response[:300]}...", flush=True)
    
    # Parse column mapping
    column_mapping = {}
    grid_selector = "#RsltsGrid"
    
    try:
        # Extract JSON from response using regex (handles markdown and prefix text)
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group())
            grid_selector = parsed.get("grid_selector", grid_selector)
            columns = parsed.get("columns", [])
            if columns:
                for i, col in enumerate(columns):
                    column_mapping[f"col_{i}"] = col
            else:
                # Default columns if list is empty
                column_mapping = {"col_0": "Name", "col_1": "Date", "col_2": "Type"}
        else:
            raise ValueError("No JSON found in response")
            
    except Exception as e:
        print(f"⚠️ Column parse error: {e}")
        # Default columns if parsing fails
        column_mapping = {"col_0": "Name", "col_1": "Date", "col_2": "Type"}
    
    # Track step
    recorded_steps = state.get("recorded_steps", [])
    recorded_steps.append({
        "action": "capture_grid",
        "grid_selector": grid_selector,
        "row_selector": "tbody tr",
        "column_mapping": column_mapping,
        "description": "Capture grid structure"
    })
    
    # Extract grid HTML fragment for context
    grid_html = ""
    if grid_selector:
        try:
            # Try to grab a chunk of HTML around the grid
            grid_match = re.search(f'<{grid_selector.replace("#", "").replace(".", "")}.*?</table>', content, re.DOTALL | re.IGNORECASE)
            if grid_match:
                grid_html = grid_match.group(0)
            else:
                grid_html = content[:20000] # Fallback
        except:
            grid_html = content[:20000]
            
    return {
        "status": "COLUMNS_CAPTURED",
        "current_page_summary": content[:5000],
        "recorded_steps": recorded_steps,
        "column_mapping": column_mapping,
        "grid_html": grid_html,
        "search_selectors": {**state.get("search_selectors", {}), "grid": grid_selector},
        "logs": (state.get("logs") or []) + [f"Captured columns: {list(column_mapping.values())}"]
    }


async def node_generate_script_mcp(state: AgentState) -> Dict[str, Any]:
    """
    Generate script using LLM based on recorded steps, columns, and selectors.
    
    The LLM receives all navigation info and generates a complete Python script.
    """
    print("--- Node: Generate Script (LLM) ---")
    
    target_url = state.get("target_url", "")
    recorded_steps = state.get("recorded_steps", [])
    column_mapping = state.get("column_mapping", {})
    grid_html = state.get("grid_html", "")
    columns_list = list(column_mapping.values()) if column_mapping else []
    
    # Extract site name from URL domain
    from urllib.parse import urlparse
    parsed = urlparse(target_url)
    hostname = (parsed.hostname or "unknown").lower()
    
    # Improved logic: look for 'clerk' in any part, or take the main domain
    site_name = "unknown"
    parts = hostname.split('.')
    for part in parts:
        if 'clerk' in part:
            site_name = part
            break
    
    if site_name == "unknown":
        site_name = parts[1] if len(parts) > 2 and parts[0] == 'www' else parts[0]
    
    site_name = site_name.replace('-', '_').lower()
    
    # End MCP codegen session
    try:
        await browser.end_codegen_session()
    except:
        pass
    
    # Build LLM prompt with all collected information
    steps_json = json.dumps(recorded_steps, indent=2)
    
    prompt = f"""Generate a robust Python Playwright script for data extraction.

## TARGET
- Site: {site_name}
- URL: {target_url}

## NAVIGATION STEPS (USE THESE SELECTORS)
These are the EXACT steps and selectors that worked in the recording:
{steps_json}

## DATA EXTRACTION CONTEXT (GRID HTML)
Use this HTML fragment to map the data columns to table cells:
{grid_html[:30000]}

## COLUMNS TO EXTRACT
{json.dumps(columns_list)}

## CRITICAL REQUIREMENTS
1. **Dynamic Search**: Use `import sys` and `search_term = sys.argv[1]`.
2. **Recorded Logic**: Follow ALL `recorded_steps` exactly. If a disclaimer click or a popup "Done" button click was recorded, your script MUST include it.
3. **Conditional Start**: Browser sessions vary. Your script MUST be robust: if it starts on a Disclaimer but the search input is not yet visible, click the recorded Accept button. If it's already on the Search page, proceed directly.
4. **Selector Priority**: Use the selectors provided in the `recorded_steps` for all interactions.
4. **Network Waits**: Use `page.wait_for_load_state("networkidle")` or `page.wait_for_load_state("load")` after all clicks/navigation.
5. **Data Extraction**: Map the columns to table cells using the `grid_html` context.
6. **Output**: Save results to `{site_name}_results_[timestamp].csv` and `.json`.
7. **No False Success**: If no data is extracted or a timeout occurs, the script MUST print "FAILED" or "ERROR" clearly.

## OUTPUT FORMAT
Return ONLY the clean Python code. No markdown formatting.
"""

    print("🤖 Asking LLM to generate script...")
    
    try:
        result = await llm.ainvoke([
            SystemMessage(content="You are an expert Python/Playwright developer. Generate clean, working code only."),
            HumanMessage(content=prompt)
        ])
        
        script_code = extract_llm_text(result.content).strip()
        
        # Clean up code if wrapped in markdown
        if script_code.startswith("```python"):
            script_code = script_code[9:]
        if script_code.startswith("```"):
            script_code = script_code[3:]
        if script_code.endswith("```"):
            script_code = script_code[:-3]
        script_code = script_code.strip()
        
        print(f"✅ LLM generated {len(script_code)} chars of code")
        
    except Exception as e:
        print(f"❌ LLM script generation failed: {e}")
        return {
            "status": "SCRIPT_ERROR",
            "script_error": str(e),
            "logs": (state.get("logs") or []) + [f"Script generation failed: {e}"]
        }
    
    # Save the generated script
    output_dir = os.path.join(os.getcwd(), "output", "generated_scripts")
    os.makedirs(output_dir, exist_ok=True)
    
    import datetime
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    script_path = os.path.join(output_dir, f"{site_name}_scraper_{timestamp}.py")
    
    with open(script_path, 'w', encoding='utf-8') as f:
        f.write(script_code)
    
    print(f"📄 Script saved: {script_path}")
    
    return {
        "status": "SCRIPT_GENERATED",
        "generated_script_path": script_path,
        "generated_script_code": script_code,
        "recorded_steps": recorded_steps,
        "column_mapping": column_mapping,
        "script_test_attempts": 0,
        "extracted_data": [],
        "logs": (state.get("logs") or []) + [
            f"✅ LLM generated script: {script_path}",
            f"Steps: {len(recorded_steps)}, Columns: {len(columns_list)}"
        ]
    }


async def node_test_script(state: AgentState) -> Dict[str, Any]:
    """
    Test the generated script by running it.
    
    Captures any errors for the fix node.
    """
    print("--- Node: Test Script ---")
    
    script_path = state.get("generated_script_path")
    script_code = state.get("generated_script_code", "")
    search_query = state.get("search_query", "Test")
    attempts = state.get("script_test_attempts", 0) + 1
    
    if not script_path or not os.path.exists(script_path):
        return {
            "status": "SCRIPT_ERROR",
            "script_error": "Script file not found",
            "script_test_attempts": attempts,
            "logs": (state.get("logs") or []) + ["Script file not found"]
        }
    
    print(f"🧪 Testing script (attempt {attempts})...")
    
    import subprocess
    import sys
    
    try:
        # Run the script with the search query
        result = subprocess.run(
            [sys.executable, script_path, search_query],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=os.getcwd()
        )
        
        if result.returncode == 0:
            stdout_lower = result.stdout.lower()
            failure_keywords = ["error", "failed", "exception", "timed out", "no data extracted"]
            if any(key in stdout_lower for key in failure_keywords):
                # False positive: script printed error but exited with 0
                error_msg = result.stdout
                print(f"❌ Script failed (detected in output): {error_msg[:500]}")
                return {
                    "status": "SCRIPT_FAILED",
                    "script_test_attempts": attempts,
                    "script_error": error_msg,
                    "logs": (state.get("logs") or []) + [f"Script test failed: {error_msg[:200]}"]
                }
                
            print("✅ Script executed successfully!")
            print(f"Output: {result.stdout[:500]}")
            
            return {
                "status": "SCRIPT_TESTED",
                "script_test_attempts": attempts,
                "script_error": None,
                "logs": (state.get("logs") or []) + [
                    f"✅ Script test passed (attempt {attempts})",
                    f"Output: {result.stdout[:200]}"
                ]
            }
        else:
            error_msg = result.stderr or result.stdout
            print(f"❌ Script failed: {error_msg[:500]}")
            
            return {
                "status": "SCRIPT_FAILED",
                "script_test_attempts": attempts,
                "script_error": error_msg,
                "logs": (state.get("logs") or []) + [f"Script test failed: {error_msg[:200]}"]
            }
            
    except subprocess.TimeoutExpired:
        return {
            "status": "SCRIPT_FAILED",
            "script_test_attempts": attempts,
            "script_error": "Script timed out after 120 seconds",
            "logs": (state.get("logs") or []) + ["Script timed out"]
        }
    except Exception as e:
        return {
            "status": "SCRIPT_FAILED", 
            "script_test_attempts": attempts,
            "script_error": str(e),
            "logs": (state.get("logs") or []) + [f"Script test error: {e}"]
        }


async def node_fix_script(state: AgentState) -> Dict[str, Any]:
    """
    Use LLM to fix script errors based on the error message.
    """
    print("--- Node: Fix Script (LLM) ---")
    
    script_code = state.get("generated_script_code", "")
    script_path = state.get("generated_script_path", "")
    error_msg = state.get("script_error", "")
    attempts = state.get("script_test_attempts", 0)
    
    print(f"✍️ Attempting to fix script (attempt {attempts})...")
    print(f"Error: {error_msg[:300]}")
    
    prompt = f"""Fix this Python Playwright script that has an error.

## CURRENT SCRIPT
```python
{script_code}
```

## ERROR MESSAGE
{error_msg}

## INSTRUCTIONS
1. Analyze the error and fix the issue
2. Make sure the script is complete and runnable
3. Keep the same function signature and structure
4. Fix any selector issues, timing issues, or logic errors

Return ONLY the fixed Python code, no explanations.
"""

    try:
        result = await llm.ainvoke([
            SystemMessage(content="You are an expert Python/Playwright debugger. Fix the code."),
            HumanMessage(content=prompt)
        ])
        
        fixed_code = extract_llm_text(result.content).strip()
        
        # Clean up code if wrapped in markdown
        if fixed_code.startswith("```python"):
            fixed_code = fixed_code[9:]
        if fixed_code.startswith("```"):
            fixed_code = fixed_code[3:]
        if fixed_code.endswith("```"):
            fixed_code = fixed_code[:-3]
        fixed_code = fixed_code.strip()
        
        # Save the fixed script
        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(fixed_code)
        
        print(f"✅ Script fixed and saved")
        
        return {
            "status": "SCRIPT_FIXED",
            "generated_script_code": fixed_code,
            "script_error": None,
            "logs": (state.get("logs") or []) + [f"Script fixed (attempt {attempts})"]
        }
        
    except Exception as e:
        print(f"❌ Fix failed: {e}")
        return {
            "status": "SCRIPT_ERROR",
            "script_error": str(e),
            "logs": (state.get("logs") or []) + [f"Fix failed: {e}"]
        }




async def node_escalate(state: AgentState) -> Dict[str, Any]:
    """Escalate to human review on failure."""
    print("🚨 ESCALATION: Agent cannot proceed.")
    return {
        "status": "NEEDS_HUMAN_REVIEW",
        "needs_human_review": True,
        "logs": state.get("logs", []) + ["Escalated to human review"]
    }
