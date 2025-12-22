"""Random choice tool for sampling from lists.

This module uses the new observability decorators for automatic logging.
The @traced_tool decorator handles all tool instrumentation.
"""

import logging
import random
from typing import Any

from ..observability.decorators import traced_tool
from .base import BaseTool
from .validation import validated_tool

logger = logging.getLogger(__name__)


class RandomChoiceTool(BaseTool):
    """Randomly pick items from a list."""

    name = "random_choice"
    description = (
        "Randomly pick N items from a list of candidates. Useful for sampling without bias."
    )

    @traced_tool(name="random_choice")
    @validated_tool
    def execute(self, **kwargs: Any) -> dict[str, Any]:
        """Pick random items from candidates. Instrumented by @traced_tool."""
        candidates = kwargs["candidates"]
        count = kwargs["count"]
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

        return {
            "success": True,
            "result": picked,
            "count": len(picked),
            "total_candidates": len(candidates),
        }
