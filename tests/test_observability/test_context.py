"""Tests for context propagation."""

import pytest
from src.observability.context import (
    ObservabilityContext,
    get_or_create_context,
    set_context,
    reset_context,
    ObservabilitySpan,
)


class TestObservabilityContext:
    """Tests for ObservabilityContext dataclass."""

    def test_create_root(self):
        """Test creating a root context."""
        ctx = ObservabilityContext.create_root()
        
        assert ctx.trace_id.startswith("trace_")
        assert ctx.span_id.startswith("span_")
        assert ctx.parent_span_id is None
        assert ctx.session_id.startswith("sess_")
        assert ctx.request_id.startswith("req_")
        assert ctx.component_stack == ["root"]

    def test_create_root_with_session_id(self):
        """Test creating root context with custom session ID."""
        ctx = ObservabilityContext.create_root(session_id="custom_session")
        
        assert ctx.session_id == "custom_session"

    def test_create_child(self):
        """Test creating a child context."""
        parent = ObservabilityContext.create_root()
        child = parent.create_child("my_component")
        
        # Child inherits trace_id and session info
        assert child.trace_id == parent.trace_id
        assert child.session_id == parent.session_id
        assert child.request_id == parent.request_id
        
        # Child has different span_id
        assert child.span_id != parent.span_id
        
        # Child's parent is the parent's span
        assert child.parent_span_id == parent.span_id
        
        # Component stack is extended
        assert child.component_stack == ["root", "my_component"]

    def test_triggered_by(self):
        """Test triggered_by property."""
        root = ObservabilityContext.create_root()
        assert root.triggered_by == "direct_call"
        
        child1 = root.create_child("component1")
        assert child1.triggered_by == "root"
        
        child2 = child1.create_child("component2")
        assert child2.triggered_by == "component1"

    def test_current_component(self):
        """Test current_component property."""
        root = ObservabilityContext.create_root()
        assert root.current_component == "root"
        
        child = root.create_child("my_tool")
        assert child.current_component == "my_tool"

    def test_to_dict(self):
        """Test serialization to dictionary."""
        ctx = ObservabilityContext.create_root()
        data = ctx.to_dict()
        
        assert "trace_id" in data
        assert "span_id" in data
        assert "parent_span_id" in data
        assert "session_id" in data
        assert "request_id" in data
        assert "triggered_by" in data
        assert "component_stack" in data
        assert "start_time" in data


class TestContextFunctions:
    """Tests for context management functions."""

    def test_get_or_create_creates_root(self):
        """Test that get_or_create_context creates a root if none exists."""
        # Reset context first
        from src.observability.context import _observability_context
        _observability_context.set(None)
        
        ctx = get_or_create_context("test_component")
        
        assert ctx is not None
        assert ctx.trace_id.startswith("trace_")
        assert ctx.component_stack == ["test_component"]

    def test_set_and_reset_context(self):
        """Test setting and resetting context."""
        original = ObservabilityContext.create_root()
        token = set_context(original)
        
        current = ObservabilityContext.get_current()
        assert current == original
        
        reset_context(token)


class TestObservabilitySpan:
    """Tests for ObservabilitySpan context manager."""

    def test_span_creates_child_context(self):
        """Test that span context manager creates child context."""
        parent = ObservabilityContext.create_root()
        set_context(parent)
        
        with ObservabilitySpan("test_span") as ctx:
            assert ctx.parent_span_id == parent.span_id
            assert ctx.trace_id == parent.trace_id
            assert "test_span" in ctx.component_stack

    def test_span_restores_context(self):
        """Test that span restores original context on exit."""
        parent = ObservabilityContext.create_root()
        token = set_context(parent)
        
        with ObservabilitySpan("test_span"):
            pass
        
        # After exiting, context should be restored
        current = ObservabilityContext.get_current()
        assert current.span_id == parent.span_id
        
        reset_context(token)

    def test_nested_spans(self):
        """Test nested span context managers."""
        root = ObservabilityContext.create_root()
        set_context(root)
        
        with ObservabilitySpan("level1") as ctx1:
            assert ctx1.triggered_by == "root"
            
            with ObservabilitySpan("level2") as ctx2:
                assert ctx2.triggered_by == "level1"
                assert ctx2.parent_span_id == ctx1.span_id
