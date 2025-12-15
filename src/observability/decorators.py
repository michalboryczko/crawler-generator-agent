"""Decorator-based instrumentation using native OTel spans.

Decorators create proper parent-child span relationships via OTel context.
No manual ID generation or parent tracking - OTel handles all of that.

Usage:
    @traced_tool(name="MyTool")
    def my_tool(arg: str) -> dict:
        return {"result": arg}

    @traced_agent(name="MyAgent")
    async def run_agent(task: str) -> dict:
        return {"success": True}
"""

from functools import wraps
import time
import traceback
import asyncio
import inspect
from typing import Callable, Any, TypeVar, Optional

from opentelemetry import trace
from opentelemetry.trace import SpanKind, Status, StatusCode

from .tracer import get_tracer
from .context import (
    ObservabilityContext,
    get_or_create_context,
    set_context,
    reset_context,
)
from .emitters import (
    emit_component_start,
    emit_component_end,
    emit_component_error,
)
from .serializers import safe_serialize

F = TypeVar('F', bound=Callable[..., Any])


def _get_effective_name(
    provided_name: str | None,
    args: tuple,
    func: Callable
) -> str:
    """Get effective component name, checking self.name for methods.

    Priority:
    1. If self.name exists (for class methods), use it
    2. If provided_name is given, use it
    3. Fall back to function name

    Args:
        provided_name: Name explicitly provided to decorator
        args: Function arguments (first may be self)
        func: The decorated function

    Returns:
        Effective name to use for tracing
    """
    # Check if this is a method call with self.name
    if args and hasattr(args[0], 'name'):
        instance_name = getattr(args[0], 'name', None)
        if instance_name:
            return instance_name

    # Use provided name or function name
    return provided_name or func.__name__


def traced_tool(name: str | None = None) -> Callable[[F], F]:
    """Decorator for tool functions/methods.

    Creates a child OTel span under the current active span.
    OTel automatically handles parent-child relationship.

    Automatically:
    - Creates child span context via OTel
    - Logs tool.input with full arguments
    - Logs tool.output with full result
    - Logs tool.error with stack trace on exception
    - Emits trace events for tool.triggered and tool.execution_completed
    - Re-raises exceptions after logging

    Args:
        name: Tool name for identification. If None, uses self.name from the
              instance (for class methods) or the function name as fallback.

    Usage:
        @traced_tool(name="WebSearch")
        def search(query: str, max_results: int = 10) -> dict:
            return {"results": [...]}

        # Or let it auto-detect from self.name:
        @traced_tool()
        def execute(self, **kwargs) -> dict:
            ...  # Uses self.name
    """
    def decorator(func: F) -> F:
        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                effective_name = _get_effective_name(name, args, func)
                return await _execute_with_tracing_async(func, effective_name, "tool", args, kwargs)
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                effective_name = _get_effective_name(name, args, func)
                return _execute_with_tracing_sync(func, effective_name, "tool", args, kwargs)
            return sync_wrapper
    return decorator


def traced_agent(name: str | None = None) -> Callable[[F], F]:
    """Decorator for agent run methods.

    Creates an OTel span for the agent execution.
    If called without an active parent span, this becomes the root span.

    Automatically:
    - Creates child span context via OTel
    - Logs agent.triggered with input
    - Logs agent.execution_completed with output and metrics
    - Logs agent.error with stack trace on exception
    - Emits trace events for agent lifecycle

    Args:
        name: Agent name for identification. If None, uses self.name from the
              instance (for class methods) or the function name as fallback.
    """
    def decorator(func: F) -> F:
        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                effective_name = _get_effective_name(name, args, func)
                return await _execute_with_tracing_async(func, effective_name, "agent", args, kwargs)
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                effective_name = _get_effective_name(name, args, func)
                return _execute_with_tracing_sync(func, effective_name, "agent", args, kwargs)
            return sync_wrapper
    return decorator


def traced_llm_client(provider: str) -> Callable[[F], F]:
    """Decorator for LLM client call methods.

    Creates a child OTel span for the LLM call.

    Automatically:
    - Creates child span context via OTel
    - Logs llm.request with full messages and parameters
    - Logs llm.response with full response, usage, and cost
    - Logs llm.error with stack trace on exception
    - Calculates and logs token usage and cost metrics

    The span name includes component_name if available on the LLM client instance,
    e.g., "openai:main_agent" instead of just "openai".

    Args:
        provider: LLM provider name (e.g., "openai", "anthropic")
    """
    def decorator(func: F) -> F:
        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                effective_name = _get_llm_effective_name(provider, args)
                return await _execute_with_tracing_async(func, effective_name, "llm", args, kwargs)
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                effective_name = _get_llm_effective_name(provider, args)
                return _execute_with_tracing_sync(func, effective_name, "llm", args, kwargs)
            return sync_wrapper
    return decorator


