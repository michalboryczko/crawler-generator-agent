"""Tests for tool parameter validation decorator."""


from src.tools.base import BaseTool
from src.tools.validation import validated_tool


class MockValidatedTool(BaseTool):
    """Test tool with validated execute."""

    @property
    def name(self) -> str:
        return "mock_validated"

    @property
    def description(self) -> str:
        return "A mock tool for testing validation"

    @validated_tool
    def execute(
        self,
        required_arg: str,
        optional_arg: str = "default",
    ) -> dict[str, any]:
        return {
            "success": True,
            "required": required_arg,
            "optional": optional_arg,
        }

    def get_parameters_schema(self) -> dict[str, any]:
        return {
            "type": "object",
            "properties": {
                "required_arg": {
                    "type": "string",
                    "description": "A required argument",
                },
                "optional_arg": {
                    "type": "string",
                    "description": "An optional argument",
                },
            },
            "required": ["required_arg"],
        }


class TestValidatedTool:
    """Tests for @validated_tool decorator."""

    def test_valid_arguments_passes(self):
        """Tool executes normally with valid arguments."""
        tool = MockValidatedTool()
        result = tool.execute(required_arg="test_value")

        assert result["success"] is True
        assert result["required"] == "test_value"
        assert result["optional"] == "default"

    def test_valid_arguments_with_optional(self):
        """Tool executes normally with all arguments."""
        tool = MockValidatedTool()
        result = tool.execute(required_arg="test", optional_arg="custom")

        assert result["success"] is True
        assert result["required"] == "test"
        assert result["optional"] == "custom"

    def test_missing_required_argument_returns_error(self):
        """Missing required argument returns structured error, not exception."""
        tool = MockValidatedTool()
        result = tool.execute()  # No arguments!

        assert result["success"] is False
        assert "Missing required argument: required_arg" in result["error"]
        assert "provided_arguments" in result
        assert "hint" in result

    def test_missing_multiple_required_arguments(self):
        """Multiple missing arguments are listed."""

        class MultiRequiredTool(BaseTool):
            @property
            def name(self) -> str:
                return "multi_required"

            @property
            def description(self) -> str:
                return "Tool with multiple required args"

            @validated_tool
            def execute(self, arg1: str, arg2: str, arg3: str) -> dict[str, any]:
                return {"success": True}

            def get_parameters_schema(self) -> dict[str, any]:
                return {
                    "type": "object",
                    "properties": {
                        "arg1": {"type": "string"},
                        "arg2": {"type": "string"},
                        "arg3": {"type": "string"},
                    },
                    "required": ["arg1", "arg2", "arg3"],
                }

        tool = MultiRequiredTool()
        result = tool.execute(arg1="only_one")

        assert result["success"] is False
        assert "Missing required arguments:" in result["error"]
        assert "arg2" in result["error"]
        assert "arg3" in result["error"]

    def test_invalid_type_returns_error(self):
        """Invalid argument type returns validation error."""

        class TypedTool(BaseTool):
            @property
            def name(self) -> str:
                return "typed"

            @property
            def description(self) -> str:
                return "Tool with typed args"

            @validated_tool
            def execute(self, count: int) -> dict[str, any]:
                return {"success": True, "count": count}

            def get_parameters_schema(self) -> dict[str, any]:
                return {
                    "type": "object",
                    "properties": {
                        "count": {"type": "integer"},
                    },
                    "required": ["count"],
                }

        tool = TypedTool()
        result = tool.execute(count="not_an_integer")

        assert result["success"] is False
        assert "Validation error:" in result["error"] or "Invalid argument" in result["error"]

    def test_error_includes_provided_arguments(self):
        """Error response includes list of provided arguments for debugging."""
        tool = MockValidatedTool()
        result = tool.execute(wrong_arg="value")

        assert result["success"] is False
        assert result["provided_arguments"] == ["wrong_arg"]


class TestValidateResponseToolIntegration:
    """Integration test for ValidateResponseTool with validation."""

    def test_missing_response_json_returns_helpful_error(self):
        """Calling without response_json returns helpful error, not traceback."""
        from src.tools.agent_tools.validate_response import ValidateResponseTool

        tool = ValidateResponseTool()
        result = tool.execute(run_identifier="some-uuid")  # Missing response_json!

        assert result["success"] is False
        assert "response_json" in result["error"]
        assert "Missing required argument" in result["error"]

    def test_missing_run_identifier_returns_helpful_error(self):
        """Calling without run_identifier returns helpful error."""
        from src.tools.agent_tools.validate_response import ValidateResponseTool

        tool = ValidateResponseTool()
        result = tool.execute(response_json={"data": "value"})  # Missing run_identifier!

        assert result["success"] is False
        assert "run_identifier" in result["error"]
        assert "Missing required argument" in result["error"]

    def test_both_arguments_missing_lists_all(self):
        """Calling with no arguments lists all missing required args."""
        from src.tools.agent_tools.validate_response import ValidateResponseTool

        tool = ValidateResponseTool()
        result = tool.execute()  # No arguments at all!

        assert result["success"] is False
        assert "Missing required arguments:" in result["error"]
        assert "run_identifier" in result["error"]
        assert "response_json" in result["error"]
