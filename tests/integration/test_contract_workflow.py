"""Integration tests for contract validation workflow.

Tests verify the full validation workflow:
- generate UUID → prepare validation → child validates → returns
"""

import json
import time

import pytest

from src.contracts.validation_registry import ValidationRegistry
from src.prompts.template_renderer import render_template
from src.tools.agent_tools import (
    GenerateUuidTool,
    PrepareAgentOutputValidationTool,
    ValidateResponseTool,
)


class TestFullValidationWorkflow:
    """Test complete validation workflow."""

    @pytest.fixture(autouse=True)
    def reset_registry(self):
        """Reset singleton registry before each test."""
        ValidationRegistry.reset_instance()
        yield
        ValidationRegistry.reset_instance()

    @pytest.fixture
    def schema_paths(self, tmp_path):
        """Create test schema files."""
        schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "required": ["article_urls", "pagination"],
            "properties": {
                "article_urls": {"type": "array", "items": {"type": "string"}},
                "pagination": {"type": "object"},
                "agent_response_content": {"type": "string"},
            },
        }
        schema_file = tmp_path / "test_agent" / "output.schema.json"
        schema_file.parent.mkdir(parents=True)
        schema_file.write_text(json.dumps(schema))
        return {"test_agent": str(schema_file)}

    def test_workflow_generate_prepare_validate(self, schema_paths):
        """Test: generate UUID → prepare validation → validate response."""
        # Step 1: Generate UUID
        uuid_tool = GenerateUuidTool()
        uuid_result = uuid_tool.execute()
        assert uuid_result["success"]
        run_identifier = uuid_result["run_identifier"]

        # Step 2: Prepare validation
        prepare_tool = PrepareAgentOutputValidationTool(schema_paths)
        prepare_result = prepare_tool.execute(
            run_identifier=run_identifier, agent_name="test_agent"
        )
        assert prepare_result["success"]
        assert run_identifier in prepare_result["message"]

        # Step 3: Child agent validates response
        validate_tool = ValidateResponseTool()
        valid_response = {
            "article_urls": ["http://example.com/1", "http://example.com/2"],
            "pagination": {"type": "numbered"},
            "agent_response_content": "Found 2 articles with numbered pagination",
        }
        validate_result = validate_tool.execute(
            run_identifier=run_identifier, response_json=valid_response
        )
        assert validate_result["success"]
        assert validate_result["valid"]

    def test_workflow_invalid_response_caught(self, schema_paths):
        """Test: validation catches schema violations."""
        uuid_tool = GenerateUuidTool()
        run_identifier = uuid_tool.execute()["run_identifier"]

        prepare_tool = PrepareAgentOutputValidationTool(schema_paths)
        prepare_tool.execute(run_identifier=run_identifier, agent_name="test_agent")

        validate_tool = ValidateResponseTool()
        invalid_response = {
            # Missing required 'pagination' field
            "article_urls": ["http://example.com/1"]
        }
        result = validate_tool.execute(
            run_identifier=run_identifier, response_json=invalid_response
        )
        assert result["success"]  # Tool executed successfully
        assert not result["valid"]  # But validation failed
        assert len(result["validation_errors"]) > 0

    def test_workflow_wrong_type_caught(self, schema_paths):
        """Test: validation catches wrong types."""
        uuid_tool = GenerateUuidTool()
        run_identifier = uuid_tool.execute()["run_identifier"]

        prepare_tool = PrepareAgentOutputValidationTool(schema_paths)
        prepare_tool.execute(run_identifier=run_identifier, agent_name="test_agent")

        validate_tool = ValidateResponseTool()
        invalid_response = {
            "article_urls": "not-an-array",  # Should be array
            "pagination": {"type": "numbered"},
        }
        result = validate_tool.execute(
            run_identifier=run_identifier, response_json=invalid_response
        )
        assert result["success"]
        assert not result["valid"]
        assert any("array" in e["message"] for e in result["validation_errors"])

    def test_workflow_expired_context(self, schema_paths):
        """Test: expired contexts are rejected."""
        # Create registry with very short TTL
        ValidationRegistry.reset_instance()
        registry = ValidationRegistry(ttl=0.001)  # 1ms TTL

        uuid_tool = GenerateUuidTool()
        run_identifier = uuid_tool.execute()["run_identifier"]

        prepare_tool = PrepareAgentOutputValidationTool(schema_paths, registry=registry)
        prepare_tool.execute(run_identifier=run_identifier, agent_name="test_agent")

        time.sleep(0.01)  # Wait for expiration

        validate_tool = ValidateResponseTool(registry=registry)
        result = validate_tool.execute(
            run_identifier=run_identifier, response_json={"article_urls": [], "pagination": {}}
        )
        assert not result["success"]
        assert "No validation context" in result["error"]

    def test_workflow_unknown_run_identifier(self):
        """Test: unknown run_identifier is rejected."""
        validate_tool = ValidateResponseTool()
        result = validate_tool.execute(
            run_identifier="unknown-uuid-that-does-not-exist",
            response_json={"some": "data"},
        )
        assert not result["success"]
        assert "No validation context" in result["error"]

    def test_workflow_unknown_agent_name(self, schema_paths):
        """Test: unknown agent name is rejected during preparation."""
        uuid_tool = GenerateUuidTool()
        run_identifier = uuid_tool.execute()["run_identifier"]

        prepare_tool = PrepareAgentOutputValidationTool(schema_paths)
        result = prepare_tool.execute(run_identifier=run_identifier, agent_name="unknown_agent")
        assert not result["success"]
        assert "Unknown agent" in result["error"]


