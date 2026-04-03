import timeit

def test_original():
    page_content = "some long string " * 5000 + "searchform"
    search_indicators = ["#SearchOnName", "SearchOnName", "#RecordDateFrom", "#RecordDateTo", "name-Name", "#name-Name", "beginDate-Name", "endDate-Name", "#nameSearchModalSubmit", "nameSearchModal", 'type="search"', 'name="searchTerm"', 'id="searchInput"', "SearchCriteria", "searchForm", "txtSearch"]
    return any(indicator.lower() in page_content.lower() for indicator in search_indicators)

def test_optimized():
    page_content = "some long string " * 5000 + "searchform"
    search_indicators = ["#SearchOnName", "SearchOnName", "#RecordDateFrom", "#RecordDateTo", "name-Name", "#name-Name", "beginDate-Name", "endDate-Name", "#nameSearchModalSubmit", "nameSearchModal", 'type="search"', 'name="searchTerm"', 'id="searchInput"', "SearchCriteria", "searchForm", "txtSearch"]
    page_content_lower = page_content.lower()
    return any(indicator.lower() in page_content_lower for indicator in search_indicators)

print("Original:", timeit.timeit(test_original, number=1000))
print("Optimized:", timeit.timeit(test_optimized, number=1000))
