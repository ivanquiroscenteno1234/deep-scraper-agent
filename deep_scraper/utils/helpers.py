"""
Helpers module - Reusable utilities for the Deep Scraper Agent.

Contains:
- LLM text extraction
- Markdown code block extraction
- HTML cleaning for LLM analysis
- Page analysis helpers
- Structured logging
- Type definitions (Pydantic models)
"""

import re
import datetime
from typing import Any, Dict, List, Optional, Type, TypeVar
from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage


# ============================================================================
# TYPE DEFINITIONS (Pydantic Models)
# ============================================================================

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
    start_date_input_ref: str = Field(default="", description="CSS selector for start date input if search page (e.g. #RecordDateFrom)")
    end_date_input_ref: str = Field(default="", description="CSS selector for end date input if search page (e.g. #RecordDateTo)")
    grid_selector: str = Field(default="", description="CSS selector for data grid/table if results grid")


class PopupAnalysis(BaseModel):
    """Analysis result for popup detection after search."""
    has_popup: bool = Field(description="True if there's a popup/modal requiring user action before results")
    popup_selector: str = Field(default="", description="CSS selector for the popup container if present")
    action_button_selector: str = Field(default="", description="CSS selector for the button to click (e.g., Done, Submit, OK)")
    description: str = Field(description="Brief description of what was found")


class PostClickAnalysis(BaseModel):
    """Analysis result after clicking a button."""
    page_changed: bool = Field(description="True if the page content changed after the click")
    is_search_page: bool = Field(description="True if we're now on a search form page")
    still_on_disclaimer: bool = Field(description="True if still showing disclaimer/accept content")
    description: str = Field(description="Brief description of current page state")


class PostPopupAnalysis(BaseModel):
    """Analysis result after handling a popup."""
    has_results_grid: bool = Field(description="True if results grid/table is now visible")
    grid_selector: str = Field(default="", description="CSS selector for the results grid if found")
    needs_more_action: bool = Field(description="True if another action is needed before results appear")
    next_action: str = Field(default="", description="Description of next action needed, if any")


class ColumnAnalysis(BaseModel):
    """Analysis result for grid column detection."""
    grid_selector: str = Field(description="Primary CSS selector for the grid")
    row_selector: str = Field(description="CSS selector for data rows")
    columns: list = Field(description="List of column names found")


# ============================================================================
# TEXT EXTRACTION UTILITIES
# ============================================================================

