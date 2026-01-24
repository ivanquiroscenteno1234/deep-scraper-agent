import time
import timeit

# Original logic simulation
def original_check(page_content):
    search_indicators = [
        # AcclaimWeb patterns
        "#SearchOnName", "SearchOnName", "#RecordDateFrom", "#RecordDateTo",
        # Landmark Web patterns (Flagler, etc.)
        "name-Name", "#name-Name", "beginDate-Name", "endDate-Name",
        "#nameSearchModalSubmit", "nameSearchModal",
        # Generic patterns
        'type="search"', 'name="searchTerm"', 'id="searchInput"',
        "SearchCriteria", "searchForm", "txtSearch",
    ]
    # Simulate the check
    has_search_indicators = any(indicator.lower() in page_content.lower() for indicator in search_indicators)
    return has_search_indicators

# Optimized logic simulation
_SEARCH_INDICATORS = [
    # AcclaimWeb patterns
    "#SearchOnName", "SearchOnName", "#RecordDateFrom", "#RecordDateTo",
    # Landmark Web patterns (Flagler, etc.)
    "name-Name", "#name-Name", "beginDate-Name", "endDate-Name",
    "#nameSearchModalSubmit", "nameSearchModal",
    # Generic patterns
    'type="search"', 'name="searchTerm"', 'id="searchInput"',
    "SearchCriteria", "searchForm", "txtSearch",
]
_SEARCH_INDICATORS_LOWER = [ind.lower() for ind in _SEARCH_INDICATORS]

def optimized_check(page_content):
    # Hoist lower()
    page_content_lower = page_content.lower()
    has_search_indicators = any(indicator in page_content_lower for indicator in _SEARCH_INDICATORS_LOWER)
    return has_search_indicators

if __name__ == "__main__":
    # Create a large page content string (100KB)
    # Include one indicator at the very end to force worst-case traversal
    # Or include none to force full traversal of list
    page_content = "<div>Some random content</div>" * 5000 + "<div>txtSearch</div>"

    print(f"Page content length: {len(page_content)}")

    # Verify correctness
    assert original_check(page_content) == optimized_check(page_content)
    print("Correctness check passed.")

    # Benchmark
    iterations = 1000

    start = time.time()
    for _ in range(iterations):
        original_check(page_content)
    original_time = time.time() - start

    start = time.time()
    for _ in range(iterations):
        optimized_check(page_content)
    optimized_time = time.time() - start

    print(f"Original time ({iterations} runs): {original_time:.4f}s")
    print(f"Optimized time ({iterations} runs): {optimized_time:.4f}s")
    print(f"Speedup: {original_time / optimized_time:.2f}x")
