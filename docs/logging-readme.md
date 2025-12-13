# Structured Logging System

A production-ready logging system for the crawler agent with OpenTelemetry-compatible structured output, trace correlation, and cost tracking.

## Quick Start

```python
from src.core.log_context import init_logging, get_logger, span

# Initialize logging (call once at startup)
init_logging()

# Get logger instance
slog = get_logger()

# Log events
slog.info(
    event=LogEvent(
        category=EventCategory.TOOL_EXECUTION,
        event_type="tool.browser.navigate",
        name="Navigation completed",
    ),
    message="Navigated to https://example.com",
    data={"url": "https://example.com", "status": 200},
    tags=["browser", "navigate"],
)
```

## Configuration

All settings are configured via environment variables. Copy `.env.example` and customize:

```bash
# Logging Configuration
LOG_LEVEL=INFO                              # DEBUG, INFO, WARNING, ERROR
SERVICE_NAME=crawler-agent                  # Service name in logs

# Console Output
LOG_CONSOLE=true                            # Enable console output
LOG_COLOR=true                              # Colored output (disable in CI/CD)

# JSON Lines Output (for file-based logging)
LOG_JSONL=true                              # Enable JSONL file output
LOG_JSONL_PATH=                             # Custom path (auto-generated if empty)
LOG_JSONL_ASYNC=true                        # Async buffered writing
LOG_DIR=./logs                              # Log directory

# OpenTelemetry Export
LOG_OTEL=false                              # Enable OTel export
LOG_OTEL_ENDPOINT=localhost:4317            # OTLP gRPC endpoint (host:port)
LOG_OTEL_INSECURE=true                      # Use insecure (non-TLS) connection

# Production Features
LOG_SAMPLING=false                          # Enable event sampling
LOG_SAMPLING_RATE=1.0                       # Global rate (0.0-1.0)
LOG_REDACT_PII=true                         # Redact emails, phones, etc.
```

## Core Concepts

### Trace Hierarchy

Every log entry includes correlation IDs for distributed tracing:

```
session_id    → Unique per application run
  └─ request_id  → Unique per user request/workflow
       └─ trace_id   → Unique per agent task
            └─ span_id    → Unique per operation (with parent_span_id)
```

### Event Categories

```python
from src.core.structured_logger import EventCategory

EventCategory.LLM_CALL           # LLM API interactions
EventCategory.TOOL_EXECUTION     # Tool invocations
EventCategory.AGENT_LIFECYCLE    # Agent start/stop/iteration
EventCategory.BROWSER_OPERATION  # Browser actions
EventCategory.MEMORY_OPERATION   # Memory read/write
EventCategory.ERROR              # Error events
EventCategory.DECISION           # Routing/fallback decisions
```

### Log Levels

```python
from src.core.structured_logger import LogLevel

LogLevel.DEBUG    # Detailed debugging info
LogLevel.INFO     # Normal operations
LogLevel.WARNING  # Recoverable issues
LogLevel.ERROR    # Failures requiring attention
```

## Usage Patterns

### Basic Logging

```python
from src.core.log_context import get_logger
from src.core.structured_logger import EventCategory, LogEvent, LogMetrics

slog = get_logger()

# Simple info log
slog.info(
    event=LogEvent(
        category=EventCategory.TOOL_EXECUTION,
        event_type="tool.fetch.complete",
        name="HTTP fetch completed",
    ),
    message="Fetched page successfully",
    data={"url": "https://example.com", "status_code": 200},
)

# With timing metrics
slog.info(
    event=LogEvent(
        category=EventCategory.BROWSER_OPERATION,
        event_type="browser.navigate.complete",
        name="Navigation completed",
    ),
    message="Page loaded",
    metrics=LogMetrics(duration_ms=1250.5),
    tags=["browser", "navigate"],
)
```

### Logging LLM Calls

```python
slog.log_llm_call(
    model="gpt-5.1",
    tokens_input=1500,
    tokens_output=500,
    duration_ms=2340.0,
    success=True,
    prompt_preview="Analyze this HTML...",
    response_preview="The page contains...",
)
```

### Logging Tool Execution

```python
slog.log_tool_execution(
    tool_name="navigate",
    success=True,
    duration_ms=1500.0,
    input_preview="url=https://example.com",
    output_preview="status=success",
)
```

### Logging Agent Lifecycle

