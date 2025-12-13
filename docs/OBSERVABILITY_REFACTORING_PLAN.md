# Observability Refactoring Plan: OpenTelemetry Logs + Traces Separation

## Executive Summary

### Current State Overview
The codebase has a well-structured custom logging system with:
- Custom `StructuredLogger` with `LogEntry`, `TraceContext`, `LogMetrics` dataclasses
- Context propagation via Python's `contextvars` (`_current_logger`)
- Multiple output targets (Console, JSONLines, OpenTelemetry)
- Manual logging calls scattered throughout agents, tools, and LLM client

### Key Problems Identified

1. **Log Level Filtering Active**: The `StructuredLogger._should_log()` method filters based on `min_level`, violating the "log everything" requirement
2. **Sampling Infrastructure Exists**: `src/core/sampling.py` implements event sampling that drops logs
3. **Manual Logging Pattern**: Each component manually calls `get_logger()` and emits logs - no decorator-based automation
4. **Inconsistent Context Propagation**: Context is passed via `get_logger()` but not automatically through function calls
5. **No Trace/Log Separation**: Everything goes through `LogEntry` - no proper OpenTelemetry Traces vs Logs separation
6. **Mixed Responsibilities**: Tools log their own execution rather than having a centralized observability layer
7. **Incomplete Error Capture**: Stack traces not captured consistently; errors re-logged at multiple levels

### Proposed Solution Summary
- Implement decorator-based instrumentation (`@traced_agent`, `@traced_tool`, `@traced_llm_client`)
- Remove all log level filtering - emit everything unconditionally
- Separate OpenTelemetry Traces (spans with hierarchy) from Logs (detailed data)
- Automatic context propagation via `contextvars` with proper parent-child span relationships
- Components become "observability-unaware" - decorators handle all logging

### Expected Outcomes
- Complete observability with zero data loss
- Clean component code without logging boilerplate
- Proper distributed tracing visualization in Jaeger/Grafana
- Queryable logs in Loki/Elasticsearch with full context

---

## Current State Analysis

### 2.1 Complete Code Inventory

| File | Lines | Type | Description |
|------|-------|------|-------------|
| `src/core/structured_logger.py` | 1-481 | Core | LogLevel enum, TraceContext, LogEntry, LogMetrics, StructuredLogger class |
| `src/core/log_context.py` | 1-277 | Core | ContextVar storage, `get_logger()`, `set_logger()`, `span()` context manager, `with_span` decorator, LoggerManager |
| `src/core/log_outputs.py` | 1-536 | Core | JSONLinesOutput, ConsoleOutput, AsyncBufferedOutput, OpenTelemetryOutput, CompositeOutput |
| `src/core/log_config.py` | 1-306 | Core | LoggingConfig dataclass, MODEL_COSTS dict, `estimate_cost()` function |
| `src/core/sampling.py` | 1-259 | Core | SamplingConfig, EventSampler, SampledOutput - **PROBLEMATIC: filters logs** |
| `src/core/pii_redactor.py` | 1-214 | Core | PIIRedactor class - useful, should be preserved |
| `src/agents/base.py` | 1-221 | Agent | BaseAgent with manual slog calls for agent lifecycle, tool execution |
| `src/agents/main_agent.py` | 1-230 | Agent | MainAgent with workflow logging |
| `src/agents/browser_agent.py` | 1-97 | Agent | No additional logging beyond BaseAgent |
| `src/agents/selector_agent.py` | 1-137 | Agent | No additional logging beyond BaseAgent |
| `src/agents/accessibility_agent.py` | 1-74 | Agent | No additional logging beyond BaseAgent |
| `src/agents/data_prep_agent.py` | 1-176 | Agent | No additional logging beyond BaseAgent |
| `src/core/llm.py` | 1-139 | LLM | LLMClient with manual logging of calls and responses |
| `src/tools/base.py` | 1-39 | Tool | BaseTool abstract class - no logging |
| `src/tools/browser.py` | 1-513 | Tool | NavigateTool, GetHTMLTool, ClickTool, QuerySelectorTool, WaitTool, ExtractLinksTool - all with manual logging |
| `src/tools/memory.py` | 1-350 | Tool | MemoryStore, MemoryReadTool, MemoryWriteTool, MemorySearchTool, MemoryListTool, MemoryDumpTool - all with manual logging |
| `src/tools/extraction.py` | 1-714 | Tool | FetchAndStoreHTMLTool, BatchFetchURLsTool, RunExtractionAgentTool, BatchExtractArticlesTool, BatchExtractListingsTool - with logging |
| `src/tools/http.py` | 1-154 | Tool | HTTPRequestTool with manual logging |
| `src/tools/orchestration.py` | 1-358 | Tool | RunBrowserAgentTool, RunSelectorAgentTool, RunAccessibilityAgentTool, RunDataPrepAgentTool - with logging |
| `main.py` | 1-241 | Entry | Application entry with structured logging setup |

### 2.2 Existing Fields Inventory

| Field Name | Current Location | Type | Current Usage | Migration Plan |
|------------|------------------|------|---------------|----------------|
| `duration_ms` | LogMetrics | float | Tool/agent execution timing | Preserve as `metrics.duration_ms` |
| `time_to_first_token_ms` | LogMetrics | float | LLM streaming metric | Preserve as `llm.timing.time_to_first_token_ms` |
| `tokens_input` | LogMetrics | int | LLM input token count | Migrate to `llm.tokens.input` |
| `tokens_output` | LogMetrics | int | LLM output token count | Migrate to `llm.tokens.output` |
| `tokens_total` | LogMetrics | int | Total tokens | Migrate to `llm.tokens.total` |
| `estimated_cost_usd` | LogMetrics | float | Estimated API cost | Migrate to `llm.cost.total` |
| `retry_count` | LogMetrics | int | Retry attempts | Preserve as `metrics.retry_count` |
| `content_size_bytes` | LogMetrics | int | Content size | Preserve as `metrics.content_size_bytes` |
| `session_id` | TraceContext | str | Session identifier | Preserve at root span |
| `request_id` | TraceContext | str | Request identifier | Migrate to `trace.request_id` attribute |
| `trace_id` | TraceContext | str | Trace correlation ID | Map to OTel trace_id |
| `span_id` | TraceContext | str | Span identifier | Map to OTel span_id |
| `parent_span_id` | TraceContext | str | Parent span ID | Map to OTel parent context |
| `model` | llm.py:105 | str | LLM model name | Migrate to `llm.model` |
| `tool_called` | llm.py:98 | str | Tool name from LLM response | Preserve as `llm.response.tool_called` |
| `finish_reason` | llm.py:95 | str | LLM stop reason | Preserve as `llm.response.finish_reason` |
| `url` | Various tools | str | Target URL | Preserve as context field |
| `selector` | Browser tools | str | CSS selector | Preserve as context field |
| `success` | All results | bool | Operation success | Preserve as context field |
| `error` | Error handling | str | Error message | Migrate to `error.message` |
| `error_type` | Not captured consistently | str | Exception type | Add as `error.type` |
| `stack_trace` | Not captured | str | Full traceback | Add as `error.stack_trace` |
| `agent_name` | log_agent_lifecycle | str | Agent identifier | Preserve as `agent.name` |
| `tool_name` | log_tool_execution | str | Tool identifier | Preserve as `tool.name` |
| `iterations` | Agent results | int | Agent loop count | Preserve as `agent.iterations` |
| `message_count` | llm.py:73 | int | Message count | Preserve as `llm.request.message_count` |
| `has_tools` | llm.py:74 | bool | Whether tools provided | Preserve as `llm.request.has_tools` |
| `tool_count` | llm.py:75 | int | Number of tools | Preserve as `llm.request.tool_count` |
| `html_length` | Browser/extraction | int | HTML size | Preserve as `metrics.content_size_bytes` |
| `links_count` | ExtractLinksTool | int | Links found | Preserve as context field |

### 2.3 Current Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Application Entry (main.py)                     │
│  - Creates LoggingConfig from environment                                   │
│  - Initializes LoggerManager with outputs                                   │
│  - Sets root logger in contextvars                                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        LoggerManager (log_context.py)                        │
│  - Holds root StructuredLogger                                              │
│  - Manages singleton instance                                               │
│  - Provides initialize(), get_instance(), reset()                           │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     _current_logger: ContextVar                              │
│  - Thread-safe storage for current logger                                   │
│  - Accessed via get_logger() / set_logger()                                 │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
              ┌───────────────────────┼───────────────────────┐
              ▼                       ▼                       ▼
┌──────────────────────┐  ┌──────────────────────┐  ┌──────────────────────┐
│  MainAgent           │  │  BrowserAgent        │  │  Other Agents        │
│  - Calls get_logger()│  │  - Calls get_logger()│  │  - Calls get_logger()│
│  - Manual slog.info()│  │  - Inherits from Base│  │  - Inherits from Base│
│  - Invokes sub-agents│  │                      │  │                      │
└──────────────────────┘  └──────────────────────┘  └──────────────────────┘
              │                       │                       │
              ▼                       ▼                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            BaseAgent (base.py)                               │
