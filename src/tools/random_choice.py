"""Random choice tool for sampling from lists."""
import logging
import random
from typing import Any

from .base import BaseTool

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
        try:
            if not candidates:
                return {"success": False, "error": "Candidates list is empty"}

            if count <= 0:
                return {"success": False, "error": "Count must be positive"}

            if count > len(candidates):
                logger.warning(
                    f"Requested {count} items but only {len(candidates)} available. "
                    "Returning all candidates."
                )
                count = len(candidates)

            picked = random.sample(candidates, count)
            logger.info(f"Randomly picked {len(picked)} items from {len(candidates)} candidates")

            return {
                "success": True,
                "result": picked,
                "count": len(picked),
                "total_candidates": len(candidates)
            }
        except Exception as e:
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
