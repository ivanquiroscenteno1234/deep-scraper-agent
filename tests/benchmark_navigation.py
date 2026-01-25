
import timeit
import random
import string

# Mock data
SEARCH_INDICATORS = [
    "#SearchOnName", "SearchOnName", "#RecordDateFrom", "#RecordDateTo",
    "name-Name", "#name-Name", "beginDate-Name", "endDate-Name",
    "#nameSearchModalSubmit", "nameSearchModal",
    'type="search"', 'name="searchTerm"', 'id="searchInput"',
    "SearchCriteria", "searchForm", "txtSearch",
]

# Create a large random string (100k chars)
def generate_random_html(size=100000):
    return ''.join(random.choices(string.ascii_letters + string.digits + " <>=/\"\'", k=size))

PAGE_CONTENT = generate_random_html()

# Ensure we don't accidentally match early to test worst case,
# or match late to test typical case.
# Let's append a match at the very end to force full traversal if using generator logic naively.
PAGE_CONTENT += ' <input type="search"> '

def original_logic():
    page_content = PAGE_CONTENT
    search_indicators = SEARCH_INDICATORS

    # Original logic from navigation.py
    has_input_elements = '<input' in page_content.lower()
    has_search_indicators = any(indicator.lower() in page_content.lower() for indicator in search_indicators)
    return has_input_elements and has_search_indicators

_SEARCH_INDICATORS_LOWER = [s.lower() for s in SEARCH_INDICATORS]

def optimized_logic():
    page_content = PAGE_CONTENT

    # Optimized logic
    page_content_lower = page_content.lower()
    has_input_elements = '<input' in page_content_lower
    # Hoisted lower() and pre-compiled list
    has_search_indicators = any(indicator in page_content_lower for indicator in _SEARCH_INDICATORS_LOWER)
    return has_input_elements and has_search_indicators

if __name__ == "__main__":
    print("Benchmarking...")

    iterations = 100

    t_orig = timeit.timeit(original_logic, number=iterations)
    print(f"Original logic ({iterations} runs): {t_orig:.4f}s")

    t_opt = timeit.timeit(optimized_logic, number=iterations)
    print(f"Optimized logic ({iterations} runs): {t_opt:.4f}s")

    speedup = t_orig / t_opt
    print(f"Speedup: {speedup:.2f}x")
