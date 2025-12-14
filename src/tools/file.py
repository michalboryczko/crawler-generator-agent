"""File tool for reading and writing files in output directory.

This module uses the new observability decorators for automatic logging.
The @traced_tool decorator handles all tool instrumentation.
"""
import logging
from pathlib import Path
from typing import Any

from .base import BaseTool
from ..observability.decorators import traced_tool

logger = logging.getLogger(__name__)


class FileCreateTool(BaseTool):
    """Create a new file with given content."""

    name = "file_create"
    description = "Create a new file with given content in the output directory."

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir

    @traced_tool(name="file_create")
    def execute(self, filename: str, content: str) -> dict[str, Any]:
        """Create a file with content. Instrumented by @traced_tool."""
        filepath = self.output_dir / filename
        # Ensure parent directories exist
        filepath.parent.mkdir(parents=True, exist_ok=True)

        if filepath.exists():
            return {
                "success": False,
                "error": f"File already exists: {filename}. Use file_replace to overwrite."
            }

        filepath.write_text(content, encoding="utf-8")
        logger.info(f"Created file: {filepath}")

        return {
            "success": True,
            "result": f"Created file: {filename}",
            "path": str(filepath)
        }

    def get_parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "Relative path to file within output directory (e.g., 'plan.md', 'data/test.jsonl')"
                },
                "content": {
                    "type": "string",
                    "description": "Content to write to the file"
                }
            },
            "required": ["filename", "content"]
        }


class FileReadTool(BaseTool):
    """Read content from a file."""

    name = "file_read"
    description = "Read content from a file in the output directory. Supports head/tail options."

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir

    @traced_tool(name="file_read")
    def execute(
        self,
        filename: str,
        head: int | None = None,
        tail: int | None = None
    ) -> dict[str, Any]:
        """Read file content with optional head/tail. Instrumented by @traced_tool."""
        filepath = self.output_dir / filename

        if not filepath.exists():
            return {"success": False, "error": f"File not found: {filename}"}

        content = filepath.read_text(encoding="utf-8")
        lines = content.splitlines()
        total_lines = len(lines)

        if head is not None:
            lines = lines[:head]
        elif tail is not None:
            lines = lines[-tail:]

        return {
            "success": True,
            "result": "\n".join(lines),
            "total_lines": total_lines,
            "returned_lines": len(lines)
        }

    def get_parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "Relative path to file within output directory"
                },
                "head": {
                    "type": "integer",
                    "description": "Return only first N lines"
                },
                "tail": {
                    "type": "integer",
                    "description": "Return only last N lines"
                }
            },
            "required": ["filename"]
        }


class FileAppendTool(BaseTool):
    """Append content to a file."""

    name = "file_append"
    description = "Append content to an existing file in the output directory."

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir

    @traced_tool(name="file_append")
    def execute(self, filename: str, content: str) -> dict[str, Any]:
        """Append content to file. Instrumented by @traced_tool."""
        filepath = self.output_dir / filename

        if not filepath.exists():
            return {
                "success": False,
                "error": f"File not found: {filename}. Use file_create first."
            }

        with filepath.open("a", encoding="utf-8") as f:
            f.write(content)

        logger.info(f"Appended to file: {filepath}")

        return {
            "success": True,
            "result": f"Appended content to: {filename}"
        }

    def get_parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "Relative path to file within output directory"
                },
                "content": {
                    "type": "string",
                    "description": "Content to append to the file"
                }
            },
            "required": ["filename", "content"]
        }


class FileReplaceTool(BaseTool):
    """Replace content of a file."""

    name = "file_replace"
    description = "Replace entire content of a file in the output directory."

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir

    @traced_tool(name="file_replace")
    def execute(self, filename: str, content: str) -> dict[str, Any]:
        """Replace file content. Instrumented by @traced_tool."""
        filepath = self.output_dir / filename
        filepath.parent.mkdir(parents=True, exist_ok=True)

        filepath.write_text(content, encoding="utf-8")
        logger.info(f"Replaced file: {filepath}")

        return {
            "success": True,
            "result": f"Replaced content of: {filename}",
            "path": str(filepath)
        }

    def get_parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "Relative path to file within output directory"
                },
                "content": {
                    "type": "string",
                    "description": "New content for the file"
                }
            },
            "required": ["filename", "content"]
        }
