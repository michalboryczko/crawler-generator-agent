"""Structured logging system with OpenTelemetry-compatible schema.

This module provides the core classes for structured logging:
- LogLevel and LogLevelDetail for log level management
- EventCategory for event classification
- TraceContext for distributed tracing correlation
- LogEvent, LogMetrics, LogEntry for structured log data
- StructuredLogger for emitting logs
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
import uuid


class LogLevel(Enum):
    """Standard log levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogLevelDetail(Enum):
    """Sub-levels for granular filtering."""
    # DEBUG sub-levels
    DEBUG_VERBOSE = "DEBUG.VERBOSE"
    DEBUG_TRACE = "DEBUG.TRACE"
    DEBUG_INTERNAL = "DEBUG.INTERNAL"

    # INFO sub-levels
    INFO_LIFECYCLE = "INFO.LIFECYCLE"
    INFO_METRIC = "INFO.METRIC"
    INFO_DECISION = "INFO.DECISION"
    INFO_PROGRESS = "INFO.PROGRESS"

    # WARNING sub-levels
    WARNING_DEGRADED = "WARNING.DEGRADED"
    WARNING_LIMIT = "WARNING.LIMIT"
    WARNING_RETRY = "WARNING.RETRY"

    # ERROR sub-levels
    ERROR_RECOVERABLE = "ERROR.RECOVERABLE"
    ERROR_UNRECOVERABLE = "ERROR.UNRECOVERABLE"
    ERROR_EXTERNAL = "ERROR.EXTERNAL"


class EventCategory(Enum):
    """High-level event categories."""
    AGENT_LIFECYCLE = "agent_lifecycle"
    TOOL_EXECUTION = "tool_execution"
    LLM_INTERACTION = "llm_interaction"
    DECISION = "decision"
    MEMORY_OPERATION = "memory_operation"
    BROWSER_OPERATION = "browser_operation"
    HTTP_OPERATION = "http_operation"
    FILE_OPERATION = "file_operation"
    ERROR = "error"
    METRIC = "metric"


@dataclass
class TraceContext:
    """Immutable trace context for correlation.

    Provides session, request, trace, and span IDs for distributed tracing.
    """
    session_id: str
    request_id: str
    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None

    def child_span(self) -> "TraceContext":
        """Create a child span context."""
        return TraceContext(
            session_id=self.session_id,
            request_id=self.request_id,
            trace_id=self.trace_id,
            span_id=f"span_{uuid.uuid4().hex[:12]}",
            parent_span_id=self.span_id
        )

    @classmethod
    def new_session(cls) -> "TraceContext":
        """Create a new root session context."""
        session_id = f"sess_{uuid.uuid4().hex[:12]}"
        request_id = f"req_{uuid.uuid4().hex[:12]}"
        trace_id = f"trace_{uuid.uuid4().hex[:12]}"
        span_id = f"span_{uuid.uuid4().hex[:12]}"
        return cls(
            session_id=session_id,
            request_id=request_id,
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=None
        )

    def new_request(self) -> "TraceContext":
        """Create a new request within the same session."""
        return TraceContext(
            session_id=self.session_id,
            request_id=f"req_{uuid.uuid4().hex[:12]}",
            trace_id=f"trace_{uuid.uuid4().hex[:12]}",
            span_id=f"span_{uuid.uuid4().hex[:12]}",
            parent_span_id=None
        )


@dataclass
class LogEvent:
    """Structured log event."""
    category: EventCategory
    event_type: str
    name: str


@dataclass
class LogMetrics:
    """Metrics associated with a log entry."""
    duration_ms: Optional[float] = None
    time_to_first_token_ms: Optional[float] = None
    tokens_input: Optional[int] = None
    tokens_output: Optional[int] = None
    tokens_total: Optional[int] = None
    estimated_cost_usd: Optional[float] = None
    retry_count: Optional[int] = None
    content_size_bytes: Optional[int] = None


