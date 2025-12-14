# Trace/Span ID Refactoring Plan: Standard OTel Compliance

## Executive Summary

This document outlines the required changes to migrate from our **custom trace/span ID generation** to **standard OpenTelemetry (OTel) semantics**.

### Current State (Problems)

Our current implementation:
1. **Generates custom IDs** with prefixes (`trace_`, `span_`, `sess_`, `req_`)
2. **Manually manages parent-child relationships** via `parent_span_id` field
3. **Uses Python `contextvars`** independently of OTel context
4. **Creates disconnected OTel spans** - `send_trace()` uses `start_as_current_span()` without proper parent linkage
5. **Dual context systems** - our `ObservabilityContext` and OTel context are not synchronized

### Target State

Standard OTel compliance:
- **One agent execution = one trace** (new `trace_id` per run)
- **Span IDs generated exclusively by OTel**
- **Parent-child relationships derived from active OTel context**
- **No custom ID generation** - OTel manages all IDs
- **Hybrid context** - OTel for trace/span IDs + our metadata wrapper

---

## Data Preservation Guarantees

### Critical Requirement

**ALL existing data fields MUST be preserved.** Only the SOURCE of trace/span IDs changes.

### Field Mapping: Before vs After

| Field | Current Source | After Refactoring | Data Format |
|-------|----------------|-------------------|-------------|
| `trace_id` | `f"trace_{uuid.hex[:16]}"` | OTel span context | `format(ctx.trace_id, '032x')` |
| `span_id` | `f"span_{uuid.hex[:12]}"` | OTel span context | `format(ctx.span_id, '016x')` |
| `parent_span_id` | Manual `create_child()` | OTel span context (or None for root) | `format(parent.span_id, '016x')` |
| `session_id` | `f"sess_{uuid.hex[:12]}"` | **PRESERVED** - business metadata | Same format |
| `request_id` | `f"req_{uuid.hex[:12]}"` | **PRESERVED** - business metadata | Same format |
| `component_stack` | Manual tracking | **PRESERVED** - via wrapper context | Same list |
| `triggered_by` | Derived from stack | **PRESERVED** - via wrapper context | Same string |
| `component_type` | From decorator | **PRESERVED** - span attribute | Same string |
| `component_name` | From decorator | **PRESERVED** - span attribute | Same string |
| `data` | Full payload | **PRESERVED** - log attribute | Same dict |
| `metrics` | Full metrics | **PRESERVED** - log attribute | Same dict |
| `tags` | Tag list | **PRESERVED** - log attribute | Same list |

### What Changes

```
BEFORE: trace_id = "trace_abc123def456"  (custom format)
AFTER:  trace_id = "abc123def456789012345678901234"  (OTel 128-bit hex)

BEFORE: span_id = "span_abc123def"  (custom format)
AFTER:  span_id = "abc123def4567890"  (OTel 64-bit hex)

BEFORE: parent_span_id set manually via create_child()
AFTER:  parent_span_id derived from OTel active span context
```

### What Does NOT Change

- `session_id` format and value
- `request_id` format and value
- `triggered_by` logic (parent component name)
- `component_stack` tracking
- All `data` payload contents
- All `metrics` values
- All `tags` values
- `LogRecord` structure (same 13 fields)
- `TraceEvent` structure (same 6 fields)
- Console output format
- Elasticsearch index mapping

---

## Hybrid Context Architecture

### Approach: Wrap OTel Span with Business Metadata

Instead of replacing `ObservabilityContext` entirely, we create a **hybrid** that:
1. Gets `trace_id`, `span_id`, `parent_span_id` from OTel span
2. Carries our business metadata (`session_id`, `request_id`, `component_stack`)

