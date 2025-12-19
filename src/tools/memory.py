"""Memory tools for storing and retrieving data across agent calls.

Tools are thin controllers that delegate to MemoryService.
The @traced_tool decorator handles all tool instrumentation.

Usage:
    from src.infrastructure import Container

    container = Container.create_inmemory()
    service = container.memory_service('browser')
    tool = MemoryReadTool(service)
"""

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..observability.decorators import traced_tool
from .base import BaseTool

if TYPE_CHECKING:
    from ..services.memory_service import MemoryService

logger = logging.getLogger(__name__)


class MemoryReadTool(BaseTool):
    """Read from shared memory."""

    name = "memory_read"
    description = "Read a value from shared memory by key. Returns null if key doesn't exist."

    def __init__(self, service: "MemoryService") -> None:
        self._service = service

    @traced_tool(name="memory_read")
    def execute(self, key: str) -> dict[str, Any]:
        """Read from memory."""
        value = self._service.read(key)
        return {
            "success": True,
            "result": value,
            "found": value is not None,
        }

    def get_parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "The key to read from memory",
                }
            },
            "required": ["key"],
        }


class MemoryWriteTool(BaseTool):
    """Write to shared memory."""

    name = "memory_write"
    description = "Write a value to shared memory. Overwrites existing values."

    def __init__(self, service: "MemoryService") -> None:
        self._service = service

    @traced_tool(name="memory_write")
    def execute(self, key: str, value: Any) -> dict[str, Any]:
        """Write to memory."""
        overwritten = self._service.read(key) is not None
        self._service.write(key, value)

        value_size = len(json.dumps(value, default=str)) if value else 0

        return {
            "success": True,
            "result": f"Stored value at key: {key}",
            "overwritten": overwritten,
            "value_size": value_size,
        }

    def get_parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "The key to write to",
                },
                "value": {
                    "description": "The value to store (any JSON-serializable type)",
                },
            },
            "required": ["key", "value"],
        }


class MemorySearchTool(BaseTool):
    """Search memory keys by pattern."""

    name = "memory_search"
    description = "Search for keys matching a glob pattern (e.g., 'articles.*', '*_selector')."

    def __init__(self, service: "MemoryService") -> None:
        self._service = service

    @traced_tool(name="memory_search")
    def execute(self, pattern: str) -> dict[str, Any]:
        """Search memory keys."""
        keys = self._service.search(pattern)
        return {
            "success": True,
            "result": keys,
            "count": len(keys),
        }

    def get_parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern to match keys (e.g., 'page.*', '*_url')",
                }
            },
            "required": ["pattern"],
        }


class MemoryListTool(BaseTool):
    """List all memory keys."""

    name = "memory_list"
    description = "List all keys currently stored in memory."

    def __init__(self, service: "MemoryService") -> None:
        self._service = service

    @traced_tool(name="memory_list")
    def execute(self) -> dict[str, Any]:
        """List all memory keys."""
        keys = self._service.list_keys()
        return {
            "success": True,
            "result": keys,
            "count": len(keys),
        }

    def get_parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
        }


class MemoryDumpTool(BaseTool):
    """Dump memory keys to JSONL file."""

    name = "memory_dump"
    description = (
        "Dump specified memory keys to a JSONL file. Each line contains the value of one key."
    )

    def __init__(self, service: "MemoryService", output_dir: Path) -> None:
        self._service = service
        self._output_dir = output_dir

    @traced_tool(name="memory_dump")
    def execute(self, keys: list[str], filename: str) -> dict[str, Any]:
        """Dump keys to JSONL file."""
        output_path = self._output_dir / filename
        count = self._service.dump_to_jsonl(keys, output_path)

        return {
            "success": True,
            "result": f"Dumped {count} entries to {filename}",
            "path": str(output_path),
            "count": count,
        }

    def get_parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "keys": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of memory keys to dump",
                },
                "filename": {
                    "type": "string",
                    "description": "Output filename (e.g., 'data/test_set.jsonl')",
                },
            },
            "required": ["keys", "filename"],
        }
