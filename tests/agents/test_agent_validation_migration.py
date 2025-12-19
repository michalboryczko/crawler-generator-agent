"""Tests for sub-agent validation tool migration."""

from unittest.mock import MagicMock, patch

import pytest

from src.tools.agent_tools import ValidateResponseTool


class MockLLMClient:
    """Mock LLM client for testing."""

    def chat(self, messages, tools=None):
        return {"content": "Done", "tool_calls": []}


class MockBrowserSession:
    """Mock browser session."""

    pass


class MockMemoryService:
    """Mock memory service."""

    def get_snapshot(self):
        return {}


class TestDiscoveryAgentHasValidateTool:
    """Tests for DiscoveryAgent validation tool."""

    def test_discovery_agent_has_validate_tool(self):
        """ValidateResponseTool is in DiscoveryAgent's tools list."""
        from src.agents.discovery_agent import DiscoveryAgent

        llm = MockLLMClient()
        browser = MockBrowserSession()
        memory = MockMemoryService()

        agent = DiscoveryAgent(llm=llm, browser_session=browser, memory_service=memory)

        tool_names = [t.name for t in agent.tools]
        assert "validate_response" in tool_names

    def test_discovery_agent_validate_tool_is_correct_type(self):
        """DiscoveryAgent's validate_response tool is ValidateResponseTool."""
        from src.agents.discovery_agent import DiscoveryAgent

        llm = MockLLMClient()
        browser = MockBrowserSession()
        memory = MockMemoryService()

        agent = DiscoveryAgent(llm=llm, browser_session=browser, memory_service=memory)

        validate_tool = next(t for t in agent.tools if t.name == "validate_response")
        assert isinstance(validate_tool, ValidateResponseTool)


class TestSelectorAgentHasValidateTool:
    """Tests for SelectorAgent validation tool."""

    def test_selector_agent_has_validate_tool(self):
        """ValidateResponseTool is in SelectorAgent's tools list."""
        from src.agents.selector_agent import SelectorAgent

        llm = MockLLMClient()
        browser = MockBrowserSession()
        memory = MockMemoryService()

        agent = SelectorAgent(llm=llm, browser_session=browser, memory_service=memory)

        tool_names = [t.name for t in agent.tools]
        assert "validate_response" in tool_names


class TestAccessibilityAgentHasValidateTool:
    """Tests for AccessibilityAgent validation tool."""

    def test_accessibility_agent_has_validate_tool(self):
        """ValidateResponseTool is in AccessibilityAgent's tools list."""
        from src.agents.accessibility_agent import AccessibilityAgent

        llm = MockLLMClient()
        memory = MockMemoryService()

        agent = AccessibilityAgent(llm=llm, memory_service=memory)

        tool_names = [t.name for t in agent.tools]
        assert "validate_response" in tool_names


class TestDataPrepAgentHasValidateTool:
    """Tests for DataPrepAgent validation tool."""

    def test_data_prep_agent_has_validate_tool(self):
        """ValidateResponseTool is in DataPrepAgent's tools list."""
        from src.agents.data_prep_agent import DataPrepAgent

        llm = MockLLMClient()
        browser = MockBrowserSession()
        memory = MockMemoryService()

        agent = DataPrepAgent(llm=llm, browser_session=browser, memory_service=memory)

        tool_names = [t.name for t in agent.tools]
        assert "validate_response" in tool_names


class TestAgentPromptsValidationInstructions:
    """Tests for validation instructions in prompts.

    Note: Validation instructions are now dynamically injected via templates
    when run_identifier and expected_outputs are provided to run().
    The base prompts no longer contain hardcoded validation sections.
    These tests verify the dynamic injection mechanism.
    """

    def test_base_prompts_do_not_contain_hardcoded_validation(self):
        """Base prompts should not contain hardcoded validation sections.

        Validation is now injected dynamically via _build_response_rules()
        when run_identifier is provided.
        """
        from src.prompts import get_prompt_provider

        provider = get_prompt_provider()

        agent_types = ["discovery", "selector", "accessibility", "data_prep"]
        for agent_type in agent_types:
            prompt = provider.get_agent_prompt(agent_type)
            # Base prompts should NOT have the hardcoded "## Response Validation" section
            assert "## Response Validation" not in prompt, (
                f"{agent_type} prompt should not have hardcoded Response Validation section"
            )
