"""SQLAlchemy ORM model for crawler sessions.

Tracks the lifecycle of crawler runs including status, timing, and output location.
"""

from datetime import UTC, datetime
from enum import Enum

from sqlalchemy import Column, DateTime, Index, String, Text

from .base import Base


class SessionStatus(str, Enum):
    """Status of a crawler session."""

    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"


class Session(Base):
    """SQLAlchemy model for crawler sessions.

    Tracks each crawler run with its target, status, and output location.

    Attributes:
        id: Session ID (UUID string, same as used throughout the system)
        target_site: The URL being crawled
        init_at: Timestamp when session started (used for output dir naming)
        status: Current status (in_progress, success, failed)
        output_dir: Path to the output directory
        agent_version: Version of the agent (from AGENT_VERSION env)
        error_message: Error details if status is failed
        completed_at: Timestamp when session finished (success or failed)
    """

    __tablename__ = "sessions"

    id = Column(String(64), primary_key=True)  # UUID string
    target_site = Column(Text, nullable=False)
    init_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    status = Column(
        String(20),
        default=SessionStatus.IN_PROGRESS.value,
        nullable=False,
        index=True,
    )
    output_dir = Column(String(512), nullable=True)
    agent_version = Column(String(32), nullable=True)
    error_message = Column(Text, nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_session_status", "status"),
        Index("idx_session_init_at", "init_at"),
    )

    def __repr__(self) -> str:
        return f"Session(id={self.id!r}, target_site={self.target_site!r}, status={self.status!r})"

    def mark_success(self) -> None:
        """Mark session as successfully completed."""
        self.status = SessionStatus.SUCCESS.value
        self.completed_at = datetime.now(UTC)

    def mark_failed(self, error: str) -> None:
        """Mark session as failed with error message."""
        self.status = SessionStatus.FAILED.value
        self.error_message = error
        self.completed_at = datetime.now(UTC)
