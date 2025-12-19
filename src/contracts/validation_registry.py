"""Thread-safe validation context registry with TTL cleanup."""

import threading
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ValidationContext:
    """Validation context for a specific run.

    Stores schema and expected outputs for validating agent responses.
    Tracks creation time for TTL-based expiration.
    """

    run_identifier: str
    schema: dict[str, Any]
    agent_name: str
    expected_outputs: list[str]
    created_at: float = field(default_factory=time.time)

    def is_expired(self, ttl: float) -> bool:
        """Check if context has exceeded its TTL.

        Args:
            ttl: Time-to-live in seconds

        Returns:
            True if context is expired
        """
        return time.time() - self.created_at > ttl


class ValidationRegistry:
    """Thread-safe singleton registry for validation contexts.

    Stores validation contexts keyed by run_identifier, with automatic
    expiration based on TTL. Used by parent agents to prepare validation
    contexts that child agents can retrieve and use.

    Usage:
        # Parent agent prepares validation
        registry = ValidationRegistry.get_instance()
        registry.register(
            run_identifier="uuid-123",
            schema=load_schema("agent/output.schema.json"),
            agent_name="discovery_agent",
            expected_outputs=["article_urls", "pagination"]
        )

        # Child agent validates
        context = registry.get("uuid-123")
        if context:
            jsonschema.validate(response, context.schema)
    """

    _instance: "ValidationRegistry | None" = None
    _lock = threading.Lock()

    def __new__(cls, ttl: float = 3600.0) -> "ValidationRegistry":
        """Create or return singleton instance.

        Args:
            ttl: Time-to-live for contexts in seconds (default 1 hour)
        """
        if cls._instance is None:
            with cls._lock:
                # Double-check locking pattern
                if cls._instance is None:
                    instance = super().__new__(cls)
                    instance._contexts: dict[str, ValidationContext] = {}
                    instance._ttl = ttl
                    instance._context_lock = threading.RLock()
                    cls._instance = instance
        return cls._instance

    @classmethod
    def get_instance(cls, ttl: float = 3600.0) -> "ValidationRegistry":
        """Get singleton instance.

        Args:
            ttl: Time-to-live for contexts in seconds

        Returns:
            The singleton ValidationRegistry instance
        """
        return cls(ttl)

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton instance for testing.

        This clears all registered contexts and allows a fresh
        instance to be created with different TTL settings.
        """
        with cls._lock:
            cls._instance = None

    def register(
        self,
        run_identifier: str,
        schema: dict[str, Any],
        agent_name: str,
        expected_outputs: list[str],
    ) -> ValidationContext:
        """Register a validation context.

        Args:
            run_identifier: Unique identifier for this validation run
            schema: JSON schema to validate against
            agent_name: Name of the agent being validated
            expected_outputs: List of expected output field names

        Returns:
            The registered ValidationContext
        """
        with self._context_lock:
            context = ValidationContext(
                run_identifier=run_identifier,
                schema=schema,
                agent_name=agent_name,
                expected_outputs=expected_outputs,
            )
            self._contexts[run_identifier] = context
            return context

    def get(self, run_identifier: str) -> ValidationContext | None:
        """Get validation context by run identifier.

        Returns None if:
        - No context exists for the identifier
        - The context has expired (and removes it)

        Args:
            run_identifier: The unique run identifier

        Returns:
            ValidationContext if found and not expired, else None
        """
        with self._context_lock:
            context = self._contexts.get(run_identifier)
            if context is None:
                return None
            if context.is_expired(self._ttl):
                del self._contexts[run_identifier]
                return None
            return context

    def is_registered(self, run_identifier: str) -> bool:
        """Check if a run identifier is registered and not expired.

        Args:
            run_identifier: The unique run identifier

        Returns:
            True if registered and not expired
        """
        return self.get(run_identifier) is not None

    def cleanup_expired(self) -> int:
        """Remove all expired contexts.

        Returns:
            Number of contexts removed
        """
        with self._context_lock:
            expired_keys = [
                key
                for key, context in self._contexts.items()
                if context.is_expired(self._ttl)
            ]
            for key in expired_keys:
                del self._contexts[key]
            return len(expired_keys)
