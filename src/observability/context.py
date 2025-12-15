"""Hybrid context for observability: OTel span + business metadata.

This module provides context propagation that:
1. Gets trace_id, span_id, parent_span_id from OTel span context
2. Manages business metadata (session_id, request_id, component_stack) separately

The ObservabilityContext wraps an OTel span and carries our business fields.
"""

import contextvars
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, List, Any

from opentelemetry import trace

from .tracer import format_trace_id, format_span_id


# Global context storage for business metadata
_observability_context: contextvars.ContextVar['ObservabilityContext'] = \
    contextvars.ContextVar('observability_context', default=None)


@dataclass
class ObservabilityContext:
    """Hybrid observability context: OTel span + business metadata.

    trace_id/span_id/parent_span_id come from OTel span context (via properties).
    Business fields (session_id, request_id, component_stack) are managed by us.

    Attributes:
        session_id: Session identifier (preserved across spans)
        request_id: Request identifier (preserved across spans)
        component_stack: Stack of component names for triggered_by tracking
        start_time: When this context was created
        _span: Reference to OTel span (for extracting IDs)
    """
    # Business metadata (WE manage these - not OTel)
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    component_stack: List[str] = field(default_factory=list)
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # OTel span reference (for extracting IDs) - not serialized
    _span: Optional[Any] = field(default=None, repr=False, compare=False)

    @property
    def trace_id(self) -> str:
        """Get trace_id from OTel span context.

        Returns:
            32-character hex string or empty string if no valid span
        """
        span = self._span or trace.get_current_span()
        ctx = span.get_span_context()
        if ctx.is_valid:
            return format_trace_id(ctx.trace_id)
        return ""

    @property
    def span_id(self) -> str:
        """Get span_id from OTel span context.

        Returns:
            16-character hex string or empty string if no valid span
        """
        span = self._span or trace.get_current_span()
        ctx = span.get_span_context()
        if ctx.is_valid:
            return format_span_id(ctx.span_id)
        return ""

    @property
    def parent_span_id(self) -> Optional[str]:
        """Get parent span ID from OTel span.

        Note: OTel manages parent-child relationships internally.
        We extract it if available, but it may be None.

        Returns:
            16-character hex string or None if no parent
        """
        span = self._span or trace.get_current_span()
        # OTel SDK spans have a parent attribute with the parent SpanContext
        if hasattr(span, 'parent') and span.parent is not None:
            parent_ctx = span.parent
            if hasattr(parent_ctx, 'span_id') and parent_ctx.span_id:
                return format_span_id(parent_ctx.span_id)
        return None

    @property
    def triggered_by(self) -> str:
        """Get the name of the parent component.

        Returns:
            Name of the component that triggered this one, or 'direct_call'.
        """
        if len(self.component_stack) > 1:
            return self.component_stack[-2]
        return "direct_call"

    @property
    def current_component(self) -> str:
        """Get the name of the current component.

        Returns:
            Name of the current component, or 'unknown'.
        """
        if self.component_stack:
            return self.component_stack[-1]
        return "unknown"

    @classmethod
    def get_current(cls) -> Optional['ObservabilityContext']:
        """Get current context from contextvars.

        Returns:
            Current ObservabilityContext or None if not set.
        """
        return _observability_context.get()

    @classmethod
    def create_root(cls, session_id: str = None) -> 'ObservabilityContext':
        """Create a new root context (no parent span yet).

        This creates the business metadata. OTel span will be attached
        when a traced decorator runs.

        Args:
            session_id: Optional session identifier. Generated if not provided.

        Returns:
            New root ObservabilityContext with business metadata.
        """
        return cls(
            session_id=session_id or f"sess_{uuid.uuid4().hex[:12]}",
            request_id=f"req_{uuid.uuid4().hex[:12]}",
            component_stack=["root"],
            _span=None  # Will be set when entering a traced decorator
        )

    def create_child(self, component_name: str, span: Any = None) -> 'ObservabilityContext':
        """Create a child context with inherited business metadata.

        The child inherits session_id, request_id and extends component_stack.
        trace_id/span_id come from the OTel span (passed or current).

        Args:
            component_name: Name of the component creating this child.
            span: OTel span to attach (uses current span if None)

        Returns:
            New child ObservabilityContext.
        """
        return ObservabilityContext(
            session_id=self.session_id,
            request_id=self.request_id,
            component_stack=[*self.component_stack, component_name],
            _span=span or trace.get_current_span()
        )

    def with_span(self, span: Any) -> 'ObservabilityContext':
        """Create a new context with a different OTel span attached.

        Preserves all business metadata but changes the span reference.

        Args:
            span: OTel span to attach

        Returns:
            New ObservabilityContext with updated span
        """
        return ObservabilityContext(
            session_id=self.session_id,
            request_id=self.request_id,
            component_stack=self.component_stack.copy(),
            start_time=self.start_time,
            _span=span
        )

    def to_dict(self) -> dict:
        """Convert context to dictionary for serialization.

        Returns:
            Dictionary representation of the context.
        """
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "session_id": self.session_id,
            "request_id": self.request_id,
            "triggered_by": self.triggered_by,
            "component_stack": self.component_stack,
            "start_time": self.start_time.isoformat()
        }


