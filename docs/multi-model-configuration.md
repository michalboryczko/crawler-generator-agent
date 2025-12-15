# Multi-Model Configuration System

## Overview

This document describes the architecture for supporting multiple LLM providers and models across different agents and tools. The system allows each agent and LLM-based tool to be configured with its own model, API key, and endpoint while maintaining the OpenAI API standard for all providers.

## Current State

Currently, the application uses a single `OpenAIConfig` for all components:

```python
@dataclass
class OpenAIConfig:
    api_key: str
    model: str = "gpt-4o"
    temperature: float = 0.0
```

All 5 agents and 8 LLM-based tools share this single configuration.

## Target State

Each agent and LLM-based tool should be independently configurable with:
- Model name
- API key (via environment variable reference)
- API base URL
- Temperature
- Additional provider-specific parameters

## Architecture

### 1. Model Registry

A central registry that defines available models and their connection details.

**File**: `src/core/model_registry.py`

```python
from dataclasses import dataclass, field
from typing import Optional
import os

@dataclass
class ModelConfig:
    """Configuration for a single model."""
    model_id: str                    # Unique identifier (e.g., "gpt-4o", "claude-3-opus")
    api_key_env: str                 # Environment variable name for API key (e.g., "OPENAI_KEY")
    api_base_url: Optional[str] = None  # Base URL (None = provider default)
    temperature: float = 0.0
    max_tokens: Optional[int] = None
    extra_params: dict = field(default_factory=dict)  # Provider-specific params

    def get_api_key(self) -> str:
        """Resolve API key from environment variable."""
        key = os.getenv(self.api_key_env)
        if not key:
            raise ValueError(
                f"API key not found. Set environment variable: {self.api_key_env}"
            )
        return key

    def get_api_base(self) -> Optional[str]:
        """Get API base URL, checking for override env var."""
        # Allow override via {MODEL_ID}_API_BASE env var
        override_env = f"{self.model_id.upper().replace('-', '_')}_API_BASE"
        return os.getenv(override_env, self.api_base_url)


@dataclass
class ModelRegistry:
    """Registry of all available models."""
    models: dict[str, ModelConfig] = field(default_factory=dict)

    def register(self, config: ModelConfig) -> None:
        """Register a model configuration."""
        self.models[config.model_id] = config

    def get(self, model_id: str) -> ModelConfig:
        """Get configuration for a model."""
        if model_id not in self.models:
            raise ValueError(
                f"Unknown model: {model_id}. "
                f"Available models: {list(self.models.keys())}"
            )
        return self.models[model_id]

    def list_models(self) -> list[str]:
        """List all registered model IDs."""
        return list(self.models.keys())

    @classmethod
    def from_config(cls, config_data: list[dict]) -> "ModelRegistry":
        """Create registry from configuration data."""
        registry = cls()
        for item in config_data:
            config = ModelConfig(
                model_id=item["model_id"],
                api_key_env=item["api_key_env"],
                api_base_url=item.get("api_base_url"),
                temperature=item.get("temperature", 0.0),
                max_tokens=item.get("max_tokens"),
                extra_params=item.get("extra_params", {}),
            )
            registry.register(config)
        return registry
```

### 2. Default Model Registry Configuration

**File**: `src/core/default_models.py`

