"""Base agent class with reasoning loop.

This module uses the new observability decorators for automatic logging.
The @traced_agent decorator handles all agent instrumentation.

Supports both single LLMClient (legacy) and LLMClientFactory (multi-model) modes.
"""

import json
import logging
from typing import TYPE_CHECKING, Any, Union

from ..core.llm import LLMClient
from ..observability.decorators import traced_agent
from ..tools.base import BaseTool
from .result import AgentResult

if TYPE_CHECKING:
    from ..core.llm import LLMClientFactory
    from ..services.memory_service import MemoryService
    from ..tools.agent_tools import AgentTool

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 100
MAX_VALIDATION_RETRIES = 3


class BaseAgent:
    """Base agent with thought→action→observation loop.

    Supports both legacy (single LLMClient) and multi-model (LLMClientFactory) modes.
    When a factory is provided, the agent gets its own client from the factory
    based on its name.
    """

    name: str = "base_agent"
    description: str = "Base agent"
    system_prompt: str = "You are a helpful assistant."

    def get_description(self) -> str:
        """Return formatted agent description.

        Returns:
            String in format "{name} - {description}"
        """
        return f"{self.name} - {self.description}"

    def __init__(
        self,
        llm: Union[LLMClient, "LLMClientFactory"],
        tools: list[BaseTool] | None = None,
        component_name: str | None = None,
        memory_service: "MemoryService | None" = None,
    ):
        """Initialize the agent.

        Args:
            llm: Either an LLMClient (legacy) or LLMClientFactory (multi-model)
            tools: Optional list of tools available to the agent.
                   AgentTool instances are auto-detected and accessible
                   via the agent_tools property.
            component_name: Override the component name for factory lookup
                           (defaults to agent's name attribute)
            memory_service: MemoryService for agent memory
        """
        # Handle both LLMClient and LLMClientFactory
        self.llm_factory: Any = None  # Type: LLMClientFactory when using factory mode
        if hasattr(llm, "get_client"):
            # It's a factory - get a client for this agent
            self.llm_factory = llm
            effective_name = component_name or self.name
            self.llm = llm.get_client(effective_name)
            logger.debug(
                f"Agent '{self.name}' initialized with factory client for '{effective_name}'"
            )
        else:
            # Direct LLMClient
            self.llm_factory = None
            self.llm = llm

        self.tools = tools or []
        self._memory_service = memory_service

        # Auto-detect AgentTools from tools list
        from ..tools.agent_tools import AgentTool

        self._agent_tools = [t for t in self.tools if isinstance(t, AgentTool)]

        # Auto-attach DescribeOutputContractTool if AgentTools present
        if self._agent_tools:
            from ..tools.agent_tools import DescribeOutputContractTool

            # Build schema paths from AgentTools
            schema_paths = {at.get_agent_name(): at._output_schema_path for at in self._agent_tools}
            describe_tool = DescribeOutputContractTool(schema_paths)
            self.tools = [*list(self.tools), describe_tool]

        self._tool_map = {t.name: t for t in self.tools}
        self._validation_retries = 0

    def _can_retry_validation(self) -> bool:
        """Check if more validation retries are allowed."""
        return self._validation_retries < MAX_VALIDATION_RETRIES

    @property
    def agent_tools(self) -> "list[AgentTool]":
        """Return auto-detected AgentTools from tools list."""
        return self._agent_tools

    @property
    def memory_service(self) -> "MemoryService | None":
        """Return the agent's memory service."""
        return self._memory_service

    @traced_agent()  # Uses self.name dynamically
    def run(
        self,
        task: str,
        context: dict[str, Any] | None = None,
        expected_outputs: list[str] | None = None,
        run_identifier: str | None = None,
        output_contract_schema: dict | None = None,
    ) -> AgentResult:
        """Execute agent task with tool loop.

        Instrumented by @traced_agent - logs agent lifecycle, iterations, and results.

        Args:
            task: The task description to complete
            context: Optional explicit data from parent agent/orchestrator
            expected_outputs: Optional list of expected output fields for validation
            run_identifier: Optional UUID for validation context tracking
            output_contract_schema: Optional JSON schema for the expected response

        Returns:
            AgentResult with success, data, errors, and optional memory snapshot
        """
        # Build system message with contract sections
        system_content = self._build_final_prompt(
            expected_outputs=expected_outputs,
            run_identifier=run_identifier,
            context=context,
            output_contract_schema=output_contract_schema,
        )

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": task},
        ]

        # Reset validation retry counter for this run
        self._validation_retries = 0

        for iteration in range(MAX_ITERATIONS):
            logger.info(f"Agent {self.name} iteration {iteration + 1}")

            response = self.llm.chat(messages, tools=self.tools if self.tools else None)

            if response["tool_calls"]:
                # IMPORTANT: Only process ONE tool call at a time to ensure sequential execution
                # Even if model returns multiple tool calls, we only execute the first one
                # This forces navigate→wait→getHTML sequence instead of batching
                tool_calls_to_process = response["tool_calls"][:1]  # Only first tool call

                if len(response["tool_calls"]) > 1:
                    logger.warning(
                        f"Model returned {len(response['tool_calls'])} tool calls, "
                        f"but only processing first one to ensure sequential execution"
                    )

                # Add assistant message with only the tool call we're processing
                messages.append(
                    {
                        "role": "assistant",
                        "content": response["content"],
                        "tool_calls": [
                            {
                                "id": tc["id"],
                                "type": "function",
                                "function": {"name": tc["name"], "arguments": str(tc["arguments"])},
                            }
                            for tc in tool_calls_to_process
                        ],
                    }
                )

                # Execute the single tool call
                for tool_call in tool_calls_to_process:
                    result = self._execute_tool(tool_call["name"], tool_call["arguments"])
                    messages.append(
                        {"role": "tool", "tool_call_id": tool_call["id"], "content": str(result)}
                    )
            else:
                # No tool calls - agent wants to finish
                result_data = self._extract_result_data(response["content"])

                # Guard: no validation needed
                validate_tool = self._tool_map.get("validate_response")
                if not run_identifier or not validate_tool:
                    return AgentResult(
                        success=True,
                        data=result_data,
                        memory_snapshot=self._get_memory_snapshot(),
                        iterations=iteration + 1,
                    )

                # Run validation
                validation_result = validate_tool.execute(
                    run_identifier=run_identifier,
                    response_json=response["content"],
                )

                # Guard: validation failed - retry if possible
                if not validation_result.get("valid", False):
                    if self._can_retry_validation():
                        self._validation_retries += 1
                        if validation_result.get("extraction_failed"):
                            error_msg = self._build_json_extraction_error(
                                self._validation_retries
                            )
                        else:
                            errors = validation_result.get("validation_errors", [])
                            error_msg = self._build_validation_error_message_from_tool(
                                errors, self._validation_retries
                            )
                        messages.append({"role": "assistant", "content": response["content"]})
                        messages.append({"role": "user", "content": error_msg})
                        continue

                    logger.error(
                        f"[{self.name}] Validation failed after "
                        f"{MAX_VALIDATION_RETRIES} retries."
                    )

                # Validation passed - extract JSON
                from ..core.json_parser import extract_json

                extracted = extract_json(response["content"])
                final_data = extracted if extracted is not None else result_data

                return AgentResult(
                    success=True,
                    data=final_data,
                    memory_snapshot=self._get_memory_snapshot(),
                    iterations=iteration + 1,
                )

        # Max iterations reached
        return AgentResult(
            success=False,
            errors=[f"Max iterations ({MAX_ITERATIONS}) reached"],
            memory_snapshot=self._get_memory_snapshot(),
            iterations=MAX_ITERATIONS,
        )

    def _build_final_prompt(
        self,
        expected_outputs: list[str] | None = None,
        run_identifier: str | None = None,
        context: dict[str, Any] | None = None,
        output_contract_schema: dict | None = None,
    ) -> str:
        """Build final system prompt with contract sections.

        Template method: Override in subclasses for custom prompt building.

        Order: response_rules (critical) → system_prompt → sub_agents → context
        Response rules come FIRST so they're most prominent to the model.

        Args:
            expected_outputs: List of expected output fields for validation
            run_identifier: UUID for validation context tracking
            context: Context data from orchestrator
            output_contract_schema: Full JSON schema for expected response

        Returns:
            Complete system prompt with all sections
        """
        prompt_parts = []

        # Add response rules FIRST if validation context provided (most critical)
        if run_identifier and expected_outputs:
            prompt_parts.append(
                self._build_response_rules(expected_outputs, run_identifier, output_contract_schema)
            )

        # Add base system prompt
        prompt_parts.append(self.system_prompt)

        # Add sub-agents section if agent_tools exist
        sub_agents_section = self._build_sub_agents_section()
        if sub_agents_section:
            prompt_parts.append(sub_agents_section)

        # Inject context last
        if context:
            prompt_parts.append(self._inject_context(context))

        return "\n\n".join(prompt_parts)

    def _build_sub_agents_section(self) -> str:
        """Build prompt section describing available sub-agents.

        Returns:
            Formatted sub-agents section, or empty string if no agent_tools
        """
        if not self.agent_tools:
            return ""

        from ..prompts.template_renderer import render_template

        return render_template(
            "sub_agents_section.md.j2",
            agent_tools=self.agent_tools,
        )

    def _build_response_rules(
        self,
        expected_outputs: list[str],
        run_identifier: str,
        output_contract_schema: dict | None = None,
    ) -> str:
        """Build response validation rules section.

        Args:
            expected_outputs: List of expected output fields
            run_identifier: UUID for validation context
            output_contract_schema: Full JSON schema for expected response.
                                   If None, an empty dict is used.

        Returns:
            Formatted response rules section
        """
        from ..prompts.template_renderer import render_template

        # Build example JSON with placeholder values
        example_json = {field: "<value>" for field in expected_outputs}

        return render_template(
            "response_rules.md.j2",
            run_identifier=run_identifier,
            expected_outputs=expected_outputs,
            required_fields=expected_outputs,
            output_contract_schema=output_contract_schema or {},
            example_json=example_json,
        )

    def _inject_context(self, context: dict[str, Any]) -> str:
        """Format context for injection into prompt.

        Args:
            context: Context data from orchestrator

        Returns:
            Formatted context section
        """
        context_str = json.dumps(context, indent=2)
        return f"## Context from Orchestrator\n```json\n{context_str}\n```"

    def _execute_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Execute a tool by name with arguments.

        Tool execution is instrumented by the tool's own @traced_tool decorator.
        """
        if name not in self._tool_map:
            return {"success": False, "error": f"Unknown tool: {name}"}

        tool = self._tool_map[name]
        try:
            arg_summary = (
                str(arguments)[:200] + "..." if len(str(arguments)) > 200 else str(arguments)
            )
            logger.info(f"[{self.name}] Executing tool: {name} with args: {arg_summary}")

            result = tool.execute(**arguments)

            result_summary = str(result)[:300] + "..." if len(str(result)) > 300 else str(result)
            logger.info(f"[{self.name}] Tool {name} completed: {result_summary}")

            return result
        except Exception as e:
            logger.error(f"[{self.name}] Tool {name} failed: {e}")
            return {"success": False, "error": str(e)}

    def _extract_result_data(self, content: str) -> dict[str, Any]:
        """Extract structured data from final response.

        Override in subclasses to extract specific data from the agent's response.

        Args:
            content: The final response content from the LLM

        Returns:
            Dictionary with extracted data
        """
        return {"result": content}

    def _get_memory_snapshot(self) -> dict[str, Any] | None:
        """Return snapshot of agent's memory if available.

        Returns:
            Dictionary with all memory keys/values, or None if no memory service
        """
        if self._memory_service:
            return self._memory_service.get_snapshot()
        return None

    def _build_json_extraction_error(self, attempt: int) -> str:
        """Build error message for JSON extraction failure.

        Args:
            attempt: Current retry attempt number

        Returns:
            Formatted error message for the agent
        """
        from ..prompts.template_renderer import render_template

        return render_template(
            "json_extraction_error.md.j2",
            error_message="Could not parse response as valid JSON",
            retries_remaining=MAX_VALIDATION_RETRIES - attempt,
        )

    def _build_validation_error_message_from_tool(
        self, errors: list[dict[str, str]], attempt: int
    ) -> str:
        """Build error message from validate_response tool errors.

        Args:
            errors: List of error dicts with 'path' and 'message'
            attempt: Current retry attempt number

        Returns:
            Formatted error message for the agent
        """
        from ..prompts.template_renderer import render_template

        error_messages = [e.get("message", str(e)) for e in errors]
        return render_template(
            "validation_error.md.j2",
            errors=error_messages,
            retries_remaining=MAX_VALIDATION_RETRIES - attempt,
        )
