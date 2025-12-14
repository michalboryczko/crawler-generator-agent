"""Log emitters for observability.

This module provides the core emission functions for logs.
All emissions are UNCONDITIONAL - level is metadata only, not a filter.

Logs are sent to:
1. LogHandler (OTel backend → Elasticsearch)
2. ConsoleOutput (optional, for development)

OTel spans are created by decorators in decorators.py - NOT here.
Logs are correlated to spans via trace_id/span_id extracted from OTel span context.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional, List

from .context import ObservabilityContext
from .config import get_handler, get_console_output, is_initialized, get_config
from .schema import LogRecord, F, D, M
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

    trace_id/span_id are automatically extracted from the OTel span
    attached to the ObservabilityContext.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR) - metadata only!
        event: Event type (e.g., "tool.input", "agent.error")
        ctx: Current observability context (hybrid: OTel span + business metadata)
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

    # Create LogRecord - trace_id/span_id come from OTel span via context properties
    record = LogRecord(
        timestamp=datetime.now(timezone.utc),
        trace_id=ctx.trace_id,           # From OTel span context
        span_id=ctx.span_id,             # From OTel span context
        parent_span_id=ctx.parent_span_id,  # From OTel span context
        session_id=ctx.session_id,       # Business metadata (we manage)
        request_id=ctx.request_id,       # Business metadata (we manage)
        level=level,
        event=event,
        component_type=component_type,
        component_name=component_name,
        triggered_by=ctx.triggered_by,   # Derived from component_stack
        data=data,
        metrics=metrics or {},
        tags=tags or []
    )

    # Send to handler (OTel backend → Elasticsearch)
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


def emit_debug(
    event: str,
    ctx: ObservabilityContext,
    data: Dict[str, Any],
    metrics: Optional[Dict[str, Any]] = None,
    tags: Optional[List[str]] = None
) -> None:
    """Convenience function to emit DEBUG level log."""
    emit_log("DEBUG", event, ctx, data, metrics, tags)


def emit_info(
    event: str,
    ctx: ObservabilityContext,
    data: Dict[str, Any],
    metrics: Optional[Dict[str, Any]] = None,
    tags: Optional[List[str]] = None
) -> None:
    """Convenience function to emit INFO level log."""
    emit_log("INFO", event, ctx, data, metrics, tags)


def emit_warning(
    event: str,
    ctx: ObservabilityContext,
    data: Dict[str, Any],
    metrics: Optional[Dict[str, Any]] = None,
    tags: Optional[List[str]] = None
) -> None:
    """Convenience function to emit WARNING level log."""
    emit_log("WARNING", event, ctx, data, metrics, tags)


def emit_error(
    event: str,
    ctx: ObservabilityContext,
    data: Dict[str, Any],
    metrics: Optional[Dict[str, Any]] = None,
    tags: Optional[List[str]] = None
) -> None:
    """Convenience function to emit ERROR level log."""
    emit_log("ERROR", event, ctx, data, metrics, tags)


def emit_component_start(
    component_type: str,
    component_name: str,
    ctx: ObservabilityContext,
    input_data: Dict[str, Any]
) -> None:
    """Emit component start log.

    OTel span is created by the decorator - this only emits the log.

    Args:
        component_type: Type of component (agent, tool, llm_client)
        component_name: Name of the component
        ctx: Observability context
        input_data: Input data for the component
    """
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


def emit_component_end(
    component_type: str,
    component_name: str,
    ctx: ObservabilityContext,
    output_data: Dict[str, Any],
    duration_ms: float,
    metrics: Optional[Dict[str, Any]] = None
) -> None:
    """Emit component completion log.

    OTel span status is set by the decorator - this only emits the log.

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


def emit_component_error(
    component_type: str,
    component_name: str,
    ctx: ObservabilityContext,
    exception: Exception,
    input_data: Dict[str, Any],
    duration_ms: float
) -> None:
    """Emit component error log.

    OTel span error status is set by the decorator - this only emits the log.

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
