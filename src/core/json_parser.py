"""JSON response parser for LLM outputs.

Provides robust parsing of JSON from LLM responses which may include:
- Raw JSON
- JSON wrapped in markdown code blocks (```json ... ``` or ``` ... ```)
- JSON embedded in surrounding text
- JSON arrays as well as objects
"""

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


class JSONParseError(Exception):
    """Raised when JSON parsing fails after all attempts."""

    def __init__(self, message: str, content: str, attempts: list[str]):
        super().__init__(message)
        self.content = content
        self.attempts = attempts


def parse_json_response(
    content: str,
    *,
    allow_array: bool = True,
    strict: bool = False,
) -> dict | list | None:
    """Parse JSON from an LLM response, handling various formats.

    Attempts parsing in this order:
    1. Direct JSON parse (raw JSON)
    2. Extract from ```json ... ``` code block
    3. Extract from ``` ... ``` code block (generic)
    4. Find JSON object/array by matching braces/brackets

    Args:
        content: The LLM response text that may contain JSON
        allow_array: If True, also accept JSON arrays. If False, only objects.
        strict: If True, raise JSONParseError on failure. If False, return None.

    Returns:
        Parsed JSON as dict or list, or None if parsing fails and strict=False

    Raises:
        JSONParseError: If strict=True and parsing fails after all attempts
    """
    if not content or not content.strip():
        if strict:
            raise JSONParseError("Empty content", content or "", ["empty_check"])
        return None

    content = content.strip()
    attempts: list[str] = []

    # Attempt 1: Direct parse
    attempts.append("direct_parse")
    result = _try_direct_parse(content)
    if result is not None and _is_valid_type(result, allow_array):
        return result

    # Attempt 2: Extract from ```json code block
    attempts.append("json_code_block")
    result = _try_json_code_block(content)
    if result is not None and _is_valid_type(result, allow_array):
        return result

    # Attempt 3: Extract from generic ``` code block
    attempts.append("generic_code_block")
    result = _try_generic_code_block(content)
    if result is not None and _is_valid_type(result, allow_array):
        return result

    # Attempt 4: Find JSON by brace/bracket matching
    attempts.append("brace_matching")
    result = _try_brace_matching(content, allow_array)
    if result is not None and _is_valid_type(result, allow_array):
        return result

    # Attempt 5: Try to fix common JSON issues and retry
    attempts.append("fix_and_retry")
    result = _try_fix_and_parse(content)
    if result is not None and _is_valid_type(result, allow_array):
        return result

    # All attempts failed
    if strict:
        raise JSONParseError(
            f"Failed to parse JSON after {len(attempts)} attempts", content, attempts
        )

    logger.debug(f"JSON parse failed after attempts: {attempts}")
    return None


def _is_valid_type(result: Any, allow_array: bool) -> bool:
    """Check if result is a valid JSON type."""
    if isinstance(result, dict):
        return True
    return bool(isinstance(result, list) and allow_array)


def _try_direct_parse(content: str) -> dict | list | None:
    """Attempt direct JSON parsing."""
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return None


def _try_json_code_block(content: str) -> dict | list | None:
    """Extract and parse JSON from ```json ... ``` code block."""
    if "```json" not in content.lower():
        return None

    try:
        # Case-insensitive match for ```json
        pattern = r"```[jJ][sS][oO][nN]\s*\n?(.*?)\n?```"
        match = re.search(pattern, content, re.DOTALL)
        if match:
            json_str = match.group(1).strip()
            # Try direct parse first
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                # Try fixing common issues
                fixed = _try_fix_and_parse(json_str)
                if fixed is not None:
                    return fixed

        # Fallback: simple split
        parts = content.lower().split("```json")
        if len(parts) > 1:
            # Find the actual position in original content
            idx = content.lower().find("```json") + 7
            remainder = content[idx:]
            if "```" in remainder:
                json_str = remainder.split("```")[0].strip()
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    # Try fixing common issues
                    fixed = _try_fix_and_parse(json_str)
                    if fixed is not None:
                        return fixed
    except (json.JSONDecodeError, IndexError):
        pass

    return None


