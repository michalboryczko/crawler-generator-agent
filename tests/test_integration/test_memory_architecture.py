"""Integration tests for memory isolation.

These tests verify the memory architecture where:
1. Each agent has an isolated MemoryService
2. Data is properly isolated by agent name within a session
"""

from src.core.config import StorageConfig
from src.infrastructure import init_container
from src.repositories.inmemory import InMemoryRepository
from src.services.memory_service import MemoryService


class TestContainerAndMemoryService:
    """Test Container and MemoryService integration."""

    def test_container_creates_memory_services(self):
        """Container creates isolated memory services per agent."""
        config = StorageConfig(backend_type="memory")
        container = init_container(config)

        service1 = container.memory_service("browser")
        service2 = container.memory_service("selector")

        # Both services use the same repository but different agent names
        service1.write("key", "value1")
        service2.write("key", "value2")

        assert service1.read("key") == "value1"
        assert service2.read("key") == "value2"

    def test_container_session_isolation(self):
        """Different containers have different sessions."""
        config = StorageConfig(backend_type="memory")
        container1 = init_container(config)
        container2 = init_container(config)

        service1 = container1.memory_service("agent")
        service2 = container2.memory_service("agent")

        service1.write("key", "value1")
        service2.write("key", "value2")

        # Different sessions, so data is isolated
        assert service1.read("key") == "value1"
        assert service2.read("key") == "value2"


class TestMemoryServiceIsolation:
    """Test that memory services provide proper isolation."""

    def test_agent_isolation_with_shared_repo(self):
        """Multiple services on same repo are isolated by agent name."""
        repo = InMemoryRepository()
        session_id = "test-session"

        browser_service = MemoryService(repo, session_id, "browser")
        selector_service = MemoryService(repo, session_id, "selector")
        accessibility_service = MemoryService(repo, session_id, "accessibility")
        data_prep_service = MemoryService(repo, session_id, "data_prep")

        # Write same key to each service
        browser_service.write("result", "browser_data")
        selector_service.write("result", "selector_data")
        accessibility_service.write("result", "accessibility_data")
        data_prep_service.write("result", "data_prep_data")

        # Each service sees only its own data
        assert browser_service.read("result") == "browser_data"
        assert selector_service.read("result") == "selector_data"
        assert accessibility_service.read("result") == "accessibility_data"
        assert data_prep_service.read("result") == "data_prep_data"

    def test_write_to_one_service_doesnt_affect_others(self):
        """Writing to one service doesn't leak to others."""
        repo = InMemoryRepository()

        service1 = MemoryService(repo, "session", "agent1")
        service2 = MemoryService(repo, "session", "agent2")

        service1.write("secret", "agent1_data")

        assert service1.read("secret") == "agent1_data"
        assert service2.read("secret") is None
