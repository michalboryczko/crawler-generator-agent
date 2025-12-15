"""Output implementations for observability.

This module provides local output targets (console).
For backend integration, see handlers.py.
"""

import contextlib
import sys
import threading
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, ClassVar, TextIO

from .schema import LogRecord


class LogOutput(ABC):
    """Abstract base for local log outputs (console, etc.)."""

    @abstractmethod
    def write_log(self, record: LogRecord) -> None:
        """Write a log record."""
        pass

    def write_trace_event(self, event: dict[str, Any]) -> None:  # noqa: B027
        """Write a trace event (optional default implementation)."""
        pass

    def flush(self) -> None:  # noqa: B027
        """Flush buffered data (optional default implementation)."""
        pass

    def close(self) -> None:  # noqa: B027
        """Close the output (optional default implementation)."""
        pass


class ConsoleOutput(LogOutput):
    """Human-readable console output with optional colors.

    Formats log records for easy reading in terminal.
    Thread-safe for concurrent writes.
    """

    LEVEL_COLORS: ClassVar[dict[str, str]] = {
        "DEBUG": "\033[36m",    # Cyan
        "INFO": "\033[32m",     # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",    # Red
        "CRITICAL": "\033[35m", # Magenta
    }
    RESET: ClassVar[str] = "\033[0m"
    DIM: ClassVar[str] = "\033[2m"
    BOLD: ClassVar[str] = "\033[1m"

    def __init__(self, stream: TextIO | None = None, color: bool = True):
        """Initialize console output.

        Args:
            stream: Output stream (default: sys.stdout).
            color: Whether to use ANSI colors.
        """
        self.stream = stream or sys.stdout
        self.color = color and hasattr(self.stream, 'isatty') and self.stream.isatty()
        self._lock = threading.Lock()

    def write_log(self, record: LogRecord) -> None:
        """Write log record to console."""
        color = self.LEVEL_COLORS.get(record.level, "") if self.color else ""
        reset = self.RESET if self.color else ""
        dim = self.DIM if self.color else ""
        bold = self.BOLD if self.color else ""

        # Format timestamp
        if isinstance(record.timestamp, datetime):
            timestamp = record.timestamp.strftime("%H:%M:%S.%f")[:-3]
        else:
            timestamp = str(record.timestamp)[:12]

        # Short span ID for readability
        span_short = record.span_id[-8:] if record.span_id else "--------"

        # Build the log line
        line = (
            f"{dim}{timestamp}{reset} "
            f"{color}{record.level:8}{reset} "
            f"{dim}[{span_short}]{reset} "
            f"{bold}{record.event:30}{reset} "
            f"- {record.component_name}"
        )

        # Add triggered_by if not direct call
        if record.triggered_by and record.triggered_by != "direct_call":
            line += f" {dim}(from {record.triggered_by}){reset}"

        # Add key metrics inline
        if record.metrics.get("duration_ms"):
            duration = record.metrics['duration_ms']
            line += f" {dim}({duration:.0f}ms){reset}"

        # Add error indicator
        if record.level == "ERROR" and record.data.get("error_message"):
            error_msg = record.data["error_message"]
            if len(error_msg) > 80:
                error_msg = error_msg[:77] + "..."
            line += f"\n  {color}└─ {error_msg}{reset}"

        with self._lock, contextlib.suppress(Exception):
            self.stream.write(line + "\n")

    def write_trace_event(self, event: dict[str, Any]) -> None:
        """Write trace event to console (simplified format)."""
        if not self.color:
            dim = ""
            reset = ""
        else:
            dim = self.DIM
            reset = self.RESET

        name = event.get("name", "unknown")
        span_id = event.get("span_id", "")[-8:]

        line = f"{dim}    TRACE [{span_id}] {name}{reset}"

        with self._lock, contextlib.suppress(Exception):
            self.stream.write(line + "\n")

    def flush(self) -> None:
        """Flush the output stream."""
        with self._lock, contextlib.suppress(Exception):
            self.stream.flush()

    def close(self) -> None:
        """Close console output (no-op for stdout)."""
        pass


class NullOutput(LogOutput):
    """Null output that discards all data."""

    def write_log(self, record: LogRecord) -> None:
        pass

    def write_trace_event(self, event: dict[str, Any]) -> None:
        pass
