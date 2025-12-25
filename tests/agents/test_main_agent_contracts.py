"""Tests for MainAgent contract orchestration integration.

Tests verify that MainAgent:
1. Has contract orchestration tools (GenerateUuidTool, PrepareAgentOutputValidationTool)
2. Uses AgentTool wrappers for sub-agents with proper schema paths
3. Prompt building includes sub-agent sections
"""

import json
from unittest.mock import MagicMock

import pytest

from src.agents.main_agent import MainAgent
from src.core.config import AgentSchemaConfig, AgentsConfig
from src.tools.agent_tools import AgentTool, GenerateUuidTool, PrepareAgentOutputValidationTool


@pytest.fixture
def mock_llm():
    """Create a mock LLM client."""
    llm = MagicMock()
    llm.call.return_value = {"content": "test response"}
    return llm


@pytest.fixture
def mock_browser():
    """Create a mock browser session."""
    return MagicMock()


@pytest.fixture
def mock_memory():
    """Create a mock memory service."""
    memory = MagicMock()
    memory.read.return_value = None
    return memory


@pytest.fixture
def mock_container(mock_memory):
    """Create a mock container that returns isolated memory services."""
    container = MagicMock()
    container.memory_service.return_value = MagicMock()
    return container


@pytest.fixture
def test_agents_config(tmp_path):
    """Create test schema files and AgentsConfig."""
    # Sample output schema for testing
    output_schema = {
        "type": "object",
        "properties": {
            "article_urls": {"type": "array", "items": {"type": "string"}},
            "pagination_type": {"type": "string"},
        },
        "required": ["article_urls"],
    }
    input_schema = {
        "type": "object",
        "properties": {"url": {"type": "string"}},
        "required": ["url"],
    }

    # Create schema files for each agent
    agents = {}
    for agent_name in ["discovery", "selector", "accessibility", "data_prep", "plan_generator"]:
        agent_dir = tmp_path / f"{agent_name}_agent"
        agent_dir.mkdir()

        output_path = agent_dir / "output.schema.json"
        output_path.write_text(json.dumps(output_schema))

        input_path = agent_dir / "input.schema.json"
        input_path.write_text(json.dumps(input_schema))

        agents[agent_name] = AgentSchemaConfig(
            output_contract_schema_path=str(output_path),
            input_contract_schema_path=str(input_path),
        )

    return AgentsConfig(agents=agents)


@pytest.fixture
def main_agent(mock_llm, mock_browser, mock_memory, mock_container, tmp_path, test_agents_config):
    """Create a MainAgent instance with mocks."""
    return MainAgent(
        llm=mock_llm,
        browser_session=mock_browser,
        output_dir=tmp_path,
        memory_service=mock_memory,
        container=mock_container,
        agents_config=test_agents_config,
    )


class TestMainAgentHasContractTools:
    """Tests that MainAgent has the contract orchestration tools."""

    def test_has_generate_uuid_tool(self, main_agent):
        """MainAgent should have GenerateUuidTool for creating run identifiers."""
        tool_names = [t.name for t in main_agent.tools]
        assert "generate_uuid" in tool_names

    def test_has_prepare_validation_tool(self, main_agent):
        """MainAgent should have PrepareAgentOutputValidationTool."""
        tool_names = [t.name for t in main_agent.tools]
        assert "prepare_agent_output_validation" in tool_names

    def test_generate_uuid_is_correct_type(self, main_agent):
        """GenerateUuidTool should be the correct class instance."""
        tool = main_agent._tool_map.get("generate_uuid")
        assert tool is not None
        assert isinstance(tool, GenerateUuidTool)

    def test_prepare_validation_is_correct_type(self, main_agent):
        """PrepareAgentOutputValidationTool should be the correct class instance."""
        tool = main_agent._tool_map.get("prepare_agent_output_validation")
        assert tool is not None
        assert isinstance(tool, PrepareAgentOutputValidationTool)


