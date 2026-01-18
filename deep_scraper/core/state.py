"""
Agent State - TypedDict defining the state for the Deep Scraper agent.

See .agent/workflows/project-specification.md for workflow details.
"""

from typing import TypedDict, List, Dict, Optional, Any


class AgentState(TypedDict):
    """
    State of the Deep Scraper agent.
    
    Core fields for navigation and step recording:
    - target_url: Starting URL
    - search_query: Term to search
    - recorded_steps: List of actions for script generation
    - column_mapping: Grid column names identified by LLM
    """
    # Core navigation
    target_url: str
    search_query: str
    start_date: str
    end_date: str
    current_page_summary: str
    
    # Control flow
    status: str  # NAVIGATING, SEARCH_PAGE_FOUND, SEARCH_EXECUTED, SCRIPT_GENERATED, FAILED
    attempt_count: int
    healing_attempts: int
    needs_human_review: bool
    
    # Step recording (key for script generation)
    recorded_steps: List[Dict[str, Any]]
    search_selectors: Optional[Dict[str, str]]
    column_mapping: Dict[str, str]
    
    # Output
    generated_script_path: Optional[str]
    generated_script_code: Optional[str]
    extracted_data: List[Dict[str, Any]]
    
    # Logging
    logs: List[str]
    
    # Script testing (optional)
    script_test_attempts: int
    script_error: Optional[str]
    discovered_grid_selectors: List[str]
    thought_signature: Optional[str]
    
    # Disclaimer/click loop prevention
    disclaimer_click_attempts: int  # How many times we've clicked accept buttons
    clicked_selectors: List[str]    # Selectors we've already tried clicking
    grid_html: Optional[str]
    
    # React SPA detection
    is_react_spa: bool  # True if page requires React-specific input handling
