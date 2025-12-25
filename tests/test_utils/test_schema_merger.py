"""Tests for schema merger utility."""

from src.utils.schema_merger import merge_agent_tool_schema, merge_schemas


class TestMergeSchemas:
    """Tests for basic schema merging."""

    def test_merge_empty_list(self):
        """Empty list returns minimal schema."""
        result = merge_schemas()
        assert result == {"type": "object", "properties": {}}

    def test_merge_none_values_skipped(self):
        """None values are filtered out."""
        schema = {"type": "object", "properties": {"a": {"type": "string"}}}
        result = merge_schemas(None, schema, None)
        assert result["properties"]["a"]["type"] == "string"

    def test_merge_single_schema(self):
        """Single schema is returned as copy."""
        schema = {"type": "object", "properties": {"x": {"type": "integer"}}}
        result = merge_schemas(schema)
        assert result["properties"]["x"]["type"] == "integer"
        # Verify it's a copy, not the same object
        result["properties"]["x"]["type"] = "string"
        assert schema["properties"]["x"]["type"] == "integer"

    def test_merge_properties(self):
        """Properties from multiple schemas are merged."""
        schema1 = {"type": "object", "properties": {"a": {"type": "string"}}}
        schema2 = {"type": "object", "properties": {"b": {"type": "integer"}}}
        result = merge_schemas(schema1, schema2)
        assert "a" in result["properties"]
        assert "b" in result["properties"]

    def test_later_schema_overrides_property(self):
        """Later schema property overrides earlier one."""
        schema1 = {"type": "object", "properties": {"x": {"type": "string"}}}
        schema2 = {"type": "object", "properties": {"x": {"type": "integer"}}}
        result = merge_schemas(schema1, schema2)
        assert result["properties"]["x"]["type"] == "integer"

    def test_merge_required_arrays(self):
        """Required arrays are unioned."""
        schema1 = {"type": "object", "required": ["a", "b"], "properties": {}}
        schema2 = {"type": "object", "required": ["b", "c"], "properties": {}}
        result = merge_schemas(schema1, schema2)
        assert set(result["required"]) == {"a", "b", "c"}

    def test_merge_defs(self):
        """$defs are merged from all schemas."""
        schema1 = {"type": "object", "properties": {}, "$defs": {"Def1": {"type": "string"}}}
        schema2 = {"type": "object", "properties": {}, "$defs": {"Def2": {"type": "integer"}}}
        result = merge_schemas(schema1, schema2)
        assert "Def1" in result["$defs"]
        assert "Def2" in result["$defs"]

    def test_metadata_from_later_schema(self):
        """Title, description come from later schema."""
        schema1 = {"type": "object", "title": "First", "properties": {}}
        schema2 = {"type": "object", "title": "Second", "properties": {}}
        result = merge_schemas(schema1, schema2)
        assert result["title"] == "Second"


class TestMergeAgentToolSchema:
    """Tests for agent tool schema merging."""

    def test_merge_with_none_input_schema(self):
        """When input schema is None, returns copy of base."""
        base = {
            "type": "object",
            "properties": {"task": {"type": "string"}},
            "required": ["task"],
        }
        result = merge_agent_tool_schema(base, None)
        assert result["properties"]["task"]["type"] == "string"
        assert "task" in result["required"]

    def test_merges_agent_input_at_top_level(self):
        """Agent input properties appear at top level."""
        base = {
            "type": "object",
            "properties": {"task": {"type": "string"}},
            "required": ["task"],
        }
        agent_input = {
            "type": "object",
            "properties": {"target_url": {"type": "string", "format": "uri"}},
            "required": ["target_url"],
        }
        result = merge_agent_tool_schema(base, agent_input)
        assert "target_url" in result["properties"]
        assert result["properties"]["target_url"]["format"] == "uri"

    def test_merges_required_fields(self):
        """Required from both schemas are merged."""
        base = {
            "type": "object",
            "properties": {"task": {"type": "string"}},
            "required": ["task"],
        }
        agent_input = {
            "type": "object",
            "properties": {"target_url": {"type": "string"}},
            "required": ["target_url"],
        }
        result = merge_agent_tool_schema(base, agent_input)
        assert "task" in result["required"]
        assert "target_url" in result["required"]

    def test_task_always_required(self):
        """Task is always in required even if base doesn't have it."""
        base = {"type": "object", "properties": {"task": {"type": "string"}}}
        agent_input = {
            "type": "object",
            "properties": {"x": {"type": "string"}},
            "required": ["x"],
        }
        result = merge_agent_tool_schema(base, agent_input)
        assert "task" in result["required"]

    def test_preserves_defs_from_agent_input(self):
        """$defs from agent input schema are preserved."""
        base = {
            "type": "object",
            "properties": {"task": {"type": "string"}},
            "required": ["task"],
        }
        agent_input = {
            "type": "object",
            "properties": {"items": {"type": "array", "items": {"$ref": "#/$defs/Item"}}},
            "$defs": {"Item": {"type": "object", "properties": {"name": {"type": "string"}}}},
        }
        result = merge_agent_tool_schema(base, agent_input)
        assert "$defs" in result
        assert "Item" in result["$defs"]

    def test_full_discovery_agent_merge(self):
        """Integration test with realistic discovery agent schema."""
        base = {
            "type": "object",
            "properties": {
                "task": {"type": "string", "description": "Task description"},
                "run_identifier": {"type": "string"},
                "expected_outputs": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["task"],
        }
        discovery_input = {
            "type": "object",
            "required": ["target_url"],
            "properties": {
                "target_url": {
                    "type": "string",
                    "format": "uri",
                    "description": "The base URL of the site to analyze",
                }
            },
        }
        result = merge_agent_tool_schema(base, discovery_input)

        # All properties at top level
        assert "task" in result["properties"]
        assert "target_url" in result["properties"]
        assert "run_identifier" in result["properties"]

        # Required merged correctly
        assert set(result["required"]) == {"task", "target_url"}

        # Descriptions preserved
        assert "uri" in result["properties"]["target_url"].get("format", "")
