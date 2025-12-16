"""SQLAlchemy repository implementation for persistent storage.

This repository persists MemoryEntry objects to SQL databases
(MySQL, PostgreSQL, SQLite) using SQLAlchemy 2.0 ORM.
"""

import fnmatch
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session, sessionmaker

from ..models.memory import MemoryEntry
from .base import AbstractMemoryRepository


class SQLAlchemyRepository(AbstractMemoryRepository):
    """SQLAlchemy repository for persistent memory storage.

    Supports MySQL, PostgreSQL, and SQLite backends via connection string.
    Uses SQLAlchemy 2.0 style queries with type-safe select statements.

    Example connection strings:
        - MySQL: mysql+mysqlconnector://user:pass@localhost/db
        - PostgreSQL: postgresql://user:pass@localhost/db
        - SQLite: sqlite:///./crawler.db
    """

    def __init__(
        self,
        connection_string: str,
        echo: bool = False,
    ) -> None:
        """Initialize SQLAlchemy repository.

        Args:
            connection_string: SQLAlchemy database URL
            echo: If True, log all SQL statements

        Note:
            Database tables must be created via Alembic migrations before use.
            Run: alembic upgrade head
        """
        self.engine = create_engine(connection_string, echo=echo)
        self._session_factory = sessionmaker(
            bind=self.engine,
            expire_on_commit=False,
        )

    def _get_session(self) -> Session:
        """Get a new database session."""
        return self._session_factory()

    def get(self, session_id: str, agent_name: str, key: str) -> MemoryEntry | None:
        """Retrieve a memory entry by key."""
        with self._get_session() as session:
            stmt = select(MemoryEntry).where(
                MemoryEntry.session_id == session_id,
                MemoryEntry.agent_name == agent_name,
                MemoryEntry.key == key,
            )
            result = session.execute(stmt).scalar_one_or_none()

            if result:
                # Detach from session to allow use outside context
                session.expunge(result)

            return result

    def save(self, entry: MemoryEntry) -> MemoryEntry:
        """Save or update a memory entry (upsert)."""
        with self._get_session() as session:
            # Check for existing entry
            stmt = select(MemoryEntry).where(
                MemoryEntry.session_id == entry.session_id,
                MemoryEntry.agent_name == entry.agent_name,
                MemoryEntry.key == entry.key,
            )
            existing = session.execute(stmt).scalar_one_or_none()

            now = datetime.now(UTC)

            if existing:
                # Update existing
                existing.value = entry.value
                existing.updated_at = now
                session.commit()
                session.expunge(existing)
                return existing
            else:
                # Insert new
                entry.created_at = now
                entry.updated_at = now
                session.add(entry)
                session.commit()
                session.expunge(entry)
                return entry

    def delete(self, session_id: str, agent_name: str, key: str) -> bool:
        """Delete a memory entry by key."""
        with self._get_session() as session:
            stmt = delete(MemoryEntry).where(
                MemoryEntry.session_id == session_id,
                MemoryEntry.agent_name == agent_name,
                MemoryEntry.key == key,
            )
            result = session.execute(stmt)
            session.commit()
            return result.rowcount > 0

    def find_by_pattern(
        self, session_id: str, agent_name: str, pattern: str
    ) -> list[str]:
        """Find keys matching a glob pattern.

        Note: Uses in-memory filtering with fnmatch for glob compatibility.
        For large datasets, consider SQL LIKE patterns instead.
        """
        # Get all keys and filter with fnmatch
        all_keys = self.list_keys(session_id, agent_name)
        return sorted(k for k in all_keys if fnmatch.fnmatch(k, pattern))

    def list_keys(self, session_id: str, agent_name: str) -> list[str]:
        """List all keys for a session/agent."""
        with self._get_session() as session:
            stmt = select(MemoryEntry.key).where(
                MemoryEntry.session_id == session_id,
                MemoryEntry.agent_name == agent_name,
            ).order_by(MemoryEntry.key)

            result = session.execute(stmt).scalars().all()
            return list(result)

    def clear(self, session_id: str, agent_name: str) -> int:
        """Clear all entries for a session/agent."""
        with self._get_session() as session:
            stmt = delete(MemoryEntry).where(
                MemoryEntry.session_id == session_id,
                MemoryEntry.agent_name == agent_name,
            )
            result = session.execute(stmt)
            session.commit()
            return result.rowcount

    def bulk_get(
        self, session_id: str, agent_name: str, keys: list[str]
    ) -> dict[str, Any]:
        """Get multiple values at once."""
        if not keys:
            return {}

        with self._get_session() as session:
            stmt = select(MemoryEntry).where(
                MemoryEntry.session_id == session_id,
                MemoryEntry.agent_name == agent_name,
                MemoryEntry.key.in_(keys),
            )
            entries = session.execute(stmt).scalars().all()
            return {entry.key: entry.value for entry in entries}

    def bulk_save(self, entries: list[MemoryEntry]) -> int:
        """Save multiple entries at once."""
        if not entries:
            return 0

        with self._get_session() as session:
            now = datetime.now(UTC)
            count = 0

            for entry in entries:
                # Check for existing
                stmt = select(MemoryEntry).where(
                    MemoryEntry.session_id == entry.session_id,
                    MemoryEntry.agent_name == entry.agent_name,
                    MemoryEntry.key == entry.key,
                )
                existing = session.execute(stmt).scalar_one_or_none()

                if existing:
                    existing.value = entry.value
                    existing.updated_at = now
                else:
                    entry.created_at = now
                    entry.updated_at = now
                    session.add(entry)

                count += 1

            session.commit()
            return count

    def clear_session(self, session_id: str) -> int:
        """Clear all entries for an entire session (all agents)."""
        with self._get_session() as session:
            stmt = delete(MemoryEntry).where(
                MemoryEntry.session_id == session_id,
            )
            result = session.execute(stmt)
            session.commit()
            return result.rowcount

    def close(self) -> None:
        """Close the database engine."""
        self.engine.dispose()
