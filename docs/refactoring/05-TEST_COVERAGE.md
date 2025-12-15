# Test Coverage Plan

## Current State

### Existing Tests
```
tests/
├── __init__.py
├── test_json_parser.py           # JSON parsing utilities
└── test_observability/
    ├── __init__.py
    ├── test_serializers.py       # Serialization utilities
    ├── test_decorators.py        # Instrumentation decorators
    └── test_context.py           # Observability context
```

### Coverage Gaps
- No tests for agents
- No tests for tools
- No tests for LLM client
- No tests for configuration
- No tests for browser integration

## Testing Strategy

Given the project is in early development, focus on:
1. **Core utilities** - Functions used everywhere
2. **Public APIs** - Agent and tool interfaces
3. **Critical paths** - Main execution flow

Avoid over-testing:
- No tests for trivial getters/setters
- No tests for third-party library wrappers
- Minimal integration tests (expensive, slow)

---

## Priority Test Areas

### Priority 1: Core Utilities (Already Partially Done)

**`src/core/json_parser.py`** - Has tests, verify coverage

**`src/core/config.py`** - Configuration loading
```python
# tests/test_config.py
def test_output_config_from_env(monkeypatch):
    monkeypatch.setenv("OUTPUT_DIR", "/tmp/test")
    config = OutputConfig.from_env()
    assert config.base_output_dir == Path("/tmp/test")

def test_output_config_defaults():
    config = OutputConfig()
    assert config.base_output_dir == Path("./output")
```

### Priority 2: LLM Client

**`src/core/llm.py`** - Mock OpenAI responses
```python
# tests/test_llm.py
from unittest.mock import MagicMock, patch

def test_llm_client_chat():
    """Test basic chat completion."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "Hello"
    mock_response.choices[0].message.tool_calls = None
    mock_response.choices[0].finish_reason = "stop"
    mock_response.usage.prompt_tokens = 10
    mock_response.usage.completion_tokens = 5
    mock_response.usage.total_tokens = 15

    with patch("openai.OpenAI") as mock_openai:
        mock_openai.return_value.chat.completions.create.return_value = mock_response
        config = OpenAIConfig(api_key="test", model="gpt-4")
        client = LLMClient(config)
        result = client.chat([{"role": "user", "content": "Hi"}])

    assert result["content"] == "Hello"
    assert result["tool_calls"] is None

def test_llm_client_with_tools():
    """Test chat with tool calls."""
    # Test tool call parsing
    ...

def test_llm_client_factory():
    """Test multi-model factory."""
    ...
```

### Priority 3: Base Classes

**`src/agents/base.py`** - Agent execution loop
```python
# tests/test_agents/test_base.py
from unittest.mock import MagicMock

def test_base_agent_run_simple():
    """Test agent completes without tools."""
    mock_llm = MagicMock()
    mock_llm.chat.return_value = {
        "content": "Done",
        "tool_calls": None,
        "finish_reason": "stop"
    }

    agent = BaseAgent(llm=mock_llm)
    result = agent.run("Simple task")

    assert result["success"] is True
    assert result["result"] == "Done"

def test_base_agent_run_with_tool():
    """Test agent executes tool and continues."""
    ...

def test_base_agent_max_iterations():
    """Test agent stops at max iterations."""
    ...
```

**`src/tools/base.py`** - Tool interface
```python
# tests/test_tools/test_base.py
def test_tool_to_openai_schema():
    """Test OpenAI function schema generation."""
    class TestTool(BaseTool):
        name = "test_tool"
        description = "A test tool"

        def execute(self, param: str) -> dict:
            return {"success": True, "result": param}

        def get_parameters_schema(self) -> dict:
            return {
                "type": "object",
                "properties": {"param": {"type": "string"}},
                "required": ["param"]
            }

    tool = TestTool()
    schema = tool.to_openai_schema()

    assert schema["type"] == "function"
    assert schema["function"]["name"] == "test_tool"
```

### Priority 4: Key Tools

**`src/tools/memory.py`** - Memory operations
```python
# tests/test_tools/test_memory.py
def test_memory_write_and_read():
    """Test basic memory operations."""
    store = MemoryStore()
    store.write("key", {"data": "value"})
    assert store.read("key") == {"data": "value"}

def test_memory_tool_execute():
    """Test memory tool wrapper."""
    store = MemoryStore()
    tool = WriteMemoryTool(store)
    result = tool.execute(key="test", value="data")
    assert result["success"] is True
```

---

## Test Structure

```
tests/
├── __init__.py
├── conftest.py                   # Shared fixtures
├── test_json_parser.py           # (existing)
├── test_config.py                # NEW
├── test_llm.py                   # NEW
├── test_agents/
│   ├── __init__.py
│   ├── test_base.py              # NEW
│   └── conftest.py               # Agent fixtures
├── test_tools/
│   ├── __init__.py
│   ├── test_base.py              # NEW
│   ├── test_memory.py            # NEW
│   └── conftest.py               # Tool fixtures
└── test_observability/           # (existing)
    ├── __init__.py
    ├── test_serializers.py
    ├── test_decorators.py
    └── test_context.py
```

---

## Shared Fixtures

Create `tests/conftest.py`:

```python
import pytest
from unittest.mock import MagicMock

@pytest.fixture
def mock_llm():
    """Mock LLM client that returns simple responses."""
    llm = MagicMock()
    llm.chat.return_value = {
        "content": "Mock response",
        "tool_calls": None,
        "finish_reason": "stop",
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
    }
    return llm

@pytest.fixture
def mock_llm_with_tools():
    """Mock LLM client that returns tool calls."""
    llm = MagicMock()
    # First call returns tool call, second returns final response
    llm.chat.side_effect = [
        {
            "content": None,
            "tool_calls": [{"id": "1", "name": "test_tool", "arguments": {"param": "value"}}],
            "finish_reason": "tool_calls"
        },
        {
            "content": "Done with tools",
            "tool_calls": None,
            "finish_reason": "stop"
        }
    ]
    return llm

@pytest.fixture
def memory_store():
    """Fresh memory store for each test."""
    # Note: This requires removing the singleton pattern
    from src.tools.memory import MemoryStore
    store = MemoryStore.__new__(MemoryStore)
    store._data = {}
    return store
```

---

## Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_llm.py

# Run with verbose output
pytest -v

# Run only fast tests (exclude integration)
pytest -m "not integration"
```

---

## Coverage Goals

| Module | Current | Target | Priority |
|--------|---------|--------|----------|
| `src/core/json_parser.py` | ~80%+ | 90% | Done |
| `src/core/config.py` | 0% | 70% | High |
| `src/core/llm.py` | 0% | 60% | High |
| `src/agents/base.py` | 0% | 70% | High |
| `src/tools/base.py` | 0% | 80% | Medium |
| `src/tools/memory.py` | 0% | 70% | Medium |
| `src/observability/*` | ~60%+ | 70% | Done |

**Total target: 50-60% coverage on core modules**

This is intentionally modest for early development. Increase as the codebase stabilizes.

---

## What NOT to Test

1. **Third-party wrappers** - OpenAI client calls (mock them)
2. **Browser automation** - Requires real browser (integration test only)
3. **LLM outputs** - Non-deterministic (test parsing, not generation)
4. **File I/O** - Use tmp_path fixtures, don't test OS operations
5. **Simple data classes** - `@dataclass` fields don't need tests
