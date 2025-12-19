"""System prompts for all agents.

DEPRECATED: Import directly from src.prompts instead.
This module is kept for backward compatibility only.

Usage (preferred):
    from src.prompts import get_prompt_provider
    provider = get_prompt_provider()
    prompt = provider.get_agent_prompt('main')

Legacy usage (deprecated):
    from src.agents.prompts import MAIN_AGENT_PROMPT
"""

import warnings

from src.prompts import get_prompt_provider

warnings.warn(
    "Importing from src.agents.prompts is deprecated. "
    "Use src.prompts.get_prompt_provider() instead.",
    DeprecationWarning,
    stacklevel=2,
)

# Lazy-loaded prompt constants for backward compatibility
# These are properties that fetch from PromptProvider on access


class _PromptProxy:
    """Proxy class that fetches prompts from PromptProvider on access."""

    def __init__(self, agent_name: str) -> None:
        self._agent_name = agent_name
        self._cached: str | None = None

    def __str__(self) -> str:
        if self._cached is None:
            provider = get_prompt_provider()
            self._cached = provider.get_agent_prompt(self._agent_name)
        return self._cached

    def __repr__(self) -> str:
        return f"_PromptProxy({self._agent_name!r})"

    # Support string operations
    def __add__(self, other: str) -> str:
        return str(self) + other

    def __radd__(self, other: str) -> str:
        return other + str(self)

    def __len__(self) -> int:
        return len(str(self))

    def __contains__(self, item: str) -> bool:
        return item in str(self)

    def __getattr__(self, name: str) -> object:
        # Delegate string methods to the actual string
        return getattr(str(self), name)


# Backward-compatible exports - these work like string constants
# but fetch from PromptProvider on first access
MAIN_AGENT_PROMPT: str = _PromptProxy("main")  # type: ignore[assignment]
BROWSER_AGENT_PROMPT: str = _PromptProxy("browser")  # type: ignore[assignment]
SELECTOR_AGENT_PROMPT: str = _PromptProxy("selector")  # type: ignore[assignment]
ACCESSIBILITY_AGENT_PROMPT: str = _PromptProxy("accessibility")  # type: ignore[assignment]
DATA_PREP_AGENT_PROMPT: str = _PromptProxy("data_prep")  # type: ignore[assignment]

__all__ = [
    "ACCESSIBILITY_AGENT_PROMPT",
    "BROWSER_AGENT_PROMPT",
    "DATA_PREP_AGENT_PROMPT",
    "MAIN_AGENT_PROMPT",
    "SELECTOR_AGENT_PROMPT",
]
