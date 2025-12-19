"""Tests for custom exception hierarchy."""

import pytest

from src.core.exceptions import (
    BrowserError,
    ConfigError,
    CrawlerError,
    LLMError,
    ToolError,
    ValidationError,
)


class TestCrawlerError:
    """Tests for base CrawlerError."""

    def test_basic_creation(self):
        """Test creating basic error."""
        error = CrawlerError("Something went wrong")
        assert str(error) == "Something went wrong"
        assert error.message == "Something went wrong"
        assert error.details == {}

    def test_with_details(self):
        """Test creating error with details."""
        error = CrawlerError("Error", details={"code": 500})
        assert error.details == {"code": 500}

    def test_is_exception(self):
        """Test CrawlerError is an Exception."""
        error = CrawlerError("Error")
        assert isinstance(error, Exception)

    def test_can_be_raised_and_caught(self):
        """Test error can be raised and caught."""
        with pytest.raises(CrawlerError) as exc_info:
            raise CrawlerError("Test error")
        assert "Test error" in str(exc_info.value)


class TestToolError:
    """Tests for ToolError."""

    def test_basic_creation(self):
        """Test creating tool error."""
        error = ToolError("memory_read", "Key not found")
        assert "memory_read" in str(error)
        assert "Key not found" in str(error)
        assert error.tool_name == "memory_read"

    def test_inherits_crawler_error(self):
        """Test ToolError inherits from CrawlerError."""
        error = ToolError("tool", "error")
        assert isinstance(error, CrawlerError)

    def test_with_details(self):
        """Test tool error with details."""
        error = ToolError("http_request", "Timeout", details={"url": "http://example.com"})
        assert error.details == {"url": "http://example.com"}

    def test_catch_as_crawler_error(self):
        """Test ToolError can be caught as CrawlerError."""
        with pytest.raises(CrawlerError):
            raise ToolError("tool", "error")


class TestLLMError:
    """Tests for LLMError."""

    def test_basic_creation(self):
        """Test creating LLM error."""
        error = LLMError("Rate limit exceeded")
        assert "Rate limit exceeded" in str(error)
        assert error.provider == "unknown"
        assert error.status_code is None

    def test_with_provider(self):
        """Test LLM error with provider."""
        error = LLMError("API error", provider="openai")
        assert error.provider == "openai"
        assert "openai" in str(error)

    def test_with_status_code(self):
        """Test LLM error with status code."""
        error = LLMError("Rate limited", provider="openai", status_code=429)
        assert error.status_code == 429

    def test_inherits_crawler_error(self):
        """Test LLMError inherits from CrawlerError."""
        error = LLMError("error")
        assert isinstance(error, CrawlerError)


class TestBrowserError:
    """Tests for BrowserError."""

    def test_basic_creation(self):
        """Test creating browser error."""
        error = BrowserError("Connection failed")
        assert "Connection failed" in str(error)
        assert error.operation == "unknown"
        assert error.url is None

    def test_with_operation(self):
        """Test browser error with operation."""
        error = BrowserError("Element not found", operation="click")
        assert error.operation == "click"
        assert "click" in str(error)

    def test_with_url(self):
        """Test browser error with URL."""
        error = BrowserError("Page load timeout", operation="navigate", url="http://example.com")
        assert error.url == "http://example.com"

    def test_inherits_crawler_error(self):
        """Test BrowserError inherits from CrawlerError."""
        error = BrowserError("error")
        assert isinstance(error, CrawlerError)


class TestConfigError:
    """Tests for ConfigError."""

    def test_basic_creation(self):
        """Test creating config error."""
        error = ConfigError("Invalid value")
        assert "Configuration error" in str(error)
        assert "Invalid value" in str(error)

    def test_with_config_key(self):
        """Test config error with key."""
        error = ConfigError("Must be positive", config_key="timeout")
        assert error.config_key == "timeout"

    def test_inherits_crawler_error(self):
        """Test ConfigError inherits from CrawlerError."""
        error = ConfigError("error")
        assert isinstance(error, CrawlerError)


class TestValidationError:
    """Tests for ValidationError."""

    def test_basic_creation(self):
        """Test creating validation error."""
        error = ValidationError("Invalid email format")
        assert "Validation error" in str(error)
        assert "Invalid email format" in str(error)

    def test_with_field(self):
        """Test validation error with field."""
        error = ValidationError("Required field", field="email")
        assert error.field == "email"

    def test_inherits_crawler_error(self):
        """Test ValidationError inherits from CrawlerError."""
        error = ValidationError("error")
        assert isinstance(error, CrawlerError)


class TestExceptionHierarchy:
    """Tests for exception hierarchy and isinstance checks."""

    def test_all_errors_are_crawler_errors(self):
        """Test all custom errors inherit from CrawlerError."""
        errors = [
            ToolError("tool", "msg"),
            LLMError("msg"),
            BrowserError("msg"),
            ConfigError("msg"),
            ValidationError("msg"),
        ]
        for error in errors:
            assert isinstance(error, CrawlerError)
            assert isinstance(error, Exception)

    def test_catch_specific_then_general(self):
        """Test specific exceptions can be caught before general."""
        caught_type = None

        try:
            raise ToolError("tool", "error")
        except ToolError:
            caught_type = "tool"
        except CrawlerError:
            caught_type = "crawler"

        assert caught_type == "tool"

    def test_catch_general_catches_all(self):
        """Test CrawlerError catches all specific types."""
        error_types = [
            ToolError("t", "m"),
            LLMError("m"),
            BrowserError("m"),
            ConfigError("m"),
            ValidationError("m"),
        ]

        for error in error_types:
            try:
                raise error
            except CrawlerError as e:
                assert e is error  # Same object was caught