```python
"""Default model configurations."""

DEFAULT_MODELS = [
    # OpenAI Models
    {
        "model_id": "gpt-4o",
        "api_key_env": "OPENAI_KEY",
        "api_base_url": None,  # Uses OpenAI default
        "temperature": 0.0,
    },
    {
        "model_id": "gpt-4o-mini",
        "api_key_env": "OPENAI_KEY",
        "api_base_url": None,
        "temperature": 0.0,
    },
    {
        "model_id": "gpt-4-turbo",
        "api_key_env": "OPENAI_KEY",
        "api_base_url": None,
        "temperature": 0.0,
    },
    {
        "model_id": "o1",
        "api_key_env": "OPENAI_KEY",
        "api_base_url": None,
        "temperature": 1.0,  # o1 requires temperature=1
        "extra_params": {"reasoning_effort": "medium"},
    },
    {
        "model_id": "o1-mini",
        "api_key_env": "OPENAI_KEY",
        "api_base_url": None,
        "temperature": 1.0,
    },

    # Anthropic Models (via OpenAI-compatible endpoint)
    {
        "model_id": "claude-3-5-sonnet-20241022",
        "api_key_env": "ANTHROPIC_KEY",
        "api_base_url": "https://api.anthropic.com/v1",  # Or OpenRouter/other proxy
        "temperature": 0.0,
    },
    {
        "model_id": "claude-3-opus-20240229",
        "api_key_env": "ANTHROPIC_KEY",
        "api_base_url": "https://api.anthropic.com/v1",
        "temperature": 0.0,
    },

    # Example: Local/Self-hosted Models
    {
        "model_id": "llama-3-70b",
        "api_key_env": "LOCAL_LLM_KEY",
        "api_base_url": "http://localhost:8000/v1",
        "temperature": 0.0,
    },

    # Example: OpenRouter (access multiple providers)
    {
        "model_id": "openrouter/anthropic/claude-3.5-sonnet",
        "api_key_env": "OPENROUTER_KEY",
        "api_base_url": "https://openrouter.ai/api/v1",
        "temperature": 0.0,
    },

    # Example: Kimi (Moonshot AI)
    {
        "model_id": "moonshot-v1-8k",
        "api_key_env": "KIMI_KEY",
        "api_base_url": "https://api.moonshot.cn/v1",
        "temperature": 0.0,
    },
    {
        "model_id": "moonshot-v1-32k",
        "api_key_env": "KIMI_KEY",
        "api_base_url": "https://api.moonshot.cn/v1",
        "temperature": 0.0,
    },

    # Example: DeepSeek
    {
        "model_id": "deepseek-chat",
        "api_key_env": "DEEPSEEK_KEY",
        "api_base_url": "https://api.deepseek.com/v1",
        "temperature": 0.0,
    },
    {
        "model_id": "deepseek-coder",
        "api_key_env": "DEEPSEEK_KEY",
        "api_base_url": "https://api.deepseek.com/v1",
        "temperature": 0.0,
    },
]


def get_default_registry() -> "ModelRegistry":
    """Create registry with default model configurations."""
    from src.core.model_registry import ModelRegistry
    return ModelRegistry.from_config(DEFAULT_MODELS)
```

### 3. Component Model Assignment Configuration

**File**: `src/core/component_models.py`

