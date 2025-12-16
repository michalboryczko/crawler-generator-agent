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
"""

from .provider import PromptProvider, get_prompt_provider
from .registry import PromptInfo, PromptRegistry

__all__ = [
    "PromptInfo",
    "PromptProvider",
    "PromptRegistry",
    "get_prompt_provider",
]
