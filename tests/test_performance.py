
import timeit
import pytest

def test_performance_optimization():
    # Simulate large page content (approx 100KB)
    page_content = "<html><body>" + "Some random content that repeats " * 2000 + "</body></html>"
    # Make sure some indicators are present so we don't just fail fast every time (though fail fast is also a valid case)
    # Adding one indicator at the end
    page_content += " SearchCriteria "

    search_indicators = [
        "#SearchOnName", "SearchOnName", "#RecordDateFrom", "#RecordDateTo",
        "name-Name", "#name-Name", "beginDate-Name", "endDate-Name",
        "#nameSearchModalSubmit", "nameSearchModal",
        'type="search"', 'name="searchTerm"', 'id="searchInput"',
        "SearchCriteria", "searchForm", "txtSearch",
    ]

    # Original inefficient implementation
    def original_implementation():
        has_input_elements = '<input' in page_content.lower()
        has_search_indicators = any(indicator.lower() in page_content.lower() for indicator in search_indicators)
        return has_input_elements and has_search_indicators

    # Optimized implementation
    def optimized_implementation():
        page_content_lower = page_content.lower()
        has_input_elements = '<input' in page_content_lower
        has_search_indicators = any(indicator.lower() in page_content_lower for indicator in search_indicators)
        return has_input_elements and has_search_indicators

    # Measure time
    iterations = 100
    original_time = timeit.timeit(original_implementation, number=iterations)
    optimized_time = timeit.timeit(optimized_implementation, number=iterations)

    print(f"\nOriginal time ({iterations} runs): {original_time:.4f}s")
    print(f"Optimized time ({iterations} runs): {optimized_time:.4f}s")
    print(f"Speedup: {original_time / optimized_time:.2f}x")

    assert optimized_time < original_time
