"""Supervisor Tool for LLM-based output validation.

Validates generated plan quality using LLM analysis, checking completeness,
consistency, and correctness of the generated output.

The @traced_tool decorator handles all tool instrumentation.
"""

import json
import logging
import re
from typing import TYPE_CHECKING, Any

from ..observability.decorators import traced_tool
from .base import BaseTool
from .validation import validated_tool

if TYPE_CHECKING:
    from ..core.llm import LLMClient, LLMClientFactory

logger = logging.getLogger(__name__)


class SupervisorTool(BaseTool):
    """Validate generated output quality using LLM analysis.

    This tool uses an LLM to analyze generated content (plans, configs)
    and validate their completeness, consistency, and correctness against
    the input data and task requirements.

    Validation checks:
    - Completeness: All required sections present
    - Consistency: Data matches input from sub-agents
    - Correctness: Selectors and config are properly formatted
    - Quality: Content is well-structured and actionable
    """

    name = "supervisor_tool"
    description = (
        "Validate plan quality and completeness using LLM analysis. "
        "Returns validation result with issues if any problems found."
    )

    def __init__(self, llm: "LLMClient | LLMClientFactory"):
        """Initialize the supervisor tool.

        Args:
            llm: Either an LLMClient instance or LLMClientFactory.
                 If factory provided, will get client for 'supervisor_tool'.
        """
        from ..core.llm import LLMClientFactory

        if isinstance(llm, LLMClientFactory):
            self._llm = llm.get_client("supervisor_tool")
        else:
            self._llm = llm

    @traced_tool(name="supervisor_tool")
    @validated_tool
    def execute(self, **kwargs: Any) -> dict[str, Any]:
        """Validate generated output using LLM analysis.

        Args:
            given_task: Description of the task that was performed
            input_data: The input provided to the agent (collected_information)
            output_data: The generated output to validate (plan content)
            context_data: Additional context (optional)

        Returns:
            dict with validation result, issues list, and recommendations
        """
        given_task = kwargs["given_task"]
        input_data = kwargs["input_data"]
        output_data = kwargs["output_data"]
        context_data = kwargs.get("context_data", "")

        # Build prompts
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(
            given_task=given_task,
            input_data=input_data,
            output_data=output_data,
            context_data=context_data,
        )

        # Call LLM for validation
        response = self._llm.chat([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ])

        # Parse validation result from LLM response
        return self._parse_validation_result(response.get("content", ""))

    def _build_system_prompt(self) -> str:
        """Build system prompt for supervisor validation."""
        return """You are a Quality Assurance Supervisor for an AI agent system that generates web crawler plans.

Your role is to validate generated outputs for:
1. **Completeness**: All required sections and fields are present
2. **Consistency**: Data matches the input from discovery and selector agents
3. **Correctness**: Selectors, URLs, and configuration are properly formatted
4. **Quality**: Content is well-structured, clear, and actionable

## Validation Rules

### For Crawl Plans (plan.md):
- Must have all 10 standard sections
- Selectors must match those from collected_information
- URLs must be valid
- Configuration JSON must be valid and complete
- Recommendations must be relevant to the site

### For Crawler Configuration:
- Must include: start_url, listing, detail, pagination, request, deduplication
- Listing and detail must have selector arrays
- Pagination must match discovery findings
- Browser requirements must match accessibility findings

## Response Format

You MUST respond with a JSON object:
```json
{
  "valid": true/false,
  "confidence": 0.0-1.0,
  "issues": [
    {
      "severity": "critical/high/medium/low",
      "category": "completeness/consistency/correctness/quality",
      "description": "Description of the issue",
      "location": "Where the issue was found",
      "suggestion": "How to fix it"
    }
  ],
  "summary": "Brief summary of validation result",
  "recommendations": ["List of recommendations for improvement"]
}
```

Be thorough but fair. Only flag genuine issues, not stylistic preferences."""

    def _build_user_prompt(
        self,
        given_task: str,
        input_data: Any,
        output_data: Any,
        context_data: str,
    ) -> str:
        """Build user prompt for validation request."""
        # Serialize data for prompt
        input_str = self._serialize_for_prompt(input_data)
        output_str = self._serialize_for_prompt(output_data)

        prompt = f"""Please validate the following generated output.

## Task Description
{given_task}

## Input Data (from sub-agents)
{input_str}

## Generated Output (to validate)
{output_str}
"""

        if context_data:
            prompt += f"""
## Additional Context
{context_data}
"""

        prompt += """
## Validation Request
Please analyze the output and provide your validation result as a JSON object.
Check for completeness, consistency with input data, correctness of format, and overall quality."""

        return prompt

    def _serialize_for_prompt(self, data: Any) -> str:
        """Serialize data for inclusion in prompt."""
        if isinstance(data, str):
            return data
        try:
            return json.dumps(data, indent=2, default=str)
        except (TypeError, ValueError):
            return str(data)

    def _parse_validation_result(self, content: str) -> dict[str, Any]:
        """Parse LLM response into structured validation result."""
        # Try to extract JSON from response (or use raw content)
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", content)
        json_str = json_match.group(1).strip() if json_match else content.strip()

        try:
            result = json.loads(json_str)

            # Ensure required fields exist with defaults
            return {
                "success": True,
                "valid": result.get("valid", False),
                "confidence": result.get("confidence", 0.5),
                "issues": result.get("issues", []),
                "summary": result.get("summary", "Validation completed"),
                "recommendations": result.get("recommendations", []),
                "raw_response": content,
            }

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse supervisor response as JSON: {e}")

            # Return a fallback result based on content analysis
            is_valid = "valid" in content.lower() and "invalid" not in content.lower()

            return {
                "success": True,
                "valid": is_valid,
                "confidence": 0.3,  # Low confidence due to parse failure
                "issues": [{
                    "severity": "medium",
                    "category": "quality",
                    "description": "Could not parse structured validation response",
                    "location": "supervisor_response",
                    "suggestion": "Manual review recommended",
                }],
                "summary": "Validation completed but response parsing failed",
                "recommendations": ["Review the raw response for details"],
                "raw_response": content,
                "parse_error": str(e),
            }