def extract_llm_text(content: Any) -> str:
    """
    Safely extract text from LLM content.
    
    Handles both string and list/multimodal formats from LLM responses.
    
    Args:
        content: LLM response content (str, list, or other)
        
    Returns:
        Extracted text as string
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            item.get("text", "") if isinstance(item, dict) else str(item) 
            for item in content
        )
    return str(content)


def extract_code_from_markdown(text: str) -> str:
    """
    Strip markdown code fences from LLM response.
    
    Args:
        text: Raw LLM response that may contain ```python ... ``` blocks
        
    Returns:
        Clean code without markdown fences
    """
    text = text.strip()
    
    # Remove opening fence
    if text.startswith("```python"):
        text = text[9:]
    elif text.startswith("```"):
        text = text[3:]
    
    # Remove closing fence
    if text.endswith("```"):
        text = text[:-3]
    
    return text.strip()


# ============================================================================
# HTML CLEANING FOR LLM
# ============================================================================

# Pre-compiled regex patterns for performance (Bolt ⚡ Optimization)
_SCRIPT_PATTERN = re.compile(r'<script[^>]*>.*?</script>', re.DOTALL | re.IGNORECASE)
_STYLE_PATTERN = re.compile(r'<style[^>]*>.*?</style>', re.DOTALL | re.IGNORECASE)
_COMMENT_PATTERN = re.compile(r'<!--.*?-->', re.DOTALL)
_HIDDEN_DISPLAY_PATTERN = re.compile(r'<[^>]+display:\s*none[^>]*>.*?</[^>]+>', re.DOTALL | re.IGNORECASE)
_HIDDEN_VISIBILITY_PATTERN = re.compile(r'<[^>]+visibility:\s*hidden[^>]*>.*?</[^>]+>', re.DOTALL | re.IGNORECASE)
_SVG_PATTERN = re.compile(r'<svg[^>]*>.*?</svg>', re.DOTALL | re.IGNORECASE)
_WHITESPACE_PATTERN = re.compile(r'\s+')

def clean_html_for_llm(html: str, max_length: int = 30000) -> str:
    """
    Clean HTML for better LLM analysis.
    
    Removes noise like scripts, styles, comments, and hidden elements
    to help the LLM focus on visible, interactive content.
    
    Args:
        html: Raw HTML string
        max_length: Maximum length to return
        
    Returns:
        Cleaned HTML string
    """
    # Remove script tags and content
    html = _SCRIPT_PATTERN.sub('', html)
    
    # Remove style tags and content
    html = _STYLE_PATTERN.sub('', html)
    
    # Remove HTML comments
    html = _COMMENT_PATTERN.sub('', html)
    
    # Remove hidden elements (common patterns)
    html = _HIDDEN_DISPLAY_PATTERN.sub('', html)
    html = _HIDDEN_VISIBILITY_PATTERN.sub('', html)
    
    # Remove SVG content (usually icons, very verbose)
    html = _SVG_PATTERN.sub('[SVG]', html)
    
    # Collapse multiple whitespace
    html = _WHITESPACE_PATTERN.sub(' ', html)
    
    # Truncate to max length
    if len(html) > max_length:
        html = html[:max_length] + "\n... [TRUNCATED]"
    
    return html.strip()


# ============================================================================
# STRUCTURED LOGGING
# ============================================================================

class StructuredLogger:
    """
    Structured logger that captures logs with timestamps and context.
    
    Stores logs in a list for inclusion in agent state while also
    printing to console for real-time visibility.
    """
    
    def __init__(self, node_name: str):
        self.node_name = node_name
        self.logs: List[str] = []
    
    def _format(self, level: str, message: str) -> str:
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        return f"[{timestamp}] [{self.node_name}] {level}: {message}"
    
    def info(self, message: str) -> None:
        formatted = self._format("INFO", message)
        print(formatted)
        self.logs.append(formatted)
    
    def warning(self, message: str) -> None:
        formatted = self._format("WARN", message)
        print(f"⚠️ {formatted}")
        self.logs.append(formatted)
    
    def error(self, message: str) -> None:
        formatted = self._format("ERROR", message)
        print(f"❌ {formatted}")
        self.logs.append(formatted)
    
    def success(self, message: str) -> None:
        formatted = self._format("OK", message)
        print(f"✅ {formatted}")
        self.logs.append(formatted)
    
    def debug(self, message: str) -> None:
        formatted = self._format("DEBUG", message)
        # Debug only to console, not stored
        print(f"🔍 {formatted}")
    
    def get_logs(self) -> List[str]:
        """Get all captured logs."""
        return self.logs


# ============================================================================
# LLM ANALYSIS HELPERS
# ============================================================================

T = TypeVar('T', bound=BaseModel)


async def analyze_page_with_llm(
    browser,
    llm,
    model_class: Type[T],
    system_prompt: str,
    user_prompt: str,
    html_limit: int = 20000
) -> T:
    """
    Common pattern for analyzing a page with LLM and structured output.
    
    Args:
        browser: MCPBrowserAdapter instance
        llm: LangChain LLM instance
        model_class: Pydantic model class for structured output
        system_prompt: System message for the LLM
        user_prompt: User message template (will have HTML appended)
        html_limit: Maximum characters of HTML to include
        
    Returns:
        Parsed model instance from LLM response
    """
    # Get page snapshot
    snapshot = await browser.get_snapshot()
    full_html = snapshot.get("html", str(snapshot))
    print(f"📸 Got snapshot ({len(full_html)} chars)")
    
    # Clean HTML before truncating (Bolt ⚡ Optimization)
    # This removes scripts/styles/comments first, ensuring the truncated content
    # is actually useful for the LLM, rather than being 20k chars of <script> tags.
    html = clean_html_for_llm(full_html, max_length=html_limit)
    
    # Build full prompt with HTML
    full_user_prompt = f"{user_prompt}\n\nHTML:\n{html}"
    
    # Get structured response
    structured_llm = llm.with_structured_output(model_class)
    result = await structured_llm.ainvoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=full_user_prompt)
    ])
    
    return result


def get_site_name_from_url(url: str) -> str:
    """
    Extract a clean site name from a URL for use in filenames.
    
    Args:
        url: Full URL
        
    Returns:
        Clean site name (e.g., 'brevardclerk' from 'https://brevardclerk.us/...')
    """
    from urllib.parse import urlparse
    import re
    
    parsed = urlparse(url)
    hostname = parsed.hostname or "unknown"
    
    # Clean up the hostname
    # Remove common prefixes
    for prefix in ["www.", "www2.", "apps.", "portal.", "vaclmweb1."]:
        if hostname.startswith(prefix):
            hostname = hostname[len(prefix):]
    
    # Remove TLD and keep just the main domain part
    parts = hostname.split(".")
    if len(parts) >= 2:
        site_name = parts[0]
    else:
        site_name = hostname
    
    # Clean to alphanumeric only
    site_name = re.sub(r'[^a-zA-Z0-9]', '', site_name)
    
    return site_name.lower() or "unknown"
