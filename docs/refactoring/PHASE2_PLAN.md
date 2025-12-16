# Phase 2 Refactoring Plan: Prompt Provider & Memory Architecture

## Executive Summary

This plan addresses three major architectural improvements:
1. **Prompt Provider System** - Centralize all prompts (static and dynamic) into a single provider
2. **Memory Isolation** - Replace shared memory with agent-specific stores and explicit data passing
3. **Optional MySQL Backend** - Add persistence layer with ORM for production use

---

## Part 1: Prompt Provider System

### Current State Analysis

Prompts are scattered across multiple locations:

| Location | Type | Content |
|----------|------|---------|
| `src/agents/prompts.py` | Static | 5 agent system prompts (MAIN_AGENT_PROMPT, etc.) |
| `src/tools/selector_extraction.py` | Static | LISTING_EXTRACTION_PROMPT, ARTICLE_EXTRACTION_PROMPT |
| `src/tools/selector_sampling.py` | Dynamic | f-string prompts for pagination/URL analysis |
| `src/tools/extraction.py` | Dynamic | f-string prompts for HTML extraction |

### Problems
1. No single source of truth for prompts
2. Hard to audit/modify prompts across the system
3. Dynamic prompts mixed with business logic
4. No versioning or A/B testing capability
5. Difficult to add prompt optimization later

### Proposed Architecture

```
src/
  prompts/
    __init__.py           # PromptProvider class
    registry.py           # PromptRegistry with all prompt definitions
    templates/
      agents.py           # Agent system prompts
      extraction.py       # Extraction prompts (static + templates)
      selectors.py        # Selector analysis prompts
```

### PromptProvider Interface

```python
class PromptProvider:
    """Centralized prompt management."""

    # Static prompts
    def get_agent_prompt(self, agent_name: str) -> str
    def get_extraction_prompt(self, extraction_type: str) -> str

    # Dynamic prompts (template + context)
    def render_prompt(self, template_name: str, **context) -> str

    # Metadata
    def list_prompts(self) -> list[PromptInfo]
    def get_prompt_version(self, name: str) -> str
```

### Implementation Tasks
1. Create `src/prompts/` package structure
2. Create `PromptRegistry` with all static prompts
3. Create `PromptTemplate` class for dynamic prompts with Jinja2
4. Migrate agent prompts from `prompts.py`
5. Migrate extraction prompts from `selector_extraction.py`
6. Migrate dynamic prompts from `selector_sampling.py` and `extraction.py`
7. Update all consumers to use PromptProvider
8. Add unit tests for prompt rendering
9. Delete old prompt definitions

---

## Part 2: Memory Architecture Refactoring

### Current State Analysis

```
MainAgent
    └── shared MemoryStore ──┬── BrowserAgent
                             ├── SelectorAgent
                             ├── AccessibilityAgent
                             └── DataPrepAgent
```

All agents read/write to the same memory instance with implicit key conventions:
- `target_url`, `article_selector`, `pagination_selector`, etc.

### Problems
1. **Tight coupling**: Agents depend on implicit key names
2. **No clear data flow**: Hard to trace what data flows where
3. **Testing difficulty**: Must set up full memory state for tests
4. **No persistence**: Data lost on restart
5. **Race conditions**: Potential issues in async scenarios

### Proposed Architecture

```
MainAgent
    ├── own MemoryStore (orchestration data)
    │
    ├── BrowserAgent ──── own MemoryStore ──────┐
    │                                           │
    ├── SelectorAgent ─── own MemoryStore ──────┤ Explicit data passing
    │                                           │ via AgentResult
    ├── AccessibilityAgent ── own MemoryStore ──┤
    │                                           │
    └── DataPrepAgent ─── own MemoryStore ──────┘
```

### AgentResult Pattern

```python
@dataclass
class AgentResult:
    """Result from agent execution with explicit outputs."""
    success: bool
    data: dict[str, Any]  # Structured output
    memory_snapshot: dict[str, Any] | None = None  # Optional internal state
    errors: list[str] = field(default_factory=list)

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)
```

### Data Flow Examples

**Before (implicit):**
```python
# BrowserAgent writes to shared memory
self.memory_store.write("article_links", links)

# SelectorAgent reads from shared memory (implicit dependency)
links = self.memory_store.read("article_links")
```

**After (explicit):**
```python
# BrowserAgent returns structured result
return AgentResult(success=True, data={"article_links": links, "pagination_type": "numbered"})

# MainAgent passes data explicitly
browser_result = self.browser_agent.run(task)
selector_result = self.selector_agent.run(
    task,
    context={"article_links": browser_result.get("article_links")}
)
```

### Implementation Tasks
1. Create `AgentResult` dataclass
2. Update `BaseAgent.run()` to return `AgentResult`
3. Add `context` parameter to agent run methods
4. Create `MemoryStore.create_isolated()` factory method
5. Update MainAgent to create isolated stores per agent
6. Update orchestration tools to pass data explicitly
7. Refactor BrowserAgent for isolated memory
8. Refactor SelectorAgent for isolated memory
9. Refactor AccessibilityAgent for isolated memory
10. Refactor DataPrepAgent for isolated memory
11. Add integration tests for data flow
12. Update documentation

---

## Part 3: Optional MySQL Backend

### Architecture

```
MemoryStore (abstract interface)
    ├── InMemoryStore (current, default)
    └── MySQLStore (new, optional)
```

### Docker Setup

```yaml
# docker-compose.yml
services:
  mysql:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: root
      MYSQL_DATABASE: crawler
    ports:
      - "3306:3306"
```

### ORM Schema

```python
# Using SQLAlchemy
class MemoryEntry(Base):
    __tablename__ = "memory_entries"

    id = Column(Integer, primary_key=True)
    session_id = Column(String(64), index=True)  # For isolation
    agent_name = Column(String(64), index=True)
    key = Column(String(256), index=True)
    value = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('session_id', 'agent_name', 'key'),
    )
```

### Implementation Tasks
1. Add SQLAlchemy and mysql-connector to dependencies
2. Create `docker-compose.yml` with MySQL service
3. Create `src/storage/` package
4. Define `MemoryBackend` abstract interface
5. Implement `InMemoryBackend` (refactor from MemoryStore)
6. Implement `MySQLBackend` with SQLAlchemy
7. Add factory function for backend selection
8. Update configuration to support backend choice
9. Add migration scripts
10. Add integration tests for MySQL backend

---

## Dependency Order

```
Phase 2.1: Prompt Provider (independent)
    └── Can be done first, minimal dependencies

Phase 2.2: Memory Architecture (depends on 2.1 completion for clean integration)
    ├── AgentResult pattern
    ├── Isolated memory stores
    └── Explicit data passing

Phase 2.3: MySQL Backend (depends on 2.2)
    └── Builds on new memory abstraction
```

---

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| Breaking existing functionality | Comprehensive test coverage, incremental changes |
| Performance regression with MySQL | Keep in-memory as default, MySQL opt-in |
| Complex migration | Clear deprecation path, adapter pattern |
| Prompt compatibility | Version prompts, regression tests |

---

## Success Criteria

1. All prompts accessible via single PromptProvider
2. No shared memory between agents
3. Clear data flow visible in code
4. MySQL backend working in Docker
5. All existing tests passing
6. Coverage maintained above 48%
7. No performance regression for in-memory mode
