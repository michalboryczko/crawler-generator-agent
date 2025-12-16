"""Agent result types for explicit data passing.

This module provides the AgentResult dataclass that enables explicit data
passing between agents instead of implicit shared memory. This follows
the microservices pattern where each service has its own isolated data store.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentResult:
    """Result from agent execution with explicit outputs.

    Replaces implicit memory-based data sharing between agents
    with explicit, typed data passing.

    Example:
        # Creating a result
        result = AgentResult.ok(
            extracted_articles=["url1", "url2"],
            pagination_type="numbered"
        )

        # Accessing data
        articles = result.get("extracted_articles", [])
        if result.has("pagination_type"):
            ptype = result["pagination_type"]

        # Creating failure
        result = AgentResult.failure("Connection timeout", url=target_url)
    """

    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    memory_snapshot: dict[str, Any] | None = None  # Optional internal state
    errors: list[str] = field(default_factory=list)
    iterations: int = 0

    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from the data dict.

        Args:
            key: Data key to retrieve
            default: Default value if key not found

        Returns:
            The value or default
        """
        return self.data.get(key, default)

    def __getitem__(self, key: str) -> Any:
        """Allow dict-like access: result['key'].

        Args:
            key: Data key to retrieve

        Returns:
            The value

        Raises:
            KeyError: If key not found
        """
        return self.data[key]

    def has(self, key: str) -> bool:
        """Check if key exists in data.

        Args:
            key: Key to check

        Returns:
            True if key exists
        """
        return key in self.data

    @property
    def failed(self) -> bool:
        """Inverse of success for readability.

        Returns:
            True if result indicates failure
        """
        return not self.success

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization.

        Returns:
            Dictionary representation of result
        """
        return {
            "success": self.success,
            "data": self.data,
            "errors": self.errors,
            "iterations": self.iterations,
        }

    @classmethod
    def failure(cls, error: str, **data: Any) -> "AgentResult":
        """Factory for failure results.

        Args:
            error: Error message describing the failure
            **data: Additional data to include

        Returns:
            AgentResult with success=False
        """
        return cls(success=False, errors=[error], data=data)

    @classmethod
    def ok(cls, **data: Any) -> "AgentResult":
        """Factory for success results.

        Args:
            **data: Data to include in result

        Returns:
            AgentResult with success=True
        """
        return cls(success=True, data=data)

    def merge_data(self, other: dict[str, Any]) -> "AgentResult":
        """Merge additional data into result.

        Args:
            other: Dictionary of data to merge

        Returns:
            Self for chaining
        """
        self.data.update(other)
        return self

    def add_error(self, error: str) -> "AgentResult":
        """Add an error message.

        Args:
            error: Error message to add

        Returns:
            Self for chaining
        """
        self.errors.append(error)
        return self