@dataclass
class LogEntry:
    """Complete structured log entry."""
    timestamp: datetime
    level: LogLevel
    level_detail: LogLevelDetail
    logger: str
    trace_context: TraceContext
    event: LogEvent
    context: dict[str, Any]
    data: dict[str, Any]
    metrics: LogMetrics
    tags: list[str]
    message: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "level": self.level.value,
            "level_detail": self.level_detail.value,
            "logger": self.logger,
            "trace_context": {
                "session_id": self.trace_context.session_id,
                "request_id": self.trace_context.request_id,
                "trace_id": self.trace_context.trace_id,
                "span_id": self.trace_context.span_id,
                "parent_span_id": self.trace_context.parent_span_id,
            },
            "event": {
                "category": self.event.category.value,
                "type": self.event.event_type,
                "name": self.event.name,
            },
            "context": self.context,
            "data": self.data,
            "metrics": {
                k: v for k, v in {
                    "duration_ms": self.metrics.duration_ms,
                    "time_to_first_token_ms": self.metrics.time_to_first_token_ms,
                    "tokens_input": self.metrics.tokens_input,
                    "tokens_output": self.metrics.tokens_output,
                    "tokens_total": self.metrics.tokens_total,
                    "estimated_cost_usd": self.metrics.estimated_cost_usd,
                    "retry_count": self.metrics.retry_count,
                    "content_size_bytes": self.metrics.content_size_bytes,
                }.items() if v is not None
            },
            "tags": self.tags,
            "message": self.message,
        }


class LogOutput(ABC):
    """Abstract base for log outputs."""

    @abstractmethod
    def write(self, entry: LogEntry) -> None:
        """Write a log entry."""
        pass

    @abstractmethod
    def flush(self) -> None:
        """Flush any buffered entries."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Close the output."""
        pass


