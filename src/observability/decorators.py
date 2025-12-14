"""Decorator-based instrumentation for observability.

This module provides decorators that automatically handle:
- Context propagation
- Input/output logging
- Error capture with stack traces
- Timing metrics
- Trace event emission

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
from typing import Callable, Any, TypeVar, Optional, Union

from .context import (
    ObservabilityContext,
    get_or_create_context,
    set_context,
    reset_context,
)
from .emitters import (
    emit_log,
    emit_trace_event,
    emit_component_start,
    emit_component_end,
    emit_component_error,
)
from .serializers import safe_serialize

F = TypeVar('F', bound=Callable[..., Any])


def traced_tool(name: str) -> Callable[[F], F]:
    """Decorator for tool functions/methods.
    
    Automatically:
    - Creates child span context
    - Logs tool.input with full arguments
    - Logs tool.output with full result
    - Logs tool.error with stack trace on exception
    - Emits trace events for tool.triggered and tool.execution_completed
    - Re-raises exceptions after logging
    
    Args:
        name: Tool name for identification (e.g., "NavigateTool", "MemoryRead")
        
    Usage:
        @traced_tool(name="WebSearch")
        def search(query: str, max_results: int = 10) -> dict:
            return {"results": [...]}
    """
    def decorator(func: F) -> F:
        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                return await _execute_with_tracing_async(func, name, "tool", args, kwargs)
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                return _execute_with_tracing_sync(func, name, "tool", args, kwargs)
            return sync_wrapper
    return decorator


def traced_agent(name: str) -> Callable[[F], F]:
    """Decorator for agent run methods.
    
    Automatically:
    - Creates child span context
    - Logs agent.triggered with input
    - Logs agent.execution_completed with output and metrics
    - Logs agent.error with stack trace on exception
    - Emits trace events for agent lifecycle
    
    Args:
        name: Agent name for identification (e.g., "BrowserAgent", "MainAgent")
    """
    def decorator(func: F) -> F:
        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                return await _execute_with_tracing_async(func, name, "agent", args, kwargs)
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                return _execute_with_tracing_sync(func, name, "agent", args, kwargs)
            return sync_wrapper
    return decorator


def traced_llm_client(provider: str) -> Callable[[F], F]:
    """Decorator for LLM client call methods.
    
    Automatically:
    - Creates child span context
    - Logs llm.request with full messages and parameters
    - Logs llm.response with full response, usage, and cost
    - Logs llm.error with stack trace on exception
    - Calculates and logs token usage and cost metrics
    
    Args:
        provider: LLM provider name (e.g., "openai", "anthropic")
    """
    def decorator(func: F) -> F:
        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                return await _execute_with_tracing_async(func, provider, "llm", args, kwargs)
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                return _execute_with_tracing_sync(func, provider, "llm", args, kwargs)
            return sync_wrapper
    return decorator


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
    # Get function signature to understand parameters
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


def _execute_with_tracing_sync(
    func: Callable,
    name: str,
    component_type: str,
    args: tuple,
    kwargs: dict
) -> Any:
    """Core tracing execution logic for synchronous functions.
    
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
    # Get or create context
    parent_ctx = get_or_create_context(name)
    ctx = parent_ctx.create_child(name)
    token = set_context(ctx)
    
    # Prepare input data
    input_data = _prepare_input_data(args, kwargs, func)
    
    # Log entry - ALWAYS (no level filtering)
    emit_component_start(component_type, name, ctx, input_data)
    
    start_time = time.perf_counter()
    
    try:
        result = func(*args, **kwargs)
        
        duration_ms = (time.perf_counter() - start_time) * 1000
        
        # Extract additional metrics for LLM calls
        metrics = {}
        if component_type == "llm":
            metrics = _extract_llm_metrics(result, kwargs)
        
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
    # Get or create context
    parent_ctx = get_or_create_context(name)
    ctx = parent_ctx.create_child(name)
    token = set_context(ctx)
    
    # Prepare input data
    input_data = _prepare_input_data(args, kwargs, func)
    
    # Log entry - ALWAYS (no level filtering)
    emit_component_start(component_type, name, ctx, input_data)
    
    start_time = time.perf_counter()
    
    try:
        result = await func(*args, **kwargs)
        
        duration_ms = (time.perf_counter() - start_time) * 1000
        
        # Extract additional metrics for LLM calls
        metrics = {}
        if component_type == "llm":
            metrics = _extract_llm_metrics(result, kwargs)
        
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
    
    # Model info from kwargs
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