class TestMainAgentHasAgentTools:
    """Tests that MainAgent uses AgentTool wrappers for sub-agents."""

    def test_has_agent_tools_list(self, main_agent):
        """MainAgent should have a non-empty agent_tools list."""
        assert hasattr(main_agent, "agent_tools")
        assert len(main_agent.agent_tools) > 0

    def test_agent_tools_are_agent_tool_instances(self, main_agent):
        """All items in agent_tools should be AgentTool instances."""
        for tool in main_agent.agent_tools:
            assert isinstance(tool, AgentTool), f"{tool} is not an AgentTool"

    def test_has_discovery_agent_tool(self, main_agent):
        """MainAgent should have an AgentTool for discovery agent."""
        tool_names = [t.name for t in main_agent.agent_tools]
        assert "run_discovery_agent" in tool_names

    def test_has_selector_agent_tool(self, main_agent):
        """MainAgent should have an AgentTool for selector agent."""
        tool_names = [t.name for t in main_agent.agent_tools]
        assert "run_selector_agent" in tool_names

    def test_has_accessibility_agent_tool(self, main_agent):
        """MainAgent should have an AgentTool for accessibility agent."""
        tool_names = [t.name for t in main_agent.agent_tools]
        assert "run_accessibility_agent" in tool_names

    def test_has_data_prep_agent_tool(self, main_agent):
        """MainAgent should have an AgentTool for data prep agent."""
        tool_names = [t.name for t in main_agent.agent_tools]
        assert "run_data_prep_agent" in tool_names

    def test_has_plan_generator_agent_tool(self, main_agent):
        """MainAgent should have an AgentTool for plan generator agent."""
        tool_names = [t.name for t in main_agent.agent_tools]
        assert "run_plan_generator_agent" in tool_names


class TestPromptIncludesSubAgents:
    """Tests that prompt building includes sub-agent information."""

    def test_build_sub_agents_section_not_empty(self, main_agent):
        """_build_sub_agents_section should return non-empty string."""
        section = main_agent._build_sub_agents_section()
        assert section != ""
        # New template uses workflow-based format
        assert "## Sub-Agents usage" in section
        assert "Available agents" in section

    def test_sub_agents_section_includes_all_agents(self, main_agent):
        """Sub-agents section should include all agent names."""
        section = main_agent._build_sub_agents_section()
        assert "discovery_agent" in section
        assert "selector_agent" in section
        assert "accessibility_agent" in section
        assert "data_prep_agent" in section
        assert "plan_generator_agent" in section

    def test_sub_agents_section_includes_workflow_rules(self, main_agent):
        """Sub-agents section should include workflow rules."""
        section = main_agent._build_sub_agents_section()
        # Should have workflow instructions
        assert "Agent usage rules" in section
        assert "describe_output_contract" in section
        assert "prepare_agent_output_validation" in section

    def test_final_prompt_includes_sub_agents(self, main_agent):
        """_build_final_prompt should include sub-agents section."""
        prompt = main_agent._build_final_prompt()
        assert "Sub-Agents usage" in prompt
        assert "discovery_agent" in prompt


class TestAgentToolsInToolMap:
    """Tests that AgentTools are accessible via the tool map."""

    def test_agent_tools_in_tool_map(self, main_agent):
        """AgentTools should be accessible via _tool_map."""
        assert "run_discovery_agent" in main_agent._tool_map
        assert "run_selector_agent" in main_agent._tool_map
        assert "run_accessibility_agent" in main_agent._tool_map
        assert "run_data_prep_agent" in main_agent._tool_map
        assert "run_plan_generator_agent" in main_agent._tool_map

    def test_tool_map_entries_are_agent_tools(self, main_agent):
        """Tool map entries for agent runners should be AgentTool instances."""
        assert isinstance(main_agent._tool_map["run_discovery_agent"], AgentTool)
        assert isinstance(main_agent._tool_map["run_selector_agent"], AgentTool)
        assert isinstance(main_agent._tool_map["run_accessibility_agent"], AgentTool)
        assert isinstance(main_agent._tool_map["run_data_prep_agent"], AgentTool)
        assert isinstance(main_agent._tool_map["run_plan_generator_agent"], AgentTool)
