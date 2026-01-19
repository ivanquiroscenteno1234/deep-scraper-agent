"""
Script testing nodes - Test and fix generated scripts.

Contains:
- node_test_script: Run generated script and capture errors
- node_fix_script: Use LLM to fix errors
- node_escalate: Escalate to human review
"""

import json
import os
import re
import subprocess
import sys
from typing import Any, Dict

from langchain_core.messages import SystemMessage, HumanMessage

from deep_scraper.core.state import AgentState
from deep_scraper.graph.nodes.config import (
    llm_high_thinking,
    extract_llm_text,
    extract_code_from_markdown,
    StructuredLogger,
    MAX_SCRIPT_FIX_ATTEMPTS,
    SCRIPT_TEST_TIMEOUT_SECONDS,
)


async def node_test_script(state: AgentState) -> Dict[str, Any]:
    """
    Test the generated script by running it.
    
    Captures any errors for the fix node.
    """
    log = StructuredLogger("TestScript")
    
    script_path = state.get("generated_script_path")
    script_code = state.get("generated_script_code", "")
    search_query = state.get("search_query", "Test")
    start_date = state.get("start_date", "01/01/1980")
    end_date = state.get("end_date", "01/01/2025")
    attempts = state.get("script_test_attempts", 0) + 1
    
    log.info(f"Testing script (attempt {attempts}) with dates {start_date} - {end_date}")
    
    if not script_path or not os.path.exists(script_path):
        log.error("Script file not found")
        return {
            "status": "SCRIPT_ERROR",
            "script_error": "Script file not found",
            "script_test_attempts": attempts,
            "logs": (state.get("logs") or []) + log.get_logs()
        }
    
    try:
        result = subprocess.run(
            [sys.executable, script_path, search_query, start_date, end_date],
            capture_output=True,
            text=True,
            timeout=SCRIPT_TEST_TIMEOUT_SECONDS,
            cwd=os.getcwd()
        )
        
        log.debug(f"Script stdout ({len(result.stdout)} chars)")
        if result.stderr:
            log.debug(f"Script stderr ({len(result.stderr)} chars)")
        
        # Extract step logs for debugging
        step_logs = [line for line in result.stdout.split('\n') if line.strip().startswith('[STEP')]
        
        if result.returncode == 0:
            stdout_upper = result.stdout.upper()
            is_success = "SUCCESS" in stdout_upper or "[SUCCESS]" in stdout_upper
            
            if is_success and any(x in stdout_upper for x in ["EXTRACTED", "FOUND", "SAVED"]):
                # Parse row count
                row_count = 0
                patterns = [
                    r'(?:Extracted|Found|Saved)\s+(\d+)\s+(?:rows|records|items)',
                    r'SUCCESS:\s+Extracted\s+(\d+)',
                ]
                for pattern in patterns:
                    match = re.search(pattern, result.stdout, re.IGNORECASE)
                    if match:
                        row_count = int(match.group(1))
                        break
                
                if row_count > 0:
                    log.success(f"Script passed! Extracted {row_count} rows")
                    return {
                        "status": "SCRIPT_TESTED",
                        "script_test_attempts": attempts,
                        "script_error": None,
                        "logs": (state.get("logs") or []) + log.get_logs()
                    }
                else:
                    error_msg = "Script completed but extracted 0 rows"
                    log.error(error_msg)
                    return {
                        "status": "SCRIPT_FAILED",
                        "script_test_attempts": attempts,
                        "script_error": f"{error_msg}\n\nOutput:\n{result.stdout}",
                        "logs": (state.get("logs") or []) + log.get_logs()
                    }
                    
            elif "No results found" in result.stdout:
                log.success("Script works (no results for search term)")
                return {
                    "status": "SCRIPT_TESTED",
                    "script_test_attempts": attempts,
                    "script_error": None,
                    "logs": (state.get("logs") or []) + log.get_logs()
                }
            else:
                error_msg = f"Script completed without SUCCESS message\n\nOutput:\n{result.stdout}"
                log.error("No SUCCESS message in output")
                return {
                    "status": "SCRIPT_FAILED",
                    "script_test_attempts": attempts,
                    "script_error": error_msg,
                    "script_output": result.stdout,
                    "logs": (state.get("logs") or []) + log.get_logs() + step_logs[-5:]
                }
        else:
            error_msg = result.stderr or result.stdout
            log.error(f"Script exited with code {result.returncode}")
            return {
                "status": "SCRIPT_FAILED",
                "script_test_attempts": attempts,
                "script_error": error_msg,
                "logs": (state.get("logs") or []) + log.get_logs()
            }
            
    except subprocess.TimeoutExpired:
        log.error(f"Script timed out after {SCRIPT_TEST_TIMEOUT_SECONDS}s")
        return {
            "status": "SCRIPT_FAILED",
            "script_test_attempts": attempts,
            "script_error": f"Script timed out after {SCRIPT_TEST_TIMEOUT_SECONDS} seconds",
            "logs": (state.get("logs") or []) + log.get_logs()
        }
    except Exception as e:
        log.error(f"Test error: {e}")
        return {
            "status": "SCRIPT_FAILED", 
            "script_test_attempts": attempts,
            "script_error": str(e),
            "logs": (state.get("logs") or []) + log.get_logs()
        }


