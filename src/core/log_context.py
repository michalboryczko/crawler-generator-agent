"""Context propagation for structured logging.

Provides thread-safe context management for trace correlation across
nested agent and tool calls using Python's contextvars.

Key components:
- ContextVar-based logger storage
- Context manager for creating child spans
- LoggerManager for initialization and access
"""

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Generator, Any

from .structured_logger import (
    StructuredLogger,
    TraceContext,
    LogOutput,
    LogLevel,
)


# Global context variable for current logger
# Uses contextvars for thread-safety and proper async handling
_current_logger: ContextVar[StructuredLogger | None] = ContextVar(
    "current_logger",
    default=None
)


def get_logger() -> StructuredLogger | None:
    """Get the current logger from context.

    Returns the StructuredLogger currently active in this execution context,
    or None if no logger is configured.

    Returns:
        Current StructuredLogger or None
    """
    return _current_logger.get()


def set_logger(logger: StructuredLogger) -> None:
    """Set the current logger in context.

    This is typically called during initialization. For creating child
    loggers within a span, use the `span` context manager instead.

    Args:
        logger: The StructuredLogger to set as current
    """
    _current_logger.set(logger)


@contextmanager
def span(
    name: str | None = None,
    context: dict[str, Any] | None = None,
    tags: list[str] | None = None,
) -> Generator[StructuredLogger, None, None]:
    """Context manager for creating a child span.

    Creates a new child logger with its own span ID while preserving
    the parent trace context. The child logger is set as current for
    the duration of the context.

    Usage:
        with span("agent.operation", context={"agent": "browser"}) as logger:
            logger.info(event, "Starting operation")
            # nested operations will use this logger as parent
            logger.info(event, "Operation complete")

    Args:
        name: Optional logger name override
        context: Additional context fields to merge
        tags: Additional tags to merge

    Yields:
        Child StructuredLogger with new span context

    Raises:
        RuntimeError: If no logger is configured in context
    """
    parent_logger = get_logger()
    if parent_logger is None:
        raise RuntimeError(
            "No logger in context. Initialize with LoggerManager first."
        )

    # Create child logger with new span
    child_logger = parent_logger.child(name=name, context=context, tags=tags)

    # Save current context and set child as current
    token = _current_logger.set(child_logger)
    try:
        yield child_logger
    finally:
        # Restore parent context
        _current_logger.reset(token)


class LoggerManager:
    """Manager for initializing and accessing structured loggers.

    Provides a singleton-style manager for the logging system, handling
    initialization, output configuration, and root logger access.

    Usage:
        # Initialize once at application start
        manager = LoggerManager.initialize(
            outputs=[ConsoleOutput(), JSONLinesOutput("logs/app.jsonl")],
            min_level="INFO",
            service_name="crawler-agent",
        )

        # Get logger anywhere in the application
        logger = LoggerManager.get_instance().root_logger
        # Or use get_logger() for current context logger
    """

    _instance: "LoggerManager | None" = None

    def __init__(self, root_logger: StructuredLogger):
        """Initialize LoggerManager with root logger.

        Args:
            root_logger: The root StructuredLogger for the application
        """
        self.root_logger = root_logger
        LoggerManager._instance = self
        set_logger(root_logger)

    @classmethod
    def get_instance(cls) -> "LoggerManager":
        """Get the singleton LoggerManager instance.

        Returns:
            The initialized LoggerManager

        Raises:
            RuntimeError: If LoggerManager hasn't been initialized
        """
        if cls._instance is None:
            raise RuntimeError(
                "LoggerManager not initialized. Call LoggerManager.initialize() first."
            )
        return cls._instance

    @classmethod
    def initialize(
        cls,
        outputs: list[LogOutput],
        min_level: str = "INFO",
        service_name: str = "crawler-agent",
        session_context: TraceContext | None = None,
    ) -> "LoggerManager":
        """Initialize the structured logging system.

        Creates a root logger with the specified configuration and sets it
        as the current logger in context. This should be called once at
        application startup.

        Args:
            outputs: List of LogOutput destinations
            min_level: Minimum log level ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
            service_name: Service name for log attribution
            session_context: Optional existing trace context (creates new if None)

        Returns:
            Initialized LoggerManager instance
        """
        # Parse log level
        level = LogLevel[min_level.upper()]

        # Create or use trace context
        trace_context = session_context or TraceContext.new_session()

        # Create root logger
        root_logger = StructuredLogger(
            name=service_name,
            trace_context=trace_context,
            outputs=outputs,
            min_level=level,
            default_tags=[service_name],
            context={"service": service_name},
        )

        return cls(root_logger)

    @classmethod
    def is_initialized(cls) -> bool:
        """Check if LoggerManager has been initialized.

        Returns:
            True if initialized, False otherwise
        """
        return cls._instance is not None

    @classmethod
    def reset(cls) -> None:
        """Reset the LoggerManager (for testing).

        Clears the singleton instance and context. Should only be used
        in testing scenarios.
        """
        if cls._instance is not None:
            # Close all outputs
            for output in cls._instance.root_logger.outputs:
                try:
                    output.close()
                except Exception:
                    pass
        cls._instance = None
        _current_logger.set(None)

    def get_trace_context(self) -> TraceContext:
        """Get the current trace context.

        Returns:
            Current TraceContext from the root logger
        """
        return self.root_logger.trace_context

    def new_request(self) -> StructuredLogger:
        """Create a new logger for a new request within the same session.

        Creates a new request_id and trace_id while preserving session_id.
        Useful for processing multiple requests within a single application run.

        Returns:
            New StructuredLogger with fresh request context
        """
        new_context = self.root_logger.trace_context.new_request()
        new_logger = StructuredLogger(
            name=self.root_logger.name,
            trace_context=new_context,
            outputs=self.root_logger.outputs,
            min_level=self.root_logger.min_level,
            default_tags=self.root_logger.default_tags,
            context=self.root_logger.default_context,
        )
        set_logger(new_logger)
        return new_logger


def with_span(
    name: str | None = None,
    context: dict[str, Any] | None = None,
    tags: list[str] | None = None,
):
    """Decorator for automatically wrapping function in a span.

    Creates a child span for the duration of the decorated function.

    Usage:
        @with_span("browser.navigate", tags=["browser"])
        def navigate_to_url(url: str):
            # This function runs within its own span
            pass

    Args:
        name: Optional span name (defaults to function name)
        context: Additional context fields
        tags: Additional tags

    Returns:
        Decorated function
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            span_name = name or f"function.{func.__name__}"
            with span(span_name, context=context, tags=tags):
                return func(*args, **kwargs)
        return wrapper
    return decorator