│  - get_logger() at each operation                                           │
│  - slog.log_agent_lifecycle() for start/complete/error                      │
│  - slog.log_tool_execution() for tool calls                                 │
│  - slog.debug/info for iterations                                           │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Tools (browser.py, memory.py, etc.)                  │
│  - Each tool calls get_logger()                                             │
│  - Each tool manually emits slog.info/debug/error                           │
│  - Duplicates logging already done by BaseAgent._execute_tool()             │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          LLMClient (llm.py)                                  │
│  - Calls get_logger()                                                       │
│  - slog.info for call start                                                 │
│  - slog.log_llm_call for completion                                         │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      StructuredLogger (structured_logger.py)                 │
│  - _should_log(level) FILTERS based on min_level ⚠️                         │
│  - _emit() writes to all outputs                                            │
│  - Creates LogEntry with TraceContext                                       │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
              ┌───────────────────────┼───────────────────────┐
              ▼                       ▼                       ▼
┌──────────────────────┐  ┌──────────────────────┐  ┌──────────────────────┐
│  ConsoleOutput       │  │  JSONLinesOutput     │  │  OpenTelemetryOutput │
│  - Human-readable    │  │  - JSONL files       │  │  - OTLP spans        │
│  - Colored output    │  │  - For aggregators   │  │  - To Jaeger/etc     │
└──────────────────────┘  └──────────────────────┘  └──────────────────────┘
```

### 2.4 Identified Problems

#### P1: Log Level Filtering (CRITICAL)
**Location:** `src/core/structured_logger.py:243-250`
```python
def _should_log(self, level: LogLevel) -> bool:
    """Check if level should be logged."""
    return self._LEVEL_ORDER.index(level) >= self._LEVEL_ORDER.index(self.min_level)

def _emit(self, entry: LogEntry) -> None:
    """Emit log entry to all outputs."""
    if not self._should_log(entry.level):  # ⚠️ FILTERS LOGS
        return
```
**Impact:** DEBUG level logs are dropped when `min_level=INFO`

#### P2: Sampling Infrastructure (CRITICAL)
**Location:** `src/core/sampling.py:81-123`
```python
def should_sample(self, entry: LogEntry) -> bool:
    """Determine if a log entry should be sampled (logged)."""
    if not self.config.enabled:
        return True  # Sampling disabled, log everything
    # ... sampling logic that can DROP logs
```
**Impact:** High-volume events like `memory.read` sampled at 10%

#### P3: Manual Logging Everywhere
**Locations:**
- `src/agents/base.py:48-69, 115-143` - Agent lifecycle
- `src/tools/browser.py:34-86` - Each tool method
- `src/core/llm.py:63-112` - LLM calls

**Impact:**
- Boilerplate code in every component
- Inconsistent logging patterns
- Easy to forget logging in new code

#### P4: Duplicate Logging
**Example:** Tool execution logged twice:
1. `BaseAgent._execute_tool()` at `src/agents/base.py:175-203`
2. Each tool's own logging (e.g., `NavigateTool.execute()` at `src/tools/browser.py:31-86`)

#### P5: No Automatic Context Propagation
Context requires manual `get_logger()` calls. The `span()` context manager exists but isn't used consistently. No automatic parent-child span relationships.

#### P6: Incomplete Error Capture
- Stack traces not captured consistently
- Error type (`type(e).__name__`) captured inconsistently
- Original input/args not always included with errors

#### P7: Mixed Trace/Log Concerns
`OpenTelemetryOutput` creates spans from `LogEntry` objects, but there's no distinction between:
- Traces (timing spans with hierarchy)
- Logs (detailed data events)

---

## Gap Analysis

| Current State | Target State | Gap | Priority |
|---------------|--------------|-----|----------|
| `_should_log()` filters by level | Always emit, level is metadata | Remove filtering logic | P0 - Critical |
| `SamplingConfig` drops events | No sampling at emission | Remove/disable sampling | P0 - Critical |
| Manual `slog.xxx()` calls | Decorator-based instrumentation | Implement decorators | P0 - Critical |
| `get_logger()` at each site | Automatic context inheritance | Enhance context manager | P1 - High |
| Stack traces sometimes captured | Always capture on error | Update error handling | P1 - High |
| Tool logs own execution | Decorator handles all logging | Remove tool logging | P1 - High |
| Single `LogEntry` for all | Separate Trace Events + Logs | Implement dual emission | P1 - High |
| Inconsistent field names | Standardized OTel semantic conventions | Refactor field names | P2 - Medium |
| No `triggered_by` field | Track caller component | Add to context | P2 - Medium |
| PII redaction in place | Keep and integrate | Preserve redactor | P3 - Low |

---

## Target Architecture Design

### 4.1 Context Propagation Mechanism

```python
# src/observability/context.py
import contextvars
from dataclasses import dataclass, field
from typing import Optional, List
import uuid
from datetime import datetime, timezone

# Global context storage - single source of truth
_observability_context: contextvars.ContextVar['ObservabilityContext'] = \
    contextvars.ContextVar('observability_context', default=None)

@dataclass
class ObservabilityContext:
    """Immutable observability context for correlation."""
    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    component_stack: List[str] = field(default_factory=list)
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def get_current(cls) -> Optional['ObservabilityContext']:
        """Get current context from contextvars."""
        return _observability_context.get()

    @classmethod
    def create_root(cls, session_id: str = None) -> 'ObservabilityContext':
        """Create a new root context (no parent)."""
        return cls(
            trace_id=f"trace_{uuid.uuid4().hex[:16]}",
            span_id=f"span_{uuid.uuid4().hex[:12]}",
            parent_span_id=None,
            session_id=session_id or f"sess_{uuid.uuid4().hex[:12]}",
            request_id=f"req_{uuid.uuid4().hex[:12]}",
            component_stack=["root"]
        )

    def create_child(self, component_name: str) -> 'ObservabilityContext':
        """Create a child context inheriting trace_id."""
        return ObservabilityContext(
            trace_id=self.trace_id,
            span_id=f"span_{uuid.uuid4().hex[:12]}",
            parent_span_id=self.span_id,
            session_id=self.session_id,
            request_id=self.request_id,
            component_stack=[*self.component_stack, component_name]
        )

    @property
    def triggered_by(self) -> str:
        """Get the name of the parent component."""
        if len(self.component_stack) > 1:
            return self.component_stack[-2]
        return "direct_call"

def get_or_create_context(component_name: str = "unknown") -> 'ObservabilityContext':
    """Get current context or create root if none exists."""
    ctx = _observability_context.get()
    if ctx is None:
        ctx = ObservabilityContext.create_root()
        ctx = ObservabilityContext(
            trace_id=ctx.trace_id,
            span_id=ctx.span_id,
            parent_span_id=None,
            session_id=ctx.session_id,
            request_id=ctx.request_id,
            component_stack=[component_name]
        )
    return ctx
```

### 4.2 Decorator Specifications

```python
# src/observability/decorators.py
from functools import wraps
import time
import traceback
import asyncio
from typing import Callable, Any, TypeVar, Union
from .context import ObservabilityContext, _observability_context, get_or_create_context
from .emitters import emit_log, emit_trace_event
from .serializers import safe_serialize

F = TypeVar('F', bound=Callable[..., Any])

def traced_tool(name: str) -> Callable[[F], F]:
    """
    Decorator for tool functions/methods.

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
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            return _execute_with_tracing(func, name, "tool", args, kwargs, is_async=False)

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            return await _execute_with_tracing(func, name, "tool", args, kwargs, is_async=True)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    return decorator


def traced_agent(name: str) -> Callable[[F], F]:
    """
    Decorator for agent run methods.

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
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            return _execute_with_tracing(func, name, "agent", args, kwargs, is_async=False)

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            return await _execute_with_tracing(func, name, "agent", args, kwargs, is_async=True)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    return decorator


