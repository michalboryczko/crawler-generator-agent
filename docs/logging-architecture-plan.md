# Comprehensive Logging Architecture Plan

## Executive Summary

This document outlines a structured logging architecture for the Crawler Agent multi-model, multi-tool AI system. The proposed solution transforms basic text logging into a rich, queryable observability system supporting distributed tracing, metrics collection, and visualization.

**Current State:**
- Basic Python `logging` with text format: `%(asctime)s - %(name)s - %(levelname)s - %(message)s`
- No correlation IDs or trace context
- No structured fields for machine parsing
- No metrics capture (tokens, latency, costs)
- No parent-child relationship tracking

**Target State:**
- OpenTelemetry-compatible structured logging with JSON Lines output
- Full trace/span hierarchy for agent→tool→LLM operations
- Rich context propagation (session, request, agent, span IDs)
- Metrics capture for LLM calls (tokens, latency, cost)
- PII redaction and sampling strategies
- Dashboard-ready data structure

**Infrastructure Requirements:**
- **Required:** None - works standalone with local JSON Lines files
- **Optional:** Elasticsearch/OpenSearch for search and dashboards
- **Optional:** OpenTelemetry Collector for distributed tracing
- **Optional:** Grafana/Kibana for visualization

The core implementation writes to local `.jsonl` files that can be:
1. Analyzed with simple Python scripts or `jq`
2. Ingested into log aggregators when needed
3. Viewed in trace viewers via OTel export (optional)

---

## Table of Contents

