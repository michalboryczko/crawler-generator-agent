"""Observability module for logging and tracing.

This module provides:
- Decorator-based instrumentation (@traced_agent, @traced_tool, @traced_llm_client)
- Automatic context propagation via OTel and contextvars
- OTel spans created by decorators for proper trace hierarchy
- Logs correlated to spans via trace_id/span_id

Architecture:
- Tracer: Creates OTel spans (in decorators)
- LogHandler: Sends logs to OTel Collector → Elasticsearch
- ConsoleOutput: Optional human-readable output for development
- Emitters: Create LogRecords with trace_id/span_id from active span

Data Flow:
- Spans: decorators → OTel tracer → OTel Collector → Jaeger/Tempo
- Logs: emitters → handler.send_log() → OTel Collector → Elasticsearch

Usage:
    from src.observability import initialize_observability, ObservabilityConfig
    from src.observability.decorators import traced_tool, traced_agent
    from src.observability.handlers import OTelGrpcHandler, OTelConfig

    # Initialize at application start
    handler = OTelGrpcHandler(OTelConfig())
    initialize_observability(handler=handler)

    # Apply decorators to components
    @traced_tool(name="MyTool")
    def my_tool_function(arg: str) -> dict:
        return {"result": arg}

Key Concepts:
    - Level is METADATA only, never used for filtering
    - All logs are always emitted
    - Spans are created by decorators with proper parent-child hierarchy
    - Logs get trace_id/span_id from active OTel span
"""

from .config import (
    ObservabilityConfig,
    get_config,
    get_console_output,
    get_handler,
    initialize_observability,
    is_initialized,
    shutdown,
)
from .context import (
    ObservabilityContext,
    ObservabilitySpan,
    get_or_create_context,
    reset_context,
    set_context,
)
from .decorators import (
    traced_agent,
    traced_browser_action,
    traced_http_call,
    traced_llm_client,
    traced_memory_operation,
    traced_tool,
)
from .emitters import (
    emit_component_end,
    emit_component_error,
    emit_component_start,
    emit_debug,
    emit_error,
    emit_info,
    emit_log,
    emit_warning,
)
from .handlers import (
    CompositeHandler,
    LogHandler,
    NullHandler,
    OTelConfig,
    OTelGrpcHandler,
)
from .outputs import ConsoleOutput, LogOutput, NullOutput
from .schema import ComponentType, LogRecord, TraceEvent
from .serializers import extract_error_info, safe_serialize
from .tracer import (
    format_span_id,
    format_trace_id,
    get_current_span,
    get_tracer,
    init_tracer,
    shutdown_tracer,
)

__all__ = [
    "ComponentType",
    "CompositeHandler",
    "ConsoleOutput",
    # Handlers (backends)
    "LogHandler",
    # Outputs (local)
    "LogOutput",
    # Schema
    "LogRecord",
    "NullHandler",
    "NullOutput",
    "OTelConfig",
    "OTelGrpcHandler",
    # Configuration
    "ObservabilityConfig",
    # Context
    "ObservabilityContext",
    "ObservabilitySpan",
    "TraceEvent",
    "emit_component_end",
    "emit_component_error",
    "emit_component_start",
    "emit_debug",
    "emit_error",
    "emit_info",
    # Emitters
    "emit_log",
    "emit_warning",
    "extract_error_info",
    "format_span_id",
    "format_trace_id",
    "get_config",
    "get_console_output",
    "get_current_span",
    "get_handler",
    "get_or_create_context",
    "get_tracer",
    # Tracer
    "init_tracer",
    "initialize_observability",
    "is_initialized",
    "reset_context",
    # Serializers
    "safe_serialize",
    "set_context",
    "shutdown",
    "shutdown_tracer",
    "traced_agent",
    "traced_browser_action",
    "traced_http_call",
    "traced_llm_client",
    "traced_memory_operation",
    # Decorators
    "traced_tool",
]

# Version - bumped to 3.0.0 for OTel native spans
__version__ = "3.0.0"
