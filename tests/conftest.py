import os
import pytest

# Set dummy env vars for testing
os.environ["GOOGLE_API_KEY"] = "dummy_key"
os.environ["GEMINI_MODEL"] = "gemini-1.5-flash"
