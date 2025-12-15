# Code Duplication Analysis

## Overview

This document identifies code duplication opportunities in the codebase. Removing duplication improves maintainability and reduces bugs.

## Critical Duplications

### 1. JSON Response Parsing (4 occurrences)

**Severity**: High
**Lines saved**: ~100 lines
**Effort**: Low

**Problem**: The `_parse_json_response` method is duplicated identically in 4 tool classes.

**Locations**:
- `src/tools/selector_sampling.py:ListingPagesGeneratorTool._parse_json_response`
- `src/tools/selector_extraction.py:ListingPageExtractorTool._parse_json_response`
- `src/tools/selector_extraction.py:ArticlePageExtractorTool._parse_json_response`
- `src/tools/selector_extraction.py:SelectorAggregatorTool._parse_json_response`

**Existing Solution**: `src/core/json_parser.py` already has a robust `parse_json_response` function.

**Action**:
```python
# Before (duplicated in each class)
def _parse_json_response(self, content: str) -> dict | None:
    """Parse JSON from LLM response."""
    try:
        return json.loads(content.strip())
    except json.JSONDecodeError:
        pass
    # ... 26 lines of fallback logic

# After
from src.core.json_parser import parse_json_response

# Use directly in execute method:
result = parse_json_response(response["content"])
```

**Files to modify**:
1. `src/tools/selector_sampling.py` - Remove `_parse_json_response`, import from core
2. `src/tools/selector_extraction.py` - Remove 3 copies of `_parse_json_response`, import from core

---

### 2. Configuration from_env Pattern (5 occurrences)

**Severity**: Medium
**Lines saved**: ~50 lines
**Effort**: Medium

**Problem**: Each config class has its own `from_env` classmethod with similar structure.

**Locations**:
- `src/core/config.py:OutputConfig.from_env`
- `src/core/config.py:OpenAIConfig.from_env`
- `src/core/config.py:BrowserConfig.from_env`
- `src/core/config.py:AppConfig.from_env`
- `src/core/llm.py:LLMClientFactory.from_env`

**Action**:

Option A: Base mixin class
```python
class EnvConfigMixin:
    @classmethod
    def from_env(cls) -> Self:
        """Load config from environment variables."""
        # Use dataclass fields to determine env var names
        ...
```

Option B: Use Pydantic Settings (recommended for new projects)
```python
from pydantic_settings import BaseSettings

class OutputConfig(BaseSettings):
    base_output_dir: Path = Path("./output")

    class Config:
        env_prefix = "OUTPUT_"
```

---

### 3. Tool Orchestration Boilerplate (4 occurrences)

**Severity**: Medium
**Lines saved**: ~60 lines
**Effort**: Medium

**Problem**: Agent runner tools follow identical pattern.

**Locations**:
- `src/tools/orchestration.py:RunBrowserAgentTool`
- `src/tools/orchestration.py:RunSelectorAgentTool`
- `src/tools/orchestration.py:RunAccessibilityAgentTool`
- `src/tools/orchestration.py:RunDataPrepAgentTool`

**Current pattern**:
```python
class RunBrowserAgentTool(BaseTool):
    name = "run_browser_agent"
    description = "Run browser agent..."

    def __init__(self, browser_agent):
        self.agent = browser_agent

    def execute(self, task: str) -> dict[str, Any]:
        return self.agent.run(task)

    def get_parameters_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {"task": {...}}, "required": ["task"]}
```

**Action**: Factory function
```python
def create_agent_runner_tool(
    agent_name: str,
    agent: BaseAgent,
    description: str
) -> BaseTool:
    """Create a tool that runs an agent."""

    class AgentRunnerTool(BaseTool):
        name = f"run_{agent_name}_agent"
        description = description

        def execute(self, task: str) -> dict[str, Any]:
            return agent.run(task)

        def get_parameters_schema(self) -> dict[str, Any]:
            return {
                "type": "object",
                "properties": {"task": {"type": "string", "description": "Task to execute"}},
                "required": ["task"]
            }

    return AgentRunnerTool()
```

---

## Moderate Duplications

### 4. Browser Session Dependency

**Problem**: Many tools take `BrowserSession` in `__init__` with similar patterns.

**Locations**:
- `src/tools/browser.py` - 6 tool classes
- `src/tools/selector.py` - 4 tool classes
- `src/tools/extraction.py` - 2 tool classes

**Action**: Consider a `BrowserTool` base class
```python
class BrowserTool(BaseTool):
    """Base class for tools that need browser access."""

    def __init__(self, session: BrowserSession):
        self.session = session
```

### 5. Memory Store Dependency

**Problem**: Many tools take `MemoryStore` in `__init__`.

**Locations**:
- `src/tools/memory.py` - 5 tool classes
- `src/tools/plan_generator.py` - 2 tool classes
- `src/tools/extraction.py` - 4 tool classes

**Action**: Consider a `StatefulTool` base class
```python
class StatefulTool(BaseTool):
    """Base class for tools that need memory/state access."""

    def __init__(self, store: MemoryStore):
        self.store = store
```

---

## Summary

| Issue | Severity | Lines Saved | Priority |
|-------|----------|-------------|----------|
| JSON parsing duplication | High | ~100 | 1 |
| Config from_env pattern | Medium | ~50 | 3 |
| Orchestration boilerplate | Medium | ~60 | 4 |
| Browser session deps | Low | ~20 | 5 |
| Memory store deps | Low | ~20 | 5 |

## Implementation Order

1. **JSON parsing** - Immediate win, already has solution in `core/json_parser.py`
   - See `docs/REFACTORING_PLAN.md` Task 1 for exact code changes
2. **Orchestration tools** - Use factory pattern
   - See `docs/REFACTORING_PLAN.md` Task 3 for complete implementation
3. **Config pattern** - Part of larger architecture improvement
4. **Base classes** - Nice to have, lower priority

**Note**: The existing `docs/REFACTORING_PLAN.md` contains ready-to-implement code for items 1-2 above.
