"""Output implementations for observability.

This module provides various output targets for log records and trace events.
All outputs are thread-safe and handle errors gracefully.
"""

import json
import sys
import threading
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import TextIO, Any, Dict, Optional

from .schema import LogRecord, TraceEvent


class LogOutput(ABC):
    """Abstract base for log outputs.
    
    All outputs must implement write_log, flush, and close.
    write_trace_event is optional for outputs that support tracing.
    """

    @abstractmethod
    def write_log(self, record: LogRecord) -> None:
        """Write a log record.
        
        Args:
            record: LogRecord to write.
        """
        pass

    def write_trace_event(self, event: Dict[str, Any]) -> None:
        """Write a trace event (optional).
        
        Override this method to support trace events.
        
        Args:
            event: Trace event dictionary.
        """
        pass

    @abstractmethod
    def flush(self) -> None:
        """Flush buffered data."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Close the output and release resources."""
        pass


class ConsoleOutput(LogOutput):
    """Human-readable console output with optional colors.
    
    Formats log records for easy reading in terminal.
    Thread-safe for concurrent writes.
    """

    LEVEL_COLORS = {
        "DEBUG": "\033[36m",    # Cyan
        "INFO": "\033[32m",     # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",    # Red
        "CRITICAL": "\033[35m", # Magenta
    }
    RESET = "\033[0m"
    DIM = "\033[2m"
    BOLD = "\033[1m"

    def __init__(self, stream: TextIO = None, color: bool = True):
        """Initialize console output.
        
        Args:
            stream: Output stream (default: sys.stdout).
            color: Whether to use ANSI colors.
        """
        self.stream = stream or sys.stdout
        self.color = color and hasattr(self.stream, 'isatty') and self.stream.isatty()
        self._lock = threading.Lock()

    def write_log(self, record: LogRecord) -> None:
        """Write log record to console.
        
        Args:
            record: LogRecord to write.
        """
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

        with self._lock:
            try:
                self.stream.write(line + "\n")
            except Exception:
                pass  # Don't let console errors break the application

    def write_trace_event(self, event: Dict[str, Any]) -> None:
        """Write trace event to console (simplified format).
        
        Args:
            event: Trace event dictionary.
        """
        if not self.color:
            dim = ""
            reset = ""
        else:
            dim = self.DIM
            reset = self.RESET
        
        name = event.get("name", "unknown")
        span_id = event.get("span_id", "")[-8:]
        
        line = f"{dim}    TRACE [{span_id}] {name}{reset}"
        
        with self._lock:
            try:
                self.stream.write(line + "\n")
            except Exception:
                pass

    def flush(self) -> None:
        """Flush the output stream."""
        with self._lock:
            try:
                self.stream.flush()
            except Exception:
                pass

    def close(self) -> None:
        """Close console output (no-op for stdout)."""
        pass


class JSONLinesOutput(LogOutput):
    """JSON Lines file output.
    
    Writes each log record as a single JSON line.
    Thread-safe for concurrent writes.
    """

    def __init__(self, file_path: Path):
        """Initialize JSONL output.
        
        Args:
            file_path: Path to the output file.
        """
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self._file = open(self.file_path, "a", encoding="utf-8")
        self._lock = threading.Lock()

    def write_log(self, record: LogRecord) -> None:
        """Write log record as JSON line.
        
        Args:
            record: LogRecord to write.
        """
        try:
            line = json.dumps(record.to_dict(), default=str, ensure_ascii=False) + "\n"
            with self._lock:
                self._file.write(line)
        except Exception:
            pass  # Don't let file errors break the application

    def write_trace_event(self, event: Dict[str, Any]) -> None:
        """Write trace event as JSON line.
        
        Args:
            event: Trace event dictionary.
        """
        try:
            # Mark trace events with a type field
            event_with_type = {"_type": "trace_event", **event}
            line = json.dumps(event_with_type, default=str, ensure_ascii=False) + "\n"
            with self._lock:
                self._file.write(line)
        except Exception:
            pass

    def flush(self) -> None:
        """Flush the file buffer."""
        with self._lock:
            try:
                self._file.flush()
            except Exception:
                pass

    def close(self) -> None:
        """Close the file."""
        with self._lock:
            try:
                self._file.close()
            except Exception:
                pass


