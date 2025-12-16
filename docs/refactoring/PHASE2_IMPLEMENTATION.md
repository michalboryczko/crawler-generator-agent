# Phase 2 Implementation Summary

This document describes the refactoring work completed in Phase 2, covering the new prompt provider system, memory architecture, and optional MySQL backend.

## Architecture Overview

### Memory Architecture

The new memory architecture follows a microservices pattern with isolated memory stores per agent and explicit data flow:

```
┌─────────────────────────────────────────────────────────────────┐
│                       MainAgent                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              Orchestrator Memory (optional)              │   │
│  │     Stores shared data via store_keys parameter          │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                   │
│     ┌────────────────────────┼────────────────────────┐        │
│     │                        │                        │        │
│     ▼                        ▼                        ▼        │
│ ┌─────────┐           ┌─────────┐            ┌─────────┐       │
│ │ Browser │           │Selector │            │ Access. │       │
│ │ Agent   │──context──│ Agent   │──context───│ Agent   │       │
│ └────┬────┘           └────┬────┘            └────┬────┘       │
│      │                     │                      │             │
│ ┌────┴────┐           ┌────┴────┐            ┌────┴────┐       │
│ │Isolated │           │Isolated │            │Isolated │       │
│ │ Memory  │           │ Memory  │            │ Memory  │       │
│ └─────────┘           └─────────┘            └─────────┘       │
└─────────────────────────────────────────────────────────────────┘
```

Key principles:
1. **Isolation**: Each agent has its own MemoryStore instance
2. **Explicit data flow**: Data passes via AgentResult.data and context parameters
3. **Optional sharing**: Orchestration tools can store specific keys in shared memory

### Prompt Provider System

```
┌─────────────────────────────────────────────────────────────┐
│                    PromptProvider                            │
│  ┌─────────────────────────┐  ┌──────────────────────────┐ │
│  │    PromptRegistry       │  │   Dynamic Templates      │ │
│  │                         │  │                          │ │
│  │  agent.main             │  │  pagination_pattern      │ │
│  │  agent.browser          │  │  article_extraction      │ │
│  │  agent.selector         │  │  listing_url_extraction  │ │
│  │  agent.accessibility    │  │  article_url_pattern     │ │
│  │  agent.data_prep        │  │  selector_aggregation    │ │
│  │  extraction.listing     │  │                          │ │
│  │  extraction.article     │  │  PromptTemplate          │ │
│  │                         │  │  (Jinja2-based)          │ │
│  └─────────────────────────┘  └──────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## Migration Guide

### From Old Prompts Import

**Before (deprecated):**
```python
from src.agents.prompts import MAIN_AGENT_PROMPT

class MyAgent(BaseAgent):
    system_prompt = MAIN_AGENT_PROMPT
```

**After (recommended):**
```python
from src.prompts import get_prompt_provider

class MyAgent(BaseAgent):
    system_prompt = get_prompt_provider().get_agent_prompt("main")
```

### Using Dynamic Templates

```python
from src.prompts import get_prompt_provider

provider = get_prompt_provider()

# Render pagination pattern analysis
prompt = provider.render_prompt(
    "pagination_pattern",
    target_url="http://example.com",
    pagination_links=["http://example.com?page=1", "http://example.com?page=2"]
)

# Render article extraction
prompt = provider.render_prompt(
    "article_extraction",
    json_example='{"title": "", "content": ""}',
    selector_hints="h1.title, div.content"
)
```

### Using Orchestration Tools with Memory

```python
from src.tools.memory import MemoryStore
from src.tools.orchestration import RunBrowserAgentTool

# Create shared orchestrator memory
shared_memory = MemoryStore.create_isolated("orchestrator")

# Create tool that stores specific results
tool = RunBrowserAgentTool(
    browser_agent,
    orchestrator_memory=shared_memory,
    store_keys=["pagination_type", "extracted_count"]
)

# Execute - results stored in shared_memory
result = tool.execute(task="Analyze page")

