# Plan: Auto-Generated Tool Descriptions in Agent Prompts

## Goal
Replace hardcoded "## Available Tools" sections in agent prompts with auto-generated sections from actual tools attached to each agent, similar to how sub-agents are auto-generated via `_build_sub_agents_section()`.

## Current State
- **Sub-agents pattern**: `sub_agents_section.md.j2` template rendered by `_build_sub_agents_section()` in BaseAgent
- **Hardcoded tool sections** in 4 templates:
  - `selector_agent.md.j2` - 8 tools with categories (Sampling/Extraction/Aggregation/Memory)
  - `main_agent.md.j2` - 9 tools in simple list
  - `data_prep_agent.md.j2` - 8 tools with detailed parameters
  - `accessibility_agent.md.j2` - tools embedded in workflow

## Design Decisions

1. **No tips feature**: Agent-specific workflow guidance stays in prompt templates (e.g., "Call memory_read for 'target_url'"). The auto-generated section only describes WHAT tools are available, not HOW to use them in the workflow.

2. **Alphabetical category ordering**: Categories sorted alphabetically for simplicity and predictability.

3. **Separation of concerns**:
   - **Template (manual)**: Workflow steps, logic, agent-specific instructions
   - **Auto-generated**: "## Available Tools" section with tool names, descriptions, categories

## Implementation Plan

### Phase 1: Extend BaseTool Interface

**File: `src/tools/base.py`**

Add `category` class attribute and new methods to `BaseTool` class:

```python
class BaseTool(ABC):
    """Abstract base class for all tools."""

    # NEW: Optional category for grouping tools in prompts (default "general")
    category: str = "general"

    # Existing abstract properties remain unchanged
    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def description(self) -> str: ...

    # NEW: Getter methods for template access (consistent with AgentTool pattern)
    def get_tool_name(self) -> str:
        """Return the tool's name for template rendering."""
        return self.name

    def get_tool_description(self) -> str:
        """Return the tool's description for template rendering."""
        return self.description

    def get_tool_category(self) -> str:
        """Return the tool's category for grouping in prompts."""
        return self.category

    def get_parameters_description(self) -> str:
        """Return formatted parameter descriptions from schema.

        Returns:
            Human-readable parameter documentation string
        """
        schema = self.get_parameters_schema()
        properties = schema.get("properties", {})
        required = set(schema.get("required", []))

        if not properties:
            return "No parameters"

        lines = []
        for param_name, prop in properties.items():
            req_marker = "(required)" if param_name in required else "(optional)"
            desc = prop.get("description", "No description")
            param_type = prop.get("type", "any")
            lines.append(f"  - {param_name} ({param_type}) {req_marker}: {desc}")

        return "\n".join(lines)
```

### Phase 2: Add Categories to Existing Tools

Add `category` class attribute to each tool class. Example:

```python
# In src/tools/memory.py
class MemoryReadTool(BaseTool):
    category = "memory"  # ADD THIS LINE
    name = "memory_read"
    description = "Read a value from shared memory by key."
    # ... rest unchanged

class MemoryWriteTool(BaseTool):
    category = "memory"  # ADD THIS LINE
    name = "memory_write"
    # ...
```

**Full mapping of tools to categories:**

| Tool File | Tools | Category |
|-----------|-------|----------|
| `src/tools/memory.py` | MemoryRead/Write/Search/List/Dump | `"memory"` |
| `src/tools/selector_sampling.py` | ListingPagesGenerator, ArticlePagesGenerator | `"sampling"` |
| `src/tools/selector_extraction.py` | ListingPageExtractor, ArticlePageExtractor | `"extraction"` |
| `src/tools/selector_extraction.py` | SelectorAggregator | `"aggregation"` |
| `src/tools/extraction.py` | BatchFetchURLsTool | `"fetch"` |
| `src/tools/extraction.py` | BatchExtractListingsTool, BatchExtractArticlesTool | `"extraction"` |
| `src/tools/file.py` | FileCreateTool, FileReadTool, FileReplaceTool | `"file"` |
| `src/tools/plan_generator.py` | GeneratePlanTool, GenerateTestMdTool | `"generator"` |
| `src/contracts/tools/*.py` | ValidateResponse, PrepareValidation, GenerateUuid, etc. | `"contract"` |

### Phase 3: Create Templates