```python
@dataclass
class ObservabilityContext:
    """Hybrid context: OTel span + business metadata.

    trace_id/span_id come from OTel span context.
    Business fields (session_id, request_id, component_stack) are managed by us.
    """
    # Business metadata (WE manage these)
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    component_stack: List[str] = field(default_factory=list)

    # OTel span reference (for extracting IDs)
    _span: Optional[Span] = field(default=None, repr=False)

    @property
    def trace_id(self) -> str:
        """Get trace_id from OTel span context."""
        if self._span:
            ctx = self._span.get_span_context()
            if ctx.is_valid:
                return format(ctx.trace_id, '032x')
        return ""

    @property
    def span_id(self) -> str:
        """Get span_id from OTel span context."""
        if self._span:
            ctx = self._span.get_span_context()
            if ctx.is_valid:
                return format(ctx.span_id, '016x')
        return ""

    @property
    def parent_span_id(self) -> Optional[str]:
        """Parent span ID - extracted from OTel parent link."""
        # OTel handles this internally via context propagation
        # We can get it from span.parent if needed
        if self._span and hasattr(self._span, 'parent') and self._span.parent:
            return format(self._span.parent.span_id, '016x')
        return None

    @property
    def triggered_by(self) -> str:
        """Parent component name from our stack."""
        if len(self.component_stack) > 1:
            return self.component_stack[-2]
        return "direct_call"
```

### Context Flow with Hybrid Approach

```
1. Application Start
   └─ Create root ObservabilityContext with session_id, request_id
   └─ No OTel span yet (no _span reference)

2. @traced_agent("MainAgent") called
   └─ tracer.start_as_current_span("agent.MainAgent")
   └─ Create child ObservabilityContext:
      ├─ _span = current OTel span
      ├─ session_id = inherited from parent
      ├─ request_id = inherited from parent
      └─ component_stack = ["root", "MainAgent"]
   └─ trace_id/span_id now come from OTel span

3. @traced_tool("Navigate") called inside agent
   └─ tracer.start_as_current_span("tool.Navigate")  # OTel creates child span
   └─ Create child ObservabilityContext:
      ├─ _span = current OTel span (child)
      ├─ session_id = inherited
      ├─ request_id = inherited
      └─ component_stack = ["root", "MainAgent", "Navigate"]
   └─ trace_id same (inherited by OTel)
   └─ span_id new (created by OTel)
   └─ parent_span_id = MainAgent's span_id (by OTel context)
```

---

## Log Handling: Full Preservation

### Current Log Flow

```
emit_log() → LogRecord → handler.send_log() → OTel Log Exporter → Collector → Elasticsearch
```

**LogRecord contains:**
- `trace_id`, `span_id`, `parent_span_id` (correlation)
- `session_id`, `request_id` (business IDs)
- `level`, `event` (classification)
- `component_type`, `component_name`, `triggered_by` (component info)
- `data`, `metrics`, `tags` (payload)

### After Refactoring: Same Flow, Same Data

The only change is WHERE `trace_id`/`span_id`/`parent_span_id` come from:

```python
# BEFORE (emitters.py:62-77)
record = LogRecord(
    timestamp=datetime.now(timezone.utc),
    trace_id=ctx.trace_id,           # From custom ObservabilityContext
    span_id=ctx.span_id,             # From custom ObservabilityContext
    parent_span_id=ctx.parent_span_id,  # From custom ObservabilityContext
    session_id=ctx.session_id,       # Same
    request_id=ctx.request_id,       # Same
    ...
)

# AFTER (same structure, different source)
record = LogRecord(
    timestamp=datetime.now(timezone.utc),
    trace_id=ctx.trace_id,           # Now from OTel span via property
    span_id=ctx.span_id,             # Now from OTel span via property
    parent_span_id=ctx.parent_span_id,  # Now from OTel span via property
    session_id=ctx.session_id,       # Same - still managed by us
    request_id=ctx.request_id,       # Same - still managed by us
    ...
)
```

### Log-Trace Correlation Guarantee

**Before:**
```json
{
  "trace_id": "trace_abc123def456",
  "span_id": "span_xyz789",
  "parent_span_id": "span_uvw456",
  "session_id": "sess_abc123",
  "event": "tool.input",
  "data": { "tool_name": "Navigate", "input": {...} }
}
```

**After:**
```json
{
  "trace_id": "abc123def456789012345678901234",
  "span_id": "xyz789012345678",
  "parent_span_id": "uvw456012345678",
  "session_id": "sess_abc123",
  "event": "tool.input",
  "data": { "tool_name": "Navigate", "input": {...} }
}
```

**Same fields, same structure, same correlation** - only ID format changes.

### OTel Log Exporter: No Changes Needed

