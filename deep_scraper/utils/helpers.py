"""
helpers.py — Backward-compatibility shim.

All symbols have been moved to focused modules:
  - Pydantic models      → deep_scraper.core.schemas
  - Text utilities       → deep_scraper.utils.text
  - HTML cleaning        → deep_scraper.utils.html
  - Structured logging   → deep_scraper.utils.logging

Import from those modules directly for new code.
"""

# Re-export everything so existing imports keep working without changes.
from deep_scraper.core.schemas import (  # noqa: F401
    NavigationDecision,
    PopupAnalysis,
    PostClickAnalysis,
    PostPopupAnalysis,
    ColumnAnalysis,
)
from deep_scraper.utils.text import (  # noqa: F401
    extract_llm_text,
    extract_code_from_markdown,
    get_site_name_from_url,
)
from deep_scraper.utils.html import clean_html_for_llm  # noqa: F401
from deep_scraper.utils.logging import StructuredLogger  # noqa: F401

# analyze_page_with_llm kept here as it depends on multiple modules
import datetime
from typing import Any, Type, TypeVar
from pydantic import BaseModel
from langchain_core.messages import SystemMessage, HumanMessage

T = TypeVar("T", bound=BaseModel)


async def analyze_page_with_llm(
    browser,
    llm,
    model_class: Type[T],
    system_prompt: str,
    user_prompt: str,
    html_limit: int = 20000,
) -> T:
    """
    Common pattern for analyzing a page with LLM and structured output.
    """
    snapshot = await browser.get_snapshot()
    full_html = snapshot.get("html", str(snapshot))
    print(f"📸 Got snapshot ({len(full_html)} chars)")

    html = full_html[:html_limit]
    full_user_prompt = f"{user_prompt}\n\nHTML:\n{html}"

    structured_llm = llm.with_structured_output(model_class)
    result = await structured_llm.ainvoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=full_user_prompt),
    ])
    return result