```python
"""Configuration for which model each component uses."""

from dataclasses import dataclass, field
from typing import Optional
import os

# Default model for all components if not specified
GLOBAL_DEFAULT_MODEL = "gpt-4o"


@dataclass
class ComponentModelConfig:
    """Maps components to their model assignments."""

    # Agent model assignments
    main_agent: str = GLOBAL_DEFAULT_MODEL
    browser_agent: str = GLOBAL_DEFAULT_MODEL
    selector_agent: str = GLOBAL_DEFAULT_MODEL
    accessibility_agent: str = GLOBAL_DEFAULT_MODEL
    data_prep_agent: str = GLOBAL_DEFAULT_MODEL

    # Tool model assignments (for LLM-based tools)
    listing_page_extractor: str = GLOBAL_DEFAULT_MODEL
    article_page_extractor: str = GLOBAL_DEFAULT_MODEL
    selector_aggregator: str = GLOBAL_DEFAULT_MODEL
    listing_pages_generator: str = GLOBAL_DEFAULT_MODEL
    article_pages_generator: str = GLOBAL_DEFAULT_MODEL
    batch_extract_listings: str = GLOBAL_DEFAULT_MODEL
    batch_extract_articles: str = GLOBAL_DEFAULT_MODEL
    extraction_agent: str = GLOBAL_DEFAULT_MODEL

    @classmethod
    def from_env(cls) -> "ComponentModelConfig":
        """
        Load component model assignments from environment variables.

        Environment variable naming convention:
        - {COMPONENT_NAME}_MODEL

        Examples:
        - MAIN_AGENT_MODEL=gpt-4o
        - SELECTOR_AGENT_MODEL=claude-3-5-sonnet-20241022
        - LISTING_PAGE_EXTRACTOR_MODEL=gpt-4o-mini
        """
        # Get global default (can be overridden)
        global_default = os.getenv("DEFAULT_MODEL", GLOBAL_DEFAULT_MODEL)

        return cls(
            # Agents
            main_agent=os.getenv("MAIN_AGENT_MODEL", global_default),
            browser_agent=os.getenv("BROWSER_AGENT_MODEL", global_default),
            selector_agent=os.getenv("SELECTOR_AGENT_MODEL", global_default),
            accessibility_agent=os.getenv("ACCESSIBILITY_AGENT_MODEL", global_default),
            data_prep_agent=os.getenv("DATA_PREP_AGENT_MODEL", global_default),

            # Tools
            listing_page_extractor=os.getenv("LISTING_PAGE_EXTRACTOR_MODEL", global_default),
            article_page_extractor=os.getenv("ARTICLE_PAGE_EXTRACTOR_MODEL", global_default),
            selector_aggregator=os.getenv("SELECTOR_AGGREGATOR_MODEL", global_default),
            listing_pages_generator=os.getenv("LISTING_PAGES_GENERATOR_MODEL", global_default),
            article_pages_generator=os.getenv("ARTICLE_PAGES_GENERATOR_MODEL", global_default),
            batch_extract_listings=os.getenv("BATCH_EXTRACT_LISTINGS_MODEL", global_default),
            batch_extract_articles=os.getenv("BATCH_EXTRACT_ARTICLES_MODEL", global_default),
            extraction_agent=os.getenv("EXTRACTION_AGENT_MODEL", global_default),
        )

    def get_model_for_component(self, component_name: str) -> str:
        """Get the model ID for a given component."""
        # Convert component name to attribute name
        attr_name = component_name.lower().replace("-", "_").replace(" ", "_")

        if hasattr(self, attr_name):
            return getattr(self, attr_name)

        raise ValueError(f"Unknown component: {component_name}")
```

### 4. Updated LLM Client

**File**: `src/core/llm.py` (updated)

```python
from openai import OpenAI
from typing import Optional
from src.core.model_registry import ModelConfig, ModelRegistry
from src.core.component_models import ComponentModelConfig


class LLMClient:
    """
    OpenAI-compatible LLM client that can connect to multiple providers.

    All providers must support the OpenAI API standard.
    """

    def __init__(
        self,
        model_config: ModelConfig,
        component_name: Optional[str] = None,
    ):
        """
        Initialize LLM client with model configuration.

        Args:
            model_config: Configuration for the model to use
            component_name: Optional name for logging/tracking
        """
        self.model_config = model_config
        self.component_name = component_name

        # Initialize OpenAI client with provider-specific settings
        client_kwargs = {
            "api_key": model_config.get_api_key(),
        }

        base_url = model_config.get_api_base()
        if base_url:
            client_kwargs["base_url"] = base_url

        self.client = OpenAI(**client_kwargs)

    def chat(
        self,
        messages: list[dict],
        tools: Optional[list] = None,
        tool_choice: str = "auto",
        parallel_tool_calls: bool = False,
        **kwargs,
    ) -> dict:
        """
        Send chat completion request.

        Uses OpenAI API standard, compatible with all configured providers.
        """
        request_kwargs = {
            "model": self.model_config.model_id,
            "messages": messages,
            "temperature": self.model_config.temperature,
            **self.model_config.extra_params,  # Provider-specific params
            **kwargs,  # Call-specific overrides
        }

        if self.model_config.max_tokens:
            request_kwargs["max_tokens"] = self.model_config.max_tokens

        if tools:
            request_kwargs["tools"] = [t.to_openai_schema() for t in tools]
            request_kwargs["tool_choice"] = tool_choice
            request_kwargs["parallel_tool_calls"] = parallel_tool_calls

        response = self.client.chat.completions.create(**request_kwargs)
        return self._parse_response(response)

    def _parse_response(self, response) -> dict:
        """Parse OpenAI response into standardized format."""
        choice = response.choices[0]
        message = choice.message

        result = {
            "role": "assistant",
            "content": message.content,
            "finish_reason": choice.finish_reason,
            "tool_calls": None,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
            "model": response.model,  # Actual model used (useful for routing)
        }

        if message.tool_calls:
            result["tool_calls"] = [
                {
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": json.loads(tc.function.arguments),
                }
                for tc in message.tool_calls
            ]

        return result


class LLMClientFactory:
    """
    Factory for creating LLM clients for specific components.

    Manages the model registry and component assignments.
    """

    def __init__(
        self,
        registry: ModelRegistry,
        component_config: ComponentModelConfig,
    ):
        self.registry = registry
        self.component_config = component_config
        self._clients: dict[str, LLMClient] = {}

    def get_client(self, component_name: str) -> LLMClient:
        """
        Get or create an LLM client for a specific component.

        Args:
            component_name: Name of the agent or tool

        Returns:
            Configured LLMClient instance
        """
        if component_name not in self._clients:
            model_id = self.component_config.get_model_for_component(component_name)
            model_config = self.registry.get(model_id)
            self._clients[component_name] = LLMClient(
                model_config=model_config,
                component_name=component_name,
            )

        return self._clients[component_name]

    def get_client_for_model(self, model_id: str) -> LLMClient:
        """
        Get client for a specific model (bypassing component mapping).

        Useful for tools that need to create isolated LLM contexts.
        """
        model_config = self.registry.get(model_id)
        return LLMClient(model_config=model_config)

    @classmethod
    def from_env(cls) -> "LLMClientFactory":
        """Create factory with environment-based configuration."""
        from src.core.default_models import get_default_registry

        registry = get_default_registry()
        component_config = ComponentModelConfig.from_env()

        return cls(registry, component_config)
```