The `OTelGrpcHandler.send_log()` already sends logs via OTLP:

```python
# handlers.py:159-167 - This code stays THE SAME
attributes = {
    "event": record.event,
    "component_type": record.component_type,
    "component_name": record.component_name,
    "trace_id": record.trace_id,        # Now OTel-format hex
    "span_id": record.span_id,          # Now OTel-format hex
    "parent_span_id": record.parent_span_id or "",  # Now OTel-format hex
    "triggered_by": record.triggered_by,
    ...
}
```

### Logs in Elasticsearch: Query Compatibility

**Before query:**
```json
{"query": {"term": {"trace_id": "trace_abc123def456"}}}
```

**After query:**
```json
{"query": {"term": {"trace_id": "abc123def456789012345678901234"}}}
```

The ES index mapping (`keyword` type) works for both formats.

### Log Levels: No Changes

Log levels remain metadata-only (no filtering):
- `emit_debug()` → level="DEBUG"
- `emit_info()` → level="INFO"
- `emit_warning()` → level="WARNING"
- `emit_error()` → level="ERROR"

All logs still emitted unconditionally.

---

## Span-Log Relationship

### Current Problem

Spans and logs are **disconnected** because:
1. Our logs have `trace_id="trace_abc123"` (custom)
2. OTel spans have `trace_id=0xdef456...` (OTel generated)
3. They don't match → can't correlate in Jaeger/Grafana

### After Refactoring

Spans and logs **share the same IDs** because both come from OTel:

```
OTel Span (trace_id=T1, span_id=S1)
    │
    ├── Log: tool.input   (trace_id=T1, span_id=S1)
    ├── Log: tool.output  (trace_id=T1, span_id=S1)
    │
    └── Child Span (trace_id=T1, span_id=S2, parent=S1)
            │
            ├── Log: llm.input  (trace_id=T1, span_id=S2)
            └── Log: llm.output (trace_id=T1, span_id=S2)
```

**Result:** Click on a span in Jaeger → see all related logs in Elasticsearch.

---

## Current Architecture Analysis

### Files to Modify

| File | Current Responsibility | Changes Required |
|------|------------------------|------------------|
| `context.py` | Custom `ObservabilityContext` with manual ID generation | **Major rewrite** - Remove custom context, use OTel context |
| `decorators.py` | Creates child spans via `create_child()` | **Major rewrite** - Use `tracer.start_as_current_span()` |
| `handlers.py` | `send_trace()` creates disconnected spans | **Major rewrite** - Remove span creation, use active span |
| `schema.py` | `trace_id`, `span_id`, `parent_span_id` fields | **Minor update** - Keep for log records, derive from OTel span |
| `emitters.py` | Emits logs/traces with custom context | **Medium update** - Extract IDs from active OTel span |
| `main.py` | Creates root context manually | **Medium update** - Create root span via OTel tracer |

### Current Flow (Broken)

```
1. main.py: get_or_create_context("application")
   └─ Creates ObservabilityContext with trace_abc123, span_001

2. @traced_agent decorator:
   └─ parent_ctx.create_child(name) → span_002 with parent_span_id=span_001
   └─ set_context(ctx) → contextvars updated (NOT OTel)

3. @traced_tool decorator:
   └─ parent_ctx.create_child(name) → span_003 with parent_span_id=span_002

4. handlers.py send_trace():
   └─ self._tracer.start_as_current_span(name)
   └─ Creates NEW OTel span with NEW trace_id, NO parent linkage!
```

### Target Flow (Correct)

```
1. main.py: tracer.start_as_current_span("agent.run")
   └─ OTel creates root span: trace_id=T1, span_id=S1, parent=None
   └─ Span is set as current in OTel context

2. @traced_agent decorator:
   └─ with tracer.start_as_current_span("agent.main"):
   └─ OTel automatically links: trace_id=T1, span_id=S2, parent=S1

3. @traced_tool decorator (within agent):
   └─ with tracer.start_as_current_span("tool.navigate"):
   └─ OTel automatically links: trace_id=T1, span_id=S3, parent=S2

4. Log emission:
   └─ span = trace.get_current_span()
   └─ ctx = span.get_span_context()
   └─ trace_id, span_id extracted from active span
```

