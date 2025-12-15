"""Shared test fixtures for all tests."""

import pytest

from src.tools.memory import MemoryStore


@pytest.fixture
def memory_store():
    """Create a fresh MemoryStore for testing."""
    return MemoryStore()


@pytest.fixture
def populated_memory_store(memory_store):
    """Create a MemoryStore with sample data."""
    memory_store.write("user.name", "Test User")
    memory_store.write("user.email", "test@example.com")
    memory_store.write("articles.item1", {"title": "Article 1", "url": "http://example.com/1"})
    memory_store.write("articles.item2", {"title": "Article 2", "url": "http://example.com/2"})
    memory_store.write("config.timeout", 30)
    return memory_store


@pytest.fixture
def mock_llm_response():
    """Create a mock LLM response for testing."""
    return {
        "role": "assistant",
        "content": "This is a test response.",
        "finish_reason": "stop",
        "tool_calls": None,
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 20,
            "total_tokens": 30,
        },
    }


@pytest.fixture
def mock_llm_tool_response():
    """Create a mock LLM response with tool calls."""
    return {
        "role": "assistant",
        "content": None,
        "finish_reason": "tool_calls",
        "tool_calls": [
            {
                "id": "call_123",
                "name": "memory_read",
                "arguments": {"key": "user.name"},
            }
        ],
        "usage": {
            "prompt_tokens": 15,
            "completion_tokens": 25,
            "total_tokens": 40,
        },
    }
