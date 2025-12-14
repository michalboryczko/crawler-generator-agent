"""Safe serialization utilities for observability data.

This module provides utilities for safely serializing any object for logging.
IMPORTANT: Does NOT truncate data. Full data is always captured.
Truncation happens at query/display time, not emission time.
"""

from typing import Any
from datetime import datetime, date
from dataclasses import is_dataclass, asdict
from enum import Enum
from pathlib import Path
import uuid


def safe_serialize(obj: Any, max_depth: int = 10, current_depth: int = 0) -> Any:
    """Safely serialize any object for logging.
    
    Handles:
    - Primitives (str, int, float, bool, None)
    - Dataclasses
    - Enums
    - Datetime objects
    - Paths
    - UUIDs
    - Nested structures (dicts, lists, tuples, sets)
    - Circular references (via depth limit)
    - Non-serializable objects (converted to str)
    
    IMPORTANT: Does NOT truncate data. Full data is always captured.
    Truncation happens at query/display time, not emission time.
    
    Args:
        obj: Object to serialize
        max_depth: Maximum nesting depth to prevent infinite recursion
        current_depth: Current depth in recursion (internal use)
        
    Returns:
        JSON-serializable representation of the object
    """
    if current_depth > max_depth:
        return f"<max depth {max_depth} exceeded>"

    if obj is None:
        return None

    if isinstance(obj, (str, int, float, bool)):
        return obj

    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    
    if isinstance(obj, Path):
        return str(obj)
    
    if isinstance(obj, uuid.UUID):
        return str(obj)

    if isinstance(obj, Enum):
        return obj.value

    if is_dataclass(obj) and not isinstance(obj, type):
        try:
            return safe_serialize(asdict(obj), max_depth, current_depth + 1)
        except Exception:
            # Some dataclasses may fail to convert, fallback to __dict__
            if hasattr(obj, '__dict__'):
                return safe_serialize(obj.__dict__, max_depth, current_depth + 1)
            return str(obj)

    if isinstance(obj, dict):
        return {
            safe_serialize(k, max_depth, current_depth + 1): safe_serialize(v, max_depth, current_depth + 1)
            for k, v in obj.items()
        }

    if isinstance(obj, (list, tuple)):
        return [safe_serialize(item, max_depth, current_depth + 1) for item in obj]

    if isinstance(obj, set):
        return [safe_serialize(item, max_depth, current_depth + 1) for item in sorted(obj, key=str)]
    
    if isinstance(obj, bytes):
        try:
            return obj.decode('utf-8')
        except UnicodeDecodeError:
            return f"<bytes: {len(obj)} bytes>"
    
    if isinstance(obj, type):
        return f"<class {obj.__name__}>"

    if hasattr(obj, '__dict__'):
        try:
            return safe_serialize(obj.__dict__, max_depth, current_depth + 1)
        except Exception:
            pass

    # Fallback to string representation
    try:
        return str(obj)
    except Exception:
        return f"<unserializable: {type(obj).__name__}>"


def truncate_for_display(obj: Any, max_length: int = 1000) -> Any:
    """Truncate strings for display purposes only.
    
    NOTE: This is for DISPLAY only, not for storage.
    Full data should always be stored.
    
    Args:
        obj: Object to truncate for display
        max_length: Maximum string length
        
    Returns:
        Truncated representation
    """
    if isinstance(obj, str) and len(obj) > max_length:
        return obj[:max_length] + f"... ({len(obj)} chars total)"
    
    if isinstance(obj, dict):
        return {k: truncate_for_display(v, max_length) for k, v in obj.items()}
    
    if isinstance(obj, (list, tuple)):
        return [truncate_for_display(item, max_length) for item in obj]
    
    return obj


def redact_sensitive(obj: Any, patterns: list = None) -> Any:
    """Redact sensitive data from objects.
    
    Args:
        obj: Object to redact
        patterns: List of key patterns to redact (default: password, secret, token, key, auth)
        
    Returns:
        Object with sensitive values redacted
    """
    if patterns is None:
        patterns = ['password', 'secret', 'token', 'key', 'auth', 'credential', 'api_key', 'apikey']
    
    def should_redact(key: str) -> bool:
        key_lower = key.lower()
        return any(pattern in key_lower for pattern in patterns)
    
    if isinstance(obj, dict):
        result = {}
        for k, v in obj.items():
            if isinstance(k, str) and should_redact(k):
                result[k] = "[REDACTED]"
            else:
                result[k] = redact_sensitive(v, patterns)
        return result
    
    if isinstance(obj, (list, tuple)):
        return [redact_sensitive(item, patterns) for item in obj]
    
    return obj


def extract_error_info(exception: Exception) -> dict:
    """Extract detailed error information from an exception.
    
    Args:
        exception: The exception to extract info from
        
    Returns:
        Dictionary with error details
    """
    import traceback
    
    return {
        "error_type": type(exception).__name__,
        "error_message": str(exception),
        "error_module": type(exception).__module__,
        "stack_trace": traceback.format_exc(),
        "exception_args": safe_serialize(exception.args)
    }
