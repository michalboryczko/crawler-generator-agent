"""Accessibility Validation Agent to check if site works without JavaScript.

This agent inherits from BaseAgent which uses the @traced_agent decorator
for automatic observability instrumentation.
"""
from ..core.llm import LLMClient
from ..tools.http import HTTPRequestTool
from ..tools.memory import (
    MemoryReadTool,
    MemoryStore,
    MemoryWriteTool,
)
from .base import BaseAgent
from .prompts import ACCESSIBILITY_AGENT_PROMPT


class AccessibilityAgent(BaseAgent):
    """Agent to validate if site content is accessible via HTTP."""

    name = "accessibility_agent"
    system_prompt = ACCESSIBILITY_AGENT_PROMPT

    def __init__(
        self,
        llm: LLMClient,
        memory_store: MemoryStore | None = None
    ):
        self.memory_store = memory_store or MemoryStore()

        tools = [
            HTTPRequestTool(),
            MemoryReadTool(self.memory_store),
            MemoryWriteTool(self.memory_store),
        ]

        super().__init__(llm, tools)
