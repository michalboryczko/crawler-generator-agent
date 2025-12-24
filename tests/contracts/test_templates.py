"""Tests for Jinja2 contract template rendering."""

import pytest

from src.prompts.template_renderer import get_template_env, render_template


class TestTemplateEnvironment:
    """Tests for template environment setup."""

    def test_get_template_env_returns_environment(self):
        """get_template_env returns Jinja2 Environment."""
        env = get_template_env()
        assert env is not None
        assert hasattr(env, "get_template")

    def test_tojson_filter_available(self):
        """Custom tojson filter is registered."""
        env = get_template_env()
        assert "tojson" in env.filters


class TestTojsonFilter:
    """Tests for custom tojson filter."""

    def test_tojson_formats_dict(self):
        """tojson filter formats dictionary."""
        env = get_template_env()
        template = env.from_string("{{ data | tojson }}")
        result = template.render(data={"key": "value"})
        assert '"key"' in result
        assert '"value"' in result

    def test_tojson_formats_list(self):
        """tojson filter formats list."""
        env = get_template_env()
        template = env.from_string("{{ items | tojson }}")
        result = template.render(items=["a", "b", "c"])
        assert '"a"' in result
        assert '"b"' in result

    def test_tojson_indents_properly(self):
        """tojson filter indents JSON."""
        env = get_template_env()
        template = env.from_string("{{ data | tojson }}")
        result = template.render(data={"nested": {"key": "value"}})
        # Should have indentation (newlines for nested structure)
        assert "\n" in result


class TestRenderSubAgentItem:
    """Tests for sub_agent_item.md.j2 template."""

    def test_render_sub_agent_item_basic(self):
        """Render basic agent item."""
        result = render_template(
            "sub_agent_item.md.j2",
            agent_name="discovery_agent",
            tool_name="run_discovery_agent",
            description="Find article URLs on a page",
            fields_markdown="**article_urls** (required): List of URLs",
            example_json={"article_urls": ["https://example.com/a1"]},
        )

        assert "discovery_agent" in result
        assert "run_discovery_agent" in result
        assert "Find article URLs" in result
        assert "Output Contract" in result
        assert "article_urls" in result

    def test_render_sub_agent_item_has_example(self):
        """Rendered item includes example JSON."""
        result = render_template(
            "sub_agent_item.md.j2",
            agent_name="test_agent",
            tool_name="run_test",
            description="Test",
            fields_markdown="fields",
            example_json={"test": "value"},
        )

        assert "Example Output" in result
        assert "```json" in result

    def test_render_sub_agent_item_no_example(self):
        """Rendered item handles missing example."""
        result = render_template(
            "sub_agent_item.md.j2",
            agent_name="test_agent",
            tool_name="run_test",
            description="Test",
            fields_markdown="fields",
            example_json=None,
        )

        assert "test_agent" in result
        # Should not have example section when example_json is None
        assert "Example Output" not in result


class MockAgentTool:
    """Mock AgentTool for template testing."""

    def __init__(self, agent_name: str, description: str, tool_name: str):
        self._agent_name = agent_name
        self._description = description
        self._tool_name = tool_name

    def get_agent_name(self) -> str:
        return self._agent_name

    def get_agent_description(self) -> str:
        return f"{self._agent_name} - {self._description}"

    def get_tool_name(self) -> str:
        return self._tool_name


class TestRenderSubAgentsSection:
    """Tests for sub_agents_section.md.j2 template."""

    def test_render_sub_agents_section(self):
        """Render section with multiple agents."""
        agent_tools = [
            MockAgentTool("discovery_agent", "Find articles", "run_discovery_agent"),
            MockAgentTool("selector_agent", "Build selectors", "run_selector_agent"),
        ]

        result = render_template("sub_agents_section.md.j2", agent_tools=agent_tools)

        assert "Available agents" in result
        assert "discovery_agent" in result
        assert "selector_agent" in result
        assert "Agent usage rules" in result

    def test_render_sub_agents_section_empty(self):
        """Handle empty agents list."""
        result = render_template("sub_agents_section.md.j2", agent_tools=[])

        assert "Available agents" in result


