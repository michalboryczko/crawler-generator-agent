# Architecture Patterns

This document describes the key architectural patterns used in this project. All new features and components should follow these patterns for consistency.

## Table of Contents

1. [Project Structure](#1-project-structure)
2. [Configuration Patterns](#2-configuration-patterns)
3. [Dependency Injection](#3-dependency-injection)
4. [Tool Pattern](#4-tool-pattern)
5. [Agent Pattern](#5-agent-pattern)
6. [Error Handling](#6-error-handling)
7. [Logging & Observability](#7-logging--observability)
8. [Memory & Data Flow](#8-memory--data-flow)
9. [Async Patterns](#9-async-patterns)
10. [Design Patterns Summary](#10-design-patterns-summary)

---

## 1. Project Structure

### Directory Organization

```
src/
├── core/                    # Core infrastructure & abstractions
│   ├── config.py           # Configuration dataclasses
│   ├── llm.py              # LLM client wrapper
│   ├── browser.py          # CDP browser client
│   ├── structured_logger.py # Structured logging system
│   ├── log_context.py      # Context propagation
│   ├── log_config.py       # Logging configuration
│   └── log_outputs.py      # Output destinations
│
├── agents/                  # Agent implementations
│   ├── base.py             # BaseAgent abstract class
│   ├── main_agent.py       # Orchestrator agent
│   ├── browser_agent.py    # Browser navigation agent
│   ├── selector_agent.py   # CSS selector discovery agent
│   ├── accessibility_agent.py
│   └── data_prep_agent.py
│
└── tools/                   # Tool implementations
    ├── base.py             # BaseTool abstract class
    ├── browser.py          # Browser tools
    ├── memory.py           # Memory store tools
    ├── orchestration.py    # Sub-agent invocation tools
    ├── extraction.py       # Data extraction tools
    └── ...
```

### Module Boundaries

| Module | Responsibility | Dependencies |
|--------|---------------|--------------|
| `core/` | Infrastructure, no business logic | External libs only |
| `agents/` | Reasoning loops, orchestration | `core/`, `tools/` |
| `tools/` | Atomic actions, side effects | `core/` |

### Import Rules

```python
# GOOD: Tools import from core
from src.core.config import BrowserConfig
from src.core.llm import LLMClient

# GOOD: Agents import from core and tools
from src.core.llm import LLMClient
from src.tools.browser import NavigateTool

# BAD: Core should not import from agents or tools
# BAD: Tools should not import from agents
```

---

## 2. Configuration Patterns

### Pattern: Dataclass with `from_env()` Factory

All configuration uses dataclasses with a `from_env()` class method for loading from environment variables.

```python
from dataclasses import dataclass
from typing import Optional
import os


@dataclass
class ServiceConfig:
    """Configuration for a service."""

    # Required fields (no default)
    api_key: str

    # Optional fields (with defaults)
    endpoint: str = "https://api.example.com"
    timeout: int = 30
    max_retries: int = 3

    @classmethod
    def from_env(cls) -> "ServiceConfig":
        """
        Load configuration from environment variables.

        Environment variables:
            SERVICE_API_KEY: Required API key
            SERVICE_ENDPOINT: Optional endpoint URL
            SERVICE_TIMEOUT: Optional timeout in seconds
        """
        api_key = os.environ.get("SERVICE_API_KEY")
        if not api_key:
            raise ValueError("SERVICE_API_KEY environment variable required")

        return cls(
            api_key=api_key,
            endpoint=os.environ.get("SERVICE_ENDPOINT", cls.endpoint),
            timeout=int(os.environ.get("SERVICE_TIMEOUT", cls.timeout)),
            max_retries=int(os.environ.get("SERVICE_MAX_RETRIES", cls.max_retries)),
        )
```

### Pattern: Hierarchical Configuration Composition

Compose smaller configs into larger application config:

```python
@dataclass
class AppConfig:
    """Main application configuration."""
    openai: OpenAIConfig
    browser: BrowserConfig
    output: OutputConfig
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "AppConfig":
        """Load all configuration from environment."""
        return cls(
            openai=OpenAIConfig.from_env(),
            browser=BrowserConfig.from_env(),
            output=OutputConfig.from_env(),
            log_level=os.environ.get("LOG_LEVEL", "INFO"),
        )
```

### Pattern: Preset Configurations

Provide named presets for common scenarios:

```python
@dataclass
class LoggingConfig:
    min_level: str = "INFO"
    console_enabled: bool = True
    jsonl_enabled: bool = True

    @classmethod
    def from_env(cls) -> "LoggingConfig":
        """Load from environment variables."""
        ...

    @classmethod
    def development(cls) -> "LoggingConfig":
        """Pre-configured for development."""
        return cls(
            min_level="DEBUG",
            console_enabled=True,
            jsonl_enabled=False,
        )

    @classmethod
    def production(cls) -> "LoggingConfig":
        """Pre-configured for production."""
        return cls(
            min_level="INFO",
            console_enabled=False,
            jsonl_enabled=True,
        )

    @classmethod
    def testing(cls) -> "LoggingConfig":
        """Pre-configured for testing."""
        return cls(
            min_level="WARNING",
            console_enabled=False,
            jsonl_enabled=False,
        )
```

### Validation Rules

1. **Fail fast**: Validate required fields in `from_env()`, raise `ValueError` immediately
2. **Type conversion**: Convert env strings to proper types (`int()`, `float()`, `bool`)
3. **Defaults**: Always provide sensible defaults for optional fields
4. **Documentation**: Document env var names in docstrings

---

## 3. Dependency Injection

### Pattern: Constructor Injection

Pass dependencies through constructors, not global state:

```python
class MyAgent(BaseAgent):
    def __init__(
        self,
        llm: LLMClient,                    # Required
        browser_session: BrowserSession,    # Required
        memory_store: MemoryStore | None = None,  # Optional with default
    ):
        self.memory_store = memory_store or MemoryStore()
        self.browser_session = browser_session

        # Create tools with injected dependencies
        tools = [
            NavigateTool(browser_session),
            MemoryReadTool(self.memory_store),
            MemoryWriteTool(self.memory_store),
        ]

        super().__init__(llm, tools)
```

### Pattern: Dependency Flow

Dependencies flow from `main.py` down through the component hierarchy:

```
main.py
  │
  ├── config = AppConfig.from_env()
  ├── llm = LLMClient(config.openai)
  ├── browser = BrowserSession(config.browser)
  ├── memory = MemoryStore()
  │
  └── MainAgent(llm, browser, output_dir, memory)
        │
        ├── BrowserAgent(llm, browser, memory)
        │     └── Tools(browser, memory)
        │
        ├── SelectorAgent(llm, browser, memory)
        │     └── Tools(llm, browser, memory)
        │
        └── Tools(memory, output_dir, sub_agents)
```

### Pattern: Context-Based Injection (Logging)

For cross-cutting concerns like logging, use context variables:

```python
from contextvars import ContextVar

# Global context variable (thread-safe)
_current_logger: ContextVar[StructuredLogger | None] = ContextVar(
    "current_logger", default=None
)

def get_logger() -> StructuredLogger | None:
    """Get current logger from context."""
    return _current_logger.get()

def set_logger(logger: StructuredLogger) -> None:
    """Set current logger in context."""
    _current_logger.set(logger)

# Usage anywhere in code:
slog = get_logger()
if slog:
    slog.info(...)
```

### Anti-Patterns to Avoid

```python
# BAD: Global imports
from src.core.llm import global_llm_client  # Don't do this

# BAD: Hardcoded instantiation
class MyTool:
    def __init__(self):
        self.llm = LLMClient(OpenAIConfig.from_env())  # Don't do this

# GOOD: Accept dependencies
class MyTool:
    def __init__(self, llm: LLMClient):
        self.llm = llm
```

---

## 4. Tool Pattern

### BaseTool Interface

All tools extend `BaseTool` and implement the required methods:

```python
from abc import ABC, abstractmethod
from typing import Any


class BaseTool(ABC):
    """Abstract base class for all tools."""

    # Class attributes - override in subclasses
    name: str = "base_tool"
    description: str = "Base tool description"

    @abstractmethod
    def execute(self, **kwargs: Any) -> dict[str, Any]:
        """
        Execute the tool with given parameters.

        Returns:
            dict with structure:
            - Success: {"success": True, "result": <any>}
            - Failure: {"success": False, "error": <str>}
        """
        pass

    @abstractmethod
    def get_parameters_schema(self) -> dict[str, Any]:
        """
        Return JSON schema for tool parameters.

        Returns:
            JSON Schema object describing parameters
        """
        pass

    def to_openai_schema(self) -> dict[str, Any]:
        """Convert tool to OpenAI function calling schema."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.get_parameters_schema()
            }
        }
```

### Tool Implementation Template

```python
class MyActionTool(BaseTool):
    """Tool that performs some action."""

    name = "my_action"
    description = "Performs a specific action with the given parameters."

    def __init__(self, dependency: SomeDependency):
        """
        Initialize tool with dependencies.

        Args:
            dependency: Required dependency for this tool
        """
        self.dependency = dependency

    def get_parameters_schema(self) -> dict[str, Any]:
        """Define the parameters this tool accepts."""
        return {
            "type": "object",
            "properties": {
                "required_param": {
                    "type": "string",
                    "description": "A required string parameter"
                },
                "optional_param": {
                    "type": "integer",
                    "description": "An optional integer parameter",
                    "default": 10
                },
                "enum_param": {
                    "type": "string",
                    "enum": ["option_a", "option_b", "option_c"],
                    "description": "One of the allowed options"
                }
            },
            "required": ["required_param"]
        }

    def execute(
        self,
        required_param: str,
        optional_param: int = 10,
        enum_param: str = "option_a",
    ) -> dict[str, Any]:
        """
        Execute the action.

        Args:
            required_param: The required parameter
            optional_param: Optional parameter with default
            enum_param: One of the allowed options

        Returns:
            Result dict with success status
        """
        slog = get_logger()

        try:
            # Log start
            if slog:
                slog.debug(
                    event=LogEvent(
                        category=EventCategory.TOOL_EXECUTION,
                        event_type="my_action.start",
                        name="MyAction started",
                    ),
                    message=f"Starting action with param: {required_param}",
                )

            # Do the actual work
            result = self.dependency.do_something(required_param, optional_param)

            return {
                "success": True,
                "result": result,
                "details": {"param_used": required_param}
            }

        except SpecificError as e:
            return {
                "success": False,
                "error": f"Specific error occurred: {str(e)}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Unexpected error: {str(e)}"
            }
```

### Parameter Schema Patterns

```python
# String parameter
"name": {
    "type": "string",
    "description": "Description of the parameter"
}

# Integer with constraints
"count": {
    "type": "integer",
    "description": "Number of items",
    "minimum": 1,
    "maximum": 100,
    "default": 10
}

# Enum (fixed choices)
"format": {
    "type": "string",
    "enum": ["json", "csv", "xml"],
    "description": "Output format"
}

# Array of strings
"urls": {
    "type": "array",
    "items": {"type": "string"},
    "description": "List of URLs to process"
}

# Nested object
"options": {
    "type": "object",
    "properties": {
        "verbose": {"type": "boolean"},
        "timeout": {"type": "integer"}
    },
    "description": "Additional options"
}
```

### Tool Categories

| Category | Purpose | Example Tools |
|----------|---------|---------------|
| Browser | Web interaction | Navigate, GetHTML, Click, QuerySelector |
| Memory | Data storage | Read, Write, Search, List, Dump |
| Extraction | Data extraction | BatchExtract, SelectorExtract |
| Orchestration | Sub-agent control | RunBrowserAgent, RunSelectorAgent |
| File | File operations | FileCreate, FileReplace |
| HTTP | Direct HTTP | HTTPRequest |
| Generation | Content creation | GeneratePlan, GenerateTest |

---

## 5. Agent Pattern

### BaseAgent Structure

```python
class BaseAgent:
    """Base class for all agents with thought-action-observation loop."""

    name: str = "base_agent"
    system_prompt: str = "You are a helpful assistant."

    def __init__(
        self,
        llm: LLMClient,
        tools: list[BaseTool] | None = None,
    ):
        self.llm = llm
        self.tools = tools or []
        self._tool_map = {t.name: t for t in self.tools}

    def run(self, task: str) -> dict[str, Any]:
        """Execute task with thought-action-observation loop."""
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": task}
        ]

        for iteration in range(MAX_ITERATIONS):
            # THOUGHT: Get LLM response
            response = self.llm.chat(
                messages,
                tools=self.tools if self.tools else None
            )

            if response["tool_calls"]:
                # ACTION: Execute tool (one at a time)
                tool_call = response["tool_calls"][0]

                messages.append({
                    "role": "assistant",
                    "content": response["content"],
                    "tool_calls": [tool_call]
                })

                # OBSERVATION: Get result
                result = self._execute_tool(
                    tool_call["name"],
                    tool_call["arguments"]
                )

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": str(result)
                })
            else:
                # No tool calls - agent is done
                return {
                    "success": True,
                    "result": response["content"],
                    "history": messages,
                    "iterations": iteration + 1
                }

        return {
            "success": False,
            "error": f"Max iterations ({MAX_ITERATIONS}) reached",
            "history": messages,
        }
```

### Agent Implementation Template

```python
class MySpecializedAgent(BaseAgent):
    """Agent specialized for a specific task domain."""

    name = "my_specialized_agent"

    system_prompt = """You are a specialized agent for [domain].

## Your Capabilities
- Capability 1
- Capability 2

## Available Tools
- tool_name_1: Description of what it does
- tool_name_2: Description of what it does

## Workflow
1. First, do X
2. Then, do Y
3. Finally, do Z

## Important Rules
- Always do A before B
- Never do C without D
"""

    def __init__(
        self,
        llm: LLMClient,
        some_dependency: SomeDependency,
        memory_store: MemoryStore,
    ):
        self.some_dependency = some_dependency
        self.memory_store = memory_store

        tools = [
            SpecificTool1(some_dependency),
            SpecificTool2(some_dependency),
            MemoryReadTool(memory_store),
            MemoryWriteTool(memory_store),
        ]

        super().__init__(llm, tools)
```

### Agent Hierarchy

```
BaseAgent (abstract)
│
├── MainAgent (orchestrator)
│   ├── Coordinates sub-agents
│   ├── Manages workflow phases
│   └── Produces final outputs
│
├── BrowserAgent
│   ├── Web navigation
│   └── Page interaction
│
├── SelectorAgent
│   ├── CSS selector discovery
│   └── Pattern recognition
│
├── AccessibilityAgent
│   └── HTTP accessibility checks
│
└── DataPrepAgent
    └── Test dataset creation
```

### Sequential Tool Execution

Tools are executed one at a time to maintain deterministic state:

```python
# In BaseAgent.run():
if response["tool_calls"]:
    # Only process first tool call
    tool_calls_to_process = response["tool_calls"][:1]

    if len(response["tool_calls"]) > 1:
        logger.warning(
            f"Model returned {len(response['tool_calls'])} tool calls, "
            f"but only processing first one"
        )

# In LLMClient:
kwargs["parallel_tool_calls"] = False
```

---

## 6. Error Handling

### Pattern: Structured Error Returns

Tools return errors as structured dicts, not exceptions:

```python
def execute(self, **kwargs) -> dict[str, Any]:
    try:
        result = do_something()
        return {"success": True, "result": result}
    except SpecificError as e:
        return {"success": False, "error": f"Specific error: {e}"}
    except Exception as e:
        return {"success": False, "error": f"Unexpected error: {e}"}
```

### Pattern: Error Propagation to LLM

Errors are added to message history so the LLM can adapt:

```python
result = self._execute_tool(tool_call["name"], tool_call["arguments"])
messages.append({
    "role": "tool",
    "tool_call_id": tool_call["id"],
    "content": str(result)  # Includes error info
})
# LLM sees: {"success": false, "error": "..."}
# LLM can retry with different parameters
```

### Pattern: Fail-Fast Configuration

Validate configuration at startup:

```python
@classmethod
def from_env(cls) -> "Config":
    api_key = os.environ.get("API_KEY")
    if not api_key:
        raise ValueError("API_KEY environment variable required")

    timeout = os.environ.get("TIMEOUT", "30")
    try:
        timeout = int(timeout)
    except ValueError:
        raise ValueError(f"TIMEOUT must be integer, got: {timeout}")

    return cls(api_key=api_key, timeout=timeout)
```

### Pattern: Logged Error Handling

Always log errors with context:

```python
def _execute_tool(self, name: str, arguments: dict) -> dict:
    slog = get_logger()

    try:
        start_time = time.perf_counter()
        result = tool.execute(**arguments)
        duration_ms = (time.perf_counter() - start_time) * 1000

        if slog:
            slog.log_tool_execution(
                tool_name=name,
                success=True,
                duration_ms=duration_ms,
            )
        return result

    except Exception as e:
        duration_ms = (time.perf_counter() - start_time) * 1000

        if slog:
            slog.log_tool_execution(
                tool_name=name,
                success=False,
                duration_ms=duration_ms,
                error=str(e),
            )
        return {"success": False, "error": str(e)}
```

### Error Categories

| Category | Handling | Example |
|----------|----------|---------|
| Configuration | Fail fast at startup | Missing API key |
| Tool execution | Return error dict | Network timeout |
| Agent iteration | Return with error | Max iterations |
| Unexpected | Log and return error | Null pointer |

---

## 7. Logging & Observability

### Structured Log Entry

Every log entry contains:

```python
@dataclass
class LogEntry:
    timestamp: datetime           # When
    level: LogLevel              # Severity (DEBUG, INFO, WARNING, ERROR)
    level_detail: LogLevelDetail # Sub-level for filtering
    logger: str                  # Logger name
    trace_context: TraceContext  # Correlation IDs
    event: LogEvent              # What happened
    context: dict[str, Any]      # Contextual data
    data: dict[str, Any]         # Event-specific data
    metrics: LogMetrics          # Measurements
    tags: list[str]              # For filtering
    message: str                 # Human-readable
```

### Event Categories

```python
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
```

### Trace Context Hierarchy

```
Session (app lifecycle)
  └── Request (agent task)
       └── Trace (major operation)
            └── Span (sub-operation)
                 └── Child Span (nested operation)
```

### Logging Usage Patterns

```python
# Get logger from context
slog = get_logger()

# Simple info log
slog.info(
    event=LogEvent(
        category=EventCategory.AGENT_LIFECYCLE,
        event_type="agent.start",
        name="Agent started",
    ),
    message="Starting browser agent",
    data={"task": task[:100]},
    tags=["agent", "browser", "start"],
)

# Log with metrics
slog.log_llm_call(
    model="gpt-4o",
    tokens_input=1500,
    tokens_output=200,
    duration_ms=1234.5,
    estimated_cost_usd=0.0425,
    finish_reason="tool_calls",
    tool_called="browser_navigate",
)

# Log tool execution
slog.log_tool_execution(
    tool_name="browser_navigate",
    success=True,
    duration_ms=2500.0,
    input_preview="url=https://example.com",
    output_preview="Navigated successfully",
)

# Create child span for nested operations
with span("extract_data", context={"url": url}):
    slog = get_logger()  # Gets child logger
    slog.info(...)
```

### Multiple Output Destinations

```python
# Configure outputs
outputs = [
    ConsoleOutput(color=True),                    # Human-readable
    AsyncBufferedOutput(                          # Buffered file
        JSONLinesOutput(file_path="logs/app.jsonl")
    ),
    OpenTelemetryOutput(                          # Distributed tracing
        service_name="my-service",
        endpoint="http://localhost:4317"
    )
]
```

---

## 8. Memory & Data Flow

### Memory Store Pattern

Singleton shared store for cross-agent communication:

```python
class MemoryStore:
    """Singleton in-memory storage shared across all agents."""

    _instance = None
    _data: dict[str, Any] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._data = {}
        return cls._instance

    def read(self, key: str) -> Any | None:
        return self._data.get(key)

    def write(self, key: str, value: Any) -> None:
        self._data[key] = value

    def search(self, pattern: str) -> list[str]:
        """Search keys matching glob pattern."""
        return [k for k in self._data.keys()
                if fnmatch.fnmatch(k, pattern)]

    def dump_to_jsonl(self, keys: list[str], path: Path) -> int:
        """Export keys to JSONL file."""
        ...
```

### Key Naming Conventions

```
# Agent outputs
extracted_articles         # List of found articles
pagination_type           # Type of pagination found
pagination_selector       # CSS selector for pagination

# Selector discovery
article_selector          # Main article link selector
detail_selectors          # Map of detail page selectors
listing_container_selector

# Test data (indexed)
test-data-listing-1       # First listing test case
test-data-listing-2       # Second listing test case
test-data-article-1       # First article test case

# Configuration
target_url                # Initial URL to process
```

### Data Flow Between Agents

```
MainAgent orchestrates:
  │
  ├─→ BrowserAgent
  │     Writes: extracted_articles, pagination_*
  │
  ├─→ SelectorAgent (reads pagination_*)
  │     Writes: article_selector, detail_selectors
  │
  ├─→ AccessibilityAgent (reads selectors)
  │     Writes: accessibility_result
  │
  ├─→ DataPrepAgent (reads all above)
  │     Writes: test-data-listing-*, test-data-article-*
  │
  └─→ Output generation (reads all)
        Creates: plan.md, test.md, test_set.jsonl
```

### Message History

Agents maintain full conversation history:

```python
messages = [
    {"role": "system", "content": system_prompt},
    {"role": "user", "content": task},
    # Iteration 1
    {"role": "assistant", "content": "...", "tool_calls": [...]},
    {"role": "tool", "tool_call_id": "...", "content": "..."},
    # Iteration 2
    {"role": "assistant", "content": "...", "tool_calls": [...]},
    {"role": "tool", "tool_call_id": "...", "content": "..."},
    # Final response
    {"role": "assistant", "content": "Final answer..."},
]
```

---

## 9. Async Patterns

### Pattern: Async Core with Sync Wrapper

Internal async implementation with sync API for tools:

```python
class CDPClient:
    """Chrome DevTools Protocol client (async)."""

    async def navigate(self, url: str) -> dict:
        result = await self.send("Page.navigate", {"url": url})
        await asyncio.sleep(2)
        return result


class BrowserSession:
    """Synchronous wrapper for tool use."""

    def __init__(self, config: BrowserConfig):
        self._client: CDPClient | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    def _run(self, coro):
        """Run coroutine synchronously."""
        loop = self._get_loop()
        if loop.is_running():
            # Handle nested event loops
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result()
        return loop.run_until_complete(coro)

    def navigate(self, url: str) -> dict:
        """Sync interface for navigation."""
        return self._run(self._client.navigate(url))
```

### Pattern: Per-Request Event Loop

For tools making HTTP requests:

```python
class HTTPRequestTool(BaseTool):
    def execute(self, url: str, **kwargs) -> dict:
        async def _request():
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    return await response.text()

        try:
            loop = asyncio.new_event_loop()
            result = loop.run_until_complete(_request())
            loop.close()
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}
```

### Pattern: Async Buffered Output

Non-blocking logging with background flush:

```python
class AsyncBufferedOutput(LogOutput):
    def __init__(self, output: LogOutput, buffer_size: int = 100):
        self.output = output
        self.queue: Queue[LogEntry] = Queue()
        self.thread = threading.Thread(target=self._flush_loop, daemon=True)
        self.thread.start()

    def write(self, entry: LogEntry) -> None:
        """Queue entry (non-blocking)."""
        self.queue.put(entry)

    def _flush_loop(self):
        """Background thread that flushes."""
        while not self.stopped:
            entry = self.queue.get(timeout=1.0)
            self.output.write(entry)
```

---

## 10. Design Patterns Summary

### Patterns Used

| Pattern | Location | Purpose |
|---------|----------|---------|
| **Factory** | `LoggingConfig.create_outputs()` | Create objects based on config |
| **Singleton** | `MemoryStore` | Shared state across agents |
| **Strategy** | `BaseTool` implementations | Interchangeable algorithms |
| **Template Method** | `BaseAgent.run()` | Algorithm skeleton with hooks |
| **Adapter** | `BrowserSession` | Async→Sync interface conversion |
| **Decorator** | `@with_span()` | Add behavior to functions |
| **Composite** | `AppConfig` | Hierarchical configuration |
| **Observer** | `LogOutput` list | Multiple output destinations |

### Pattern: Factory

```python
def create_outputs(self) -> list[LogOutput]:
    """Create log outputs based on configuration."""
    outputs = []
    if self.console_enabled:
        outputs.append(ConsoleOutput(color=self.console_color))
    if self.jsonl_enabled:
        outputs.append(JSONLinesOutput(path=self.jsonl_path))
    return outputs
```

### Pattern: Singleton

```python
class MemoryStore:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
```

### Pattern: Strategy

```python
class BaseTool(ABC):
    @abstractmethod
    def execute(self, **kwargs) -> dict:
        pass

class NavigateTool(BaseTool):
    def execute(self, url: str) -> dict:
        # Navigate implementation

class ClickTool(BaseTool):
    def execute(self, selector: str) -> dict:
        # Click implementation
```

### Pattern: Template Method

```python
class BaseAgent:
    def run(self, task: str) -> dict:
        # Fixed algorithm structure
        messages = self._init_messages(task)
        for i in range(MAX_ITERATIONS):
            response = self._get_response(messages)
            if self._has_tool_calls(response):
                self._execute_tools(response, messages)
            else:
                return self._finalize(response, messages)
```

### Pattern: Adapter

```python
class BrowserSession:
    """Adapts async CDPClient to sync interface."""

    def navigate(self, url: str) -> dict:
        return self._run(self._client.navigate(url))
```

---

## Quick Reference

### Creating a New Tool

1. Extend `BaseTool`
2. Set `name` and `description` class attributes
3. Implement `get_parameters_schema()` returning JSON Schema
4. Implement `execute()` returning `{"success": bool, ...}`
5. Accept dependencies via `__init__`
6. Add logging with `get_logger()`

### Creating a New Agent

1. Extend `BaseAgent`
2. Set `name` and `system_prompt` class attributes
3. Accept dependencies in `__init__`
4. Create tool instances with dependencies
5. Call `super().__init__(llm, tools)`

### Creating a New Config

1. Create `@dataclass` with typed fields
2. Add `from_env()` classmethod
3. Validate required fields
4. Convert types from strings
5. Provide sensible defaults

### Adding New Environment Variables

1. Document in `.env.example`
2. Load in appropriate `from_env()` method
3. Provide default value
4. Add validation if needed
