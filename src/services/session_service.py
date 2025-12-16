"""Service for managing crawler sessions.

Handles session lifecycle: creation, status updates, and completion tracking.
"""

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from ..models.session import Session, SessionStatus

if TYPE_CHECKING:
    from sqlalchemy.orm import sessionmaker


class SessionService:
    """Service for managing Session lifecycle.

    Provides methods to create, update, and query crawler sessions.
    Only persists to database when a session factory is provided.

    Usage:
        # With database
        service = SessionService(session_factory)
        session = service.create(session_id, url, output_dir, agent_version)
        ...
        service.mark_success(session_id)

        # Without database (no-op mode)
        service = SessionService(None)
        session = service.create(...)  # Returns Session object but doesn't persist
    """

    def __init__(self, session_factory: "sessionmaker[DBSession] | None") -> None:
        """Initialize session service.

        Args:
            session_factory: SQLAlchemy session factory, or None for no-op mode
        """
        self._session_factory = session_factory

    def _get_session(self) -> "DBSession | None":
        """Get a database session if factory is available."""
        if self._session_factory is None:
            return None
        return self._session_factory()

    def create(
        self,
        session_id: str,
        target_site: str,
        output_dir: Path | str | None = None,
        agent_version: str | None = None,
        init_at: datetime | None = None,
    ) -> Session:
        """Create a new session record.

        Args:
            session_id: Unique session identifier
            target_site: URL being crawled
            output_dir: Path to output directory
            agent_version: Version of the agent
            init_at: Session start time (defaults to now)

        Returns:
            The created Session object
        """
        init_at = init_at or datetime.now(UTC)

        session_obj = Session(
            id=session_id,
            target_site=target_site,
            init_at=init_at,
            status=SessionStatus.IN_PROGRESS.value,
            output_dir=str(output_dir) if output_dir else None,
            agent_version=agent_version,
        )

        db_session = self._get_session()
        if db_session:
            with db_session:
                db_session.add(session_obj)
                db_session.commit()
                db_session.expunge(session_obj)

        return session_obj

    def get(self, session_id: str) -> Session | None:
        """Get a session by ID.

        Args:
            session_id: The session ID to look up

        Returns:
            Session object or None if not found
        """
        db_session = self._get_session()
        if db_session is None:
            return None

        with db_session:
            stmt = select(Session).where(Session.id == session_id)
            result = db_session.execute(stmt).scalar_one_or_none()
            if result:
                db_session.expunge(result)
            return result

    def mark_success(self, session_id: str) -> bool:
        """Mark a session as successfully completed.

        Args:
            session_id: The session ID to update

        Returns:
            True if updated, False if not found or no database
        """
        db_session = self._get_session()
        if db_session is None:
            return False

        with db_session:
            stmt = select(Session).where(Session.id == session_id)
            session_obj = db_session.execute(stmt).scalar_one_or_none()
            if session_obj:
                session_obj.mark_success()
                db_session.commit()
                return True
            return False

    def mark_failed(self, session_id: str, error: str) -> bool:
        """Mark a session as failed.

        Args:
            session_id: The session ID to update
            error: Error message describing the failure

        Returns:
            True if updated, False if not found or no database
        """
        db_session = self._get_session()
        if db_session is None:
            return False

        with db_session:
            stmt = select(Session).where(Session.id == session_id)
            session_obj = db_session.execute(stmt).scalar_one_or_none()
            if session_obj:
                session_obj.mark_failed(error)
                db_session.commit()
                return True
            return False

    def update_output_dir(self, session_id: str, output_dir: Path | str) -> bool:
        """Update the output directory for a session.

        Args:
            session_id: The session ID to update
            output_dir: New output directory path

        Returns:
            True if updated, False if not found or no database
        """
        db_session = self._get_session()
        if db_session is None:
            return False

        with db_session:
            stmt = select(Session).where(Session.id == session_id)
            session_obj = db_session.execute(stmt).scalar_one_or_none()
            if session_obj:
                session_obj.output_dir = str(output_dir)
                db_session.commit()
                return True
            return False
