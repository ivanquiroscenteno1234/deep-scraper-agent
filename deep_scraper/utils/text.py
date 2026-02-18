"""
Text extraction utilities for Deep Scraper Agent.

Extracted from deep_scraper/utils/helpers.py.
"""

import re
from typing import Any


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


def get_site_name_from_url(url: str) -> str:
    """
    Extract a clean site name from a URL for use in filenames.

    Args:
        url: Full URL

    Returns:
        Clean site name (e.g., 'brevardclerk' from 'https://brevardclerk.us/...')
    """
    from urllib.parse import urlparse

    parsed = urlparse(url)
    hostname = parsed.hostname or "unknown"

    # Remove common prefixes
    for prefix in ["www.", "www2.", "apps.", "portal.", "vaclmweb1."]:
        if hostname.startswith(prefix):
            hostname = hostname[len(prefix):]

    # Keep just the main domain part (drop TLD)
    parts = hostname.split(".")
    site_name = parts[0] if len(parts) >= 2 else hostname

    # Clean to alphanumeric only
    site_name = re.sub(r"[^a-zA-Z0-9]", "", site_name)

    return site_name.lower() or "unknown"
