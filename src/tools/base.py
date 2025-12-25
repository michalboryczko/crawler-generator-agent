"""Base tool abstraction for all agent tools."""

import logging
from abc import ABC, abstractmethod
from typing import Any

from ..contracts.schema_parser import TOOL_SCHEMAS_PATH, load_schema

logger = logging.getLogger(__name__)


class BaseTool(ABC):
    """Abstract base class for all tools.

    Subclasses must implement:
        - name: Tool identifier used in function calling
        - description: Human-readable description for LLM
        - execute(): Tool execution logic

    Schema is loaded automatically from src/contracts/schemas/tools/{name}.schema.json
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

    def get_parameters_schema(self) -> dict[str, Any]:
        """Load JSON schema for tool parameters from file.

        Schema file location: src/contracts/schemas/tools/{self.name}.schema.json
        Override this method for tools with dynamic schemas (e.g., AgentTool).
        """
        return load_schema(TOOL_SCHEMAS_PATH / f"{self.name}.schema.json")