def _get_llm_effective_name(provider: str, args: tuple) -> str:
    """Get effective name for LLM client, including component context.

    Args:
        provider: Base provider name (e.g., "openai")
        args: Function arguments (first may be self with component_name)

    Returns:
        Name like "openai:main_agent" or just "openai"
    """
    if args and hasattr(args[0], 'component_name'):
        component_name = getattr(args[0], 'component_name', None)
        if component_name:
            return f"{provider}:{component_name}"
    return provider


def _prepare_input_data(args: tuple, kwargs: dict, func: Callable) -> dict:
    """Prepare input data for logging.

    Handles special cases like 'self' argument for methods.

    Args:
        args: Positional arguments
        kwargs: Keyword arguments
        func: The function being called

    Returns:
        Dictionary with serializable input data
    """
    try:
        sig = inspect.signature(func)
        params = list(sig.parameters.keys())

        # Skip 'self' or 'cls' for methods
        args_to_log = args
        if params and params[0] in ('self', 'cls') and len(args) > 0:
            args_to_log = args[1:]
            params = params[1:]

        # Build named args dict
        named_args = {}
        for i, arg in enumerate(args_to_log):
            if i < len(params):
                named_args[params[i]] = arg
            else:
                named_args[f"arg_{i}"] = arg

        return {
            "args": safe_serialize(named_args),
            "kwargs": safe_serialize(kwargs)
        }
    except Exception:
        # Fallback to simple serialization
        return {
            "args": safe_serialize(args[1:] if args else []),
            "kwargs": safe_serialize(kwargs)
        }


def _get_span_name(component_type: str, name: str) -> str:
    """Generate OTel span name.

    Args:
        component_type: Type of component (tool, agent, llm)
        name: Component name

    Returns:
        Span name in format "component_type.name"
    """
    return f"{component_type}.{name}"


def _execute_with_tracing_sync(
    func: Callable,
    name: str,
    component_type: str,
    args: tuple,
    kwargs: dict
) -> Any:
    """Core tracing execution logic for synchronous functions.

    Creates an OTel span and manages our hybrid context.

    Args:
        func: Function to execute
        name: Component name
        component_type: Type of component (tool, agent, llm)
        args: Positional arguments
        kwargs: Keyword arguments

    Returns:
        Function result

    Raises:
        Any exception from the function (after logging)
    """
    tracer = get_tracer()
    span_name = _get_span_name(component_type, name)

    # Get or create parent context (for business metadata)
    parent_ctx = get_or_create_context(name)

    # Prepare input data before starting span
    input_data = _prepare_input_data(args, kwargs, func)

    # Start OTel span - this creates proper parent-child relationship
    with tracer.start_as_current_span(
        name=span_name,
        kind=SpanKind.INTERNAL
    ) as span:
        # Set span attributes
        span.set_attribute("component.type", component_type)
        span.set_attribute("component.name", name)
        span.set_attribute("session.id", parent_ctx.session_id or "")
        span.set_attribute("request.id", parent_ctx.request_id or "")

        # Create child context with this span
        ctx = parent_ctx.create_child(name, span)
        token = set_context(ctx)

        # Log entry - ALWAYS (no level filtering)
        emit_component_start(component_type, name, ctx, input_data)

        start_time = time.perf_counter()

        try:
            result = func(*args, **kwargs)

            duration_ms = (time.perf_counter() - start_time) * 1000

            # Set span status to OK
            span.set_status(Status(StatusCode.OK))
            span.set_attribute("duration_ms", duration_ms)

            # Extract additional metrics for LLM calls
            metrics = {}
            if component_type == "llm":
                metrics = _extract_llm_metrics(result, kwargs)
                for key, value in metrics.items():
                    if isinstance(value, (str, int, float, bool)):
                        span.set_attribute(key, value)

            # Log output
            emit_component_end(
                component_type,
                name,
                ctx,
                safe_serialize(result),
                duration_ms,
                metrics
            )

            return result

        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Set span status to ERROR
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
            span.set_attribute("duration_ms", duration_ms)

            # Log error with full context
            emit_component_error(
                component_type,
                name,
                ctx,
                e,
                input_data,
                duration_ms
            )

            raise  # Re-raise after logging

        finally:
            reset_context(token)


