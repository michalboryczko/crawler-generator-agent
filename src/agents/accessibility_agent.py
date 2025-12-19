"""Accessibility Validation Agent to check if site works without JavaScript.

This agent inherits from BaseAgent which uses the @traced_agent decorator
for automatic observability instrumentation.
"""
from typing import TYPE_CHECKING

from src.prompts import get_prompt_provider

from ..core.llm import LLMClient
from ..tools.agent_tools import ValidateResponseTool
from ..tools.http import HTTPRequestTool
from ..tools.memory import (
    MemoryReadTool,
    MemoryWriteTool,
)
from .base import BaseAgent

if TYPE_CHECKING:
    from ..services.memory_service import MemoryService


class AccessibilityAgent(BaseAgent):
    """Agent to validate if site content is accessible via HTTP."""

    name = "accessibility_agent"
    description = "Checks if site content is accessible via HTTP without JavaScript"
    system_prompt = get_prompt_provider().get_agent_prompt("accessibility")

    def __init__(
        self,
        llm: LLMClient,
        memory_service: "MemoryService",
    ):
        tools = [
            HTTPRequestTool(),
            MemoryReadTool(memory_service),
            MemoryWriteTool(memory_service),
            # Contract validation
            ValidateResponseTool(),
        ]

        super().__init__(llm, tools, memory_service=memory_service)
