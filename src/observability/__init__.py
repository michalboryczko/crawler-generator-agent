"""Observability module for unconditional logging and tracing.

This module provides:
- Decorator-based instrumentation (@traced_agent, @traced_tool, @traced_llm_client)
- Automatic context propagation via contextvars
- Separate Trace Events (spans) and Logs (detailed data)
- Zero log filtering - everything is always logged

Usage:
    from src.observability import initialize_observability, ObservabilityConfig
    from src.observability.decorators import traced_tool, traced_agent

    # Initialize at application start
    initialize_observability(ObservabilityConfig.from_env())

    # Apply decorators to components
    @traced_tool(name="MyTool")
    def my_tool_function(arg: str) -> dict:
        return {"result": arg}

Key Concepts:
    - Level is METADATA only, never used for filtering
    - All events are always emitted to all outputs
    - Context propagation is automatic via decorators
    - Traces and Logs are separate concerns
"""

from .config import (
    ObservabilityConfig,
    initialize_observability,
    is_initialized,
    get_outputs,
    get_config,
    shutdown,
)
from .context import (
    ObservabilityContext,
    get_or_create_context,
    set_context,
    reset_context,
    ObservabilitySpan,
)
from .emitters import (
    emit_log,
    emit_trace_event,
    emit_debug,
    emit_info,
    emit_warning,
    emit_error,
    emit_component_start,
    emit_component_end,
    emit_component_error,
)
from .schema import LogRecord, TraceEvent, ComponentType
from .serializers import safe_serialize, redact_sensitive, extract_error_info
from .outputs import (
    LogOutput,
    ConsoleOutput,
    JSONLinesOutput,
    OTLPOutput,
    CompositeOutput,
    NullOutput,
)
from .decorators import (
    traced_tool,
    traced_agent,
    traced_llm_client,
    traced_http_call,
    traced_browser_action,
    traced_memory_operation,
)

__all__ = [
    # Configuration
    "ObservabilityConfig",
    "initialize_observability",
    "is_initialized",
    "get_outputs",
    "get_config",
    "shutdown",
    # Context
    "ObservabilityContext",
    "get_or_create_context",
    "set_context",
    "reset_context",
    "ObservabilitySpan",
    # Emitters
    "emit_log",
    "emit_trace_event",
    "emit_debug",
    "emit_info",
    "emit_warning",
    "emit_error",
    "emit_component_start",
    "emit_component_end",
    "emit_component_error",
    # Schema
    "LogRecord",
    "TraceEvent",
    "ComponentType",
    # Serializers
    "safe_serialize",
    "redact_sensitive",
    "extract_error_info",
    # Outputs
    "LogOutput",
    "ConsoleOutput",
    "JSONLinesOutput",
    "OTLPOutput",
    "CompositeOutput",
    "NullOutput",
    # Decorators
    "traced_tool",
    "traced_agent",
    "traced_llm_client",
    "traced_http_call",
    "traced_browser_action",
    "traced_memory_operation",
]

# Version
__version__ = "1.0.0"
