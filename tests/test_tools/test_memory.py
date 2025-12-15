"""Tests for memory tools."""

import tempfile
from pathlib import Path

from src.tools.memory import (
    MemoryDumpTool,
    MemoryListTool,
    MemoryReadTool,
    MemorySearchTool,
    MemoryWriteTool,
)


class TestMemoryStore:
    """Tests for MemoryStore class."""

    def test_write_and_read(self, memory_store):
        """Test basic write and read."""
        memory_store.write("key1", "value1")
        assert memory_store.read("key1") == "value1"

    def test_read_nonexistent(self, memory_store):
        """Test reading nonexistent key returns None."""
        assert memory_store.read("nonexistent") is None

    def test_overwrite(self, memory_store):
        """Test overwriting existing key."""
        memory_store.write("key", "value1")
        memory_store.write("key", "value2")
        assert memory_store.read("key") == "value2"

    def test_delete_existing(self, memory_store):
        """Test deleting existing key."""
        memory_store.write("key", "value")
        assert memory_store.delete("key") is True
        assert memory_store.read("key") is None

    def test_delete_nonexistent(self, memory_store):
        """Test deleting nonexistent key returns False."""
        assert memory_store.delete("nonexistent") is False

    def test_search_pattern(self, populated_memory_store):
        """Test searching with glob pattern."""
        keys = populated_memory_store.search("user.*")
        assert sorted(keys) == ["user.email", "user.name"]

    def test_search_wildcard(self, populated_memory_store):
        """Test searching with wildcard."""
        keys = populated_memory_store.search("articles.*")
        assert len(keys) == 2
        assert "articles.item1" in keys
        assert "articles.item2" in keys

    def test_search_no_match(self, populated_memory_store):
        """Test searching with no matches."""
        keys = populated_memory_store.search("nonexistent.*")
        assert keys == []

    def test_list_keys(self, populated_memory_store):
        """Test listing all keys."""
        keys = populated_memory_store.list_keys()
        assert len(keys) == 5
        assert "user.name" in keys
        assert "articles.item1" in keys

    def test_list_keys_empty(self, memory_store):
        """Test listing keys on empty store."""
        assert memory_store.list_keys() == []

    def test_clear(self, populated_memory_store):
        """Test clearing all data."""
        populated_memory_store.clear()
        assert populated_memory_store.list_keys() == []

    def test_dump_to_jsonl(self, populated_memory_store):
        """Test dumping to JSONL file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "output.jsonl"
            count = populated_memory_store.dump_to_jsonl(
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

    def test_dump_to_jsonl_missing_keys(self, populated_memory_store):
        """Test dumping with some missing keys."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "output.jsonl"
            count = populated_memory_store.dump_to_jsonl(
                ["user.name", "nonexistent"],
                output_path,
            )
            assert count == 1  # Only one key exists


class TestMemoryReadTool:
    """Tests for MemoryReadTool."""

    def test_read_existing(self, populated_memory_store):
        """Test reading existing key."""
        tool = MemoryReadTool(store=populated_memory_store)
        result = tool.execute(key="user.name")
        assert result["success"] is True
        assert result["result"] == "Test User"
        assert result["found"] is True

    def test_read_nonexistent(self, memory_store):
        """Test reading nonexistent key."""
        tool = MemoryReadTool(store=memory_store)
        result = tool.execute(key="nonexistent")
        assert result["success"] is True
        assert result["result"] is None
        assert result["found"] is False

    def test_get_parameters_schema(self, memory_store):
        """Test parameter schema."""
        tool = MemoryReadTool(store=memory_store)
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

    def test_write_new_key(self, memory_store):
        """Test writing to new key."""
        tool = MemoryWriteTool(store=memory_store)
        result = tool.execute(key="new_key", value="new_value")
        assert result["success"] is True
        assert result["overwritten"] is False
        assert memory_store.read("new_key") == "new_value"

    def test_write_overwrite(self, populated_memory_store):
        """Test overwriting existing key."""
        tool = MemoryWriteTool(store=populated_memory_store)
        result = tool.execute(key="user.name", value="New Name")
        assert result["success"] is True
        assert result["overwritten"] is True
        assert populated_memory_store.read("user.name") == "New Name"

    def test_write_complex_value(self, memory_store):
        """Test writing complex value."""
        tool = MemoryWriteTool(store=memory_store)
        complex_value = {"nested": {"data": [1, 2, 3]}}
        result = tool.execute(key="complex", value=complex_value)
        assert result["success"] is True
        assert result["value_size"] > 0
        assert memory_store.read("complex") == complex_value

    def test_get_parameters_schema(self, memory_store):
        """Test parameter schema."""
        tool = MemoryWriteTool(store=memory_store)
        schema = tool.get_parameters_schema()
        assert "key" in schema["properties"]
        assert "value" in schema["properties"]
        assert "key" in schema["required"]
        assert "value" in schema["required"]


