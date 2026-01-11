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


class TestMemorySessionCopy:
    """Test copying memory between sessions for --copy mode."""

    def test_copy_all_memory_entries(self):
        """Copy all memory entries from source to target session."""
        repo = InMemoryRepository()

        # Create source session with multiple agents and entries
        source_agent1 = MemoryService(repo, "source-session", "agent1")
        source_agent2 = MemoryService(repo, "source-session", "agent2")

        source_agent1.write("key1", "value1")
        source_agent1.write("key2", "value2")
        source_agent2.write("key3", "value3")

        # Copy to target session
        copied = MemoryService.copy_session_memory(
            repository=repo,
            source_session_id="source-session",
            target_session_id="target-session",
        )

        assert copied == 3

        # Verify entries exist in target session
        target_agent1 = MemoryService(repo, "target-session", "agent1")
        target_agent2 = MemoryService(repo, "target-session", "agent2")

        assert target_agent1.read("key1") == "value1"
        assert target_agent1.read("key2") == "value2"
        assert target_agent2.read("key3") == "value3"

    def test_copy_with_timestamp_filter(self):
        """Copy only entries created before a specific timestamp."""
        from datetime import timedelta

        repo = InMemoryRepository()

        # Create source session entries
        source_agent = MemoryService(repo, "source-session", "agent")
        source_agent.write("early_key", "early_value")

        # Get the entry's created_at timestamp
        entry1 = repo.get("source-session", "agent", "early_key")
        cutoff = entry1.created_at + timedelta(milliseconds=1)

        # Create another entry "later"
        source_agent.write("late_key", "late_value")

        # Manually backdate the late entry for testing
        # (In real code, entries are created with current timestamp)
        late_entry = repo.get("source-session", "agent", "late_key")
        late_entry.created_at = cutoff + timedelta(seconds=1)

        # Copy with timestamp filter
        copied = MemoryService.copy_session_memory(
            repository=repo,
            source_session_id="source-session",
            target_session_id="target-session",
            up_to_timestamp=cutoff,
        )

        assert copied == 1

        # Verify only early entry was copied
        target_agent = MemoryService(repo, "target-session", "agent")
        assert target_agent.read("early_key") == "early_value"
        assert target_agent.read("late_key") is None

    def test_copy_preserves_agent_isolation(self):
        """Copied entries maintain their agent name isolation."""
        repo = InMemoryRepository()

        # Create entries for different agents
        MemoryService(repo, "source", "browser").write("data", "browser_data")
        MemoryService(repo, "source", "selector").write("data", "selector_data")

        # Copy session
        copied = MemoryService.copy_session_memory(
            repository=repo,
            source_session_id="source",
            target_session_id="target",
        )

        assert copied == 2

        # Verify agent isolation is preserved
        target_browser = MemoryService(repo, "target", "browser")
        target_selector = MemoryService(repo, "target", "selector")

        assert target_browser.read("data") == "browser_data"
        assert target_selector.read("data") == "selector_data"

    def test_copy_empty_session(self):
        """Copying from empty session returns 0."""
        repo = InMemoryRepository()

        copied = MemoryService.copy_session_memory(
            repository=repo,
            source_session_id="empty-source",
            target_session_id="target",
        )

        assert copied == 0

    def test_copy_doesnt_affect_source(self):
        """Copying doesn't modify source session entries."""
        repo = InMemoryRepository()

        source_agent = MemoryService(repo, "source", "agent")
        source_agent.write("key", "original_value")

        # Copy to target
        MemoryService.copy_session_memory(
            repository=repo,
            source_session_id="source",
            target_session_id="target",
        )

        # Modify target
        target_agent = MemoryService(repo, "target", "agent")
        target_agent.write("key", "modified_value")

        # Source should be unchanged
        assert source_agent.read("key") == "original_value"
        assert target_agent.read("key") == "modified_value"
