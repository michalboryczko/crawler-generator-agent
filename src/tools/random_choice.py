"""Random choice tool for sampling from lists."""
import logging
import random
from typing import Any

from .base import BaseTool
from ..core.log_context import get_logger
from ..core.structured_logger import EventCategory, LogEvent

logger = logging.getLogger(__name__)


class RandomChoiceTool(BaseTool):
    """Randomly pick items from a list."""

    name = "random_choice"
    description = "Randomly pick N items from a list of candidates. Useful for sampling without bias."

    def execute(
        self,
        candidates: list[Any],
        count: int
    ) -> dict[str, Any]:
        """Pick random items from candidates.

        Args:
            candidates: List of items to choose from
            count: Number of items to pick

        Returns:
            Dict with success status and picked items
        """
        slog = get_logger()

        try:
            if not candidates:
                return {"success": False, "error": "Candidates list is empty"}

            if count <= 0:
                return {"success": False, "error": "Count must be positive"}

            actual_count = count
            if count > len(candidates):
                logger.warning(
                    f"Requested {count} items but only {len(candidates)} available. "
                    "Returning all candidates."
                )
                actual_count = len(candidates)

            picked = random.sample(candidates, actual_count)
            logger.info(f"Randomly picked {len(picked)} items from {len(candidates)} candidates")

            if slog:
                slog.info(
                    event=LogEvent(
                        category=EventCategory.TOOL_EXECUTION,
                        event_type="tool.random_choice.complete",
                        name="Random selection completed",
                    ),
                    message=f"Picked {len(picked)} items from {len(candidates)} candidates",
                    data={
                        "requested_count": count,
                        "actual_count": len(picked),
                        "total_candidates": len(candidates),
                    },
                    tags=["random", "sampling", "success"],
                )

            return {
                "success": True,
                "result": picked,
                "count": len(picked),
                "total_candidates": len(candidates)
            }
        except Exception as e:
            if slog:
                slog.error(
                    event=LogEvent(
                        category=EventCategory.ERROR,
                        event_type="tool.random_choice.error",
                        name="Random selection failed",
                    ),
                    message=f"Failed to pick random items: {e}",
                    data={"error": str(e)},
                    tags=["random", "sampling", "error"],
                )
            return {"success": False, "error": str(e)}

    def get_parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "candidates": {
                    "type": "array",
                    "items": {},
                    "description": "List of items to choose from"
                },
                "count": {
                    "type": "integer",
                    "description": "Number of items to randomly pick"
                }
            },
            "required": ["candidates", "count"]
        }
