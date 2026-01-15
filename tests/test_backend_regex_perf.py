
import re
import time
import asyncio
import pytest

# Mock implementation of the logic in backend/main.py BEFORE optimization
class MockBackendExecutor:
    def __init__(self):
        pass

    def execute_script_logic(self, stdout_text):
        import re
        # 1. Flexible Success Detection
        stdout_upper = stdout_text.upper()

        # 2. Extract Row Count
        row_count = 0
        row_match = re.search(r'(?:Extracted|Found|Saved|Saving)\s+(\d+)\s+(?:rows|records|items)', stdout_text, re.IGNORECASE)
        if row_match:
            row_count = int(row_match.group(1))

        # 3. CSV File Resolution
        csv_file = None
        # Try finding path in stdout - support multiple formats
        csv_path_match = re.search(r'(?:saved to|CSV saved:|to|Saved)\s+([^\s]+\.csv)', stdout_text, re.IGNORECASE)
        if csv_path_match:
            csv_file = csv_path_match.group(1).strip()

        return row_count, csv_file

# Optimized implementation (mocking module-level compilation)
ROW_PATTERN = re.compile(r'(?:Extracted|Found|Saved|Saving)\s+(\d+)\s+(?:rows|records|items)', re.IGNORECASE)
CSV_PATH_PATTERN = re.compile(r'(?:saved to|CSV saved:|to|Saved)\s+([^\s]+\.csv)', re.IGNORECASE)

class OptimizedBackendExecutor:
    def __init__(self):
        pass

    def execute_script_logic(self, stdout_text):
        # 1. Flexible Success Detection
        stdout_upper = stdout_text.upper()

        # 2. Extract Row Count
        row_count = 0
        row_match = ROW_PATTERN.search(stdout_text)
        if row_match:
            row_count = int(row_match.group(1))

        # 3. CSV File Resolution
        csv_file = None
        csv_path_match = CSV_PATH_PATTERN.search(stdout_text)
        if csv_path_match:
            csv_file = csv_path_match.group(1).strip()

        return row_count, csv_file

def generate_large_log():
    # Simulate a large log file output from a scraper
    lines = []
    lines.append("Starting scraper...")
    for i in range(100):
        lines.append(f"Processing row {i}...")
    lines.append("Found 500 rows.")
    lines.append("Saved to /tmp/output.csv")
    lines.append("[SUCCESS] processing complete.")
    return "\n".join(lines)

def test_regex_performance():
    log_content = generate_large_log()
    iterations = 50000

    current = MockBackendExecutor()
    optimized = OptimizedBackendExecutor()

    # Measure Current
    start_time = time.time()
    for _ in range(iterations):
        current.execute_script_logic(log_content)
    current_duration = time.time() - start_time

    # Measure Optimized
    start_time = time.time()
    for _ in range(iterations):
        optimized.execute_script_logic(log_content)
    optimized_duration = time.time() - start_time

    print(f"\nPerformance Benchmark (iterations={iterations}):")
    print(f"Current Implementation (imports/compilation inside loop): {current_duration:.4f}s")
    print(f"Optimized Implementation (module-level constants): {optimized_duration:.4f}s")
    improvement = (current_duration - optimized_duration) / current_duration * 100
    print(f"Improvement: {improvement:.2f}%")

    assert optimized_duration < current_duration, "Optimized version should be faster"

if __name__ == "__main__":
    test_regex_performance()