def traced_llm_client(provider: str) -> Callable[[F], F]:
    """
    Decorator for LLM client call methods.

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
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            return _execute_with_tracing(func, provider, "llm_client", args, kwargs, is_async=False)

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            return await _execute_with_tracing(func, provider, "llm_client", args, kwargs, is_async=True)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    return decorator


def _execute_with_tracing(
    func: Callable,
    name: str,
    component_type: str,
    args: tuple,
    kwargs: dict,
    is_async: bool
) -> Any:
    """Core tracing execution logic."""
    # Get or create context
    parent_ctx = get_or_create_context(name)
    ctx = parent_ctx.create_child(name)
    token = _observability_context.set(ctx)

    # Prepare input data
    input_data = {
        "args": safe_serialize(args[1:]) if args else [],  # Skip self
        "kwargs": safe_serialize(kwargs)
    }

    # Log entry - ALWAYS (no level filtering)
    emit_log(
        level="DEBUG",
        event=f"{component_type}.input",
        ctx=ctx,
        data={
            f"{component_type}_name": name,
            "triggered_by": ctx.triggered_by,
            "input": input_data
        }
    )

    # Emit trace event
    emit_trace_event(f"{component_type}.triggered", ctx, {
        f"{component_type}_name": name,
        "triggered_by": ctx.triggered_by
    })

    start_time = time.perf_counter()

    try:
        if is_async:
            import asyncio
            result = asyncio.get_event_loop().run_until_complete(func(*args, **kwargs))
        else:
            result = func(*args, **kwargs)

        duration_ms = (time.perf_counter() - start_time) * 1000

        # Log output - ALWAYS
        output_data = {
            f"{component_type}_name": name,
            "output": safe_serialize(result),
            "duration_ms": duration_ms
        }

        # Add LLM-specific metrics
        if component_type == "llm_client":
            output_data.update(_extract_llm_metrics(result, kwargs))

        emit_log(
            level="DEBUG",
            event=f"{component_type}.output",
            ctx=ctx,
            data=output_data,
            metrics={"duration_ms": duration_ms}
        )

        # Emit trace event
        emit_trace_event(f"{component_type}.execution_completed", ctx, {
            f"{component_type}_name": name,
            "duration_ms": duration_ms,
            **(_extract_llm_metrics(result, kwargs) if component_type == "llm_client" else {})
        })

        return result

    except Exception as e:
        duration_ms = (time.perf_counter() - start_time) * 1000

        # Log error - ALWAYS with full context
        emit_log(
            level="ERROR",
            event=f"{component_type}.error",
            ctx=ctx,
            data={
                f"{component_type}_name": name,
                "triggered_by": ctx.triggered_by,
                "error_type": type(e).__name__,
                "error_message": str(e),
                "stack_trace": traceback.format_exc(),
                "input": input_data,
                "duration_ms": duration_ms
            },
            metrics={"duration_ms": duration_ms}
        )

        # Emit trace event
        emit_trace_event(f"{component_type}.error", ctx, {
            f"{component_type}_name": name,
            "error_type": type(e).__name__,
            "error_message": str(e)
        })

        raise  # Re-raise after logging

    finally:
        _observability_context.reset(token)


def _extract_llm_metrics(result: Any, kwargs: dict) -> dict:
    """Extract LLM-specific metrics from response."""
    metrics = {}

    # Extract from response object (OpenAI-style)
    if hasattr(result, 'usage'):
        usage = result.usage
        metrics["llm.tokens.input"] = getattr(usage, 'prompt_tokens', 0)
        metrics["llm.tokens.output"] = getattr(usage, 'completion_tokens', 0)
        metrics["llm.tokens.total"] = getattr(usage, 'total_tokens', 0)

    # Extract from dict result
    elif isinstance(result, dict):
        if "usage" in result:
            metrics["llm.tokens.input"] = result["usage"].get("prompt_tokens", 0)
            metrics["llm.tokens.output"] = result["usage"].get("completion_tokens", 0)
        if "tokens_input" in result:
            metrics["llm.tokens.input"] = result["tokens_input"]
        if "tokens_output" in result:
            metrics["llm.tokens.output"] = result["tokens_output"]

    # Model info from kwargs
    metrics["llm.model"] = kwargs.get("model", "unknown")
    metrics["llm.temperature"] = kwargs.get("temperature")
    metrics["llm.max_tokens"] = kwargs.get("max_tokens")

    return {k: v for k, v in metrics.items() if v is not None}
```

### 4.3 Log Schema

```python
# src/observability/schema.py
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional, Dict, List
from enum import Enum

class ComponentType(Enum):
    AGENT = "agent"
    TOOL = "tool"
    LLM_CLIENT = "llm_client"

@dataclass
class LogRecord:
    """
    Complete log record for unconditional emission.

    Level is METADATA ONLY, never used for filtering.
    """
    # Timing
    timestamp: datetime

    # Identity (from ObservabilityContext)
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    session_id: Optional[str]
    request_id: Optional[str]

    # Event classification
    level: str  # "DEBUG", "INFO", "WARNING", "ERROR" - metadata only!
    event: str  # e.g., "tool.input", "agent.error", "llm.response"

    # Component info
    component_type: str  # "agent", "tool", "llm_client"
    component_name: str  # e.g., "BrowserAgent", "NavigateTool"
    triggered_by: str    # Parent component name

    # Data payload (no truncation!)
    data: Dict[str, Any] = field(default_factory=dict)

    # Metrics
    metrics: Dict[str, Any] = field(default_factory=dict)

    # Tags for filtering at query time
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Serialize to dict for output."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "session_id": self.session_id,
            "request_id": self.request_id,
            "level": self.level,
            "event": self.event,
            "component_type": self.component_type,
            "component_name": self.component_name,
            "triggered_by": self.triggered_by,
            "data": self.data,
            "metrics": self.metrics,
            "tags": self.tags
        }
```

### 4.4 Trace Schema

```python
# Trace Events Taxonomy

TRACE_EVENTS = {
    # Agent events
    "agent.triggered": "Agent execution started",
    "agent.llm_call_started": "Agent initiated LLM call",
    "agent.llm_call_completed": "Agent received LLM response",
    "agent.tool_selected": "Agent decided to use a tool",
    "agent.execution_completed": "Agent finished successfully",
    "agent.error": "Agent failed",

    # Tool events
    "tool.triggered": "Tool execution started",
    "tool.execution_completed": "Tool finished successfully",
    "tool.error": "Tool failed",

    # LLM client events
    "llm.request_started": "LLM API call initiated",
    "llm.response_received": "LLM response fully received",
    "llm.stream_chunk": "Streaming chunk received (optional)",
    "llm.error": "LLM call failed"
}

# Required attributes on ALL trace events
REQUIRED_TRACE_ATTRIBUTES = [
    "trace_id",
    "span_id",
    "parent_span_id",
    "component_type",
    "component_name",
    "triggered_by",
    "timestamp",
    "event"
]

# LLM-specific trace attributes
LLM_TRACE_ATTRIBUTES = [
    "llm.tokens.input",
    "llm.tokens.output",
    "llm.tokens.total",
    "llm.cost.input",
    "llm.cost.output",
    "llm.cost.total",
    "llm.model",
    "llm.provider",
    "llm.temperature",
    "llm.max_tokens",
    "duration_ms",
    "time_to_first_token_ms"
]
```

### 4.5 Preserved Fields Mapping

| Old Field | New Field | Location |
|-----------|-----------|----------|
| `LogMetrics.duration_ms` | `metrics.duration_ms` | Preserved |
| `LogMetrics.time_to_first_token_ms` | `llm.timing.time_to_first_token_ms` | LLM events |
| `LogMetrics.tokens_input` | `llm.tokens.input` | LLM events |
| `LogMetrics.tokens_output` | `llm.tokens.output` | LLM events |
| `LogMetrics.tokens_total` | `llm.tokens.total` | LLM events |
| `LogMetrics.estimated_cost_usd` | `llm.cost.total` | LLM events |
| `LogMetrics.content_size_bytes` | `metrics.content_size_bytes` | Preserved |
| `TraceContext.session_id` | `session_id` | Root level |
| `TraceContext.request_id` | `request_id` | Root level |
| `TraceContext.trace_id` | `trace_id` | Root level |
| `TraceContext.span_id` | `span_id` | Root level |
| `TraceContext.parent_span_id` | `parent_span_id` | Root level |
| `context.model_name` | `llm.model` | LLM events |
| `context.tool_name` | `tool.name` | Tool events |
| `context.agent_name` | `agent.name` | Agent events |
| `data.error` | `error.message` | Error events |
| N/A (new) | `error.type` | Error events |
| N/A (new) | `error.stack_trace` | Error events |
| N/A (new) | `triggered_by` | All events |

---

## File-by-File Change Specification

### File: src/core/structured_logger.py

#### Summary
- Total lines affected: ~50
- Lines to remove: 8
- Lines to modify: 12
- New lines to add: 0

#### Lines to REMOVE:

**L243-250: Log level filtering**
```python
def _should_log(self, level: LogLevel) -> bool:
    """Check if level should be logged."""
    return self._LEVEL_ORDER.index(level) >= self._LEVEL_ORDER.index(self.min_level)

def _emit(self, entry: LogEntry) -> None:
    """Emit log entry to all outputs."""
    if not self._should_log(entry.level):
        return
```
**Reason:** Log level filtering violates "log everything" requirement

#### Lines to MODIFY:

**L247-256: Remove filtering from _emit**
**Current:**
```python
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
```
**New:**
```python
def _emit(self, entry: LogEntry) -> None:
    """Emit log entry to all outputs unconditionally.

    Note: Level is metadata only, never used for filtering.
    All events are always emitted.
    """
    for output in self.outputs:
        try:
            output.write(entry)
        except Exception:
            # Don't let logging failures break the application
            pass
```

**L222: Remove min_level default**
**Current:**
```python
min_level: LogLevel = LogLevel.INFO,
```
**New:**
```python
min_level: LogLevel = LogLevel.DEBUG,  # Kept for backward compat, not used for filtering
```

#### Validation Checklist:
- [ ] `_should_log` method removed or always returns True
- [ ] `_emit` no longer checks level
- [ ] All existing LogEntry structure preserved
- [ ] LogMetrics fields unchanged

---

### File: src/core/sampling.py

#### Summary
- Total lines affected: Entire file (259 lines)
- Recommendation: **DISABLE by default or REMOVE**

#### Lines to MODIFY:

**L61: Disable sampling by default**
**Current:**
```python
enabled: bool = True
```
**New:**
```python
enabled: bool = False  # DISABLED: All events must be logged
```

**L26-27: Set global rate to 1.0**
**Current:**
```python
# Global sampling rate (0.0 to 1.0, where 1.0 = log everything)
global_rate: float = 1.0
```
**New:**
```python
# Global sampling rate - MUST be 1.0 (log everything)
# Sampling at emission time violates observability requirements
global_rate: float = 1.0  # DO NOT CHANGE
```

#### Alternative: Remove File Entirely
If sampling is never desired, delete `src/core/sampling.py` and remove all references:
- `src/core/log_config.py:59-65` (sampling_enabled, sampling_rate, sampled_event_types)

#### Validation Checklist:
- [ ] Sampling disabled by default
- [ ] No events dropped at emission time
- [ ] Sampling config parameters documented as "do not use"

---

### File: src/core/log_config.py

#### Summary
- Total lines affected: ~20
- Lines to remove: 0
- Lines to modify: 15

#### Lines to MODIFY:

**L37: Default to DEBUG level**
**Current:**
```python
min_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
```
**New:**
```python
min_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "DEBUG"  # Log everything
```

**L59-60: Disable sampling**
**Current:**
```python
sampling_enabled: bool = False
sampling_rate: float = 1.0  # 1.0 = log everything
```
**New:**
```python
# IMPORTANT: Sampling must stay disabled - we log everything
sampling_enabled: bool = False  # DO NOT ENABLE
sampling_rate: float = 1.0      # DO NOT CHANGE
```

**L186-195: Update development config**
**Current:**
```python
@classmethod
def development(cls) -> "LoggingConfig":
    return cls(
        min_level="DEBUG",
        ...
        sampling_enabled=False,
```
**New:**
```python
@classmethod
def development(cls) -> "LoggingConfig":
    """Development config - logs everything (same as production)."""
    return cls(
        min_level="DEBUG",  # Level is metadata, not filter
        ...
        sampling_enabled=False,  # Never sample
```

**L197-217: Update production config**
**Current:**
```python
@classmethod
def production(cls) -> "LoggingConfig":
    return cls(
        min_level="INFO",
        ...
        sampling_enabled=False,  # Enable if needed for high volume
```
**New:**
```python
@classmethod
def production(cls) -> "LoggingConfig":
    """Production config - logs everything (same as development).

    Note: Level is metadata only. All events are logged.
    Filter at query time, not emission time.
    """
    return cls(
        min_level="DEBUG",  # Log everything, level is metadata
        ...
        sampling_enabled=False,  # NEVER enable - filter at query time
```

#### Validation Checklist:
- [ ] Default min_level is DEBUG
- [ ] sampling_enabled defaults to False
- [ ] Production config logs everything
- [ ] Comments explain "log everything" philosophy

---

### File: src/agents/base.py

#### Summary
- Total lines affected: ~150
- Lines to remove: ~80 (manual logging)
- Lines to modify: ~20 (decorator application)
- New imports to add: 5

#### Lines to REMOVE:

**L43-69: Manual agent lifecycle logging in run()**
```python
# Get structured logger and create agent span
slog = get_logger()
start_time = time.perf_counter()

# Log agent start
if slog:
    slog.log_agent_lifecycle(
        agent_name=self.name,
        event_type="agent.start",
        message=f"Agent {self.name} started with task: {task[:100]}...",
    )

for iteration in range(MAX_ITERATIONS):
    logger.info(f"Agent {self.name} iteration {iteration + 1}")

    # Log iteration
    if slog:
        slog.debug(
            event=LogEvent(
                category=EventCategory.AGENT_LIFECYCLE,
                event_type="agent.iteration",
                name=f"{self.name} iteration",
            ),
            message=f"Agent {self.name} iteration {iteration + 1}",
            data={"iteration": iteration + 1, "max_iterations": MAX_ITERATIONS},
            tags=["agent", self.name, "iteration"],
        )
```
**Reason:** Replaced by @traced_agent decorator

**L112-144: Manual completion/error logging**
```python
duration_ms = (time.perf_counter() - start_time) * 1000

# Log agent completion
if slog:
    slog.log_agent_lifecycle(
        agent_name=self.name,
        event_type="agent.complete",
        ...
    )
# ... and max iterations logging
```
**Reason:** Decorator handles completion/error logging

**L155-220: Manual tool execution logging in _execute_tool()**
```python
slog = get_logger()

if name not in self._tool_map:
    # Log unknown tool error
    if slog:
        slog.log_tool_execution(...)

# ... all the manual logging for tool start/complete/error
```
**Reason:** Tools will have @traced_tool decorator

#### Lines to MODIFY:

**L7-9: Update imports**
**Current:**
```python
from ..core.log_context import get_logger, span
from ..core.structured_logger import (
    EventCategory, LogEvent, LogLevel, LogLevelDetail, LogMetrics
)
```
**New:**
```python
from ..observability.decorators import traced_agent
# Remove unused imports
```

**L29: Add decorator to run method**
**Current:**
```python
def run(self, task: str) -> dict[str, Any]:
```
**New:**
```python
@traced_agent(name="BaseAgent")  # Subclasses should override
def run(self, task: str) -> dict[str, Any]:
```

#### Code to ADD:

**After L27: Property for agent name in decorator**
```python
def __init__(self, llm: LLMClient, tools: list[BaseTool] | None = None):
    self.llm = llm
    self.tools = tools or []
    self._tool_map = {t.name: t for t in self.tools}

# Note: Subclasses override `name` class attribute which decorator uses
```

#### Validation Checklist:
- [ ] All manual slog calls removed from run()
- [ ] All manual slog calls removed from _execute_tool()
- [ ] @traced_agent decorator applied to run()
- [ ] Legacy `logger` calls can remain for backward compat (optional)
- [ ] Agent name correctly passed to decorator

---

### File: src/agents/main_agent.py

#### Summary
- Total lines affected: ~70
- Lines to remove: ~50 (manual logging)
- Lines to modify: ~10

#### Lines to REMOVE:

**L159-173: Manual workflow start logging**
```python
slog = get_logger()
start_time = time.perf_counter()

# Log workflow start
if slog:
    slog.info(
        event=LogEvent(...),
        message=f"Starting crawl plan creation for {url}",
        ...
    )
```
**Reason:** Decorator handles entry logging

**L190-227: Manual completion/error logging**
```python
duration_ms = (time.perf_counter() - start_time) * 1000

# Log workflow completion
if slog:
    if result.get("success"):
        slog.info(...)
    else:
        slog.error(...)
```
**Reason:** Decorator handles completion/error logging

#### Lines to MODIFY:

**L14-17: Update imports**
**Current:**
```python
from ..core.log_context import get_logger
from ..core.structured_logger import (
    EventCategory, LogEvent, LogMetrics
)
```
**New:**
```python
from ..observability.decorators import traced_agent
```

**L157: Add decorator**
**Current:**
```python
def create_crawl_plan(self, url: str) -> dict[str, Any]:
```
**New:**
```python
@traced_agent(name="MainAgent.create_crawl_plan")
def create_crawl_plan(self, url: str) -> dict[str, Any]:
```

#### Validation Checklist:
- [ ] All manual logging removed from create_crawl_plan
- [ ] @traced_agent decorator applied
- [ ] Result still returned correctly
- [ ] Exception handling preserved (re-raised after logging)

---

### File: src/core/llm.py

#### Summary
- Total lines affected: ~60
- Lines to remove: ~40 (manual logging)
- Lines to modify: ~10

#### Lines to REMOVE:

**L58-79: Manual LLM call start logging**
```python
# Get structured logger if available
slog = get_logger()

# Log LLM call start
logger.debug(f"LLM request with {len(messages)} messages")
if slog:
    slog.info(
        event=LogEvent(...),
        message=f"LLM call to {self.config.model} with {len(messages)} messages",
        ...
    )
```
**Reason:** Decorator handles request logging

**L100-112: Manual LLM call completion logging**
```python
logger.debug(f"LLM response: {finish_reason}")

# Log LLM call completion with metrics
if slog:
    slog.log_llm_call(
        model=self.config.model,
        tokens_input=tokens_input,
        ...
    )
```
**Reason:** Decorator handles response logging with metrics

#### Lines to MODIFY:

**L11-14: Update imports**
**Current:**
```python
from .log_context import get_logger
from .structured_logger import (
    EventCategory, LogEvent, LogLevel, LogLevelDetail, LogMetrics
)
```
**New:**
```python
from ..observability.decorators import traced_llm_client
```

**L27: Add decorator to chat method**
**Current:**
```python
def chat(
    self,
    messages: list[dict[str, Any]],
    ...
) -> dict[str, Any]:
```
**New:**
```python
@traced_llm_client(provider="openai")
def chat(
    self,
    messages: list[dict[str, Any]],
    ...
) -> dict[str, Any]:
```

#### Validation Checklist:
- [ ] All manual logging removed from chat()
- [ ] @traced_llm_client decorator applied
- [ ] Token metrics still captured (by decorator)
- [ ] Cost estimation still works (integrate with decorator)

---

### File: src/tools/browser.py

#### Summary
- Total lines affected: ~400
- Lines to remove: ~250 (manual logging in each tool)
- Lines to modify: ~30 (decorator applications)

#### Lines to REMOVE (per tool):

**Example: NavigateTool (L26-88) - Remove manual logging**
```python
def execute(self, url: str) -> dict[str, Any]:
    slog = get_logger()
    start_time = time.perf_counter()

    try:
        logger.info(f">>> BROWSER NAVIGATING TO: {url}")

        # Log navigation start
        if slog:
            slog.info(
                event=LogEvent(...),
                ...
            )
        # ... 60 lines of manual logging
```
**Reason:** @traced_tool decorator handles all logging

#### Lines to MODIFY:

**L7-12: Update imports**
**Current:**
```python
from ..core.log_context import get_logger
from ..core.structured_logger import (
    EventCategory, LogEvent, LogLevel, LogLevelDetail, LogMetrics
)
```
**New:**
```python
from ..observability.decorators import traced_tool
```

**Each execute method: Add decorator**

**NavigateTool.execute (L26):**
```python
@traced_tool(name="browser_navigate")
def execute(self, url: str) -> dict[str, Any]:
    result = self.session.navigate(url)
    return {
        "success": True,
        "result": f"Navigated to {url}",
        "details": result
    }
```

**GetHTMLTool.execute (L114):**
```python
@traced_tool(name="browser_get_html")
def execute(self, raw: bool = False) -> dict[str, Any]:
    html = self.session.get_html()
    # ... processing logic only, no logging
    return {"success": True, "result": html, ...}
```

**ClickTool.execute (L207):**
```python
@traced_tool(name="browser_click")
def execute(self, selector: str) -> dict[str, Any]:
    result = self.session.click(selector)
    return {"success": result.get("success"), ...}
```

**QuerySelectorTool.execute (L287):**
```python
@traced_tool(name="browser_query")
def execute(self, selector: str) -> dict[str, Any]:
    elements = self.session.query_selector_all(selector)
    return {"success": True, "result": elements, "count": len(elements)}
```

**WaitTool.execute (L351):**
```python
@traced_tool(name="browser_wait")
def execute(self, selector: str | None = None, seconds: int | None = None) -> dict[str, Any]:
    # ... logic only, no logging
```

**ExtractLinksTool.execute (L464):**
```python
@traced_tool(name="browser_extract_links")
def execute(self) -> dict[str, Any]:
    elements = self.session.query_selector_all("a[href]")
    links = [...]
    return {"success": True, "result": links, "count": len(links)}
```

#### Validation Checklist:
- [ ] All 6 browser tools have @traced_tool decorator
- [ ] All manual slog/logger calls removed
- [ ] Return values unchanged
- [ ] Exception handling via decorator (remove try/except for logging)

---

### File: src/tools/memory.py

#### Summary
- Total lines affected: ~200
- Lines to remove: ~100 (manual logging)
- Lines to modify: ~20

#### Pattern to apply to each tool:

**MemoryReadTool.execute (L92-114):**
**Current:**
```python
def execute(self, key: str) -> dict[str, Any]:
    slog = get_logger()
    value = self.store.read(key)
    found = value is not None

    # Log memory read
    if slog:
        value_preview = str(value)[:100] + "..." if value and len(str(value)) > 100 else str(value)
        slog.debug(
            event=LogEvent(...),
            ...
        )

    return {"success": True, "result": value}
```
**New:**
```python
@traced_tool(name="memory_read")
def execute(self, key: str) -> dict[str, Any]:
    value = self.store.read(key)
    return {"success": True, "result": value}
```

Apply same pattern to:
- `MemoryWriteTool.execute` (L138-169) -> `@traced_tool(name="memory_write")`
- `MemorySearchTool.execute` (L196-216) -> `@traced_tool(name="memory_search")`
- `MemoryListTool.execute` (L240-260) -> `@traced_tool(name="memory_list")`
- `MemoryDumpTool.execute` (L279-332) -> `@traced_tool(name="memory_dump")`

#### Validation Checklist:
- [ ] All 5 memory tools have @traced_tool decorator
- [ ] All manual logging removed
- [ ] MemoryStore class unchanged (no logging there)

---

### File: src/tools/orchestration.py

#### Summary
- Total lines affected: ~300
- Lines to remove: ~200 (manual logging)
- Lines to modify: ~20

#### Pattern for each orchestration tool:

**RunBrowserAgentTool.execute (L25-85):**
**Current:**
```python
def execute(self, task: str) -> dict[str, Any]:
    slog = get_logger()
    start_time = time.perf_counter()

    # Log sub-agent invocation start
    if slog:
        slog.info(...)

    try:
        result = self.browser_agent.run(task)
        duration_ms = (time.perf_counter() - start_time) * 1000

        # Log sub-agent completion
        if slog:
            slog.info(...)

        return {...}
    except Exception as e:
        # Log error
        if slog:
            slog.error(...)
        return {"success": False, "error": str(e)}
```
**New:**
```python
@traced_tool(name="run_browser_agent")
def execute(self, task: str) -> dict[str, Any]:
    result = self.browser_agent.run(task)
    return {
        "success": result["success"],
        "result": result.get("result", result.get("error")),
        "iterations": result.get("iterations", 0)
    }
```

Apply same pattern to:
- `RunSelectorAgentTool.execute` -> `@traced_tool(name="run_selector_agent")`
- `RunAccessibilityAgentTool.execute` -> `@traced_tool(name="run_accessibility_agent")`
- `RunDataPrepAgentTool.execute` -> `@traced_tool(name="run_data_prep_agent")`

#### Validation Checklist:
- [ ] All 4 orchestration tools have @traced_tool decorator
- [ ] Manual timing removed (decorator handles)
- [ ] Manual logging removed
- [ ] Sub-agent calls still work (they have their own @traced_agent)

---

### File: src/tools/extraction.py

#### Summary
- Total lines affected: ~400
- Lines to remove: ~200 (manual logging)
- Lines to modify: ~30

#### Tools to update:

1. `FetchAndStoreHTMLTool.execute` (L31-92) -> `@traced_tool(name="fetch_and_store_html")`
2. `BatchFetchURLsTool.execute` (L118-229) -> `@traced_tool(name="batch_fetch_urls")`
3. `RunExtractionAgentTool.execute` (L255-322) -> `@traced_tool(name="run_extraction_agent")`
4. `BatchExtractArticlesTool.execute` (L423-453) -> `@traced_tool(name="batch_extract_articles")`
5. `RunListingExtractionAgentTool.execute` (L477-540) -> `@traced_tool(name="run_listing_extraction_agent")`
6. `BatchExtractListingsTool.execute` (L641-698) -> `@traced_tool(name="batch_extract_listings")`

#### Special consideration for batch tools:

BatchFetchURLsTool has progress logging that's useful. Options:
1. Keep batch summary logging within method (acceptable)
2. Create separate observability helper for batch progress

**Recommended approach for batches:**
```python
@traced_tool(name="batch_fetch_urls")
def execute(self, urls: list[str], key_prefix: str = "fetched", wait_seconds: int = 3) -> dict[str, Any]:
    results = []
    for i, url in enumerate(urls):
        # Each individual fetch is traced via context
        self._fetch_single(url, f"{key_prefix}-{i+1}", wait_seconds, results)

    successful = sum(1 for r in results if r.get("success"))
    return {
        "success": successful > 0,
        "result": f"Fetched {successful}/{len(urls)} URLs",
        "fetched_count": successful,
        "failed_count": len(urls) - successful,
        "memory_keys": [r["memory_key"] for r in results if r.get("success")]
    }

@traced_tool(name="batch_fetch_urls.item")
def _fetch_single(self, url: str, memory_key: str, wait_seconds: int, results: list):
    # Individual fetch logic
```

#### Validation Checklist:
- [ ] All 6 extraction tools have @traced_tool decorator
- [ ] Batch progress tracking preserved where needed
- [ ] LLM calls within tools traced automatically (nested context)

---

### File: src/tools/http.py

#### Summary
- Total lines affected: ~80
- Lines to remove: ~40
- Lines to modify: ~10

#### Lines to MODIFY:

**L25-127: Simplify execute method**
**Current:**
```python
def execute(self, url: str, method: str = "GET", ...) -> dict[str, Any]:
    slog = get_logger()
    start_time = time.perf_counter()

    if slog:
        slog.info(...)

    # ... request logic with manual logging throughout
```
**New:**
```python
@traced_tool(name="http_request")
def execute(self, url: str, method: str = "GET", ...) -> dict[str, Any]:
    async def _request():
        # ... async request logic

    loop = asyncio.new_event_loop()
    result = loop.run_until_complete(_request())
    loop.close()

    return {"success": True, "result": result}
```

#### Validation Checklist:
- [ ] @traced_tool decorator applied
- [ ] All manual logging removed
- [ ] Async execution still works

---

### File: main.py

#### Summary
- Total lines affected: ~50
- Lines to modify: ~30
- Key changes: Initialize new observability system

#### Lines to MODIFY:

**L18-23: Update imports**
**Current:**
```python
# Structured logging imports
from src.core.log_config import LoggingConfig
from src.core.log_context import LoggerManager, get_logger
from src.core.structured_logger import (
    EventCategory, LogEvent, LogLevel, LogLevelDetail
)
```
**New:**
```python
# Observability imports
from src.observability import initialize_observability, ObservabilityConfig
from src.observability.context import ObservabilityContext
```

**L37-60: Update setup_structured_logging**
**Current:**
```python
def setup_structured_logging(level: str) -> LoggerManager:
    config = LoggingConfig.from_env()
    config.min_level = level.upper()
    outputs = config.create_outputs()
    manager = LoggerManager.initialize(...)
    return manager
```
**New:**
```python
def setup_observability() -> None:
    """Initialize the observability system.

    Note: Level parameter removed - we always log everything.
    Level is metadata only, filtering happens at query time.
    """
    config = ObservabilityConfig.from_env()
    initialize_observability(config)
```

**L80-98: Simplify main() logging setup**
**Current:**
```python
# Setup both legacy and structured logging
setup_logging(args.log_level)
legacy_logger = logging.getLogger(__name__)

# Initialize structured logging
log_manager = setup_structured_logging(args.log_level)
slog = log_manager.root_logger

# Log application start
slog.info(
    event=LogEvent(...),
    ...
)
```
**New:**
```python
# Setup legacy logging for third-party libraries
setup_logging(args.log_level)

# Initialize observability (logs everything, level is metadata)
setup_observability()

# Application start is logged automatically by traced entry point
```

#### Validation Checklist:
- [ ] Observability initialized before any traced code runs
- [ ] Legacy logging kept for non-instrumented code
- [ ] No manual structured logging calls in main()

---

## New Files to Create

### File: src/observability/__init__.py

```python
"""
Observability module for unconditional logging and tracing.

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
"""

from .config import ObservabilityConfig, initialize_observability
from .context import ObservabilityContext, get_or_create_context
from .decorators import traced_agent, traced_tool, traced_llm_client
from .emitters import emit_log, emit_trace_event

__all__ = [
    "ObservabilityConfig",
    "initialize_observability",
    "ObservabilityContext",
    "get_or_create_context",
    "traced_agent",
    "traced_tool",
    "traced_llm_client",
    "emit_log",
    "emit_trace_event",
]
```

### File: src/observability/config.py

```python
"""Configuration for the observability system."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from .outputs import LogOutput, ConsoleOutput, JSONLinesOutput, OTLPOutput

