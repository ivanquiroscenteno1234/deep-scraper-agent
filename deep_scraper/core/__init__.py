"""Core components: state, browser management, and schemas."""

from deep_scraper.core.state import AgentState
from deep_scraper.core.browser import BrowserManager
from deep_scraper.core.schemas import NavigationDecision, SearchFormDetails, ExtractionResult

__all__ = ["AgentState", "BrowserManager", "NavigationDecision", "SearchFormDetails", "ExtractionResult"]
