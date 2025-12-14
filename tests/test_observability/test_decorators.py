"""Tests for decorator-based instrumentation."""

import pytest
import asyncio

from src.observability import (
    initialize_observability,
    ObservabilityConfig,
    shutdown,
)
from src.observability.decorators import (
    traced_tool,
    traced_agent,
    traced_llm_client,
)
from src.observability.handlers import NullHandler


@pytest.fixture(autouse=True)
def setup_observability():
    """Setup observability for each test."""
    handler = NullHandler()
    config = ObservabilityConfig(console_enabled=False)
    initialize_observability(handler=handler, config=config)
    yield
    shutdown()


class TestTracedTool:
    """Tests for @traced_tool decorator."""

    def test_sync_function_returns_result(self):
        """Test that decorated sync function returns correct result."""
        @traced_tool(name="add_tool")
        def add(a: int, b: int) -> dict:
            return {"sum": a + b}

        result = add(1, 2)
        assert result == {"sum": 3}

    def test_sync_function_preserves_args(self):
        """Test that args are passed correctly."""
        received_args = {}

        @traced_tool(name="capture_tool")
        def capture(x, y, z="default"):
            received_args["x"] = x
            received_args["y"] = y
            received_args["z"] = z
            return {}

        capture(1, 2, z="custom")

        assert received_args["x"] == 1
        assert received_args["y"] == 2
        assert received_args["z"] == "custom"

    def test_error_is_reraised(self):
        """Test that exceptions are re-raised after logging."""
        @traced_tool(name="error_tool")
        def failing():
            raise ValueError("test error")

        with pytest.raises(ValueError, match="test error"):
            failing()

    def test_method_decorator(self):
        """Test decorator works on class methods."""
        class MyTool:
            @traced_tool(name="method_tool")
            def execute(self, value: int) -> dict:
                return {"result": value * 2}

        tool = MyTool()
        result = tool.execute(5)
        assert result == {"result": 10}


class TestTracedAgent:
    """Tests for @traced_agent decorator."""

    def test_sync_agent(self):
        """Test sync agent function."""
        @traced_agent(name="test_agent")
        def run_agent(task: str) -> dict:
            return {"success": True, "task": task}

        result = run_agent("do something")
        assert result == {"success": True, "task": "do something"}

    @pytest.mark.asyncio
    async def test_async_agent(self):
        """Test async agent function."""
        @traced_agent(name="async_agent")
        async def run_async_agent(task: str) -> dict:
            await asyncio.sleep(0.001)
            return {"success": True, "task": task}

        result = await run_async_agent("async task")
        assert result == {"success": True, "task": "async task"}


class TestTracedLLMClient:
    """Tests for @traced_llm_client decorator."""

    def test_llm_client_decorator(self):
        """Test LLM client decorator."""
        @traced_llm_client(provider="openai")
        def chat(messages: list, model: str = "gpt-4") -> dict:
            return {
                "content": "Hello!",
                "tokens_input": 10,
                "tokens_output": 5,
                "finish_reason": "stop"
            }

        result = chat([{"role": "user", "content": "Hi"}])
        assert result["content"] == "Hello!"
        assert result["tokens_input"] == 10


class TestNestedTracing:
    """Tests for nested context propagation."""

    def test_nested_tools_share_trace_id(self):
        """Test that nested tool calls share the same trace_id."""
        captured_contexts = []

        @traced_tool(name="inner_tool")
        def inner_tool():
            from src.observability.context import ObservabilityContext
            ctx = ObservabilityContext.get_current()
            captured_contexts.append(("inner", ctx))
            return {}

        @traced_tool(name="outer_tool")
        def outer_tool():
            from src.observability.context import ObservabilityContext
            ctx = ObservabilityContext.get_current()
            captured_contexts.append(("outer", ctx))
            return inner_tool()

        outer_tool()

        assert len(captured_contexts) == 2
        outer_ctx = captured_contexts[0][1]
        inner_ctx = captured_contexts[1][1]

        # Same trace_id
        assert outer_ctx.trace_id == inner_ctx.trace_id

        # Different span_ids
        assert outer_ctx.span_id != inner_ctx.span_id

        # Inner's parent is outer
        assert inner_ctx.parent_span_id == outer_ctx.span_id