@dataclass
class ObservabilityConfig:
    """
    Configuration for observability outputs.

    Note: There is NO log level filtering. Level is metadata only.
    All events are always emitted to all outputs.
    """
    service_name: str = "crawler-agent"

    # Console output
    console_enabled: bool = True
    console_color: bool = True

    # JSONL file output
    jsonl_enabled: bool = True
    jsonl_path: Optional[Path] = None
    log_dir: Path = field(default_factory=lambda: Path("logs"))

    # OpenTelemetry output
    otel_enabled: bool = False
    otel_endpoint: str = "localhost:4317"
    otel_insecure: bool = True

    # PII redaction (preserves existing functionality)
    redact_pii: bool = True

    def create_outputs(self) -> List[LogOutput]:
        """Create configured outputs."""
        outputs = []

        if self.console_enabled:
            outputs.append(ConsoleOutput(color=self.console_color))

        if self.jsonl_enabled:
            from datetime import datetime
            if self.jsonl_path is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                path = self.log_dir / f"agent_{timestamp}.jsonl"
            else:
                path = self.jsonl_path
            path.parent.mkdir(parents=True, exist_ok=True)
            outputs.append(JSONLinesOutput(path))

        if self.otel_enabled:
            outputs.append(OTLPOutput(
                service_name=self.service_name,
                endpoint=self.otel_endpoint,
                insecure=self.otel_insecure
            ))

        return outputs

    @classmethod
    def from_env(cls) -> "ObservabilityConfig":
        """Load from environment variables."""
        return cls(
            service_name=os.environ.get("SERVICE_NAME", "crawler-agent"),
            console_enabled=os.environ.get("LOG_CONSOLE", "true").lower() == "true",
            console_color=os.environ.get("LOG_COLOR", "true").lower() == "true",
            jsonl_enabled=os.environ.get("LOG_JSONL", "true").lower() == "true",
            jsonl_path=Path(p) if (p := os.environ.get("LOG_JSONL_PATH")) else None,
            log_dir=Path(os.environ.get("LOG_DIR", "logs")),
            otel_enabled=os.environ.get("LOG_OTEL", "false").lower() == "true",
            otel_endpoint=os.environ.get("LOG_OTEL_ENDPOINT", "localhost:4317"),
            otel_insecure=os.environ.get("LOG_OTEL_INSECURE", "true").lower() == "true",
            redact_pii=os.environ.get("LOG_REDACT_PII", "true").lower() == "true",
        )


