import os
import pytest

# Set dummy environment variables before any tests run
# This prevents ImportErrors when deep_scraper.graph.nodes.config is imported
os.environ["GOOGLE_API_KEY"] = "dummy_key_for_testing"
os.environ["GEMINI_MODEL"] = "dummy_model"
