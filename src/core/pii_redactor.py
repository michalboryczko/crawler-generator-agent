"""PII redaction utilities for structured logging.

Provides patterns and utilities to redact Personally Identifiable Information
(PII) from log entries before they are written to outputs.
"""

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PIIRedactor:
    """Redacts PII from log data.

    Supports redaction of:
    - Email addresses
    - Phone numbers (US format)
    - Credit card numbers
    - Social Security Numbers
    - API keys and tokens
    - Custom patterns
    """

    # Default patterns for common PII
    default_patterns: dict[str, str] = field(default_factory=lambda: {
        "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        "phone_us": r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",
        "credit_card": r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b",
        "ssn": r"\b\d{3}[-]?\d{2}[-]?\d{4}\b",
        "api_key": r"\b(sk-|pk-|api[_-]?key[=:]?\s*)[A-Za-z0-9_-]{20,}\b",
        "bearer_token": r"\bBearer\s+[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b",
        "password": r"\b(password|passwd|pwd)[=:]\s*\S+\b",
    })

    # Replacement text for redacted values
    redaction_markers: dict[str, str] = field(default_factory=lambda: {
        "email": "[EMAIL_REDACTED]",
        "phone_us": "[PHONE_REDACTED]",
        "credit_card": "[CREDIT_CARD_REDACTED]",
        "ssn": "[SSN_REDACTED]",
        "api_key": "[API_KEY_REDACTED]",
        "bearer_token": "[TOKEN_REDACTED]",
        "password": "[PASSWORD_REDACTED]",
    })

    # Fields to always redact completely
    sensitive_fields: set[str] = field(default_factory=lambda: {
        "password", "passwd", "pwd", "secret", "token", "api_key",
        "apikey", "auth", "credential", "private_key", "access_token",
        "refresh_token", "session_id", "session_token",
    })

    enabled: bool = True
    custom_patterns: dict[str, tuple[str, str]] = field(default_factory=dict)

    def __post_init__(self):
        """Compile regex patterns."""
        self._compiled_patterns: dict[str, re.Pattern] = {}
        for name, pattern in self.default_patterns.items():
            self._compiled_patterns[name] = re.compile(pattern, re.IGNORECASE)
        for name, (pattern, _) in self.custom_patterns.items():
            self._compiled_patterns[name] = re.compile(pattern, re.IGNORECASE)

    def add_pattern(self, name: str, pattern: str, replacement: str) -> None:
        """Add a custom redaction pattern.

        Args:
            name: Pattern name for identification
            pattern: Regex pattern to match
            replacement: Replacement text for matched content
        """
        self.custom_patterns[name] = (pattern, replacement)
        self._compiled_patterns[name] = re.compile(pattern, re.IGNORECASE)
        self.redaction_markers[name] = replacement

    def redact_string(self, value: str) -> str:
        """Redact PII from a string value.

        Args:
            value: String to redact

        Returns:
            String with PII redacted
        """
        if not self.enabled or not value:
            return value

        result = value
        for name, pattern in self._compiled_patterns.items():
            replacement = self.redaction_markers.get(name, f"[{name.upper()}_REDACTED]")
            result = pattern.sub(replacement, result)

        return result

    def redact_dict(self, data: dict[str, Any], depth: int = 0, max_depth: int = 10) -> dict[str, Any]:
        """Recursively redact PII from a dictionary.

        Args:
            data: Dictionary to redact
            depth: Current recursion depth
            max_depth: Maximum recursion depth to prevent infinite loops

        Returns:
            Dictionary with PII redacted
        """
        if not self.enabled or depth > max_depth:
            return data

        result = {}
        for key, value in data.items():
            # Check if key itself is sensitive
            key_lower = key.lower()
            if any(sensitive in key_lower for sensitive in self.sensitive_fields):
                result[key] = "[REDACTED]"
                continue

            # Recursively process value
            result[key] = self._redact_value(value, depth, max_depth)

        return result

    def _redact_value(self, value: Any, depth: int, max_depth: int) -> Any:
        """Redact PII from a value of any type.

        Args:
            value: Value to redact
            depth: Current recursion depth
            max_depth: Maximum recursion depth

        Returns:
            Value with PII redacted
        """
        if isinstance(value, str):
            return self.redact_string(value)
        elif isinstance(value, dict):
            return self.redact_dict(value, depth + 1, max_depth)
        elif isinstance(value, list):
            return [self._redact_value(item, depth + 1, max_depth) for item in value]
        elif isinstance(value, tuple):
            return tuple(self._redact_value(item, depth + 1, max_depth) for item in value)
        else:
            return value

    def redact_url(self, url: str) -> str:
        """Redact sensitive query parameters from URLs.

        Args:
            url: URL to redact

        Returns:
            URL with sensitive parameters redacted
        """
        if not self.enabled or not url:
            return url

        # First apply general string redaction
        result = self.redact_string(url)

        # Redact common sensitive query params
        sensitive_params = ["token", "key", "apikey", "api_key", "password", "auth", "secret"]
        for param in sensitive_params:
            # Match param=value patterns in query strings
            pattern = rf"([?&]{param}=)[^&\s]+"
            result = re.sub(pattern, r"\1[REDACTED]", result, flags=re.IGNORECASE)

        return result


# Global default redactor instance
_default_redactor: PIIRedactor | None = None


def get_redactor() -> PIIRedactor:
    """Get the default PII redactor instance.

    Returns:
        Default PIIRedactor instance
    """
    global _default_redactor
    if _default_redactor is None:
        _default_redactor = PIIRedactor()
    return _default_redactor


def set_redactor(redactor: PIIRedactor) -> None:
    """Set the default PII redactor instance.

    Args:
        redactor: PIIRedactor instance to use as default
    """
    global _default_redactor
    _default_redactor = redactor


def redact(value: Any) -> Any:
    """Redact PII from a value using the default redactor.

    Args:
        value: Value to redact (string, dict, list, etc.)

    Returns:
        Value with PII redacted
    """
    redactor = get_redactor()
    if isinstance(value, str):
        return redactor.redact_string(value)
    elif isinstance(value, dict):
        return redactor.redact_dict(value)
    elif isinstance(value, list):
        return [redact(item) for item in value]
    else:
        return value
