"""Repository for agent context persistence (event sourcing).

Provides abstract interface and SQLAlchemy implementation for storing
and retrieving agent context events for session replay.

The auto-incrementing event ID serves as global ordering across
the entire session, allowing state restoration to any point.
"""

import uuid
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ..models.agent_instance import AgentInstance
from ..models.context_event import AgentContextEvent

if TYPE_CHECKING:
    from sqlalchemy.orm import sessionmaker


class AbstractContextRepository(ABC):
    """Abstract repository for context persistence.

    Provides methods for managing agent instances and context events
    with support for event sourcing patterns.

    The event ID (auto-increment) provides global ordering across all
    agents in a session, enabling point-in-time state restoration.
    """

    @abstractmethod
    def create_instance(
        self,
        session_id: str,
        agent_name: str,
        instance_id: str | None = None,
        parent_id: str | None = None,
    ) -> AgentInstance:
        """Create a new agent instance.

        Args:
            session_id: The session this instance belongs to
            agent_name: Name of the agent
            instance_id: Optional UUID (generated if not provided)
            parent_id: Optional parent instance ID for sub-agents

        Returns:
            The created AgentInstance
        """
        pass

    @abstractmethod
    def get_instance(self, instance_id: str) -> AgentInstance | None:
        """Get an agent instance by ID.

        Args:
            instance_id: The instance UUID

        Returns:
            AgentInstance if found, None otherwise
        """
        pass

    @abstractmethod
    def get_instances_by_session(self, session_id: str) -> list[AgentInstance]:
        """Get all agent instances for a session.

        Args:
            session_id: The session ID

        Returns:
            List of AgentInstance objects
        """
        pass

    @abstractmethod
    def append_event(
        self,
        session_id: str,
        instance_id: str,
        event_type: str,
        content: dict,
        tool_call_id: str | None = None,
    ) -> AgentContextEvent:
        """Append a new event to an instance's context.

        The event is assigned a globally-unique auto-increment ID
        that provides ordering across all agents in the session.

        Args:
            session_id: The session ID (for direct querying)
            instance_id: The instance UUID
            event_type: Type of event (system_message, user_message, etc.)
            content: JSON content of the event
            tool_call_id: Optional tool call ID for tool_result events

        Returns:
            The created AgentContextEvent with assigned ID
        """
        pass

    @abstractmethod
    def get_instance_events(
        self,
        instance_id: str,
        from_event_id: int = 0,
    ) -> list[AgentContextEvent]:
        """Get events for a specific instance.

        Args:
            instance_id: The instance UUID
            from_event_id: Minimum event ID (default 0 = all)

        Returns:
            List of AgentContextEvent objects ordered by ID
        """
        pass

    @abstractmethod
    def get_session_events_up_to(
        self,
        session_id: str,
        up_to_event_id: int,
    ) -> list[AgentContextEvent]:
        """Get all session events up to a specific event ID.

        This is the key method for point-in-time state restoration.
        Returns events from ALL agents in the session where id <= up_to_event_id.

        Args:
            session_id: The session ID
            up_to_event_id: Maximum event ID to include

        Returns:
            List of AgentContextEvent objects ordered by ID
        """
        pass

    @abstractmethod
    def get_last_event_id(self, session_id: str) -> int:
        """Get the last event ID for a session.

        Args:
            session_id: The session ID

        Returns:
            Last event ID, or 0 if no events
        """
        pass

    @abstractmethod
    def delete_events_after(
        self,
        session_id: str,
        event_id: int,
    ) -> int:
        """Delete all events after a specific event ID.

        Args:
            session_id: The session ID
            event_id: Delete events with id > this value

        Returns:
            Number of events deleted
        """
        pass

    @abstractmethod
    def copy_events(
        self,
        source_instance_id: str,
        target_session_id: str,
        target_instance_id: str,
        up_to_event_id: int | None = None,
    ) -> int:
        """Copy events from one instance to another.

        Args:
            source_instance_id: Source instance UUID
            target_session_id: Target session ID
            target_instance_id: Target instance UUID
            up_to_event_id: Optional max event ID to copy

        Returns:
            Number of events copied
        """
        pass

    @abstractmethod
    def get_event(self, event_id: int) -> AgentContextEvent | None:
        """Get a specific event by ID.

        Args:
            event_id: The event ID

        Returns:
            AgentContextEvent if found, None otherwise
        """
        pass


