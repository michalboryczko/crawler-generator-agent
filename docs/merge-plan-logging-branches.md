# Merge Plan: Bring Multi-Model Config to feature/logging-refactor

## Executive Summary

**Base branch**: `feature/logging-refactor` (keep its observability/logging system)
**Source branch**: `feature/logging` (cherry-pick multi-model config + .env fix)

### Goals
- **Keep**: Observability system from `feature/logging-refactor` (`src/observability/`)
- **Add**: Multi-model configuration from `feature/logging`
- **Add**: `.env` loading fix (supports both `OPENAI_API_KEY` and `OPENAI_KEY`)
- **Discard**: Logging system from `feature/logging` (`src/core/log_*.py`)

---

## Branch Analysis

### Common Ancestor
```
1b8cc66 - Add comprehensive observability refactoring plan
```

### feature/logging-refactor (BASE - keep this logging)
**Latest commit**: `f036e75` (updated)

Has observability system:
- `src/observability/__init__.py`
- `src/observability/config.py`
- `src/observability/context.py`
- `src/observability/decorators.py`
- `src/observability/emitters.py`
- `src/observability/outputs.py`
- `src/observability/schema.py`
- `src/observability/serializers.py`
- `src/observability/handlers.py` **(NEW)**
- `src/observability/tracer.py` **(NEW)**
- `tests/test_observability/`
- `docs/traces_ids.md` **(NEW)**

Recent changes (commits c931d42, f036e75):
- Added `OTelGrpcHandler` for OpenTelemetry log export
- Added `tracer.py` for distributed tracing
- Updated `main.py` with new OTel handler initialization
- Improved context management and decorators

**Missing** multi-model files:
- `src/core/model_registry.py`
- `src/core/component_models.py`
- `src/core/default_models.py`
- `LLMClientFactory` class in `src/core/llm.py`

### feature/logging (SOURCE - cherry-pick from here)
**Latest commit**: `7f3d76b`

Has multi-model configuration:
- `src/core/model_registry.py` ✓
- `src/core/component_models.py` ✓
- `src/core/default_models.py` ✓
- `src/core/config.py` - has .env loading fix
- `src/core/llm.py` - has `LLMClientFactory`
- `.env.example` - has multi-model env vars
- `main.py` - has `--multi-model` flag

Also has:
- `src/core/json_parser.py` (useful utility)
- `tests/test_json_parser.py`

---

## Files to Transfer

### New Files (copy directly)
| File | Description |
|------|-------------|
| `src/core/model_registry.py` | Model configuration and registry |
| `src/core/component_models.py` | Per-component model assignments |
| `src/core/default_models.py` | Default model definitions |
| `src/core/json_parser.py` | JSON parsing utilities |
| `tests/test_json_parser.py` | Tests for JSON parser |
| `tests/__init__.py` | Test package init |

### Files to Update (merge changes)
| File | Changes Needed |
|------|----------------|
| `src/core/config.py` | Add `.env` loading fix + multi-model support |
| `src/core/llm.py` | Add `LLMClientFactory` class |
| `.env.example` | Add multi-model environment variables |
| `main.py` | Add `--multi-model` flag (keep observability imports) |

---

## Step-by-Step Instructions

### Step 1: Switch to feature/logging-refactor
```bash
git checkout feature/logging-refactor
git checkout -b feature/logging-refactor-with-multimodel
```

### Step 2: Copy new multi-model files from feature/logging
```bash
# Copy new files directly
git show feature/logging:src/core/model_registry.py > src/core/model_registry.py
git show feature/logging:src/core/component_models.py > src/core/component_models.py
git show feature/logging:src/core/default_models.py > src/core/default_models.py
git show feature/logging:src/core/json_parser.py > src/core/json_parser.py

# Copy test files
git show feature/logging:tests/__init__.py > tests/__init__.py
git show feature/logging:tests/test_json_parser.py > tests/test_json_parser.py

git add src/core/model_registry.py src/core/component_models.py src/core/default_models.py src/core/json_parser.py
git add tests/__init__.py tests/test_json_parser.py
```

