"""Tests for decorator-based instrumentation with OTel spans."""

import asyncio

import pytest

from src.observability import (
    ObservabilityConfig,
    initialize_observability,
    shutdown,
)
from src.observability.decorators import (
    traced_agent,
    traced_llm_client,
    traced_tool,
)
from src.observability.handlers import NullHandler


@pytest.fixture(autouse=True)
def setup_observability():
    """Setup observability for each test.

    Initializes tracer and handler with console disabled.
    """
    handler = NullHandler()
    config = ObservabilityConfig(
        console_enabled=False,
        otel_endpoint="localhost:4317",  # Won't actually connect with NullHandler
        otel_insecure=True,
    )
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
                "finish_reason": "stop",
            }

        result = chat([{"role": "user", "content": "Hi"}])
        assert result["content"] == "Hello!"
        assert result["tokens_input"] == 10


class TestNestedTracing:
    """Tests for nested context propagation with OTel spans."""

    def test_nested_tools_share_trace_id(self):
        """Test that nested tool calls share the same trace_id.

        With OTel native spans:
        - trace_id is inherited from parent span
        - span_id is unique per span
        - parent_span_id links to parent span
        """
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

        # Same trace_id (inherited from parent)
        assert outer_ctx.trace_id == inner_ctx.trace_id

        # Both have trace_id (OTel generates valid IDs)
        assert outer_ctx.trace_id != ""
        assert inner_ctx.trace_id != ""

        # Different span_ids (each span is unique)
        assert outer_ctx.span_id != inner_ctx.span_id

        # Both have span_id
        assert outer_ctx.span_id != ""
        assert inner_ctx.span_id != ""

        # Inner's parent is outer (OTel manages this)
        assert inner_ctx.parent_span_id == outer_ctx.span_id

    def test_new_agent_creates_new_trace(self):
        """Test that separate agent runs create separate traces."""
        trace_ids = []

        @traced_agent(name="test_agent")
        def run_agent():
            from src.observability.context import ObservabilityContext

            ctx = ObservabilityContext.get_current()
            trace_ids.append(ctx.trace_id)
            return {}

        run_agent()
        run_agent()

        assert len(trace_ids) == 2
        # Each run creates a new trace
        assert trace_ids[0] != trace_ids[1]

    def test_agent_with_tool_calls(self):
        """Test agent calling tools creates proper hierarchy."""
        spans = []

        @traced_tool(name="tool_a")
        def tool_a():
            from src.observability.context import ObservabilityContext

            ctx = ObservabilityContext.get_current()
            spans.append(
                {
                    "name": "tool_a",
                    "trace_id": ctx.trace_id,
                    "span_id": ctx.span_id,
                    "parent": ctx.parent_span_id,
                }
            )
            return {}

        @traced_tool(name="tool_b")
        def tool_b():
            from src.observability.context import ObservabilityContext

            ctx = ObservabilityContext.get_current()
            spans.append(
                {
                    "name": "tool_b",
                    "trace_id": ctx.trace_id,
                    "span_id": ctx.span_id,
                    "parent": ctx.parent_span_id,
                }
            )
            return {}

        @traced_agent(name="test_agent")
        def run_agent():
            from src.observability.context import ObservabilityContext

            ctx = ObservabilityContext.get_current()
            spans.append(
                {
                    "name": "agent",
                    "trace_id": ctx.trace_id,
                    "span_id": ctx.span_id,
                    "parent": ctx.parent_span_id,
                }
            )
            tool_a()
            tool_b()
            return {}

        run_agent()

        assert len(spans) == 3

        agent_span = spans[0]
        tool_a_span = spans[1]
        tool_b_span = spans[2]

        # All share same trace_id
        assert agent_span["trace_id"] == tool_a_span["trace_id"] == tool_b_span["trace_id"]

        # Tools are children of agent
        assert tool_a_span["parent"] == agent_span["span_id"]
        assert tool_b_span["parent"] == agent_span["span_id"]


class TestOTelSpanIds:
    """Tests for OTel-generated span IDs."""

    def test_span_id_is_16_hex_chars(self):
        """Test that span_id is 16 hex characters (64-bit)."""

        @traced_tool(name="test_tool")
        def test_tool():
            from src.observability.context import ObservabilityContext

            ctx = ObservabilityContext.get_current()
            return {"span_id": ctx.span_id}

        result = test_tool()
        span_id = result["span_id"]

        # OTel span_id is 64-bit = 16 hex chars
        assert len(span_id) == 16
        # Should be valid hex
        int(span_id, 16)

    def test_trace_id_is_32_hex_chars(self):
        """Test that trace_id is 32 hex characters (128-bit)."""

        @traced_tool(name="test_tool")
        def test_tool():
            from src.observability.context import ObservabilityContext

            ctx = ObservabilityContext.get_current()
            return {"trace_id": ctx.trace_id}

        result = test_tool()
        trace_id = result["trace_id"]

        # OTel trace_id is 128-bit = 32 hex chars
        assert len(trace_id) == 32
        # Should be valid hex
        int(trace_id, 16)


class TestBusinessMetadata:
    """Tests for business metadata preservation."""

    def test_session_id_preserved(self):
        """Test that session_id is preserved across nested calls."""
        session_ids = []

        @traced_tool(name="inner")
        def inner():
            from src.observability.context import ObservabilityContext

            ctx = ObservabilityContext.get_current()
            session_ids.append(ctx.session_id)
            return {}

        @traced_agent(name="outer")
        def outer():
            from src.observability.context import ObservabilityContext

            ctx = ObservabilityContext.get_current()
            session_ids.append(ctx.session_id)
            inner()
            return {}

        outer()

        assert len(session_ids) == 2
        # Session ID preserved across calls
        assert session_ids[0] == session_ids[1]
        # Has expected format
        assert session_ids[0].startswith("sess_")

    def test_triggered_by_tracking(self):
        """Test that triggered_by tracks parent component."""
        triggered_by_values = []

        @traced_tool(name="child_tool")
        def child_tool():
            from src.observability.context import ObservabilityContext

            ctx = ObservabilityContext.get_current()
            triggered_by_values.append(ctx.triggered_by)
            return {}

        @traced_agent(name="parent_agent")
        def parent_agent():
            from src.observability.context import ObservabilityContext

            ctx = ObservabilityContext.get_current()
            triggered_by_values.append(ctx.triggered_by)
            child_tool()
            return {}

        parent_agent()

        # Agent was triggered by root/direct_call
        # Tool was triggered by agent
        assert len(triggered_by_values) == 2
        assert triggered_by_values[1] == "parent_agent"