1. [Log Schema Specification](#1-log-schema-specification)
2. [Log Event Taxonomy](#2-log-event-taxonomy)
3. [Implementation Plan](#3-implementation-plan)
4. [Visualization Considerations](#4-visualization-considerations)
5. [Code Examples](#5-code-examples)
6. [Migration Strategy](#6-migration-strategy)
7. [Phased Implementation](#7-phased-implementation)

---

## 1. Log Schema Specification

### 1.1 Base Log Entry Schema

```json
{
  "timestamp": "2024-01-15T10:30:45.123456Z",
  "level": "INFO",
  "level_detail": "INFO.METRIC",
  "logger": "agents.browser",

  "trace_context": {
    "session_id": "sess_abc123",
    "request_id": "req_xyz789",
    "trace_id": "trace_def456",
    "span_id": "span_001",
    "parent_span_id": "span_000"
  },

  "event": {
    "category": "tool_execution",
    "type": "tool.execute.start",
    "name": "NavigateTool started"
  },

  "context": {
    "agent_id": "browser_agent",
    "agent_type": "BrowserAgent",
    "tool_name": "navigate",
    "iteration": 5
  },

  "data": {},

  "metrics": {
    "duration_ms": null,
    "tokens_input": null,
    "tokens_output": null
  },

  "tags": ["browser", "navigation", "tool"],

  "message": "NavigateTool starting navigation to https://example.com"
}
```

### 1.2 Field Definitions

#### Core Fields (Required)

| Field | Type | Description | Constraints |
|-------|------|-------------|-------------|
| `timestamp` | string | ISO 8601 with microseconds | Format: `YYYY-MM-DDTHH:mm:ss.ffffffZ` |
| `level` | enum | Standard log level | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `level_detail` | string | Sub-level for granular filtering | Pattern: `{LEVEL}.{SUBLEVEL}` |
| `logger` | string | Logger name/source module | Dot-notation: `agents.browser` |
| `event.category` | enum | High-level event category | See Event Categories below |
| `event.type` | string | Specific event type | Dot-notation: `tool.execute.start` |
| `event.name` | string | Human-readable event name | Max 100 chars |
| `message` | string | Human-readable description | Max 1000 chars |

#### Trace Context Fields (Required)

| Field | Type | Description | Constraints |
|-------|------|-------------|-------------|
| `trace_context.session_id` | string | Conversation/session correlation | Prefix: `sess_`, UUID format |
| `trace_context.request_id` | string | Single user request correlation | Prefix: `req_`, UUID format |
| `trace_context.trace_id` | string | Distributed trace ID | Prefix: `trace_`, UUID format |
| `trace_context.span_id` | string | Current operation span | Prefix: `span_`, sequential |
| `trace_context.parent_span_id` | string | Parent span for nesting | Null for root spans |

#### Context Fields (Conditional)

| Field | Type | When Required | Description |
|-------|------|---------------|-------------|
| `context.agent_id` | string | Agent events | Unique agent instance ID |
| `context.agent_type` | string | Agent events | Agent class name |
| `context.tool_name` | string | Tool events | Tool identifier |
| `context.tool_version` | string | Tool events | Tool version (default: "1.0") |
| `context.iteration` | int | Agent loop events | Current iteration number |
| `context.model_provider` | string | LLM events | "openai", "anthropic", etc. |
| `context.model_name` | string | LLM events | "gpt-4o", "gpt-4o-mini", etc. |
| `context.url` | string | Browser/HTTP events | Target URL (sanitized) |

#### Data Fields (Event-Specific)

| Field | Type | Description |
|-------|------|-------------|
| `data.input` | object | Sanitized input parameters |
| `data.output` | object | Truncated output summary |
| `data.error` | object | Error details if applicable |
| `data.decision` | object | Decision reasoning |
| `data.llm_request` | object | LLM request details |
| `data.llm_response` | object | LLM response summary |

#### Metrics Fields (Optional)

| Field | Type | Unit | Description |
|-------|------|------|-------------|
| `metrics.duration_ms` | float | milliseconds | Operation duration |
| `metrics.time_to_first_token_ms` | float | milliseconds | LLM TTFT |
| `metrics.tokens_input` | int | tokens | Input token count |
| `metrics.tokens_output` | int | tokens | Output token count |
| `metrics.tokens_total` | int | tokens | Total tokens |
| `metrics.estimated_cost_usd` | float | USD | Estimated API cost |
| `metrics.retry_count` | int | count | Number of retries |
| `metrics.content_size_bytes` | int | bytes | Content/payload size |

#### Tags (Required)

Array of strings for filtering. Standard tags include:
- Category tags: `agent`, `tool`, `llm`, `browser`, `http`, `memory`, `file`
- Status tags: `success`, `failure`, `retry`, `timeout`
- Priority tags: `critical`, `important`, `routine`

### 1.3 Level Detail Sub-Levels

```
DEBUG.VERBOSE    - Extremely detailed (e.g., full prompts, HTML content)
DEBUG.TRACE      - Trace-level debugging
DEBUG.INTERNAL   - Internal state changes

INFO.LIFECYCLE   - Start/stop/complete events
INFO.METRIC      - Metrics and measurements
INFO.DECISION    - Decision points and routing
INFO.PROGRESS    - Progress updates

WARNING.DEGRADED - Degraded operation (fallbacks activated)
WARNING.LIMIT    - Approaching limits (rate, context window)
WARNING.RETRY    - Retry attempts

ERROR.RECOVERABLE   - Errors that were handled
ERROR.UNRECOVERABLE - Errors requiring intervention
ERROR.EXTERNAL      - External service errors
```

### 1.4 Example Log Entries

#### Agent Start
```json
{
  "timestamp": "2024-01-15T10:30:45.123456Z",
  "level": "INFO",
  "level_detail": "INFO.LIFECYCLE",
  "logger": "agents.main",
  "trace_context": {
    "session_id": "sess_a1b2c3d4",
    "request_id": "req_e5f6g7h8",
    "trace_id": "trace_i9j0k1l2",
    "span_id": "span_001",
    "parent_span_id": null
  },
  "event": {
    "category": "agent_lifecycle",
    "type": "agent.start",
    "name": "MainAgent started"
  },
  "context": {
    "agent_id": "main_agent_001",
    "agent_type": "MainAgent",
    "target_url": "https://example.com/blog"
  },
  "data": {
    "task": "Create crawl plan for https://example.com/blog",
    "available_tools": ["memory_read", "memory_write", "run_browser_agent", "..."]
  },
  "metrics": {},
  "tags": ["agent", "lifecycle", "main_agent"],
  "message": "MainAgent started for URL: https://example.com/blog"
}
```

#### LLM Call
```json
{
  "timestamp": "2024-01-15T10:30:46.789012Z",
  "level": "INFO",
  "level_detail": "INFO.METRIC",
  "logger": "core.llm",
  "trace_context": {
    "session_id": "sess_a1b2c3d4",
    "request_id": "req_e5f6g7h8",
    "trace_id": "trace_i9j0k1l2",
    "span_id": "span_003",
    "parent_span_id": "span_002"
  },
  "event": {
    "category": "llm_interaction",
    "type": "llm.call.complete",
    "name": "LLM call completed"
  },
  "context": {
    "agent_id": "browser_agent_001",
    "agent_type": "BrowserAgent",
    "model_provider": "openai",
    "model_name": "gpt-4o",
    "iteration": 3
  },
  "data": {
    "llm_request": {
      "message_count": 7,
      "tools_provided": 6,
      "temperature": 0.0,
      "tool_choice": "auto"
    },
    "llm_response": {
      "finish_reason": "tool_calls",
      "tool_calls_count": 1,
      "tool_called": "navigate",
      "content_preview": null
    }
  },
  "metrics": {
    "duration_ms": 1523.45,
    "time_to_first_token_ms": 234.12,
    "tokens_input": 2847,
    "tokens_output": 156,
    "tokens_total": 3003,
    "estimated_cost_usd": 0.0234
  },
  "tags": ["llm", "openai", "gpt-4o", "tool_call"],
  "message": "LLM call completed: gpt-4o, 3003 tokens, 1523ms, tool_calls"
}
```

#### Tool Execution
```json
{
  "timestamp": "2024-01-15T10:30:48.345678Z",
  "level": "INFO",
  "level_detail": "INFO.LIFECYCLE",
  "logger": "tools.browser",
  "trace_context": {
    "session_id": "sess_a1b2c3d4",
    "request_id": "req_e5f6g7h8",
    "trace_id": "trace_i9j0k1l2",
    "span_id": "span_004",
    "parent_span_id": "span_003"
  },
  "event": {
    "category": "tool_execution",
    "type": "tool.execute.complete",
    "name": "NavigateTool completed"
  },
  "context": {
    "agent_id": "browser_agent_001",
    "tool_name": "navigate",
    "tool_version": "1.0"
  },
  "data": {
    "input": {
      "url": "https://example.com/blog"
    },
    "output": {
      "success": true,
      "result_preview": "Navigation successful"
    }
  },
  "metrics": {
    "duration_ms": 2156.78,
    "retry_count": 0
  },
  "tags": ["tool", "browser", "navigate", "success"],
  "message": "NavigateTool completed successfully: https://example.com/blog (2157ms)"
}
```

#### Error with Recovery
```json
{
  "timestamp": "2024-01-15T10:31:00.123456Z",
  "level": "WARNING",
  "level_detail": "WARNING.RETRY",
  "logger": "tools.http",
  "trace_context": {
    "session_id": "sess_a1b2c3d4",
    "request_id": "req_e5f6g7h8",
    "trace_id": "trace_i9j0k1l2",
    "span_id": "span_010",
    "parent_span_id": "span_009"
  },
  "event": {
    "category": "error",
    "type": "error.recoverable.retry",
    "name": "HTTP request retry"
  },
  "context": {
    "agent_id": "accessibility_agent_001",
    "tool_name": "http_request",
    "url": "https://example.com/api"
  },
  "data": {
    "error": {
      "type": "timeout",
      "message": "Request timed out after 30s",
      "attempt": 1,
      "max_attempts": 3,
      "retry_delay_ms": 1000
    },
    "recovery_action": "retry_with_backoff"
  },
  "metrics": {
    "duration_ms": 30000,
    "retry_count": 1
  },
  "tags": ["tool", "http", "error", "timeout", "retry"],
  "message": "HTTP request timed out, retrying (attempt 1/3)"
}
```

#### Decision Point
```json
{
  "timestamp": "2024-01-15T10:30:50.000000Z",
  "level": "INFO",
  "level_detail": "INFO.DECISION",
  "logger": "agents.main",
  "trace_context": {
    "session_id": "sess_a1b2c3d4",
    "request_id": "req_e5f6g7h8",
    "trace_id": "trace_i9j0k1l2",
    "span_id": "span_005",
    "parent_span_id": "span_001"
  },
  "event": {
    "category": "decision",
    "type": "decision.agent_routing",
    "name": "Sub-agent selection"
  },
  "context": {
    "agent_id": "main_agent_001",
    "agent_type": "MainAgent"
  },
  "data": {
    "decision": {
      "decision_type": "agent_routing",
      "selected": "BrowserAgent",
      "reason": "Initial site analysis required",
      "alternatives": ["SelectorAgent", "AccessibilityAgent"],
      "factors": {
        "workflow_phase": "site_analysis",
        "dependencies_met": true,
        "memory_state": "target_url set"
      }
    }
  },
  "metrics": {},
  "tags": ["decision", "routing", "agent"],
  "message": "Selected BrowserAgent for site analysis phase"
}
```

---

## 2. Log Event Taxonomy

### 2.1 Event Categories

```
agent_lifecycle    - Agent start/stop/iteration events
tool_execution     - Tool invocation and completion
llm_interaction    - LLM API calls and responses
decision           - Routing and selection decisions
memory_operation   - Memory read/write/search operations
browser_operation  - Browser navigation and DOM operations
http_operation     - HTTP request/response events
file_operation     - File system operations
error              - Error and exception events
metric             - Pure metric emissions
```

### 2.2 Complete Event Type Registry

#### Agent Lifecycle Events

| Event Type | When Fired | Key Data Fields |
|------------|------------|-----------------|
| `agent.start` | Agent instantiation | task, available_tools, config |
| `agent.iteration.start` | Beginning of reasoning loop | iteration_number, messages_count |
| `agent.iteration.complete` | End of reasoning loop | iteration_number, tool_called, duration_ms |
| `agent.complete` | Agent task completion | success, total_iterations, total_duration_ms |
| `agent.error` | Unhandled agent error | error_type, error_message, stack_trace |
| `agent.max_iterations` | Hit iteration limit | max_iterations, last_action |

#### Tool Execution Events

| Event Type | When Fired | Key Data Fields |
|------------|------------|-----------------|
| `tool.execute.start` | Tool execution begins | tool_name, input_params (sanitized) |
| `tool.execute.complete` | Tool execution ends | tool_name, success, output_summary, duration_ms |
| `tool.execute.error` | Tool execution fails | tool_name, error_type, error_message |
| `tool.retry` | Tool retry attempted | tool_name, attempt, max_attempts, reason |
| `tool.timeout` | Tool execution timeout | tool_name, timeout_ms |
| `tool.validation.error` | Input validation fails | tool_name, validation_errors |

#### Selector Extraction Events (New in Phase 8)

| Event Type | When Fired | Key Data Fields |
|------------|------------|-----------------|
| `selector.listing_pages.generated` | Listing page URLs generated | url_count, pagination_pattern, sample_rate |
| `selector.article_pages.generated` | Article page URLs sampled | url_count, groups_count, sample_rate_per_group |
| `selector.listing.extracted` | Listing page analyzed | url, selectors_found, article_urls_count |
| `selector.article.extracted` | Article page analyzed | url, selectors_found, fields_discovered |
| `selector.aggregation.complete` | Selector chains created | listing_chains_count, detail_chains_count |
| `selector.chain.created` | Individual selector chain built | field_name, chain_length, top_success_rate |

#### Batch Extraction Events

| Event Type | When Fired | Key Data Fields |
|------------|------------|-----------------|
| `batch.fetch.start` | Batch URL fetch begins | url_count, key_prefix |
| `batch.fetch.progress` | Single URL fetched | url, index, total, success |
| `batch.fetch.complete` | Batch fetch ends | successful_count, failed_count, duration_ms |
| `batch.extract.start` | Batch extraction begins | html_key_prefix, entry_type |
| `batch.extract.complete` | Batch extraction ends | extracted_count, total_urls_found |
| `batch.urls.collected` | URLs aggregated from batch | unique_urls_count, source_pages_count |

#### LLM Interaction Events

| Event Type | When Fired | Key Data Fields |
|------------|------------|-----------------|
| `llm.call.start` | LLM API call initiated | model, message_count, tools_count |
| `llm.call.complete` | LLM response received | model, tokens_*, duration_ms, finish_reason |
| `llm.call.error` | LLM API error | model, error_type, error_message |
| `llm.rate_limit` | Rate limit hit | model, retry_after_ms |
| `llm.context_truncation` | Context window truncated | model, tokens_before, tokens_after, strategy |
| `llm.tool_call.parsed` | Tool call extracted from response | tool_name, arguments_summary |
| `llm.content.generated` | Text content generated | content_preview, content_length |

#### Decision Events

| Event Type | When Fired | Key Data Fields |
|------------|------------|-----------------|
| `decision.agent_routing` | Sub-agent selected | selected_agent, reason, alternatives |
| `decision.tool_selection` | Tool chosen by LLM | selected_tool, confidence, context |
| `decision.model_selection` | Model chosen (if multi-model) | selected_model, reason, cost_factor |
| `decision.fallback_activated` | Fallback path taken | primary_failed, fallback_used, reason |
| `decision.retry_strategy` | Retry decision made | will_retry, attempt, backoff_ms |

#### Memory Operation Events

| Event Type | When Fired | Key Data Fields |
|------------|------------|-----------------|
| `memory.read` | Memory key read | key, found, value_preview |
| `memory.write` | Memory key written | key, value_size, overwritten |
| `memory.search` | Pattern search executed | pattern, matches_count |
| `memory.list` | Keys listed | total_keys |
| `memory.dump` | Memory exported to file | output_path, entries_count |

#### Browser Operation Events

| Event Type | When Fired | Key Data Fields |
|------------|------------|-----------------|
| `browser.navigate.start` | Navigation initiated | url |
| `browser.navigate.complete` | Navigation finished | url, duration_ms, status |
| `browser.navigate.error` | Navigation failed | url, error_type |
| `browser.html.fetched` | HTML retrieved | url, size_bytes, truncated |
| `browser.click` | Element clicked | selector, success |
| `browser.wait` | Wait completed | selector_or_timeout, duration_ms |
| `browser.query` | DOM query executed | selector, results_count |

#### HTTP Operation Events

| Event Type | When Fired | Key Data Fields |
|------------|------------|-----------------|
| `http.request.start` | HTTP request initiated | method, url, headers_summary |
| `http.request.complete` | HTTP response received | method, url, status_code, duration_ms |
| `http.request.error` | HTTP request failed | method, url, error_type |

#### File Operation Events

| Event Type | When Fired | Key Data Fields |
|------------|------------|-----------------|
| `file.create` | File created | path, size_bytes |
| `file.read` | File read | path, lines_read |
| `file.append` | File appended | path, bytes_appended |
| `file.replace` | File replaced | path, new_size_bytes |

#### Error Events

| Event Type | When Fired | Key Data Fields |
|------------|------------|-----------------|
| `error.validation` | Input validation error | field, expected, received |
| `error.timeout` | Operation timeout | operation, timeout_ms |
| `error.rate_limit` | Rate limit exceeded | service, retry_after |
| `error.external_service` | External service error | service, status_code, message |
| `error.internal` | Internal error | component, error_class, message, stack_trace |
| `error.recovery.success` | Error recovered | original_error, recovery_action |
| `error.recovery.failed` | Recovery failed | original_error, recovery_attempted |

### 2.3 Event Hierarchy for Trace Visualization

```
session_id: sess_abc123
└── request_id: req_xyz789 (create_crawl_plan)
    └── trace_id: trace_def456
        ├── span_001: MainAgent.run [agent.start → agent.complete]
        │   ├── span_002: LLM Call #1 [llm.call.start → llm.call.complete]
        │   ├── span_003: RunBrowserAgentTool [tool.execute.start → tool.execute.complete]
        │   │   └── span_004: BrowserAgent.run [agent.start → agent.complete]
        │   │       ├── span_005: LLM Call [llm.call.*]
        │   │       ├── span_006: NavigateTool [tool.execute.*]
        │   │       │   └── span_007: browser.navigate [browser.navigate.*]
        │   │       ├── span_008: GetHTMLTool [tool.execute.*]
        │   │       └── span_009: MemoryWriteTool [tool.execute.*, memory.write]
        │   ├── span_010: RunSelectorAgentTool [tool.execute.*]
        │   │   └── span_011: SelectorAgent.run [agent.*]
        │   │       └── ...
        │   └── ...
```

---

## 3. Implementation Plan

### 3.1 Logger Abstraction Interface

#### Core Logger Interface

```python
# src/core/structured_logger.py

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
import uuid


class LogLevel(Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogLevelDetail(Enum):
    # DEBUG sub-levels
    DEBUG_VERBOSE = "DEBUG.VERBOSE"
    DEBUG_TRACE = "DEBUG.TRACE"
    DEBUG_INTERNAL = "DEBUG.INTERNAL"

    # INFO sub-levels
    INFO_LIFECYCLE = "INFO.LIFECYCLE"
    INFO_METRIC = "INFO.METRIC"
    INFO_DECISION = "INFO.DECISION"
    INFO_PROGRESS = "INFO.PROGRESS"

    # WARNING sub-levels
    WARNING_DEGRADED = "WARNING.DEGRADED"
    WARNING_LIMIT = "WARNING.LIMIT"
    WARNING_RETRY = "WARNING.RETRY"

    # ERROR sub-levels
    ERROR_RECOVERABLE = "ERROR.RECOVERABLE"
    ERROR_UNRECOVERABLE = "ERROR.UNRECOVERABLE"
    ERROR_EXTERNAL = "ERROR.EXTERNAL"


class EventCategory(Enum):
    AGENT_LIFECYCLE = "agent_lifecycle"
    TOOL_EXECUTION = "tool_execution"
    LLM_INTERACTION = "llm_interaction"
    DECISION = "decision"
    MEMORY_OPERATION = "memory_operation"
    BROWSER_OPERATION = "browser_operation"
    HTTP_OPERATION = "http_operation"
    FILE_OPERATION = "file_operation"
    ERROR = "error"
    METRIC = "metric"


@dataclass
class TraceContext:
    """Immutable trace context for correlation."""
    session_id: str
    request_id: str
    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None

    def child_span(self) -> "TraceContext":
        """Create a child span context."""
        return TraceContext(
            session_id=self.session_id,
            request_id=self.request_id,
            trace_id=self.trace_id,
            span_id=f"span_{uuid.uuid4().hex[:12]}",
            parent_span_id=self.span_id
        )

    @classmethod
    def new_session(cls) -> "TraceContext":
        """Create a new root session context."""
        session_id = f"sess_{uuid.uuid4().hex[:12]}"
        request_id = f"req_{uuid.uuid4().hex[:12]}"
        trace_id = f"trace_{uuid.uuid4().hex[:12]}"
        span_id = f"span_{uuid.uuid4().hex[:12]}"
        return cls(
            session_id=session_id,
            request_id=request_id,
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=None
        )

    def new_request(self) -> "TraceContext":
        """Create a new request within the same session."""
        return TraceContext(
            session_id=self.session_id,
            request_id=f"req_{uuid.uuid4().hex[:12]}",
            trace_id=f"trace_{uuid.uuid4().hex[:12]}",
            span_id=f"span_{uuid.uuid4().hex[:12]}",
            parent_span_id=None
        )


@dataclass
class LogEvent:
    """Structured log event."""
    category: EventCategory
    event_type: str
    name: str


@dataclass
class LogMetrics:
    """Metrics associated with a log entry."""
    duration_ms: Optional[float] = None
    time_to_first_token_ms: Optional[float] = None
    tokens_input: Optional[int] = None
    tokens_output: Optional[int] = None
    tokens_total: Optional[int] = None
    estimated_cost_usd: Optional[float] = None
    retry_count: Optional[int] = None
    content_size_bytes: Optional[int] = None


@dataclass
class LogEntry:
    """Complete structured log entry."""
    timestamp: datetime
    level: LogLevel
    level_detail: LogLevelDetail
    logger: str
    trace_context: TraceContext
    event: LogEvent
    context: dict[str, Any]
    data: dict[str, Any]
    metrics: LogMetrics
    tags: list[str]
    message: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "level": self.level.value,
            "level_detail": self.level_detail.value,
            "logger": self.logger,
            "trace_context": {
                "session_id": self.trace_context.session_id,
                "request_id": self.trace_context.request_id,
                "trace_id": self.trace_context.trace_id,
                "span_id": self.trace_context.span_id,
                "parent_span_id": self.trace_context.parent_span_id,
            },
            "event": {
                "category": self.event.category.value,
                "type": self.event.event_type,
                "name": self.event.name,
            },
            "context": self.context,
            "data": self.data,
            "metrics": {
                k: v for k, v in {
                    "duration_ms": self.metrics.duration_ms,
                    "time_to_first_token_ms": self.metrics.time_to_first_token_ms,
                    "tokens_input": self.metrics.tokens_input,
                    "tokens_output": self.metrics.tokens_output,
                    "tokens_total": self.metrics.tokens_total,
                    "estimated_cost_usd": self.metrics.estimated_cost_usd,
                    "retry_count": self.metrics.retry_count,
                    "content_size_bytes": self.metrics.content_size_bytes,
                }.items() if v is not None
            },
            "tags": self.tags,
            "message": self.message,
        }


class LogOutput(ABC):
    """Abstract base for log outputs."""

    @abstractmethod
    def write(self, entry: LogEntry) -> None:
        """Write a log entry."""
        pass

    @abstractmethod
    def flush(self) -> None:
        """Flush any buffered entries."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Close the output."""
        pass


class StructuredLogger:
    """Main structured logger interface."""

    def __init__(
        self,
        name: str,
        trace_context: TraceContext,
        outputs: list[LogOutput],
        min_level: LogLevel = LogLevel.INFO,
        default_tags: list[str] = None,
        context: dict[str, Any] = None,
    ):
        self.name = name
        self.trace_context = trace_context
        self.outputs = outputs
        self.min_level = min_level
        self.default_tags = default_tags or []
        self.default_context = context or {}

    def _should_log(self, level: LogLevel) -> bool:
        """Check if level should be logged."""
        level_order = [LogLevel.DEBUG, LogLevel.INFO, LogLevel.WARNING, LogLevel.ERROR, LogLevel.CRITICAL]
        return level_order.index(level) >= level_order.index(self.min_level)

    def _emit(self, entry: LogEntry) -> None:
        """Emit log entry to all outputs."""
        if not self._should_log(entry.level):
            return
        for output in self.outputs:
            output.write(entry)

    def log(
        self,
        level: LogLevel,
        level_detail: LogLevelDetail,
        event: LogEvent,
        message: str,
        context: dict[str, Any] = None,
        data: dict[str, Any] = None,
        metrics: LogMetrics = None,
        tags: list[str] = None,
    ) -> None:
        """Log a structured event."""
        entry = LogEntry(
            timestamp=datetime.now(timezone.utc),
            level=level,
            level_detail=level_detail,
            logger=self.name,
            trace_context=self.trace_context,
            event=event,
            context={**self.default_context, **(context or {})},
            data=data or {},
            metrics=metrics or LogMetrics(),
            tags=self.default_tags + (tags or []),
            message=message,
        )
        self._emit(entry)

    def child(
        self,
        name: str = None,
        context: dict[str, Any] = None,
        tags: list[str] = None,
    ) -> "StructuredLogger":
        """Create a child logger with new span."""
        return StructuredLogger(
            name=name or self.name,
            trace_context=self.trace_context.child_span(),
            outputs=self.outputs,
            min_level=self.min_level,
            default_tags=self.default_tags + (tags or []),
            context={**self.default_context, **(context or {})},
        )

    # Convenience methods for common log levels
    def debug(self, event: LogEvent, message: str, **kwargs) -> None:
        self.log(LogLevel.DEBUG, LogLevelDetail.DEBUG_TRACE, event, message, **kwargs)

    def info(self, event: LogEvent, message: str, **kwargs) -> None:
        self.log(LogLevel.INFO, LogLevelDetail.INFO_LIFECYCLE, event, message, **kwargs)

    def warning(self, event: LogEvent, message: str, **kwargs) -> None:
        self.log(LogLevel.WARNING, LogLevelDetail.WARNING_DEGRADED, event, message, **kwargs)

    def error(self, event: LogEvent, message: str, **kwargs) -> None:
        self.log(LogLevel.ERROR, LogLevelDetail.ERROR_RECOVERABLE, event, message, **kwargs)
```

#### Log Outputs Implementation

```python
# src/core/log_outputs.py

import json
import sys
import threading
from datetime import datetime
from pathlib import Path
from queue import Queue
from typing import TextIO

from .structured_logger import LogEntry, LogLevel, LogOutput


class JSONLinesOutput(LogOutput):
    """JSON Lines output for log aggregators."""

    def __init__(self, file_path: Path | str | None = None, stream: TextIO = None):
        self.file_path = Path(file_path) if file_path else None
        self.stream = stream
        self._file = None

        if self.file_path:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            self._file = open(self.file_path, "a", encoding="utf-8")

    def write(self, entry: LogEntry) -> None:
        line = json.dumps(entry.to_dict(), default=str) + "\n"
        if self._file:
            self._file.write(line)
        if self.stream:
            self.stream.write(line)

    def flush(self) -> None:
        if self._file:
            self._file.flush()
        if self.stream:
            self.stream.flush()

    def close(self) -> None:
        if self._file:
            self._file.close()


class ConsoleOutput(LogOutput):
    """Human-readable console output for development."""

    LEVEL_COLORS = {
        LogLevel.DEBUG: "\033[36m",    # Cyan
        LogLevel.INFO: "\033[32m",     # Green
        LogLevel.WARNING: "\033[33m",  # Yellow
        LogLevel.ERROR: "\033[31m",    # Red
        LogLevel.CRITICAL: "\033[35m", # Magenta
    }
    RESET = "\033[0m"
    DIM = "\033[2m"

    def __init__(self, stream: TextIO = None, color: bool = True):
        self.stream = stream or sys.stdout
        self.color = color

    def write(self, entry: LogEntry) -> None:
        color = self.LEVEL_COLORS.get(entry.level, "") if self.color else ""
        reset = self.RESET if self.color else ""
        dim = self.DIM if self.color else ""

        # Format: TIMESTAMP LEVEL [SPAN] EVENT_TYPE - MESSAGE
        timestamp = entry.timestamp.strftime("%H:%M:%S.%f")[:-3]
        span_short = entry.trace_context.span_id[-8:]

        line = (
            f"{dim}{timestamp}{reset} "
            f"{color}{entry.level.value:8}{reset} "
            f"{dim}[{span_short}]{reset} "
            f"{entry.event.event_type:30} "
            f"- {entry.message}"
        )

        # Add metrics if present
        metrics_parts = []
        if entry.metrics.duration_ms:
            metrics_parts.append(f"{entry.metrics.duration_ms:.0f}ms")
        if entry.metrics.tokens_total:
            metrics_parts.append(f"{entry.metrics.tokens_total} tok")
        if entry.metrics.estimated_cost_usd:
            metrics_parts.append(f"${entry.metrics.estimated_cost_usd:.4f}")

        if metrics_parts:
            line += f" {dim}({', '.join(metrics_parts)}){reset}"

        self.stream.write(line + "\n")

    def flush(self) -> None:
        self.stream.flush()

    def close(self) -> None:
        pass


class AsyncBufferedOutput(LogOutput):
    """Async buffered output wrapper for performance."""

    def __init__(self, wrapped: LogOutput, buffer_size: int = 100):
        self.wrapped = wrapped
        self.buffer_size = buffer_size
        self.queue: Queue[LogEntry | None] = Queue()
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()

    def _worker(self) -> None:
        buffer = []
        while True:
            entry = self.queue.get()
            if entry is None:  # Shutdown signal
                for e in buffer:
                    self.wrapped.write(e)
                self.wrapped.flush()
                break

            buffer.append(entry)
            if len(buffer) >= self.buffer_size:
                for e in buffer:
                    self.wrapped.write(e)
                self.wrapped.flush()
                buffer.clear()

    def write(self, entry: LogEntry) -> None:
        self.queue.put(entry)

    def flush(self) -> None:
        pass  # Flushing happens in worker

    def close(self) -> None:
        self.queue.put(None)  # Signal shutdown
        self.thread.join(timeout=5.0)
        self.wrapped.close()


class OpenTelemetryOutput(LogOutput):
    """OpenTelemetry-compatible span output."""

    def __init__(self, service_name: str, endpoint: str = None):
        self.service_name = service_name
        self.endpoint = endpoint
        # In a real implementation, initialize OTLP exporter here
        # from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

    def write(self, entry: LogEntry) -> None:
        # Convert LogEntry to OTel span format
        span_data = {
            "traceId": entry.trace_context.trace_id.replace("trace_", ""),
            "spanId": entry.trace_context.span_id.replace("span_", ""),
            "parentSpanId": (
                entry.trace_context.parent_span_id.replace("span_", "")
                if entry.trace_context.parent_span_id else None
            ),
            "name": entry.event.name,
            "kind": "INTERNAL",
            "startTimeUnixNano": int(entry.timestamp.timestamp() * 1e9),
            "endTimeUnixNano": int(
                (entry.timestamp.timestamp() + (entry.metrics.duration_ms or 0) / 1000) * 1e9
            ),
            "attributes": [
                {"key": "service.name", "value": {"stringValue": self.service_name}},
                {"key": "event.category", "value": {"stringValue": entry.event.category.value}},
                {"key": "event.type", "value": {"stringValue": entry.event.event_type}},
                {"key": "log.level", "value": {"stringValue": entry.level.value}},
                *[
                    {"key": f"context.{k}", "value": {"stringValue": str(v)}}
                    for k, v in entry.context.items()
                ],
                *[
                    {"key": f"tag.{tag}", "value": {"boolValue": True}}
                    for tag in entry.tags
                ],
            ],
            "status": {
                "code": "ERROR" if entry.level in (LogLevel.ERROR, LogLevel.CRITICAL) else "OK"
            },
        }
        # In real implementation, send to OTLP endpoint
        # self.exporter.export([span_data])

    def flush(self) -> None:
        pass

    def close(self) -> None:
        pass
```

### 3.2 Context Propagation Strategy

#### Context Manager for Spans

```python
# src/core/log_context.py

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Generator

from .structured_logger import StructuredLogger, TraceContext


# Global context variable for current logger
_current_logger: ContextVar[StructuredLogger | None] = ContextVar("current_logger", default=None)


def get_logger() -> StructuredLogger | None:
    """Get the current logger from context."""
    return _current_logger.get()


def set_logger(logger: StructuredLogger) -> None:
    """Set the current logger in context."""
    _current_logger.set(logger)


@contextmanager
def span(
    name: str,
    context: dict = None,
    tags: list[str] = None,
) -> Generator[StructuredLogger, None, None]:
    """Context manager for creating a child span."""
    parent_logger = get_logger()
    if parent_logger is None:
        raise RuntimeError("No logger in context. Initialize with LoggerManager first.")

    child_logger = parent_logger.child(name=name, context=context, tags=tags)
    token = _current_logger.set(child_logger)
    try:
        yield child_logger
    finally:
        _current_logger.reset(token)


class LoggerManager:
    """Manager for initializing and accessing loggers."""

    _instance: "LoggerManager | None" = None

    def __init__(self, root_logger: StructuredLogger):
        self.root_logger = root_logger
        LoggerManager._instance = self
        set_logger(root_logger)

    @classmethod
    def get_instance(cls) -> "LoggerManager":
        if cls._instance is None:
            raise RuntimeError("LoggerManager not initialized")
        return cls._instance

    @classmethod
    def initialize(
        cls,
        outputs: list,
        min_level: str = "INFO",
        service_name: str = "crawler-agent",
    ) -> "LoggerManager":
        """Initialize the logging system."""
        from .structured_logger import LogLevel

        trace_context = TraceContext.new_session()
        root_logger = StructuredLogger(
            name=service_name,
            trace_context=trace_context,
            outputs=outputs,
            min_level=LogLevel[min_level],
            default_tags=[service_name],
            context={"service": service_name},
        )
        return cls(root_logger)
```

#### Integration with Agent Base Class

```python
# Modifications to src/agents/base.py

from src.core.log_context import get_logger, span
from src.core.structured_logger import (
    EventCategory, LogEvent, LogLevel, LogLevelDetail, LogMetrics
)


class BaseAgent(ABC):
    """Base agent with integrated structured logging."""

    def __init__(self, name: str, llm: LLMClient, tools: list[BaseTool]):
        self.name = name
        self.llm = llm
        self.tools = tools
        self._tool_map = {tool.name: tool for tool in tools}
        self.messages: list[dict] = []

        # Get logger from context and create agent-specific child
        parent_logger = get_logger()
        self.logger = parent_logger.child(
            name=f"agents.{name}",
            context={"agent_type": self.__class__.__name__},
            tags=["agent", name],
        ) if parent_logger else None

    def run(self, task: str) -> dict:
        """Execute agent with full logging."""
        if self.logger:
            self._log_agent_start(task)

        start_time = time.time()
        iteration = 0

        try:
            # ... existing run logic with logging calls ...

            result = self._run_loop(task)

            if self.logger:
                self._log_agent_complete(
                    success=result.get("success", False),
                    iterations=iteration,
                    duration_ms=(time.time() - start_time) * 1000,
                )

            return result

        except Exception as e:
            if self.logger:
                self._log_agent_error(e, iteration)
            raise

    def _log_agent_start(self, task: str) -> None:
        self.logger.log(
            level=LogLevel.INFO,
            level_detail=LogLevelDetail.INFO_LIFECYCLE,
            event=LogEvent(
                category=EventCategory.AGENT_LIFECYCLE,
                event_type="agent.start",
                name=f"{self.name} started",
            ),
            message=f"{self.name} starting task: {task[:100]}...",
            context={"agent_id": id(self)},
            data={
                "task": task,
                "available_tools": list(self._tool_map.keys()),
            },
            tags=["lifecycle", "start"],
        )

    def _log_agent_complete(self, success: bool, iterations: int, duration_ms: float) -> None:
        self.logger.log(
            level=LogLevel.INFO,
            level_detail=LogLevelDetail.INFO_LIFECYCLE,
            event=LogEvent(
                category=EventCategory.AGENT_LIFECYCLE,
                event_type="agent.complete",
                name=f"{self.name} completed",
            ),
            message=f"{self.name} completed: {'success' if success else 'failed'} after {iterations} iterations",
            metrics=LogMetrics(duration_ms=duration_ms),
            data={"success": success, "iterations": iterations},
            tags=["lifecycle", "complete", "success" if success else "failure"],
        )
```

### 3.3 Integration Points in Existing Code

#### File-by-File Integration Map

| File | Integration Points | Priority |
|------|-------------------|----------|
| `main.py` | Initialize LoggerManager, wrap main execution | P0 |
| `src/core/llm.py` | Log all LLM calls with tokens/latency/cost | P0 |
| `src/agents/base.py` | Log agent lifecycle, iterations, tool execution | P0 |
| `src/tools/base.py` | Log tool execution start/complete/error | P1 |
| `src/tools/browser.py` | Log browser operations with URLs | P1 |
| `src/tools/memory.py` | Log memory operations | P2 |
| `src/tools/extraction.py` | Log extraction with batch progress, URL collection | P1 |
| `src/tools/selector_extraction.py` | Log selector discovery, aggregation, chain creation | P1 |
| `src/tools/selector_sampling.py` | Log page sampling decisions, URL grouping | P1 |
| `src/tools/http.py` | Log HTTP requests/responses | P1 |
| `src/tools/orchestration.py` | Log sub-agent invocations | P1 |
| `src/tools/plan_generator.py` | Log plan generation with field discovery | P2 |
| `src/agents/main_agent.py` | Log workflow phase decisions | P1 |
| `src/agents/selector_agent.py` | Log selector workflow steps | P1 |
| `src/core/browser.py` | Log CDP operations | P2 |

#### Specific Integration: LLMClient

```python
# Modifications to src/core/llm.py

import time
from src.core.log_context import get_logger
from src.core.structured_logger import (
    EventCategory, LogEvent, LogLevel, LogLevelDetail, LogMetrics
)

# Cost per 1K tokens (approximate, update as needed)
MODEL_COSTS = {
    "gpt-4o": {"input": 0.005, "output": 0.015},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-4-turbo": {"input": 0.01, "output": 0.03},
}


class LLMClient:
    def chat(self, messages, tools=None, tool_choice="auto", parallel_tool_calls=False):
        logger = get_logger()

        # Log start
        if logger:
            logger.log(
                level=LogLevel.DEBUG,
                level_detail=LogLevelDetail.DEBUG_TRACE,
                event=LogEvent(
                    category=EventCategory.LLM_INTERACTION,
                    event_type="llm.call.start",
                    name="LLM call started",
                ),
                message=f"LLM call to {self.model} with {len(messages)} messages",
                context={
                    "model_provider": "openai",
                    "model_name": self.model,
                },
                data={
                    "llm_request": {
                        "message_count": len(messages),
                        "tools_provided": len(tools) if tools else 0,
                        "temperature": self.temperature,
                        "tool_choice": tool_choice,
                    }
                },
                tags=["llm", "openai", self.model],
            )

        start_time = time.time()

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=[tool.to_openai_schema() for tool in tools] if tools else None,
                tool_choice=tool_choice if tools else None,
                parallel_tool_calls=parallel_tool_calls,
                temperature=self.temperature,
            )

            duration_ms = (time.time() - start_time) * 1000

            # Extract token usage
            usage = response.usage
            tokens_input = usage.prompt_tokens if usage else 0
            tokens_output = usage.completion_tokens if usage else 0
            tokens_total = usage.total_tokens if usage else 0

            # Estimate cost
            cost_rates = MODEL_COSTS.get(self.model, {"input": 0, "output": 0})
            estimated_cost = (
                (tokens_input / 1000) * cost_rates["input"] +
                (tokens_output / 1000) * cost_rates["output"]
            )

            # Parse response
            choice = response.choices[0]
            finish_reason = choice.finish_reason
            content = choice.message.content
            tool_calls = self._parse_tool_calls(choice.message.tool_calls)

            # Log completion
            if logger:
                logger.log(
                    level=LogLevel.INFO,
                    level_detail=LogLevelDetail.INFO_METRIC,
                    event=LogEvent(
                        category=EventCategory.LLM_INTERACTION,
                        event_type="llm.call.complete",
                        name="LLM call completed",
                    ),
                    message=f"LLM {self.model}: {tokens_total} tokens, {duration_ms:.0f}ms, {finish_reason}",
                    context={
                        "model_provider": "openai",
                        "model_name": self.model,
                    },
                    data={
                        "llm_response": {
                            "finish_reason": finish_reason,
                            "tool_calls_count": len(tool_calls) if tool_calls else 0,
                            "tool_called": tool_calls[0]["name"] if tool_calls else None,
                            "content_preview": content[:200] if content else None,
                        }
                    },
                    metrics=LogMetrics(
                        duration_ms=duration_ms,
                        tokens_input=tokens_input,
                        tokens_output=tokens_output,
                        tokens_total=tokens_total,
                        estimated_cost_usd=estimated_cost,
                    ),
                    tags=["llm", "openai", self.model, finish_reason],
                )

            return {
                "content": content,
                "finish_reason": finish_reason,
                "tool_calls": tool_calls,
            }

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000

            if logger:
                logger.log(
                    level=LogLevel.ERROR,
                    level_detail=LogLevelDetail.ERROR_EXTERNAL,
                    event=LogEvent(
                        category=EventCategory.LLM_INTERACTION,
                        event_type="llm.call.error",
                        name="LLM call failed",
                    ),
                    message=f"LLM call failed: {type(e).__name__}: {str(e)}",
                    context={
                        "model_provider": "openai",
                        "model_name": self.model,
                    },
                    data={
                        "error": {
                            "type": type(e).__name__,
                            "message": str(e),
                        }
                    },
                    metrics=LogMetrics(duration_ms=duration_ms),
                    tags=["llm", "openai", self.model, "error"],
                )

            raise
```

### 3.4 Configuration Options

```python
# src/core/log_config.py

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from .log_outputs import (
    AsyncBufferedOutput,
    ConsoleOutput,
    JSONLinesOutput,
    OpenTelemetryOutput,
)
from .structured_logger import LogLevel, LogOutput


@dataclass
class LoggingConfig:
    """Logging configuration."""

    # General settings
    min_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    service_name: str = "crawler-agent"

    # Output settings
    console_enabled: bool = True
    console_color: bool = True

    jsonl_enabled: bool = True
    jsonl_path: Path | None = None  # None = auto-generate based on session
    jsonl_async: bool = True
    jsonl_buffer_size: int = 100

    otel_enabled: bool = False
    otel_endpoint: str = "http://localhost:4317"

    # Sampling settings (for high-volume events)
    sampling_enabled: bool = False
    sampling_rate: float = 1.0  # 1.0 = log everything
    sampled_event_types: list[str] = field(default_factory=lambda: [
        "memory.read",
        "memory.write",
        "browser.query",
    ])

    # PII redaction
    redact_pii: bool = True
    redact_patterns: list[str] = field(default_factory=lambda: [
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",  # Email
        r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",  # Phone
        r"\b\d{16}\b",  # Credit card (simple)
    ])

    # Content truncation
    max_content_preview: int = 500
    max_url_params: int = 100

    def create_outputs(self) -> list[LogOutput]:
        """Create log outputs based on configuration."""
        outputs = []

        if self.console_enabled:
            outputs.append(ConsoleOutput(color=self.console_color))

        if self.jsonl_enabled:
            jsonl_output = JSONLinesOutput(file_path=self.jsonl_path)
            if self.jsonl_async:
                jsonl_output = AsyncBufferedOutput(
                    jsonl_output,
                    buffer_size=self.jsonl_buffer_size
                )
            outputs.append(jsonl_output)

        if self.otel_enabled:
            outputs.append(OpenTelemetryOutput(
                service_name=self.service_name,
                endpoint=self.otel_endpoint,
            ))

        return outputs

    @classmethod
    def from_env(cls) -> "LoggingConfig":
        """Load configuration from environment variables."""
        import os

        return cls(
            min_level=os.environ.get("LOG_LEVEL", "INFO"),
            service_name=os.environ.get("SERVICE_NAME", "crawler-agent"),
            console_enabled=os.environ.get("LOG_CONSOLE", "true").lower() == "true",
            console_color=os.environ.get("LOG_COLOR", "true").lower() == "true",
            jsonl_enabled=os.environ.get("LOG_JSONL", "true").lower() == "true",
            jsonl_path=Path(p) if (p := os.environ.get("LOG_JSONL_PATH")) else None,
            otel_enabled=os.environ.get("LOG_OTEL", "false").lower() == "true",
            otel_endpoint=os.environ.get("LOG_OTEL_ENDPOINT", "http://localhost:4317"),
            sampling_enabled=os.environ.get("LOG_SAMPLING", "false").lower() == "true",
            sampling_rate=float(os.environ.get("LOG_SAMPLING_RATE", "1.0")),
            redact_pii=os.environ.get("LOG_REDACT_PII", "true").lower() == "true",
        )
```

### 3.5 PII Redaction Implementation

```python
# src/core/pii_redactor.py

import re
from typing import Any


class PIIRedactor:
    """Redacts sensitive information from log data."""

    DEFAULT_PATTERNS = {
        "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        "phone_us": r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b",
        "credit_card": r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b",
        "ssn": r"\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b",
        "api_key": r"\b(sk|pk|api)[_-]?[a-zA-Z0-9]{20,}\b",
        "bearer_token": r"Bearer\s+[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+",
    }

    SENSITIVE_KEYS = {
        "password", "passwd", "secret", "token", "api_key", "apikey",
        "authorization", "auth", "credential", "private_key", "access_token",
    }

    def __init__(self, patterns: dict[str, str] = None, placeholder: str = "[REDACTED]"):
        self.patterns = {
            **self.DEFAULT_PATTERNS,
            **(patterns or {}),
        }
        self.compiled_patterns = {
            name: re.compile(pattern, re.IGNORECASE)
            for name, pattern in self.patterns.items()
        }
        self.placeholder = placeholder

    def redact_string(self, value: str) -> str:
        """Redact sensitive patterns from a string."""
        result = value
        for name, pattern in self.compiled_patterns.items():
            result = pattern.sub(f"{self.placeholder}:{name}", result)
        return result

    def redact_dict(self, data: dict[str, Any]) -> dict[str, Any]:
        """Recursively redact sensitive data from a dictionary."""
        result = {}
        for key, value in data.items():
            # Check if key itself indicates sensitive data
            if any(sensitive in key.lower() for sensitive in self.SENSITIVE_KEYS):
                result[key] = self.placeholder
            elif isinstance(value, str):
                result[key] = self.redact_string(value)
            elif isinstance(value, dict):
                result[key] = self.redact_dict(value)
            elif isinstance(value, list):
                result[key] = self.redact_list(value)
            else:
                result[key] = value
        return result

    def redact_list(self, data: list) -> list:
        """Recursively redact sensitive data from a list."""
        result = []
        for item in data:
            if isinstance(item, str):
                result.append(self.redact_string(item))
            elif isinstance(item, dict):
                result.append(self.redact_dict(item))
            elif isinstance(item, list):
                result.append(self.redact_list(item))
            else:
                result.append(item)
        return result

    def redact(self, data: Any) -> Any:
        """Redact any data type."""
        if isinstance(data, str):
            return self.redact_string(data)
        elif isinstance(data, dict):
            return self.redact_dict(data)
        elif isinstance(data, list):
            return self.redact_list(data)
        return data
```

---

## 4. Visualization Considerations

### 4.0 Local Analysis (No Infrastructure Required)

The JSON Lines format enables powerful analysis with simple tools:

#### Using jq (command line)

```bash
# View all errors
cat logs/agent_*.jsonl | jq 'select(.level == "ERROR")'

# Get LLM costs summary
cat logs/agent_*.jsonl | jq 'select(.event.type == "llm.call.complete") | .metrics.estimated_cost_usd' | jq -s 'add'

# Find slow operations (>5s)
cat logs/agent_*.jsonl | jq 'select(.metrics.duration_ms > 5000) | {event: .event.type, duration: .metrics.duration_ms}'

# Trace a specific request
cat logs/agent_*.jsonl | jq 'select(.trace_context.request_id == "req_xyz789")'

# Count events by type
cat logs/agent_*.jsonl | jq -r '.event.type' | sort | uniq -c | sort -rn
```

#### Using Python

```python
import json
from pathlib import Path
from collections import defaultdict

def load_logs(log_dir: str = "logs") -> list[dict]:
    """Load all log entries from JSONL files."""
    entries = []
    for path in Path(log_dir).glob("*.jsonl"):
        with open(path) as f:
            entries.extend(json.loads(line) for line in f if line.strip())
    return entries

def analyze_costs(entries: list[dict]) -> dict:
    """Analyze LLM costs by model."""
    costs = defaultdict(float)
    for e in entries:
        if e.get("event", {}).get("type") == "llm.call.complete":
            model = e.get("context", {}).get("model_name", "unknown")
            cost = e.get("metrics", {}).get("estimated_cost_usd", 0)
            costs[model] += cost
    return dict(costs)

def find_errors(entries: list[dict]) -> list[dict]:
    """Find all error events."""
    return [e for e in entries if e.get("level") == "ERROR"]

def trace_request(entries: list[dict], request_id: str) -> list[dict]:
    """Get all events for a specific request."""
    return sorted(
        [e for e in entries if e.get("trace_context", {}).get("request_id") == request_id],
        key=lambda x: x.get("timestamp", "")
    )

# Example usage
logs = load_logs()
print(f"Total entries: {len(logs)}")
print(f"Costs by model: {analyze_costs(logs)}")
print(f"Error count: {len(find_errors(logs))}")
```

### 4.1 Key Queries and Views

#### Essential Queries

| Query | Purpose | Fields Used |
|-------|---------|-------------|
| Trace timeline | Visualize full request execution | trace_id, span_id, parent_span_id, timestamp, duration_ms |
| Error aggregation | Error hotspots by type | event.type, data.error.type, context.agent_type |
| LLM cost analysis | Token/cost tracking | metrics.tokens_*, metrics.estimated_cost_usd, context.model_name |
| Tool performance | Slow tool identification | context.tool_name, metrics.duration_ms |
| Agent iteration analysis | Loop efficiency | context.agent_type, context.iteration |
| Session overview | High-level request status | session_id, request_id, level |

#### Useful Filters

```
# Find all errors in a session
session_id:sess_abc123 AND level:ERROR

# Find slow LLM calls (>5s)
event.type:llm.call.complete AND metrics.duration_ms:>5000

# Find tool failures for a specific tool
event.type:tool.execute.error AND context.tool_name:navigate

# Find decision points
event.category:decision

# Find all browser navigation for a trace
trace_id:trace_xyz789 AND event.type:browser.navigate.*

# Cost analysis by model
event.type:llm.call.complete | stats sum(metrics.estimated_cost_usd) by context.model_name
```

### 4.2 Suggested Indexes

For Elasticsearch/OpenSearch:
```json
{
  "mappings": {
    "properties": {
      "timestamp": { "type": "date" },
      "level": { "type": "keyword" },
      "level_detail": { "type": "keyword" },
      "logger": { "type": "keyword" },
      "trace_context.session_id": { "type": "keyword" },
      "trace_context.request_id": { "type": "keyword" },
      "trace_context.trace_id": { "type": "keyword" },
      "trace_context.span_id": { "type": "keyword" },
      "trace_context.parent_span_id": { "type": "keyword" },
      "event.category": { "type": "keyword" },
      "event.type": { "type": "keyword" },
      "context.agent_type": { "type": "keyword" },
      "context.agent_id": { "type": "keyword" },
      "context.tool_name": { "type": "keyword" },
      "context.model_name": { "type": "keyword" },
      "metrics.duration_ms": { "type": "float" },
      "metrics.tokens_total": { "type": "integer" },
      "metrics.estimated_cost_usd": { "type": "float" },
      "tags": { "type": "keyword" },
      "message": { "type": "text" }
    }
  }
}
```

### 4.3 Dashboard Mockup Concepts

#### Main Dashboard Panels

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CRAWLER AGENT DASHBOARD                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐           │
│  │  REQUESTS TODAY  │  │   TOTAL COST     │  │  ERROR RATE      │           │
│  │       247        │  │     $12.45       │  │     2.3%         │           │
│  │   ▲ 12% vs yday  │  │   ▼ 8% vs yday   │  │   ▼ 0.5%         │           │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘           │
│                                                                              │
│  ┌────────────────────────────────────┐  ┌────────────────────────────────┐ │
│  │     REQUESTS OVER TIME             │  │    TOKEN USAGE BY MODEL        │ │
│  │  ▁▂▃▄▅▆▇█▇▆▅▄▃▂▁▂▃▄▅▆▇            │  │  ┌────────┐                    │ │
│  │                                    │  │  │gpt-4o  │████████████ 78%    │ │
│  │  ───────────────────────────────   │  │  │gpt-4o- │████ 22%            │ │
│  │  00:00  06:00  12:00  18:00  24:00 │  │  │mini    │                    │ │
│  └────────────────────────────────────┘  └────────────────────────────────┘ │
│                                                                              │
│  ┌────────────────────────────────────┐  ┌────────────────────────────────┐ │
│  │   AGENT PERFORMANCE (P95 LATENCY)  │  │    TOP ERRORS                  │ │
│  │                                    │  │                                │ │
│  │  MainAgent       ████████ 45s      │  │  timeout          ███████ 12   │ │
│  │  BrowserAgent    ████ 23s          │  │  rate_limit       ████ 7       │ │
│  │  SelectorAgent   ██████ 34s        │  │  navigation_err   ██ 3         │ │
│  │  AccessibilityAg █ 5s              │  │  validation       █ 1          │ │
│  │  DataPrepAgent   ███ 15s           │  │                                │ │
│  └────────────────────────────────────┘  └────────────────────────────────┘ │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                    RECENT REQUESTS                                    │   │
│  │ ──────────────────────────────────────────────────────────────────── │   │
│  │ TIME     SESSION      STATUS  DURATION  TOKENS   COST    ITERATIONS  │   │
│  │ 14:23    sess_abc123  ✓       2m 34s    45,230   $0.82   47          │   │
│  │ 14:21    sess_def456  ✗       45s       12,100   $0.21   12          │   │
│  │ 14:18    sess_ghi789  ✓       3m 12s    52,400   $0.95   52          │   │
│  │ 14:15    sess_jkl012  ✓       1m 45s    28,300   $0.51   31          │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### Trace View Panel

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  TRACE: trace_abc123   SESSION: sess_xyz789   STATUS: ✓ SUCCESS             │
│  Duration: 2m 34s   Tokens: 45,230   Cost: $0.82   Spans: 127               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Timeline (Waterfall View)                                                   │
│  ════════════════════════════════════════════════════════════════════════   │
│                                                                              │
│  ├─ MainAgent.run [154s] ═══════════════════════════════════════════════    │
│  │   ├─ llm.call #1 [1.2s] ██                                               │
│  │   ├─ RunBrowserAgentTool [45s] ════════════════                          │
│  │   │   └─ BrowserAgent.run [44s] ═══════════════                          │
│  │   │       ├─ llm.call [0.8s] █                                           │
│  │   │       ├─ NavigateTool [2.1s] ███                                     │
│  │   │       │   └─ browser.navigate [2.0s] ███                             │
│  │   │       ├─ llm.call [1.1s] █                                           │
│  │   │       ├─ GetHTMLTool [0.3s] █                                        │
│  │   │       ├─ llm.call [0.9s] █                                           │
│  │   │       └─ MemoryWriteTool [0.1s]                                      │
│  │   │                                                                       │
│  │   ├─ llm.call #2 [1.5s] ██                                               │
│  │   ├─ RunSelectorAgentTool [62s] ═══════════════════════                  │
│  │   │   └─ SelectorAgent.run [61s] ══════════════════════                  │
│  │   │       └─ ... (34 child spans)                                        │
│  │   │                                                                       │
│  │   └─ ... (more spans)                                                    │
│  │                                                                           │
│  └─────────────────────────────────────────────────────────────────────────  │
│                                                                              │
│  [Span Details] span_007: NavigateTool                                       │
│  ───────────────────────────────────────────────────────────────────────    │
│  Start: 14:23:05.123   Duration: 2156ms   Status: SUCCESS                   │
│  Tags: tool, browser, navigate, success                                      │
│  Input: {"url": "https://example.com/blog"}                                 │
│  Output: {"success": true, "result": "Navigation successful"}                │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.4 Metrics to Display

| Metric | Aggregation | Visualization |
|--------|-------------|---------------|
| Request count | Count per time bucket | Line chart |
| Request duration | P50, P95, P99 | Line chart with bands |
| Error rate | Count / Total * 100 | Line chart, alert threshold |
| Token usage | Sum by model | Stacked bar chart |
| API cost | Sum by model, time | Area chart |
| Agent iterations | Average, max | Bar chart by agent |
| Tool success rate | Success / Total | Gauge per tool |
| Tool latency | P95 by tool | Horizontal bar |
| LLM latency | P95 by model | Horizontal bar |
| Memory operations | Count by type | Pie chart |

---

## 5. Code Examples

### 5.1 Logger Initialization

```python
# main.py

import sys
from pathlib import Path
from datetime import datetime

from src.core.log_config import LoggingConfig
from src.core.log_context import LoggerManager
from src.core.log_outputs import ConsoleOutput, JSONLinesOutput, AsyncBufferedOutput


def setup_logging(config: LoggingConfig = None) -> LoggerManager:
    """Initialize the structured logging system."""
    config = config or LoggingConfig.from_env()

    # Create outputs
    outputs = []

    # Console output (always for development)
    if config.console_enabled:
        outputs.append(ConsoleOutput(color=config.console_color))

    # JSON Lines output for analysis
    if config.jsonl_enabled:
        # Auto-generate log file path based on session time
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = config.jsonl_path or Path(f"logs/agent_{timestamp}.jsonl")
        log_path.parent.mkdir(parents=True, exist_ok=True)

        jsonl_output = JSONLinesOutput(file_path=log_path)
        if config.jsonl_async:
            jsonl_output = AsyncBufferedOutput(jsonl_output, config.jsonl_buffer_size)
        outputs.append(jsonl_output)

    # Initialize the logger manager
    manager = LoggerManager.initialize(
        outputs=outputs,
        min_level=config.min_level,
        service_name=config.service_name,
    )

    return manager


def main():
    # Initialize logging first
    log_manager = setup_logging()
    logger = log_manager.root_logger

    # Log application start
    from src.core.structured_logger import EventCategory, LogEvent, LogLevel, LogLevelDetail

    logger.log(
        level=LogLevel.INFO,
        level_detail=LogLevelDetail.INFO_LIFECYCLE,
        event=LogEvent(
            category=EventCategory.AGENT_LIFECYCLE,
            event_type="application.start",
            name="Application started",
        ),
        message="Crawler Agent starting",
        data={"version": "1.0.0", "python_version": sys.version},
        tags=["application", "startup"],
    )

    try:
        # ... rest of main logic ...
        pass
    finally:
        # Ensure logs are flushed on exit
        for output in logger.outputs:
            output.flush()
            output.close()


if __name__ == "__main__":
    main()
```

### 5.2 Logging a Model Call

```python
# src/core/llm.py

import time
from src.core.log_context import get_logger
from src.core.structured_logger import (
    EventCategory, LogEvent, LogLevel, LogLevelDetail, LogMetrics
)


# Cost lookup table (per 1K tokens)
MODEL_COSTS = {
    "gpt-4o": {"input": 0.005, "output": 0.015},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
}


class LLMClient:
    def chat(self, messages, tools=None, tool_choice="auto", parallel_tool_calls=False):
        logger = get_logger()
        start_time = time.time()

        # Log the start of the LLM call
        if logger:
            logger.log(
                level=LogLevel.DEBUG,
                level_detail=LogLevelDetail.DEBUG_TRACE,
                event=LogEvent(
                    category=EventCategory.LLM_INTERACTION,
                    event_type="llm.call.start",
                    name="LLM call initiated",
                ),
                message=f"Calling {self.model} with {len(messages)} messages",
                context={
                    "model_provider": "openai",
                    "model_name": self.model,
                },
                data={
                    "llm_request": {
                        "message_count": len(messages),
                        "tools_count": len(tools) if tools else 0,
                        "tool_names": [t.name for t in tools] if tools else [],
                        "temperature": self.temperature,
                        "tool_choice": tool_choice,
                        "parallel_tool_calls": parallel_tool_calls,
                    }
                },
                tags=["llm", "openai", self.model, "call_start"],
            )

        try:
            # Make the actual API call
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=[t.to_openai_schema() for t in tools] if tools else None,
                tool_choice=tool_choice if tools else None,
                parallel_tool_calls=parallel_tool_calls,
                temperature=self.temperature,
            )

            duration_ms = (time.time() - start_time) * 1000

            # Extract usage metrics
            usage = response.usage
            tokens_input = usage.prompt_tokens if usage else 0
            tokens_output = usage.completion_tokens if usage else 0
            tokens_total = tokens_input + tokens_output

            # Calculate cost
            costs = MODEL_COSTS.get(self.model, {"input": 0, "output": 0})
            estimated_cost = (
                (tokens_input / 1000) * costs["input"] +
                (tokens_output / 1000) * costs["output"]
            )

            # Parse response
            choice = response.choices[0]
            finish_reason = choice.finish_reason
            content = choice.message.content
            tool_calls = self._parse_tool_calls(choice.message.tool_calls)

            # Log successful completion
            if logger:
                logger.log(
                    level=LogLevel.INFO,
                    level_detail=LogLevelDetail.INFO_METRIC,
                    event=LogEvent(
                        category=EventCategory.LLM_INTERACTION,
                        event_type="llm.call.complete",
                        name="LLM call completed",
                    ),
                    message=(
                        f"LLM {self.model} completed: {tokens_total} tokens, "
                        f"{duration_ms:.0f}ms, ${estimated_cost:.4f}, {finish_reason}"
                    ),
                    context={
                        "model_provider": "openai",
                        "model_name": self.model,
                    },
                    data={
                        "llm_response": {
                            "finish_reason": finish_reason,
                            "has_content": content is not None,
                            "content_length": len(content) if content else 0,
                            "content_preview": content[:200] if content else None,
                            "tool_calls_count": len(tool_calls) if tool_calls else 0,
                            "tool_called": tool_calls[0]["name"] if tool_calls else None,
                        }
                    },
                    metrics=LogMetrics(
                        duration_ms=duration_ms,
                        tokens_input=tokens_input,
                        tokens_output=tokens_output,
                        tokens_total=tokens_total,
                        estimated_cost_usd=estimated_cost,
                    ),
                    tags=["llm", "openai", self.model, "success", finish_reason],
                )

                # Log tool calls if present
                if tool_calls:
                    for tc in tool_calls:
                        logger.log(
                            level=LogLevel.DEBUG,
                            level_detail=LogLevelDetail.DEBUG_TRACE,
                            event=LogEvent(
                                category=EventCategory.LLM_INTERACTION,
                                event_type="llm.tool_call.parsed",
                                name=f"Tool call parsed: {tc['name']}",
                            ),
                            message=f"LLM requested tool: {tc['name']}",
                            data={
                                "tool_call": {
                                    "id": tc.get("id"),
                                    "name": tc["name"],
                                    "arguments_preview": str(tc["arguments"])[:200],
                                }
                            },
                            tags=["llm", "tool_call", tc["name"]],
                        )

            return {
                "content": content,
                "finish_reason": finish_reason,
                "tool_calls": tool_calls,
            }

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000

            # Determine error type
            error_type = "unknown"
            if "rate_limit" in str(e).lower():
                error_type = "rate_limit"
            elif "timeout" in str(e).lower():
                error_type = "timeout"
            elif "invalid" in str(e).lower():
                error_type = "validation"

            if logger:
                logger.log(
                    level=LogLevel.ERROR,
                    level_detail=LogLevelDetail.ERROR_EXTERNAL,
                    event=LogEvent(
                        category=EventCategory.LLM_INTERACTION,
                        event_type="llm.call.error",
                        name="LLM call failed",
                    ),
                    message=f"LLM call to {self.model} failed: {type(e).__name__}: {str(e)[:200]}",
                    context={
                        "model_provider": "openai",
                        "model_name": self.model,
                    },
                    data={
                        "error": {
                            "type": error_type,
                            "exception_class": type(e).__name__,
                            "message": str(e)[:500],
                        }
                    },
                    metrics=LogMetrics(duration_ms=duration_ms),
                    tags=["llm", "openai", self.model, "error", error_type],
                )

            raise
```

### 5.3 Logging Tool Execution

```python
# src/tools/base.py

import time
from abc import ABC, abstractmethod
from typing import Any

from src.core.log_context import get_logger
from src.core.structured_logger import (
    EventCategory, LogEvent, LogLevel, LogLevelDetail, LogMetrics
)


class BaseTool(ABC):
    """Base class for all tools with integrated logging."""

    name: str
    description: str
    version: str = "1.0"

    def __init__(self):
        self._logger = None

    @property
    def logger(self):
        """Get logger lazily."""
        if self._logger is None:
            parent = get_logger()
            if parent:
                self._logger = parent.child(
                    name=f"tools.{self.name}",
                    context={"tool_name": self.name, "tool_version": self.version},
                    tags=["tool", self.name],
                )
        return self._logger

    @abstractmethod
    def _execute(self, **kwargs) -> dict[str, Any]:
        """Implement actual tool logic here."""
        pass

    @abstractmethod
    def get_parameters_schema(self) -> dict:
        """Return JSON schema for parameters."""
        pass

    def execute(self, **kwargs) -> dict[str, Any]:
        """Execute tool with logging wrapper."""
        start_time = time.time()

        # Sanitize input for logging (remove large content)
        sanitized_input = self._sanitize_input(kwargs)

        # Log start
        if self.logger:
            self.logger.log(
                level=LogLevel.INFO,
                level_detail=LogLevelDetail.INFO_LIFECYCLE,
                event=LogEvent(
                    category=EventCategory.TOOL_EXECUTION,
                    event_type="tool.execute.start",
                    name=f"{self.name} started",
                ),
                message=f"Tool {self.name} starting execution",
                data={"input": sanitized_input},
                tags=["execute", "start"],
            )

        try:
            # Execute the actual tool logic
            result = self._execute(**kwargs)

            duration_ms = (time.time() - start_time) * 1000
            success = result.get("success", True)

            # Sanitize output for logging
            sanitized_output = self._sanitize_output(result)

            # Log completion
            if self.logger:
                level = LogLevel.INFO if success else LogLevel.WARNING
                level_detail = LogLevelDetail.INFO_LIFECYCLE if success else LogLevelDetail.WARNING_DEGRADED

                self.logger.log(
                    level=level,
                    level_detail=level_detail,
                    event=LogEvent(
                        category=EventCategory.TOOL_EXECUTION,
                        event_type="tool.execute.complete",
                        name=f"{self.name} completed",
                    ),
                    message=f"Tool {self.name} completed: {'success' if success else 'failed'} ({duration_ms:.0f}ms)",
                    data={"output": sanitized_output},
                    metrics=LogMetrics(
                        duration_ms=duration_ms,
                        content_size_bytes=len(str(result)),
                    ),
                    tags=["execute", "complete", "success" if success else "failure"],
                )

            return result

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000

            # Log error
            if self.logger:
                self.logger.log(
                    level=LogLevel.ERROR,
                    level_detail=LogLevelDetail.ERROR_RECOVERABLE,
                    event=LogEvent(
                        category=EventCategory.TOOL_EXECUTION,
                        event_type="tool.execute.error",
                        name=f"{self.name} failed",
                    ),
                    message=f"Tool {self.name} error: {type(e).__name__}: {str(e)[:200]}",
                    data={
                        "input": sanitized_input,
                        "error": {
                            "type": type(e).__name__,
                            "message": str(e)[:500],
                        }
                    },
                    metrics=LogMetrics(duration_ms=duration_ms),
                    tags=["execute", "error", type(e).__name__.lower()],
                )

            # Return error result instead of raising
            return {"success": False, "error": str(e)}

    def _sanitize_input(self, kwargs: dict) -> dict:
        """Sanitize input parameters for logging."""
        result = {}
        for key, value in kwargs.items():
            if isinstance(value, str) and len(value) > 500:
                result[key] = f"{value[:200]}... ({len(value)} chars)"
            elif isinstance(value, (list, dict)) and len(str(value)) > 500:
                result[key] = f"<{type(value).__name__} with {len(value)} items>"
            else:
                result[key] = value
        return result

    def _sanitize_output(self, result: dict) -> dict:
        """Sanitize output for logging."""
        sanitized = {}
        for key, value in result.items():
            if key == "result" and isinstance(value, str) and len(value) > 500:
                sanitized[key] = f"{value[:200]}... ({len(value)} chars)"
            elif key == "html" or key == "content":
                sanitized[key] = f"<{len(value)} chars>" if value else None
            else:
                sanitized[key] = value
        return sanitized
```

### 5.4 Creating Child Spans

```python
# src/agents/base.py

import time
from src.core.log_context import get_logger, span
from src.core.structured_logger import (
    EventCategory, LogEvent, LogLevel, LogLevelDetail, LogMetrics
)


class BaseAgent(ABC):
    """Base agent with span-based logging."""

    def run(self, task: str) -> dict:
        """Execute agent within its own span."""
        parent_logger = get_logger()

        # Create a child span for this agent's execution
        with span(
            name=f"agents.{self.name}",
            context={"agent_type": self.__class__.__name__},
            tags=["agent", self.name],
        ) as agent_logger:

            self.logger = agent_logger
            start_time = time.time()

            # Log agent start
            agent_logger.log(
                level=LogLevel.INFO,
                level_detail=LogLevelDetail.INFO_LIFECYCLE,
                event=LogEvent(
                    category=EventCategory.AGENT_LIFECYCLE,
                    event_type="agent.start",
                    name=f"{self.name} started",
                ),
                message=f"Agent {self.name} starting task",
                data={
                    "task": task[:500],
                    "tools_available": list(self._tool_map.keys()),
                },
                tags=["lifecycle", "start"],
            )

            try:
                result = self._run_reasoning_loop(task)

                duration_ms = (time.time() - start_time) * 1000

                # Log agent completion
                agent_logger.log(
                    level=LogLevel.INFO,
                    level_detail=LogLevelDetail.INFO_LIFECYCLE,
                    event=LogEvent(
                        category=EventCategory.AGENT_LIFECYCLE,
                        event_type="agent.complete",
                        name=f"{self.name} completed",
                    ),
                    message=f"Agent {self.name} completed: {result.get('success', False)}",
                    data={
                        "success": result.get("success", False),
                        "iterations": self.iteration_count,
                    },
                    metrics=LogMetrics(duration_ms=duration_ms),
                    tags=["lifecycle", "complete"],
                )

                return result

            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000

                agent_logger.log(
                    level=LogLevel.ERROR,
                    level_detail=LogLevelDetail.ERROR_UNRECOVERABLE,
                    event=LogEvent(
                        category=EventCategory.AGENT_LIFECYCLE,
                        event_type="agent.error",
                        name=f"{self.name} error",
                    ),
                    message=f"Agent {self.name} failed: {type(e).__name__}",
                    data={
                        "error": {
                            "type": type(e).__name__,
                            "message": str(e),
                        },
                        "iterations_completed": self.iteration_count,
                    },
                    metrics=LogMetrics(duration_ms=duration_ms),
                    tags=["lifecycle", "error"],
                )
                raise

    def _run_reasoning_loop(self, task: str) -> dict:
        """Run the reasoning loop with per-iteration logging."""
        self.iteration_count = 0

        while self.iteration_count < self.max_iterations:
            self.iteration_count += 1

            # Create child span for this iteration
            with span(
                name=f"iteration_{self.iteration_count}",
                context={"iteration": self.iteration_count},
                tags=["iteration"],
            ) as iter_logger:

                iter_logger.log(
                    level=LogLevel.DEBUG,
                    level_detail=LogLevelDetail.DEBUG_TRACE,
                    event=LogEvent(
                        category=EventCategory.AGENT_LIFECYCLE,
                        event_type="agent.iteration.start",
                        name=f"Iteration {self.iteration_count}",
                    ),
                    message=f"Starting iteration {self.iteration_count}/{self.max_iterations}",
                    data={"messages_count": len(self.messages)},
                    tags=["iteration", "start"],
                )

                # Execute iteration logic
                result = self._execute_iteration()

                if result.get("complete"):
                    return result

        # Max iterations reached
        return {"success": False, "error": "Max iterations reached"}
```

### 5.5 Error Logging with Full Context

```python
# src/tools/browser.py

import traceback
from src.core.log_context import get_logger
from src.core.structured_logger import (
    EventCategory, LogEvent, LogLevel, LogLevelDetail, LogMetrics
)


class NavigateTool(BaseTool):
    name = "navigate"
    description = "Navigate browser to a URL"

    def _execute(self, url: str) -> dict:
        logger = self.logger

        # Log navigation start
        if logger:
            logger.log(
                level=LogLevel.INFO,
                level_detail=LogLevelDetail.INFO_LIFECYCLE,
                event=LogEvent(
                    category=EventCategory.BROWSER_OPERATION,
                    event_type="browser.navigate.start",
                    name="Navigation started",
                ),
                message=f"Navigating to: {url}",
                context={"url": url},
                tags=["browser", "navigate", "start"],
            )

        try:
            self.browser_session.navigate(url)

            if logger:
                logger.log(
                    level=LogLevel.INFO,
                    level_detail=LogLevelDetail.INFO_LIFECYCLE,
                    event=LogEvent(
                        category=EventCategory.BROWSER_OPERATION,
                        event_type="browser.navigate.complete",
                        name="Navigation completed",
                    ),
                    message=f"Successfully navigated to: {url}",
                    context={"url": url},
                    tags=["browser", "navigate", "success"],
                )

            return {"success": True, "result": f"Navigated to {url}"}

        except TimeoutError as e:
            if logger:
                logger.log(
                    level=LogLevel.ERROR,
                    level_detail=LogLevelDetail.ERROR_RECOVERABLE,
                    event=LogEvent(
                        category=EventCategory.ERROR,
                        event_type="error.timeout",
                        name="Navigation timeout",
                    ),
                    message=f"Navigation timeout for {url}: {e}",
                    context={"url": url},
                    data={
                        "error": {
                            "type": "timeout",
                            "exception_class": "TimeoutError",
                            "message": str(e),
                            "url": url,
                        },
                        "recovery_suggestion": "Increase timeout or check network connectivity",
                    },
                    tags=["browser", "navigate", "error", "timeout"],
                )
            return {"success": False, "error": f"Timeout navigating to {url}"}

        except ConnectionError as e:
            if logger:
                logger.log(
                    level=LogLevel.ERROR,
                    level_detail=LogLevelDetail.ERROR_EXTERNAL,
                    event=LogEvent(
                        category=EventCategory.ERROR,
                        event_type="error.external_service",
                        name="Browser connection error",
                    ),
                    message=f"Browser connection error: {e}",
                    context={"url": url},
                    data={
                        "error": {
                            "type": "connection",
                            "exception_class": "ConnectionError",
                            "message": str(e),
                            "stack_trace": traceback.format_exc(),
                        },
                        "service": "chrome_cdp",
                        "recovery_suggestion": "Check if Chrome is running with --remote-debugging-port",
                    },
                    tags=["browser", "navigate", "error", "connection"],
                )
            return {"success": False, "error": f"Connection error: {e}"}

        except Exception as e:
            if logger:
                logger.log(
                    level=LogLevel.ERROR,
                    level_detail=LogLevelDetail.ERROR_UNRECOVERABLE,
                    event=LogEvent(
                        category=EventCategory.ERROR,
                        event_type="error.internal",
                        name="Unexpected navigation error",
                    ),
                    message=f"Unexpected error navigating to {url}: {type(e).__name__}",
                    context={"url": url},
                    data={
                        "error": {
                            "type": "internal",
                            "exception_class": type(e).__name__,
                            "message": str(e),
                            "stack_trace": traceback.format_exc(),
                        },
                    },
                    tags=["browser", "navigate", "error", "unexpected"],
                )
            return {"success": False, "error": str(e)}
```

### 5.6 Decision Point Logging

```python
# src/agents/main_agent.py

from src.core.log_context import get_logger
from src.core.structured_logger import (
    EventCategory, LogEvent, LogLevel, LogLevelDetail
)


class MainAgent(BaseAgent):
    """Main orchestrator agent with decision logging."""

    def _select_next_phase(self, current_phase: str, memory_state: dict) -> str:
        """Select next workflow phase with decision logging."""
        logger = get_logger()

        # Determine next phase based on workflow
        phase_order = [
            "site_analysis",      # BrowserAgent
            "selector_discovery", # SelectorAgent
            "accessibility",      # AccessibilityAgent
            "data_preparation",   # DataPrepAgent
            "output_generation",  # Plan generation
        ]

        current_idx = phase_order.index(current_phase) if current_phase in phase_order else -1
        next_phase = phase_order[current_idx + 1] if current_idx + 1 < len(phase_order) else "complete"

        # Check prerequisites
        prerequisites_met = self._check_prerequisites(next_phase, memory_state)

        if not prerequisites_met:
            # Decision: skip or retry
            decision = "retry_current" if self._should_retry(current_phase) else "skip_to_next"

            if logger:
                logger.log(
                    level=LogLevel.WARNING,
                    level_detail=LogLevelDetail.WARNING_DEGRADED,
                    event=LogEvent(
                        category=EventCategory.DECISION,
                        event_type="decision.fallback_activated",
                        name="Phase prerequisites not met",
                    ),
                    message=f"Prerequisites for {next_phase} not met, decision: {decision}",
                    data={
                        "decision": {
                            "decision_type": "phase_transition",
                            "current_phase": current_phase,
                            "intended_next": next_phase,
                            "action": decision,
                            "reason": "prerequisites_not_met",
                            "missing_prerequisites": self._get_missing_prerequisites(next_phase, memory_state),
                        }
                    },
                    tags=["decision", "fallback", "workflow"],
                )

            return current_phase if decision == "retry_current" else phase_order[current_idx + 2]

        # Log successful phase transition decision
        if logger:
            agent_map = {
                "site_analysis": "BrowserAgent",
                "selector_discovery": "SelectorAgent",
                "accessibility": "AccessibilityAgent",
                "data_preparation": "DataPrepAgent",
                "output_generation": "GeneratePlanTool",
            }

            logger.log(
                level=LogLevel.INFO,
                level_detail=LogLevelDetail.INFO_DECISION,
                event=LogEvent(
                    category=EventCategory.DECISION,
                    event_type="decision.agent_routing",
                    name=f"Phase transition to {next_phase}",
                ),
                message=f"Transitioning from {current_phase} to {next_phase} ({agent_map.get(next_phase, 'unknown')})",
                data={
                    "decision": {
                        "decision_type": "phase_transition",
                        "current_phase": current_phase,
                        "next_phase": next_phase,
                        "selected_agent": agent_map.get(next_phase),
                        "reason": "prerequisites_met",
                        "memory_keys_available": list(memory_state.keys()),
                    }
                },
                tags=["decision", "routing", "workflow", next_phase],
            )

        return next_phase
```

---

## 6. Migration Strategy

### 6.1 Current State Analysis

**Existing Logging (from codebase scan):**
- Using Python `logging` module
- Basic text format: `%(asctime)s - %(name)s - %(levelname)s - %(message)s`
- ~140 log statements across codebase
- No correlation IDs or structured data
- No metrics capture

**Files with Logging:**
```
main.py              - Application entry, setup
src/core/llm.py      - LLM client debug logs
src/core/browser.py  - Browser operations
src/agents/base.py   - Tool execution logging
src/agents/*.py      - Agent-specific logs
src/tools/*.py       - Tool operation logs
```

### 6.2 Migration Phases

#### Phase 1: Foundation (Non-Breaking)
- Add new logging infrastructure alongside existing
- Implement `StructuredLogger`, `LogOutput` classes
- Create `LoggerManager` with context propagation
- **No changes to existing log calls**

#### Phase 2: Core Integration
- Modify `main.py` to initialize `LoggerManager`
- Update `LLMClient` to use structured logging
- Update `BaseAgent` to use structured logging
- Keep existing `logging` calls as fallback

#### Phase 3: Tool Migration
- Update `BaseTool` with logging wrapper
- Migrate each tool file individually
- Add tool-specific context and metrics

#### Phase 4: Cleanup
- Remove legacy `logging` calls
- Remove `setup_logging()` from main.py
- Add configuration for outputs
- Enable production features (sampling, PII redaction)

### 6.3 Backward Compatibility Bridge

```python
# src/core/logging_bridge.py

import logging
from .structured_logger import (
    StructuredLogger, LogLevel, LogLevelDetail, LogEvent, EventCategory
)
from .log_context import get_logger


class StructuredLoggingHandler(logging.Handler):
    """Bridge handler that forwards standard logging to structured logger."""

    LEVEL_MAP = {
        logging.DEBUG: (LogLevel.DEBUG, LogLevelDetail.DEBUG_TRACE),
        logging.INFO: (LogLevel.INFO, LogLevelDetail.INFO_LIFECYCLE),
        logging.WARNING: (LogLevel.WARNING, LogLevelDetail.WARNING_DEGRADED),
        logging.ERROR: (LogLevel.ERROR, LogLevelDetail.ERROR_RECOVERABLE),
        logging.CRITICAL: (LogLevel.CRITICAL, LogLevelDetail.ERROR_UNRECOVERABLE),
    }

    def emit(self, record: logging.LogRecord) -> None:
        logger = get_logger()
        if not logger:
            return

        level, level_detail = self.LEVEL_MAP.get(
            record.levelno,
            (LogLevel.INFO, LogLevelDetail.INFO_LIFECYCLE)
        )

        # Infer category from logger name
        category = EventCategory.AGENT_LIFECYCLE
        if "tool" in record.name.lower():
            category = EventCategory.TOOL_EXECUTION
        elif "llm" in record.name.lower():
            category = EventCategory.LLM_INTERACTION
        elif "browser" in record.name.lower():
            category = EventCategory.BROWSER_OPERATION

        logger.log(
            level=level,
            level_detail=level_detail,
            event=LogEvent(
                category=category,
                event_type=f"legacy.{record.name}",
                name=f"Legacy log from {record.name}",
            ),
            message=record.getMessage(),
            context={"legacy_logger": record.name},
            tags=["legacy", record.name.split(".")[-1]],
        )


def install_bridge():
    """Install bridge to capture existing logging calls."""
    root_logger = logging.getLogger()
    root_logger.addHandler(StructuredLoggingHandler())
```

### 6.4 Migration Checklist

```markdown
## Migration Checklist

### Phase 1: Foundation
- [ ] Create `src/core/structured_logger.py`
- [ ] Create `src/core/log_outputs.py`
- [ ] Create `src/core/log_context.py`
- [ ] Create `src/core/log_config.py`
- [ ] Create `src/core/pii_redactor.py`
- [ ] Add unit tests for new modules
- [ ] Verify no breaking changes

### Phase 2: Core Integration
- [ ] Update `main.py` - initialize LoggerManager
- [ ] Update `src/core/llm.py` - structured LLM logging
- [ ] Update `src/agents/base.py` - agent lifecycle logging
- [ ] Install logging bridge for legacy compatibility
- [ ] Verify dual logging works

### Phase 3: Tool Migration
- [ ] Update `src/tools/base.py` - tool wrapper
- [ ] Update `src/tools/browser.py`
- [ ] Update `src/tools/memory.py`
- [ ] Update `src/tools/extraction.py`
- [ ] Update `src/tools/http.py`
- [ ] Update `src/tools/orchestration.py`
- [ ] Update remaining tools
- [ ] Update agent implementations

### Phase 4: Cleanup
- [ ] Remove legacy logging setup
- [ ] Remove logging bridge
- [ ] Enable PII redaction
- [ ] Configure sampling for high-volume events
- [ ] Add dashboard queries/alerts
- [ ] Update documentation
- [ ] Performance testing
```

---

## 7. Phased Implementation

### 7.1 MVP (Phase 1) - 2-3 days implementation

**Goal:** Basic structured logging with JSON output

**Scope:**
- Core logger infrastructure
- JSON Lines output
- Console output (human-readable)
- LLM call logging with tokens/cost
- Agent lifecycle logging
- Basic tool execution logging

**Files to Create:**
```
src/core/structured_logger.py   # Core classes
src/core/log_outputs.py         # Output implementations
src/core/log_context.py         # Context propagation
src/core/log_config.py          # Configuration
```

**Files to Modify:**
```
main.py                         # Initialize logging
src/core/llm.py                 # LLM metrics
src/agents/base.py              # Agent lifecycle
```

**Deliverables:**
- JSON Lines log file with all events
- Console output with trace IDs
- Token/cost tracking for all LLM calls
- Session/request correlation

### 7.2 Enhanced (Phase 2) - 2-3 days implementation

**Goal:** Complete tool coverage and error tracking

**Scope:**
- All tools with structured logging
- Error taxonomy implementation
- Decision point logging
- Memory operation tracking
- Browser operation tracking

**Files to Modify:**
```
src/tools/base.py               # Tool wrapper
src/tools/*.py                  # All tools
src/agents/main_agent.py        # Decision logging
```

**Deliverables:**
- Complete event coverage
- Error classification
- Decision audit trail

### 7.3 Production (Phase 3) - 2-3 days implementation

**Goal:** Production-ready features

**Scope:**
- PII redaction
- Sampling for high-volume events
- OpenTelemetry output
- Async buffered writing
- Configuration from environment

**Files to Create:**
```
src/core/pii_redactor.py        # PII handling
src/core/sampling.py            # Event sampling
```

**Deliverables:**
- PII-safe logs
- Configurable sampling
- OTel compatibility
- Performance optimized

### 7.4 Visualization (Phase 4) - 3-5 days implementation

**Goal:** Dashboard and analysis capabilities

**Scope:**
- Elasticsearch/OpenSearch index templates
- Grafana dashboard definitions
- Query library for common analyses
- Alerting rules

**Deliverables:**
- Index templates (JSON)
- Dashboard JSON exports
- Query documentation
- Alert definitions

---

## Appendix A: Infrastructure Setup with Docker Compose

### A.1 Overview

While the logging system works standalone with local JSONL files, you can optionally deploy infrastructure for:
- **Elasticsearch**: Full-text search, aggregations, long-term storage
- **Kibana**: Dashboards, visualizations, log exploration
- **OpenTelemetry Collector**: Distributed tracing, span collection
- **Jaeger**: Trace visualization (alternative to Kibana APM)

### A.2 Docker Compose Configuration

Create `docker-compose.logging.yml` in your project root:

```yaml
version: '3.8'

services:
  # Elasticsearch for log storage and search
  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.11.0
    container_name: crawler-elasticsearch
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=false
      - "ES_JAVA_OPTS=-Xms512m -Xmx512m"
    ports:
      - "9200:9200"
    volumes:
      - elasticsearch-data:/usr/share/elasticsearch/data
    healthcheck:
      test: ["CMD-SHELL", "curl -s http://localhost:9200/_cluster/health | grep -q 'green\\|yellow'"]
      interval: 10s
      timeout: 5s
      retries: 10

  # Kibana for visualization
  kibana:
    image: docker.elastic.co/kibana/kibana:8.11.0
    container_name: crawler-kibana
    environment:
      - ELASTICSEARCH_HOSTS=http://elasticsearch:9200
    ports:
      - "5601:5601"
    depends_on:
      elasticsearch:
        condition: service_healthy

  # OpenTelemetry Collector for trace ingestion
  otel-collector:
    image: otel/opentelemetry-collector-contrib:0.91.0
    container_name: crawler-otel-collector
    command: ["--config=/etc/otel-collector-config.yaml"]
    volumes:
      - ./infra/otel-collector-config.yaml:/etc/otel-collector-config.yaml:ro
    ports:
      - "4317:4317"   # OTLP gRPC
      - "4318:4318"   # OTLP HTTP
      - "8888:8888"   # Prometheus metrics
    depends_on:
      elasticsearch:
        condition: service_healthy

  # Jaeger for trace visualization (optional, alternative to Kibana APM)
  jaeger:
    image: jaegertracing/all-in-one:1.52
    container_name: crawler-jaeger
    environment:
      - COLLECTOR_OTLP_ENABLED=true
    ports:
      - "16686:16686"  # Jaeger UI
      - "14268:14268"  # Jaeger HTTP collector
    profiles:
      - jaeger  # Only start with: docker compose --profile jaeger up

volumes:
  elasticsearch-data:
```

### A.3 OpenTelemetry Collector Configuration

Create `infra/otel-collector-config.yaml`:

```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318

processors:
  batch:
    timeout: 1s
    send_batch_size: 1024

  # Add service name if not present
  resource:
    attributes:
      - key: service.name
        value: crawler-agent
        action: upsert

exporters:
  # Export to Elasticsearch
  elasticsearch:
    endpoints: ["http://elasticsearch:9200"]
    logs_index: crawler-logs
    traces_index: crawler-traces

  # Export to Jaeger (if using)
  otlp/jaeger:
    endpoint: jaeger:4317
    tls:
      insecure: true

  # Debug logging
  logging:
    verbosity: detailed

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch, resource]
      exporters: [elasticsearch, logging]
    logs:
      receivers: [otlp]
      processors: [batch, resource]
      exporters: [elasticsearch, logging]
```

### A.4 Elasticsearch Index Template

Create index template for optimized queries. Save as `infra/es-index-template.sh`:

```bash
#!/bin/bash
# Run after Elasticsearch starts: ./infra/es-index-template.sh

curl -X PUT "localhost:9200/_index_template/crawler-logs-template" \
  -H 'Content-Type: application/json' -d'
{
  "index_patterns": ["crawler-logs*"],
  "template": {
    "settings": {
      "number_of_shards": 1,
      "number_of_replicas": 0,
      "index.refresh_interval": "5s"
    },
    "mappings": {
      "properties": {
        "timestamp": { "type": "date" },
        "level": { "type": "keyword" },
        "level_detail": { "type": "keyword" },
        "logger": { "type": "keyword" },
        "trace_context": {
          "properties": {
            "session_id": { "type": "keyword" },
            "request_id": { "type": "keyword" },
            "trace_id": { "type": "keyword" },
            "span_id": { "type": "keyword" },
            "parent_span_id": { "type": "keyword" }
          }
        },
        "event": {
          "properties": {
            "category": { "type": "keyword" },
            "type": { "type": "keyword" },
            "name": { "type": "text" }
          }
        },
        "context": {
          "properties": {
            "agent_id": { "type": "keyword" },
            "agent_type": { "type": "keyword" },
            "tool_name": { "type": "keyword" },
            "model_name": { "type": "keyword" },
            "model_provider": { "type": "keyword" },
            "iteration": { "type": "integer" },
            "url": { "type": "keyword" }
          }
        },
        "metrics": {
          "properties": {
            "duration_ms": { "type": "float" },
            "time_to_first_token_ms": { "type": "float" },
            "tokens_input": { "type": "integer" },
            "tokens_output": { "type": "integer" },
            "tokens_total": { "type": "integer" },
            "estimated_cost_usd": { "type": "float" },
            "retry_count": { "type": "integer" },
            "content_size_bytes": { "type": "integer" }
          }
        },
        "tags": { "type": "keyword" },
        "message": { "type": "text" }
      }
    }
  }
}'

echo ""
echo "Index template created successfully"
```

### A.5 Quick Start Commands

```bash
# 1. Start core services (Elasticsearch + Kibana + OTel Collector)
docker compose -f docker-compose.logging.yml up -d

# 2. Wait for services to be healthy (~30 seconds)
docker compose -f docker-compose.logging.yml ps

# 3. Check Elasticsearch is ready
curl http://localhost:9200/_cluster/health?pretty

# 4. Create index template
chmod +x infra/es-index-template.sh
./infra/es-index-template.sh

# 5. Access services:
#    - Kibana: http://localhost:5601
#    - Elasticsearch: http://localhost:9200

# Optional: Include Jaeger for trace visualization
docker compose -f docker-compose.logging.yml --profile jaeger up -d
# Access Jaeger UI at http://localhost:16686

# Stop all services
docker compose -f docker-compose.logging.yml down

# Stop and remove volumes (clean slate)
docker compose -f docker-compose.logging.yml down -v
```

### A.6 Ingesting JSONL Files to Elasticsearch

Create `scripts/ingest_logs.py` to ingest existing JSONL log files:

```python
#!/usr/bin/env python3
"""Ingest JSONL log files into Elasticsearch."""

import json
import sys
from pathlib import Path
from datetime import datetime

try:
    from elasticsearch import Elasticsearch, helpers
except ImportError:
    print("Install elasticsearch: pip install elasticsearch>=8.0.0")
    sys.exit(1)


def ingest_logs(log_dir: str = "logs", es_host: str = "http://localhost:9200"):
    """Ingest all JSONL files from log_dir into Elasticsearch."""
    es = Elasticsearch([es_host])

    # Check connection
    if not es.ping():
        print(f"Cannot connect to Elasticsearch at {es_host}")
        sys.exit(1)

    # Generate index name with date
    index_name = f"crawler-logs-{datetime.now().strftime('%Y.%m.%d')}"

    def generate_actions():
        for log_file in Path(log_dir).glob("*.jsonl"):
            print(f"Processing: {log_file}")
            with open(log_file) as f:
                for line_num, line in enumerate(f, 1):
                    if line.strip():
                        try:
                            doc = json.loads(line)
                            yield {
                                "_index": index_name,
                                "_source": doc
                            }
                        except json.JSONDecodeError as e:
                            print(f"  Skipping line {line_num}: {e}")

    # Bulk ingest
    success, errors = helpers.bulk(es, generate_actions(), stats_only=True)
    print(f"\nIngested {success} documents, {errors} errors")
    print(f"Index: {index_name}")


if __name__ == "__main__":
    log_dir = sys.argv[1] if len(sys.argv) > 1 else "logs"
    es_host = sys.argv[2] if len(sys.argv) > 2 else "http://localhost:9200"
    ingest_logs(log_dir, es_host)
```

**Usage:**
```bash
# Install elasticsearch client
pip install elasticsearch>=8.0.0

# Ingest logs from default directory
python scripts/ingest_logs.py

# Ingest from specific directory
python scripts/ingest_logs.py /path/to/logs

# Ingest to remote Elasticsearch
python scripts/ingest_logs.py logs http://elasticsearch.example.com:9200
```

### A.7 Kibana Dashboard Setup

After ingesting logs, create a data view in Kibana:

1. Open Kibana at http://localhost:5601
2. Go to **Stack Management** → **Data Views**
3. Click **Create data view**:
   - Name: `Crawler Logs`
   - Index pattern: `crawler-logs-*`
   - Timestamp field: `timestamp`
4. Go to **Discover** to explore logs

**Useful Kibana Discover queries (KQL):**

```
# All errors
level: "ERROR"

# LLM calls with high cost
event.type: "llm.call.complete" and metrics.estimated_cost_usd > 0.01

# Slow operations (>5 seconds)
metrics.duration_ms > 5000

# Specific trace
trace_context.trace_id: "trace_abc123"

# Tool failures
event.category: "tool_execution" and level: "ERROR"

# Selector extraction events
event.type: selector.*

# All events for a session
trace_context.session_id: "sess_xyz789"

# Browser navigation events
event.type: browser.navigate.*
```

### A.8 Minimal Setup (Elasticsearch Only)

For a lightweight setup with just search (no tracing), create `docker-compose.logging-minimal.yml`:

```yaml
version: '3.8'

services:
  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.11.0
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=false
      - "ES_JAVA_OPTS=-Xms256m -Xmx256m"
    ports:
      - "9200:9200"
    volumes:
      - es-data:/usr/share/elasticsearch/data

  kibana:
    image: docker.elastic.co/kibana/kibana:8.11.0
    environment:
      - ELASTICSEARCH_HOSTS=http://elasticsearch:9200
    ports:
      - "5601:5601"
    depends_on:
      - elasticsearch

volumes:
  es-data:
```

```bash
# Start minimal stack (~500MB RAM)
docker compose -f docker-compose.logging-minimal.yml up -d
```

### A.9 Application Configuration for Infrastructure

Update `.env` to enable infrastructure integration:

```bash
# === Local file logging (always works) ===
LOG_JSONL=true
LOG_JSONL_PATH=./logs/agent.jsonl

# === OpenTelemetry export (when infrastructure is running) ===
LOG_OTEL=true
LOG_OTEL_ENDPOINT=http://localhost:4317

# === Direct Elasticsearch export (alternative to OTel) ===
# LOG_ELASTICSEARCH=true
# LOG_ELASTICSEARCH_URL=http://localhost:9200
# LOG_ELASTICSEARCH_INDEX=crawler-logs
```

### A.10 Resource Requirements

| Setup | Services | RAM | Disk |
|-------|----------|-----|------|
| **None (local files)** | - | 0 | ~1MB/1000 log entries |
| **Minimal** | ES + Kibana | ~1GB | ~500MB + logs |
| **Full** | ES + Kibana + OTel | ~1.5GB | ~600MB + logs |
| **Full + Jaeger** | ES + Kibana + OTel + Jaeger | ~2GB | ~700MB + logs |

---

## Appendix B: Environment Variables

```bash
# Logging Configuration
LOG_LEVEL=INFO                              # Minimum log level
LOG_CONSOLE=true                            # Enable console output
LOG_COLOR=true                              # Enable colored console
LOG_JSONL=true                              # Enable JSON Lines output
LOG_JSONL_PATH=./logs/agent.jsonl           # JSON Lines file path
LOG_OTEL=false                              # Enable OpenTelemetry
LOG_OTEL_ENDPOINT=http://localhost:4317     # OTel collector endpoint
LOG_ELASTICSEARCH=false                     # Enable direct ES export
LOG_ELASTICSEARCH_URL=http://localhost:9200 # Elasticsearch URL
LOG_ELASTICSEARCH_INDEX=crawler-logs        # ES index name
LOG_SAMPLING=false                          # Enable event sampling
LOG_SAMPLING_RATE=1.0                       # Sampling rate (0.0-1.0)
LOG_REDACT_PII=true                         # Enable PII redaction
SERVICE_NAME=crawler-agent                  # Service name for logs
```

## Appendix C: Cost Reference

```python
# Token costs per 1K tokens (as of December 2025, Standard tier)
# Source: https://platform.openai.com/docs/pricing
MODEL_COSTS = {
    # OpenAI GPT-5 Series
    "gpt-5.2": {"input": 0.00175, "output": 0.014},
    "gpt-5.1": {"input": 0.00125, "output": 0.01},
    "gpt-5": {"input": 0.00125, "output": 0.01},
    "gpt-5-mini": {"input": 0.00025, "output": 0.002},
    "gpt-5-nano": {"input": 0.00005, "output": 0.0004},
    "gpt-5.2-pro": {"input": 0.021, "output": 0.168},
    "gpt-5-pro": {"input": 0.015, "output": 0.12},

    # OpenAI GPT-4.1 Series
    "gpt-4.1": {"input": 0.002, "output": 0.008},
    "gpt-4.1-mini": {"input": 0.0004, "output": 0.0016},
    "gpt-4.1-nano": {"input": 0.0001, "output": 0.0004},

    # OpenAI GPT-4o Series
    "gpt-4o": {"input": 0.0025, "output": 0.01},
    "gpt-4o-2024-05-13": {"input": 0.005, "output": 0.015},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},

    # OpenAI o-Series (Reasoning)
    "o1": {"input": 0.015, "output": 0.06},
    "o1-pro": {"input": 0.15, "output": 0.6},
    "o1-mini": {"input": 0.0011, "output": 0.0044},
    "o3": {"input": 0.002, "output": 0.008},
    "o3-pro": {"input": 0.02, "output": 0.08},
    "o3-mini": {"input": 0.0011, "output": 0.0044},
    "o4-mini": {"input": 0.0011, "output": 0.0044},

    # OpenAI Legacy Models
    "gpt-4-turbo": {"input": 0.01, "output": 0.03},
    "gpt-4": {"input": 0.03, "output": 0.06},
    "gpt-4-32k": {"input": 0.06, "output": 0.12},
    "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},

    # Anthropic Claude (for future use)
    "claude-3-opus": {"input": 0.015, "output": 0.075},
    "claude-3-sonnet": {"input": 0.003, "output": 0.015},
    "claude-3-haiku": {"input": 0.00025, "output": 0.00125},

    # Embeddings
    "text-embedding-3-small": {"input": 0.00002, "output": 0.0},
    "text-embedding-3-large": {"input": 0.00013, "output": 0.0},
}
```

## Appendix C: Error Type Taxonomy

```
error.validation            # Input/output validation failures
error.validation.schema     # JSON schema validation
error.validation.type       # Type mismatch
error.validation.required   # Missing required field

error.timeout               # Operation timeouts
error.timeout.llm           # LLM API timeout
error.timeout.browser       # Browser operation timeout
error.timeout.http          # HTTP request timeout

error.rate_limit            # Rate limiting
error.rate_limit.llm        # LLM API rate limit
error.rate_limit.browser    # Browser rate limit

error.external_service      # External service failures
error.external_service.llm  # LLM API errors
error.external_service.cdp  # Chrome DevTools errors
error.external_service.http # HTTP endpoint errors

error.internal              # Internal errors
error.internal.state        # Invalid state
error.internal.logic        # Logic errors
error.internal.resource     # Resource exhaustion

error.recoverable           # Errors that were handled
error.unrecoverable         # Errors requiring intervention
```

---

## Summary

This logging architecture provides:

1. **Rich Context**: Every log entry includes session, request, trace, and span IDs for full correlation
2. **Structured Data**: Machine-parseable JSON with human-readable messages
3. **Metrics Capture**: Token counts, costs, latencies for all LLM and tool operations
4. **Decision Audit**: Full visibility into routing and fallback decisions
5. **Error Taxonomy**: Categorized errors with recovery information
6. **Visualization Ready**: Schema designed for dashboards and trace viewers
7. **Production Features**: PII redaction, sampling, async output
8. **Migration Path**: Phased approach with backward compatibility

The implementation can be completed in 4 phases over approximately 2-3 weeks, with MVP logging available within the first few days.
