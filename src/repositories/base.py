"""Abstract repository interface for memory storage.

This module defines the contract that all memory repository implementations
must follow, enabling dependency injection and storage backend swapping.
"""

from abc import ABC, abstractmethod
from typing import Any

from ..models.memory import MemoryEntry


class AbstractMemoryRepository(ABC):
    """Abstract repository for memory storage operations.

    All repository implementations (InMemory, SQLAlchemy, MongoDB) must
    implement this interface. The repository is responsible only for
    data access - business logic belongs in the service layer.

    Methods accept session_id and agent_name to support multi-tenant
    isolation at the storage level.
    """

    @abstractmethod
    def get(self, session_id: str, agent_name: str, key: str) -> MemoryEntry | None:
        """Retrieve a memory entry by key.

        Args:
            session_id: The session identifier
            agent_name: The agent name
            key: The memory key

        Returns:
            The MemoryEntry if found, None otherwise
        """
        pass

    @abstractmethod
    def save(self, entry: MemoryEntry) -> MemoryEntry:
        """Save or update a memory entry.

        If an entry with the same (session_id, agent_name, key) exists,
        it will be updated. Otherwise, a new entry is created.

        Args:
            entry: The MemoryEntry to save

        Returns:
            The saved MemoryEntry (with id populated for new entries)
        """
        pass

    @abstractmethod
    def delete(self, session_id: str, agent_name: str, key: str) -> bool:
        """Delete a memory entry by key.

        Args:
            session_id: The session identifier
            agent_name: The agent name
            key: The memory key

        Returns:
            True if an entry was deleted, False if it didn't exist
        """
        pass

    @abstractmethod
    def find_by_pattern(
        self, session_id: str, agent_name: str, pattern: str
    ) -> list[str]:
        """Find keys matching a glob pattern.

        Args:
            session_id: The session identifier
            agent_name: The agent name
            pattern: Glob pattern (e.g., "articles.*", "*_url")

        Returns:
            List of matching keys
        """
        pass

    @abstractmethod
    def list_keys(self, session_id: str, agent_name: str) -> list[str]:
        """List all keys for a session/agent.

        Args:
            session_id: The session identifier
            agent_name: The agent name

        Returns:
            List of all keys
        """
        pass

    @abstractmethod
    def clear(self, session_id: str, agent_name: str) -> int:
        """Clear all entries for a session/agent.

        Args:
            session_id: The session identifier
            agent_name: The agent name

        Returns:
            Number of entries deleted
        """
        pass

    @abstractmethod
    def bulk_get(
        self, session_id: str, agent_name: str, keys: list[str]
    ) -> dict[str, Any]:
        """Get multiple values at once.

        Args:
            session_id: The session identifier
            agent_name: The agent name
            keys: List of keys to retrieve

        Returns:
            Dictionary mapping keys to their values (missing keys omitted)
        """
        pass

    @abstractmethod
    def bulk_save(self, entries: list[MemoryEntry]) -> int:
        """Save multiple entries at once.

        Args:
            entries: List of MemoryEntry objects to save

        Returns:
            Number of entries saved
        """
        pass
