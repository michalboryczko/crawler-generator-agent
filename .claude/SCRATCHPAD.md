# Scratchpad - Complex Reasoning Notes

## Current Problem Being Solved

Working on: Observability Refactoring (OpenTelemetry Logs + Traces Separation)

---

## Architectural Decisions

### Decision 1: Context Propagation Mechanism

**Options Considered:**
1. Thread-local storage
2. contextvars (chosen)
3. Explicit context passing

**Decision:** Use `contextvars` because:
- Native Python 3.7+ support
- Works correctly with asyncio
- Automatic isolation for concurrent operations
- Similar to OpenTelemetry's approach

### Decision 2: Decorator vs Explicit Calls

**Decision:** Decorator-based instrumentation because:
- Cleaner component code
- Consistent logging patterns
- Harder to forget logging
- Easy to apply uniformly

### Decision 3: Log Level as Metadata

**Decision:** Level is metadata only, never filter because:
- "Log everything" philosophy
- Filter at query time, not emission time
- No lost data
- Can always filter down, can't filter up

---

## Debugging Notes

(Empty - to be filled as issues arise)

---

## Implementation Notes

### Phase 0 Files to Create:
1. `src/observability/__init__.py` - Module exports
2. `src/observability/context.py` - ObservabilityContext, contextvars
3. `src/observability/schema.py` - LogRecord dataclass
4. `src/observability/serializers.py` - safe_serialize function
5. `src/observability/config.py` - ObservabilityConfig, initialization
6. `src/observability/outputs.py` - ConsoleOutput, JSONLinesOutput, OTLPOutput
7. `src/observability/emitters.py` - emit_log, emit_trace_event

### Key Implementation Details:
- ObservabilityContext uses dataclass with frozen=False for mutability
- LogRecord includes all fields from original TraceContext + LogMetrics
- safe_serialize handles circular refs via max_depth
- Outputs are thread-safe with locks

---

## Risk Register

| Risk | Mitigation | Status |
|------|------------|--------|
| Async context loss | Test with async functions extensively | Pending |
| Missing metrics | Compare output before/after migration | Pending |
| Performance regression | Benchmark before/after | Pending |
| Breaking changes | Keep old module as fallback | Pending |
