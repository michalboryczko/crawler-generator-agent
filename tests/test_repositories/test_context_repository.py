"""Tests for context repository implementations."""

from datetime import UTC, datetime

from src.repositories.context_repository import InMemoryContextRepository


class TestInMemoryContextRepository:
    """Tests for InMemoryContextRepository."""

    def test_get_event_returns_event_by_id(self):
        """get_event returns event by ID."""
        repo = InMemoryContextRepository()

        # Create instance and append event
        instance = repo.create_instance("session-1", "agent")
        event = repo.append_event(
            session_id="session-1",
            instance_id=instance.id,
            event_type="user_message",
            content={"role": "user", "content": "Hello"},
        )

        # Get by ID
        result = repo.get_event(event.id)

        assert result is not None
        assert result.id == event.id
        assert result.content == {"role": "user", "content": "Hello"}

    def test_get_event_returns_none_for_nonexistent_id(self):
        """get_event returns None for nonexistent ID."""
        repo = InMemoryContextRepository()

        result = repo.get_event(999)

        assert result is None

    def test_get_event_returns_correct_event_among_many(self):
        """get_event returns correct event when multiple exist."""
        repo = InMemoryContextRepository()

        instance = repo.create_instance("session-1", "agent")
        repo.append_event(
            session_id="session-1",
            instance_id=instance.id,
            event_type="user_message",
            content={"role": "user", "content": "First"},
        )
        event2 = repo.append_event(
            session_id="session-1",
            instance_id=instance.id,
            event_type="assistant_message",
            content={"role": "assistant", "content": "Second"},
        )
        repo.append_event(
            session_id="session-1",
            instance_id=instance.id,
            event_type="user_message",
            content={"role": "user", "content": "Third"},
        )

        # Get middle event
        result = repo.get_event(event2.id)

        assert result is not None
        assert result.id == event2.id
        assert result.content["content"] == "Second"

    def test_event_has_created_at_timestamp(self):
        """Events have created_at timestamp set."""
        repo = InMemoryContextRepository()

        instance = repo.create_instance("session-1", "agent")
        before = datetime.now(UTC)
        event = repo.append_event(
            session_id="session-1",
            instance_id=instance.id,
            event_type="user_message",
            content={"role": "user", "content": "Test"},
        )
        after = datetime.now(UTC)

        assert event.created_at is not None
        assert before <= event.created_at <= after

    def test_get_event_preserves_timestamp(self):
        """get_event returns event with original timestamp."""
        repo = InMemoryContextRepository()

        instance = repo.create_instance("session-1", "agent")
        original_event = repo.append_event(
            session_id="session-1",
            instance_id=instance.id,
            event_type="user_message",
            content={"role": "user", "content": "Test"},
        )

        # Get event and verify timestamp matches
        retrieved_event = repo.get_event(original_event.id)

        assert retrieved_event.created_at == original_event.created_at