# Global outputs list
_outputs: List[LogOutput] = []
_initialized: bool = False


def initialize_observability(config: ObservabilityConfig) -> None:
    """Initialize the observability system."""
    global _outputs, _initialized
    _outputs = config.create_outputs()
    _initialized = True


def get_outputs() -> List[LogOutput]:
    """Get configured outputs."""
    return _outputs


def is_initialized() -> bool:
    """Check if observability is initialized."""
    return _initialized
```

### File: src/observability/context.py

(Content as specified in section 4.1)

### File: src/observability/decorators.py

(Content as specified in section 4.2)

### File: src/observability/emitters.py

```python
"""Log and trace event emitters."""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
import json

from .context import ObservabilityContext
from .config import get_outputs, is_initialized
from .schema import LogRecord

def emit_log(
    level: str,
    event: str,
    ctx: ObservabilityContext,
    data: Dict[str, Any],
    metrics: Optional[Dict[str, Any]] = None,
    tags: Optional[list] = None
) -> None:
    """
    Emit a log record UNCONDITIONALLY.

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
        component_name=data.get(f"{component_type}_name", ctx.component_stack[-1] if ctx.component_stack else "unknown"),
        triggered_by=ctx.triggered_by,
        data=data,
        metrics=metrics or {},
        tags=tags or []
    )

    # Emit to all outputs - NO FILTERING
    for output in get_outputs():
        try:
            output.write_log(record)
        except Exception:
            pass  # Don't let logging failures break the application


def emit_trace_event(
    event: str,
    ctx: ObservabilityContext,
    attributes: Dict[str, Any]
) -> None:
    """
    Emit a trace event (span event).

    Creates an OTel-compatible span event with proper hierarchy.

    Args:
        event: Event name (e.g., "tool.triggered")
        ctx: Current observability context
        attributes: Event attributes
    """
    if not is_initialized():
        return

    trace_event = {
        "name": event,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "trace_id": ctx.trace_id,
        "span_id": ctx.span_id,
        "parent_span_id": ctx.parent_span_id,
        "attributes": {
            **attributes,
            "triggered_by": ctx.triggered_by
        }
    }

    # Emit to OTLP-capable outputs
    for output in get_outputs():
        try:
            if hasattr(output, 'write_trace_event'):
                output.write_trace_event(trace_event)
        except Exception:
            pass
```

### File: src/observability/serializers.py

```python
"""Safe serialization utilities for observability data."""

import json
from typing import Any
from datetime import datetime, date
from dataclasses import is_dataclass, asdict
from enum import Enum

def safe_serialize(obj: Any, max_depth: int = 10, current_depth: int = 0) -> Any:
    """
    Safely serialize any object for logging.

    Handles:
    - Dataclasses
    - Enums
    - Datetime objects
    - Nested structures
    - Circular references (via depth limit)
    - Non-serializable objects (converted to str)

    IMPORTANT: Does NOT truncate data. Full data is always captured.
    Truncation happens at query/display time, not emission time.
    """
    if current_depth > max_depth:
        return f"<max depth {max_depth} exceeded>"

    if obj is None:
        return None

    if isinstance(obj, (str, int, float, bool)):
        return obj

    if isinstance(obj, (datetime, date)):
        return obj.isoformat()

    if isinstance(obj, Enum):
        return obj.value

    if is_dataclass(obj) and not isinstance(obj, type):
        return safe_serialize(asdict(obj), max_depth, current_depth + 1)

    if isinstance(obj, dict):
        return {
            str(k): safe_serialize(v, max_depth, current_depth + 1)
            for k, v in obj.items()
        }

    if isinstance(obj, (list, tuple)):
        return [safe_serialize(item, max_depth, current_depth + 1) for item in obj]

    if isinstance(obj, set):
        return list(obj)

    if hasattr(obj, '__dict__'):
        return safe_serialize(obj.__dict__, max_depth, current_depth + 1)

    # Fallback to string representation
    try:
        return str(obj)
    except Exception:
        return f"<unserializable: {type(obj).__name__}>"
```

### File: src/observability/outputs.py

```python
"""Output implementations for observability."""

import json
import sys
import threading
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import TextIO, Any, Dict

from .schema import LogRecord

class LogOutput(ABC):
    """Abstract base for log outputs."""

    @abstractmethod
    def write_log(self, record: LogRecord) -> None:
        """Write a log record."""
        pass

    def write_trace_event(self, event: Dict[str, Any]) -> None:
        """Write a trace event (optional)."""
        pass

    @abstractmethod
    def flush(self) -> None:
        """Flush buffered data."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Close the output."""
        pass


