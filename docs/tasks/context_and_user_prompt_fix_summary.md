# Context and User Prompt Fix Summary

This document consolidates all knowledge about the plan generator context handling and user prompt template fixes.

## Problem Statement

The PlanGeneratorAgent is not receiving `collected_information` from the main agent, causing plan generation to fail despite all sub-agent work being completed successfully.

### Evidence

Input received by PlanGeneratorAgent:
```json
{
  "args": {"task": "Generate comprehensive crawl plan"},
  "kwargs": {
    "context": null,
    "expected_outputs": ["plan_file_path", "status", "agent_response_content"],
    "run_identifier": "12c599f6-6eba-43c7-9e0a-746bbd295af2",
    "output_contract_schema": {...}
  }
}
```

**Missing:** `target_url`, `task_name`, `collected_information` - all required by input contract.

---

## Root Cause Analysis

### Issue 1: AgentTool Doesn't Merge Extra Kwargs into Context

**File:** `src/tools/agent_tools/agent_tool.py:100-119`

```python
def execute(self, **kwargs: Any) -> dict[str, Any]:
    task = kwargs["task"]
    context = kwargs.get("context")  # Only looks for explicit "context" key
    # ...
```

**Problem:** Parent agent passes data at the same level as `task`, not nested in `context`. AgentTool ignores these extra kwargs.

**Example of what parent agent sends:**
```python
{
    "task": "Generate Plan",
    "run_identifier": "123",
    "target_url": "https://example.com",      # Ignored!
    "collected_information": [...]             # Ignored!
}
```

### Issue 2: No Input Contract Validation (Critical Gap)

**File:** `src/tools/agent_tools/agent_tool.py:55, 68-71`

The input schema IS loaded:
```python
self._input_schema = load_schema(input_schema_path) if input_schema_path else None
```

But it's ONLY used to append text to the tool description:
```python
if self._input_schema:
    required = self._input_schema.get("required", [])
    if required:
        desc += f"\n\nREQUIRED INPUT (pass via 'context' parameter): {', '.join(required)}"
```

**No actual validation happens in `execute()`!** This is why plan_generator_agent was called with missing `collected_information` - the invalid input was silently accepted.

**This differs from output validation** which has:
- Schema validation
- Error messages returned to agent
- Retry mechanism

Input validation should work the same way - if input is invalid, return an error so the calling agent can retry with correct data.

### Issue 3: User Prompt Template Never Rendered

**File:** `src/agents/base.py:167-178`

```python
messages = [
    {"role": "system", "content": system_content},
    {"role": "user", "content": task},  # Just plain string!
]
```

The template `src/prompts/templates/agents/plan_generator_user.md.j2` exists but is never used. Context is only dumped as JSON into the system prompt via `_inject_context()`.

### Issue 4: Context Injection is Passive

**File:** `src/agents/base.py:410-420`

```python
def _inject_context(self, context: dict[str, Any]) -> str:
    context_str = json.dumps(context, indent=2)
    return f"## Context from Orchestrator\n```json\n{context_str}\n```"
```

Context goes into **system prompt** as raw JSON, not into **user prompt** as formatted markdown.

---

## Required Fixes

### Fix 1: AgentTool Kwargs Merging

**In `AgentTool.execute()`**, merge all extra kwargs (except reserved keys) into context:

```python
def execute(self, **kwargs: Any) -> dict[str, Any]:
    task = kwargs.pop("task")
    run_identifier = kwargs.pop("run_identifier", None)
    expected_outputs = kwargs.pop("expected_outputs", None)
    explicit_context = kwargs.pop("context", None)

    # Merge remaining kwargs into context
    context = explicit_context or {}
    context.update(kwargs)  # target_url, collected_information, etc.

    # Now context contains all the data
    result = self._agent.run(task, context=context, ...)
```

### Fix 2: Input Contract Validation with Retry Support

**In `AgentTool.execute()`**, validate context against input schema and return actionable error:

