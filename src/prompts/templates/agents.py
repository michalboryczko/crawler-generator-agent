"""Agent system prompts.

These prompts define the behavior and capabilities of each agent in the system.
Prompt content is loaded from template files in the agents/ directory.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..registry import PromptRegistry


def register_agent_prompts(registry: "PromptRegistry") -> None:
    """Register all agent prompts with the registry.

    Loads prompt content from template files in the agents/ directory.
    """
    from ..registry import load_agent_template

    prompts = [
        ("agent.main", "main_agent", "Main orchestrator agent"),
        ("agent.discovery", "discovery_agent", "Site discovery and navigation agent"),
        ("agent.selector", "selector_agent", "CSS selector discovery agent"),
        ("agent.accessibility", "accessibility_agent", "HTTP accessibility checker"),
        ("agent.data_prep", "data_prep_agent", "Test data preparation agent"),
    ]
    for name, template_name, description in prompts:
        registry.register_prompt(
            name=name,
            content=load_agent_template(template_name),
            version="1.0.0",
            category="agent",
            description=description,
        )