class ConsoleOutput(LogOutput):
    """Human-readable console output."""

    LEVEL_COLORS = {
        "DEBUG": "\033[36m",    # Cyan
        "INFO": "\033[32m",     # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",    # Red
    }
    RESET = "\033[0m"
    DIM = "\033[2m"

    def __init__(self, stream: TextIO = None, color: bool = True):
        self.stream = stream or sys.stdout
        self.color = color
        self._lock = threading.Lock()

    def write_log(self, record: LogRecord) -> None:
        color = self.LEVEL_COLORS.get(record.level, "") if self.color else ""
        reset = self.RESET if self.color else ""
        dim = self.DIM if self.color else ""

        timestamp = record.timestamp.strftime("%H:%M:%S.%f")[:-3]
        span_short = record.span_id[-8:] if record.span_id else "--------"

        line = (
            f"{dim}{timestamp}{reset} "
            f"{color}{record.level:8}{reset} "
            f"{dim}[{span_short}]{reset} "
            f"{record.event:30} "
            f"- {record.component_name}"
        )

        # Add key metrics inline
        if record.metrics.get("duration_ms"):
            line += f" {dim}({record.metrics['duration_ms']:.0f}ms){reset}"

        with self._lock:
            self.stream.write(line + "\n")

    def flush(self) -> None:
        with self._lock:
            self.stream.flush()

    def close(self) -> None:
        pass