class TestMemorySearchTool:
    """Tests for MemorySearchTool."""

    def test_search_pattern(self, populated_memory_store):
        """Test searching with pattern."""
        tool = MemorySearchTool(store=populated_memory_store)
        result = tool.execute(pattern="articles.*")
        assert result["success"] is True
        assert result["count"] == 2
        assert "articles.item1" in result["result"]

    def test_search_no_match(self, populated_memory_store):
        """Test searching with no matches."""
        tool = MemorySearchTool(store=populated_memory_store)
        result = tool.execute(pattern="nonexistent.*")
        assert result["success"] is True
        assert result["count"] == 0
        assert result["result"] == []

    def test_get_parameters_schema(self, memory_store):
        """Test parameter schema."""
        tool = MemorySearchTool(store=memory_store)
        schema = tool.get_parameters_schema()
        assert "pattern" in schema["properties"]
        assert "pattern" in schema["required"]


class TestMemoryListTool:
    """Tests for MemoryListTool."""

    def test_list_populated(self, populated_memory_store):
        """Test listing populated store."""
        tool = MemoryListTool(store=populated_memory_store)
        result = tool.execute()
        assert result["success"] is True
        assert result["count"] == 5
        assert len(result["result"]) == 5

    def test_list_empty(self, memory_store):
        """Test listing empty store."""
        tool = MemoryListTool(store=memory_store)
        result = tool.execute()
        assert result["success"] is True
        assert result["count"] == 0
        assert result["result"] == []

    def test_get_parameters_schema(self, memory_store):
        """Test parameter schema has empty properties."""
        tool = MemoryListTool(store=memory_store)
        schema = tool.get_parameters_schema()
        assert schema["properties"] == {}


class TestMemoryDumpTool:
    """Tests for MemoryDumpTool."""

    def test_dump_keys(self, populated_memory_store):
        """Test dumping specific keys."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            tool = MemoryDumpTool(store=populated_memory_store, output_dir=output_dir)
            result = tool.execute(
                keys=["user.name", "user.email"],
                filename="users.jsonl",
            )
            assert result["success"] is True
            assert result["count"] == 2
            assert (output_dir / "users.jsonl").exists()

    def test_dump_creates_parent_dirs(self, populated_memory_store):
        """Test dump creates parent directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            tool = MemoryDumpTool(store=populated_memory_store, output_dir=output_dir)
            result = tool.execute(
                keys=["user.name"],
                filename="subdir/output.jsonl",
            )
            assert result["success"] is True
            assert (output_dir / "subdir" / "output.jsonl").exists()

    def test_get_parameters_schema(self, memory_store):
        """Test parameter schema."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tool = MemoryDumpTool(store=memory_store, output_dir=Path(tmpdir))
            schema = tool.get_parameters_schema()
            assert "keys" in schema["properties"]
            assert "filename" in schema["properties"]
            assert schema["properties"]["keys"]["type"] == "array"