---

## Detailed Implementation Plan

### Phase 1: OTel Tracer Setup

**File: `src/observability/tracer.py` (NEW)**

Create a centralized tracer provider:

```python
"""OpenTelemetry tracer provider setup.

Single source of truth for trace/span creation.
All IDs are generated by OTel - no custom generation.
"""
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource, SERVICE_NAME

_tracer: trace.Tracer = None

def init_tracer(endpoint: str, service_name: str, insecure: bool = True) -> trace.Tracer:
    """Initialize the global OTel tracer.

    Must be called once at application startup.
    """
    global _tracer

    resource = Resource.create({SERVICE_NAME: service_name})
    provider = TracerProvider(resource=resource)

    exporter = OTLPSpanExporter(endpoint=endpoint, insecure=insecure)
    provider.add_span_processor(BatchSpanProcessor(exporter))

    trace.set_tracer_provider(provider)
    _tracer = trace.get_tracer(service_name)

    return _tracer

def get_tracer() -> trace.Tracer:
    """Get the global tracer instance."""
    global _tracer
    if _tracer is None:
        # Return no-op tracer if not initialized
        _tracer = trace.get_tracer("uninitialized")
    return _tracer
```

### Phase 2: Remove Custom Context

**File: `src/observability/context.py` (MAJOR REWRITE)**

Replace custom `ObservabilityContext` with OTel context utilities:

```python
"""Context utilities for extracting trace info from OTel spans.

We NO LONGER generate IDs. All IDs come from OTel.
This module provides helpers to extract IDs from active spans for logging.
"""
from opentelemetry import trace
from typing import Optional, Tuple

def get_current_trace_context() -> Tuple[str, str, Optional[str]]:
    """Extract trace_id, span_id, parent_span_id from current OTel span.

    Returns:
        (trace_id, span_id, parent_span_id) - all as hex strings
        If no active span, returns empty strings.
    """
    span = trace.get_current_span()
    ctx = span.get_span_context()

    if not ctx.is_valid:
        return ("", "", None)

    trace_id = format(ctx.trace_id, '032x')
    span_id = format(ctx.span_id, '016x')

    # Parent span ID is not directly available from SpanContext
    # It's managed internally by OTel - we don't need to track it
    parent_span_id = None  # OTel handles parent relationships

    return (trace_id, span_id, parent_span_id)

def get_trace_id() -> str:
    """Get current trace ID as hex string."""
    trace_id, _, _ = get_current_trace_context()
    return trace_id

def get_span_id() -> str:
    """Get current span ID as hex string."""
    _, span_id, _ = get_current_trace_context()
    return span_id
```

### Phase 3: Rewrite Decorators

**File: `src/observability/decorators.py` (MAJOR REWRITE)**

Use OTel spans instead of custom context:

```python
"""Decorator-based instrumentation using native OTel spans.

Decorators create proper parent-child span relationships via OTel context.
No manual ID generation or parent tracking.
"""
from functools import wraps
from opentelemetry import trace
from opentelemetry.trace import SpanKind, Status, StatusCode
from .tracer import get_tracer
from .emitters import emit_log_with_span

def traced_tool(name: str):
    """Decorator for tool functions.

    Creates a child span under the current active span.
    OTel automatically handles parent-child relationship.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            tracer = get_tracer()

            # start_as_current_span automatically:
            # - Creates new span_id
            # - Inherits trace_id from parent
            # - Sets parent_span_id to current span
            # - Makes this span the active context
            with tracer.start_as_current_span(
                name=f"tool.{name}",
                kind=SpanKind.INTERNAL
            ) as span:
                # Add attributes
                span.set_attribute("component.type", "tool")
                span.set_attribute("component.name", name)

                try:
                    # Emit input log (attached to current span)
                    emit_log_with_span("tool.input", {"name": name, "args": ...})

                    result = func(*args, **kwargs)

                    span.set_status(Status(StatusCode.OK))
                    emit_log_with_span("tool.output", {"name": name, "result": ...})

                    return result

                except Exception as e:
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    span.record_exception(e)
                    emit_log_with_span("tool.error", {"name": name, "error": str(e)})
                    raise

        return wrapper
    return decorator

def traced_agent(name: str):
    """Decorator for agent run methods.

    Creates the ROOT span for an agent execution.
    Each agent.run() call starts a NEW trace.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            tracer = get_tracer()

            # Agent span is typically root (no parent)
            # If called within another span, it becomes child
            with tracer.start_as_current_span(
                name=f"agent.{name}",
                kind=SpanKind.INTERNAL
            ) as span:
                span.set_attribute("component.type", "agent")
                span.set_attribute("component.name", name)

                try:
                    emit_log_with_span("agent.input", {...})
                    result = func(*args, **kwargs)
                    span.set_status(Status(StatusCode.OK))
                    emit_log_with_span("agent.output", {...})
                    return result
                except Exception as e:
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    span.record_exception(e)
                    emit_log_with_span("agent.error", {...})
                    raise

        return wrapper
    return decorator
```

