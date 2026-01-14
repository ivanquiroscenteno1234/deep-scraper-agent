
import pytest
import time
import timeit

# Replicating the logic from deep_scraper/graph/nodes/navigation.py
def original_check(page_content, search_indicators):
    has_input_elements = '<input' in page_content.lower()
    has_search_indicators = any(indicator.lower() in page_content.lower() for indicator in search_indicators)
    return has_input_elements, has_search_indicators

def optimized_check(page_content, search_indicators):
    page_content_lower = page_content.lower()
    has_input_elements = '<input' in page_content_lower
    has_search_indicators = any(indicator.lower() in page_content_lower for indicator in search_indicators)
    return has_input_elements, has_search_indicators

def test_benchmark_search_indicators():
    # Setup
    search_indicators = [
        "#SearchOnName", "SearchOnName", "#RecordDateFrom", "#RecordDateTo",
        "name-Name", "#name-Name", "beginDate-Name", "endDate-Name",
        "#nameSearchModalSubmit", "nameSearchModal",
        'type="search"', 'name="searchTerm"', 'id="searchInput"',
        "SearchCriteria", "searchForm", "txtSearch",
    ]

    # 100KB string with match at the end to force full scan
    page_content = "x" * 100000 + "SearchOnName" + "x" * 1000 + "<input type='text'>"

    # Correctness check
    orig_res = original_check(page_content, search_indicators)
    opt_res = optimized_check(page_content, search_indicators)

    assert orig_res == opt_res
    assert orig_res == (True, True)

    # Benchmark
    iterations = 1000
    t_orig = timeit.timeit(lambda: original_check(page_content, search_indicators), number=iterations)
    t_opt = timeit.timeit(lambda: optimized_check(page_content, search_indicators), number=iterations)

    print(f"\nOriginal time: {t_orig:.4f}s")
    print(f"Optimized time: {t_opt:.4f}s")
    print(f"Improvement: {(t_orig - t_opt) / t_orig * 100:.2f}%")

    # Assert improvement (allow some margin for noise, but this should be significant)
    # We expect at least 10% improvement
    assert t_opt < t_orig * 0.9, "Optimization should be at least 10% faster"

if __name__ == "__main__":
    pytest.main([__file__])
