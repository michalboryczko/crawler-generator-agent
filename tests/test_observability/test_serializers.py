"""Tests for serialization utilities."""

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import Enum
from pathlib import Path

from src.observability.serializers import (
    extract_error_info,
    safe_serialize,
    truncate_for_display,
)


class TestSafeSerialize:
    """Tests for safe_serialize function."""

    def test_primitives(self):
        """Test primitive types are passed through."""
        assert safe_serialize(None) is None
        assert safe_serialize(True) is True
        assert safe_serialize(False) is False
        assert safe_serialize(42) == 42
        assert safe_serialize(3.14) == 3.14
        assert safe_serialize("hello") == "hello"

    def test_datetime(self):
        """Test datetime serialization."""
        dt = datetime(2025, 1, 15, 10, 30, 45, tzinfo=UTC)
        result = safe_serialize(dt)
        assert result == "2025-01-15T10:30:45+00:00"

    def test_date(self):
        """Test date serialization."""
        d = date(2025, 1, 15)
        result = safe_serialize(d)
        assert result == "2025-01-15"

    def test_path(self):
        """Test Path serialization."""
        p = Path("/home/user/file.txt")
        result = safe_serialize(p)
        assert result == "/home/user/file.txt"

    def test_uuid(self):
        """Test UUID serialization."""
        u = uuid.UUID("12345678-1234-5678-1234-567812345678")
        result = safe_serialize(u)
        assert result == "12345678-1234-5678-1234-567812345678"

    def test_enum(self):
        """Test enum serialization."""

        class Color(Enum):
            RED = "red"
            BLUE = "blue"

        assert safe_serialize(Color.RED) == "red"

    def test_dataclass(self):
        """Test dataclass serialization."""

        @dataclass
        class Person:
            name: str
            age: int

        person = Person(name="Alice", age=30)
        result = safe_serialize(person)

        assert result == {"name": "Alice", "age": 30}

    def test_dict(self):
        """Test dictionary serialization."""
        data = {"key": "value", "nested": {"a": 1}}
        result = safe_serialize(data)

        assert result == {"key": "value", "nested": {"a": 1}}

    def test_list(self):
        """Test list serialization."""
        data = [1, "two", 3.0]
        result = safe_serialize(data)

        assert result == [1, "two", 3.0]

    def test_set(self):
        """Test set serialization (converted to list)."""
        data = {1, 2, 3}
        result = safe_serialize(data)

        # Sets are converted to sorted lists
        assert sorted(result) == [1, 2, 3]

    def test_bytes(self):
        """Test bytes serialization."""
        data = b"hello"
        result = safe_serialize(data)
        assert result == "hello"

        # Non-UTF8 bytes
        binary = bytes([0xFF, 0xFE])
        result = safe_serialize(binary)
        assert "<bytes:" in result

    def test_max_depth_protection(self):
        """Test that max_depth prevents infinite recursion."""
        # Create deeply nested structure
        deep = {"level": 0}
        current = deep
        for i in range(15):
            current["nested"] = {"level": i + 1}
            current = current["nested"]

        result = safe_serialize(deep, max_depth=5)

        # Should not raise, should truncate at depth
        assert isinstance(result, dict)

    def test_object_with_dict(self):
        """Test objects with __dict__ are serialized."""

        class CustomObject:
            def __init__(self):
                self.x = 1
                self.y = "two"

        obj = CustomObject()
        result = safe_serialize(obj)

        assert result == {"x": 1, "y": "two"}

    def test_unserializable_fallback(self):
        """Test that unserializable objects become strings."""

        # Use a class with no __dict__ (via __slots__) and failing __str__
        class NoStr:
            __slots__ = ()  # No __dict__

            def __str__(self):
                raise Exception("Can't stringify")

        result = safe_serialize(NoStr())
        assert "<unserializable:" in result


class TestTruncateForDisplay:
    """Tests for truncate_for_display function."""

    def test_short_string_unchanged(self):
        """Test that short strings are not truncated."""
        result = truncate_for_display("hello", max_length=10)
        assert result == "hello"

    def test_long_string_truncated(self):
        """Test that long strings are truncated."""
        long_str = "a" * 100
        result = truncate_for_display(long_str, max_length=10)

        assert len(result) < len(long_str)
        assert "..." in result
        assert "100 chars total" in result

    def test_nested_dict_truncation(self):
        """Test truncation in nested dictionaries."""
        data = {"key": "a" * 100}
        result = truncate_for_display(data, max_length=10)

        assert "..." in result["key"]


class TestExtractErrorInfo:
    """Tests for extract_error_info function."""

    def test_extracts_error_type(self):
        """Test that error type is extracted."""
        try:
            raise ValueError("test error")
        except ValueError as e:
            info = extract_error_info(e)

        assert info["error_type"] == "ValueError"

    def test_extracts_message(self):
        """Test that error message is extracted."""
        try:
            raise RuntimeError("something went wrong")
        except RuntimeError as e:
            info = extract_error_info(e)

        assert info["error_message"] == "something went wrong"

    def test_includes_stack_trace(self):
        """Test that stack trace is included."""
        try:
            raise Exception("test")
        except Exception as e:
            info = extract_error_info(e)

        assert "stack_trace" in info
        assert "Exception: test" in info["stack_trace"]
