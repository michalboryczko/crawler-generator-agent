"""Log output implementations for structured logging.

Provides various output destinations for structured logs:
- JSONLinesOutput: JSON Lines format for log aggregators
- ConsoleOutput: Human-readable colored console output
- AsyncBufferedOutput: Async buffered wrapper for performance
- OpenTelemetryOutput: OpenTelemetry-compatible span output
"""

import json
import sys
import threading
from datetime import datetime
from pathlib import Path
from queue import Queue, Empty
from typing import TextIO

from .structured_logger import LogEntry, LogLevel, LogOutput


class JSONLinesOutput(LogOutput):
    """JSON Lines output for log aggregators and analysis.

    Writes each log entry as a single JSON line, suitable for:
    - Elasticsearch ingestion
    - Log aggregator pipelines
    - Analysis with jq or Python scripts
    """

    def __init__(self, file_path: Path | str | None = None, stream: TextIO | None = None):
        """Initialize JSON Lines output.

        Args:
            file_path: Path to output file (creates parent directories if needed)
            stream: Optional stream to write to (e.g., sys.stdout)
        """
        self.file_path = Path(file_path) if file_path else None
        self.stream = stream
        self._file: TextIO | None = None
        self._lock = threading.Lock()

        if self.file_path:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            self._file = open(self.file_path, "a", encoding="utf-8")

    def write(self, entry: LogEntry) -> None:
        """Write a log entry as JSON line."""
        line = json.dumps(entry.to_dict(), default=str, ensure_ascii=False) + "\n"
        with self._lock:
            if self._file:
                self._file.write(line)
            if self.stream:
                self.stream.write(line)

    def flush(self) -> None:
        """Flush buffered entries."""
        with self._lock:
            if self._file:
                self._file.flush()
            if self.stream:
                self.stream.flush()

    def close(self) -> None:
        """Close the output file."""
        with self._lock:
            if self._file:
                self._file.close()
                self._file = None


class ConsoleOutput(LogOutput):
    """Human-readable console output for development.

    Provides colored, formatted output suitable for terminal display.
    Includes trace IDs, event types, and metrics inline.
    """

    LEVEL_COLORS = {
        LogLevel.DEBUG: "\033[36m",    # Cyan
        LogLevel.INFO: "\033[32m",     # Green
        LogLevel.WARNING: "\033[33m",  # Yellow
        LogLevel.ERROR: "\033[31m",    # Red
        LogLevel.CRITICAL: "\033[35m", # Magenta
    }
    RESET = "\033[0m"
    DIM = "\033[2m"
    BOLD = "\033[1m"

    def __init__(self, stream: TextIO | None = None, color: bool = True):
        """Initialize console output.

        Args:
            stream: Output stream (defaults to sys.stdout)
            color: Whether to use ANSI color codes
        """
        self.stream = stream or sys.stdout
        self.color = color
        self._lock = threading.Lock()

    def write(self, entry: LogEntry) -> None:
        """Write a log entry in human-readable format."""
        color = self.LEVEL_COLORS.get(entry.level, "") if self.color else ""
        reset = self.RESET if self.color else ""
        dim = self.DIM if self.color else ""
        bold = self.BOLD if self.color else ""

        # Format: TIMESTAMP LEVEL [SPAN] EVENT_TYPE - MESSAGE
        timestamp = entry.timestamp.strftime("%H:%M:%S.%f")[:-3]
        span_short = entry.trace_context.span_id[-8:]

        line = (
            f"{dim}{timestamp}{reset} "
            f"{color}{entry.level.value:8}{reset} "
            f"{dim}[{span_short}]{reset} "
            f"{entry.event.event_type:30} "
            f"- {entry.message}"
        )

        # Add metrics if present
        metrics_parts = []
        if entry.metrics.duration_ms is not None:
            metrics_parts.append(f"{entry.metrics.duration_ms:.0f}ms")
        if entry.metrics.tokens_total is not None:
            metrics_parts.append(f"{entry.metrics.tokens_total} tok")
        if entry.metrics.estimated_cost_usd is not None:
            metrics_parts.append(f"${entry.metrics.estimated_cost_usd:.4f}")

        if metrics_parts:
            line += f" {dim}({', '.join(metrics_parts)}){reset}"

        with self._lock:
            self.stream.write(line + "\n")

    def flush(self) -> None:
        """Flush the output stream."""
        with self._lock:
            self.stream.flush()

    def close(self) -> None:
        """Close the output (no-op for stdout)."""
        pass


class AsyncBufferedOutput(LogOutput):
    """Async buffered output wrapper for performance.

    Wraps another LogOutput and buffers writes in a background thread.
    Useful for file outputs to avoid blocking on I/O.
    """

    def __init__(self, wrapped: LogOutput, buffer_size: int = 100, flush_interval: float = 1.0):
        """Initialize async buffered output.

        Args:
            wrapped: The underlying LogOutput to wrap
            buffer_size: Number of entries to buffer before flushing
            flush_interval: Max seconds to hold entries before flushing
        """
        self.wrapped = wrapped
        self.buffer_size = buffer_size
        self.flush_interval = flush_interval
        self.queue: Queue[LogEntry | None] = Queue()
        self._shutdown = False
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()

    def _worker(self) -> None:
        """Background worker that processes queued log entries."""
        buffer: list[LogEntry] = []

        while not self._shutdown:
            try:
                # Wait for entries with timeout for periodic flushing
                entry = self.queue.get(timeout=self.flush_interval)

                if entry is None:  # Shutdown signal
                    break

                buffer.append(entry)

                # Flush if buffer is full
                if len(buffer) >= self.buffer_size:
                    self._flush_buffer(buffer)
                    buffer.clear()

            except Empty:
                # Timeout - flush any pending entries
                if buffer:
                    self._flush_buffer(buffer)
                    buffer.clear()

        # Final flush on shutdown
        if buffer:
            self._flush_buffer(buffer)

    def _flush_buffer(self, buffer: list[LogEntry]) -> None:
        """Flush buffer to wrapped output."""
        for entry in buffer:
            try:
                self.wrapped.write(entry)
            except Exception:
                pass  # Don't let logging failures break the application
        self.wrapped.flush()

    def write(self, entry: LogEntry) -> None:
        """Queue a log entry for async writing."""
        if not self._shutdown:
            self.queue.put(entry)

    def flush(self) -> None:
        """Request flush (processed by worker)."""
        # Force flush by sending None (worker will flush buffer)
        pass

    def close(self) -> None:
        """Signal shutdown and wait for worker to finish."""
        self._shutdown = True
        self.queue.put(None)  # Signal shutdown
        self.thread.join(timeout=5.0)
        self.wrapped.close()


