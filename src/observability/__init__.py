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
    initialize_observability,
    is_initialized,
    get_handler,
    get_console_output,
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
from .tracer import (
    init_tracer,
    get_tracer,
    get_current_span,
    shutdown_tracer,
    format_trace_id,
    format_span_id,
)
from .emitters import (
    emit_log,
    emit_debug,
    emit_info,
    emit_warning,
    emit_error,
    emit_component_start,
    emit_component_end,
    emit_component_error,
)
from .schema import LogRecord, TraceEvent, ComponentType
from .serializers import safe_serialize, extract_error_info
from .outputs import LogOutput, ConsoleOutput, NullOutput
from .handlers import (
    LogHandler,
    OTelGrpcHandler,
    OTelConfig,
    NullHandler,
    CompositeHandler,
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
    "get_handler",
    "get_console_output",
    "get_config",
    "shutdown",
    # Context
    "ObservabilityContext",
    "get_or_create_context",
    "set_context",
    "reset_context",
    "ObservabilitySpan",
    # Tracer
    "init_tracer",
    "get_tracer",
    "get_current_span",
    "shutdown_tracer",
    "format_trace_id",
    "format_span_id",
    # Emitters
    "emit_log",
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
    "extract_error_info",
    # Outputs (local)
    "LogOutput",
    "ConsoleOutput",
    "NullOutput",
    # Handlers (backends)
    "LogHandler",
    "OTelGrpcHandler",
    "OTelConfig",
    "NullHandler",
    "CompositeHandler",
    # Decorators
    "traced_tool",
    "traced_agent",
    "traced_llm_client",
    "traced_http_call",
    "traced_browser_action",
    "traced_memory_operation",
]

# Version - bumped to 3.0.0 for OTel native spans
__version__ = "3.0.0"
