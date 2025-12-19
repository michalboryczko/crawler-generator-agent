"""Tests for prompt provider system."""

import pytest

from src.prompts import PromptInfo, PromptProvider, PromptRegistry, get_prompt_provider
from src.prompts.provider import reset_prompt_provider
from src.prompts.template import PromptTemplate


class TestPromptRegistry:
    """Tests for PromptRegistry."""

    @pytest.fixture(autouse=True)
    def reset_registry(self):
        """Reset singleton between tests."""
        PromptRegistry.reset_instance()
        yield
        PromptRegistry.reset_instance()

    def test_register_and_get(self):
        """Register a prompt and retrieve it."""
        registry = PromptRegistry()
        registry.register_prompt("test", "Test content", version="1.0.0")
        assert registry.get_prompt("test") == "Test content"

    def test_get_unknown_raises(self):
        """Getting unknown prompt raises KeyError."""
        registry = PromptRegistry()
        with pytest.raises(KeyError, match="Unknown prompt"):
            registry.get_prompt("unknown")

    def test_register_with_category(self):
        """Register prompt with category."""
        registry = PromptRegistry()
        registry.register_prompt(
            "agent.main",
            "Main agent prompt",
            category="agent",
            description="Main orchestrator prompt",
        )
        assert registry.get_prompt("agent.main") == "Main agent prompt"

    def test_list_prompts_all(self):
        """List all registered prompts."""
        registry = PromptRegistry()
        registry.register_prompt("prompt1", "content1", category="cat1")
        registry.register_prompt("prompt2", "content2", category="cat2")

        prompts = registry.list_prompts()
        assert len(prompts) == 2
        names = {p.name for p in prompts}
        assert names == {"prompt1", "prompt2"}

    def test_list_by_category(self):
        """List prompts filtered by category."""
        registry = PromptRegistry()
        registry.register_prompt("agent.main", "content", category="agent")
        registry.register_prompt("extraction.listing", "content", category="extraction")

        agents = registry.list_prompts(category="agent")
        assert len(agents) == 1
        assert agents[0].name == "agent.main"

    def test_get_prompt_version(self):
        """Get version of registered prompt."""
        registry = PromptRegistry()
        registry.register_prompt("test", "content", version="2.1.0")
        assert registry.get_prompt_version("test") == "2.1.0"

    def test_get_version_unknown_raises(self):
        """Getting version of unknown prompt raises KeyError."""
        registry = PromptRegistry()
        with pytest.raises(KeyError, match="Unknown prompt"):
            registry.get_prompt_version("nonexistent")

    def test_has_prompt(self):
        """Check if prompt exists."""
        registry = PromptRegistry()
        registry.register_prompt("exists", "content")
        assert registry.has_prompt("exists") is True
        assert registry.has_prompt("nonexistent") is False

    def test_singleton_instance(self):
        """Singleton returns same instance."""
        r1 = PromptRegistry.get_instance()
        r2 = PromptRegistry.get_instance()
        assert r1 is r2

    def test_singleton_loads_defaults(self):
        """Singleton loads default prompts."""
        registry = PromptRegistry.get_instance()
        # Should have agent prompts loaded
        assert registry.has_prompt("agent.main")


class TestPromptTemplate:
    """Tests for PromptTemplate."""

    def test_render_simple(self):
        """Render simple template."""
        template = PromptTemplate("Hello {{ name }}!", name="greeting")
        result = template.render(name="World")
        assert result == "Hello World!"

    def test_render_multiple_vars(self):
        """Render template with multiple variables."""
        template = PromptTemplate("{{ greeting }}, {{ name }}!", name="multi")
        result = template.render(greeting="Hi", name="Alice")
        assert result == "Hi, Alice!"

    def test_render_loop(self):
        """Render template with loop."""
        template = PromptTemplate(
            "Items:\n{% for item in items %}- {{ item }}\n{% endfor %}", name="list"
        )
        result = template.render(items=["a", "b", "c"])
        assert "- a" in result
        assert "- b" in result
        assert "- c" in result

    def test_render_conditional(self):
        """Render template with conditional."""
        template = PromptTemplate(
            "{% if show %}Visible{% else %}Hidden{% endif %}", name="conditional"
        )
        assert template.render(show=True) == "Visible"
        assert template.render(show=False) == "Hidden"

    def test_get_required_variables(self):
        """Extract required variables from template."""
        template = PromptTemplate("{{ a }} and {{ b }}", name="test")
        required = template.get_required_variables()
        assert "a" in required
        assert "b" in required

    def test_get_required_variables_loop(self):
        """Variables in loops are detected."""
        template = PromptTemplate("{% for x in items %}{{ x }}{% endfor %}", name="loop")
        required = template.get_required_variables()
        assert "items" in required

    def test_validate_context_all_present(self):
        """Validate context with all variables present."""
        template = PromptTemplate("{{ a }} {{ b }}", name="test")
        missing = template.validate_context({"a": 1, "b": 2})
        assert missing == []

    def test_validate_context_missing(self):
        """Validate context with missing variables."""
        template = PromptTemplate("{{ required_var }}", name="test")
        missing = template.validate_context({"other_var": "value"})
        assert "required_var" in missing

    def test_validate_context_extra_ok(self):
        """Extra context variables are allowed."""
        template = PromptTemplate("{{ a }}", name="test")
        missing = template.validate_context({"a": 1, "extra": 2})
        assert missing == []

    def test_invalid_syntax_raises(self):
        """Invalid template syntax raises ValueError."""
        with pytest.raises(ValueError, match="Invalid template syntax"):
            PromptTemplate("{{ unclosed", name="bad")

    def test_repr(self):
        """Test string representation."""
        template = PromptTemplate("test", name="my_template")
        assert "my_template" in repr(template)