```python
slog.log_agent_lifecycle(
    agent_name="browser_agent",
    event_type="agent.start",
    message="Starting browser agent",
)

# Later...
slog.log_agent_lifecycle(
    agent_name="browser_agent",
    event_type="agent.complete",
    message="Browser agent completed",
    duration_ms=15000.0,
    iterations=5,
    success=True,
)
```

### Creating Spans for Operations

```python
from src.core.log_context import span

# Context manager creates a new span
with span("fetch_article_content"):
    # All logs within this block share the span_id
    slog.info(...)
    result = do_work()
    slog.info(...)
```

## Output Formats

### Console Output

Human-readable format with optional colors:

```
2025-12-13 10:30:45.123 INFO  [browser_agent] Navigation completed
  url=https://example.com status=200 duration_ms=1250
```

### JSON Lines Output

Machine-parseable format for log aggregation:

```json
{
  "timestamp": "2025-12-13T10:30:45.123Z",
  "level": "INFO",
  "message": "Navigation completed",
  "event": {
    "category": "browser_operation",
    "event_type": "browser.navigate.complete",
    "name": "Navigation completed"
  },
  "context": {
    "session_id": "sess_abc123",
    "request_id": "req_def456",
    "trace_id": "trace_ghi789",
    "span_id": "span_jkl012",
    "parent_span_id": "span_mno345"
  },
  "data": {
    "url": "https://example.com",
    "status": 200
  },
  "metrics": {
    "duration_ms": 1250.5
  },
  "tags": ["browser", "navigate"]
}
```

## Infrastructure Setup

### Minimal Setup (Elasticsearch + Kibana)

```bash
docker compose -f docker-compose.logging-minimal.yml up -d
```

- Kibana UI: http://localhost:5601
- Elasticsearch: http://localhost:9200

### Full Setup (with OpenTelemetry + Jaeger)

```bash
docker compose -f docker-compose.logging.yml up -d

# Optional: include Jaeger for trace visualization
docker compose -f docker-compose.logging.yml --profile jaeger up -d
```

- Kibana: http://localhost:5601
- Jaeger UI: http://localhost:16686
- OTel Collector: localhost:4317 (gRPC), localhost:4318 (HTTP)

### Ingesting Logs to Elasticsearch

```bash
# Ingest a JSONL log file
python scripts/ingest_logs.py logs/agent_20251213.jsonl

# With custom index
python scripts/ingest_logs.py logs/agent.jsonl --index my-logs
```

### Setting Up Elasticsearch Index Template

```bash
chmod +x infra/es-index-template.sh
./infra/es-index-template.sh
```

## Production Features

### PII Redaction

Automatically redacts sensitive data when `LOG_REDACT_PII=true`:

```python
from src.core.pii_redactor import PIIRedactor

redactor = PIIRedactor()

# Redacts emails, phones, credit cards, SSNs, API keys, passwords
text = "Contact john@example.com or call 555-123-4567"
safe_text = redactor.redact_string(text)
# "Contact [EMAIL] or call [PHONE]"
```

### Event Sampling

Reduce log volume for high-frequency events:

```python
from src.core.sampling import EventSampler, SamplingConfig

config = SamplingConfig(
    global_rate=1.0,  # Default: log everything
    event_type_rates={
        "memory.read": 0.1,      # Log 10% of memory reads
        "browser.query": 0.1,    # Log 10% of DOM queries
    },
    always_log_event_types={
        "agent.start",
        "agent.complete",
        "llm.call.complete",
        "error",
    },
)

sampler = EventSampler(config)
```

### Cost Tracking

Automatic cost estimation for LLM calls:

```python
from src.core.log_config import estimate_cost

cost = estimate_cost(
    model="gpt-5.1",
    tokens_input=1500,
    tokens_output=500,
)
# Returns: 0.006875 (USD)
```

Supported models include GPT-5.x, GPT-4.x, o-series, and Claude models.

## File Structure

```
src/core/
├── structured_logger.py   # Core logger with event schema
├── log_context.py         # Context management (trace IDs, spans)
├── log_config.py          # Configuration and cost tables
├── pii_redactor.py        # PII pattern redaction
└── sampling.py            # Event sampling logic

docker-compose.logging.yml          # Full logging stack
docker-compose.logging-minimal.yml  # Minimal ES + Kibana
infra/
├── otel-collector-config.yaml      # OTel collector config
└── es-index-template.sh            # ES index template
scripts/
└── ingest_logs.py                  # JSONL to ES ingestion
```

