"""Log output implementations for structured logging.

Provides various output destinations for structured logs:
- JSONLinesOutput: JSON Lines format for log aggregators
- ConsoleOutput: Human-readable colored console output
- AsyncBufferedOutput: Async buffered wrapper for performance
- OpenTelemetryOutput: OpenTelemetry-compatible span output via OTLP
"""

import json
import logging
import sys
import threading
from datetime import datetime
from pathlib import Path
from queue import Queue, Empty
from typing import TextIO

from .structured_logger import LogEntry, LogLevel, LogOutput

# OpenTelemetry imports - optional, gracefully degrade if not installed
try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider, ReadableSpan
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter, SpanExportResult
    from opentelemetry.sdk.resources import Resource, SERVICE_NAME
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.trace import SpanKind, Status, StatusCode
    from opentelemetry.trace.span import TraceFlags
    from opentelemetry.sdk.trace import Span
    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False
    TracerProvider = None
    OTLPSpanExporter = None

_otel_logger = logging.getLogger(__name__)


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
    """OpenTelemetry-compatible span output via OTLP protocol.

    Converts log entries to OpenTelemetry spans and exports them to an OTel Collector
    using the OTLP gRPC protocol. Supports distributed tracing with Jaeger.

    Requires opentelemetry packages:
        pip install opentelemetry-sdk opentelemetry-exporter-otlp-proto-grpc
    """

    def __init__(
        self,
        service_name: str,
        endpoint: str | None = None,
        export_logs: bool = True,
        export_traces: bool = True,
        insecure: bool = True,
    ):
        """Initialize OpenTelemetry output.

        Args:
            service_name: Name of the service for span attribution
            endpoint: OTLP endpoint (e.g., "localhost:4317" for gRPC)
            export_logs: Whether to export as OTLP logs (not yet implemented)
            export_traces: Whether to export as OTLP traces
            insecure: Whether to use insecure (non-TLS) connection
        """
        self.service_name = service_name
        self.endpoint = endpoint or "localhost:4317"
        self.export_logs = export_logs
        self.export_traces = export_traces
        self.insecure = insecure

        # Store spans for debugging
        self._spans: list[dict] = []
        self._lock = threading.Lock()

        # Track active spans by span_id for proper lifecycle management
        self._active_spans: dict[str, "Span"] = {}

        # Initialize OTel if available
        self._initialized = False
        self._tracer = None
        self._provider = None

        if not OTEL_AVAILABLE:
            _otel_logger.warning(
                "OpenTelemetry packages not installed. "
                "Install with: pip install opentelemetry-sdk opentelemetry-exporter-otlp-proto-grpc"
            )
            return

        try:
            self._initialize_otel()
            self._initialized = True
            _otel_logger.info(f"OpenTelemetry initialized, exporting to {self.endpoint}")
        except Exception as e:
            _otel_logger.error(f"Failed to initialize OpenTelemetry: {e}")

    def _initialize_otel(self) -> None:
        """Initialize OpenTelemetry SDK and exporters."""
        # Create resource with service name
        resource = Resource.create({
            SERVICE_NAME: self.service_name,
            "service.version": "0.1.0",
            "deployment.environment": "development",
        })

        # Create tracer provider
        self._provider = TracerProvider(resource=resource)

        # Create OTLP exporter
        otlp_exporter = OTLPSpanExporter(
            endpoint=self.endpoint,
            insecure=self.insecure,
        )

        # Add batch processor for efficient exporting
        span_processor = BatchSpanProcessor(
            otlp_exporter,
            max_queue_size=2048,
            max_export_batch_size=512,
            schedule_delay_millis=5000,
        )
        self._provider.add_span_processor(span_processor)

        # Set as global tracer provider
        trace.set_tracer_provider(self._provider)

        # Get tracer for this service
        self._tracer = trace.get_tracer(
            self.service_name,
            schema_url="https://opentelemetry.io/schemas/1.21.0",
        )

    def _convert_trace_id(self, trace_id: str) -> int:
        """Convert our trace_id format to OTel 128-bit trace ID."""
        # Remove prefix and convert to integer
        clean_id = trace_id.replace("trace_", "").replace("-", "")
        # Pad or truncate to 32 hex chars (128 bits)
        clean_id = clean_id[:32].ljust(32, "0")
        return int(clean_id, 16)

    def _convert_span_id(self, span_id: str) -> int:
        """Convert our span_id format to OTel 64-bit span ID."""
        # Remove prefix and convert to integer
        clean_id = span_id.replace("span_", "").replace("-", "")
        # Pad or truncate to 16 hex chars (64 bits)
        clean_id = clean_id[:16].ljust(16, "0")
        return int(clean_id, 16)

    def write(self, entry: LogEntry) -> None:
        """Convert LogEntry to OTel span and export."""
        # Always store locally for debugging
        span_data = self._create_span_data(entry)
        with self._lock:
            self._spans.append(span_data)

        # Export via OTLP if initialized
        if not self._initialized or not self._tracer:
            return

        try:
            self._export_as_span(entry)
        except Exception as e:
            _otel_logger.debug(f"Failed to export span: {e}")

    def _create_span_data(self, entry: LogEntry) -> dict:
        """Create span data dict for local storage/debugging."""
        return {
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
            "attributes": {
                "service.name": self.service_name,
                "event.category": entry.event.category.value,
                "event.type": entry.event.event_type,
                "log.level": entry.level.value,
                "log.message": entry.message,
                **{f"context.{k}": str(v) for k, v in entry.context.items()},
                **{f"tag.{tag}": True for tag in entry.tags},
            },
            "status": "ERROR" if entry.level in (LogLevel.ERROR, LogLevel.CRITICAL) else "OK",
            "metrics": {
                "duration_ms": entry.metrics.duration_ms,
                "tokens_total": entry.metrics.tokens_total,
                "estimated_cost_usd": entry.metrics.estimated_cost_usd,
            },
        }

    def _export_as_span(self, entry: LogEntry) -> None:
        """Export log entry as an OTel span."""
        # Create span context from our IDs
        trace_id = self._convert_trace_id(entry.trace_context.trace_id)
        span_id = self._convert_span_id(entry.trace_context.span_id)

        # Build parent context if exists
        parent_context = None
        if entry.trace_context.parent_span_id:
            parent_span_id = self._convert_span_id(entry.trace_context.parent_span_id)
            parent_span_context = trace.SpanContext(
                trace_id=trace_id,
                span_id=parent_span_id,
                is_remote=False,
                trace_flags=TraceFlags(TraceFlags.SAMPLED),
            )
            parent_context = trace.set_span_in_context(
                trace.NonRecordingSpan(parent_span_context)
            )

        # Determine span kind based on event category
        span_kind = SpanKind.INTERNAL
        if "http" in entry.tags or "browser" in entry.tags:
            span_kind = SpanKind.CLIENT
        elif "llm" in entry.tags:
            span_kind = SpanKind.CLIENT

        # Create span with our custom span context
        with self._tracer.start_as_current_span(
            name=entry.event.name,
            context=parent_context,
            kind=span_kind,
            start_time=int(entry.timestamp.timestamp() * 1e9),
        ) as span:
            # Set attributes
            span.set_attribute("event.category", entry.event.category.value)
            span.set_attribute("event.type", entry.event.event_type)
            span.set_attribute("log.level", entry.level.value)
            span.set_attribute("log.message", entry.message)

            # Add context attributes
            for key, value in entry.context.items():
                span.set_attribute(f"context.{key}", str(value))

            # Add tags
            for tag in entry.tags:
                span.set_attribute(f"tag.{tag}", True)

            # Add metrics as attributes
            if entry.metrics.duration_ms is not None:
                span.set_attribute("metrics.duration_ms", entry.metrics.duration_ms)
            if entry.metrics.tokens_input is not None:
                span.set_attribute("metrics.tokens_input", entry.metrics.tokens_input)
            if entry.metrics.tokens_output is not None:
                span.set_attribute("metrics.tokens_output", entry.metrics.tokens_output)
            if entry.metrics.tokens_total is not None:
                span.set_attribute("metrics.tokens_total", entry.metrics.tokens_total)
            if entry.metrics.estimated_cost_usd is not None:
                span.set_attribute("metrics.estimated_cost_usd", entry.metrics.estimated_cost_usd)

            # Set status based on log level
            if entry.level in (LogLevel.ERROR, LogLevel.CRITICAL):
                span.set_status(Status(StatusCode.ERROR, entry.message))
            else:
                span.set_status(Status(StatusCode.OK))

            # Set end time if duration is known
            # Note: The span will be ended automatically when exiting the context

    def flush(self) -> None:
        """Flush pending spans to exporter."""
        if self._initialized and self._provider:
            try:
                self._provider.force_flush(timeout_millis=5000)
            except Exception as e:
                _otel_logger.debug(f"Error flushing spans: {e}")

    def close(self) -> None:
        """Shutdown the tracer provider."""
        if self._initialized and self._provider:
            try:
                self._provider.shutdown()
                _otel_logger.info("OpenTelemetry provider shut down")
            except Exception as e:
                _otel_logger.debug(f"Error shutting down provider: {e}")

    def get_spans(self) -> list[dict]:
        """Get collected spans (for testing/debugging)."""
        with self._lock:
            return list(self._spans)

    @property
    def is_available(self) -> bool:
        """Check if OpenTelemetry is available and initialized."""
        return self._initialized


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
