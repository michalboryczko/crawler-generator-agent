"""In-memory repository implementation using SQLAlchemy ORM model objects.

This repository stores MemoryEntry ORM objects in a dictionary for
fast, transient storage during development and testing.
"""

import fnmatch
from datetime import UTC, datetime
from typing import Any

from ..models.memory import MemoryEntry
from .base import AbstractMemoryRepository


class InMemoryRepository(AbstractMemoryRepository):
    """In-memory repository storing SQLAlchemy model objects.

    Data is stored in a dictionary keyed by composite key
    (session_id:agent_name:key). This provides the same isolation
    semantics as the SQL backend without database overhead.

    Note: Data is not persisted between process restarts.
    """

    def __init__(self) -> None:
        """Initialize an empty in-memory repository."""
        self._entries: dict[str, MemoryEntry] = {}
        self._id_counter = 0

    def _make_composite_key(
        self, session_id: str, agent_name: str, key: str
    ) -> str:
        """Create composite key for internal storage."""
        return f"{session_id}:{agent_name}:{key}"

    def _get_prefix(self, session_id: str, agent_name: str) -> str:
        """Get prefix for filtering entries by session/agent."""
        return f"{session_id}:{agent_name}:"

    def get(self, session_id: str, agent_name: str, key: str) -> MemoryEntry | None:
        """Retrieve a memory entry by key."""
        composite_key = self._make_composite_key(session_id, agent_name, key)
        return self._entries.get(composite_key)

    def save(self, entry: MemoryEntry) -> MemoryEntry:
        """Save or update a memory entry."""
        composite_key = self._make_composite_key(
            entry.session_id, entry.agent_name, entry.key
        )
        existing = self._entries.get(composite_key)

        now = datetime.now(UTC)

        if existing:
            # Update existing entry
            existing.value = entry.value
            existing.updated_at = now
            return existing
        else:
            # Create new entry
            self._id_counter += 1
            entry.id = self._id_counter
            entry.created_at = now
            entry.updated_at = now
            self._entries[composite_key] = entry
            return entry

    def delete(self, session_id: str, agent_name: str, key: str) -> bool:
        """Delete a memory entry by key."""
        composite_key = self._make_composite_key(session_id, agent_name, key)
        if composite_key in self._entries:
            del self._entries[composite_key]
            return True
        return False

    def find_by_pattern(
        self, session_id: str, agent_name: str, pattern: str
    ) -> list[str]:
        """Find keys matching a glob pattern."""
        prefix = self._get_prefix(session_id, agent_name)
        prefix_len = len(prefix)

        results = []
        for composite_key in self._entries:
            if composite_key.startswith(prefix):
                key = composite_key[prefix_len:]
                if fnmatch.fnmatch(key, pattern):
                    results.append(key)

        return sorted(results)

    def list_keys(self, session_id: str, agent_name: str) -> list[str]:
        """List all keys for a session/agent."""
        prefix = self._get_prefix(session_id, agent_name)
        prefix_len = len(prefix)

        keys = [
            composite_key[prefix_len:]
            for composite_key in self._entries
            if composite_key.startswith(prefix)
        ]
        return sorted(keys)

    def clear(self, session_id: str, agent_name: str) -> int:
        """Clear all entries for a session/agent."""
        prefix = self._get_prefix(session_id, agent_name)
        keys_to_delete = [
            k for k in self._entries if k.startswith(prefix)
        ]

        for k in keys_to_delete:
            del self._entries[k]

        return len(keys_to_delete)

    def bulk_get(
        self, session_id: str, agent_name: str, keys: list[str]
    ) -> dict[str, Any]:
        """Get multiple values at once."""
        result = {}
        for key in keys:
            entry = self.get(session_id, agent_name, key)
            if entry is not None:
                result[key] = entry.value
        return result

    def bulk_save(self, entries: list[MemoryEntry]) -> int:
        """Save multiple entries at once."""
        count = 0
        for entry in entries:
            self.save(entry)
            count += 1
        return count

    def __len__(self) -> int:
        """Return total number of entries in repository."""
        return len(self._entries)

    def clear_all(self) -> int:
        """Clear all entries (for testing)."""
        count = len(self._entries)
        self._entries.clear()
        self._id_counter = 0
        return count
