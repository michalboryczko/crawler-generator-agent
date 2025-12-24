"""SQLAlchemy ORM model for agent instances.

Tracks individual agent executions within a session, supporting
hierarchical relationships between parent and child agents for event sourcing.
"""

from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import relationship

from .base import Base


class AgentInstance(Base):
    """SQLAlchemy model for agent instances.

    Tracks individual agent executions within a session with unique IDs
    and optional parent-child relationships for hierarchical agents.

    Attributes:
        id: Agent instance ID (UUID string)
        session_id: Reference to the parent session
        agent_name: Name of the agent (e.g., "main_agent", "discovery_agent")
        parent_instance_id: Optional parent instance for sub-agents
        created_at: Timestamp when instance was created
    """

    __tablename__ = "agent_instances"

    id = Column(String(64), primary_key=True)  # UUID string
    session_id = Column(
        String(64),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    agent_name = Column(String(64), nullable=False, index=True)
    parent_instance_id = Column(
        String(64),
        ForeignKey("agent_instances.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    session = relationship("Session", back_populates="agent_instances")
    parent = relationship(
        "AgentInstance",
        remote_side=[id],
        back_populates="children",
        foreign_keys=[parent_instance_id],
    )
    children = relationship(
        "AgentInstance",
        back_populates="parent",
        foreign_keys=[parent_instance_id],
    )
    events = relationship(
        "AgentContextEvent",
        back_populates="instance",
        order_by="AgentContextEvent.id",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_instance_session", "session_id"),
        Index("idx_instance_parent", "parent_instance_id"),
        Index("idx_instance_agent_name", "agent_name"),
    )

    def __repr__(self) -> str:
        return (
            f"AgentInstance(id={self.id!r}, session_id={self.session_id!r}, "
            f"agent_name={self.agent_name!r})"
        )