async def _execute_with_tracing_async(
    func: Callable,
    name: str,
    component_type: str,
    args: tuple,
    kwargs: dict
) -> Any:
    """Core tracing execution logic for async functions.

    Creates an OTel span and manages our hybrid context.

    Args:
        func: Async function to execute
        name: Component name
        component_type: Type of component (tool, agent, llm)
        args: Positional arguments
        kwargs: Keyword arguments

    Returns:
        Function result

    Raises:
        Any exception from the function (after logging)
    """
    tracer = get_tracer()
    span_name = _get_span_name(component_type, name)

    # Get or create parent context (for business metadata)
    parent_ctx = get_or_create_context(name)

    # Prepare input data before starting span
    input_data = _prepare_input_data(args, kwargs, func)

    # Start OTel span - this creates proper parent-child relationship
    with tracer.start_as_current_span(
        name=span_name,
        kind=SpanKind.INTERNAL
    ) as span:
        # Set span attributes
        span.set_attribute("component.type", component_type)
        span.set_attribute("component.name", name)
        span.set_attribute("session.id", parent_ctx.session_id or "")
        span.set_attribute("request.id", parent_ctx.request_id or "")

        # Create child context with this span
        ctx = parent_ctx.create_child(name, span)
        token = set_context(ctx)

        # Log entry - ALWAYS (no level filtering)
        emit_component_start(component_type, name, ctx, input_data)

        start_time = time.perf_counter()

        try:
            result = await func(*args, **kwargs)

            duration_ms = (time.perf_counter() - start_time) * 1000

            # Set span status to OK
            span.set_status(Status(StatusCode.OK))
            span.set_attribute("duration_ms", duration_ms)

            # Extract additional metrics for LLM calls
            metrics = {}
            if component_type == "llm":
                metrics = _extract_llm_metrics(result, kwargs)
                for key, value in metrics.items():
                    if isinstance(value, (str, int, float, bool)):
                        span.set_attribute(key, value)

            # Log output
            emit_component_end(
                component_type,
                name,
                ctx,
                safe_serialize(result),
                duration_ms,
                metrics
            )

            return result

        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Set span status to ERROR
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
            span.set_attribute("duration_ms", duration_ms)

            # Log error with full context
            emit_component_error(
                component_type,
                name,
                ctx,
                e,
                input_data,
                duration_ms
            )

            raise  # Re-raise after logging

        finally:
            reset_context(token)


def _extract_llm_metrics(result: Any, kwargs: dict) -> dict:
    """Extract LLM-specific metrics from response.

    Handles various response formats from different LLM providers.

    Args:
        result: LLM response object or dict
        kwargs: Call kwargs (for model info)

    Returns:
        Dictionary with LLM metrics
    """
    metrics = {}

    # Extract from response object (OpenAI-style)
    if hasattr(result, 'usage'):
        usage = result.usage
        metrics["llm.tokens.input"] = getattr(usage, 'prompt_tokens', 0)
        metrics["llm.tokens.output"] = getattr(usage, 'completion_tokens', 0)
        metrics["llm.tokens.total"] = getattr(usage, 'total_tokens', 0)

    # Extract from dict result (our wrapper format)
    elif isinstance(result, dict):
        if "usage" in result:
            metrics["llm.tokens.input"] = result["usage"].get("prompt_tokens", 0)
            metrics["llm.tokens.output"] = result["usage"].get("completion_tokens", 0)
            metrics["llm.tokens.total"] = result["usage"].get("total_tokens", 0)

        # Handle our custom format
        if "tokens_input" in result:
            metrics["llm.tokens.input"] = result["tokens_input"]
        if "tokens_output" in result:
            metrics["llm.tokens.output"] = result["tokens_output"]
        if "tokens_total" in result:
            metrics["llm.tokens.total"] = result["tokens_total"]
        if "estimated_cost_usd" in result:
            metrics["llm.cost.total"] = result["estimated_cost_usd"]
        if "finish_reason" in result:
            metrics["llm.response.finish_reason"] = result["finish_reason"]
        if "tool_called" in result:
            metrics["llm.response.tool_called"] = result["tool_called"]

    # Model info - check result first (from LLMClient.chat), then kwargs, then fallback
    if isinstance(result, dict) and "model" in result:
        metrics["llm.model"] = result["model"]
    else:
        metrics["llm.model"] = kwargs.get("model", "unknown")

    if kwargs.get("temperature") is not None:
        metrics["llm.temperature"] = kwargs["temperature"]
    if kwargs.get("max_tokens") is not None:
        metrics["llm.max_tokens"] = kwargs["max_tokens"]

    # Filter out None values
    return {k: v for k, v in metrics.items() if v is not None}


# Convenience decorators for specific use cases

def traced_http_call(name: str = "http_request") -> Callable[[F], F]:
    """Decorator for HTTP request functions.

    Alias for traced_tool with HTTP-specific naming.
    """
    return traced_tool(name)


def traced_browser_action(name: str) -> Callable[[F], F]:
    """Decorator for browser automation actions.

    Alias for traced_tool with browser-specific naming.
    """
    return traced_tool(f"browser_{name}")


def traced_memory_operation(name: str) -> Callable[[F], F]:
    """Decorator for memory store operations.

    Alias for traced_tool with memory-specific naming.
    """
    return traced_tool(f"memory_{name}")