**New files in `src/contracts/templates/`:**

**1. `tools_section.md.j2`** - Main template with category grouping
```jinja2
## Available Tools
{% if categorize_tools %}
{% for category in tools_by_category.keys() | sort %}
### {{ category | title }} Tools
{% for tool in tools_by_category[category] %}
{% include tool_item_template with context %}
{% endfor %}
{% endfor %}
{% else %}
{% for tool in tools %}
{% include tool_item_template with context %}
{% endfor %}
{% endif %}
```

**2. `tool_item_standard.md.j2`** - Default: name + description
```jinja2
- **{{ tool.get_tool_name() }}**: {{ tool.get_tool_description() }}
```

**3. `tool_item_detailed.md.j2`** - With parameters (for data_prep_agent)
```jinja2
#### {{ tool.get_tool_name() }}
{{ tool.get_tool_description() }}

**Parameters:**
{{ tool.get_parameters_description() }}

```

### Phase 4: Extend BaseAgent

**File: `src/agents/base.py`**

**Step 1: Add enum (at top of file or in separate `src/tools/enums.py`):**
```python
from enum import Enum

class ToolDescriptionLevel(Enum):
    """Level of detail for tool descriptions in prompts."""
    STANDARD = "standard"    # Name + description (default)
    DETAILED = "detailed"    # Name + description + parameters
```

**Step 2: Add class attributes to BaseAgent:**
```python
class BaseAgent:
    name: str = "base_agent"
    description: str = "Base agent"
    system_prompt: str = "You are a helpful assistant."

    # NEW: Configuration for auto-generated tools section
    tools_description_level: ToolDescriptionLevel = ToolDescriptionLevel.STANDARD
    categorize_tools: bool = True
    exclude_agent_tools_from_tools_section: bool = True
```

**Step 3: Add `_build_tools_section()` method:**
```python
def _build_tools_section(self) -> str:
    """Build prompt section describing available tools.

    Returns:
        Formatted tools section, or empty string if no tools
    """
    # Filter out AgentTools (they have their own section via _build_sub_agents_section)
    if self.exclude_agent_tools_from_tools_section:
        from ..contracts.agent_tool import AgentTool
        tools = [t for t in self.tools if not isinstance(t, AgentTool)]
    else:
        tools = list(self.tools)

    if not tools:
        return ""

    from ..contracts.template_renderer import render_template

    # Group tools by category (sorted alphabetically)
    tools_by_category: dict[str, list] = {}
    for tool in tools:
        category = tool.get_tool_category()
        if category not in tools_by_category:
            tools_by_category[category] = []
        tools_by_category[category].append(tool)

    # Select item template based on detail level
    item_template = {
        ToolDescriptionLevel.STANDARD: "tool_item_standard.md.j2",
        ToolDescriptionLevel.DETAILED: "tool_item_detailed.md.j2",
    }[self.tools_description_level]

    return render_template(
        "tools_section.md.j2",
        tools=tools,
        tools_by_category=tools_by_category,
        categorize_tools=self.categorize_tools,
        tool_item_template=item_template,
    )
```

**Step 4: Update `_build_final_prompt()` to include tools section:**
```python
def _build_final_prompt(self, ...) -> str:
    prompt_parts = [self.system_prompt]

    # NEW: Add tools section
    tools_section = self._build_tools_section()
    if tools_section:
        prompt_parts.append(tools_section)

    # Existing: Add sub-agents section if agent_tools exist
    sub_agents_section = self._build_sub_agents_section()
    if sub_agents_section:
        prompt_parts.append(sub_agents_section)

    # ... rest of existing code (response rules, context injection) ...
    return "\n\n".join(prompt_parts)
```

### Phase 5: Configure Each Agent

| Agent | Detail Level | Categorize |
|-------|--------------|------------|
| `SelectorAgent` | STANDARD | Yes |
| `DataPrepAgent` | DETAILED | Yes |
| `MainAgent` | STANDARD | Yes |
| `DiscoveryAgent` | STANDARD | No |

### Phase 6: Migrate Prompts

Remove hardcoded `## Available Tools` sections from each template:

**1. `src/prompts/templates/agents/selector_agent.md.j2`**
Remove lines 5-24 (the entire "## Available Tools" section including all subsections):
```markdown
## Available Tools

### Sampling Tools
- generate_listing_pages: ...
- generate_article_pages: ...

### Extraction Tools
- extract_listing_page: ...
- extract_article_page: ...

### Aggregation Tool
- aggregate_selectors: ...

### Memory Tools
- memory_read: ...
- memory_write: ...
- memory_search: ...
```
Keep: Line 1-4 (intro) and line 26+ (## Workflow section and everything after)

**2. `src/prompts/templates/agents/main_agent.md.j2`**
Remove the "## Available Tools" section (approximately lines 55-65):
```markdown
## Available Tools

**Agents:** run_discovery_agent, run_selector_agent, ...
**Generators:** generate_plan_md, generate_test_md
**Memory:** memory_read, memory_write, memory_list
**Files:** file_create, file_replace
```
Keep: All workflow and strategy sections

**3. `src/prompts/templates/agents/data_prep_agent.md.j2`**
Remove lines 37-68 (the detailed tool descriptions):
```markdown
### batch_fetch_urls
Fetch multiple URLs...

### batch_extract_listings
Extract article URLs...
(etc.)
```
Keep: Lines 1-36 (intro, context, and workflow steps) and line 69+ (remaining sections)

## Files to Modify

| File | Action |
|------|--------|
| `src/tools/base.py` | Add category, getter methods |
| `src/tools/memory.py` | Add `category = "memory"` |
| `src/tools/selector_sampling.py` | Add `category = "sampling"` |
| `src/tools/selector_extraction.py` | Add categories |
| `src/tools/extraction.py` | Add categories |
| `src/tools/file.py` | Add `category = "file"` |
| `src/agents/base.py` | Add `_build_tools_section()` |
| `src/contracts/templates/tools_section.md.j2` | Create |
| `src/contracts/templates/tool_item_standard.md.j2` | Create |
| `src/contracts/templates/tool_item_detailed.md.j2` | Create |
| `src/prompts/templates/agents/selector_agent.md.j2` | Remove tools section |
| `src/prompts/templates/agents/main_agent.md.j2` | Remove tools section |
| `src/prompts/templates/agents/data_prep_agent.md.j2` | Remove tools section |

## Migration Strategy

1. **Non-breaking first**: Add all new code without changing existing prompts
2. **Test per-agent**: Enable for one agent, compare output, verify functionality
3. **Gradual migration**: Remove hardcoded sections one agent at a time
4. **Cleanup**: Add tests, documentation

## Testing & Verification

**Unit Tests to Add (in `tests/agents/test_base_agent_tools_section.py`):**

```python
def test_build_tools_section_empty():
    """Returns empty string when no tools."""
    agent = BaseAgent(llm=mock_llm, tools=[])
    assert agent._build_tools_section() == ""

def test_build_tools_section_categorized():
    """Tools grouped by category alphabetically."""
    tools = [
        MockTool(name="a_tool", category="zebra"),
        MockTool(name="b_tool", category="alpha"),
    ]
    agent = BaseAgent(llm=mock_llm, tools=tools)
    section = agent._build_tools_section()
    assert "### Alpha Tools" in section
    assert "### Zebra Tools" in section
    # Alpha should come before Zebra
    assert section.index("Alpha") < section.index("Zebra")

def test_build_tools_section_excludes_agent_tools():
    """AgentTools excluded from tools section."""
    # ... test with mixed tools and AgentTools
```

**Manual Verification:**
1. Run agent and check logs for generated prompt
2. Compare auto-generated tools section with previous hardcoded one
3. Verify all tools are listed with correct categories
4. Test that agents can still call tools correctly

## Reference: Existing Sub-Agents Pattern

**Template location**: `src/contracts/templates/sub_agents_section.md.j2`

**BaseAgent method**:
```python
def _build_sub_agents_section(self) -> str:
    if not self.agent_tools:
        return ""
    from ..contracts.template_renderer import render_template
    return render_template(
        "sub_agents_section.md.j2",
        agent_tools=self.agent_tools,
    )
```

**Integration in _build_final_prompt()**:
```python
prompt_parts = [self.system_prompt]
# Add tools section (NEW)
tools_section = self._build_tools_section()
if tools_section:
    prompt_parts.append(tools_section)
# Add sub-agents section (existing)
sub_agents_section = self._build_sub_agents_section()
if sub_agents_section:
    prompt_parts.append(sub_agents_section)
```
