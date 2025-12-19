"""Base tool abstraction for all agent tools."""

import logging
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


class BaseTool(ABC):
    """Abstract base class for all tools.

    Subclasses must implement:
        - name: Tool identifier used in function calling
        - description: Human-readable description for LLM
        - execute(): Tool execution logic
        - get_parameters_schema(): JSON schema for parameters
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Tool identifier used in function calling."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description for LLM."""
        pass

    @abstractmethod
    def execute(self, **kwargs: Any) -> dict[str, Any]:
        """Execute the tool with given parameters.

        Returns:
            dict with 'success' bool and 'result' or 'error' key
        """
        pass

    def to_openai_schema(self) -> dict[str, Any]:
        """Convert tool to OpenAI function calling schema."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.get_parameters_schema(),
            },
        }

    @abstractmethod
    def get_parameters_schema(self) -> dict[str, Any]:
        """Return JSON schema for tool parameters."""
        pass