### Step 3: Update src/core/config.py

Apply these changes manually to `src/core/config.py`:

```python
# Add imports at top
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .model_registry import ModelRegistry
    from .component_models import ComponentModelConfig

# Update OpenAIConfig class
@dataclass
class OpenAIConfig:
    """Legacy OpenAI API configuration.

    This class is maintained for backward compatibility. For new code,
    use LLMClientFactory with ModelConfig and ComponentModelConfig instead.

    See docs/multi-model-configuration.md for migration guide.
    """
    api_key: str
    model: str = "gpt-5.1"
    temperature: float = 0.0

    @classmethod
    def from_env(cls) -> "OpenAIConfig":
        """Load configuration from environment variables.

        Supports both legacy (OPENAI_API_KEY) and new (OPENAI_KEY) variable names.
        """
        # Support both old and new env var names
        api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENAI_KEY")
        if not api_key:
            raise ValueError(
                "OpenAI API key not found. Set OPENAI_API_KEY or OPENAI_KEY environment variable"
            )
        return cls(
            api_key=api_key,
            model=os.environ.get("OPENAI_MODEL", os.environ.get("DEFAULT_MODEL", "gpt-5.1")),
            temperature=float(os.environ.get("OPENAI_TEMPERATURE", "0.0")),
        )
```

### Step 4: Update src/core/llm.py

Add the `LLMClientFactory` class from `feature/logging`. This requires careful merging because `feature/logging-refactor` uses `@traced_llm_client` decorator.

**Option A**: Extract just `LLMClientFactory` class and add it to existing file
```bash
# View the LLMClientFactory class
git show feature/logging:src/core/llm.py | grep -A200 "class LLMClientFactory"
```

**Option B**: Copy entire file and re-add observability decorators
```bash
# Get the new file
git show feature/logging:src/core/llm.py > src/core/llm.py.new

# Manually merge, keeping:
# - @traced_llm_client decorator from feature/logging-refactor
# - LLMClientFactory class from feature/logging
# - Multi-model support from feature/logging
```

Key changes needed in `llm.py`:
1. Keep `from ..observability.decorators import traced_llm_client`
2. Keep `@traced_llm_client` decorator on `LLMClient.chat()` method
3. Add imports: `from .model_registry import ModelConfig, ModelRegistry`
4. Add imports: `from .component_models import ComponentModelConfig`
5. Add `LLMClientFactory` class
6. Update `LLMClient` to support both `OpenAIConfig` and `ModelConfig`

### Step 5: Update .env.example

Add multi-model configuration section from `feature/logging`:

```bash
# View new .env.example content
git show feature/logging:.env.example
```

Add these sections:
```env
# =============================================================================
# Multi-Model Configuration
# =============================================================================
MULTI_MODEL_ENABLED=false

# Provider API Keys
# OPENAI_KEY=sk-...
# ANTHROPIC_KEY=sk-ant-...
# OPENROUTER_KEY=sk-or-...

# Global default model
DEFAULT_MODEL=gpt-5.1

# Agent-specific model assignments
# MAIN_AGENT_MODEL=gpt-5.1
# BROWSER_AGENT_MODEL=gpt-5.1-mini
# ... (see full list in feature/logging:.env.example)
```

### Step 6: Update main.py

Add `--multi-model` flag while keeping the new observability imports:

```python
# Keep these imports from feature/logging-refactor (updated structure):
from src.observability.config import (
    ObservabilityConfig,
    initialize_observability,
    shutdown,
)
from src.observability.handlers import OTelGrpcHandler, OTelConfig
from src.observability.context import get_or_create_context, set_context
from src.observability.emitters import emit_info, emit_warning, emit_error

# Add these imports for multi-model:
from src.core.llm import LLMClient, LLMClientFactory

# Add arguments after existing args:
parser.add_argument(
    "--multi-model", "-m",
    action="store_true",
    help="Enable multi-model mode (use LLMClientFactory with per-component models)"
)
parser.add_argument(
    "--list-models",
    action="store_true",
    help="List available models and exit"
)

# Add logic to use factory when --multi-model is set
# Place this after ObservabilityConfig initialization:
if args.multi_model:
    factory = LLMClientFactory.from_env()
    # Pass factory to agents instead of single LLMClient
else:
    llm = LLMClient(config.openai)
    # Use single client (legacy mode)
```