```python
def execute(self, **kwargs: Any) -> dict[str, Any]:
    # ... merge kwargs into context first ...

    # Validate input contract BEFORE calling agent
    if self._input_schema:
        validation_error = self._validate_input(context)
        if validation_error:
            return validation_error  # Agent can retry with correct input

    # Only proceed if validation passed
    result = self._agent.run(task, context=context, ...)

def _validate_input(self, context: dict[str, Any] | None) -> dict[str, Any] | None:
    """Validate context against input schema. Returns error dict or None if valid."""
    from jsonschema import validate, ValidationError

    if context is None:
        context = {}

    try:
        validate(instance=context, schema=self._input_schema)
        return None  # Valid
    except ValidationError as e:
        # Build detailed error message for calling agent to retry
        required = self._input_schema.get("required", [])
        missing = [f for f in required if f not in context]

        return {
            "success": False,
            "error": "Input contract validation failed",
            "validation_message": e.message,
            "path": list(e.path),
            "required_fields": required,
            "missing_fields": missing,
            "provided_fields": list(context.keys()) if context else [],
            "hint": f"Please provide all required fields: {', '.join(missing)}"
        }
```

**Key:** The error response gives the calling agent enough information to fix the input and retry, similar to output validation.

### Fix 3: Default User Prompt with Context

**Add to `BaseAgent`** a method to build user prompt with context:

```python
def _build_user_prompt(self, task: str, context: dict[str, Any] | None) -> str:
    """Build user prompt with task and context.

    Override in subclasses for custom formatting.
    """
    if not context:
        return task

    from ..prompts.template_renderer import render_template
    return render_template(
        "default_user_prompt.md.j2",
        task=task,
        context=context
    )
```

**Template `default_user_prompt.md.j2`:**
```markdown
{{ task }}

## Context
```json
{{ context | tojson(indent=2) }}
```
```

### Fix 4: PlanGeneratorAgent User Prompt Override

**In `PlanGeneratorAgent`**, override to use specialized template:

```python
class PlanGeneratorAgent(BaseAgent):
    user_prompt_template = "agents/plan_generator_user.md.j2"

    def _build_user_prompt(self, task: str, context: dict[str, Any] | None) -> str:
        if not context or "collected_information" not in context:
            return super()._build_user_prompt(task, context)

        from ..prompts.template_renderer import render_template
        return render_template(
            self.user_prompt_template,
            task=task,
            target_url=context.get("target_url", ""),
            task_name=context.get("task_name", "Generate Crawl Plan"),
            collected_information=context.get("collected_information", [])
        )
```

### Fix 5: Update BaseAgent.run() to Use User Prompt Method

**In `BaseAgent.run()`**, use the new method:

```python
def run(self, task: str, context: dict[str, Any] | None = None, ...) -> AgentResult:
    system_content = self._build_final_prompt(...)
    user_content = self._build_user_prompt(task, context)  # NEW

    messages = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content},  # Was just `task`
    ]
```

---

### Fix 6: Improve Input Schema Descriptions

**File:** `src/contracts/schemas/plan_generator_agent/input.schema.json`

Current `collected_information` description is too brief:
```json
"description": "Aggregated outputs from sub-agents (Discovery, Selector, Accessibility, DataPrep)"
```

Should be more detailed to help LLM understand what's expected:

```json
{
  "collected_information": {
    "type": "array",
    "description": "CRITICAL: Array of outputs from sub-agents that ran before plan generation. Each item contains the complete response from one sub-agent. This is the PRIMARY data source for generating the crawl plan - selectors, pagination info, accessibility requirements, and sample articles all come from here. Must include at least discovery_agent and selector_agent outputs.",
    "minItems": 1,
    "items": {
      "$ref": "#/$defs/agentOutput"
    }
  }
}
```

Also improve `agentOutput` definition:
```json
{
  "agentOutput": {
    "type": "object",
    "description": "Complete output from a sub-agent execution",
    "required": ["agent_name", "output", "description"],
    "properties": {
      "agent_name": {
        "type": "string",
        "description": "Identifier of the source agent",
        "enum": ["discovery_agent", "selector_agent", "accessibility_agent", "data_prep_agent"]
      },
      "output": {
        "type": "object",
        "description": "The COMPLETE response object from the agent, including all fields like selectors, URLs, pagination info, etc. Do not filter or summarize - include everything.",
        "additionalProperties": true
      },
      "description": {
        "type": "string",
        "description": "Brief explanation of what this agent discovered and how it helps plan generation. Example: 'Selector Agent found 5 listing selectors and 8 detail page selectors with 95%+ success rate'"
      }
    }
  }
}
```

