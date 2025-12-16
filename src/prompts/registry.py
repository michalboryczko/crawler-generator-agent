"""Prompt registry for storing and managing prompt definitions."""

from dataclasses import dataclass
from typing import Any


@dataclass
class PromptInfo:
    """Metadata about a registered prompt."""

    name: str
    version: str
    category: str  # 'agent', 'extraction', 'selector'
    description: str
    has_template: bool = False


class PromptRegistry:
    """Registry for storing all prompt definitions.

    Supports versioning and categorization of prompts.
    """

    _instance: "PromptRegistry | None" = None

    def __init__(self) -> None:
        self._prompts: dict[str, dict[str, Any]] = {}

    @classmethod
    def get_instance(cls) -> "PromptRegistry":
        """Get singleton instance of the registry."""
        if cls._instance is None:
            cls._instance = cls()
            cls._instance._load_defaults()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton instance (for testing)."""
        cls._instance = None

    def register_prompt(
        self,
        name: str,
        content: str,
        version: str = "1.0.0",
        category: str = "general",
        description: str = "",
    ) -> None:
        """Register a prompt with the registry.

        Args:
            name: Unique prompt identifier (e.g., 'agent.main')
            content: The prompt content
            version: Semantic version string
            category: Category for filtering ('agent', 'extraction', 'selector')
            description: Human-readable description
        """
        self._prompts[name] = {
            "content": content,
            "version": version,
            "category": category,
            "description": description,
        }

    def get_prompt(self, name: str) -> str:
        """Get prompt content by name.

        Args:
            name: The prompt identifier

        Returns:
            The prompt content string

        Raises:
            KeyError: If prompt not found
        """
        if name not in self._prompts:
            raise KeyError(f"Unknown prompt: {name}")
        return self._prompts[name]["content"]

    def get_prompt_version(self, name: str) -> str:
        """Get version of a registered prompt."""
        if name not in self._prompts:
            raise KeyError(f"Unknown prompt: {name}")
        return self._prompts[name]["version"]

    def list_prompts(self, category: str | None = None) -> list[PromptInfo]:
        """List all prompts, optionally filtered by category.

        Args:
            category: Optional category filter

        Returns:
            List of PromptInfo objects
        """
        result = []
        for name, data in self._prompts.items():
            if category is None or data["category"] == category:
                result.append(
                    PromptInfo(
                        name=name,
                        version=data["version"],
                        category=data["category"],
                        description=data["description"],
                    )
                )
        return result

    def has_prompt(self, name: str) -> bool:
        """Check if a prompt exists."""
        return name in self._prompts

    def _load_defaults(self) -> None:
        """Load default prompts from template modules."""
        from .templates import agents, extraction

        agents.register_agent_prompts(self)
        extraction.register_extraction_prompts(self)
