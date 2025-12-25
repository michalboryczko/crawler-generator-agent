"""SQLAlchemy ORM model for agent context events.

Stores immutable event records that can be replayed to reconstruct
agent conversation context at any point (event sourcing pattern).
"""

from datetime import UTC, datetime
from enum import Enum

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.types import JSON

from .base import Base


class EventType(str, Enum):
    """Types of context events for event sourcing."""

    SYSTEM_MESSAGE = "system_message"
    USER_MESSAGE = "user_message"
    ASSISTANT_MESSAGE = "assistant_message"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"


class AgentContextEvent(Base):
    """SQLAlchemy model for agent context events.

    Stores immutable event records that can be replayed to reconstruct
    agent conversation context at any point.

    The auto-incrementing `id` serves as the global event ordering across
    the entire session. This allows restoring session state to any point
    by querying all events with id <= target_id.

    Attributes:
        id: Auto-incrementing primary key (global event ordering)
        session_id: Direct reference to session for efficient queries
        instance_id: Reference to the agent instance
        event_type: Type of event (system_message, user_message, etc.)
        content: JSON content of the event (message dict)
        tool_call_id: Optional tool call ID for tool_result events
        created_at: Timestamp when event was created
    """

    __tablename__ = "agent_context_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(
        String(64),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    instance_id = Column(
        String(64),
        ForeignKey("agent_instances.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type = Column(String(32), nullable=False)
    content = Column(JSON, nullable=False)
    tool_call_id = Column(String(64), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationship
    instance = relationship("AgentInstance", back_populates="events")

    __table_args__ = (
        Index("idx_event_instance", "instance_id"),
        Index("idx_event_session_id", "session_id", "id"),
    )

    def __repr__(self) -> str:
        return (
            f"AgentContextEvent(id={self.id}, session_id={self.session_id!r}, "
            f"instance_id={self.instance_id!r}, type={self.event_type!r})"
        )