### 5. Updated Application Configuration

**File**: `src/core/config.py` (updated)

```python
from dataclasses import dataclass
from src.core.model_registry import ModelRegistry
from src.core.component_models import ComponentModelConfig
from src.core.default_models import get_default_registry


@dataclass
class AppConfig:
    """Application configuration."""
    model_registry: ModelRegistry
    component_models: ComponentModelConfig
    browser: BrowserConfig
    output: OutputConfig

    @classmethod
    def from_env(cls) -> "AppConfig":
        """Load configuration from environment."""
        return cls(
            model_registry=get_default_registry(),
            component_models=ComponentModelConfig.from_env(),
            browser=BrowserConfig.from_env(),
            output=OutputConfig.from_env(),
        )
```

## Environment Variables

### API Keys

```bash
# Provider API Keys
OPENAI_KEY=sk-...
ANTHROPIC_KEY=sk-ant-...
OPENROUTER_KEY=sk-or-...
KIMI_KEY=...
DEEPSEEK_KEY=...
LOCAL_LLM_KEY=...

# Optional: Override API base URLs
# Format: {MODEL_ID}_API_BASE (model ID uppercased, hyphens to underscores)
GPT_4O_API_BASE=https://custom-endpoint.example.com/v1
```

### Component Model Assignments

```bash
# Global default (used if component-specific not set)
DEFAULT_MODEL=gpt-4o

# Agent models
MAIN_AGENT_MODEL=gpt-4o
BROWSER_AGENT_MODEL=gpt-4o-mini
SELECTOR_AGENT_MODEL=claude-3-5-sonnet-20241022
ACCESSIBILITY_AGENT_MODEL=gpt-4o-mini
DATA_PREP_AGENT_MODEL=gpt-4o

# Tool models
LISTING_PAGE_EXTRACTOR_MODEL=gpt-4o
ARTICLE_PAGE_EXTRACTOR_MODEL=gpt-4o
SELECTOR_AGGREGATOR_MODEL=gpt-4o
LISTING_PAGES_GENERATOR_MODEL=gpt-4o-mini
ARTICLE_PAGES_GENERATOR_MODEL=gpt-4o-mini
BATCH_EXTRACT_LISTINGS_MODEL=gpt-4o-mini
BATCH_EXTRACT_ARTICLES_MODEL=gpt-4o-mini
EXTRACTION_AGENT_MODEL=gpt-4o
```

## Example .env File

