"""Centralized prompt management system.

This module provides the PromptProvider interface for accessing
all prompts (static and dynamic) used throughout the system.

Usage:
    from src.prompts import get_prompt_provider

    provider = get_prompt_provider()

    # Get static agent prompt
    prompt = provider.get_agent_prompt('main')

    # Get static extraction prompt
    prompt = provider.get_extraction_prompt('listing')

    # Render dynamic template
    prompt = provider.render_prompt('pagination_pattern', target_url=url, links=links)

    # Render shared templates (contract summaries, sub-agent sections, etc.)
    from src.prompts import render_template
    render_template('sub_agents_section.md.j2', agent_tools=tools)
"""

from .provider import PromptProvider, get_prompt_provider
from .registry import PromptInfo, PromptRegistry
from .template_renderer import get_template_env, render_template

__all__ = [
    "PromptInfo",
    "PromptProvider",
    "PromptRegistry",
    "get_prompt_provider",
    # Template rendering
    "get_template_env",
    "render_template",
]
