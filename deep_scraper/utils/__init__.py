"""Utility functions, helpers, and constants."""

from deep_scraper.utils.dom import simplify_dom, get_interactive_map
from deep_scraper.utils.prompts import EXPLORER_SYSTEM_PROMPT, CODE_GENERATION_PROMPT
from deep_scraper.utils.helpers import (
    extract_llm_text,
    extract_code_from_markdown,
    clean_html_for_llm,
    analyze_page_with_llm,
    get_site_name_from_url,
    StructuredLogger,
    NavigationDecision,
    PopupAnalysis,
    PostClickAnalysis,
    PostPopupAnalysis,
    ColumnAnalysis,
)
from deep_scraper.utils.constants import (
    RESULTS_GRID_SELECTORS,
    KNOWN_GRID_COLUMNS,
    DEFAULT_NAVIGATION_TIMEOUT,
    DEFAULT_ELEMENT_TIMEOUT,
    DEFAULT_GRID_WAIT_TIMEOUT,
    MAX_SCRIPT_FIX_ATTEMPTS,
    SCRIPT_TEST_TIMEOUT_SECONDS,
    DEFAULT_HTML_LIMIT,
    POPUP_HTML_LIMIT,
    COLUMN_HTML_LIMIT,
)
from deep_scraper.utils.script_template import build_script_prompt

__all__ = [
    # DOM utilities
    "simplify_dom", 
    "get_interactive_map", 
    # Prompts
    "EXPLORER_SYSTEM_PROMPT", 
    "CODE_GENERATION_PROMPT",
    # Helpers
    "extract_llm_text",
    "extract_code_from_markdown",
    "clean_html_for_llm",
    "analyze_page_with_llm",
    "get_site_name_from_url",
    "StructuredLogger",
    # Models
    "NavigationDecision",
    "PopupAnalysis",
    "PostClickAnalysis",
    "PostPopupAnalysis",
    "ColumnAnalysis",
    # Constants
    "RESULTS_GRID_SELECTORS",
    "KNOWN_GRID_COLUMNS",
    "DEFAULT_NAVIGATION_TIMEOUT",
    "DEFAULT_ELEMENT_TIMEOUT",
    "DEFAULT_GRID_WAIT_TIMEOUT",
    "MAX_SCRIPT_FIX_ATTEMPTS",
    "SCRIPT_TEST_TIMEOUT_SECONDS",
    "DEFAULT_HTML_LIMIT",
    "POPUP_HTML_LIMIT",
    "COLUMN_HTML_LIMIT",
    # Template
    "build_script_prompt",
]