```bash
# =============================================================================
# API Keys
# =============================================================================

# OpenAI
OPENAI_KEY=sk-proj-...

# Anthropic (if using via OpenAI-compatible proxy)
ANTHROPIC_KEY=sk-ant-...

# Optional: Other providers
# OPENROUTER_KEY=sk-or-...
# KIMI_KEY=...
# DEEPSEEK_KEY=...

# =============================================================================
# Model Assignments
# =============================================================================

# Global default model (fallback for all components)
DEFAULT_MODEL=gpt-4o

# Agents - use more capable models for orchestration
MAIN_AGENT_MODEL=gpt-4o
SELECTOR_AGENT_MODEL=gpt-4o

# Agents - use faster/cheaper models for simple tasks
BROWSER_AGENT_MODEL=gpt-4o-mini
ACCESSIBILITY_AGENT_MODEL=gpt-4o-mini
DATA_PREP_AGENT_MODEL=gpt-4o-mini

# Tools - match complexity to task
LISTING_PAGE_EXTRACTOR_MODEL=gpt-4o
ARTICLE_PAGE_EXTRACTOR_MODEL=gpt-4o
SELECTOR_AGGREGATOR_MODEL=gpt-4o
LISTING_PAGES_GENERATOR_MODEL=gpt-4o-mini
ARTICLE_PAGES_GENERATOR_MODEL=gpt-4o-mini
BATCH_EXTRACT_LISTINGS_MODEL=gpt-4o-mini
BATCH_EXTRACT_ARTICLES_MODEL=gpt-4o-mini

# =============================================================================
# Other Configuration
# =============================================================================

CDP_HOST=localhost
CDP_PORT=9222
LOG_LEVEL=INFO
```

## Adding a New Provider

To add a new provider (e.g., Kimi/Moonshot AI):

### Step 1: Add Model Configuration

Edit `src/core/default_models.py`:

```python
DEFAULT_MODELS = [
    # ... existing models ...

    # Kimi (Moonshot AI)
    {
        "model_id": "moonshot-v1-8k",
        "api_key_env": "KIMI_KEY",
        "api_base_url": "https://api.moonshot.cn/v1",
        "temperature": 0.0,
    },
    {
        "model_id": "moonshot-v1-32k",
        "api_key_env": "KIMI_KEY",
        "api_base_url": "https://api.moonshot.cn/v1",
        "temperature": 0.0,
    },
    {
        "model_id": "moonshot-v1-128k",
        "api_key_env": "KIMI_KEY",
        "api_base_url": "https://api.moonshot.cn/v1",
        "temperature": 0.0,
    },
]
```

### Step 2: Set Environment Variables

```bash
# Add to .env
KIMI_KEY=your-api-key-here

# Assign to components
SELECTOR_AGENT_MODEL=moonshot-v1-32k
```

### Step 3: Verify Provider Compatibility

Ensure the provider supports:
- OpenAI-compatible `/v1/chat/completions` endpoint
- Function calling (tools) if the component uses tools
- The message format (system/user/assistant/tool roles)

## Usage Patterns

### Pattern 1: Cost Optimization

Use cheaper models for simpler tasks:

```bash
# Expensive: Complex reasoning and orchestration
MAIN_AGENT_MODEL=gpt-4o
SELECTOR_AGENT_MODEL=gpt-4o

# Cheaper: Simple extraction and generation
BROWSER_AGENT_MODEL=gpt-4o-mini
LISTING_PAGES_GENERATOR_MODEL=gpt-4o-mini
BATCH_EXTRACT_LISTINGS_MODEL=gpt-4o-mini
```

### Pattern 2: Provider Diversity

Use different providers for redundancy or capability matching:

```bash
# OpenAI for general tasks
MAIN_AGENT_MODEL=gpt-4o
BROWSER_AGENT_MODEL=gpt-4o-mini

# Anthropic for complex extraction (better at structured output)
SELECTOR_AGENT_MODEL=claude-3-5-sonnet-20241022
LISTING_PAGE_EXTRACTOR_MODEL=claude-3-5-sonnet-20241022

# Local model for high-volume batch operations
BATCH_EXTRACT_LISTINGS_MODEL=llama-3-70b
```

### Pattern 3: Experimentation

A/B test different models:

```bash
# Test run with new model
SELECTOR_AGENT_MODEL=gpt-4o-new-version

# Compare results with baseline
```