class OpenTelemetryOutput(LogOutput):
    """OpenTelemetry-compatible span output.

    Converts log entries to OpenTelemetry span format for distributed tracing.
    Can export to OTel Collector via OTLP protocol.
    """

    def __init__(
        self,
        service_name: str,
        endpoint: str | None = None,
        export_logs: bool = True,
        export_traces: bool = True,
    ):
        """Initialize OpenTelemetry output.

        Args:
            service_name: Name of the service for span attribution
            endpoint: OTLP endpoint (e.g., "http://localhost:4317")
            export_logs: Whether to export as OTLP logs
            export_traces: Whether to export as OTLP traces
        """
        self.service_name = service_name
        self.endpoint = endpoint
        self.export_logs = export_logs
        self.export_traces = export_traces

        # Store spans for potential trace export
        self._spans: list[dict] = []
        self._lock = threading.Lock()

        # In a full implementation, initialize OTLP exporters here:
        # from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        # self.exporter = OTLPSpanExporter(endpoint=endpoint)

    def write(self, entry: LogEntry) -> None:
        """Convert LogEntry to OTel span format."""
        span_data = {
            "traceId": entry.trace_context.trace_id.replace("trace_", ""),
            "spanId": entry.trace_context.span_id.replace("span_", ""),
            "parentSpanId": (
                entry.trace_context.parent_span_id.replace("span_", "")
                if entry.trace_context.parent_span_id else None
            ),
            "name": entry.event.name,
            "kind": "INTERNAL",
            "startTimeUnixNano": int(entry.timestamp.timestamp() * 1e9),
            "endTimeUnixNano": int(
                (entry.timestamp.timestamp() + (entry.metrics.duration_ms or 0) / 1000) * 1e9
            ),
            "attributes": [
                {"key": "service.name", "value": {"stringValue": self.service_name}},
                {"key": "event.category", "value": {"stringValue": entry.event.category.value}},
                {"key": "event.type", "value": {"stringValue": entry.event.event_type}},
                {"key": "log.level", "value": {"stringValue": entry.level.value}},
                {"key": "log.message", "value": {"stringValue": entry.message}},
                *[
                    {"key": f"context.{k}", "value": {"stringValue": str(v)}}
                    for k, v in entry.context.items()
                ],
                *[
                    {"key": f"tag.{tag}", "value": {"boolValue": True}}
                    for tag in entry.tags
                ],
            ],
            "status": {
                "code": "ERROR" if entry.level in (LogLevel.ERROR, LogLevel.CRITICAL) else "OK"
            },
        }

        # Add metrics as attributes
        if entry.metrics.duration_ms is not None:
            span_data["attributes"].append({
                "key": "metrics.duration_ms",
                "value": {"doubleValue": entry.metrics.duration_ms}
            })
        if entry.metrics.tokens_total is not None:
            span_data["attributes"].append({
                "key": "metrics.tokens_total",
                "value": {"intValue": entry.metrics.tokens_total}
            })
        if entry.metrics.estimated_cost_usd is not None:
            span_data["attributes"].append({
                "key": "metrics.estimated_cost_usd",
                "value": {"doubleValue": entry.metrics.estimated_cost_usd}
            })

        with self._lock:
            self._spans.append(span_data)

        # In a full implementation, export to OTLP endpoint:
        # self.exporter.export([span_data])

    def flush(self) -> None:
        """Flush pending spans to exporter."""
        # In a full implementation, export buffered spans
        pass

    def close(self) -> None:
        """Close the exporter."""
        # In a full implementation, shutdown the exporter
        pass

    def get_spans(self) -> list[dict]:
        """Get collected spans (for testing/debugging)."""
        with self._lock:
            return list(self._spans)


class CompositeOutput(LogOutput):
    """Combines multiple outputs into one.

    Writes to all configured outputs, useful for simultaneously logging
    to console and file.
    """

    def __init__(self, outputs: list[LogOutput]):
        """Initialize composite output.

        Args:
            outputs: List of LogOutput instances to write to
        """
        self.outputs = outputs

    def write(self, entry: LogEntry) -> None:
        """Write to all outputs."""
        for output in self.outputs:
            try:
                output.write(entry)
            except Exception:
                pass  # Don't let one output failure affect others

    def flush(self) -> None:
        """Flush all outputs."""
        for output in self.outputs:
            try:
                output.flush()
            except Exception:
                pass

    def close(self) -> None:
        """Close all outputs."""
        for output in self.outputs:
            try:
                output.close()
            except Exception:
                pass
