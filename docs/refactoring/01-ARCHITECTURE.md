# Architecture Analysis and Improvements

## Current Architecture

```
src/
├── agents/           # Agent implementations
│   ├── base.py       # BaseAgent with thought→action→observation loop
│   ├── main_agent.py
│   ├── browser_agent.py
│   ├── selector_agent.py
│   ├── data_prep_agent.py
│   └── accessibility_agent.py
├── tools/            # Tool implementations
│   ├── base.py       # BaseTool abstract class
│   ├── browser.py    # Browser interaction tools
│   ├── selector*.py  # CSS selector tools
│   ├── extraction.py # Data extraction tools
│   ├── file.py       # File operations
│   ├── memory.py     # Memory/state management
│   ├── orchestration.py  # Agent orchestration tools
│   └── ...
├── core/             # Core infrastructure
│   ├── llm.py        # LLMClient and LLMClientFactory
│   ├── config.py     # Configuration classes
│   ├── browser.py    # Browser session management
│   ├── json_parser.py
│   ├── model_registry.py
│   └── ...
└── observability/    # Telemetry and logging
    ├── decorators.py # @traced_agent, @traced_tool, etc.
    ├── context.py    # ObservabilityContext
    └── ...
```

## Strengths

1. **Clear separation of concerns** - agents, tools, core, observability
2. **Good abstraction** - BaseAgent and BaseTool provide consistent interfaces
3. **Multi-model support** - LLMClientFactory enables different models per component
4. **Decorator-based observability** - Clean instrumentation approach

## Issues Identified

### Issue 1: Agent-Tool Coupling

**Problem**: Orchestration tools directly instantiate agents, creating tight coupling.

**Location**: `src/tools/orchestration.py`

```python
class RunBrowserAgentTool(BaseTool):
    def __init__(self, browser_agent):  # Direct dependency
        self.browser_agent = browser_agent
```

**Impact**:
- Hard to test tools in isolation
- Agent changes require tool changes

**Recommendation**: Consider a registry or factory pattern for agent instantiation.

### Issue 2: Inconsistent Configuration Pattern

**Problem**: Multiple `from_env` class methods across different config classes.

**Location**: `src/core/config.py`, `src/core/llm.py`

```python
# In config.py
class OutputConfig:
    @classmethod
    def from_env(cls) -> "OutputConfig": ...

class OpenAIConfig:
    @classmethod
    def from_env(cls) -> "OpenAIConfig": ...

class BrowserConfig:
    @classmethod
    def from_env(cls) -> "BrowserConfig": ...

class AppConfig:
    @classmethod
    def from_env(cls) -> "AppConfig": ...

# In llm.py
class LLMClientFactory:
    @classmethod
    def from_env(cls) -> "LLMClientFactory": ...
```

**Impact**:
- Code repetition
- Inconsistent error handling
- No centralized env validation

**Recommendation**: Create a base config mixin or use a configuration framework like Pydantic Settings.

### Issue 3: MemoryStore Singleton Anti-Pattern

**Problem**: MemoryStore uses singleton pattern which makes testing difficult.

**Location**: `src/tools/memory.py`

```python
class MemoryStore:
    _instance: "MemoryStore | None" = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._data = {}
        return cls._instance
```

**Impact**:
- State leaks between tests
- Hard to inject mock stores
- Global mutable state

**Recommendation**: Use dependency injection instead. Already documented in `docs/REFACTORING_PLAN.md`.

### Issue 4: Mixed Abstraction Levels in Tools

**Problem**: Some tools do too much (LLM calls + parsing + business logic).

**Location**: `src/tools/selector_extraction.py`, `src/tools/extraction.py`

**Example**: `RunExtractionAgentTool` handles:
- Prompt building
- LLM communication
- Response parsing
- Data transformation

**Recommendation**:
- Extract prompt building to separate module
- Use centralized JSON parsing (already exists in `core/json_parser.py`)
- Keep tools focused on orchestration

### Issue 5: No Error Hierarchy

**Problem**: Tools return `dict` with `success: bool` instead of typed results or exceptions.

**Current pattern**:
```python
return {"success": False, "error": str(e)}
```

**Impact**:
- Inconsistent error handling
- No typed error information
- Hard to distinguish error types

**Recommendation**:
```python
# Option 1: Custom exceptions
class ToolError(Exception):
    pass

class ToolNotFoundError(ToolError):
    pass

# Option 2: Result type
@dataclass
class ToolResult:
    success: bool
    data: Any = None
    error: str | None = None
    error_type: str | None = None
```

### Issue 6: Main Function Has Too Many Responsibilities

**Problem**: `main.py:main()` handles 6 different concerns in ~217 lines.

**Location**: `main.py`

**Current responsibilities**:
1. Argument parsing
2. Model listing
3. Logging setup
4. Observability initialization
5. LLM/Browser initialization
6. Agent execution

**Recommendation**: Extract into focused functions:
```python
def parse_arguments() -> argparse.Namespace: ...
def list_models() -> int: ...
def setup_logging(level: str) -> logging.Logger: ...
def setup_observability(config: AppConfig) -> tuple: ...
def create_llm(app_config, multi_model, ctx, logger) -> tuple: ...
def run_crawler_workflow(url, llm, app_config, ctx, logger) -> int: ...

def main() -> int:
    args = parse_arguments()
    if args.list_models:
        return list_models()
    logger = setup_logging(args.log_level)
    # ... etc
```

See `docs/REFACTORING_PLAN.md` section 3.4 for complete implementation.

### Issue 7: Long System Prompts Embedded in Agent Code

**Problem**: System prompts (60-120 lines each) embedded directly in agent classes.

**Locations**:
- `main_agent.py`: 67-line MAIN_AGENT_PROMPT
- `data_prep_agent.py`: 120-line DATA_PREP_AGENT_PROMPT
- `selector_agent.py`: 78-line SELECTOR_AGENT_PROMPT

**Impact**:
- Clutters agent implementation code
- Hard to iterate on prompts
- No prompt versioning

**Recommendation**: Extract prompts to dedicated module or files:

Option A - External files:
```
src/prompts/
├── __init__.py
├── main_agent.txt
├── browser_agent.txt
└── ...
```

Option B - Constants module:
```python
# src/agents/prompts.py
MAIN_AGENT_PROMPT = """You are the Main Orchestrator Agent..."""
BROWSER_AGENT_PROMPT = """You are a Browser Interaction Agent..."""
```

See `docs/REFACTORING_PLAN.md` section 3.5 for complete implementation.

## Recommended Architecture Improvements

### Priority 1: Centralize Configuration
- Create `src/core/settings.py` with Pydantic Settings
- Single source of truth for all env vars
- Built-in validation and type coercion

### Priority 2: Dependency Injection
- Remove MemoryStore singleton
- Pass dependencies through constructors
- Consider a simple DI container for complex apps

### Priority 3: Extract Prompts
- Move system prompts to `src/prompts/` directory
- Use template strings or files
- Enable prompt versioning

### Priority 4: Typed Results
- Introduce `ToolResult` dataclass
- Consistent error handling across tools
- Better IDE support and documentation

## Migration Strategy

These are architectural improvements that should be done incrementally:

1. Start with new code following new patterns
2. Refactor existing code module by module
3. Keep backward compatibility during transition
4. Add deprecation warnings where needed
