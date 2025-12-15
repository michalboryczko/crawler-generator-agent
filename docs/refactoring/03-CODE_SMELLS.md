# Code-Level Smells and Improvements

## Overview

This document identifies code-level issues related to naming, typing, and readability.

## Type Annotation Issues

### 1. Missing Return Type Annotations

**Severity**: Medium
**Files affected**: Multiple

**Examples found**:
```python
# src/tools/plan_generator.py:663
def load_test_data(path):  # Missing: path: str, return type
    ...
```

**Action**: Add return type annotations to all public functions.

```python
# Before
def load_test_data(path):
    ...

# After
def load_test_data(path: str | Path) -> dict[str, Any]:
    ...
```

### 2. Overuse of `Any` Type

**Severity**: Medium
**Locations**:
- `src/tools/memory.py:31` - `def write(self, key: str, value: Any)`
- `src/tools/memory.py:120` - `def execute(self, key: str, value: Any)`
- `src/tools/base.py:16` - `def execute(self, **kwargs: Any)`
- `src/core/llm.py:169` - `**kwargs: Any`
- `src/core/llm.py:226` - `def _parse_response(self, response: Any)`

**Recommendation**:
- For `MemoryStore.write`: Consider `value: JSON` type alias
- For `BaseTool.execute`: This is intentional for flexibility, acceptable
- For `LLMClient._parse_response`: Use `ChatCompletion` type from OpenAI SDK

```python
# Create type aliases for common patterns
from typing import TypeAlias

JSON: TypeAlias = dict[str, "JSON"] | list["JSON"] | str | int | float | bool | None
```

### 3. Missing Parameter Type Hints in `__init__`

**Severity**: Low
**Locations**: Various tool classes

**Example**:
```python
# src/tools/extraction.py
def __init__(self, llm_client, memory_store: MemoryStore):
    # llm_client missing type annotation
```

**Action**: Add type hints:
```python
def __init__(self, llm_client: LLMClient, memory_store: MemoryStore):
```

---

## Naming Issues

### 1. Inconsistent Naming Conventions

**Issue**: Mix of naming styles for similar concepts.

**Examples**:
- `llm_client` vs `llm` for LLM client instances
- `browser_session` vs `session` for browser sessions
- `memory_store` vs `store` for memory stores

**Recommendation**: Standardize to shorter names when unambiguous:
- `llm` for LLMClient instances
- `session` for BrowserSession instances
- `store` for MemoryStore instances

### 2. Tool Name Verbosity

**Issue**: Some tool names are overly verbose.

**Examples**:
- `RunExtractionAgentTool` - "Tool" suffix is redundant
- `FetchAndStoreHTMLTool` - Could be `HTMLFetcher`
- `BatchExtractArticlesTool` - Could be `ArticleExtractor`

**Recommendation**: Remove "Tool" suffix, it's implied by the class hierarchy.

---

## Readability Issues

### 1. Long Methods

**Locations**:
- `src/agents/base.py:BaseAgent.run` - 50+ lines
- `src/tools/selector_sampling.py:ListingPagesGeneratorTool.execute` - Complex logic

**Recommendation**: Extract helper methods for distinct logical steps.

### 2. Magic Strings

**Issue**: Hardcoded strings for status, roles, etc.

**Examples**:
```python
# Throughout codebase
{"role": "assistant", ...}
{"role": "user", ...}
{"success": True, ...}
```

**Recommendation**: Use enums or constants:
```python
from enum import StrEnum

class Role(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"
```

### 3. Inline Type Casts and Ignores

**Location**: `src/core/llm.py:148`
```python
self.config = config  # type: ignore
```

**Recommendation**: Refactor to avoid type ignore, or document why it's necessary.

---

## Documentation Issues

### 1. Missing Module Docstrings

**Affected files**:
- `src/tools/__init__.py`
- `src/agents/__init__.py`
- `src/core/__init__.py`

**Action**: Add module-level docstrings explaining purpose and contents.

### 2. Inconsistent Docstring Style

**Issue**: Mix of Google style, NumPy style, and no docstrings.

**Recommendation**: Standardize on Google style (matches existing examples).

---

## Improvement Priority

### Priority 1: Quick Fixes (1-2 hours)
- [ ] Add missing return type annotations
- [ ] Add parameter types to `__init__` methods
- [ ] Add module docstrings

### Priority 2: Medium Effort (Half day)
- [ ] Replace `Any` with specific types where possible
- [ ] Standardize naming conventions
- [ ] Create type aliases for common patterns

### Priority 3: Larger Refactoring (1+ days)
- [ ] Extract long methods
- [ ] Introduce enums for magic strings
- [ ] Standardize docstring style

---

## Ruff Rules to Enable

These Ruff rules will automatically catch many of these issues:

```toml
[tool.ruff.lint]
select = [
    "E",      # pycodestyle errors
    "F",      # Pyflakes
    "I",      # isort
    "N",      # pep8-naming
    "W",      # pycodestyle warnings
    # Add these:
    "ANN",    # flake8-annotations (type hints)
    "D",      # pydocstyle (docstrings)
    "UP",     # pyupgrade (modern syntax)
    "RUF",    # Ruff-specific rules
]
```

See [04-STATIC_ANALYSIS.md](04-STATIC_ANALYSIS.md) for complete configuration.