### Phase 4: Update Log Emission

**File: `src/observability/emitters.py` (MEDIUM UPDATE)**

Emit logs with trace context from active span:

```python
"""Log emission with automatic OTel trace context.

Logs are correlated to spans by extracting trace_id/span_id from active span.
"""
from opentelemetry import trace
from .context import get_current_trace_context
from .schema import LogRecord

def emit_log_with_span(event: str, data: dict, level: str = "INFO"):
    """Emit a log record attached to the current OTel span.

    Automatically extracts trace_id and span_id from active span context.
    """
    trace_id, span_id, parent_span_id = get_current_trace_context()

    record = LogRecord(
        timestamp=datetime.now(timezone.utc),
        trace_id=trace_id,      # From OTel, not generated
        span_id=span_id,        # From OTel, not generated
        parent_span_id=parent_span_id,
        level=level,
        event=event,
        data=data,
        # ... other fields
    )

    get_handler().send_log(record)
```

### Phase 5: Simplify Handler

**File: `src/observability/handlers.py` (MAJOR REWRITE)**

Remove `send_trace()` span creation - spans are already created by decorators:

```python
class OTelGrpcHandler(LogHandler):
    """Handler that sends logs to OTel Collector.

    IMPORTANT: This handler does NOT create spans.
    Spans are created by decorators using the tracer directly.
    This handler only sends log records.
    """

    def send_log(self, record: LogRecord) -> None:
        """Send log record via OTLP.

        The record already contains trace_id/span_id from the active span.
        """
        # ... emit log with trace correlation

    def send_trace(self, event: TraceEvent) -> None:
        """DEPRECATED - spans are created by decorators.

        This method may be removed or converted to add span events.
        """
        # Option A: Remove entirely
        # Option B: Use trace.get_current_span().add_event(event.name, event.attributes)
        pass
```

### Phase 6: Update Application Entry Point

**File: `main.py` (MEDIUM UPDATE)**

Initialize tracer and create root span:

```python
from src.observability.tracer import init_tracer, get_tracer

def main():
    # Initialize OTel tracer (once at startup)
    tracer = init_tracer(
        endpoint=os.environ.get("OTEL_ENDPOINT", "localhost:4317"),
        service_name=os.environ.get("SERVICE_NAME", "crawler-agent"),
        insecure=True
    )

    # The agent's @traced_agent decorator creates the root span
    # No need to manually create context here

    agent = MainAgent(llm, tools)
    result = agent.run(task)  # Root span created here by decorator
```

---

## Migration Checklist

### Files to Create
- [ ] `src/observability/tracer.py` - Centralized tracer provider

### Files to Rewrite (Major Changes)
- [ ] `src/observability/context.py` - Remove custom context, add OTel helpers
- [ ] `src/observability/decorators.py` - Use OTel `start_as_current_span()`
- [ ] `src/observability/handlers.py` - Remove span creation from `send_trace()`

### Files to Update (Medium Changes)
- [ ] `src/observability/emitters.py` - Extract IDs from active OTel span
- [ ] `main.py` - Initialize tracer, remove manual context creation
- [ ] `src/observability/config.py` - Add tracer initialization to `initialize_observability()`

### Files to Review (Minor Changes)
- [ ] `src/observability/schema.py` - Keep `trace_id`/`span_id` fields (derived from OTel)
- [ ] `src/observability/outputs.py` - Should work as-is (receives LogRecords)
- [ ] `tests/test_observability/*.py` - Update tests for new behavior

