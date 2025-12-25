"""Service for managing agent context with event sourcing.

Provides a message-list-like interface that automatically persists
all operations as events for later replay.

The event ID (auto-increment) provides global ordering across all
agents in a session, enabling point-in-time state restoration.
"""

from typing import Any, cast

from ..models.context_event import EventType
from ..repositories.context_repository import AbstractContextRepository


class ContextService:
    """Service for managing agent context with event sourcing.

    Provides a message-list-like interface that automatically persists
    all operations as events for later replay.

    The event ID provides global ordering across all agents in a session,
    enabling point-in-time state restoration via get_session_events_up_to().

    Usage:
        # Create service for an agent instance
        service = ContextService(repository, session_id, instance_id)

        # Append messages (automatically persisted as events)
        service.append_message("system", "You are a helpful assistant.")
        service.append_message("user", "Hello!")

        # Get all messages for this instance
        messages = service.get_messages()

        # Get all session events up to a specific point (across all agents)
        events = service.get_session_events_up_to(event_id=15)

        # Session management operations
        service.copy_to_new_instance(new_session_id, new_instance_id, up_to_event_id=10)
        service.truncate_after_event(5)
    """

    def __init__(
        self,
        repository: AbstractContextRepository,
        session_id: str,
        instance_id: str,
    ) -> None:
        """Initialize the context service.

        Args:
            repository: Context repository for persistence
            session_id: The session ID (for global event ordering)
            instance_id: The agent instance UUID
        """
        self._repository = repository
        self._session_id = session_id
        self._instance_id = instance_id
        self._messages_cache: list[dict[str, Any]] | None = None

    @property
    def session_id(self) -> str:
        """Get the session ID."""
        return self._session_id

    @property
    def instance_id(self) -> str:
        """Get the agent instance ID."""
        return self._instance_id

    @property
    def repository(self) -> AbstractContextRepository:
        """Get the underlying repository."""
        return self._repository

    def append_message(
        self,
        role: str,
        content: str,
        tool_calls: list[dict[str, Any]] | None = None,
        tool_call_id: str | None = None,
    ) -> int:
        """Append a message to the context.

        Automatically determines the event type from the role and persists
        the message as an event.

        Args:
            role: Message role (system, user, assistant, tool)
            content: Message content
            tool_calls: Optional list of tool calls (for assistant messages)
            tool_call_id: Optional tool call ID (for tool result messages)

        Returns:
            The event ID assigned by the database (global ordering)
        """
        # Determine event type from role
        event_type_map = {
            "system": EventType.SYSTEM_MESSAGE.value,
            "user": EventType.USER_MESSAGE.value,
            "assistant": EventType.ASSISTANT_MESSAGE.value,
            "tool": EventType.TOOL_RESULT.value,
        }
        event_type = event_type_map.get(role, EventType.USER_MESSAGE.value)

        # Build message content dict
        message_content: dict[str, Any] = {"role": role, "content": content}
        if tool_calls:
            message_content["tool_calls"] = tool_calls
        if tool_call_id:
            message_content["tool_call_id"] = tool_call_id

        # Persist as event
        event = self._repository.append_event(
            session_id=self._session_id,
            instance_id=self._instance_id,
            event_type=event_type,
            content=message_content,
            tool_call_id=tool_call_id,
        )

        # Invalidate cache
        self._messages_cache = None

        return event.id

    def get_messages(self) -> list[dict[str, Any]]:
        """Get all messages for this instance reconstructed from events.

        Returns cached messages if available, otherwise loads from repository.

        Returns:
            List of message dictionaries in conversation order
        """
        if self._messages_cache is not None:
            return self._messages_cache

        events = self._repository.get_instance_events(self._instance_id)
        self._messages_cache = cast(list[dict[str, Any]], [event.content for event in events])
        return self._messages_cache

    def replay_from_event(self, event_id: int) -> list[dict[str, Any]]:
        """Replay instance messages from a specific event ID.

        Args:
            event_id: Starting event ID (inclusive)

        Returns:
            List of message dictionaries from event_id onwards
        """
        events = self._repository.get_instance_events(self._instance_id, from_event_id=event_id)
        return [event.content for event in events]

    def get_session_events_up_to(self, event_id: int) -> list[dict[str, Any]]:
        """Get all session events up to a specific event ID.

        This is the key method for point-in-time state restoration.
        Returns events from ALL agents in the session where id <= event_id.

        Example:
            Main agent has events 1-10, Discovery has 11-20, Selector has 21-32.
            Calling get_session_events_up_to(15) returns:
            - All main agent events (1-10)
            - Discovery events 11-15
            - No selector events

        Args:
            event_id: Maximum event ID to include

        Returns:
            List of event content dictionaries ordered by ID
        """
        events = self._repository.get_session_events_up_to(
            session_id=self._session_id,
            up_to_event_id=event_id,
        )
        return [{"instance_id": e.instance_id, "content": e.content} for e in events]

    def get_last_event_id(self) -> int:
        """Get the last event ID for the session.

        Returns:
            Last event ID across all agents in session, or 0 if no events
        """
        return self._repository.get_last_event_id(self._session_id)

    def copy_to_new_instance(
        self,
        target_session_id: str,
        target_instance_id: str,
        up_to_event_id: int | None = None,
    ) -> int:
        """Copy events to a new instance.

        Args:
            target_session_id: Target session ID
            target_instance_id: Target instance UUID
            up_to_event_id: Optional max event ID to copy

        Returns:
            Number of events copied
        """
        return self._repository.copy_events(
            source_instance_id=self._instance_id,
            target_session_id=target_session_id,
            target_instance_id=target_instance_id,
            up_to_event_id=up_to_event_id,
        )

    def truncate_after_event(self, event_id: int) -> int:
        """Delete events after a specific event ID.

        Used for --overwrite mode to reset context to a specific point.
        Deletes events across ALL agents in the session.

        Args:
            event_id: Keep events with id <= this value

        Returns:
            Number of events deleted
        """
        count = self._repository.delete_events_after(
            session_id=self._session_id,
            event_id=event_id,
        )
        # Invalidate cache
        self._messages_cache = None
        return count

    def clear_cache(self) -> None:
        """Clear the messages cache.

        Useful when external operations may have modified events.
        """
        self._messages_cache = None
