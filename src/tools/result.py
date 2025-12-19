"""Typed result wrapper for tool execution.

Provides a consistent interface for tool results with success/failure states.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolResult:
    """Typed result from tool execution.

    Provides a consistent structure for all tool returns with:
    - success: Whether the operation completed successfully
    - data: The result data on success
    - error: Error message on failure
    - error_type: Classification of the error
    - metadata: Additional context (duration, counts, etc.)

    Example:
        # Success case
        result = ToolResult.ok({"items": [1, 2, 3]})
        if result.success:
            process(result.data)

        # Failure case
        result = ToolResult.fail("Connection timeout", "network")
        if not result.success:
            log_error(result.error, result.error_type)

        # With metadata
        result = ToolResult.ok(data, metadata={"count": 10, "duration_ms": 150})
    """

    success: bool
    data: Any = None
    error: str | None = None
    error_type: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def ok(cls, data: Any, metadata: dict[str, Any] | None = None) -> "ToolResult":
        """Create a successful result.

        Args:
            data: The result data
            metadata: Optional metadata (counts, timing, etc.)

        Returns:
            ToolResult with success=True
        """
        return cls(success=True, data=data, metadata=metadata or {})

    @classmethod
    def fail(
        cls,
        error: str,
        error_type: str = "unknown",
        metadata: dict[str, Any] | None = None,
    ) -> "ToolResult":
        """Create a failure result.

        Args:
            error: Error message describing what went wrong
            error_type: Classification (e.g., "network", "validation", "timeout")
            metadata: Optional metadata

        Returns:
            ToolResult with success=False
        """
        return cls(
            success=False,
            error=error,
            error_type=error_type,
            metadata=metadata or {},
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        Returns legacy-compatible format with 'result' key for data.
        """
        result: dict[str, Any] = {"success": self.success}

        if self.success:
            result["result"] = self.data
        else:
            result["error"] = self.error
            if self.error_type:
                result["error_type"] = self.error_type

        if self.metadata:
            result.update(self.metadata)

        return result

    def __bool__(self) -> bool:
        """Allow using ToolResult in boolean context.

        Example:
            if tool.execute(...):
                # success
        """
        return self.success