class SQLAlchemyContextRepository(AbstractContextRepository):
    """SQLAlchemy implementation of context repository."""

    def __init__(self, session_factory: "sessionmaker[Session]"):
        """Initialize with SQLAlchemy session factory.

        Args:
            session_factory: SQLAlchemy sessionmaker instance
        """
        self._session_factory = session_factory

    def _get_session(self) -> Session:
        """Get a new database session."""
        return self._session_factory()

    def create_instance(
        self,
        session_id: str,
        agent_name: str,
        instance_id: str | None = None,
        parent_id: str | None = None,
    ) -> AgentInstance:
        """Create a new agent instance."""
        with self._get_session() as db_session:
            instance = AgentInstance(
                id=instance_id or str(uuid.uuid4()),
                session_id=session_id,
                agent_name=agent_name,
                parent_instance_id=parent_id,
            )
            db_session.add(instance)
            db_session.commit()
            db_session.expunge(instance)
            return instance

    def get_instance(self, instance_id: str) -> AgentInstance | None:
        """Get an agent instance by ID."""
        with self._get_session() as db_session:
            stmt = select(AgentInstance).where(AgentInstance.id == instance_id)
            instance = db_session.execute(stmt).scalar_one_or_none()
            if instance:
                db_session.expunge(instance)
            return instance

    def get_instances_by_session(self, session_id: str) -> list[AgentInstance]:
        """Get all agent instances for a session."""
        with self._get_session() as db_session:
            stmt = (
                select(AgentInstance)
                .where(AgentInstance.session_id == session_id)
                .order_by(AgentInstance.created_at)
            )
            instances = list(db_session.execute(stmt).scalars().all())
            for instance in instances:
                db_session.expunge(instance)
            return instances

    def append_event(
        self,
        session_id: str,
        instance_id: str,
        event_type: str,
        content: dict,
        tool_call_id: str | None = None,
    ) -> AgentContextEvent:
        """Append a new event to an instance's context.

        The database auto-increment ID guarantees global ordering
        even with parallel agent execution.
        """
        with self._get_session() as db_session:
            event = AgentContextEvent(
                session_id=session_id,
                instance_id=instance_id,
                event_type=event_type,
                content=content,
                tool_call_id=tool_call_id,
            )
            db_session.add(event)
            db_session.commit()
            db_session.refresh(event)  # Get the assigned ID
            db_session.expunge(event)
            return event

    def get_instance_events(
        self,
        instance_id: str,
        from_event_id: int = 0,
    ) -> list[AgentContextEvent]:
        """Get events for a specific instance."""
        with self._get_session() as db_session:
            stmt = (
                select(AgentContextEvent)
                .where(
                    AgentContextEvent.instance_id == instance_id,
                    AgentContextEvent.id >= from_event_id,
                )
                .order_by(AgentContextEvent.id)
            )
            events = list(db_session.execute(stmt).scalars().all())
            for event in events:
                db_session.expunge(event)
            return events

    def get_session_events_up_to(
        self,
        session_id: str,
        up_to_event_id: int,
    ) -> list[AgentContextEvent]:
        """Get all session events up to a specific event ID.

        Returns events from ALL agents in the session where id <= up_to_event_id,
        ordered by ID for correct replay order.
        """
        with self._get_session() as db_session:
            stmt = (
                select(AgentContextEvent)
                .where(
                    AgentContextEvent.session_id == session_id,
                    AgentContextEvent.id <= up_to_event_id,
                )
                .order_by(AgentContextEvent.id)
            )
            events = list(db_session.execute(stmt).scalars().all())
            for event in events:
                db_session.expunge(event)
            return events

    def get_last_event_id(self, session_id: str) -> int:
        """Get the last event ID for a session."""
        with self._get_session() as db_session:
            max_id = db_session.execute(
                select(func.max(AgentContextEvent.id)).where(
                    AgentContextEvent.session_id == session_id
                )
            ).scalar()
            return max_id or 0

    def delete_events_after(
        self,
        session_id: str,
        event_id: int,
    ) -> int:
        """Delete all events after a specific event ID."""
        with self._get_session() as db_session:
            stmt = delete(AgentContextEvent).where(
                AgentContextEvent.session_id == session_id,
                AgentContextEvent.id > event_id,
            )
            result = db_session.execute(stmt)
            db_session.commit()
            return result.rowcount  # type: ignore[return-value]

    def copy_events(
        self,
        source_instance_id: str,
        target_session_id: str,
        target_instance_id: str,
        up_to_event_id: int | None = None,
    ) -> int:
        """Copy events from one instance to another."""
        events = self.get_instance_events(source_instance_id)
        if up_to_event_id is not None:
            events = [e for e in events if e.id <= up_to_event_id]

        count = 0
        for event in events:
            self.append_event(
                session_id=target_session_id,
                instance_id=target_instance_id,
                event_type=event.event_type,
                content=event.content,
                tool_call_id=event.tool_call_id,
            )
            count += 1
        return count

    def get_event(self, event_id: int) -> AgentContextEvent | None:
        """Get a specific event by ID."""
        with self._get_session() as db_session:
            stmt = select(AgentContextEvent).where(AgentContextEvent.id == event_id)
            event = db_session.execute(stmt).scalar_one_or_none()
            if event:
                db_session.expunge(event)
            return event