class TestPromptProvider:
    """Tests for PromptProvider."""

    @pytest.fixture(autouse=True)
    def reset_provider(self):
        """Reset singletons between tests."""
        reset_prompt_provider()
        yield
        reset_prompt_provider()

    def test_get_agent_prompt(self):
        """Get agent prompt via provider."""
        provider = get_prompt_provider()
        prompt = provider.get_agent_prompt("main")
        assert "Orchestrator" in prompt

    def test_get_agent_prompt_discovery(self):
        """Get discovery agent prompt."""
        provider = get_prompt_provider()
        prompt = provider.get_agent_prompt("discovery")
        assert len(prompt) > 0

    def test_get_agent_prompt_unknown_raises(self):
        """Getting unknown agent raises KeyError."""
        provider = get_prompt_provider()
        with pytest.raises(KeyError):
            provider.get_agent_prompt("nonexistent_agent")

    def test_get_extraction_prompt_listing(self):
        """Get listing extraction prompt."""
        provider = get_prompt_provider()
        prompt = provider.get_extraction_prompt("listing")
        assert len(prompt) > 0

    def test_get_extraction_prompt_article(self):
        """Get article extraction prompt."""
        provider = get_prompt_provider()
        prompt = provider.get_extraction_prompt("article")
        assert len(prompt) > 0

    def test_get_prompt_direct(self):
        """Get prompt by full name."""
        provider = get_prompt_provider()
        prompt = provider.get_prompt("agent.main")
        assert "Orchestrator" in prompt

    def test_register_template(self):
        """Register and use a template."""
        provider = PromptProvider()
        provider.register_template("test_template", PromptTemplate("URL: {{ url }}", name="test"))
        assert provider.has_template("test_template")

    def test_render_prompt(self):
        """Render registered template."""
        provider = PromptProvider()
        provider.register_template("test_template", PromptTemplate("URL: {{ url }}", name="test"))
        result = provider.render_prompt("test_template", url="http://example.com")
        assert "http://example.com" in result

    def test_render_prompt_unknown_raises(self):
        """Rendering unknown template raises KeyError."""
        provider = PromptProvider()
        with pytest.raises(KeyError, match="Unknown template"):
            provider.render_prompt("nonexistent")

    def test_render_prompt_missing_context_raises(self):
        """Rendering with missing context raises ValueError."""
        provider = PromptProvider()
        provider.register_template("needs_var", PromptTemplate("{{ required }}", name="needs"))
        with pytest.raises(ValueError, match="Missing context variables"):
            provider.render_prompt("needs_var")

    def test_list_prompts(self):
        """List all prompts."""
        provider = get_prompt_provider()
        prompts = provider.list_prompts()
        assert len(prompts) > 0
        assert all(isinstance(p, PromptInfo) for p in prompts)

    def test_list_prompts_by_category(self):
        """List prompts filtered by category."""
        provider = get_prompt_provider()
        agents = provider.list_prompts(category="agent")
        for p in agents:
            assert p.category == "agent"

    def test_list_templates(self):
        """List registered templates."""
        provider = PromptProvider()
        provider.register_template("t1", PromptTemplate("a", name="t1"))
        provider.register_template("t2", PromptTemplate("b", name="t2"))
        templates = provider.list_templates()
        assert "t1" in templates
        assert "t2" in templates

    def test_get_prompt_version(self):
        """Get version of a prompt."""
        provider = get_prompt_provider()
        version = provider.get_prompt_version("agent.main")
        assert version  # Non-empty version string

    def test_singleton(self):
        """Singleton returns same instance."""
        p1 = get_prompt_provider()
        p2 = get_prompt_provider()
        assert p1 is p2


class TestDynamicTemplates:
    """Tests for pre-registered dynamic templates."""

    @pytest.fixture(autouse=True)
    def reset_provider(self):
        """Reset singletons between tests."""
        reset_prompt_provider()
        yield
        reset_prompt_provider()

    def test_pagination_pattern_template_registered(self):
        """Pagination pattern template is registered."""
        provider = get_prompt_provider()
        assert provider.has_template("pagination_pattern")

    def test_pagination_pattern_renders(self):
        """Pagination pattern template renders correctly."""
        provider = get_prompt_provider()
        result = provider.render_prompt(
            "pagination_pattern",
            target_url="http://example.com",
            pagination_links=["http://example.com?page=1", "http://example.com?page=2"],
        )
        assert "http://example.com" in result
        assert "page=1" in result

    def test_article_extraction_template_registered(self):
        """Article extraction template is registered."""
        provider = get_prompt_provider()
        assert provider.has_template("article_extraction")

    def test_article_extraction_renders(self):
        """Article extraction template renders correctly."""
        provider = get_prompt_provider()
        result = provider.render_prompt(
            "article_extraction",
            json_example='{"title": "", "content": ""}',
            selector_hints="h1.title, div.content",
        )
        assert "title" in result
        assert "content" in result

    def test_listing_url_extraction_template_registered(self):
        """Listing URL extraction template is registered."""
        provider = get_prompt_provider()
        assert provider.has_template("listing_url_extraction")

    def test_listing_url_extraction_renders(self):
        """Listing URL extraction template renders correctly."""
        provider = get_prompt_provider()
        result = provider.render_prompt(
            "listing_url_extraction",
            page_url="http://example.com/list?page=1",
            base_url="http://example.com",
            selector_hint="a.article-link",
        )
        assert "http://example.com" in result
        assert "a.article-link" in result
