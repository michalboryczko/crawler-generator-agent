"""Schema definitions for observability records.

This module defines the data structures for log records and trace events.
Level is METADATA ONLY - never used for filtering.

Field definitions include Elasticsearch types for index template generation.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional, Dict, List
from enum import Enum


class ComponentType(Enum):
    """Types of observable components."""
    AGENT = "agent"
    TOOL = "tool"
    LLM_CLIENT = "llm_client"


class ESType(Enum):
    """Elasticsearch field types."""
    KEYWORD = "keyword"
    TEXT = "text"
    DATE = "date"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    OBJECT = "object"


@dataclass
class FieldDef:
    """Field definition with ES type mapping."""
    name: str
    es_type: ESType
    description: str
    required: bool = False
    nested_fields: Dict[str, "FieldDef"] = field(default_factory=dict)


# =============================================================================
# FIELD NAME CONSTANTS - Single source of truth for field names
# =============================================================================

class F:
    """Field name constants for LogRecord and TraceEvent.

    Use these instead of hardcoded strings to ensure consistency
    between schema, serialization, and ES mappings.
    """
    # Core identity fields
    TIMESTAMP = "timestamp"
    TRACE_ID = "trace_id"
    SPAN_ID = "span_id"
    PARENT_SPAN_ID = "parent_span_id"
    SESSION_ID = "session_id"
    REQUEST_ID = "request_id"

    # Event classification
    LEVEL = "level"
    EVENT = "event"

    # Component info
    COMPONENT_TYPE = "component_type"
    COMPONENT_NAME = "component_name"
    TRIGGERED_BY = "triggered_by"

    # Payload fields
    DATA = "data"
    METRICS = "metrics"
    TAGS = "tags"

    # Trace-specific
    NAME = "name"
    ATTRIBUTES = "attributes"
    TYPE = "_type"


class M:
    """Metric field name constants (nested under 'metrics')."""
    DURATION_MS = "duration_ms"
    TIME_TO_FIRST_TOKEN_MS = "time_to_first_token_ms"
    TOKENS_INPUT = "tokens_input"
    TOKENS_OUTPUT = "tokens_output"
    TOKENS_TOTAL = "tokens_total"
    ESTIMATED_COST_USD = "estimated_cost_usd"
    RETRY_COUNT = "retry_count"
    CONTENT_SIZE_BYTES = "content_size_bytes"


class D:
    """Data field name constants (nested under 'data').

    The 'data' field contains event-specific payload. Structure depends on event type:

    tool.input:
        - tool_name: str - Name of the tool
        - triggered_by: str - Parent component
        - input: dict - {args: {...}, kwargs: {...}}

    tool.output:
        - tool_name: str
        - output: Any - Tool return value
        - duration_ms: float

    tool.error:
        - tool_name: str
        - error_type: str - Exception class name
        - error_message: str
        - stack_trace: str
        - input: dict - Original input that caused error
        - duration_ms: float

    llm.input:
        - llm_name: str - Provider name
        - triggered_by: str
        - input: dict - {args: {messages: [...], ...}, kwargs: {...}}

    llm.output:
        - llm_name: str
        - output: dict - Full LLM response with content, tool_calls, etc.
        - duration_ms: float

    agent.input:
        - agent_name: str
        - triggered_by: str
        - input: dict - Task/parameters

    agent.output:
        - agent_name: str
        - output: dict - Agent result
        - duration_ms: float
    """
    # Common fields
    INPUT = "input"
    OUTPUT = "output"
    DURATION_MS = "duration_ms"

    # Error fields
    ERROR_TYPE = "error_type"
    ERROR_MESSAGE = "error_message"
    STACK_TRACE = "stack_trace"

    # Component name fields (in data payload)
    TOOL_NAME = "tool_name"
    AGENT_NAME = "agent_name"
    LLM_NAME = "llm_name"


# =============================================================================
# LOG RECORD SCHEMA - Fields with ES types
# =============================================================================
LOG_RECORD_FIELDS: Dict[str, FieldDef] = {
    # Core identity fields - OTel standard format
    F.TIMESTAMP: FieldDef(F.TIMESTAMP, ESType.DATE, "When the event occurred (UTC)", required=True),
    F.TRACE_ID: FieldDef(F.TRACE_ID, ESType.KEYWORD, "OTel trace ID (32 hex chars, 128-bit)", required=True),
    F.SPAN_ID: FieldDef(F.SPAN_ID, ESType.KEYWORD, "OTel span ID (16 hex chars, 64-bit)", required=True),
    F.PARENT_SPAN_ID: FieldDef(F.PARENT_SPAN_ID, ESType.KEYWORD, "Parent span ID (None for root, 16 hex chars)"),
    F.SESSION_ID: FieldDef(F.SESSION_ID, ESType.KEYWORD, "Session identifier (sess_ prefix)"),
    F.REQUEST_ID: FieldDef(F.REQUEST_ID, ESType.KEYWORD, "Request identifier (req_ prefix)"),

    # Event classification
    F.LEVEL: FieldDef(F.LEVEL, ESType.KEYWORD, "Log level (DEBUG, INFO, WARNING, ERROR) - metadata only!", required=True),
    F.EVENT: FieldDef(F.EVENT, ESType.KEYWORD, "Event type (e.g., tool.input, agent.error)", required=True),

    # Component info
    F.COMPONENT_TYPE: FieldDef(F.COMPONENT_TYPE, ESType.KEYWORD, "Type: agent, tool, llm_client", required=True),
    F.COMPONENT_NAME: FieldDef(F.COMPONENT_NAME, ESType.KEYWORD, "Specific component name", required=True),
    F.TRIGGERED_BY: FieldDef(F.TRIGGERED_BY, ESType.KEYWORD, "Parent component that triggered this one", required=True),

    # Data payload (dynamic object - see class D for structure)
    F.DATA: FieldDef(F.DATA, ESType.OBJECT, "Full data payload (see class D for structure)"),

    # Metrics (typed numeric fields - see class M for field names)
    F.METRICS: FieldDef(F.METRICS, ESType.OBJECT, "Numeric metrics", nested_fields={
        M.DURATION_MS: FieldDef(M.DURATION_MS, ESType.FLOAT, "Execution duration in milliseconds"),
        M.TIME_TO_FIRST_TOKEN_MS: FieldDef(M.TIME_TO_FIRST_TOKEN_MS, ESType.FLOAT, "Time to first LLM token"),
        M.TOKENS_INPUT: FieldDef(M.TOKENS_INPUT, ESType.INTEGER, "Input token count"),
        M.TOKENS_OUTPUT: FieldDef(M.TOKENS_OUTPUT, ESType.INTEGER, "Output token count"),
        M.TOKENS_TOTAL: FieldDef(M.TOKENS_TOTAL, ESType.INTEGER, "Total token count"),
        M.ESTIMATED_COST_USD: FieldDef(M.ESTIMATED_COST_USD, ESType.FLOAT, "Estimated API cost in USD"),
        M.RETRY_COUNT: FieldDef(M.RETRY_COUNT, ESType.INTEGER, "Number of retries"),
        M.CONTENT_SIZE_BYTES: FieldDef(M.CONTENT_SIZE_BYTES, ESType.INTEGER, "Content size in bytes"),
    }),

    # Tags for filtering
    F.TAGS: FieldDef(F.TAGS, ESType.KEYWORD, "String tags for categorization"),
}


# =============================================================================
# TRACE EVENT SCHEMA - Fields with ES types
# Note: Spans are now created by OTel tracer, not stored in ES directly.
# This schema is kept for reference and any custom span events.
# =============================================================================
TRACE_EVENT_FIELDS: Dict[str, FieldDef] = {
    F.TYPE: FieldDef(F.TYPE, ESType.KEYWORD, "Record type discriminator (trace_event)"),
    F.NAME: FieldDef(F.NAME, ESType.KEYWORD, "Event name (e.g., tool.triggered)", required=True),
    F.TIMESTAMP: FieldDef(F.TIMESTAMP, ESType.DATE, "When the event occurred", required=True),
    F.TRACE_ID: FieldDef(F.TRACE_ID, ESType.KEYWORD, "OTel trace ID (32 hex chars)", required=True),
    F.SPAN_ID: FieldDef(F.SPAN_ID, ESType.KEYWORD, "OTel span ID (16 hex chars)", required=True),
    F.PARENT_SPAN_ID: FieldDef(F.PARENT_SPAN_ID, ESType.KEYWORD, "Parent span ID (16 hex chars)"),

    # Attributes (typed fields within dynamic object)
    F.ATTRIBUTES: FieldDef(F.ATTRIBUTES, ESType.OBJECT, "Span attributes", nested_fields={
        F.COMPONENT_TYPE: FieldDef(F.COMPONENT_TYPE, ESType.KEYWORD, "Component type"),
        F.COMPONENT_NAME: FieldDef(F.COMPONENT_NAME, ESType.KEYWORD, "Component name"),
        F.TRIGGERED_BY: FieldDef(F.TRIGGERED_BY, ESType.KEYWORD, "Parent component"),
        M.DURATION_MS: FieldDef(M.DURATION_MS, ESType.FLOAT, "Duration in milliseconds"),
        "success": FieldDef("success", ESType.BOOLEAN, "Whether operation succeeded"),
        D.ERROR_TYPE: FieldDef(D.ERROR_TYPE, ESType.KEYWORD, "Exception type name"),
        D.ERROR_MESSAGE: FieldDef(D.ERROR_MESSAGE, ESType.TEXT, "Error message (full-text searchable)"),
        M.TOKENS_INPUT: FieldDef(M.TOKENS_INPUT, ESType.INTEGER, "Input tokens"),
        M.TOKENS_OUTPUT: FieldDef(M.TOKENS_OUTPUT, ESType.INTEGER, "Output tokens"),
        M.TOKENS_TOTAL: FieldDef(M.TOKENS_TOTAL, ESType.INTEGER, "Total tokens"),
        M.ESTIMATED_COST_USD: FieldDef(M.ESTIMATED_COST_USD, ESType.FLOAT, "Estimated cost"),
        "llm_model": FieldDef("llm_model", ESType.KEYWORD, "LLM model name"),
        "llm_provider": FieldDef("llm_provider", ESType.KEYWORD, "LLM provider"),
    }),
}


# =============================================================================
# EVENT TAXONOMIES
# =============================================================================

LOG_EVENTS = {
    # Agent log events (full data capture)
    "agent.input": "Agent started with input data",
    "agent.output": "Agent completed with output data",
    "agent.error": "Agent failed with error details",
    "agent.iteration": "Agent loop iteration with state",
    "agent.decision": "Agent made a decision (tool selection, etc.)",

    # Tool log events (full data capture)
    "tool.input": "Tool called with input arguments",
    "tool.output": "Tool returned with output data",
    "tool.error": "Tool failed with error details",

    # LLM log events (full data capture)
    "llm.input": "LLM request with full messages",
    "llm.output": "LLM response with full content and usage",
    "llm.error": "LLM call failed with error details",

    # Application log events
    "application.start": "Application started",
    "application.complete": "Application completed successfully",
    "application.error": "Application failed",
    "application.interrupted": "Application interrupted by user",

    # Browser log events
    "browser.connect.start": "Browser connection initiated",
    "browser.connect.complete": "Browser connected",
    "browser.disconnect": "Browser disconnected",
    "browser.navigate": "Browser navigated to URL",
    "browser.query": "Browser DOM query executed",

    # Memory log events
    "memory.read": "Memory read operation",
    "memory.write": "Memory write operation",
    "memory.search": "Memory search operation",

    # Config log events
    "config.loaded": "Configuration loaded",
}

TRACE_EVENTS = {
    # Agent trace events (span lifecycle)
    "agent.triggered": "Agent execution started",
    "agent.execution_completed": "Agent finished successfully",
    "agent.error": "Agent failed",

    # Tool trace events (span lifecycle)
    "tool.triggered": "Tool execution started",
    "tool.execution_completed": "Tool finished successfully",
    "tool.error": "Tool failed",

    # LLM trace events (span lifecycle)
    "llm.triggered": "LLM call started",
    "llm.execution_completed": "LLM call finished",
    "llm.error": "LLM call failed",
}


# =============================================================================
# ES MAPPING GENERATOR
# =============================================================================

def field_to_es_mapping(field_def: FieldDef) -> dict:
    """Convert a FieldDef to ES mapping format."""
    if field_def.es_type == ESType.OBJECT:
        if field_def.nested_fields:
            return {
                "type": "object",
                "properties": {
                    name: field_to_es_mapping(f)
                    for name, f in field_def.nested_fields.items()
                }
            }
        else:
            # Dynamic object
            return {"type": "object", "enabled": True, "dynamic": True}
    else:
        return {"type": field_def.es_type.value}


def generate_es_mappings(fields: Dict[str, FieldDef]) -> dict:
    """Generate ES mappings from field definitions."""
    return {
        "properties": {
            name: field_to_es_mapping(field_def)
            for name, field_def in fields.items()
        }
    }


def generate_log_index_template(index_pattern: str = "crawler-logs*") -> dict:
    """Generate ES index template for log records."""
    return {
        "index_patterns": [index_pattern],
        "priority": 100,
        "template": {
            "settings": {
                "number_of_shards": 1,
                "number_of_replicas": 0,
                "index.refresh_interval": "5s"
            },
            "mappings": generate_es_mappings(LOG_RECORD_FIELDS)
        }
    }


def generate_trace_index_template(index_pattern: str = "crawler-traces*") -> dict:
    """Generate ES index template for trace events."""
    return {
        "index_patterns": [index_pattern],
        "priority": 100,
        "template": {
            "settings": {
                "number_of_shards": 1,
                "number_of_replicas": 0,
                "index.refresh_interval": "5s"
            },
            "mappings": generate_es_mappings(TRACE_EVENT_FIELDS)
        }
    }


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class LogRecord:
    """Complete log record for unconditional emission.

    IMPORTANT: Level is METADATA ONLY, never used for filtering.
    All events are always emitted.

    The 'data' field structure depends on event type - see class D for documentation.
    The 'metrics' field uses keys from class M.
    """
    timestamp: datetime
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    session_id: Optional[str]
    request_id: Optional[str]
    level: str
    event: str
    component_type: str
    component_name: str
    triggered_by: str
    data: Dict[str, Any] = field(default_factory=dict)
    metrics: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Serialize to dict for output. Field names from F class constants."""
        return {
            F.TIMESTAMP: self.timestamp.isoformat() if isinstance(self.timestamp, datetime) else self.timestamp,
            F.TRACE_ID: self.trace_id,
            F.SPAN_ID: self.span_id,
            F.PARENT_SPAN_ID: self.parent_span_id,
            F.SESSION_ID: self.session_id,
            F.REQUEST_ID: self.request_id,
            F.LEVEL: self.level,
            F.EVENT: self.event,
            F.COMPONENT_TYPE: self.component_type,
            F.COMPONENT_NAME: self.component_name,
            F.TRIGGERED_BY: self.triggered_by,
            F.DATA: self.data,
            F.METRICS: self.metrics,
            F.TAGS: self.tags
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'LogRecord':
        """Create LogRecord from dictionary. Field names from F class constants."""
        timestamp = data.get(F.TIMESTAMP)
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        elif timestamp is None:
            timestamp = datetime.now(timezone.utc)

        return cls(
            timestamp=timestamp,
            trace_id=data.get(F.TRACE_ID, ""),
            span_id=data.get(F.SPAN_ID, ""),
            parent_span_id=data.get(F.PARENT_SPAN_ID),
            session_id=data.get(F.SESSION_ID),
            request_id=data.get(F.REQUEST_ID),
            level=data.get(F.LEVEL, "INFO"),
            event=data.get(F.EVENT, ""),
            component_type=data.get(F.COMPONENT_TYPE, "unknown"),
            component_name=data.get(F.COMPONENT_NAME, "unknown"),
            triggered_by=data.get(F.TRIGGERED_BY, "direct_call"),
            data=data.get(F.DATA, {}),
            metrics=data.get(F.METRICS, {}),
            tags=data.get(F.TAGS, [])
        )


@dataclass
class TraceEvent:
    """Trace event for span creation/completion.

    The 'attributes' field contains span metadata - see TRACE_EVENT_FIELDS
    for the defined attribute schema.
    """
    name: str
    timestamp: datetime
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    attributes: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serialize to dict for output. Field names from F class constants."""
        return {
            F.NAME: self.name,
            F.TIMESTAMP: self.timestamp.isoformat() if isinstance(self.timestamp, datetime) else self.timestamp,
            F.TRACE_ID: self.trace_id,
            F.SPAN_ID: self.span_id,
            F.PARENT_SPAN_ID: self.parent_span_id,
            F.ATTRIBUTES: self.attributes
        }