class InMemoryContextRepository(AbstractContextRepository):
    """In-memory implementation of context repository for testing."""

    def __init__(self) -> None:
        """Initialize empty storage."""
        self._instances: dict[str, AgentInstance] = {}
        self._events: list[AgentContextEvent] = []
        self._event_counter = 0

    def create_instance(
        self,
        session_id: str,
        agent_name: str,
        instance_id: str | None = None,
        parent_id: str | None = None,
    ) -> AgentInstance:
        """Create a new agent instance."""
        from datetime import UTC, datetime

        inst_id = instance_id or str(uuid.uuid4())
        instance = AgentInstance(
            id=inst_id,
            session_id=session_id,
            agent_name=agent_name,
            parent_instance_id=parent_id,
            created_at=datetime.now(UTC),
        )
        self._instances[inst_id] = instance
        return instance

    def get_instance(self, instance_id: str) -> AgentInstance | None:
        """Get an agent instance by ID."""
        return self._instances.get(instance_id)

    def get_instances_by_session(self, session_id: str) -> list[AgentInstance]:
        """Get all agent instances for a session."""
        return [inst for inst in self._instances.values() if inst.session_id == session_id]

    def append_event(
        self,
        session_id: str,
        instance_id: str,
        event_type: str,
        content: dict,
        tool_call_id: str | None = None,
    ) -> AgentContextEvent:
        """Append a new event to an instance's context."""
        from datetime import UTC, datetime

        self._event_counter += 1

        event = AgentContextEvent(
            id=self._event_counter,
            session_id=session_id,
            instance_id=instance_id,
            event_type=event_type,
            content=content,
            tool_call_id=tool_call_id,
            created_at=datetime.now(UTC),
        )
        self._events.append(event)
        return event

    def get_instance_events(
        self,
        instance_id: str,
        from_event_id: int = 0,
    ) -> list[AgentContextEvent]:
        """Get events for a specific instance."""
        return [e for e in self._events if e.instance_id == instance_id and e.id >= from_event_id]

    def get_session_events_up_to(
        self,
        session_id: str,
        up_to_event_id: int,
    ) -> list[AgentContextEvent]:
        """Get all session events up to a specific event ID."""
        return [e for e in self._events if e.session_id == session_id and e.id <= up_to_event_id]

    def get_last_event_id(self, session_id: str) -> int:
        """Get the last event ID for a session."""
        session_events = [e for e in self._events if e.session_id == session_id]
        if not session_events:
            return 0
        return max(e.id for e in session_events)

    def delete_events_after(
        self,
        session_id: str,
        event_id: int,
    ) -> int:
        """Delete all events after a specific event ID."""
        original_count = len(self._events)
        self._events = [
            e for e in self._events if not (e.session_id == session_id and e.id > event_id)
        ]
        return original_count - len(self._events)

    def copy_events(
        self,
        source_instance_id: str,
        target_session_id: str,
        target_instance_id: str,
        up_to_event_id: int | None = None,
    ) -> int:
        """Copy events from one instance to another."""
        events = self.get_instance_events(source_instance_id)
        if up_to_event_id is not None:
            events = [e for e in events if e.id <= up_to_event_id]

        count = 0
        for event in events:
            self.append_event(
                session_id=target_session_id,
                instance_id=target_instance_id,
                event_type=event.event_type,
                content=event.content,
                tool_call_id=event.tool_call_id,
            )
            count += 1
        return count

    def get_event(self, event_id: int) -> AgentContextEvent | None:
        """Get a specific event by ID."""
        for event in self._events:
            if event.id == event_id:
                return event
        return None
