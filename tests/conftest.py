"""Shared test fixtures for all tests."""

import pytest

from src.repositories.inmemory import InMemoryRepository
from src.services.memory_service import MemoryService


@pytest.fixture
def memory_repository():
    """Create a fresh InMemoryRepository for testing."""
    return InMemoryRepository()


@pytest.fixture
def memory_service(memory_repository):
    """Create a fresh MemoryService for testing."""
    return MemoryService(
        repository=memory_repository,
        session_id="test-session",
        agent_name="test-agent",
    )


@pytest.fixture
def populated_memory_service(memory_service):
    """Create a MemoryService with sample data."""
    memory_service.write("user.name", "Test User")
    memory_service.write("user.email", "test@example.com")
    memory_service.write("articles.item1", {"title": "Article 1", "url": "http://example.com/1"})
    memory_service.write("articles.item2", {"title": "Article 2", "url": "http://example.com/2"})
    memory_service.write("config.timeout", 30)
    return memory_service


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
