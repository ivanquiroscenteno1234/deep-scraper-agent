import time
import pytest

# Simulation of page content (100KB) - NO search indicators
PAGE_CONTENT = ("<html><body>" + "<div>Some text content</div>" * 2000 + "</body></html>") * 2

SEARCH_INDICATORS = [
    "#SearchOnName", "SearchOnName", "#RecordDateFrom", "#RecordDateTo",
    "name-Name", "#name-Name", "beginDate-Name", "endDate-Name",
    "#nameSearchModalSubmit", "nameSearchModal",
    'type="search"', 'name="searchTerm"', 'id="searchInput"',
    "SearchCriteria", "searchForm", "txtSearch",
]

def original_logic(content):
    start = time.time()
    # Simulate the logic in navigation.py
    has_input_elements = '<input' in content.lower()
    has_search_indicators = any(indicator.lower() in content.lower() for indicator in SEARCH_INDICATORS)
    end = time.time()
    return end - start, has_search_indicators

def optimized_logic(content):
    start = time.time()

    # Pre-computation (simulating module-level constant)
    indicators_lower = [s.lower() for s in SEARCH_INDICATORS]

    # Optimization: Call .lower() once
    content_lower = content.lower()

    has_input_elements = '<input' in content_lower
    has_search_indicators = any(indicator in content_lower for indicator in indicators_lower)

    end = time.time()
    return end - start, has_search_indicators

def test_navigation_benchmark():
    print(f"\nBenchmarking with content size: {len(PAGE_CONTENT)/1024:.2f} KB")
    print(f"Number of indicators: {len(SEARCH_INDICATORS)}")

    # Warmup
    original_logic(PAGE_CONTENT[:1000])
    optimized_logic(PAGE_CONTENT[:1000])

    # Run Benchmark (averaged over N runs)
    N = 100
    orig_total = 0
    opt_total = 0

    for _ in range(N):
        t, _ = original_logic(PAGE_CONTENT)
        orig_total += t

        t, _ = optimized_logic(PAGE_CONTENT)
        opt_total += t

    avg_orig = orig_total / N
    avg_opt = opt_total / N

    print(f"Original Time (avg):  {avg_orig*1000:.4f}ms")
    print(f"Optimized Time (avg): {avg_opt*1000:.4f}ms")

    speedup = avg_orig / avg_opt
    print(f"Speedup: {speedup:.2f}x")

    assert speedup > 1.5, f"Expected >1.5x speedup, but got {speedup:.2f}x"
