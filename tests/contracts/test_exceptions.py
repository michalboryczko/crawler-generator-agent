"""Tests for contract system exceptions."""

import pytest

from src.contracts.exceptions import ContractValidationError, SchemaLoadError


class TestContractValidationError:
    """Tests for ContractValidationError."""

    def test_basic_creation(self):
        """Test creating basic validation error."""
        error = ContractValidationError("Validation failed")
        assert str(error) == "Validation failed"
        assert error.message == "Validation failed"
        assert error.errors == []

    def test_with_errors_list(self):
        """Test creating error with validation errors."""
        errors = [
            {"path": "name", "message": "Required field missing"},
            {"path": "age", "message": "Must be integer"},
        ]
        error = ContractValidationError("Validation failed", errors=errors)

        assert error.errors == errors
        assert len(error.errors) == 2

    def test_is_exception(self):
        """Test ContractValidationError is an Exception."""
        error = ContractValidationError("Error")
        assert isinstance(error, Exception)

    def test_can_be_raised_and_caught(self):
        """Test error can be raised and caught."""
        with pytest.raises(ContractValidationError) as exc_info:
            raise ContractValidationError("Test error")
        assert "Test error" in str(exc_info.value)


class TestSchemaLoadError:
    """Tests for SchemaLoadError."""

    def test_basic_creation(self):
        """Test creating schema load error."""
        error = SchemaLoadError("/path/to/schema.json", "File not found")

        assert "/path/to/schema.json" in str(error)
        assert "File not found" in str(error)
        assert error.schema_path == "/path/to/schema.json"
        assert error.reason == "File not found"

    def test_formatted_message(self):
        """Test error message is properly formatted."""
        error = SchemaLoadError("schema.json", "Invalid JSON")

        assert "Failed to load schema" in str(error)
        assert "schema.json" in str(error)
        assert "Invalid JSON" in str(error)

    def test_is_exception(self):
        """Test SchemaLoadError is an Exception."""
        error = SchemaLoadError("path", "reason")
        assert isinstance(error, Exception)

    def test_can_be_raised_and_caught(self):
        """Test error can be raised and caught."""
        with pytest.raises(SchemaLoadError) as exc_info:
            raise SchemaLoadError("test.json", "Not found")

        assert exc_info.value.schema_path == "test.json"
        assert exc_info.value.reason == "Not found"