class OTLPOutput(LogOutput):
    """OpenTelemetry OTLP output for traces and logs.
    
    Sends telemetry data to an OTLP-compatible collector.
    Handles initialization errors gracefully.
    """

    def __init__(self, service_name: str, endpoint: str, insecure: bool = True):
        """Initialize OTLP output.
        
        Args:
            service_name: Service name for trace identification.
            endpoint: OTLP collector endpoint.
            insecure: Whether to use insecure connection.
        """
        self.service_name = service_name
        self.endpoint = endpoint
        self.insecure = insecure
        self._tracer = None
        self._provider = None
        self._initialized = False
        self._lock = threading.Lock()
        self._active_spans: Dict[str, Any] = {}
        self._initialize()

    def _initialize(self) -> None:
        """Initialize OpenTelemetry components."""
        try:
            from opentelemetry import trace
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            from opentelemetry.sdk.resources import Resource, SERVICE_NAME

            resource = Resource.create({SERVICE_NAME: self.service_name})
            self._provider = TracerProvider(resource=resource)

            exporter = OTLPSpanExporter(
                endpoint=self.endpoint,
                insecure=self.insecure
            )
            self._provider.add_span_processor(BatchSpanProcessor(exporter))

            trace.set_tracer_provider(self._provider)
            self._tracer = trace.get_tracer(self.service_name)
            self._initialized = True
        except ImportError:
            # OpenTelemetry packages not installed
            pass
        except Exception:
            # Other initialization errors
            pass

    def write_log(self, record: LogRecord) -> None:
        """Write log record to OTLP.
        
        Currently logs are not sent via OTLP. Override this
        to implement OTLP log export when needed.
        
        Args:
            record: LogRecord to write.
        """
        # OTLP log export could be implemented here
        # For now, logs go to JSONLines, traces go to OTLP
        pass

    def write_trace_event(self, event: Dict[str, Any]) -> None:
        """Write trace event to OTLP.
        
        Creates or updates spans based on event type.
        
        Args:
            event: Trace event dictionary.
        """
        if not self._initialized or not self._tracer:
            return

        try:
            from opentelemetry import trace
            from opentelemetry.trace import SpanKind, Status, StatusCode
            
            event_name = event.get("name", "unknown")
            span_id = event.get("span_id", "")
            attributes = event.get("attributes", {})
            
            # Flatten nested attributes for OTel
            flat_attrs = {}
            for k, v in attributes.items():
                if isinstance(v, (str, int, float, bool)):
                    flat_attrs[k] = v
                elif v is not None:
                    flat_attrs[k] = str(v)
            
            # Handle span lifecycle events
            if event_name.endswith(".triggered") or event_name.endswith(".input"):
                # Start a new span
                span = self._tracer.start_span(
                    name=event_name.rsplit(".", 1)[0],
                    kind=SpanKind.INTERNAL,
                    attributes=flat_attrs
                )
                with self._lock:
                    self._active_spans[span_id] = span
                    
            elif event_name.endswith(".execution_completed") or event_name.endswith(".output"):
                # End the span
                with self._lock:
                    span = self._active_spans.pop(span_id, None)
                if span:
                    for k, v in flat_attrs.items():
                        span.set_attribute(k, v)
                    span.set_status(Status(StatusCode.OK))
                    span.end()
                    
            elif event_name.endswith(".error"):
                # End span with error status
                with self._lock:
                    span = self._active_spans.pop(span_id, None)
                if span:
                    for k, v in flat_attrs.items():
                        span.set_attribute(k, v)
                    error_msg = attributes.get("error_message", "Unknown error")
                    span.set_status(Status(StatusCode.ERROR, error_msg))
                    span.end()
                    
            else:
                # Add as span event to active span
                with self._lock:
                    span = self._active_spans.get(span_id)
                if span:
                    span.add_event(event_name, attributes=flat_attrs)
                    
        except Exception:
            pass  # Don't let OTLP errors break the application

    def flush(self) -> None:
        """Force flush the span processor."""
        if self._initialized and self._provider:
            try:
                self._provider.force_flush()
            except Exception:
                pass

    def close(self) -> None:
        """Shutdown the provider."""
        if self._initialized and self._provider:
            try:
                # End any remaining spans
                with self._lock:
                    for span in self._active_spans.values():
                        try:
                            span.end()
                        except Exception:
                            pass
                    self._active_spans.clear()
                self._provider.shutdown()
            except Exception:
                pass


class CompositeOutput(LogOutput):
    """Combines multiple outputs into one.
    
    Writes to all configured outputs. Errors in one output
    don't affect others.
    """

    def __init__(self, outputs: list):
        """Initialize composite output.
        
        Args:
            outputs: List of LogOutput instances.
        """
        self.outputs = outputs

    def write_log(self, record: LogRecord) -> None:
        """Write to all outputs.
        
        Args:
            record: LogRecord to write.
        """
        for output in self.outputs:
            try:
                output.write_log(record)
            except Exception:
                pass

    def write_trace_event(self, event: Dict[str, Any]) -> None:
        """Write trace event to all outputs.
        
        Args:
            event: Trace event dictionary.
        """
        for output in self.outputs:
            try:
                output.write_trace_event(event)
            except Exception:
                pass

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


class NullOutput(LogOutput):
    """Null output that discards all data.
    
    Useful for testing or when observability is disabled.
    """

    def write_log(self, record: LogRecord) -> None:
        """Discard log record."""
        pass

    def write_trace_event(self, event: Dict[str, Any]) -> None:
        """Discard trace event."""
        pass

    def flush(self) -> None:
        """No-op flush."""
        pass

    def close(self) -> None:
        """No-op close."""
        pass
