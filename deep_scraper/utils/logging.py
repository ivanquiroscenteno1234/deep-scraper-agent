"""
Structured logging utility for Deep Scraper Agent nodes.

Extracted from deep_scraper/utils/helpers.py.
"""

import datetime
from typing import List


class StructuredLogger:
    """
    Structured logger that captures logs with timestamps and context.

    Stores logs in a list for inclusion in agent state while also
    printing to console for real-time visibility.
    """

    def __init__(self, node_name: str):
        self.node_name = node_name
        self.logs: List[str] = []

    def _format(self, level: str, message: str) -> str:
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        return f"[{timestamp}] [{self.node_name}] {level}: {message}"

    def info(self, message: str) -> None:
        formatted = self._format("INFO", message)
        print(formatted)
        self.logs.append(formatted)

    def warning(self, message: str) -> None:
        formatted = self._format("WARN", message)
        print(f"⚠️ {formatted}")
        self.logs.append(formatted)

    def error(self, message: str) -> None:
        formatted = self._format("ERROR", message)
        print(f"❌ {formatted}")
        self.logs.append(formatted)

    def success(self, message: str) -> None:
        formatted = self._format("OK", message)
        print(f"✅ {formatted}")
        self.logs.append(formatted)

    def debug(self, message: str) -> None:
        formatted = self._format("DEBUG", message)
        # Debug only to console, not stored
        print(f"🔍 {formatted}")

    def get_logs(self) -> List[str]:
        """Get all captured logs."""
        return self.logs
