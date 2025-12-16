"""Main PromptProvider interface for centralized prompt access."""

from typing import Any

from .registry import PromptInfo, PromptRegistry
from .template import PromptTemplate


class PromptProvider:
    """Centralized prompt management.

    Provides access to both static prompts (from registry) and
    dynamic templates (rendered with context).

    Example:
        provider = get_prompt_provider()

        # Static prompt
        prompt = provider.get_agent_prompt('main')

        # Dynamic template
        prompt = provider.render_prompt('pagination', target_url=url, links=links)
    """

    def __init__(self, registry: PromptRegistry | None = None) -> None:
        """Initialize provider.

        Args:
            registry: PromptRegistry instance (uses singleton if None)
        """
        self._registry = registry or PromptRegistry.get_instance()
        self._templates: dict[str, PromptTemplate] = {}

    # Static prompts
    def get_agent_prompt(self, agent_name: str) -> str:
        """Get system prompt for an agent.

        Args:
            agent_name: Agent identifier (main, browser, selector, accessibility, data_prep)

        Returns:
            The agent's system prompt

        Raises:
            KeyError: If agent prompt not found
        """
        key = f"agent.{agent_name}"
        return self._registry.get_prompt(key)

    def get_extraction_prompt(self, extraction_type: str) -> str:
        """Get extraction prompt (listing or article).

        Args:
            extraction_type: Either 'listing' or 'article'

        Returns:
            The extraction prompt

        Raises:
            KeyError: If extraction prompt not found
        """
        key = f"extraction.{extraction_type}"
        return self._registry.get_prompt(key)

    def get_prompt(self, name: str) -> str:
        """Get any prompt by full name.

        Args:
            name: Full prompt name (e.g., 'agent.main', 'extraction.listing')

        Returns:
            The prompt content
        """
        return self._registry.get_prompt(name)

    # Dynamic prompts (template + context)
    def render_prompt(self, template_name: str, **context: Any) -> str:
        """Render a dynamic prompt template with context.

        Args:
            template_name: Registered template name
            **context: Variable values for the template

        Returns:
            Rendered prompt string

        Raises:
            KeyError: If template not found
            ValueError: If required context variables missing
        """
        if template_name not in self._templates:
            raise KeyError(f"Unknown template: {template_name}")
        template = self._templates[template_name]
        missing = template.validate_context(context)
        if missing:
            raise ValueError(f"Missing context variables for {template_name}: {missing}")
        return template.render(**context)

    def register_template(self, name: str, template: PromptTemplate) -> None:
        """Register a dynamic template.

        Args:
            name: Template identifier
            template: PromptTemplate instance
        """
        self._templates[name] = template

    def has_template(self, name: str) -> bool:
        """Check if a template is registered."""
        return name in self._templates

    # Metadata
    def list_prompts(self, category: str | None = None) -> list[PromptInfo]:
        """List all registered prompts.

        Args:
            category: Optional filter by category

        Returns:
            List of PromptInfo objects
        """
        return self._registry.list_prompts(category)

    def list_templates(self) -> list[str]:
        """List all registered template names."""
        return list(self._templates.keys())

    def get_prompt_version(self, name: str) -> str:
        """Get version of a registered prompt."""
        return self._registry.get_prompt_version(name)


# Module-level singleton access
_provider_instance: PromptProvider | None = None


def _register_all_templates(provider: PromptProvider) -> None:
    """Register all dynamic templates with the provider."""
    from .templates.dynamic import register_dynamic_templates

    register_dynamic_templates(provider)


def get_prompt_provider() -> PromptProvider:
    """Get the singleton PromptProvider instance.

    Returns:
        The global PromptProvider instance
    """
    global _provider_instance
    if _provider_instance is None:
        _provider_instance = PromptProvider()
        _register_all_templates(_provider_instance)
    return _provider_instance


def reset_prompt_provider() -> None:
    """Reset the singleton instance (for testing)."""
    global _provider_instance
    _provider_instance = None
    PromptRegistry.reset_instance()