class TestRenderResponseRules:
    """Tests for response_rules.md.j2 template."""

    def test_render_response_rules_basic(self):
        """Render response rules with run identifier."""
        schema = {
            "type": "object",
            "properties": {
                "article_urls": {"type": "array", "items": {"type": "string"}},
                "pagination_type": {"type": "string"},
            },
            "required": ["article_urls"],
        }
        expected_outputs = ["article_urls"]
        result = render_template(
            "response_rules.md.j2",
            run_identifier="uuid-123-456",
            required_fields=["article_urls", "pagination_type"],
            expected_outputs=expected_outputs,
            output_contract_schema=schema,
            example_json={field: "<value>" for field in expected_outputs},
        )

        assert "uuid-123-456" in result
        assert "article_urls" in result
        assert "pagination_type" in result
        assert "validate_response" in result
        # Should include schema in output
        assert '"type": "object"' in result

    def test_render_response_rules_includes_instructions(self):
        """Rules include validation instructions."""
        schema = {"type": "object", "properties": {"name": {"type": "string"}}}
        expected_outputs = ["name"]
        result = render_template(
            "response_rules.md.j2",
            run_identifier="test-uuid",
            required_fields=["name"],
            expected_outputs=expected_outputs,
            output_contract_schema=schema,
            example_json={field: "<value>" for field in expected_outputs},
        )

        assert "MUST" in result
        assert "JSON" in result
        assert "CRITICAL" in result  # Uses CRITICAL instead of REQUIRED
        assert "automatic" in result  # Mentions automatic validation

    def test_render_response_rules_with_expected_outputs(self):
        """Expected outputs section rendered."""
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "value": {"type": "string"},
                "metadata": {"type": "object"},
            },
        }
        expected_outputs = ["name", "value", "metadata"]
        result = render_template(
            "response_rules.md.j2",
            run_identifier="test-uuid",
            required_fields=["name"],
            expected_outputs=expected_outputs,
            output_contract_schema=schema,
            example_json={field: "<value>" for field in expected_outputs},
        )

        assert "Required Fields" in result
        assert "name" in result
        assert "value" in result
        assert "metadata" in result

    def test_render_response_rules_with_empty_schema(self):
        """Empty schema renders as empty object."""
        expected_outputs = ["name"]
        result = render_template(
            "response_rules.md.j2",
            run_identifier="test-uuid",
            required_fields=["name"],
            expected_outputs=expected_outputs,
            output_contract_schema={},
            example_json={field: "<value>" for field in expected_outputs},
        )

        assert "test-uuid" in result
        assert "{}" in result  # Empty schema renders as {}


class TestRenderContractSummary:
    """Tests for contract_summary.md.j2 template."""

    def test_render_contract_summary(self):
        """Render contract summary from schema."""
        schema = {
            "$id": "discovery/output.schema.json",
            "description": "Discovery agent output schema",
            "type": "object",
            "properties": {
                "article_urls": {"type": "array", "description": "List of discovered URLs"},
                "pagination_type": {"type": "string", "description": "Type of pagination"},
            },
            "required": ["article_urls", "pagination_type"],
        }

        result = render_template(
            "contract_summary.md.j2",
            agent_name="discovery_agent",
            schema_path="discovery/output.schema.json",
            schema=schema,
        )

        assert "discovery_agent" in result
        assert "discovery/output.schema.json" in result
        assert "Discovery agent output schema" in result
        assert "article_urls" in result
        assert "pagination_type" in result

    def test_render_contract_summary_missing_description(self):
        """Handle schema without description."""
        schema = {"type": "object", "properties": {}, "required": []}

        result = render_template(
            "contract_summary.md.j2",
            agent_name="test_agent",
            schema_path="test.schema.json",
            schema=schema,
        )

        assert "test_agent" in result
        assert "No description" in result