**Note**: The updated `main.py` in `feature/logging-refactor` now uses:
- `OTelGrpcHandler` for log export
- `OTelConfig` for endpoint configuration
- `set_context` for context management

Make sure to preserve this new structure when adding multi-model support.

### Step 7: Update agents to support factory (optional)

If you want agents to work with `LLMClientFactory`:

In `src/agents/base.py`, the `__init__` should accept both:
```python
def __init__(
    self,
    llm: Union[LLMClient, "LLMClientFactory"],
    tools: list[BaseTool] | None = None,
    component_name: Optional[str] = None,
):
    if hasattr(llm, 'get_client'):
        # It's a factory
        self.llm_factory = llm
        self.llm = llm.get_client(component_name or self.name)
    else:
        # Direct LLMClient
        self.llm_factory = None
        self.llm = llm
```

**Note**: Keep the `@traced_agent` decorator from `feature/logging-refactor`.

### Step 8: Commit the changes
```bash
git add -A
git commit -m "feat: Add multi-model configuration to feature/logging-refactor

- Add model registry, component models, and default models
- Add LLMClientFactory for per-component model assignment
- Fix .env loading to support both OPENAI_API_KEY and OPENAI_KEY
- Add --multi-model CLI flag
- Add JSON parser utilities
- Keep observability system intact"
```

---

## Files Requiring Manual Review

| File | Review Points |
|------|---------------|
| `src/core/llm.py` | Merge LLMClientFactory + keep @traced_llm_client |
| `src/agents/base.py` | Add factory support + keep @traced_agent |
| `main.py` | Add --multi-model + keep observability imports |

---

## Post-Merge Verification Checklist

### Observability (must be preserved)
- [ ] `src/observability/` directory exists with all files
- [ ] `src/observability/handlers.py` exists (OTelGrpcHandler)
- [ ] `src/observability/tracer.py` exists
- [ ] `src/core/llm.py` has `@traced_llm_client` decorator
- [ ] `main.py` imports from `src.observability.*`
- [ ] `main.py` uses `OTelGrpcHandler` and `OTelConfig`

### Multi-model (must be added)
- [ ] `src/core/model_registry.py` exists
- [ ] `src/core/component_models.py` exists
- [ ] `src/core/default_models.py` exists
- [ ] `src/core/json_parser.py` exists
- [ ] `src/core/config.py` has dual .env variable support (OPENAI_API_KEY + OPENAI_KEY)
- [ ] `src/core/llm.py` has `LLMClientFactory` class
- [ ] `main.py` has `--multi-model` flag
- [ ] `.env.example` has multi-model section

### Tests
- [ ] Tests pass: `pytest tests/`
- [ ] App starts in legacy mode: `python main.py --help`
- [ ] App starts in multi-model mode: `python main.py --multi-model --list-models`

---

## Merging to Main

After verification:
```bash
git checkout main
git merge feature/logging-refactor-with-multimodel --no-ff -m "feat: Observability system + multi-model configuration

- Decorator-based observability with @traced_agent, @traced_llm_client
- Multi-model support via LLMClientFactory
- Per-component model assignments
- Flexible .env configuration"
```

---

## Summary

| Component | Source Branch | Action |
|-----------|--------------|--------|
| Observability (`src/observability/`) | feature/logging-refactor | Keep |
| Multi-model config | feature/logging | Copy |
| .env loading fix | feature/logging | Merge into config.py |
| LLMClientFactory | feature/logging | Merge into llm.py |
| Logging (`src/core/log_*.py`) | feature/logging | Do NOT copy |