### Fields to Remove from `ObservabilityContext`
- [x] `trace_id` generation (`trace_{uuid}`)
- [x] `span_id` generation (`span_{uuid}`)
- [x] `parent_span_id` manual tracking
- [x] `session_id` (optional - may keep as business metadata)
- [x] `request_id` (optional - may keep as business metadata)
- [x] `create_root()` method
- [x] `create_child()` method

---

## Behavioral Changes

### Before (Current)

```
Custom Context                    OTel (Disconnected)
─────────────────                 ────────────────────
trace_abc123                      trace_xyz789 (new)
├─ span_001 (root)                ├─ span_A (disconnected)
│  └─ span_002 (agent)            ├─ span_B (disconnected)
│     └─ span_003 (tool)          └─ span_C (disconnected)
```

### After (Target)

```
Single OTel Context
───────────────────
trace_abc123 (OTel generated)
├─ span_001 (agent.run - root)
│  ├─ span_002 (tool.navigate)
│  ├─ span_003 (llm.chat)
│  │  └─ span_004 (http.request)
│  └─ span_005 (tool.memory)
```

---

## Validation Strategy: Guaranteeing Same Data

### Validation Test Suite

Before deployment, run comparison tests that verify identical output:

```python
"""validation_tests.py - Ensure data parity between old and new implementations."""

def test_log_record_fields_identical():
    """Verify LogRecord has ALL the same fields after refactoring."""

    # Run same operation with OLD implementation
    old_record = run_with_old_context("test_tool")

    # Run same operation with NEW implementation
    new_record = run_with_new_context("test_tool")

    # These MUST be identical
    assert old_record.session_id == new_record.session_id
    assert old_record.request_id == new_record.request_id
    assert old_record.component_type == new_record.component_type
    assert old_record.component_name == new_record.component_name
    assert old_record.triggered_by == new_record.triggered_by
    assert old_record.event == new_record.event
    assert old_record.level == new_record.level
    assert old_record.data == new_record.data
    assert old_record.metrics == new_record.metrics
    assert old_record.tags == new_record.tags

    # These change FORMAT but not meaning
    assert len(new_record.trace_id) == 32  # OTel 128-bit hex
    assert len(new_record.span_id) == 16   # OTel 64-bit hex

def test_log_output_to_elasticsearch_same_structure():
    """Verify ES documents have same structure."""

    old_doc = emit_and_capture_es_doc_old()
    new_doc = emit_and_capture_es_doc_new()

    # Same keys
    assert set(old_doc.keys()) == set(new_doc.keys())

    # Same nested structure
    assert set(old_doc['data'].keys()) == set(new_doc['data'].keys())
    assert set(old_doc['metrics'].keys()) == set(new_doc['metrics'].keys())

def test_console_output_format_identical():
    """Verify console output format unchanged."""

    old_output = capture_console_old()
    new_output = capture_console_new()

    # Format should be identical except for ID values
    # e.g., "[INFO] tool.input component=Navigate ..."
```

### Field-by-Field Validation Matrix

| Field | Validation Check | Pass Criteria |
|-------|------------------|---------------|
| `timestamp` | Type check | `datetime` object |
| `trace_id` | Length check | 32 chars (was variable) |
| `span_id` | Length check | 16 chars (was variable) |
| `parent_span_id` | Nullable check | `str` or `None` |
| `session_id` | Format check | `sess_` prefix preserved |
| `request_id` | Format check | `req_` prefix preserved |
| `level` | Enum check | DEBUG/INFO/WARNING/ERROR |
| `event` | Pattern check | `{component}.{action}` |
| `component_type` | Enum check | agent/tool/llm_client |
| `component_name` | Non-empty | string |
| `triggered_by` | Non-empty | string |
| `data` | Type check | `dict` |
| `metrics` | Type check | `dict` |
| `tags` | Type check | `list[str]` |

### Emitters API: No Breaking Changes

The emitter functions keep **exactly the same signatures**:

```python
# These function signatures DO NOT CHANGE

def emit_log(
    level: str,
    event: str,
    ctx: ObservabilityContext,  # Same type, different internals
    data: Dict[str, Any],
    metrics: Optional[Dict[str, Any]] = None,
    tags: Optional[List[str]] = None
) -> None:

def emit_component_start(
    component_type: str,
    component_name: str,
    ctx: ObservabilityContext,  # Same type
    input_data: Dict[str, Any]
) -> None:

def emit_component_end(
    component_type: str,
    component_name: str,
    ctx: ObservabilityContext,  # Same type
    output_data: Dict[str, Any],
    duration_ms: float,
    metrics: Optional[Dict[str, Any]] = None
) -> None:

def emit_component_error(
    component_type: str,
    component_name: str,
    ctx: ObservabilityContext,  # Same type
    exception: Exception,
    input_data: Dict[str, Any],
    duration_ms: float
) -> None:
```

**No code changes needed in places that call these functions.**

---

## Testing Strategy

### Unit Tests
1. **Span hierarchy** - Verify nested decorators create proper parent-child relationships
2. **Trace ID persistence** - Verify all spans in one agent run share the same trace_id
3. **New trace per run** - Verify each `agent.run()` call creates a new trace_id
4. **Log correlation** - Verify logs contain correct trace_id/span_id from active span
5. **Business metadata preserved** - Verify session_id, request_id, triggered_by unchanged

### Integration Tests
1. **End-to-end trace** - Run agent with tools, verify trace in Jaeger/Tempo
2. **Error propagation** - Verify errors properly set span status and record exception
3. **Async support** - Verify async decorators maintain context across await points
4. **Log-span correlation** - Query ES logs by trace_id, verify they match Jaeger spans
5. **Console output** - Verify console shows same format as before

### Test Code Example

```python
def test_nested_spans_share_trace_id():
    """All spans within one agent run share the same trace_id."""
    captured_spans = []

    @traced_tool(name="inner")
    def inner_tool():
        span = trace.get_current_span()
        captured_spans.append(span.get_span_context())
        return {}

    @traced_agent(name="test")
    def test_agent():
        span = trace.get_current_span()
        captured_spans.append(span.get_span_context())
        inner_tool()
        return {}

    test_agent()

    # Same trace_id
    assert captured_spans[0].trace_id == captured_spans[1].trace_id
    # Different span_ids
    assert captured_spans[0].span_id != captured_spans[1].span_id

def test_new_agent_run_creates_new_trace():
    """Each agent.run() creates a new trace."""
    trace_ids = []

    @traced_agent(name="test")
    def test_agent():
        span = trace.get_current_span()
        trace_ids.append(span.get_span_context().trace_id)
        return {}

    test_agent()
    test_agent()

    # Different trace_ids
    assert trace_ids[0] != trace_ids[1]
```

---

## Rollback Plan

If issues arise:
1. Keep old `context.py` as `context_legacy.py`
2. Feature flag to switch between old/new context systems
3. Gradual migration: decorators can check flag and use appropriate context

---

## Open Questions

1. **Session ID** - Should we keep `session_id` as business metadata on spans?
   - Option A: Add as span attribute (`span.set_attribute("session.id", ...)`)
   - Option B: Remove entirely

2. **TraceEvent schema** - Should we keep `TraceEvent` class?
   - Option A: Remove - spans are created by OTel directly
   - Option B: Convert to span events (`span.add_event(...)`)

3. **Backward compatibility** - How long to maintain dual-mode support?

---

## Timeline Estimate

| Phase | Effort | Dependencies |
|-------|--------|--------------|
| Phase 1: Tracer setup | Small | None |
| Phase 2: Remove custom context | Medium | Phase 1 |
| Phase 3: Rewrite decorators | Large | Phase 1, 2 |
| Phase 4: Update emitters | Medium | Phase 2 |
| Phase 5: Simplify handler | Medium | Phase 3 |
| Phase 6: Update main.py | Small | Phase 1-5 |
| Testing | Large | All phases |

---

## References

- [OpenTelemetry Python SDK](https://opentelemetry.io/docs/instrumentation/python/)
- [OTel Tracing Specification](https://opentelemetry.io/docs/specs/otel/trace/)
- [Span Hierarchy Best Practices](https://opentelemetry.io/docs/concepts/signals/traces/)