class StructuredLogger:
    """Main structured logger interface.

    Provides methods for emitting structured log entries with full context,
    metrics, and trace correlation.
    """

    # Level ordering for filtering
    _LEVEL_ORDER = [LogLevel.DEBUG, LogLevel.INFO, LogLevel.WARNING, LogLevel.ERROR, LogLevel.CRITICAL]

    def __init__(
        self,
        name: str,
        trace_context: TraceContext,
        outputs: list[LogOutput],
        min_level: LogLevel = LogLevel.INFO,
        default_tags: list[str] | None = None,
        context: dict[str, Any] | None = None,
    ):
        """Initialize structured logger.

        Args:
            name: Logger name (e.g., "agents.browser")
            trace_context: Current trace context for correlation
            outputs: List of log output destinations
            min_level: Minimum log level to emit
            default_tags: Tags to include in all log entries
            context: Default context fields for all log entries
        """
        self.name = name
        self.trace_context = trace_context
        self.outputs = outputs
        self.min_level = min_level
        self.default_tags = default_tags or []
        self.default_context = context or {}

    def _should_log(self, level: LogLevel) -> bool:
        """Check if level should be logged."""
        return self._LEVEL_ORDER.index(level) >= self._LEVEL_ORDER.index(self.min_level)

    def _emit(self, entry: LogEntry) -> None:
        """Emit log entry to all outputs."""
        if not self._should_log(entry.level):
            return
        for output in self.outputs:
            try:
                output.write(entry)
            except Exception:
                # Don't let logging failures break the application
                pass

    def log(
        self,
        level: LogLevel,
        level_detail: LogLevelDetail,
        event: LogEvent,
        message: str,
        context: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        metrics: LogMetrics | None = None,
        tags: list[str] | None = None,
    ) -> None:
        """Log a structured event.

        Args:
            level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            level_detail: Sub-level for granular filtering
            event: Event category, type, and name
            message: Human-readable message
            context: Additional context fields
            data: Event-specific data
            metrics: Metrics associated with the event
            tags: Additional tags for filtering
        """
        entry = LogEntry(
            timestamp=datetime.now(timezone.utc),
            level=level,
            level_detail=level_detail,
            logger=self.name,
            trace_context=self.trace_context,
            event=event,
            context={**self.default_context, **(context or {})},
            data=data or {},
            metrics=metrics or LogMetrics(),
            tags=self.default_tags + (tags or []),
            message=message,
        )
        self._emit(entry)

    def child(
        self,
        name: str | None = None,
        context: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> "StructuredLogger":
        """Create a child logger with new span.

        Args:
            name: Override logger name (defaults to parent name)
            context: Additional context to merge with parent context
            tags: Additional tags to merge with parent tags

        Returns:
            New StructuredLogger with child span context
        """
        return StructuredLogger(
            name=name or self.name,
            trace_context=self.trace_context.child_span(),
            outputs=self.outputs,
            min_level=self.min_level,
            default_tags=self.default_tags + (tags or []),
            context={**self.default_context, **(context or {})},
        )

    # Convenience methods for common log patterns

    def debug(
        self,
        event: LogEvent,
        message: str,
        level_detail: LogLevelDetail = LogLevelDetail.DEBUG_TRACE,
        **kwargs
    ) -> None:
        """Log a debug event."""
        self.log(LogLevel.DEBUG, level_detail, event, message, **kwargs)

    def info(
        self,
        event: LogEvent,
        message: str,
        level_detail: LogLevelDetail = LogLevelDetail.INFO_LIFECYCLE,
        **kwargs
    ) -> None:
        """Log an info event."""
        self.log(LogLevel.INFO, level_detail, event, message, **kwargs)

    def warning(
        self,
        event: LogEvent,
        message: str,
        level_detail: LogLevelDetail = LogLevelDetail.WARNING_DEGRADED,
        **kwargs
    ) -> None:
        """Log a warning event."""
        self.log(LogLevel.WARNING, level_detail, event, message, **kwargs)

    def error(
        self,
        event: LogEvent,
        message: str,
        level_detail: LogLevelDetail = LogLevelDetail.ERROR_RECOVERABLE,
        **kwargs
    ) -> None:
        """Log an error event."""
        self.log(LogLevel.ERROR, level_detail, event, message, **kwargs)

    def critical(
        self,
        event: LogEvent,
        message: str,
        level_detail: LogLevelDetail = LogLevelDetail.ERROR_UNRECOVERABLE,
        **kwargs
    ) -> None:
        """Log a critical event."""
        self.log(LogLevel.CRITICAL, level_detail, event, message, **kwargs)

    # Specialized logging methods for common event types

    def log_llm_call(
        self,
        model: str,
        tokens_input: int,
        tokens_output: int,
        duration_ms: float,
        estimated_cost_usd: float,
        finish_reason: str,
        tool_called: str | None = None,
        **kwargs
    ) -> None:
        """Log an LLM call completion with metrics."""
        self.log(
            level=LogLevel.INFO,
            level_detail=LogLevelDetail.INFO_METRIC,
            event=LogEvent(
                category=EventCategory.LLM_INTERACTION,
                event_type="llm.call.complete",
                name="LLM call completed",
            ),
            message=f"LLM {model}: {tokens_input + tokens_output} tokens, {duration_ms:.0f}ms, ${estimated_cost_usd:.4f}",
            context={"model_name": model},
            data={
                "llm_response": {
                    "finish_reason": finish_reason,
                    "tool_called": tool_called,
                }
            },
            metrics=LogMetrics(
                duration_ms=duration_ms,
                tokens_input=tokens_input,
                tokens_output=tokens_output,
                tokens_total=tokens_input + tokens_output,
                estimated_cost_usd=estimated_cost_usd,
            ),
            tags=["llm", model, finish_reason],
            **kwargs
        )

    def log_tool_execution(
        self,
        tool_name: str,
        success: bool,
        duration_ms: float,
        input_preview: str | None = None,
        output_preview: str | None = None,
        error: str | None = None,
        **kwargs
    ) -> None:
        """Log a tool execution completion."""
        level = LogLevel.INFO if success else LogLevel.WARNING
        level_detail = LogLevelDetail.INFO_LIFECYCLE if success else LogLevelDetail.WARNING_DEGRADED

        self.log(
            level=level,
            level_detail=level_detail,
            event=LogEvent(
                category=EventCategory.TOOL_EXECUTION,
                event_type="tool.execute.complete",
                name=f"{tool_name} completed",
            ),
            message=f"Tool {tool_name}: {'success' if success else 'failed'} ({duration_ms:.0f}ms)",
            context={"tool_name": tool_name},
            data={
                "input_preview": input_preview,
                "output_preview": output_preview,
                "error": error,
            },
            metrics=LogMetrics(duration_ms=duration_ms),
            tags=["tool", tool_name, "success" if success else "failure"],
            **kwargs
        )

    def log_agent_lifecycle(
        self,
        agent_name: str,
        event_type: str,
        message: str,
        duration_ms: float | None = None,
        iterations: int | None = None,
        success: bool | None = None,
        **kwargs
    ) -> None:
        """Log an agent lifecycle event (start, complete, error)."""
        level = LogLevel.INFO
        if event_type == "agent.error":
            level = LogLevel.ERROR

        self.log(
            level=level,
            level_detail=LogLevelDetail.INFO_LIFECYCLE,
            event=LogEvent(
                category=EventCategory.AGENT_LIFECYCLE,
                event_type=event_type,
                name=f"{agent_name} {event_type.split('.')[-1]}",
            ),
            message=message,
            context={"agent_name": agent_name},
            data={
                "success": success,
                "iterations": iterations,
            },
            metrics=LogMetrics(duration_ms=duration_ms) if duration_ms else LogMetrics(),
            tags=["agent", agent_name, event_type.split(".")[-1]],
            **kwargs
        )
