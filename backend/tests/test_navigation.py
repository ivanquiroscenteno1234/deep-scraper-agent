
import pytest
import sys
import os
import unittest.mock

# Set dummy environment variables to bypass validation
os.environ["GOOGLE_API_KEY"] = "dummy_key"
os.environ["GEMINI_MODEL"] = "dummy_model"

# Ensure we can import from deep_scraper
# backend/tests -> backend/ -> root/
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

# Mocking modules that might cause side effects or require connections
# We only want to import the constants from navigation.py
with unittest.mock.patch.dict(sys.modules):
    # Depending on how the imports are structured, we might trigger graph initialization
    # so we might need to be careful.
    try:
        from deep_scraper.graph.nodes.navigation import _SEARCH_INDICATORS_LOWER
    except ImportError:
        # Fallback if the path is slightly off or import fails due to other deps
        # We try to load it manually or just fail the test
        raise

def test_search_indicator_logic():
    """
    Verify that the optimized search indicator logic correctly detects
    indicators in HTML content.
    """

    # Verify constants are lowercase
    for ind in _SEARCH_INDICATORS_LOWER:
        assert ind == ind.lower(), f"Indicator {ind} should be lowercase"

    # Test cases
    test_cases = [
        # (html_content, expected_has_indicators)
        ("<html><body><input id='SearchOnName'></body></html>", True),
        ("<div>some random text</div>", False),
        # 'searchForm' is in the list. 'searchform' should match.
        ("<div><form id='searchForm'></form></div>", True), # 'searchform' matches just the string 'searchform'
        ("<div><input id=\"searchInput\"></div>", True), # Must use double quotes as per indicators list
        ("<div>name-Name</div>", True),
        ("NON MATCHING CONTENT", False),
    ]

    for html, expected in test_cases:
        # Simulate the optimization logic
        page_content_lower = html.lower()
        has_indicators = any(indicator in page_content_lower for indicator in _SEARCH_INDICATORS_LOWER)

        assert has_indicators == expected, f"Failed for content: {html}"

def test_input_element_logic():
    """
    Verify the logic for detecting input elements.
    """
    test_cases = [
        ("<input type='text'>", True),
        ("<INPUT TYPE='TEXT'>", True), # case insensitive check
        ("<div>no inputs here</div>", False),
        ("<textarea>not an input</textarea>", False),
    ]

    for html, expected in test_cases:
        page_content_lower = html.lower()
        has_input = '<input' in page_content_lower
        assert has_input == expected, f"Failed input check for: {html}"
