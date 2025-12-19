# Typing System Refactor

This document tracks mypy type checking issues that are currently disabled or suppressed. It serves as a starting point for a future refactor to achieve full type safety.

## Current Status

**Mypy is enabled and passing in CI.** The configuration uses relaxed settings to suppress known patterns that would require significant refactoring. See the disabled error codes and module overrides below.

## Current Mypy Configuration

```toml
[tool.mypy]
python_version = "3.11"
warn_return_any = false
warn_unused_ignores = true
ignore_missing_imports = true
disable_error_code = [
    "override",      # Allow flexible tool execute() signatures
    "attr-defined",  # Singleton pattern dynamic attributes
    "misc",          # Various edge cases (type declarations in __new__)
    "union-attr",    # JSON parsing returns dict | list, we handle it
    "arg-type",      # Flexible argument types in tools
    "return-value",  # Decorator return types, sorted() key functions
]
exclude = ["tests/", "infra/", ".venv/"]

[[tool.mypy.overrides]]
module = "src.models.*"
ignore_errors = true

[[tool.mypy.overrides]]
module = "src.repositories.*"
ignore_errors = true

[[tool.mypy.overrides]]
module = "src.services.session_service"
ignore_errors = true
```

---

## Disabled Error Codes

### 1. `override` - Tool Execute Signatures

**Why disabled:** The `BaseTool` class uses `Protocol` with a generic `execute(**kwargs)` signature, but concrete tools define specific parameters.

**Example:**
```python
# BaseTool (Protocol)
def execute(self, **kwargs: Any) -> dict[str, Any]: ...

# Concrete tool violates LSP
class NavigateTool(BaseTool):
    def execute(self, url: str) -> dict[str, Any]:  # Different signature
        ...
```

**Affected files:** All tools in `src/tools/`

**Fix approach:**
1. Option A: Make all tools use `**kwargs` and validate internally
2. Option B: Use `@overload` decorators for type hints
3. Option C: Create tool-specific protocols for each tool category
4. Option D: Use generic types with TypeVar for parameters

**Recommended:** Option C or D - Create a proper type hierarchy:
```python
class ToolParameters(TypedDict):
    pass

class NavigateParams(ToolParameters):
    url: str

class Tool(Protocol[P]):
    def execute(self, params: P) -> ToolResult: ...
```

---

### 2. `attr-defined` - Singleton Dynamic Attributes

**Why disabled:** Singleton pattern stores instance in class variable that's dynamically created.

**Example:**
```python
class ValidationRegistry:
    _instance: "ValidationRegistry | None" = None

    def __new__(cls, ttl: float = 3600.0):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._contexts = {}  # Dynamic attribute
        return cls._instance
```

**Affected files:**
- `src/contracts/validation_registry.py`
- `src/core/llm.py` (LLMClientFactory singleton)

**Fix approach:**
1. Declare all instance attributes in `__init__` or as class-level annotations
2. Use a proper singleton metaclass that preserves typing
3. Use module-level instance instead of class singleton

**Recommended:** Declare attributes as class-level `ClassVar` or in `__init__`:
```python
class ValidationRegistry:
    _instance: ClassVar["ValidationRegistry | None"] = None
    _contexts: dict[str, ValidationContext]
    _ttl: float
    _lock: threading.Lock

    def __init__(self, ttl: float = 3600.0):
        if not hasattr(self, '_initialized'):
            self._contexts = {}
            self._ttl = ttl
            self._lock = threading.Lock()
            self._initialized = True
```

---

### 3. `misc` - Type Declaration Edge Cases

**Why disabled:** Various edge cases including type declarations in `__new__` methods and complex generic expressions.

**Affected patterns:**
- Type declarations in singleton `__new__` methods
- Complex union types in generic contexts

**Fix approach:** Case-by-case refactoring, often related to singleton pattern fixes above.

---

### 4. `union-attr` - JSON Parsing Union Types

**Why disabled:** `json.loads()` returns `dict | list | str | int | float | bool | None`, and we access attributes assuming dict.

**Example:**
```python
data = json.loads(response)  # Could be dict or list
result = data["key"]  # Error: list has no __getitem__ with str
```

**Affected files:**
- `src/tools/validate_response.py`
- Various tools parsing JSON responses

**Fix approach:**
1. Add explicit type narrowing with `isinstance()` checks
2. Use TypedDict for known JSON structures
3. Create parsing utilities with proper type guards