def get_or_create_context(component_name: str = "unknown") -> 'ObservabilityContext':
    """Get current context or create root if none exists.

    Args:
        component_name: Name of the component requesting context.

    Returns:
        Current context or newly created root context.
    """
    ctx = _observability_context.get()
    if ctx is None:
        ctx = ObservabilityContext.create_root()
        ctx = ObservabilityContext(
            session_id=ctx.session_id,
            request_id=ctx.request_id,
            component_stack=[component_name],
            _span=trace.get_current_span()
        )
    return ctx


def set_context(ctx: ObservabilityContext) -> contextvars.Token:
    """Set the current observability context.

    Args:
        ctx: Context to set as current.

    Returns:
        Token for resetting context later.
    """
    return _observability_context.set(ctx)


def reset_context(token: contextvars.Token) -> None:
    """Reset context to previous state using token.

    Args:
        token: Token from previous set_context call.
    """
    _observability_context.reset(token)


class ObservabilitySpan:
    """Context manager for creating child spans with business metadata.

    This is a convenience wrapper that:
    1. Creates an OTel span via tracer
    2. Creates child ObservabilityContext with the span
    3. Restores previous context on exit

    Usage:
        with ObservabilitySpan("my_component") as ctx:
            # Code runs with child context
            # ctx has trace_id, span_id from OTel
            # ctx has session_id, request_id, component_stack from us
            pass
    """

    def __init__(self, component_name: str):
        """Initialize span context manager.

        Args:
            component_name: Name of the component for this span.
        """
        self.component_name = component_name
        self.token: Optional[contextvars.Token] = None
        self.context: Optional[ObservabilityContext] = None
        self._otel_span = None
        self._otel_token = None

    def __enter__(self) -> 'ObservabilityContext':
        """Enter the span context.

        Returns:
            The child context for this span.
        """
        from .tracer import get_tracer

        # Start OTel span
        tracer = get_tracer()
        self._otel_span = tracer.start_span(self.component_name)
        self._otel_token = trace.use_span(self._otel_span, end_on_exit=False)
        self._otel_token.__enter__()

        # Get or create parent context
        existing_ctx = _observability_context.get()

        if existing_ctx is None:
            # No existing context - create root with this component as first entry
            self.context = ObservabilityContext(
                session_id=f"sess_{uuid.uuid4().hex[:12]}",
                request_id=f"req_{uuid.uuid4().hex[:12]}",
                component_stack=[self.component_name],
                _span=self._otel_span
            )
        else:
            # Existing context - create child with inherited business metadata
            self.context = existing_ctx.create_child(self.component_name, self._otel_span)

        self.token = set_context(self.context)

        return self.context

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit the span context."""
        # End OTel span
        if self._otel_span is not None:
            if exc_type is not None:
                from opentelemetry.trace import Status, StatusCode
                self._otel_span.set_status(Status(StatusCode.ERROR, str(exc_val)))
                self._otel_span.record_exception(exc_val)
            self._otel_span.end()

        # Exit OTel context
        if self._otel_token is not None:
            self._otel_token.__exit__(exc_type, exc_val, exc_tb)

        # Restore previous observability context
        if self.token is not None:
            reset_context(self.token)

        return False  # Don't suppress exceptions
