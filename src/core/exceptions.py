"""Custom exception hierarchy for the crawler agent.

Provides typed exceptions for better error handling and classification.
"""


class CrawlerError(Exception):
    """Base exception for all crawler errors.

    All custom exceptions inherit from this, allowing:
        try:
            ...
        except CrawlerError as e:
            # Handle any crawler-specific error
    """

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ToolError(CrawlerError):
    """Error during tool execution.

    Raised when a tool fails to complete its operation.

    Attributes:
        tool_name: Name of the tool that failed
        message: Error description
        details: Additional context
    """

    def __init__(self, tool_name: str, message: str, details: dict | None = None):
        super().__init__(f"Tool '{tool_name}' failed: {message}", details)
        self.tool_name = tool_name


class LLMError(CrawlerError):
    """Error from LLM communication.

    Raised when LLM API calls fail or return unexpected results.

    Attributes:
        provider: LLM provider (e.g., "openai", "anthropic")
        message: Error description
        status_code: HTTP status code if applicable
    """

    def __init__(
        self,
        message: str,
        provider: str = "unknown",
        status_code: int | None = None,
        details: dict | None = None,
    ):
        super().__init__(f"LLM error ({provider}): {message}", details)
        self.provider = provider
        self.status_code = status_code


class BrowserError(CrawlerError):
    """Error from browser operations.

    Raised when browser automation fails.

    Attributes:
        operation: The browser operation that failed
        url: URL being accessed when error occurred
    """

    def __init__(
        self,
        message: str,
        operation: str = "unknown",
        url: str | None = None,
        details: dict | None = None,
    ):
        super().__init__(f"Browser error during {operation}: {message}", details)
        self.operation = operation
        self.url = url


class ConfigError(CrawlerError):
    """Error in configuration.

    Raised when configuration is invalid or missing.

    Attributes:
        config_key: The configuration key that caused the error
    """

    def __init__(
        self,
        message: str,
        config_key: str | None = None,
        details: dict | None = None,
    ):
        super().__init__(f"Configuration error: {message}", details)
        self.config_key = config_key


class ValidationError(CrawlerError):
    """Error in data validation.

    Raised when input data fails validation.

    Attributes:
        field: The field that failed validation
    """

    def __init__(
        self,
        message: str,
        field: str | None = None,
        details: dict | None = None,
    ):
        super().__init__(f"Validation error: {message}", details)
        self.field = field
