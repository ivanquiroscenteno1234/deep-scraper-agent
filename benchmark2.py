import timeit

search_indicators = [
    "#SearchOnName", "SearchOnName", "#RecordDateFrom", "#RecordDateTo",
    "name-Name", "#name-Name", "beginDate-Name", "endDate-Name",
    "#nameSearchModalSubmit", "nameSearchModal",
    'type="search"', 'name="searchTerm"', 'id="searchInput"',
    "SearchCriteria", "searchForm", "txtSearch",
]
_SEARCH_INDICATORS_LOWER = [i.lower() for i in search_indicators]
page_content = "<html>" + "a" * 100000 + " </html>" # Worst case, not found

def unoptimized():
    has_search_indicators = any(indicator.lower() in page_content.lower() for indicator in search_indicators)

def fully_optimized():
    page_content_lower = page_content.lower()
    has_search_indicators = any(indicator in page_content_lower for indicator in _SEARCH_INDICATORS_LOWER)

n = 1000
unopt_time = timeit.timeit(unoptimized, number=n)
full_opt_time = timeit.timeit(fully_optimized, number=n)

print(f"Unoptimized: {unopt_time:.4f}s")
print(f"Fully optimized: {full_opt_time:.4f}s")
