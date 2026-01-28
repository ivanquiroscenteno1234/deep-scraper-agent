
import timeit
import time

def test_perf_optimization():
    page_content = "x" * 50000 + "searchcriteria" + "y" * 50000

    search_indicators = [
        "#SearchOnName", "SearchOnName", "#RecordDateFrom", "#RecordDateTo",
        "name-Name", "#name-Name", "beginDate-Name", "endDate-Name",
        "#nameSearchModalSubmit", "nameSearchModal",
        'type="search"', 'name="searchTerm"', 'id="searchInput"',
        "SearchCriteria", "searchForm", "txtSearch",
    ]

    # Original
    def original():
        return any(indicator.lower() in page_content.lower() for indicator in search_indicators)

    # Optimized
    _SEARCH_INDICATORS_LOWER = [s.lower() for s in search_indicators]
    def optimized():
        page_content_lower = page_content.lower()
        return any(indicator in page_content_lower for indicator in _SEARCH_INDICATORS_LOWER)

    # Warmup
    original()
    optimized()

    # Measure
    t_original = timeit.timeit(original, number=100)
    t_optimized = timeit.timeit(optimized, number=100)

    print(f"Original: {t_original:.4f}s")
    print(f"Optimized: {t_optimized:.4f}s")
    print(f"Speedup: {t_original / t_optimized:.2f}x")

    assert t_optimized < t_original, "Optimization should be faster"

if __name__ == "__main__":
    test_perf_optimization()
