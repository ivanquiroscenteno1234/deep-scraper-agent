import os

def pytest_configure():
    os.environ["GOOGLE_API_KEY"] = "dummy_api_key_for_tests"
    os.environ["GEMINI_MODEL"] = "dummy_model"
