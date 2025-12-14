"""Tests for decorator-based instrumentation."""

import pytest
import asyncio
from unittest.mock import patch, MagicMock
import json
from pathlib import Path
from tempfile import TemporaryDirectory

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
from src.observability.outputs import NullOutput


class TestTracedTool:
    """Tests for @traced_tool decorator."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup for each test."""
        config = ObservabilityConfig(
            console_enabled=False,
            jsonl_enabled=False,
        )
        initialize_observability(config)
        yield
        shutdown()

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

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup for each test."""
        config = ObservabilityConfig(
            console_enabled=False,
            jsonl_enabled=False,
        )
        initialize_observability(config)
        yield
        shutdown()

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

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup for each test."""
        config = ObservabilityConfig(
            console_enabled=False,
            jsonl_enabled=False,
        )
        initialize_observability(config)
        yield
        shutdown()

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


class TestLogOutput:
    """Tests for log output integration."""

    def test_jsonl_output_captures_logs(self):
        """Test that JSONL output captures all log events."""
        with TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.jsonl"
            
            config = ObservabilityConfig(
                console_enabled=False,
                jsonl_enabled=True,
                jsonl_path=log_file,
            )
            initialize_observability(config)
            
            @traced_tool(name="logged_tool")
            def my_tool(x: int) -> dict:
                return {"result": x}
            
            my_tool(42)
            
            # Flush and read logs
            from src.observability.config import get_outputs
            for output in get_outputs():
                output.flush()
            
            # Read the log file
            with open(log_file, 'r') as f:
                all_entries = [json.loads(line) for line in f]

            # Filter for log records (not trace events)
            logs = [e for e in all_entries if "event" in e]

            # Should have input and output logs
            assert len(logs) >= 2

            events = [log["event"] for log in logs]
            assert "tool.input" in events
            assert "tool.output" in events
            
            shutdown()

    def test_error_logs_include_stack_trace(self):
        """Test that error logs include stack trace."""
        with TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test_error.jsonl"
            
            config = ObservabilityConfig(
                console_enabled=False,
                jsonl_enabled=True,
                jsonl_path=log_file,
            )
            initialize_observability(config)
            
            @traced_tool(name="error_tool")
            def error_tool():
                raise RuntimeError("Something went wrong")
            
            with pytest.raises(RuntimeError):
                error_tool()
            
            # Flush and read logs
            from src.observability.config import get_outputs
            for output in get_outputs():
                output.flush()
            
            with open(log_file, 'r') as f:
                all_entries = [json.loads(line) for line in f]

            # Filter for log records (not trace events)
            logs = [e for e in all_entries if "event" in e]

            # Find error log
            error_log = next(l for l in logs if l["event"] == "tool.error")
            
            assert error_log["level"] == "ERROR"
            assert error_log["data"]["error_type"] == "RuntimeError"
            assert "Something went wrong" in error_log["data"]["error_message"]
            assert "stack_trace" in error_log["data"]
            assert "RuntimeError" in error_log["data"]["stack_trace"]
            
            shutdown()


class TestNestedTracing:
    """Tests for nested context propagation."""

    def test_nested_tools_share_trace_id(self):
        """Test that nested tool calls share the same trace_id."""
        captured_contexts = []
        
        config = ObservabilityConfig(
            console_enabled=False,
            jsonl_enabled=False,
        )
        initialize_observability(config)
        
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
        
        shutdown()
