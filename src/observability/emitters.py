"""Log and trace event emitters.

This module provides the core emission functions for observability.
All emissions are UNCONDITIONAL - level is metadata only, not a filter.

Emitters send data to:
1. LogHandler (abstract backend - OTel, etc.)
2. ConsoleOutput (optional, for development)
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional, List

from .context import ObservabilityContext
from .config import get_handler, get_console_output, is_initialized, get_config
from .schema import LogRecord, TraceEvent, F, D, M
from .serializers import safe_serialize, redact_sensitive


def emit_log(
    level: str,
    event: str,
    ctx: ObservabilityContext,
    data: Dict[str, Any],
    metrics: Optional[Dict[str, Any]] = None,
    tags: Optional[List[str]] = None
) -> None:
    """Emit a log record UNCONDITIONALLY.

    Level is metadata only - never used for filtering.
    All logs are always emitted.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR) - metadata only!
        event: Event type (e.g., "tool.input", "agent.error")
        ctx: Current observability context
        data: Event data payload
        metrics: Optional metrics dict
        tags: Optional tags list
    """
    if not is_initialized():
        return

    # Parse component info from event
    parts = event.split(".")
    component_type = parts[0] if parts else "unknown"

    # Get component name from data or context
    component_name = (
        data.get(f"{component_type}_name") or
        data.get("component_name") or
        (ctx.component_stack[-1] if ctx.component_stack else "unknown")
    )

    # Apply PII redaction if configured
    config = get_config()
    if config and config.redact_pii:
        data = redact_sensitive(safe_serialize(data))
    else:
        data = safe_serialize(data)

    record = LogRecord(
        timestamp=datetime.now(timezone.utc),
        trace_id=ctx.trace_id,
        span_id=ctx.span_id,
        parent_span_id=ctx.parent_span_id,
        session_id=ctx.session_id,
        request_id=ctx.request_id,
        level=level,
        event=event,
        component_type=component_type,
        component_name=component_name,
        triggered_by=ctx.triggered_by,
        data=data,
        metrics=metrics or {},
        tags=tags or []
    )

    # Send to handler (OTel backend)
    handler = get_handler()
    if handler:
        try:
            handler.send_log(record)
        except Exception:
            pass

    # Also write to console if enabled (for dev)
    console = get_console_output()
    if console:
        try:
            console.write_log(record)
        except Exception:
            pass


def emit_trace_event(
    event: str,
    ctx: ObservabilityContext,
    attributes: Dict[str, Any]
) -> None:
    """Emit a trace event (span event).

    Creates an OTel-compatible span event with proper hierarchy.

    Args:
        event: Event name (e.g., "tool.triggered")
        ctx: Current observability context
        attributes: Event attributes
    """
    if not is_initialized():
        return

    # Serialize attributes
    serialized_attrs = safe_serialize(attributes)

    # Apply PII redaction if configured
    config = get_config()
    if config and config.redact_pii:
        serialized_attrs = redact_sensitive(serialized_attrs)

    trace_event = TraceEvent(
        name=event,
        timestamp=datetime.now(timezone.utc),
        trace_id=ctx.trace_id,
        span_id=ctx.span_id,
        parent_span_id=ctx.parent_span_id,
        attributes={
            **serialized_attrs,
            F.TRIGGERED_BY: ctx.triggered_by
        }
    )

    # Send to handler (OTel backend)
    handler = get_handler()
    if handler:
        try:
            handler.send_trace(trace_event)
        except Exception:
            pass

    # Also write to console if enabled (for dev)
    console = get_console_output()
    if console and hasattr(console, 'write_trace_event'):
        try:
            console.write_trace_event(trace_event.to_dict())
        except Exception:
            pass


def emit_debug(
    event: str,
    ctx: ObservabilityContext,
    data: Dict[str, Any],
    metrics: Optional[Dict[str, Any]] = None,
    tags: Optional[List[str]] = None
) -> None:
    """Convenience function to emit DEBUG level log.
    
    Args:
        event: Event type
        ctx: Observability context
        data: Event data
        metrics: Optional metrics
        tags: Optional tags
    """
    emit_log("DEBUG", event, ctx, data, metrics, tags)


def emit_info(
    event: str,
    ctx: ObservabilityContext,
    data: Dict[str, Any],
    metrics: Optional[Dict[str, Any]] = None,
    tags: Optional[List[str]] = None
) -> None:
    """Convenience function to emit INFO level log.
    
    Args:
        event: Event type
        ctx: Observability context
        data: Event data
        metrics: Optional metrics
        tags: Optional tags
    """
    emit_log("INFO", event, ctx, data, metrics, tags)


def emit_warning(
    event: str,
    ctx: ObservabilityContext,
    data: Dict[str, Any],
    metrics: Optional[Dict[str, Any]] = None,
    tags: Optional[List[str]] = None
) -> None:
    """Convenience function to emit WARNING level log.
    
    Args:
        event: Event type
        ctx: Observability context
        data: Event data
        metrics: Optional metrics
        tags: Optional tags
    """
    emit_log("WARNING", event, ctx, data, metrics, tags)


def emit_error(
    event: str,
    ctx: ObservabilityContext,
    data: Dict[str, Any],
    metrics: Optional[Dict[str, Any]] = None,
    tags: Optional[List[str]] = None
) -> None:
    """Convenience function to emit ERROR level log.
    
    Args:
        event: Event type
        ctx: Observability context
        data: Event data
        metrics: Optional metrics
        tags: Optional tags
    """
    emit_log("ERROR", event, ctx, data, metrics, tags)


def emit_component_start(
    component_type: str,
    component_name: str,
    ctx: ObservabilityContext,
    input_data: Dict[str, Any]
) -> None:
    """Emit component start events (log + trace).

    Standard pattern for component entry points.

    Args:
        component_type: Type of component (agent, tool, llm_client)
        component_name: Name of the component
        ctx: Observability context
        input_data: Input data for the component
    """
    # Build component name key dynamically (e.g., "tool_name", "agent_name")
    name_key = f"{component_type}_name"

    emit_log(
        level="DEBUG",
        event=f"{component_type}.input",
        ctx=ctx,
        data={
            name_key: component_name,
            F.TRIGGERED_BY: ctx.triggered_by,
            D.INPUT: input_data
        }
    )

    emit_trace_event(f"{component_type}.triggered", ctx, {
        name_key: component_name,
        F.TRIGGERED_BY: ctx.triggered_by
    })


def emit_component_end(
    component_type: str,
    component_name: str,
    ctx: ObservabilityContext,
    output_data: Dict[str, Any],
    duration_ms: float,
    metrics: Optional[Dict[str, Any]] = None
) -> None:
    """Emit component completion events (log + trace).

    Standard pattern for component completion.

    Args:
        component_type: Type of component
        component_name: Name of the component
        ctx: Observability context
        output_data: Output data from the component
        duration_ms: Execution duration in milliseconds
        metrics: Additional metrics
    """
    name_key = f"{component_type}_name"

    all_metrics = {M.DURATION_MS: duration_ms}
    if metrics:
        all_metrics.update(metrics)

    emit_log(
        level="DEBUG",
        event=f"{component_type}.output",
        ctx=ctx,
        data={
            name_key: component_name,
            D.OUTPUT: output_data,
            D.DURATION_MS: duration_ms
        },
        metrics=all_metrics
    )

    emit_trace_event(f"{component_type}.execution_completed", ctx, {
        name_key: component_name,
        M.DURATION_MS: duration_ms,
        **(metrics or {})
    })


def emit_component_error(
    component_type: str,
    component_name: str,
    ctx: ObservabilityContext,
    exception: Exception,
    input_data: Dict[str, Any],
    duration_ms: float
) -> None:
    """Emit component error events (log + trace).

    Standard pattern for component errors.

    Args:
        component_type: Type of component
        component_name: Name of the component
        ctx: Observability context
        exception: The exception that occurred
        input_data: Input data when error occurred
        duration_ms: Duration until error in milliseconds
    """
    import traceback

    name_key = f"{component_type}_name"

    error_data = {
        name_key: component_name,
        F.TRIGGERED_BY: ctx.triggered_by,
        D.ERROR_TYPE: type(exception).__name__,
        D.ERROR_MESSAGE: str(exception),
        D.STACK_TRACE: traceback.format_exc(),
        D.INPUT: input_data,
        D.DURATION_MS: duration_ms
    }

    emit_log(
        level="ERROR",
        event=f"{component_type}.error",
        ctx=ctx,
        data=error_data,
        metrics={M.DURATION_MS: duration_ms}
    )

    emit_trace_event(f"{component_type}.error", ctx, {
        name_key: component_name,
        D.ERROR_TYPE: type(exception).__name__,
        D.ERROR_MESSAGE: str(exception)
    })
