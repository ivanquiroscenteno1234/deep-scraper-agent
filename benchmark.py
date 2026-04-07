import timeit

page_content = "<html>" + "a" * 100000 + "<input> some content here "#searchonname" </html>"
search_indicators = [
    "#SearchOnName", "SearchOnName", "#RecordDateFrom", "#RecordDateTo",
    "name-Name", "#name-Name", "beginDate-Name", "endDate-Name",
    "#nameSearchModalSubmit", "nameSearchModal",
    'type="search"', 'name="searchTerm"', 'id="searchInput"',
    "SearchCriteria", "searchForm", "txtSearch",
]

def unoptimized():
    has_input_elements = '<input' in page_content.lower()
    has_search_indicators = any(indicator.lower() in page_content.lower() for indicator in search_indicators)
    return has_input_elements, has_search_indicators

def optimized():
    page_content_lower = page_content.lower()
    has_input_elements = '<input' in page_content_lower
    # Pre-lowering indicators would be done once at module level, but let's just do it here to simulate
    has_search_indicators = any(indicator.lower() in page_content_lower for indicator in search_indicators)
    return has_input_elements, has_search_indicators

_SEARCH_INDICATORS_LOWER = [i.lower() for i in search_indicators]

def fully_optimized():
    page_content_lower = page_content.lower()
    has_input_elements = '<input' in page_content_lower
    has_search_indicators = any(indicator in page_content_lower for indicator in _SEARCH_INDICATORS_LOWER)
    return has_input_elements, has_search_indicators

n = 1000
unopt_time = timeit.timeit(unoptimized, number=n)
opt_time = timeit.timeit(optimized, number=n)
full_opt_time = timeit.timeit(fully_optimized, number=n)

print(f"Unoptimized: {unopt_time:.4f}s")
print(f"Optimized (hoist lower): {opt_time:.4f}s")
print(f"Fully optimized (module level lists): {full_opt_time:.4f}s")
