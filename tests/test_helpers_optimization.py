import sys
import os
from unittest.mock import MagicMock

# Inject dummy env vars
os.environ["GOOGLE_API_KEY"] = "dummy"
os.environ["GEMINI_MODEL"] = "dummy"

# Mock necessary modules to avoid import side effects
sys.modules['mcp'] = MagicMock()
sys.modules['mcp.client'] = MagicMock()
sys.modules['mcp.client.stdio'] = MagicMock()
sys.modules['mcp.client.sse'] = MagicMock()
sys.modules['pydantic'] = MagicMock()
sys.modules['langchain_core'] = MagicMock()
sys.modules['langchain_core.messages'] = MagicMock()
sys.modules['langchain_google_genai'] = MagicMock()
sys.modules['langgraph'] = MagicMock()
sys.modules['langgraph.graph'] = MagicMock()
sys.modules['bs4'] = MagicMock()
sys.modules['dotenv'] = MagicMock()

from deep_scraper.utils.helpers import get_site_name_from_url

def test_get_site_name_from_url():
    # Test cases: (input_url, expected_output)
    test_cases = [
        ("https://www.example.com/path", "example"),
        ("https://www2.example.org", "example"),
        ("https://apps.example.net", "example"),
        ("https://portal.example.gov", "example"),
        ("https://vaclmweb1.example.edu", "example"),
        ("https://www.apps.example.com", "example"),  # Both removed because 'www.' is before 'apps.' in the tuple
        ("https://portal.www2.example.com", "www2"),  # Only 'portal.' removed because 'portal.' is after 'www2.' in the tuple (faithful to original)
        ("https://example.com", "example"),
        ("https://sub.example.com", "sub"),
        ("https://www.my-site.com", "mysite"),
        ("https://my_site123.com", "mysite123"),
        ("", "unknown"),
        ("not-a-url", "unknown"),
    ]

    for url, expected in test_cases:
        result = get_site_name_from_url(url)
        print(f"URL: {url:<35} | Expected: {expected:<10} | Got: {result:<10}")
        assert result == expected

if __name__ == "__main__":
    try:
        test_get_site_name_from_url()
        print("\n✅ All tests passed!")
    except AssertionError as e:
        print("\n❌ Test failed!")
        sys.exit(1)