# Access shared data
pagination = shared_memory.read("pagination_type")
```

## API Reference

### PromptProvider

```python
class PromptProvider:
    def get_agent_prompt(self, agent_name: str) -> str:
        """Get system prompt for an agent."""

    def get_extraction_prompt(self, extraction_type: str) -> str:
        """Get extraction prompt ('listing' or 'article')."""

    def get_prompt(self, name: str) -> str:
        """Get any prompt by full name."""

    def render_prompt(self, template_name: str, **context) -> str:
        """Render a dynamic template with context."""

    def register_template(self, name: str, template: PromptTemplate) -> None:
        """Register a new dynamic template."""

    def list_prompts(self, category: str | None = None) -> list[PromptInfo]:
        """List all registered prompts."""

    def list_templates(self) -> list[str]:
        """List registered template names."""
```

### AgentResult

```python
@dataclass
class AgentResult:
    success: bool
    data: dict[str, Any]
    errors: list[str]
    iterations: int

    @classmethod
    def ok(cls, **data) -> "AgentResult":
        """Create a successful result."""

    @classmethod
    def failure(cls, error: str) -> "AgentResult":
        """Create a failed result."""

    def get(self, key: str, default=None) -> Any:
        """Get data value by key."""

    def has(self, key: str) -> bool:
        """Check if data has key."""

    def add_error(self, error: str) -> None:
        """Add an error to the result."""
```

### MemoryStore

```python
class MemoryStore:
    @classmethod
    def create_isolated(cls, name: str) -> "MemoryStore":
        """Create an isolated memory store with unique name."""

    def read(self, key: str) -> Any | None:
        """Read value by key."""

    def write(self, key: str, value: Any) -> None:
        """Write value to key."""

    def delete(self, key: str) -> bool:
        """Delete key."""

    def list_keys(self) -> list[str]:
        """List all keys."""

    def search(self, pattern: str) -> list[str]:
        """Search keys by glob pattern."""
```

## Storage Backend Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `STORAGE_BACKEND` | `memory` | Backend type: `memory` or `mysql` |
| `MYSQL_HOST` | `localhost` | MySQL server host |
| `MYSQL_PORT` | `3306` | MySQL server port |
| `MYSQL_DATABASE` | `crawler` | Database name |
| `MYSQL_USER` | `crawler` | Database user |
| `MYSQL_PASSWORD` | `` | Database password |

### Using MySQL Backend

1. Start MySQL with Docker:
```bash
docker-compose up -d mysql
```

2. Set environment variables:
```bash
export STORAGE_BACKEND=mysql
export MYSQL_HOST=localhost
export MYSQL_PASSWORD=crawler_password
```

3. Initialize database (automatic on first run)

### Programmatic Configuration

```python
from src.core.config import StorageConfig
from src.storage import get_backend_from_config

# From environment
config = StorageConfig.from_env()

# Or explicit
config = StorageConfig(
    backend_type="mysql",
    mysql_host="db.example.com",
    mysql_password="secret"
)

backend = get_backend_from_config(config)
```

## Test Coverage

The refactoring maintains comprehensive test coverage:

- **360+ tests** covering all functionality
- **Unit tests** for PromptProvider, PromptRegistry, PromptTemplate
- **Integration tests** for memory isolation and data flow
- **Storage backend tests** for InMemoryBackend and MySQL

Run tests:
```bash
# All tests
uv run pytest

# Prompt provider tests
uv run pytest tests/test_prompts/ -v

# Integration tests
uv run pytest tests/test_integration/ -v

# Storage tests
uv run pytest tests/test_storage/ -v
```

## Files Changed

### New Files
- `src/prompts/` - Centralized prompt management
- `src/storage/` - Storage backend abstraction
- `tests/test_prompts/` - Prompt provider tests
- `tests/test_integration/` - Memory architecture tests
- `docker-compose.yml` - MySQL service
- `init.sql` - Database schema

### Modified Files
- `src/agents/*_agent.py` - Use PromptProvider
- `src/agents/prompts.py` - Deprecation wrapper
- `src/tools/orchestration.py` - Context and memory support
- `src/tools/memory.py` - Isolated store factory
- `src/core/config.py` - StorageConfig dataclass
