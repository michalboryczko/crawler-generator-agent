"""Agent implementations for the crawler system.

This module provides agent classes that orchestrate browser operations,
selector discovery, accessibility checking, and data preparation.

Key exports:
    - AgentResult: Result dataclass for explicit data passing between agents
    - MAIN_AGENT_PROMPT, etc: System prompts for agents (via PromptProvider)
"""

from .result import AgentResult

__all__ = [
    "AgentResult",
]
