"""Context propagation for observability.

This module provides automatic context propagation via Python's contextvars.
It maintains trace hierarchy and correlation IDs across nested function calls.
"""

import contextvars
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, List

# Global context storage - single source of truth
_observability_context: contextvars.ContextVar['ObservabilityContext'] = \
    contextvars.ContextVar('observability_context', default=None)


@dataclass
class ObservabilityContext:
    """Immutable observability context for correlation.
    
    Maintains trace hierarchy with proper parent-child span relationships.
    All fields are preserved through context propagation.
    
    Attributes:
        trace_id: Unique identifier for the entire trace (preserved across spans)
        span_id: Unique identifier for this specific span
        parent_span_id: Span ID of the parent (None for root)
        session_id: Session identifier (preserved at root)
        request_id: Request identifier (preserved at root)
        component_stack: Stack of component names for triggered_by tracking
        start_time: When this span was created
    """
    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    component_stack: List[str] = field(default_factory=list)
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def get_current(cls) -> Optional['ObservabilityContext']:
        """Get current context from contextvars.
        
        Returns:
            Current ObservabilityContext or None if not set.
        """
        return _observability_context.get()

    @classmethod
    def create_root(cls, session_id: str = None) -> 'ObservabilityContext':
        """Create a new root context (no parent).
        
        Args:
            session_id: Optional session identifier. Generated if not provided.
            
        Returns:
            New root ObservabilityContext.
        """
        return cls(
            trace_id=f"trace_{uuid.uuid4().hex[:16]}",
            span_id=f"span_{uuid.uuid4().hex[:12]}",
            parent_span_id=None,
            session_id=session_id or f"sess_{uuid.uuid4().hex[:12]}",
            request_id=f"req_{uuid.uuid4().hex[:12]}",
            component_stack=["root"]
        )

    def create_child(self, component_name: str) -> 'ObservabilityContext':
        """Create a child context inheriting trace_id.
        
        Args:
            component_name: Name of the component creating this child span.
            
        Returns:
            New child ObservabilityContext with proper hierarchy.
        """
        return ObservabilityContext(
            trace_id=self.trace_id,
            span_id=f"span_{uuid.uuid4().hex[:12]}",
            parent_span_id=self.span_id,
            session_id=self.session_id,
            request_id=self.request_id,
            component_stack=[*self.component_stack, component_name]
        )

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
            trace_id=ctx.trace_id,
            span_id=ctx.span_id,
            parent_span_id=None,
            session_id=ctx.session_id,
            request_id=ctx.request_id,
            component_stack=[component_name]
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
    """Context manager for creating child spans.
    
    Usage:
        with ObservabilitySpan("my_component") as span:
            # Code runs with child context
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
    
    def __enter__(self) -> 'ObservabilityContext':
        """Enter the span context.
        
        Returns:
            The child context for this span.
        """
        parent_ctx = get_or_create_context(self.component_name)
        self.context = parent_ctx.create_child(self.component_name)
        self.token = set_context(self.context)
        return self.context
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit the span context."""
        if self.token is not None:
            reset_context(self.token)
        return False  # Don't suppress exceptions
