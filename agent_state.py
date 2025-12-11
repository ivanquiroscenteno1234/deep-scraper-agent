from typing import TypedDict, List, Dict, Optional, Any

class AgentState(TypedDict):
    """
    Represents the state of the Deep Scraper agent.
    
    Attributes:
        target_url: The starting URL for the navigation.
        search_query: The term to search for (e.g., "Smith").
        current_page_summary: Markdown text summary of the current page content.
        logs: History of actions taken by the agent.
        attempt_count: Circuit breaker counter.
        status: High-level status of the agent.
        extracted_data: List of extracted records.
        search_selectors: Dict to store identified form selectors (input/submit).
    """
    target_url: str
    search_query: str
    current_page_summary: str
    logs: List[str]
    attempt_count: int
    status: str  # Enum: "NAVIGATING", "SEARCH_PAGE_FOUND", "SEARCH_EXECUTED", "COMPLETED", "FAILED"
    extracted_data: List[Dict[str, Any]]
    search_selectors: Optional[Dict[str, str]]
