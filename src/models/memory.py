"""SQLAlchemy ORM model for memory entries.

This model is used by both InMemoryRepository and SQLAlchemyRepository,
providing a consistent domain object across storage backends.
"""

from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Index, Integer, String
from sqlalchemy.types import JSON

from .base import Base


class MemoryEntry(Base):
    """SQLAlchemy model for memory entries.

    Represents a key-value pair stored in agent memory with session
    and agent isolation. Used by both in-memory and persistent storage.

    Attributes:
        id: Auto-incrementing primary key
        session_id: Identifies the workflow session
        agent_name: Identifies which agent owns this entry
        key: The memory key (unique within session+agent scope)
        value: JSON-serializable value
        created_at: Timestamp when entry was first created
        updated_at: Timestamp of last modification
    """

    __tablename__ = "memory_entries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), nullable=False, index=True)
    agent_name = Column(String(64), nullable=False, index=True)
    key = Column(String(256), nullable=False, index=True)
    value = Column(JSON, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (
        Index("idx_session_agent", "session_id", "agent_name"),
        Index(
            "idx_unique_entry",
            "session_id",
            "agent_name",
            "key",
            unique=True,
        ),
    )

    def __repr__(self) -> str:
        return (
            f"MemoryEntry(id={self.id}, session_id={self.session_id!r}, "
            f"agent_name={self.agent_name!r}, key={self.key!r})"
        )
