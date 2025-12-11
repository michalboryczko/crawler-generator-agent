"""Memory tool for storing and retrieving data across agent calls."""
import fnmatch
import json
import logging
from pathlib import Path
from typing import Any

from .base import BaseTool

logger = logging.getLogger(__name__)


class MemoryStore:
    """Singleton in-memory storage shared across all agents."""

    _instance = None
    _data: dict[str, Any] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._data = {}
        return cls._instance

    def read(self, key: str) -> Any | None:
        """Read value by key."""
        return self._data.get(key)

    def write(self, key: str, value: Any) -> None:
        """Write value to key."""
        self._data[key] = value
        logger.debug(f"Memory write: {key}")

    def delete(self, key: str) -> bool:
        """Delete key if exists."""
        if key in self._data:
            del self._data[key]
            return True
        return False

    def search(self, pattern: str) -> list[str]:
        """Search keys matching glob pattern."""
        return [k for k in self._data.keys() if fnmatch.fnmatch(k, pattern)]

    def list_keys(self) -> list[str]:
        """List all keys."""
        return list(self._data.keys())

    def clear(self) -> None:
        """Clear all data."""
        self._data.clear()

    def dump_to_jsonl(self, keys: list[str], output_path: Path) -> int:
        """Dump specified keys to JSONL file.

        Args:
            keys: List of keys to dump
            output_path: Path to output JSONL file

        Returns:
            Number of entries written
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        count = 0

        with output_path.open("w", encoding="utf-8") as f:
            for key in keys:
                value = self._data.get(key)
                if value is not None:
                    line = json.dumps(value, ensure_ascii=False)
                    f.write(line + "\n")
                    count += 1

        logger.info(f"Dumped {count} entries to {output_path}")
        return count


class MemoryReadTool(BaseTool):
    """Read from shared memory."""

    name = "memory_read"
    description = "Read a value from shared memory by key. Returns null if key doesn't exist."

    def __init__(self, store: MemoryStore | None = None):
        self.store = store or MemoryStore()

    def execute(self, key: str) -> dict[str, Any]:
        value = self.store.read(key)
        return {
            "success": True,
            "result": value
        }

    def get_parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "The key to read from memory"
                }
            },
            "required": ["key"]
        }


class MemoryWriteTool(BaseTool):
    """Write to shared memory."""

    name = "memory_write"
    description = "Write a value to shared memory. Overwrites existing values."

    def __init__(self, store: MemoryStore | None = None):
        self.store = store or MemoryStore()

    def execute(self, key: str, value: Any) -> dict[str, Any]:
        self.store.write(key, value)
        return {
            "success": True,
            "result": f"Stored value at key: {key}"
        }

    def get_parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "The key to write to"
                },
                "value": {
                    "description": "The value to store (any JSON-serializable type)"
                }
            },
            "required": ["key", "value"]
        }


class MemorySearchTool(BaseTool):
    """Search memory keys by pattern."""

    name = "memory_search"
    description = "Search for keys matching a glob pattern (e.g., 'articles.*', '*_selector')."

    def __init__(self, store: MemoryStore | None = None):
        self.store = store or MemoryStore()

    def execute(self, pattern: str) -> dict[str, Any]:
        keys = self.store.search(pattern)
        return {
            "success": True,
            "result": keys
        }

    def get_parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern to match keys (e.g., 'page.*', '*_url')"
                }
            },
            "required": ["pattern"]
        }


class MemoryListTool(BaseTool):
    """List all memory keys."""

    name = "memory_list"
    description = "List all keys currently stored in memory."

    def __init__(self, store: MemoryStore | None = None):
        self.store = store or MemoryStore()

    def execute(self) -> dict[str, Any]:
        keys = self.store.list_keys()
        return {
            "success": True,
            "result": keys
        }

    def get_parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {}
        }


class MemoryDumpTool(BaseTool):
    """Dump memory keys to JSONL file."""

    name = "memory_dump"
    description = "Dump specified memory keys to a JSONL file. Each line contains the value of one key."

    def __init__(self, store: MemoryStore, output_dir: Path):
        self.store = store
        self.output_dir = output_dir

    def execute(self, keys: list[str], filename: str) -> dict[str, Any]:
        """Dump keys to JSONL file.

        Args:
            keys: List of memory keys to dump
            filename: Output filename (relative to output directory)
        """
        try:
            output_path = self.output_dir / filename
            count = self.store.dump_to_jsonl(keys, output_path)
            return {
                "success": True,
                "result": f"Dumped {count} entries to {filename}",
                "path": str(output_path),
                "count": count
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "keys": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of memory keys to dump"
                },
                "filename": {
                    "type": "string",
                    "description": "Output filename (e.g., 'data/test_set.jsonl')"
                }
            },
            "required": ["keys", "filename"]
        }
