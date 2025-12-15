"""Tests for ToolResult dataclass."""


from src.tools.result import ToolResult


class TestToolResultOk:
    """Tests for ToolResult.ok() factory method."""

    def test_ok_basic(self):
        """Test creating successful result."""
        result = ToolResult.ok("some data")
        assert result.success is True
        assert result.data == "some data"
        assert result.error is None
        assert result.error_type is None

    def test_ok_with_dict_data(self):
        """Test successful result with dict data."""
        data = {"key": "value", "count": 42}
        result = ToolResult.ok(data)
        assert result.success is True
        assert result.data == data

    def test_ok_with_none_data(self):
        """Test successful result with None data."""
        result = ToolResult.ok(None)
        assert result.success is True
        assert result.data is None

    def test_ok_with_metadata(self):
        """Test successful result with metadata."""
        result = ToolResult.ok("data", metadata={"duration_ms": 150})
        assert result.success is True
        assert result.metadata == {"duration_ms": 150}

    def test_ok_default_empty_metadata(self):
        """Test metadata defaults to empty dict."""
        result = ToolResult.ok("data")
        assert result.metadata == {}


class TestToolResultFail:
    """Tests for ToolResult.fail() factory method."""

    def test_fail_basic(self):
        """Test creating failure result."""
        result = ToolResult.fail("Something went wrong")
        assert result.success is False
        assert result.error == "Something went wrong"
        assert result.error_type == "unknown"
        assert result.data is None

    def test_fail_with_error_type(self):
        """Test failure with specific error type."""
        result = ToolResult.fail("Connection refused", error_type="network")
        assert result.success is False
        assert result.error == "Connection refused"
        assert result.error_type == "network"

    def test_fail_with_metadata(self):
        """Test failure with metadata."""
        result = ToolResult.fail(
            "Timeout",
            error_type="timeout",
            metadata={"elapsed_ms": 30000},
        )
        assert result.success is False
        assert result.metadata == {"elapsed_ms": 30000}


class TestToolResultToDict:
    """Tests for ToolResult.to_dict() method."""

    def test_to_dict_success(self):
        """Test converting successful result to dict."""
        result = ToolResult.ok({"items": [1, 2, 3]})
        d = result.to_dict()
        assert d["success"] is True
        assert d["result"] == {"items": [1, 2, 3]}
        assert "error" not in d

    def test_to_dict_failure(self):
        """Test converting failure result to dict."""
        result = ToolResult.fail("Error message", error_type="validation")
        d = result.to_dict()
        assert d["success"] is False
        assert d["error"] == "Error message"
        assert d["error_type"] == "validation"
        assert "result" not in d

    def test_to_dict_with_metadata(self):
        """Test metadata is included in dict."""
        result = ToolResult.ok("data", metadata={"count": 5})
        d = result.to_dict()
        assert d["count"] == 5

    def test_to_dict_failure_without_error_type(self):
        """Test failure without error_type doesn't include it."""
        result = ToolResult(success=False, error="Error", error_type=None)
        d = result.to_dict()
        assert "error_type" not in d


class TestToolResultBool:
    """Tests for ToolResult boolean conversion."""

    def test_bool_success(self):
        """Test successful result is truthy."""
        result = ToolResult.ok("data")
        assert bool(result) is True
        assert result  # Direct usage in boolean context

    def test_bool_failure(self):
        """Test failure result is falsy."""
        result = ToolResult.fail("error")
        assert bool(result) is False
        assert not result  # Direct usage in boolean context

    def test_if_statement(self):
        """Test usage in if statement."""
        success_result = ToolResult.ok("data")
        fail_result = ToolResult.fail("error")

        # Success result evaluates to True in conditionals
        passed_success = bool(success_result)
        assert passed_success is True

        # Failure result evaluates to False in conditionals
        passed_fail = bool(fail_result)
        assert passed_fail is False
