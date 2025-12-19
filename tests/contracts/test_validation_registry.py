"""Tests for thread-safe ValidationRegistry with TTL cleanup."""

import threading
import time

import pytest

from src.contracts.validation_registry import ValidationContext, ValidationRegistry


class TestValidationContext:
    """Tests for ValidationContext dataclass."""

    def test_context_creation(self):
        """Create validation context with required fields."""
        context = ValidationContext(
            run_identifier="test-uuid",
            schema={"type": "object"},
            agent_name="test_agent",
            expected_outputs=["field1", "field2"],
        )

        assert context.run_identifier == "test-uuid"
        assert context.schema == {"type": "object"}
        assert context.agent_name == "test_agent"
        assert context.expected_outputs == ["field1", "field2"]
        assert context.created_at > 0

    def test_context_not_expired(self):
        """Context is not expired immediately after creation."""
        context = ValidationContext(
            run_identifier="test", schema={}, agent_name="agent", expected_outputs=[]
        )

        assert not context.is_expired(ttl=3600)

    def test_context_expired(self):
        """Context is expired after TTL passes."""
        context = ValidationContext(
            run_identifier="test",
            schema={},
            agent_name="agent",
            expected_outputs=[],
            created_at=time.time() - 10,  # Created 10 seconds ago
        )

        assert context.is_expired(ttl=5)  # 5 second TTL
        assert not context.is_expired(ttl=20)  # 20 second TTL


class TestValidationRegistry:
    """Tests for ValidationRegistry singleton."""

    @pytest.fixture(autouse=True)
    def reset_registry(self):
        """Reset singleton before and after each test."""
        ValidationRegistry.reset_instance()
        yield
        ValidationRegistry.reset_instance()

    def test_register_and_get(self):
        """Register context and retrieve it."""
        registry = ValidationRegistry()

        registry.register(
            run_identifier="uuid-123",
            schema={"type": "object", "required": ["name"]},
            agent_name="discovery_agent",
            expected_outputs=["name", "value"],
        )

        retrieved = registry.get("uuid-123")

        assert retrieved is not None
        assert retrieved.run_identifier == "uuid-123"
        assert retrieved.schema == {"type": "object", "required": ["name"]}
        assert retrieved.agent_name == "discovery_agent"
        assert retrieved.expected_outputs == ["name", "value"]

    def test_get_nonexistent(self):
        """Returns None for unknown run_identifier."""
        registry = ValidationRegistry()

        result = registry.get("nonexistent-uuid")

        assert result is None

    def test_is_registered(self):
        """is_registered returns True for registered, False for unknown."""
        registry = ValidationRegistry()

        registry.register(
            run_identifier="registered-uuid", schema={}, agent_name="agent", expected_outputs=[]
        )

        assert registry.is_registered("registered-uuid")
        assert not registry.is_registered("unknown-uuid")

    def test_singleton_pattern(self):
        """Multiple instances share same data."""
        registry1 = ValidationRegistry()
        registry1.register(
            run_identifier="shared-uuid",
            schema={"shared": True},
            agent_name="agent1",
            expected_outputs=[],
        )

        registry2 = ValidationRegistry()
        retrieved = registry2.get("shared-uuid")

        assert retrieved is not None
        assert retrieved.schema == {"shared": True}
        assert registry1 is registry2

    def test_get_instance(self):
        """get_instance returns singleton."""
        instance1 = ValidationRegistry.get_instance()
        instance2 = ValidationRegistry.get_instance()

        assert instance1 is instance2

    def test_ttl_expiration(self):
        """Context expires after TTL."""
        ValidationRegistry.reset_instance()
        registry = ValidationRegistry(ttl=0.1)  # 100ms TTL

        registry.register(
            run_identifier="expiring-uuid", schema={}, agent_name="agent", expected_outputs=[]
        )

        # Should exist immediately
        assert registry.get("expiring-uuid") is not None

        # Wait for expiration
        time.sleep(0.15)

        # Should be expired now
        assert registry.get("expiring-uuid") is None

    def test_cleanup_expired(self):
        """cleanup_expired removes old contexts."""
        ValidationRegistry.reset_instance()
        registry = ValidationRegistry(ttl=0.1)

        # Register two contexts
        registry.register("uuid-1", {}, "agent", [])
        registry.register("uuid-2", {}, "agent", [])

        # Wait for expiration
        time.sleep(0.15)

        # Add a fresh one
        registry.register("uuid-3", {}, "agent", [])

        # Cleanup should remove 2 expired contexts
        removed = registry.cleanup_expired()

        assert removed == 2
        assert registry.get("uuid-1") is None
        assert registry.get("uuid-2") is None
        assert registry.get("uuid-3") is not None

    def test_reset_instance(self):
        """reset_instance allows fresh registry for tests."""
        registry1 = ValidationRegistry()
        registry1.register("uuid-before-reset", {}, "agent", [])

        ValidationRegistry.reset_instance()

        registry2 = ValidationRegistry()

        # Data should be cleared
        assert registry2.get("uuid-before-reset") is None
        # New instance should be different
        assert registry1 is not registry2


class TestValidationRegistryThreadSafety:
    """Thread-safety tests for ValidationRegistry."""

    @pytest.fixture(autouse=True)
    def reset_registry(self):
        """Reset singleton before and after each test."""
        ValidationRegistry.reset_instance()
        yield
        ValidationRegistry.reset_instance()

    def test_concurrent_register(self):
        """Concurrent register operations don't corrupt data."""
        registry = ValidationRegistry()
        errors = []
        num_threads = 10
        registrations_per_thread = 100

        def register_batch(thread_id):
            try:
                for i in range(registrations_per_thread):
                    registry.register(
                        run_identifier=f"thread-{thread_id}-{i}",
                        schema={"thread": thread_id, "index": i},
                        agent_name=f"agent_{thread_id}",
                        expected_outputs=[f"field_{i}"],
                    )
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=register_batch, args=(t,)) for t in range(num_threads)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # No errors should have occurred
        assert len(errors) == 0

        # All registrations should be retrievable
        for thread_id in range(num_threads):
            for i in range(registrations_per_thread):
                context = registry.get(f"thread-{thread_id}-{i}")
                assert context is not None
                assert context.schema["thread"] == thread_id
                assert context.schema["index"] == i

    def test_concurrent_get_and_register(self):
        """Concurrent get and register operations are safe."""
        registry = ValidationRegistry()
        errors = []

        def writer():
            try:
                for i in range(100):
                    registry.register(f"concurrent-{i}", {}, "agent", [])
            except Exception as e:
                errors.append(f"writer: {e}")

        def reader():
            try:
                for _ in range(200):
                    # Read various keys, some exist, some don't
                    for i in range(0, 150, 10):
                        registry.get(f"concurrent-{i}")
                        registry.is_registered(f"concurrent-{i}")
            except Exception as e:
                errors.append(f"reader: {e}")

        threads = [
            threading.Thread(target=writer),
            threading.Thread(target=reader),
            threading.Thread(target=reader),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