class TestPlanGeneratorUserTemplate:
    """Tests for plan_generator_user.md.j2 template with nested markdown rendering."""

    def test_renders_simple_values_inline(self):
        """Simple string/number values render inline with key."""
        from src.prompts.template_renderer import render_agent_template

        collected_information = [
            {
                "agent_name": "discovery_agent",
                "description": "Found articles",
                "output": {
                    "pagination_type": "numbered",
                    "max_pages": 10,
                    "success": True,
                },
            }
        ]

        result = render_agent_template(
            "plan_generator_user.md.j2",
            task="Test",
            target_url="https://example.com",
            collected_information=collected_information,
        )

        # Simple values should be inline
        assert "- **pagination_type**: numbered" in result
        assert "- **max_pages**: 10" in result
        assert "- **success**: true" in result
        # Should NOT contain json blocks for simple values
        assert "```json\nnumbered" not in result

    def test_renders_arrays_as_nested_lists(self):
        """Arrays render as nested markdown lists, not JSON."""
        from src.prompts.template_renderer import render_agent_template

        collected_information = [
            {
                "agent_name": "discovery_agent",
                "description": "Found articles",
                "output": {
                    "article_urls": [
                        "https://example.com/article1",
                        "https://example.com/article2",
                    ],
                },
            }
        ]

        result = render_agent_template(
            "plan_generator_user.md.j2",
            task="Test",
            target_url="https://example.com",
            collected_information=collected_information,
        )

        # Should render as nested list
        assert "- **article_urls**:" in result
        assert "- https://example.com/article1" in result
        assert "- https://example.com/article2" in result
        # Should NOT be JSON
        assert '["https://example.com/article1"' not in result

    def test_renders_nested_objects_as_nested_lists(self):
        """Nested objects render as nested markdown lists."""
        from src.prompts.template_renderer import render_agent_template

        collected_information = [
            {
                "agent_name": "selector_agent",
                "description": "Built selectors",
                "output": {
                    "listing_selectors": {
                        "title": ".article-title",
                        "link": "a.read-more",
                    },
                },
            }
        ]

        result = render_agent_template(
            "plan_generator_user.md.j2",
            task="Test",
            target_url="https://example.com",
            collected_information=collected_information,
        )

        # Should render nested object as nested list
        assert "- **listing_selectors**:" in result
        assert "- **title**: .article-title" in result
        assert "- **link**: a.read-more" in result

    def test_renders_deeply_nested_structures(self):
        """Deeply nested structures render correctly."""
        from src.prompts.template_renderer import render_agent_template

        collected_information = [
            {
                "agent_name": "selector_agent",
                "description": "Complex output",
                "output": {
                    "data": {
                        "selectors": {
                            "listing": {
                                "title": ".title",
                                "urls": ["url1", "url2"],
                            }
                        }
                    }
                },
            }
        ]

        result = render_agent_template(
            "plan_generator_user.md.j2",
            task="Test",
            target_url="https://example.com",
            collected_information=collected_information,
        )

        # Check nested structure is rendered
        assert "- **data**:" in result
        assert "- **selectors**:" in result
        assert "- **listing**:" in result
        assert "- **title**: .title" in result
        assert "- url1" in result
        assert "- url2" in result

    def test_handles_null_values(self):
        """Null values render as 'null'."""
        from src.prompts.template_renderer import render_agent_template

        collected_information = [
            {
                "agent_name": "discovery_agent",
                "description": "Test",
                "output": {
                    "next_page_selector": None,
                },
            }
        ]

        result = render_agent_template(
            "plan_generator_user.md.j2",
            task="Test",
            target_url="https://example.com",
            collected_information=collected_information,
        )

        assert "- **next_page_selector**: null" in result

    def test_includes_task_section(self):
        """Template includes Your Task section with instructions."""
        from src.prompts.template_renderer import render_agent_template

        result = render_agent_template(
            "plan_generator_user.md.j2",
            task="Generate Plan",
            target_url="https://example.com",
            collected_information=[],
        )

        assert "## Your Task" in result
        assert "plan_draft_provider" in result
        assert "prepare_crawler_configuration" in result

    def test_no_json_blocks_for_nested_data(self):
        """Verify no ```json blocks appear for nested data structures."""
        from src.prompts.template_renderer import render_agent_template

        collected_information = [
            {
                "agent_name": "discovery_agent",
                "description": "Found data",
                "output": {
                    "success": True,
                    "data": {
                        "pagination_type": "numbered",
                        "max_pages": 589,
                        "article_urls": ["url1", "url2", "url3"],
                        "nested": {"key": "value"},
                    },
                },
            }
        ]

        result = render_agent_template(
            "plan_generator_user.md.j2",
            task="Test",
            target_url="https://example.com",
            collected_information=collected_information,
        )

        # Count occurrences of ```json - should be 0 in output section
        # (might be in Your Task section example, but not in rendered data)
        output_section = result.split("## From discovery_agent")[1].split("## Your Task")[0]
        assert "```json" not in output_section


class TestTemplateErrors:
    """Tests for template error handling."""

    def test_template_not_found(self):
        """FileNotFoundError for unknown template."""
        from jinja2 import TemplateNotFound

        with pytest.raises(TemplateNotFound):
            render_template("nonexistent_template.j2")
