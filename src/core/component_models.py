"""Configuration for which model each component uses.

This module maps agents and tools to their assigned LLM models.
Configuration is loaded from environment variables, allowing different
models for different components without code changes.
"""

import logging
import os
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Default model for all components if not specified
GLOBAL_DEFAULT_MODEL = "gpt-5.1"


@dataclass
class ComponentModelConfig:
    """Maps components (agents and tools) to their model assignments.

    Each field represents a component that can have an independently
    configured LLM model. Defaults to GLOBAL_DEFAULT_MODEL if not set.

    Attributes:
        # Agents
        main_agent: Main orchestrator agent
        discovery_agent: Site discovery and navigation agent
        selector_agent: CSS selector discovery agent
        accessibility_agent: HTTP accessibility check agent
        data_prep_agent: Test data preparation agent
        plan_generator_agent: Plan generation from collected data

        # LLM-based tools
        listing_page_extractor: Extract selectors from listing pages
        article_page_extractor: Extract selectors from article pages
        selector_aggregator: Aggregate selector patterns
        listing_pages_generator: Generate pagination URLs
        article_pages_generator: Group and sample article URLs
        batch_extract_listings: Batch listing extraction
        batch_extract_articles: Batch article extraction
        extraction_agent: Isolated extraction context
        supervisor_tool: LLM-based output validation
    """

    # Agent model assignments
    main_agent: str = GLOBAL_DEFAULT_MODEL
    discovery_agent: str = GLOBAL_DEFAULT_MODEL
    selector_agent: str = GLOBAL_DEFAULT_MODEL
    accessibility_agent: str = GLOBAL_DEFAULT_MODEL
    data_prep_agent: str = GLOBAL_DEFAULT_MODEL
    plan_generator_agent: str = GLOBAL_DEFAULT_MODEL

    # Tool model assignments (for LLM-based tools)
    listing_page_extractor: str = GLOBAL_DEFAULT_MODEL
    article_page_extractor: str = GLOBAL_DEFAULT_MODEL
    selector_aggregator: str = GLOBAL_DEFAULT_MODEL
    listing_pages_generator: str = GLOBAL_DEFAULT_MODEL
    article_pages_generator: str = GLOBAL_DEFAULT_MODEL
    batch_extract_listings: str = GLOBAL_DEFAULT_MODEL
    batch_extract_articles: str = GLOBAL_DEFAULT_MODEL
    extraction_agent: str = GLOBAL_DEFAULT_MODEL
    supervisor_tool: str = GLOBAL_DEFAULT_MODEL

    @classmethod
    def with_default(cls, model_id: str) -> "ComponentModelConfig":
        """Create config where all components use the same model.

        Useful for legacy mode where a single model is used for everything.

        Args:
            model_id: The model ID to use for all components

        Returns:
            ComponentModelConfig with all fields set to the given model
        """
        # Build kwargs for all fields with the same model
        field_values = {field: model_id for field in cls.__dataclass_fields__}
        return cls(**field_values)

    @classmethod
    def from_env(cls) -> "ComponentModelConfig":
        """Load component model assignments from environment variables.

        Environment variable naming convention:
        - {COMPONENT_NAME}_MODEL

        Examples:
            MAIN_AGENT_MODEL=gpt-4o
            SELECTOR_AGENT_MODEL=claude-3-5-sonnet-20241022
            LISTING_PAGE_EXTRACTOR_MODEL=gpt-4o-mini

        The DEFAULT_MODEL environment variable sets the fallback for all
        components that don't have an explicit assignment.

        Returns:
            ComponentModelConfig with environment-based assignments
        """
        # Get global default (can be overridden)
        global_default = os.getenv("DEFAULT_MODEL", GLOBAL_DEFAULT_MODEL)

        config = cls(
            # Agents
            main_agent=os.getenv("MAIN_AGENT_MODEL", global_default),
            discovery_agent=os.getenv("DISCOVERY_AGENT_MODEL", global_default),
            selector_agent=os.getenv("SELECTOR_AGENT_MODEL", global_default),
            accessibility_agent=os.getenv("ACCESSIBILITY_AGENT_MODEL", global_default),
            data_prep_agent=os.getenv("DATA_PREP_AGENT_MODEL", global_default),
            plan_generator_agent=os.getenv("PLAN_GENERATOR_AGENT_MODEL", global_default),
            # Tools
            listing_page_extractor=os.getenv("LISTING_PAGE_EXTRACTOR_MODEL", global_default),
            article_page_extractor=os.getenv("ARTICLE_PAGE_EXTRACTOR_MODEL", global_default),
            selector_aggregator=os.getenv("SELECTOR_AGGREGATOR_MODEL", global_default),
            listing_pages_generator=os.getenv("LISTING_PAGES_GENERATOR_MODEL", global_default),
            article_pages_generator=os.getenv("ARTICLE_PAGES_GENERATOR_MODEL", global_default),
            batch_extract_listings=os.getenv("BATCH_EXTRACT_LISTINGS_MODEL", global_default),
            batch_extract_articles=os.getenv("BATCH_EXTRACT_ARTICLES_MODEL", global_default),
            extraction_agent=os.getenv("EXTRACTION_AGENT_MODEL", global_default),
            supervisor_tool=os.getenv("SUPERVISOR_TOOL_MODEL", global_default),
        )

        # Log non-default assignments
        for field_name in config.__dataclass_fields__:
            value = getattr(config, field_name)
            if value != global_default:
                logger.info(f"Component '{field_name}' using model: {value}")

        return config

    def get_model_for_component(self, component_name: str) -> str:
        """Get the model ID for a given component.

        Args:
            component_name: Name of the agent or tool. Can use various formats:
                - "main_agent"
                - "main-agent"
                - "MainAgent"
                - "listing_page_extractor"

        Returns:
            The model ID assigned to the component

        Raises:
            ValueError: If the component is not recognized
        """
        # Normalize component name to attribute format
        attr_name = component_name.lower().replace("-", "_").replace(" ", "_")

        # Handle class name format (e.g., "MainAgent" -> "main_agent")
        import re

        attr_name = re.sub(r"(?<!^)(?=[A-Z])", "_", attr_name).lower()

        if hasattr(self, attr_name):
            return getattr(self, attr_name)

        # Try without trailing "_agent" or "_tool" suffix
        for suffix in ["_agent", "_tool"]:
            if attr_name.endswith(suffix):
                base_name = attr_name[: -len(suffix)]
                if hasattr(self, base_name):
                    return getattr(self, base_name)

        raise ValueError(
            f"Unknown component: {component_name}. "
            f"Available components: {list(self.__dataclass_fields__.keys())}"
        )

    def list_components(self) -> list[str]:
        """List all configurable component names.

        Returns:
            List of component names that can be configured
        """
        return list(self.__dataclass_fields__.keys())

    def get_all_assignments(self) -> dict[str, str]:
        """Get all component-to-model assignments.

        Returns:
            Dictionary mapping component names to their model IDs
        """
        return {field_name: getattr(self, field_name) for field_name in self.__dataclass_fields__}

    def get_models_in_use(self) -> set[str]:
        """Get the set of unique models being used.

        Useful for pre-validating that all required models are available.

        Returns:
            Set of model IDs that are assigned to at least one component
        """
        return set(self.get_all_assignments().values())

    def __repr__(self) -> str:
        assignments = self.get_all_assignments()
        # Group by model
        by_model: dict[str, list[str]] = {}
        for comp, model in assignments.items():
            by_model.setdefault(model, []).append(comp)

        parts = []
        for model, components in sorted(by_model.items()):
            parts.append(f"{model}: [{', '.join(components)}]")

        return f"ComponentModelConfig({'; '.join(parts)})"