async def node_fix_script(state: AgentState) -> Dict[str, Any]:
    """
    Use LLM to fix script errors based on the error message.
    """
    log = StructuredLogger("FixScript")
    
    script_code = state.get("generated_script_code", "")
    script_path = state.get("generated_script_path", "")
    error_msg = state.get("script_error", "")
    recorded_steps = state.get("recorded_steps", [])
    attempts = state.get("script_test_attempts", 0)
    site_type = state.get("site_type", "UNKNOWN")
    
    log.info(f"Fixing script (attempt {attempts})")
    log.debug(f"Error: {error_msg[:200]}...")
    
    # Add hints for common issues
    error_hints = []
    if "strict mode violation" in error_msg.lower():
        error_hints.append("IMPORTANT: Selector matches multiple elements. Use more specific selector like '#NamesWin input[type=submit]'.")
    if "resolved to" in error_msg and "elements" in error_msg:
        error_hints.append("Multiple elements matched. Scope the selector with a parent container ID.")
    
    hints_text = "\n".join(error_hints) if error_hints else ""
    
    prompt = f"""Fix this Python Playwright script that has an error.

## GROUND TRUTH (RECORDED STEPS)
These steps are known working selectors from the recording session.
YOU MUST prioritize these over any hallucinations or generic selectors.
- Site Type: {site_type}
{json.dumps(recorded_steps, indent=2)}

## CURRENT SCRIPT
```python
{script_code}
```

## ERROR MESSAGE
{error_msg}

{f"## HINTS{chr(10)}{hints_text}" if hints_text else ""}

## INSTRUCTIONS
1. Analyze the error and fix it by referring to the GROUND TRUTH.
2. If the error is a timeout, check if an intermediate popup (from GROUND TRUTH) needs to be handled.
3. If a selector matches multiple elements (strict mode violation), use the most specific selector from GROUND TRUTH or scope it with a parent ID (e.g., `#NamesWin input[type='submit']`).
4. Ensure you use a combined wait pattern after search: `page.wait_for_selector("GRID_SELECTOR, POPUP_SELECTOR", timeout=20000)`.

Return ONLY the fixed Python code, no explanations.
"""

    try:
        log.info("Sending to LLM for fix")
        result = await llm_high_thinking.ainvoke([
            SystemMessage(content="You are an expert Python/Playwright debugger. Fix strict mode violations by using more specific selectors."),
            HumanMessage(content=prompt)
        ])
        
        fixed_code = extract_code_from_markdown(extract_llm_text(result.content))
        
        log.info(f"Original: {len(script_code)} chars, Fixed: {len(fixed_code)} chars")
        
        # Save fixed script
        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(fixed_code)
        
        log.success(f"Script fixed and saved")
        
        return {
            "status": "SCRIPT_FIXED",
            "generated_script_code": fixed_code,
            "script_error": None,
            "logs": (state.get("logs") or []) + log.get_logs()
        }
        
    except Exception as e:
        log.error(f"Fix failed: {e}")
        return {
            "status": "SCRIPT_ERROR",
            "script_error": str(e),
            "logs": (state.get("logs") or []) + log.get_logs()
        }


async def node_escalate(state: AgentState) -> Dict[str, Any]:
    """Escalate to human review on failure."""
    log = StructuredLogger("Escalate")
    log.warning("Agent cannot proceed - escalating to human review")
    
    return {
        "status": "NEEDS_HUMAN_REVIEW",
        "needs_human_review": True,
        "logs": (state.get("logs") or []) + log.get_logs()
    }
