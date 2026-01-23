
import pytest
import os

# Mock env vars if not set
if "GOOGLE_API_KEY" not in os.environ:
    os.environ["GOOGLE_API_KEY"] = "dummy"
if "GEMINI_MODEL" not in os.environ:
    os.environ["GEMINI_MODEL"] = "dummy"

from deep_scraper.graph.nodes.navigation import _SEARCH_INDICATORS, _SEARCH_INDICATORS_LOWER

def test_search_indicators_constants():
    assert len(_SEARCH_INDICATORS) > 0
    assert len(_SEARCH_INDICATORS) == len(_SEARCH_INDICATORS_LOWER)

    for original, lower in zip(_SEARCH_INDICATORS, _SEARCH_INDICATORS_LOWER):
        assert original.lower() == lower

def test_search_detection_logic():
    # Simulate the logic in node_analyze_mcp

    # Case 1: Indicator present
    page_content = "Some random content... SearchCriteria ... more content"
    page_content_lower = page_content.lower()

    # This is the logic we optimized
    has_search_indicators = any(indicator in page_content_lower for indicator in _SEARCH_INDICATORS_LOWER)

    assert has_search_indicators is True

    # Case 2: Indicator NOT present
    page_content = "Some random content... NoSearchHere ... more content"
    page_content_lower = page_content.lower()
    has_search_indicators = any(indicator in page_content_lower for indicator in _SEARCH_INDICATORS_LOWER)

    assert has_search_indicators is False

    # Case 3: Indicator present but Case Mismatch (should work because we check against lower)
    page_content = "Some random content... searchcriteria ... more content"
    page_content_lower = page_content.lower()
    has_search_indicators = any(indicator in page_content_lower for indicator in _SEARCH_INDICATORS_LOWER)

    assert has_search_indicators is True