class JSONLinesOutput(LogOutput):
    """JSON Lines file output."""

    def __init__(self, file_path: Path):
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self._file = open(self.file_path, "a", encoding="utf-8")
        self._lock = threading.Lock()

    def write_log(self, record: LogRecord) -> None:
        line = json.dumps(record.to_dict(), default=str, ensure_ascii=False) + "\n"
        with self._lock:
            self._file.write(line)

    def flush(self) -> None:
        with self._lock:
            self._file.flush()

    def close(self) -> None:
        with self._lock:
            self._file.close()


class OTLPOutput(LogOutput):
    """OpenTelemetry OTLP output for traces and logs."""

    def __init__(self, service_name: str, endpoint: str, insecure: bool = True):
        self.service_name = service_name
        self.endpoint = endpoint
        self.insecure = insecure
        self._tracer = None
        self._initialized = False
        self._initialize()

    def _initialize(self) -> None:
        try:
            from opentelemetry import trace
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            from opentelemetry.sdk.resources import Resource, SERVICE_NAME

            resource = Resource.create({SERVICE_NAME: self.service_name})
            provider = TracerProvider(resource=resource)

            exporter = OTLPSpanExporter(
                endpoint=self.endpoint,
                insecure=self.insecure
            )
            provider.add_span_processor(BatchSpanProcessor(exporter))

            trace.set_tracer_provider(provider)
            self._tracer = trace.get_tracer(self.service_name)
            self._provider = provider
            self._initialized = True
        except ImportError:
            pass

    def write_log(self, record: LogRecord) -> None:
        # For now, logs go to JSONL. OTLP logs can be added later.
        pass

    def write_trace_event(self, event: Dict[str, Any]) -> None:
        if not self._initialized or not self._tracer:
            return

        # Create span for the trace event
        # Implementation depends on specific OTel span creation needs
        pass

    def flush(self) -> None:
        if self._initialized and hasattr(self, '_provider'):
            self._provider.force_flush()

    def close(self) -> None:
        if self._initialized and hasattr(self, '_provider'):
            self._provider.shutdown()
```

### File: src/observability/schema.py

(Content as specified in section 4.3)

---

## Implementation Plan

### Phase 0: Preparation
**Estimated effort:** 2-4 hours
**Dependencies:** None

- [ ] Create `src/observability/` directory
- [ ] Create `__init__.py` with module exports
- [ ] Create `context.py` with ObservabilityContext
- [ ] Create `schema.py` with LogRecord
- [ ] Create `serializers.py` with safe_serialize
- [ ] Create `config.py` with ObservabilityConfig
- [ ] Create `outputs.py` with output implementations
- [ ] Create `emitters.py` with emit_log, emit_trace_event

**Files to create:**
- `src/observability/__init__.py`
- `src/observability/context.py`
- `src/observability/schema.py`
- `src/observability/serializers.py`
- `src/observability/config.py`
- `src/observability/outputs.py`
- `src/observability/emitters.py`

### Phase 1: Core Infrastructure
**Estimated effort:** 4-6 hours
**Dependencies:** Phase 0

- [ ] Create `decorators.py` with @traced_tool, @traced_agent, @traced_llm_client
- [ ] Unit test decorators with mock functions
- [ ] Test context propagation across nested calls
- [ ] Test error capture with stack traces
- [ ] Verify all existing LogMetrics fields are preserved

**Files to create:**
- `src/observability/decorators.py`
- `tests/test_observability/test_decorators.py`
- `tests/test_observability/test_context.py`

### Phase 2: Remove Filtering
**Estimated effort:** 1-2 hours
**Dependencies:** Phase 0

- [ ] Modify `src/core/structured_logger.py` - remove `_should_log` filtering
- [ ] Modify `src/core/sampling.py` - disable by default
- [ ] Modify `src/core/log_config.py` - update defaults
- [ ] Test that all levels now emit

**Files to modify:**
- `src/core/structured_logger.py`
- `src/core/sampling.py`
- `src/core/log_config.py`

### Phase 3: Migration - LLM Client
**Estimated effort:** 2-3 hours
**Dependencies:** Phase 1

- [ ] Add @traced_llm_client to `LLMClient.chat()`
- [ ] Remove manual logging from llm.py
- [ ] Verify token metrics captured
- [ ] Verify cost estimation works
- [ ] Test error capture

**Files to modify:**
- `src/core/llm.py`

### Phase 4: Migration - Tools
**Estimated effort:** 4-6 hours
**Dependencies:** Phase 1

For each tool file:
- [ ] `src/tools/browser.py` - 6 tools
- [ ] `src/tools/memory.py` - 5 tools
- [ ] `src/tools/extraction.py` - 6 tools
- [ ] `src/tools/http.py` - 1 tool
- [ ] `src/tools/orchestration.py` - 4 tools

Per tool:
1. Add @traced_tool decorator
2. Remove manual logging
3. Simplify try/except (decorator handles)
4. Verify return values unchanged

### Phase 5: Migration - Agents
**Estimated effort:** 3-4 hours
**Dependencies:** Phase 3, Phase 4

For each agent:
- [ ] `src/agents/base.py` - BaseAgent.run(), BaseAgent._execute_tool()
- [ ] `src/agents/main_agent.py` - MainAgent.create_crawl_plan()
- [ ] `src/agents/browser_agent.py` - verify inherits properly
- [ ] `src/agents/selector_agent.py` - verify inherits properly
- [ ] `src/agents/accessibility_agent.py` - verify inherits properly
- [ ] `src/agents/data_prep_agent.py` - verify inherits properly

### Phase 6: Update Entry Point
**Estimated effort:** 1-2 hours
**Dependencies:** Phase 5

- [ ] Modify `main.py` to use new observability module
- [ ] Remove manual structured logging calls
- [ ] Test end-to-end execution
- [ ] Verify logs in console and JSONL

**Files to modify:**
- `main.py`

### Phase 7: Cleanup
**Estimated effort:** 2-3 hours
**Dependencies:** Phase 6

- [ ] Remove unused imports from all modified files
- [ ] Consider deprecating old logging module (keep for backward compat?)
- [ ] Update any remaining `logger.info()` calls
- [ ] Remove `src/core/sampling.py` if truly unused
- [ ] Clean up test files

**Files to potentially delete:**
- `src/core/sampling.py` (if unused)

**Files to clean:**
- All modified files - remove unused imports

### Phase 8: Validation
**Estimated effort:** 4-6 hours
**Dependencies:** Phase 7

- [ ] Run full application workflow
- [ ] Verify trace hierarchy in Jaeger
- [ ] Verify logs capture everything
- [ ] Verify no log level filtering
- [ ] Compare old vs new log output
- [ ] Performance testing (no regression)
- [ ] Check all existing metrics preserved

---

## Configuration Design

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SERVICE_NAME` | `crawler-agent` | Service name for logs/traces |
| `LOG_CONSOLE` | `true` | Enable console output |
| `LOG_COLOR` | `true` | Enable colored console |
| `LOG_JSONL` | `true` | Enable JSONL file output |
| `LOG_JSONL_PATH` | auto-generated | JSONL file path |
| `LOG_DIR` | `logs` | Log directory |
| `LOG_OTEL` | `false` | Enable OpenTelemetry |
| `LOG_OTEL_ENDPOINT` | `localhost:4317` | OTLP endpoint |
| `LOG_OTEL_INSECURE` | `true` | Use insecure connection |
| `LOG_REDACT_PII` | `true` | Enable PII redaction |

### Removed/Ignored Variables

| Variable | Reason |
|----------|--------|
| `LOG_LEVEL` | Level is metadata only, not for filtering |
| `LOG_SAMPLING` | Sampling disabled - log everything |
| `LOG_SAMPLING_RATE` | Sampling disabled |

---

## Testing Strategy

### Unit Tests

1. **Decorator tests** (`tests/test_observability/test_decorators.py`)
   - Test @traced_tool captures input/output
   - Test @traced_agent creates proper context
   - Test @traced_llm_client captures metrics
   - Test error handling with stack trace
   - Test async function support

