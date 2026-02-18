"""
HTML utilities for Deep Scraper Agent.

Merged from:
- deep_scraper/utils/dom.py (simplify_dom, get_interactive_map)
- deep_scraper/utils/helpers.py (clean_html_for_llm)
- deep_scraper/graph/nodes/extraction.py (filter_hidden_columns_from_html)
"""

import re
from typing import List, Tuple

from bs4 import BeautifulSoup


# ---------------------------------------------------------------------------
# LLM-oriented cleaning
# ---------------------------------------------------------------------------

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
    html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)

    # Remove style tags and content
    html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)

    # Remove HTML comments
    html = re.sub(r"<!--.*?-->", "", html, flags=re.DOTALL)

    # Remove hidden elements with inline styles
    html = re.sub(
        r"<[^>]+display:\s*none[^>]*>.*?</[^>]+>", "", html, flags=re.DOTALL | re.IGNORECASE
    )
    html = re.sub(
        r"<[^>]+visibility:\s*hidden[^>]*>.*?</[^>]+>", "", html, flags=re.DOTALL | re.IGNORECASE
    )

    # Remove elements with common hidden CSS classes
    hidden_class_patterns = [
        r'<div[^>]+class="[^"]*\bhide\b[^"]*"[^>]*>.*?</div>',
        r'<div[^>]+class="[^"]*\bhidden\b[^"]*"[^>]*>.*?</div>',
        r'<div[^>]+class="[^"]*\bd-none\b[^"]*"[^>]*>.*?</div>',
        r'<div[^>]+class="[^"]*\bdisplay-none\b[^"]*"[^>]*>.*?</div>',
        r'<section[^>]+class="[^"]*\bhide\b[^"]*"[^>]*>.*?</section>',
    ]
    for pattern in hidden_class_patterns:
        html = re.sub(pattern, "", html, flags=re.DOTALL | re.IGNORECASE)

    # Remove SVG content (usually icons, very verbose)
    html = re.sub(r"<svg[^>]*>.*?</svg>", "[SVG]", html, flags=re.DOTALL | re.IGNORECASE)

    # Collapse multiple whitespace
    html = re.sub(r"\s+", " ", html)

    if len(html) > max_length:
        html = html[:max_length] + "\n... [TRUNCATED]"

    return html.strip()


# ---------------------------------------------------------------------------
# Interactive-element extraction (formerly dom.py)
# ---------------------------------------------------------------------------

def simplify_dom(html_content: str) -> str:
    """
    Simplify HTML to only include interactive elements and essential structure.

    Reduces token count for the LLM by removing non-interactive noise.

    Keeps: input, button, select, a (with text), label.
    """
    soup = BeautifulSoup(html_content, "lxml")

    # Remove non-interactive boilerplate
    for tag in soup(["script", "style", "meta", "head", "svg", "path", "noscript", "iframe", "link"]):
        tag.decompose()

    # Remove hidden inputs
    for tag in soup.find_all("input", type="hidden"):
        tag.decompose()

    def clean_attrs(tag) -> None:
        allowed = ["id", "name", "type", "placeholder", "value", "aria-label", "role", "class"]
        attrs = dict(tag.attrs)
        tag.attrs = {k: v for k, v in attrs.items() if k in allowed}
        if "class" in tag.attrs:
            tag.attrs["class"] = " ".join(tag.attrs["class"])

    interactables = soup.find_all(["input", "button", "select", "textarea", "a", "label"])
    simplified_html = ""
    for tag in interactables:
        clean_attrs(tag)
        if tag.name == "a" and not tag.get_text(strip=True):
            continue
        simplified_html += str(tag) + "\n"

    return simplified_html


def get_interactive_map(page) -> str:
    """
    Return a simplified representation of a page's interactive elements.

    Args:
        page: Playwright page-like object with a .content() method.
    """
    content = page.content()
    return simplify_dom(content)


# ---------------------------------------------------------------------------
# Hidden column filtering (moved from extraction.py)
# ---------------------------------------------------------------------------

def filter_hidden_columns_from_html(html: str) -> Tuple[str, List[int]]:
    """
    Filter out hidden table columns from HTML and return visible column indices.

    Detects columns hidden via:
    - CSS class="hidden", class="hide", or class containing "hidden"
    - Inline style display:none or visibility:hidden

    Returns:
        Tuple of (filtered_html, visible_column_indices)
    """
    visible_indices: List[int] = []

    th_pattern = re.compile(r"<th([^>]*)>(.*?)</th>", re.IGNORECASE | re.DOTALL)

    hidden_patterns = [
        r'class\s*=\s*["\'][^"\']*\b(hidden|hide)\b[^"\']*["\']',
        r'style\s*=\s*["\'][^"\']*display\s*:\s*none[^"\']*["\']',
        r'style\s*=\s*["\'][^"\']*visibility\s*:\s*hidden[^"\']*["\']',
    ]

    def is_hidden(attrs: str) -> bool:
        return any(re.search(p, attrs, re.IGNORECASE) for p in hidden_patterns)

    all_ths = th_pattern.findall(html)
    for i, (attrs, _content) in enumerate(all_ths):
        if not is_hidden(attrs):
            visible_indices.append(i)

    filtered_html = html

    # Remove hidden <th> and <td> elements by class
    hidden_cell_pattern = re.compile(
        r'<(th|td)\s+[^>]*class\s*=\s*["\'][^"\']*\b(hidden|hide)\b[^"\']*["\'][^>]*>.*?</\1>',
        re.IGNORECASE | re.DOTALL,
    )
    filtered_html = hidden_cell_pattern.sub("", filtered_html)

    # Remove cells with inline display:none
    hidden_style_pattern = re.compile(
        r'<(th|td)\s+[^>]*style\s*=\s*["\'][^"\']*display\s*:\s*none[^"\']*["\'][^>]*>.*?</\1>',
        re.IGNORECASE | re.DOTALL,
    )
    filtered_html = hidden_style_pattern.sub("", filtered_html)

    return filtered_html, visible_indices