## Event Type Reference

### Agent Events
- `agent.start` - Agent begins execution
- `agent.iteration` - Agent loop iteration
- `agent.complete` - Agent finishes successfully
- `agent.error` - Agent fails
- `agent.subagent.start` - Sub-agent invocation
- `agent.subagent.complete` - Sub-agent completion

### LLM Events
- `llm.call.start` - LLM request initiated
- `llm.call.complete` - LLM response received
- `llm.call.error` - LLM call failed

### Tool Events
- `tool.execute.start` - Tool invocation begins
- `tool.execute.complete` - Tool returns result
- `tool.execute.error` - Tool fails

### Browser Events
- `browser.navigate.start/complete` - Page navigation
- `browser.click.start/complete` - Element click
- `browser.query.start/complete` - DOM query
- `browser.extract.complete` - Content extraction

### Memory Events
- `memory.read` - Memory key read
- `memory.write` - Memory key write
- `memory.search` - Pattern search
- `memory.dump` - Export to file

## Using Kibana

### Automatic Setup (Recommended)

Run the setup script to import the pre-built dashboard, saved searches, and visualizations:

```bash
# After Kibana is running
./infra/setup-kibana.sh
```

This creates:
- **Data view**: `crawler-logs-*`
- **Saved searches**: All Logs, Errors Only, LLM Calls, Agent Events, Slow Operations
- **Dashboard**: Crawler Agent Dashboard with 8 visualizations
- **Visualizations**: Error trends, LLM costs, token usage, agent duration, tool usage

After setup, go directly to: http://localhost:5601/app/dashboards#/view/crawler-dashboard

### Manual Setup (Alternative)

1. **Open Kibana**: http://localhost:5601

2. **Create Data View** (required before searching):
   - Go to **Stack Management** (gear icon in left sidebar) → **Data Views**
   - Click **Create data view**
   - Name: `crawler-logs`
   - Index pattern: `crawler-logs-*`
   - Timestamp field: `@timestamp`
   - Click **Save data view to Kibana**

3. **Discover Logs**:
   - Go to **Discover** (compass icon in left sidebar)
   - Select `crawler-logs` data view from the dropdown
   - Adjust time range in top-right (e.g., "Last 15 minutes")

### Searching Logs

**Basic search examples:**

```
# Find all errors
level: ERROR

# Find specific agent
context.agent_name: browser_agent

# Find LLM calls
event.category: llm_call

# Find slow operations (>5 seconds)
metrics.duration_ms > 5000

# Find by trace ID
context.trace_id: "trace_abc123"

# Combine filters
level: ERROR AND event.category: tool_execution
```

### Useful Fields to Add as Columns

In Discover, click **+** next to fields to add them as columns:
- `level` - Log level
- `message` - Human-readable message
- `event.event_type` - Specific event type
- `context.agent_name` - Which agent
- `metrics.duration_ms` - Operation timing
- `metrics.cost_usd` - LLM cost

### Creating Dashboards

1. Go to **Dashboard** (grid icon) → **Create dashboard**
2. Click **Create visualization**

**Useful visualizations:**

| Visualization | Type | Configuration |
|---------------|------|---------------|
| Errors over time | Line chart | X: @timestamp, Y: Count, Filter: level:ERROR |
| LLM costs | Metric | Sum of metrics.cost_usd |
| Agent duration | Bar chart | X: context.agent_name, Y: Avg metrics.duration_ms |
| Events by category | Pie chart | Split by event.category |
| Tool usage | Table | Split by event.event_type, filter: event.category:tool_execution |

### Saved Searches

Save frequently used searches:
1. Set up your filters in Discover
2. Click **Save** in top toolbar
3. Name it (e.g., "All Errors", "LLM Calls", "Slow Operations")

## Using Jaeger

### First Time Setup

1. Start with Jaeger profile:
   ```bash
   docker compose -f docker-compose.logging.yml --profile jaeger up -d
   ```

2. **Open Jaeger UI**: http://localhost:16686

### Finding Traces

1. **Service dropdown**: Select `crawler-agent`
2. **Operation dropdown**: Select specific operation or leave as "all"
3. **Tags**: Add filters like `agent.name=browser_agent`
4. **Lookback**: Set time range (e.g., "Last Hour")
5. Click **Find Traces**

