"""Tests for AgentResult dataclass."""

import pytest

from src.agents.result import AgentResult


class TestAgentResultBasics:
    """Test basic AgentResult functionality."""

    def test_creation_with_defaults(self) -> None:
        """Test creating result with minimal arguments."""
        result = AgentResult(success=True)
        assert result.success is True
        assert result.data == {}
        assert result.errors == []
        assert result.iterations == 0
        assert result.memory_snapshot is None

    def test_creation_with_data(self) -> None:
        """Test creating result with data."""
        result = AgentResult(
            success=True,
            data={"key": "value", "count": 42},
            iterations=5
        )
        assert result.success is True
        assert result.data == {"key": "value", "count": 42}
        assert result.iterations == 5


class TestAgentResultGet:
    """Test get() method."""

    def test_get_existing_key(self) -> None:
        """Test get() returns value for existing key."""
        result = AgentResult(success=True, data={"name": "test"})
        assert result.get("name") == "test"

    def test_get_missing_key_returns_none(self) -> None:
        """Test get() returns None for missing key by default."""
        result = AgentResult(success=True, data={})
        assert result.get("missing") is None

    def test_get_missing_key_returns_default(self) -> None:
        """Test get() returns custom default for missing key."""
        result = AgentResult(success=True, data={})
        assert result.get("missing", "default_value") == "default_value"
        assert result.get("missing", []) == []


class TestAgentResultGetitem:
    """Test __getitem__ (dict-like access)."""

    def test_getitem_existing_key(self) -> None:
        """Test dict-like access for existing key."""
        result = AgentResult(success=True, data={"url": "https://example.com"})
        assert result["url"] == "https://example.com"

    def test_getitem_missing_key_raises(self) -> None:
        """Test dict-like access raises KeyError for missing key."""
        result = AgentResult(success=True, data={})
        with pytest.raises(KeyError):
            _ = result["missing"]


class TestAgentResultHas:
    """Test has() method."""

    def test_has_existing_key(self) -> None:
        """Test has() returns True for existing key."""
        result = AgentResult(success=True, data={"articles": []})
        assert result.has("articles") is True

    def test_has_missing_key(self) -> None:
        """Test has() returns False for missing key."""
        result = AgentResult(success=True, data={"articles": []})
        assert result.has("missing") is False

    def test_has_with_none_value(self) -> None:
        """Test has() returns True even if value is None."""
        result = AgentResult(success=True, data={"nullable": None})
        assert result.has("nullable") is True


class TestAgentResultFailed:
    """Test failed property."""

    def test_failed_when_success_true(self) -> None:
        """Test failed is False when success is True."""
        result = AgentResult(success=True)
        assert result.failed is False

    def test_failed_when_success_false(self) -> None:
        """Test failed is True when success is False."""
        result = AgentResult(success=False)
        assert result.failed is True


class TestAgentResultToDict:
    """Test to_dict() serialization."""

    def test_to_dict_basic(self) -> None:
        """Test basic serialization."""
        result = AgentResult(success=True, data={"key": "value"})
        d = result.to_dict()

        assert d["success"] is True
        assert d["data"] == {"key": "value"}
        assert d["errors"] == []
        assert d["iterations"] == 0

    def test_to_dict_with_errors(self) -> None:
        """Test serialization includes errors."""
        result = AgentResult(
            success=False,
            errors=["Error 1", "Error 2"],
            iterations=3
        )
        d = result.to_dict()

        assert d["success"] is False
        assert d["errors"] == ["Error 1", "Error 2"]
        assert d["iterations"] == 3

    def test_to_dict_does_not_include_memory_snapshot(self) -> None:
        """Test memory_snapshot is not in serialized dict."""
        result = AgentResult(
            success=True,
            memory_snapshot={"internal": "state"}
        )
        d = result.to_dict()

        assert "memory_snapshot" not in d


class TestAgentResultFailureFactory:
    """Test failure() factory method."""

    def test_failure_creates_failed_result(self) -> None:
        """Test failure() creates result with success=False."""
        result = AgentResult.failure("Something went wrong")

        assert result.success is False
        assert result.failed is True
        assert "Something went wrong" in result.errors

    def test_failure_with_data(self) -> None:
        """Test failure() includes additional data."""
        result = AgentResult.failure(
            "Connection timeout",
            url="https://example.com",
            attempt=3
        )

        assert result.success is False
        assert result.errors == ["Connection timeout"]
        assert result.data["url"] == "https://example.com"
        assert result.data["attempt"] == 3


class TestAgentResultOkFactory:
    """Test ok() factory method."""

    def test_ok_creates_success_result(self) -> None:
        """Test ok() creates result with success=True."""
        result = AgentResult.ok()

        assert result.success is True
        assert result.failed is False
        assert result.errors == []

    def test_ok_with_data(self) -> None:
        """Test ok() includes provided data."""
        result = AgentResult.ok(
            articles=["url1", "url2"],
            count=2,
            pagination="numbered"
        )

        assert result.success is True
        assert result.data["articles"] == ["url1", "url2"]
        assert result.data["count"] == 2
        assert result.data["pagination"] == "numbered"


class TestAgentResultChaining:
    """Test chaining methods."""

    def test_merge_data(self) -> None:
        """Test merge_data adds to existing data."""
        result = AgentResult.ok(initial="value")
        result.merge_data({"additional": "data", "count": 5})

        assert result.data["initial"] == "value"
        assert result.data["additional"] == "data"
        assert result.data["count"] == 5

    def test_merge_data_returns_self(self) -> None:
        """Test merge_data returns self for chaining."""
        result = AgentResult.ok()
        returned = result.merge_data({"key": "value"})

        assert returned is result

    def test_add_error(self) -> None:
        """Test add_error appends to errors list."""
        result = AgentResult(success=True)
        result.add_error("First error")
        result.add_error("Second error")

        assert result.errors == ["First error", "Second error"]

    def test_add_error_returns_self(self) -> None:
        """Test add_error returns self for chaining."""
        result = AgentResult(success=True)
        returned = result.add_error("error")

        assert returned is result

    def test_chaining_multiple_operations(self) -> None:
        """Test chaining multiple operations."""
        result = (
            AgentResult.ok(initial="data")
            .merge_data({"more": "data"})
            .add_error("warning")
        )

        assert result.data["initial"] == "data"
        assert result.data["more"] == "data"
        assert "warning" in result.errors