class TestConcurrentValidation:
    """Test thread-safety with concurrent access."""

    @pytest.fixture(autouse=True)
    def reset_registry(self):
        """Reset singleton registry before each test."""
        ValidationRegistry.reset_instance()
        yield
        ValidationRegistry.reset_instance()

    @pytest.fixture
    def schema_paths(self, tmp_path):
        """Create test schema files."""
        schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "required": ["value"],
            "properties": {"value": {"type": "integer"}},
        }
        schema_file = tmp_path / "test_agent" / "output.schema.json"
        schema_file.parent.mkdir(parents=True)
        schema_file.write_text(json.dumps(schema))
        return {"test_agent": str(schema_file)}

    def test_concurrent_registrations(self, schema_paths):
        """Test multiple concurrent registrations don't interfere."""
        import threading

        uuid_tool = GenerateUuidTool()
        prepare_tool = PrepareAgentOutputValidationTool(schema_paths)
        validate_tool = ValidateResponseTool()

        results = {}
        errors = []

        def register_and_validate(thread_id: int):
            try:
                # Each thread generates its own UUID
                run_identifier = uuid_tool.execute()["run_identifier"]
                results[f"uuid_{thread_id}"] = run_identifier

                # Prepare validation
                prepare_tool.execute(run_identifier=run_identifier, agent_name="test_agent")

                # Validate with unique value
                response = {"value": thread_id}
                result = validate_tool.execute(
                    run_identifier=run_identifier, response_json=response
                )
                results[f"valid_{thread_id}"] = result["valid"]
            except Exception as e:
                errors.append((thread_id, str(e)))

        # Run 10 concurrent threads
        threads = [threading.Thread(target=register_and_validate, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All should succeed
        assert len(errors) == 0, f"Errors: {errors}"
        for i in range(10):
            assert results.get(f"valid_{i}"), f"Thread {i} validation failed"


class TestTemplateIntegration:
    """Test template rendering with real schemas."""

    def test_render_response_rules_with_schema(self):
        """Test rendering response rules template."""
        schema = {
            "type": "object",
            "properties": {
                "article_urls": {"type": "array", "items": {"type": "string"}},
                "pagination": {"type": "string"},
            },
            "required": ["article_urls"],
        }
        rendered = render_template(
            "response_rules.md.j2",
            run_identifier="test-uuid-123",
            expected_outputs=["article_urls", "pagination"],
            required_fields=["article_urls", "pagination"],
            output_contract_schema=schema,
        )

        assert "test-uuid-123" in rendered
        assert "article_urls" in rendered
        assert "validate_response" in rendered
        # Schema should be included in the rendered output
        assert '"type": "object"' in rendered

    def test_render_sub_agent_item_template(self):
        """Test rendering sub-agent item template."""
        rendered = render_template(
            "sub_agent_item.md.j2",
            agent_name="discovery_agent",
            tool_name="run_discovery_agent",
            description="Discover site structure",
            fields_markdown="- article_urls (required): List of URLs",
            example_json='{"article_urls": []}',
        )

        assert "discovery_agent" in rendered
        assert "run_discovery_agent" in rendered
        assert "article_urls" in rendered

    def test_render_contract_summary_template(self):
        """Test rendering contract summary template."""
        schema = {
            "description": "Test agent output",
            "properties": {
                "field1": {"description": "First field"},
                "field2": {"description": "Second field"},
            },
            "required": ["field1"],
        }

        rendered = render_template(
            "contract_summary.md.j2",
            agent_name="test_agent",
            schema_path="test/output.schema.json",
            schema=schema,
        )

        assert "test_agent" in rendered
        assert "field1" in rendered
        assert "(required)" in rendered
        assert "field2" in rendered


class TestSchemaValidationDetails:
    """Test detailed schema validation scenarios."""

    @pytest.fixture(autouse=True)
    def reset_registry(self):
        """Reset singleton registry before each test."""
        ValidationRegistry.reset_instance()
        yield
        ValidationRegistry.reset_instance()

    def test_nested_object_validation(self, tmp_path):
        """Test validation of nested objects."""
        schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "required": ["nested"],
            "properties": {
                "nested": {
                    "type": "object",
                    "required": ["inner_field"],
                    "properties": {
                        "inner_field": {"type": "string"},
                    },
                }
            },
        }
        schema_file = tmp_path / "nested" / "output.schema.json"
        schema_file.parent.mkdir(parents=True)
        schema_file.write_text(json.dumps(schema))
        schema_paths = {"nested_agent": str(schema_file)}

        uuid_tool = GenerateUuidTool()
        run_identifier = uuid_tool.execute()["run_identifier"]

        prepare_tool = PrepareAgentOutputValidationTool(schema_paths)
        prepare_tool.execute(run_identifier=run_identifier, agent_name="nested_agent")

        validate_tool = ValidateResponseTool()

        # Valid nested structure
        valid_response = {"nested": {"inner_field": "test value"}}
        result = validate_tool.execute(run_identifier=run_identifier, response_json=valid_response)
        assert result["valid"]

    def test_array_items_validation(self, tmp_path):
        """Test validation of array items."""
        schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "required": ["urls"],
            "properties": {
                "urls": {
                    "type": "array",
                    "items": {"type": "string", "format": "uri"},
                    "minItems": 1,
                }
            },
        }
        schema_file = tmp_path / "array" / "output.schema.json"
        schema_file.parent.mkdir(parents=True)
        schema_file.write_text(json.dumps(schema))
        schema_paths = {"array_agent": str(schema_file)}

        uuid_tool = GenerateUuidTool()
        run_identifier = uuid_tool.execute()["run_identifier"]

        prepare_tool = PrepareAgentOutputValidationTool(schema_paths)
        prepare_tool.execute(run_identifier=run_identifier, agent_name="array_agent")

        validate_tool = ValidateResponseTool()

        # Empty array should fail minItems
        invalid_response = {"urls": []}
        result = validate_tool.execute(
            run_identifier=run_identifier, response_json=invalid_response
        )
        assert not result["valid"]
        assert any(
            "minItems" in e["message"] or "[]" in e["message"] for e in result["validation_errors"]
        )