---

## Files to Modify

| File | Change |
|------|--------|
| `src/tools/agent_tools/agent_tool.py` | Merge kwargs into context, add input validation with retry |
| `src/agents/base.py` | Add `_build_user_prompt()` method, update `run()` |
| `src/agents/plan_generator_agent.py` | Override `_build_user_prompt()` |
| `src/prompts/templates/default_user_prompt.md.j2` | Create default template |
| `src/contracts/schemas/plan_generator_agent/input.schema.json` | Improve descriptions |

---

## Expected Data Flow After Fix

```
MainAgent calls run_plan_generator_agent with:
  task: "Generate comprehensive crawl plan"
  target_url: "https://example.com"
  collected_information: [{agent_name: "discovery_agent", output: {...}}, ...]

        ↓

AgentTool.execute() merges kwargs into context:
  task: "Generate comprehensive crawl plan"
  context: {
    target_url: "https://example.com",
    collected_information: [...]
  }

        ↓

AgentTool validates context against input.schema.json
  ✓ target_url: present
  ✓ task_name: present (or default)
  ✓ collected_information: present with minItems: 1

        ↓

PlanGeneratorAgent.run(task, context)
  → _build_user_prompt() renders plan_generator_user.md.j2

        ↓

User message becomes formatted markdown:
  # Collected Information for https://example.com
  ## From discovery_agent
  ### Description
  ...
  ### Output
  - **pagination_type**: numbered
  - **article_urls**: [...]
  ---
  ## From selector_agent
  ...
```

---

## Collected Information Format

### Input (JSON from context)
```json
[
  {
    "agent_name": "discovery_agent",
    "description": "Discovered pagination and article URLs",
    "output": {
      "pagination_type": "numbered",
      "max_pages": 10,
      "article_urls": ["url1", "url2"]
    }
  }
]
```

### Output (Rendered Markdown in user prompt)
```markdown
## From discovery_agent

### Description
Discovered pagination and article URLs

### Output
- **pagination_type**: numbered
- **max_pages**: 10
- **article_urls**:
  - url1
  - url2
```

---

## Task Dependencies

```
[1] Improve input schema descriptions
     ↓
[2] AgentTool kwargs merging
     ↓
[3] AgentTool input validation with retry ───┐
     ↓                                       │
[4] BaseAgent._build_user_prompt()           │
     ↓                                       │
[5] PlanGeneratorAgent override              │
     ↓                                       │
[6] Update BaseAgent.run() ←─────────────────┘
     ↓
[7] Integration testing
```

**Parallel work possible:**
- [1] can be done independently
- [2] and [3] must be done together in AgentTool
- [4], [5], [6] can be done together in agents

---

## Input Validation Retry Flow

When main agent calls `run_plan_generator_agent` with missing data:

```
MainAgent: "I'll call run_plan_generator_agent"
    ↓
AgentTool.execute({task: "Generate plan"})  # Missing collected_information!
    ↓
AgentTool._validate_input(context={})
    ↓
Returns error:
{
  "success": false,
  "error": "Input contract validation failed",
  "validation_message": "'collected_information' is a required property",
  "required_fields": ["target_url", "task_name", "collected_information"],
  "missing_fields": ["target_url", "task_name", "collected_information"],
  "provided_fields": [],
  "hint": "Please provide all required fields: target_url, task_name, collected_information"
}
    ↓
MainAgent sees error, retries with correct data:
run_plan_generator_agent(
  task="Generate plan",
  target_url="https://example.com",
  task_name="example_crawl",
  collected_information=[
    {agent_name: "discovery_agent", output: {...}, description: "..."},
    {agent_name: "selector_agent", output: {...}, description: "..."}
  ]
)
    ↓
AgentTool._validate_input() → PASSES
    ↓
PlanGeneratorAgent.run() executes successfully
```

This matches the existing output validation behavior where agents can retry on validation failure.

---

## References

- `docs/tasks/plan_generator_refactor.md` - Original requirements (point 3)
- `docs/tasks/agent_user_context.md` - Detailed implementation spec
- `src/prompts/templates/agents/plan_generator_user.md.j2` - Existing template (unused)
- `src/contracts/schemas/plan_generator_agent/input.schema.json` - Input contract