**Recommended:**
```python
def parse_json_object(data: str) -> dict[str, Any]:
    parsed = json.loads(data)
    if not isinstance(parsed, dict):
        raise ValueError(f"Expected dict, got {type(parsed)}")
    return parsed
```

---

### 5. `arg-type` - Flexible Argument Types

**Why disabled:** Tools accept various argument types that are validated at runtime.

**Example:**
```python
def some_tool(data: dict[str, Any]) -> ...:
    ...

# Called with more specific type
some_tool({"specific": "data"})  # mypy may complain about literal types
```

**Fix approach:**
1. Use more precise TypedDict definitions
2. Add `@overload` for common call patterns
3. Use Protocol for structural typing of inputs

---

### 6. `return-value` - Decorator and Callback Types

**Why disabled:** Decorator return types and `sorted()` key functions have complex type signatures.

**Example:**
```python
@trace_tool
def my_function():  # Decorator changes return type
    ...

# sorted() key function
sorted(items, key=lambda x: x.get("priority", 0))  # Complex inference
```

**Fix approach:**
1. Use `ParamSpec` and `TypeVar` for decorator typing
2. Provide explicit type annotations for complex lambdas
3. Extract key functions to named functions with annotations

---

## Module Overrides (Full Ignore)

### `src.models.*` and `src.repositories.*`

**Why ignored:** SQLAlchemy ORM has complex type interactions.

**Issues:**
- `Column[str]` vs `str` type confusion
- Relationship types and lazy loading
- Query builder return types

**Example:**
```python
class Session(Base):
    session_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    # At runtime: str
    # At type-check time: Mapped[str] or Column[str]
```

**Fix approach:**
1. Use SQLAlchemy 2.0 style with `Mapped[]` annotations consistently
2. Use `sqlalchemy-stubs` or `sqlalchemy2-stubs` package
3. Create type stubs for repository interfaces

---

## Remaining Errors (Currently 0)

All mypy errors have been resolved. The following were fixed:

### Fixed: Assignment Type Mismatches

| File | Fix Applied |
|------|-------------|
| `browser.py` | Used `Any` type for websockets connection |
| `session_service.py` | Added module override for SQLAlchemy typing |
| `container.py` | Added explicit `AbstractMemoryRepository` type annotation |
| `handlers.py` | Used `Any` for OTel LoggerProvider, explicit dict type for attributes |
| `context.py` | Used `Any` for OTel span/token types |
| `config.py` | Added explicit `| None` for optional parameter |
| `llm.py` | Declared `model_config` type once, removed duplicate annotations |

### Fixed: Type Annotations Added

| File | Fix Applied |
|------|-------------|
| `selector_sampling.py` | Added `dict[str, list[str]]` annotation for `groups` |
| `selector_extraction.py` | Added `dict[str, list[str]]` annotation for `selector_variations` |
| `extraction.py` | Added `FieldValue` type alias and explicit dict typing |
| `agents/base.py` | Added `list[dict[str, Any]]` for messages, `Any` for llm_factory |

### Fixed: Logic/Validation Errors

| File | Fix Applied |
|------|-------------|
| `validate_response.py` | Added `isinstance(response_json, dict)` type guard |

---

## Refactor Priority

### Phase 1: Quick Wins
1. Add missing type annotations for `dict` variables
2. Remove unused `type: ignore` comments
3. Add explicit `| None` for optional parameters
4. Fix container to use proper interface type

### Phase 2: Infrastructure
1. Fix SQLAlchemy model typing with proper `Mapped[]` annotations
2. Create common repository interface/protocol
3. Fix observability module Optional types

### Phase 3: Tools Architecture
1. Design proper tool type hierarchy
2. Implement new tool protocol with typed parameters
3. Migrate all tools to new pattern
4. Remove `override` disable

### Phase 4: Full Type Safety
1. Enable all disabled error codes one by one
2. Add runtime type validation where needed
3. Create type stubs for any remaining issues
4. Enable strict mode

---

## Testing Type Changes

After each refactor phase:

```bash
# Run mypy
uv run mypy src/

# Run full test suite
uv run pytest

# Check for runtime regressions
uv run python main.py --help
```

---

## References

- [mypy documentation](https://mypy.readthedocs.io/)
- [PEP 544 - Protocols](https://peps.python.org/pep-0544/)
- [PEP 612 - ParamSpec](https://peps.python.org/pep-0612/)
- [SQLAlchemy 2.0 Type Stubs](https://docs.sqlalchemy.org/en/20/orm/extensions/mypy.html)
