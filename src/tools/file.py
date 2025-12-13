"""File tool for reading and writing files in output directory."""
import logging
import time
from pathlib import Path
from typing import Any

from .base import BaseTool
from ..core.log_context import get_logger
from ..core.structured_logger import EventCategory, LogEvent

logger = logging.getLogger(__name__)


class FileCreateTool(BaseTool):
    """Create a new file with given content."""

    name = "file_create"
    description = "Create a new file with given content in the output directory."

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir

    def execute(self, filename: str, content: str) -> dict[str, Any]:
        """Create a file with content."""
        slog = get_logger()
        start_time = time.perf_counter()

        try:
            filepath = self.output_dir / filename
            # Ensure parent directories exist
            filepath.parent.mkdir(parents=True, exist_ok=True)

            if filepath.exists():
                if slog:
                    slog.warning(
                        event=LogEvent(
                            category=EventCategory.TOOL_EXECUTION,
                            event_type="tool.file.create.exists",
                            name="File already exists",
                        ),
                        message=f"File already exists: {filename}",
                        data={"filename": filename, "path": str(filepath)},
                        tags=["file", "create", "exists"],
                    )
                return {
                    "success": False,
                    "error": f"File already exists: {filename}. Use file_replace to overwrite."
                }

            filepath.write_text(content, encoding="utf-8")
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.info(f"Created file: {filepath}")

            if slog:
                slog.info(
                    event=LogEvent(
                        category=EventCategory.TOOL_EXECUTION,
                        event_type="tool.file.create.complete",
                        name="File created",
                    ),
                    message=f"Created file: {filename}",
                    data={"filename": filename, "path": str(filepath), "size_bytes": len(content)},
                    tags=["file", "create", "success"],
                    duration_ms=duration_ms,
                )

            return {
                "success": True,
                "result": f"Created file: {filename}",
                "path": str(filepath)
            }
        except Exception as e:
            if slog:
                slog.error(
                    event=LogEvent(
                        category=EventCategory.ERROR,
                        event_type="tool.file.create.error",
                        name="File create failed",
                    ),
                    message=f"Failed to create file: {e}",
                    data={"filename": filename, "error": str(e)},
                    tags=["file", "create", "error"],
                )
            return {"success": False, "error": str(e)}

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

    def execute(
        self,
        filename: str,
        head: int | None = None,
        tail: int | None = None
    ) -> dict[str, Any]:
        """Read file content with optional head/tail."""
        slog = get_logger()
        start_time = time.perf_counter()

        try:
            filepath = self.output_dir / filename

            if not filepath.exists():
                if slog:
                    slog.warning(
                        event=LogEvent(
                            category=EventCategory.TOOL_EXECUTION,
                            event_type="tool.file.read.not_found",
                            name="File not found",
                        ),
                        message=f"File not found: {filename}",
                        data={"filename": filename},
                        tags=["file", "read", "not_found"],
                    )
                return {"success": False, "error": f"File not found: {filename}"}

            content = filepath.read_text(encoding="utf-8")
            lines = content.splitlines()
            total_lines = len(lines)

            if head is not None:
                lines = lines[:head]
            elif tail is not None:
                lines = lines[-tail:]

            duration_ms = (time.perf_counter() - start_time) * 1000

            if slog:
                slog.info(
                    event=LogEvent(
                        category=EventCategory.TOOL_EXECUTION,
                        event_type="tool.file.read.complete",
                        name="File read",
                    ),
                    message=f"Read file: {filename}",
                    data={
                        "filename": filename,
                        "total_lines": total_lines,
                        "returned_lines": len(lines),
                        "head": head,
                        "tail": tail,
                    },
                    tags=["file", "read", "success"],
                    duration_ms=duration_ms,
                )

            return {
                "success": True,
                "result": "\n".join(lines),
                "total_lines": total_lines,
                "returned_lines": len(lines)
            }
        except Exception as e:
            if slog:
                slog.error(
                    event=LogEvent(
                        category=EventCategory.ERROR,
                        event_type="tool.file.read.error",
                        name="File read failed",
                    ),
                    message=f"Failed to read file: {e}",
                    data={"filename": filename, "error": str(e)},
                    tags=["file", "read", "error"],
                )
            return {"success": False, "error": str(e)}

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

    def execute(self, filename: str, content: str) -> dict[str, Any]:
        """Append content to file."""
        slog = get_logger()
        start_time = time.perf_counter()

        try:
            filepath = self.output_dir / filename

            if not filepath.exists():
                if slog:
                    slog.warning(
                        event=LogEvent(
                            category=EventCategory.TOOL_EXECUTION,
                            event_type="tool.file.append.not_found",
                            name="File not found for append",
                        ),
                        message=f"File not found: {filename}",
                        data={"filename": filename},
                        tags=["file", "append", "not_found"],
                    )
                return {
                    "success": False,
                    "error": f"File not found: {filename}. Use file_create first."
                }

            with filepath.open("a", encoding="utf-8") as f:
                f.write(content)

            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.info(f"Appended to file: {filepath}")

            if slog:
                slog.info(
                    event=LogEvent(
                        category=EventCategory.TOOL_EXECUTION,
                        event_type="tool.file.append.complete",
                        name="File appended",
                    ),
                    message=f"Appended to file: {filename}",
                    data={"filename": filename, "appended_bytes": len(content)},
                    tags=["file", "append", "success"],
                    duration_ms=duration_ms,
                )

            return {
                "success": True,
                "result": f"Appended content to: {filename}"
            }
        except Exception as e:
            if slog:
                slog.error(
                    event=LogEvent(
                        category=EventCategory.ERROR,
                        event_type="tool.file.append.error",
                        name="File append failed",
                    ),
                    message=f"Failed to append to file: {e}",
                    data={"filename": filename, "error": str(e)},
                    tags=["file", "append", "error"],
                )
            return {"success": False, "error": str(e)}

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

    def execute(self, filename: str, content: str) -> dict[str, Any]:
        """Replace file content."""
        slog = get_logger()
        start_time = time.perf_counter()

        try:
            filepath = self.output_dir / filename
            filepath.parent.mkdir(parents=True, exist_ok=True)

            filepath.write_text(content, encoding="utf-8")
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.info(f"Replaced file: {filepath}")

            if slog:
                slog.info(
                    event=LogEvent(
                        category=EventCategory.TOOL_EXECUTION,
                        event_type="tool.file.replace.complete",
                        name="File replaced",
                    ),
                    message=f"Replaced file: {filename}",
                    data={"filename": filename, "path": str(filepath), "size_bytes": len(content)},
                    tags=["file", "replace", "success"],
                    duration_ms=duration_ms,
                )

            return {
                "success": True,
                "result": f"Replaced content of: {filename}",
                "path": str(filepath)
            }
        except Exception as e:
            if slog:
                slog.error(
                    event=LogEvent(
                        category=EventCategory.ERROR,
                        event_type="tool.file.replace.error",
                        name="File replace failed",
                    ),
                    message=f"Failed to replace file: {e}",
                    data={"filename": filename, "error": str(e)},
                    tags=["file", "replace", "error"],
                )
            return {"success": False, "error": str(e)}

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