2. **Context tests** (`tests/test_observability/test_context.py`)
   - Test create_root creates valid context
   - Test create_child inherits trace_id
   - Test parent_span_id is correct
   - Test triggered_by extraction
   - Test nested context propagation

3. **Serialization tests** (`tests/test_observability/test_serializers.py`)
   - Test dataclass serialization
   - Test datetime handling
   - Test circular reference handling
   - Test non-serializable objects

### Integration Tests

```python
# tests/test_integration/test_observability_integration.py

def test_full_agent_workflow_logging():
    """Test that a full agent workflow produces complete logs."""
    # Setup
    config = ObservabilityConfig(
        console_enabled=False,
        jsonl_enabled=True,
        jsonl_path=Path("test_logs.jsonl")
    )
    initialize_observability(config)

    # Execute workflow
    agent = MainAgent(...)
    result = agent.create_crawl_plan("https://example.com")

    # Verify logs
    with open("test_logs.jsonl") as f:
        logs = [json.loads(line) for line in f]

    # Check trace hierarchy
    assert all(log["trace_id"] == logs[0]["trace_id"] for log in logs)

    # Check event coverage
    events = {log["event"] for log in logs}
    assert "agent.triggered" in events
    assert "tool.input" in events
    assert "llm.request" in events

    # Check no filtering happened
    debug_logs = [l for l in logs if l["level"] == "DEBUG"]
    assert len(debug_logs) > 0  # DEBUG logs should exist


def test_error_capture():
    """Test that errors include full stack trace."""
    @traced_tool(name="failing_tool")
    def failing_tool():
        raise ValueError("Test error")

    with pytest.raises(ValueError):
        failing_tool()

    # Check error was logged with stack trace
    logs = get_test_logs()
    error_log = next(l for l in logs if l["event"] == "tool.error")
    assert "ValueError" in error_log["data"]["error_type"]
    assert "stack_trace" in error_log["data"]
    assert "Test error" in error_log["data"]["stack_trace"]
```

### Sample Queries to Validate Data

**Loki/Grafana:**
```logql
# All events for a trace
{service_name="crawler-agent"} | json | trace_id="trace_abc123"

# All errors
{service_name="crawler-agent"} | json | event=~".*error.*"

# All LLM calls with cost
{service_name="crawler-agent"} | json | event="llm.response" | line_format "{{.llm_model}}: ${{.llm_cost_total}}"

# Tool execution times
{service_name="crawler-agent"} | json | event="tool.output" | metrics_duration_ms > 1000
```

**Elasticsearch:**
```json
// All events for a trace
{"query": {"term": {"trace_id": "trace_abc123"}}}

// All errors with stack traces
{"query": {"bool": {"must": [
  {"match": {"level": "ERROR"}},
  {"exists": {"field": "data.stack_trace"}}
]}}}

// Average LLM latency by model
{"aggs": {"by_model": {"terms": {"field": "data.llm.model"}, "aggs": {"avg_duration": {"avg": {"field": "metrics.duration_ms"}}}}}}
```

---

## Rollback Plan

### Feature Flag Approach

If issues arise, a quick rollback can be achieved by:

1. **Keep old logging module intact** during migration
2. **Add feature flag** to switch between old and new:

```python
# src/observability/config.py
USE_NEW_OBSERVABILITY = os.environ.get("USE_NEW_OBSERVABILITY", "true").lower() == "true"

# In decorators
def traced_tool(name: str):
    if not USE_NEW_OBSERVABILITY:
        return lambda func: func  # No-op decorator
    # ... actual implementation
```

3. **Set `USE_NEW_OBSERVABILITY=false`** to disable all new decorators
4. **Old manual logging** still works as fallback

### Parallel Running Strategy

During migration, both systems can run simultaneously:
- New observability system writes to new outputs
- Old StructuredLogger continues writing to existing outputs
- Compare outputs to validate equivalence

### Quick Revert

If critical issues found:
1. `git revert` the migration commits
2. Deploy previous version
3. Investigate in development environment

---

## Appendices

### A. Complete Event Taxonomy

| Event | Category | When Emitted |
|-------|----------|--------------|
| `agent.triggered` | agent | Agent execution starts |
| `agent.iteration` | agent | Each agent loop iteration |
| `agent.llm_call_started` | agent | Before LLM call |
| `agent.llm_call_completed` | agent | After LLM response |
| `agent.tool_selected` | agent | Agent chooses tool |
| `agent.execution_completed` | agent | Agent finishes successfully |
| `agent.error` | agent | Agent fails |
| `tool.input` | tool | Tool execution starts |
| `tool.output` | tool | Tool finishes successfully |
| `tool.error` | tool | Tool fails |
| `llm.request` | llm | LLM API call starts |
| `llm.response` | llm | LLM response received |
| `llm.error` | llm | LLM call fails |

### B. Complete Log Schema (JSON Schema)

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["timestamp", "trace_id", "span_id", "level", "event", "component_type", "component_name"],
  "properties": {
    "timestamp": {"type": "string", "format": "date-time"},
    "trace_id": {"type": "string"},
    "span_id": {"type": "string"},
    "parent_span_id": {"type": ["string", "null"]},
    "session_id": {"type": ["string", "null"]},
    "request_id": {"type": ["string", "null"]},
    "level": {"type": "string", "enum": ["DEBUG", "INFO", "WARNING", "ERROR"]},
    "event": {"type": "string"},
    "component_type": {"type": "string", "enum": ["agent", "tool", "llm_client"]},
    "component_name": {"type": "string"},
    "triggered_by": {"type": "string"},
    "data": {"type": "object"},
    "metrics": {
      "type": "object",
      "properties": {
        "duration_ms": {"type": "number"},
        "content_size_bytes": {"type": "integer"}
      }
    },
    "tags": {"type": "array", "items": {"type": "string"}}
  }
}
```

### C. Sample Log/Trace Output

```json
{"timestamp":"2025-01-15T10:30:45.123456Z","trace_id":"trace_abc123def456","span_id":"span_111222333","parent_span_id":"span_000111222","session_id":"sess_xyz789","request_id":"req_456def","level":"DEBUG","event":"tool.input","component_type":"tool","component_name":"browser_navigate","triggered_by":"BrowserAgent","data":{"tool_name":"browser_navigate","input":{"args":[],"kwargs":{"url":"https://example.com"}}},"metrics":{},"tags":[]}
{"timestamp":"2025-01-15T10:30:46.234567Z","trace_id":"trace_abc123def456","span_id":"span_111222333","parent_span_id":"span_000111222","session_id":"sess_xyz789","request_id":"req_456def","level":"DEBUG","event":"tool.output","component_type":"tool","component_name":"browser_navigate","triggered_by":"BrowserAgent","data":{"tool_name":"browser_navigate","output":{"success":true,"result":"Navigated to https://example.com"},"duration_ms":1111.23},"metrics":{"duration_ms":1111.23},"tags":[]}
{"timestamp":"2025-01-15T10:30:47.345678Z","trace_id":"trace_abc123def456","span_id":"span_222333444","parent_span_id":"span_111222333","session_id":"sess_xyz789","request_id":"req_456def","level":"DEBUG","event":"llm.request","component_type":"llm_client","component_name":"openai","triggered_by":"browser_navigate","data":{"llm.model":"gpt-4o","llm.request.message_count":3,"llm.request.has_tools":true},"metrics":{},"tags":[]}
{"timestamp":"2025-01-15T10:30:49.456789Z","trace_id":"trace_abc123def456","span_id":"span_222333444","parent_span_id":"span_111222333","session_id":"sess_xyz789","request_id":"req_456def","level":"DEBUG","event":"llm.response","component_type":"llm_client","component_name":"openai","triggered_by":"browser_navigate","data":{"llm.model":"gpt-4o","llm.tokens.input":1500,"llm.tokens.output":500,"llm.tokens.total":2000,"llm.cost.total":0.004},"metrics":{"duration_ms":2111.11},"tags":[]}
```

### D. Migration Checklist Template

```markdown
## Migration Checklist: [File Name]

### Pre-Migration
- [ ] Read and understand current implementation
- [ ] Identify all manual logging calls
- [ ] Note existing metrics captured
- [ ] Document current behavior

### Migration Steps
- [ ] Add import for decorator
- [ ] Apply decorator to main method(s)
- [ ] Remove manual `get_logger()` calls
- [ ] Remove manual `slog.xxx()` calls
- [ ] Remove manual timing code
- [ ] Simplify try/except blocks
- [ ] Update error handling

### Post-Migration Validation
- [ ] Run unit tests
- [ ] Verify logs emitted
- [ ] Check trace hierarchy
- [ ] Confirm metrics preserved
- [ ] Test error scenarios
- [ ] Compare old vs new output

### Sign-off
- [ ] Code review completed
- [ ] Tests passing
- [ ] Documentation updated
```

---

## Conclusion

This refactoring plan provides a complete roadmap for implementing proper OpenTelemetry-compatible observability with:

1. **Zero log filtering** - Everything is always logged
2. **Decorator-based instrumentation** - Clean component code
3. **Automatic context propagation** - Proper trace hierarchy
4. **Separate traces and logs** - OTel best practices
5. **Full error capture** - Stack traces and context
6. **Preserved metrics** - All existing fields maintained

The phased approach allows incremental migration with rollback capability at each step.