### Reading Trace View

When you click on a trace:

```
[Trace Timeline]
├─ main_agent (15.2s)                    ← Root span
│  ├─ run_browser_agent (8.5s)           ← Sub-agent call
│  │  ├─ navigate (1.2s)                 ← Tool execution
│  │  ├─ llm.chat (3.1s)                 ← LLM call
│  │  └─ extract_links (2.8s)
│  ├─ run_selector_agent (4.2s)
│  │  └─ ...
│  └─ generate_plan (1.5s)
```

- **Horizontal bars** show duration
- **Nesting** shows parent-child relationships
- Click any span to see **tags** (metadata) and **logs** (events)

### Useful Jaeger Queries

**By tag:**
```
agent.name=browser_agent
tool.name=navigate
llm.model=gpt-5.1
error=true
```

**By duration:**
- Use the "Min Duration" / "Max Duration" filters
- Find slow traces: Min Duration = 10s

**Compare traces:**
1. Select two traces using checkboxes
2. Click **Compare** to see side-by-side timing

### Trace to Logs Correlation

1. In Jaeger, find a trace and copy the `trace_id`
2. In Kibana Discover, search: `context.trace_id: "your-trace-id"`
3. See all log entries for that specific trace

## Using OpenTelemetry Collector

The OTel Collector receives traces/logs and forwards to backends.

### Verify Collector is Running

```bash
# Check health
curl http://localhost:8888/metrics

# View logs
docker logs crawler-otel-collector
```

### Collector Endpoints

| Port | Protocol | Use |
|------|----------|-----|
| 4317 | gRPC | OTLP gRPC receiver |
| 4318 | HTTP | OTLP HTTP receiver |
| 8888 | HTTP | Prometheus metrics |

### Sending Test Data

```bash
# Send test trace via HTTP
curl -X POST http://localhost:4318/v1/traces \
  -H "Content-Type: application/json" \
  -d '{"resourceSpans": []}'
```

## Common Workflows

### Debug a Failed Agent Run

1. **Find the error in Kibana:**
   ```
   level: ERROR AND context.agent_name: main_agent
   ```

2. **Get the trace_id** from the error log

3. **View full trace in Jaeger:**
   - Search by trace_id
   - See which operation failed and when

4. **Get detailed logs in Kibana:**
   ```
   context.trace_id: "trace_xxx"
   ```
   - Sort by @timestamp ascending to see sequence

### Analyze LLM Costs

1. **In Kibana, create search:**
   ```
   event.event_type: llm.call.complete
   ```

2. **Add columns:** metrics.cost_usd, metrics.tokens_input, metrics.tokens_output, data.model

3. **Create visualization:**
   - Type: Data table
   - Metrics: Sum of metrics.cost_usd
   - Split rows by: data.model
   - Shows cost breakdown by model

### Find Performance Bottlenecks

1. **In Jaeger:**
   - Find traces with high total duration
   - Look for spans that take disproportionate time

2. **In Kibana:**
   ```
   metrics.duration_ms > 5000
   ```
   - Sort by duration descending
   - Identify slow tools/operations

### Monitor Agent Health

**Create Kibana dashboard with:**

1. **Error rate** (line chart):
   - Filter: level:ERROR
   - X: @timestamp (date histogram)
   - Y: Count

2. **Agent completions** (metric):
   - Filter: event.event_type:agent.complete
   - Show count

3. **Success rate** (gauge):
   - Filter: event.event_type:agent.complete
   - Percentage where data.success:true

4. **Avg duration by agent** (bar):
   - Split by context.agent_name
   - Y: Avg metrics.duration_ms

## Troubleshooting

### Logs not appearing in Elasticsearch

1. Check ES is healthy: `curl http://localhost:9200/_cluster/health`
2. Verify index exists: `curl http://localhost:9200/_cat/indices`
3. Check OTel collector logs: `docker logs crawler-otel-collector`

### Kibana won't start (disk watermark error)

The docker-compose files disable disk watermarks for development. If you still see errors:

```bash
docker compose -f docker-compose.logging.yml down
docker volume rm agent2_elasticsearch-data
docker compose -f docker-compose.logging.yml up -d
```

### Missing trace correlation

Ensure `init_logging()` is called before any logging, and use `span()` context manager for nested operations.
