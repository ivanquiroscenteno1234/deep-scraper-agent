"""
script_runner.py — Subprocess execution + CSV parsing service.

Extracted from backend/main.py to keep route handlers thin.
"""

import csv
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ScriptResult:
    success: bool
    row_count: int = 0
    data: List[Dict[str, Any]] = field(default_factory=list)
    stdout: str = ""
    stderr: str = ""
    error: Optional[str] = None


def _resolve_csv(stdout: str, output_dir: str) -> List[Dict[str, Any]]:
    """
    Locate the CSV file produced by a script run and parse it.

    Strategy:
    1. Parse a path from stdout lines like "saved to /path/to/file.csv"
    2. Resolve relative to output_dir
    3. Fall back to the most-recently-modified .csv in output_dir
    """
    potential_paths: List[str] = []

    csv_path_match = re.search(
        r"(?:saved to|CSV saved:|to|Saved)\s+([^\s]+\.csv)",
        stdout,
        re.IGNORECASE,
    )
    if csv_path_match:
        csv_file = csv_path_match.group(1).strip()
        potential_paths.append(csv_file)
        potential_paths.append(os.path.join(output_dir, os.path.basename(csv_file)))

    # Fallback: most recent CSV in output_dir
    if os.path.isdir(output_dir):
        csv_files = sorted(
            [f for f in os.listdir(output_dir) if f.endswith(".csv")],
            key=lambda f: os.path.getmtime(os.path.join(output_dir, f)),
            reverse=True,
        )
        if csv_files:
            potential_paths.append(os.path.join(output_dir, csv_files[0]))

    for path in potential_paths:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return list(csv.DictReader(f))
            except Exception:
                continue

    return []


def run_script(
    script_path: str,
    search_query: str,
    start_date: str,
    end_date: str,
    *,
    cwd: Optional[str] = None,
    output_dir: Optional[str] = None,
    timeout: int = 180,
) -> ScriptResult:
    """
    Execute a generated scraper script as a subprocess and return structured results.

    Args:
        script_path: Absolute path to the .py script.
        search_query: Free-text query passed as first CLI argument.
        start_date: Date range start (MM/DD/YYYY).
        end_date: Date range end (MM/DD/YYYY).
        cwd: Working directory for the subprocess (defaults to script directory).
        output_dir: Directory to search for CSVs (defaults to <cwd>/output/data).
        timeout: Maximum seconds to wait for the subprocess.

    Returns:
        ScriptResult with success flag, row count, parsed data, and raw output.
    """
    if not os.path.exists(script_path):
        return ScriptResult(success=False, error="Script file not found")

    run_cwd = cwd or os.path.dirname(script_path)
    data_dir = output_dir or os.path.join(run_cwd, "output", "data")

    try:
        proc = subprocess.run(
            [sys.executable, script_path, search_query, start_date, end_date],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=run_cwd,
        )

        stdout_upper = proc.stdout.upper()
        is_success = (
            "SUCCESS" in stdout_upper
            or "[SUCCESS]" in stdout_upper
            or "[OK]" in stdout_upper
        )

        row_count = 0
        row_match = re.search(
            r"(?:Extracted|Found|Saved|Saving)\s+(\d+)\s+(?:rows|records|items)",
            proc.stdout,
            re.IGNORECASE,
        )
        if row_match:
            row_count = int(row_match.group(1))

        data = _resolve_csv(proc.stdout, data_dir)

        if is_success or data:
            return ScriptResult(
                success=True,
                row_count=len(data) if data else row_count,
                data=data,
                stdout=proc.stdout,
                stderr=proc.stderr,
            )

        return ScriptResult(
            success=False,
            error="Script execution failed or produced no valid data output",
            stdout=proc.stdout,
            stderr=proc.stderr,
        )

    except Exception as exc:
        return ScriptResult(success=False, error=str(exc))