### Pattern 4: Regional Compliance

Use region-specific providers:

```bash
# For China-based deployments
DEFAULT_MODEL=moonshot-v1-32k
KIMI_KEY=...
```

## Component Reference

### Agents

| Agent | Purpose | Recommended Model Class |
|-------|---------|------------------------|
| `main_agent` | Orchestration, planning | High capability (gpt-4o, claude-3-opus) |
| `browser_agent` | Navigation, link extraction | Medium (gpt-4o-mini) |
| `selector_agent` | CSS selector discovery | High capability |
| `accessibility_agent` | HTTP validation | Low (gpt-4o-mini) |
| `data_prep_agent` | Dataset preparation | Medium |

### LLM-Based Tools

| Tool | Purpose | Recommended Model Class |
|------|---------|------------------------|
| `listing_page_extractor` | Extract selectors from listing pages | High capability |
| `article_page_extractor` | Extract selectors from article pages | High capability |
| `selector_aggregator` | Aggregate selector patterns | High capability |
| `listing_pages_generator` | Detect pagination patterns | Medium |
| `article_pages_generator` | Group and sample URLs | Medium |
| `batch_extract_listings` | Batch listing extraction | Medium/Low |
| `batch_extract_articles` | Batch article extraction | Medium/Low |
| `extraction_agent` | Isolated extraction context | High capability |

## Migration Guide

### From Single Model to Multi-Model

1. **Update configuration loading**:
   ```python
   # Before
   config = OpenAIConfig.from_env()
   llm = LLMClient(config)

   # After
   factory = LLMClientFactory.from_env()
   llm = factory.get_client("main_agent")
   ```

2. **Update agent initialization**:
   ```python
   # Before
   class MainAgent(BaseAgent):
       def __init__(self, llm: LLMClient, ...):
           self.llm = llm

   # After
   class MainAgent(BaseAgent):
       def __init__(self, llm_factory: LLMClientFactory, ...):
           self.llm = llm_factory.get_client("main_agent")
   ```

3. **Update tools with isolated contexts**:
   ```python
   # Before
   class ListingPageExtractorTool(BaseTool):
       def __init__(self, llm: LLMClient):
           self.llm = llm

   # After
   class ListingPageExtractorTool(BaseTool):
       def __init__(self, llm_factory: LLMClientFactory):
           self.llm = llm_factory.get_client("listing_page_extractor")
   ```

4. **Set environment variables**:
   ```bash
   # Rename OPENAI_API_KEY to OPENAI_KEY
   # Add component assignments as needed
   ```

## Future Enhancements

### Planned Features

1. **Runtime model switching**: Change models without restart
2. **Model fallback chains**: Automatic fallback on failure
3. **Cost tracking per component**: Track spending by agent/tool
4. **Rate limiting per provider**: Respect provider limits
5. **Response caching**: Cache identical requests
6. **Model capability validation**: Ensure model supports required features

### Configuration File Support

Future: Support YAML/JSON configuration files:

```yaml
# models.yaml
models:
  - model_id: gpt-4o
    api_key_env: OPENAI_KEY
    temperature: 0.0

  - model_id: claude-3-5-sonnet
    api_key_env: ANTHROPIC_KEY
    api_base_url: https://api.anthropic.com/v1

components:
  main_agent: gpt-4o
  selector_agent: claude-3-5-sonnet
  browser_agent: gpt-4o-mini
```

## Troubleshooting

### Common Issues

1. **"API key not found"**
   - Ensure the environment variable is set
   - Check the variable name matches `api_key_env` in model config

2. **"Unknown model"**
   - Add model to `DEFAULT_MODELS` in `default_models.py`
   - Or register dynamically via `registry.register()`

3. **"Connection refused"**
   - Check `api_base_url` is correct
   - Verify the endpoint is accessible

4. **"Tool calls not supported"**
   - Some models/providers don't support function calling
   - Use a different model for tool-using components

### Debug Mode

Enable verbose logging to trace model usage:

```bash
LOG_LEVEL=DEBUG
```

This will log:
- Which model is used for each request
- API endpoint being called
- Token usage per component