def _try_generic_code_block(content: str) -> dict | list | None:
    """Extract and parse JSON from generic ``` ... ``` code block."""
    if "```" not in content:
        return None

    try:
        # Find all code blocks
        pattern = r"```\s*\n?(.*?)\n?```"
        matches = re.findall(pattern, content, re.DOTALL)

        for match in matches:
            json_str = match.strip()
            # Skip if it looks like a language identifier only
            if not json_str or json_str in ("json", "javascript", "python"):
                continue
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                continue
    except (json.JSONDecodeError, IndexError):
        pass

    return None


def _try_brace_matching(content: str, allow_array: bool) -> dict | list | None:
    """Find JSON by locating matching braces/brackets."""
    # Try to find JSON object
    obj_result = _extract_by_delimiters(content, "{", "}")
    if obj_result is not None:
        return obj_result

    # Try to find JSON array if allowed
    if allow_array:
        arr_result = _extract_by_delimiters(content, "[", "]")
        if arr_result is not None:
            return arr_result

    return None


def _extract_by_delimiters(content: str, open_char: str, close_char: str) -> dict | list | None:
    """Extract JSON by finding matching delimiters."""
    start = content.find(open_char)
    if start < 0:
        return None

    # Find the matching closing delimiter
    end = content.rfind(close_char)
    if end <= start:
        return None

    try:
        json_str = content[start : end + 1]
        return json.loads(json_str)
    except json.JSONDecodeError:
        pass

    # Try finding a valid JSON by iterating through possible end positions
    # This handles cases where there's trailing content after the JSON
    depth = 0
    in_string = False
    escape_next = False

    for i, char in enumerate(content[start:], start=start):
        if escape_next:
            escape_next = False
            continue

        if char == "\\":
            escape_next = True
            continue

        if char == '"' and not escape_next:
            in_string = not in_string
            continue

        if in_string:
            continue

        if char == open_char:
            depth += 1
        elif char == close_char:
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(content[start : i + 1])
                except json.JSONDecodeError:
                    pass
                break

    return None


def _try_fix_and_parse(content: str) -> dict | list | None:
    """Try to fix common JSON issues and parse."""
    # Find potential JSON region first
    start = content.find("{")
    end = content.rfind("}")
    if start < 0 or end <= start:
        start = content.find("[")
        end = content.rfind("]")
        if start < 0 or end <= start:
            return None

    json_str = content[start : end + 1]

    # Common fixes
    fixes = [
        # Fix trailing commas before closing braces/brackets
        (r",\s*([}\]])", r"\1"),
        # Fix single quotes to double quotes (careful with apostrophes)
        (r"'([^']*)'(?=\s*:)", r'"\1"'),  # Keys
        (r":\s*'([^']*)'", r': "\1"'),  # String values
        # Fix unquoted keys
        (r"([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)(\s*:)", r'\1"\2"\3'),
        # Fix Python True/False/None to JSON true/false/null
        (r"\bTrue\b", "true"),
        (r"\bFalse\b", "false"),
        (r"\bNone\b", "null"),
    ]

    fixed = json_str
    for pattern, replacement in fixes:
        fixed = re.sub(pattern, replacement, fixed)

    try:
        return json.loads(fixed)
    except json.JSONDecodeError:
        pass

    return None


# Convenience function for backward compatibility
def extract_json(content: str) -> dict | None:
    """Extract a JSON object from LLM response.

    This is a convenience wrapper that only returns dict objects.
    For full functionality, use parse_json_response() directly.

    Args:
        content: The LLM response text

    Returns:
        Parsed JSON dict, or None if parsing fails
    """
    result = parse_json_response(content, allow_array=False)
    if isinstance(result, dict):
        return result
    return None
