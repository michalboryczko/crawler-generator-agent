"""Memory service with business logic.

This service layer handles business logic that was previously in MemoryStore:
- merge_from, export_keys, dump_to_jsonl
- Validation and transformation logic

Tools delegate to this service - tools become thin controllers.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from ..models.memory import MemoryEntry
from ..repositories.base import AbstractMemoryRepository

logger = logging.getLogger(__name__)


class MemoryService:
    """Service layer for memory operations.

    Provides business logic and orchestration on top of the repository layer.
    Each agent gets its own MemoryService instance with isolated context.

    Attributes:
        session_id: The session identifier for multi-tenant isolation
        agent_name: The agent name for agent-level isolation
    """

    def __init__(
        self,
        repository: AbstractMemoryRepository,
        session_id: str,
        agent_name: str,
    ) -> None:
        """Initialize memory service.

        Args:
            repository: The repository to use for storage
            session_id: Session identifier for isolation
            agent_name: Agent name for isolation
        """
        self._repository = repository
        self._session_id = session_id
        self._agent_name = agent_name

    @property
    def session_id(self) -> str:
        """Get the session ID."""
        return self._session_id

    @property
    def agent_name(self) -> str:
        """Get the agent name."""
        return self._agent_name

    # === Basic CRUD operations (delegate to repository) ===

    def read(self, key: str) -> Any | None:
        """Read value by key.

        Args:
            key: The memory key

        Returns:
            The value if found, None otherwise
        """
        entry = self._repository.get(self._session_id, self._agent_name, key)
        return entry.value if entry else None

    def write(self, key: str, value: Any) -> None:
        """Write value to key.

        Args:
            key: The memory key
            value: The value to store (must be JSON-serializable)
        """
        entry = MemoryEntry(
            session_id=self._session_id,
            agent_name=self._agent_name,
            key=key,
            value=value,
        )
        self._repository.save(entry)
        logger.debug(f"[{self._agent_name}] Write: {key}")

    def delete(self, key: str) -> bool:
        """Delete key if exists.

        Args:
            key: The memory key

        Returns:
            True if key was deleted, False if it didn't exist
        """
        deleted = self._repository.delete(self._session_id, self._agent_name, key)
        if deleted:
            logger.debug(f"[{self._agent_name}] Delete: {key}")
        return deleted

    def search(self, pattern: str) -> list[str]:
        """Search keys matching glob pattern.

        Args:
            pattern: Glob pattern (e.g., "articles.*", "*_url")

        Returns:
            List of matching keys
        """
        return self._repository.find_by_pattern(self._session_id, self._agent_name, pattern)

    def list_keys(self) -> list[str]:
        """List all keys.

        Returns:
            List of all keys for this agent
        """
        return self._repository.list_keys(self._session_id, self._agent_name)

    def clear(self) -> int:
        """Clear all data.

        Returns:
            Number of entries deleted
        """
        count = self._repository.clear(self._session_id, self._agent_name)
        logger.debug(f"[{self._agent_name}] Clear: {count} entries")
        return count

    # === Business logic operations ===

    def merge_from(
        self,
        source: "MemoryService",
        keys: list[str] | None = None,
    ) -> int:
        """Merge data from another service's context.

        Copies data from source service to this service. Useful for
        transferring results between agents.

        Args:
            source: Source memory service to merge from
            keys: Specific keys to merge (None = all keys)

        Returns:
            Number of keys merged
        """
        source_keys = keys or source.list_keys()
        count = 0

        for key in source_keys:
            value = source.read(key)
            if value is not None:
                self.write(key, value)
                count += 1

        logger.debug(f"[{self._agent_name}] Merged {count} keys from [{source.agent_name}]")
        return count

    def export_keys(self, keys: list[str]) -> dict[str, Any]:
        """Export specific keys as a dictionary.

        Useful for passing data explicitly between agents via AgentResult.

        Args:
            keys: List of keys to export

        Returns:
            Dictionary with key-value pairs (only existing keys included)
        """
        return self._repository.bulk_get(self._session_id, self._agent_name, keys)

    def import_data(self, data: dict[str, Any]) -> int:
        """Import data from a dictionary.

        Args:
            data: Dictionary of key-value pairs to import

        Returns:
            Number of entries imported
        """
        entries = [
            MemoryEntry(
                session_id=self._session_id,
                agent_name=self._agent_name,
                key=k,
                value=v,
            )
            for k, v in data.items()
        ]
        return self._repository.bulk_save(entries)

    def dump_to_jsonl(self, keys: list[str], output_path: Path) -> int:
        """Dump specified keys to JSONL file.

        Each line in the output file contains a JSON-serialized value.

        Args:
            keys: List of keys to dump
            output_path: Path to output JSONL file

        Returns:
            Number of entries written
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        data = self._repository.bulk_get(self._session_id, self._agent_name, keys)
        count = 0

        with output_path.open("w", encoding="utf-8") as f:
            for key in keys:
                if key in data:
                    line = json.dumps(data[key], ensure_ascii=False)
                    f.write(line + "\n")
                    count += 1

        logger.debug(f"[{self._agent_name}] Dumped {count} entries to {output_path}")
        return count

    def get_snapshot(self) -> dict[str, Any]:
        """Get a snapshot of all memory contents.

        Returns:
            Dictionary with all key-value pairs
        """
        keys = self.list_keys()
        return self.export_keys(keys)

    # === Factory methods ===

    @classmethod
    def create_for_agent(
        cls,
        repository: AbstractMemoryRepository,
        agent_name: str,
        session_id: str | None = None,
    ) -> "MemoryService":
        """Factory to create a service for a specific agent.

        Args:
            repository: The repository to use
            agent_name: Name of the agent
            session_id: Optional session ID (generated if not provided)

        Returns:
            A new MemoryService instance
        """
        import uuid

        session_id = session_id or str(uuid.uuid4())
        return cls(repository, session_id, agent_name)

    @staticmethod
    def copy_session_memory(
        repository: AbstractMemoryRepository,
        source_session_id: str,
        target_session_id: str,
        up_to_timestamp: datetime | None = None,
    ) -> int:
        """Copy all memory entries from source session to target session.

        This is a session-level operation that copies memory from ALL agents
        in the source session. Used for --copy mode to give new session
        access to memory from previous run.

        Args:
            repository: The memory repository to use
            source_session_id: Source session ID to copy from
            target_session_id: Target session ID to copy to
            up_to_timestamp: Optional cutoff - only copy entries created
                             at or before this timestamp

        Returns:
            Number of entries copied
        """
        return repository.copy_session_memory(
            source_session_id=source_session_id,
            target_session_id=target_session_id,
            up_to_timestamp=up_to_timestamp,
        )
