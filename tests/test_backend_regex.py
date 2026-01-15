import pytest
from backend.main import ROW_PATTERN, CSV_PATH_PATTERN

def test_row_pattern_logic():
    """Verify the logic of the regex used for extracting row counts."""
    # Using the actual compiled pattern from backend.main
    pattern = ROW_PATTERN

    assert pattern.search("Extracted 50 rows").group(1) == "50"
    assert pattern.search("Found 100 records").group(1) == "100"
    assert pattern.search("Saved 5 items").group(1) == "5"
    assert pattern.search("Saving 20 rows").group(1) == "20"
    assert pattern.search("Other text then Extracted 99 records").group(1) == "99"
    assert pattern.search("No match here") is None

def test_csv_path_pattern_logic():
    """Verify the logic of the regex used for extracting CSV paths."""
    # Using the actual compiled pattern from backend.main
    pattern = CSV_PATH_PATTERN

    assert pattern.search("saved to output/data/results.csv").group(1) == "output/data/results.csv"
    assert pattern.search("CSV saved: my_data.csv").group(1) == "my_data.csv"
    assert pattern.search("Saved results.csv").group(1) == "results.csv"
    assert pattern.search("Data saved to /tmp/file.csv").group(1) == "/tmp/file.csv"
    assert pattern.search("No match here") is None
