"""Abstract handler interface and implementations for observability backends.

This module provides:
- Abstract LogHandler interface for sending logs to backends
- OTelGrpcHandler for OpenTelemetry Collector via gRPC

Architecture:
- Logs are sent via send_log() to OTel Collector → Elasticsearch
- Spans are created by decorators via OTel tracer → OTel Collector → Jaeger/Tempo

The handler is injected into the observability system, making the rest
of the code unaware of the specific backend.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
import threading

from .schema import LogRecord, TraceEvent


class LogHandler(ABC):
    """Abstract interface for observability backends.

    Implementations send logs to specific backends (OTel Collector, file, etc.).
    Spans are handled separately by decorators - not by this handler.
    """

    @abstractmethod
    def send_log(self, record: LogRecord) -> None:
        """Send a log record to the backend.

        Args:
            record: LogRecord to send.
        """
        pass

    @abstractmethod
    def send_trace(self, event: TraceEvent) -> None:
        """Handle a trace event.

        Note: Spans are created by decorators. This method exists for
        interface compatibility but may be a no-op in implementations.

        Args:
            event: TraceEvent (may be ignored).
        """
        pass

    @abstractmethod
    def flush(self) -> None:
        """Flush any buffered data."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Close the handler and release resources."""
        pass


@dataclass
class OTelConfig:
    """Configuration for OTel gRPC handler."""
    endpoint: str = "localhost:4317"
    insecure: bool = True
    service_name: str = "crawler-agent"
    batch_size: int = 100
    flush_interval_ms: int = 1000


class OTelGrpcHandler(LogHandler):
    """OpenTelemetry Collector handler via gRPC.

    Sends logs to OTel Collector using OTLP gRPC protocol.
    Spans are NOT created here - they are created by decorators.
    """

    def __init__(self, config: OTelConfig):
        """Initialize OTel gRPC handler.

        Args:
            config: OTel configuration.
        """
        self.config = config
        self._lock = threading.Lock()
        self._initialized = False
        self._logger_provider = None
        self._initialize()

    def _initialize(self) -> None:
        """Initialize OTel log exporter only.

        Note: Trace exporter is initialized in tracer.py, not here.
        """
        try:
            from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
            from opentelemetry.sdk._logs import LoggerProvider
            from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
            from opentelemetry.sdk.resources import Resource, SERVICE_NAME
            from opentelemetry._logs import set_logger_provider

            resource = Resource.create({SERVICE_NAME: self.config.service_name})

            # Set up log exporter only - trace exporter is in tracer.py
            log_exporter = OTLPLogExporter(
                endpoint=self.config.endpoint,
                insecure=self.config.insecure
            )
            self._logger_provider = LoggerProvider(resource=resource)
            self._logger_provider.add_log_record_processor(
                BatchLogRecordProcessor(log_exporter)
            )
            set_logger_provider(self._logger_provider)

            self._initialized = True
        except ImportError as e:
            print(f"Warning: OTel packages not installed: {e}")
        except Exception as e:
            print(f"Warning: Failed to initialize OTel: {e}")

    def send_log(self, record: LogRecord) -> None:
        """Send log record via OTLP.

        Uses OTel's native Logger.emit() API for proper structured data handling.

        Args:
            record: LogRecord to send.
        """
        if not self._initialized:
            return

        try:
            from opentelemetry._logs import SeverityNumber
            import json
            import time

            # Map our level to OTel severity
            severity_map = {
                "DEBUG": (SeverityNumber.DEBUG, "DEBUG"),
                "INFO": (SeverityNumber.INFO, "INFO"),
                "WARNING": (SeverityNumber.WARN, "WARN"),
                "ERROR": (SeverityNumber.ERROR, "ERROR"),
            }
            severity_number, severity_text = severity_map.get(
                record.level, (SeverityNumber.INFO, "INFO")
            )

            # Build attributes dict with all our structured data
            attributes = {
                "event": record.event,
                "component_type": record.component_type,
                "component_name": record.component_name,
                "trace_id": record.trace_id,
                "span_id": record.span_id,
                "parent_span_id": record.parent_span_id or "",
                "session_id": record.session_id or "",
                "request_id": record.request_id or "",
                "triggered_by": record.triggered_by,
                "tags": ",".join(record.tags) if record.tags else "",
            }

            # Add data fields as individual attributes
            if record.data:
                for key, value in record.data.items():
                    attr_key = f"data.{key}"
                    if isinstance(value, (str, int, float, bool)):
                        attributes[attr_key] = value
                    elif value is not None:
                        try:
                            json_str = json.dumps(value, default=str)
                            if len(json_str) > 65000:
                                json_str = json_str[:65000] + "...[TRUNCATED]"
                            attributes[attr_key] = json_str
                        except Exception:
                            attributes[attr_key] = "<serialization error>"

            # Add metrics as individual attributes
            if record.metrics:
                for key, value in record.metrics.items():
                    attr_key = f"metrics.{key}"
                    if isinstance(value, (int, float)):
                        attributes[attr_key] = value
                    elif value is not None:
                        attributes[attr_key] = str(value)

            # Emit using Logger.emit() with keyword arguments
            self._logger_provider.get_logger(
                self.config.service_name
            ).emit(
                timestamp=int(record.timestamp.timestamp() * 1e9),
                observed_timestamp=time.time_ns(),
                severity_number=severity_number,
                severity_text=severity_text,
                body=f"{record.event} - {record.component_name}",
                attributes=attributes,
            )

        except Exception:
            pass  # Don't let OTel errors break the application

    def send_trace(self, event: TraceEvent) -> None:
        """Handle trace event - NO-OP.

        Spans are created by decorators using OTel tracer directly.
        This method exists only for interface compatibility.

        Args:
            event: TraceEvent (ignored).
        """
        # Spans are created by decorators, not here
        pass

    def flush(self) -> None:
        """Force flush log exporter."""
        if self._initialized and self._logger_provider:
            try:
                self._logger_provider.force_flush()
            except Exception:
                pass

    def close(self) -> None:
        """Shutdown log exporter."""
        if self._initialized and self._logger_provider:
            try:
                self._logger_provider.shutdown()
            except Exception:
                pass
            self._initialized = False


class NullHandler(LogHandler):
    """Null handler that discards all data.

    Useful for testing or when observability is disabled.
    """

    def send_log(self, record: LogRecord) -> None:
        pass

    def send_trace(self, event: TraceEvent) -> None:
        pass

    def flush(self) -> None:
        pass

    def close(self) -> None:
        pass


class CompositeHandler(LogHandler):
    """Combines multiple handlers into one.

    Sends to all handlers. Errors in one don't affect others.
    """

    def __init__(self, handlers: list):
        self.handlers = handlers

    def send_log(self, record: LogRecord) -> None:
        for handler in self.handlers:
            try:
                handler.send_log(record)
            except Exception:
                pass

    def send_trace(self, event: TraceEvent) -> None:
        for handler in self.handlers:
            try:
                handler.send_trace(event)
            except Exception:
                pass

    def flush(self) -> None:
        for handler in self.handlers:
            try:
                handler.flush()
            except Exception:
                pass

    def close(self) -> None:
        for handler in self.handlers:
            try:
                handler.close()
            except Exception:
                pass
