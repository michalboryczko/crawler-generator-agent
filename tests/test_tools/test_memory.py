"""Tests for memory tools."""

import tempfile
from pathlib import Path

import pytest

from src.repositories.inmemory import InMemoryRepository
from src.services.memory_service import MemoryService
from src.tools.memory import (
    MemoryDumpTool,
    MemoryListTool,
    MemoryReadTool,
    MemorySearchTool,
    MemoryWriteTool,
)


@pytest.fixture
def memory_service():
    """Create a fresh MemoryService for testing."""
    repo = InMemoryRepository()
    return MemoryService(
        repository=repo,
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


class TestMemoryService:
    """Tests for MemoryService class."""

    def test_write_and_read(self, memory_service):
        """Test basic write and read."""
        memory_service.write("key1", "value1")
        assert memory_service.read("key1") == "value1"

    def test_read_nonexistent(self, memory_service):
        """Test reading nonexistent key returns None."""
        assert memory_service.read("nonexistent") is None

    def test_overwrite(self, memory_service):
        """Test overwriting existing key."""
        memory_service.write("key", "value1")
        memory_service.write("key", "value2")
        assert memory_service.read("key") == "value2"

    def test_delete_existing(self, memory_service):
        """Test deleting existing key."""
        memory_service.write("key", "value")
        assert memory_service.delete("key") is True
        assert memory_service.read("key") is None

    def test_delete_nonexistent(self, memory_service):
        """Test deleting nonexistent key returns False."""
        assert memory_service.delete("nonexistent") is False

    def test_search_pattern(self, populated_memory_service):
        """Test searching with glob pattern."""
        keys = populated_memory_service.search("user.*")
        assert sorted(keys) == ["user.email", "user.name"]

    def test_search_wildcard(self, populated_memory_service):
        """Test searching with wildcard."""
        keys = populated_memory_service.search("articles.*")
        assert len(keys) == 2
        assert "articles.item1" in keys
        assert "articles.item2" in keys

    def test_search_no_match(self, populated_memory_service):
        """Test searching with no matches."""
        keys = populated_memory_service.search("nonexistent.*")
        assert keys == []

    def test_list_keys(self, populated_memory_service):
        """Test listing all keys."""
        keys = populated_memory_service.list_keys()
        assert len(keys) == 5
        assert "user.name" in keys
        assert "articles.item1" in keys

    def test_list_keys_empty(self, memory_service):
        """Test listing keys on empty store."""
        assert memory_service.list_keys() == []

    def test_clear(self, populated_memory_service):
        """Test clearing all data."""
        populated_memory_service.clear()
        assert populated_memory_service.list_keys() == []

    def test_dump_to_jsonl(self, populated_memory_service):
        """Test dumping to JSONL file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "output.jsonl"
            count = populated_memory_service.dump_to_jsonl(
                ["user.name", "user.email"],
                output_path,
            )
            assert count == 2
            assert output_path.exists()

            content = output_path.read_text()
            lines = content.strip().split("\n")
            assert len(lines) == 2
            assert '"Test User"' in lines[0]
            assert '"test@example.com"' in lines[1]

    def test_dump_to_jsonl_missing_keys(self, populated_memory_service):
        """Test dumping with some missing keys."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "output.jsonl"
            count = populated_memory_service.dump_to_jsonl(
                ["user.name", "nonexistent"],
                output_path,
            )
            assert count == 1  # Only one key exists


class TestMemoryServiceIsolation:
    """Tests for MemoryService isolation features."""

    def test_session_agent_isolation(self):
        """Test different session/agent combinations are isolated."""
        repo = InMemoryRepository()
        service1 = MemoryService(repo, "session1", "agent1")
        service2 = MemoryService(repo, "session1", "agent2")
        service3 = MemoryService(repo, "session2", "agent1")

        service1.write("key", "value1")
        service2.write("key", "value2")
        service3.write("key", "value3")

        assert service1.read("key") == "value1"
        assert service2.read("key") == "value2"
        assert service3.read("key") == "value3"

    def test_merge_from_all_keys(self):
        """Test merge copies all keys from source."""
        repo = InMemoryRepository()
        source = MemoryService(repo, "session", "source")
        source.write("key1", "value1")
        source.write("key2", "value2")
        source.write("key3", "value3")

        target = MemoryService(repo, "session", "target")
        count = target.merge_from(source)

        assert count == 3
        assert target.read("key1") == "value1"
        assert target.read("key2") == "value2"
        assert target.read("key3") == "value3"

    def test_merge_from_specific_keys(self):
        """Test only specified keys are merged."""
        repo = InMemoryRepository()
        source = MemoryService(repo, "session", "source")
        source.write("key1", "value1")
        source.write("key2", "value2")
        source.write("key3", "value3")

        target = MemoryService(repo, "session", "target")
        count = target.merge_from(source, keys=["key1", "key3"])

        assert count == 2
        assert target.read("key1") == "value1"
        assert target.read("key2") is None
        assert target.read("key3") == "value3"

    def test_merge_from_nonexistent_keys(self):
        """Test merge handles nonexistent keys gracefully."""
        repo = InMemoryRepository()
        source = MemoryService(repo, "session", "source")
        source.write("key1", "value1")

        target = MemoryService(repo, "session", "target")
        count = target.merge_from(source, keys=["key1", "nonexistent"])

        assert count == 1
        assert target.read("key1") == "value1"

    def test_export_keys(self):
        """Test export returns dict with only requested keys."""
        repo = InMemoryRepository()
        service = MemoryService(repo, "session", "agent")
        service.write("key1", "value1")
        service.write("key2", {"nested": "data"})
        service.write("key3", [1, 2, 3])

        exported = service.export_keys(["key1", "key2"])

        assert exported == {"key1": "value1", "key2": {"nested": "data"}}
        assert "key3" not in exported

    def test_export_keys_filters_nonexistent(self):
        """Test export filters out nonexistent keys."""
        repo = InMemoryRepository()
        service = MemoryService(repo, "session", "agent")
        service.write("key1", "value1")

        exported = service.export_keys(["key1", "nonexistent"])

        assert exported == {"key1": "value1"}
        assert "nonexistent" not in exported


class TestMemoryReadTool:
    """Tests for MemoryReadTool."""

    def test_read_existing(self, populated_memory_service):
        """Test reading existing key."""
        tool = MemoryReadTool(service=populated_memory_service)
        result = tool.execute(key="user.name")
        assert result["success"] is True
        assert result["result"] == "Test User"
        assert result["found"] is True

    def test_read_nonexistent(self, memory_service):
        """Test reading nonexistent key."""
        tool = MemoryReadTool(service=memory_service)
        result = tool.execute(key="nonexistent")
        assert result["success"] is True
        assert result["result"] is None
        assert result["found"] is False

    def test_get_parameters_schema(self, memory_service):
        """Test parameter schema."""
        tool = MemoryReadTool(service=memory_service)
        schema = tool.get_parameters_schema()
        assert schema["type"] == "object"
        assert "key" in schema["properties"]
        assert "key" in schema["required"]

    def test_name_and_description(self):
        """Test tool metadata."""
        assert MemoryReadTool.name == "memory_read"
        assert "Read" in MemoryReadTool.description


class TestMemoryWriteTool:
    """Tests for MemoryWriteTool."""

    def test_write_new_key(self, memory_service):
        """Test writing to new key."""
        tool = MemoryWriteTool(service=memory_service)
        result = tool.execute(key="new_key", value="new_value")
        assert result["success"] is True
        assert result["overwritten"] is False
        assert memory_service.read("new_key") == "new_value"

    def test_write_overwrite(self, populated_memory_service):
        """Test overwriting existing key."""
        tool = MemoryWriteTool(service=populated_memory_service)
        result = tool.execute(key="user.name", value="New Name")
        assert result["success"] is True
        assert result["overwritten"] is True
        assert populated_memory_service.read("user.name") == "New Name"

    def test_write_complex_value(self, memory_service):
        """Test writing complex value."""
        tool = MemoryWriteTool(service=memory_service)
        complex_value = {"nested": {"data": [1, 2, 3]}}
        result = tool.execute(key="complex", value=complex_value)
        assert result["success"] is True
        assert result["value_size"] > 0
        assert memory_service.read("complex") == complex_value

    def test_get_parameters_schema(self, memory_service):
        """Test parameter schema."""
        tool = MemoryWriteTool(service=memory_service)
        schema = tool.get_parameters_schema()
        assert "key" in schema["properties"]
        assert "value" in schema["properties"]
        assert "key" in schema["required"]
        assert "value" in schema["required"]


class TestMemorySearchTool:
    """Tests for MemorySearchTool."""

    def test_search_pattern(self, populated_memory_service):
        """Test searching with pattern."""
        tool = MemorySearchTool(service=populated_memory_service)
        result = tool.execute(pattern="articles.*")
        assert result["success"] is True
        assert result["count"] == 2
        assert "articles.item1" in result["result"]

    def test_search_no_match(self, populated_memory_service):
        """Test searching with no matches."""
        tool = MemorySearchTool(service=populated_memory_service)
        result = tool.execute(pattern="nonexistent.*")
        assert result["success"] is True
        assert result["count"] == 0
        assert result["result"] == []

    def test_get_parameters_schema(self, memory_service):
        """Test parameter schema."""
        tool = MemorySearchTool(service=memory_service)
        schema = tool.get_parameters_schema()
        assert "pattern" in schema["properties"]
        assert "pattern" in schema["required"]


class TestMemoryListTool:
    """Tests for MemoryListTool."""

    def test_list_populated(self, populated_memory_service):
        """Test listing populated store."""
        tool = MemoryListTool(service=populated_memory_service)
        result = tool.execute()
        assert result["success"] is True
        assert result["count"] == 5
        assert len(result["result"]) == 5

    def test_list_empty(self, memory_service):
        """Test listing empty store."""
        tool = MemoryListTool(service=memory_service)
        result = tool.execute()
        assert result["success"] is True
        assert result["count"] == 0
        assert result["result"] == []

    def test_get_parameters_schema(self, memory_service):
        """Test parameter schema has empty properties."""
        tool = MemoryListTool(service=memory_service)
        schema = tool.get_parameters_schema()
        assert schema["properties"] == {}


class TestMemoryDumpTool:
    """Tests for MemoryDumpTool."""

    def test_dump_keys(self, populated_memory_service):
        """Test dumping specific keys."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            tool = MemoryDumpTool(service=populated_memory_service, output_dir=output_dir)
            result = tool.execute(
                keys=["user.name", "user.email"],
                filename="users.jsonl",
            )
            assert result["success"] is True
            assert result["count"] == 2
            assert (output_dir / "users.jsonl").exists()

    def test_dump_creates_parent_dirs(self, populated_memory_service):
        """Test dump creates parent directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            tool = MemoryDumpTool(service=populated_memory_service, output_dir=output_dir)
            result = tool.execute(
                keys=["user.name"],
                filename="subdir/output.jsonl",
            )
            assert result["success"] is True
            assert (output_dir / "subdir" / "output.jsonl").exists()

    def test_get_parameters_schema(self, memory_service):
        """Test parameter schema."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tool = MemoryDumpTool(service=memory_service, output_dir=Path(tmpdir))
            schema = tool.get_parameters_schema()
            assert "keys" in schema["properties"]
            assert "filename" in schema["properties"]
            assert schema["properties"]["keys"]["type"] == "array"
