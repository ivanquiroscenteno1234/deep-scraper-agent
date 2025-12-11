"""
Deep Scraper Agent - Autonomous web scraping powered by LangGraph + Gemini
"""

from deep_scraper.core.state import AgentState
from deep_scraper.core.browser import BrowserManager
from deep_scraper.graph.engine import app as graph_app

__version__ = "1.0.0"
__all__ = ["AgentState", "BrowserManager", "graph_app"]
