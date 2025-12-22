# Plan Generator Refactoring - Implementation Plan

## Executive Summary

This document outlines the detailed implementation plan for refactoring the Plan Generator from a hardcoded tool (`GeneratePlanTool`) into an intelligent agent-based architecture (`PlanGeneratorAgent`). The refactoring transforms ~870 lines of hardcoded string generation into a modular, LLM-powered system with quality validation.

**Source Task Document:** `docs/tasks/plan_generator_refactor.md`

---

## 1. Problem Analysis

### 1.1 Current Implementation Issues

**File:** `src/tools/plan_generator.py` (874 lines)

| Issue | Impact | Location |
|-------|--------|----------|
| Hardcoded text generation | No adaptability to different site structures | Lines 89-653 |
| Direct memory key coupling | Fails if keys missing; 15+ memory keys | Lines 36-46 |
| No LLM involvement | Cannot reason about data quality | Entire file |
| No output validation | Plans can be incorrect/incomplete | No validation exists |
| Rigid structure | Cannot handle edge cases | Template methods |

### 1.2 Current Data Flow

```
MainAgent
    ├─→ DiscoveryAgent (outputs to memory)
    ├─→ SelectorAgent (outputs to memory)
    ├─→ AccessibilityAgent (outputs to memory)
    ├─→ DataPrepAgent (outputs to memory)
    └─→ GeneratePlanTool (reads memory keys directly)
              │
              └─→ Hardcoded markdown generation
```

### 1.3 Target Data Flow

```
MainAgent
    ├─→ DiscoveryAgent → AgentResult
    ├─→ SelectorAgent → AgentResult
    ├─→ AccessibilityAgent → AgentResult
    ├─→ DataPrepAgent → AgentResult
    │
    └─→ PlanGeneratorAgent (via AgentTool)
              │
              ├─→ collected_information (aggregated outputs)
              ├─→ plan_draft_provider_tool (example structure)
              ├─→ prepare_crawler_configuration (dynamic config)
              ├─→ supervisor_tool (quality validation)
              │
              └─→ Intelligent plan.md + crawler config
```

---

## 2. Architecture Design

### 2.1 Input Contract Schema

**File:** `src/contracts/schemas/plan_generator_agent/input.schema.json`

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "plan_generator_agent_input",
  "title": "PlanGeneratorAgent Input Contract",
  "type": "object",
  "required": ["target_url", "task_name", "collected_information"],
  "properties": {
    "target_url": {
      "type": "string",
      "format": "uri",
      "description": "The target URL for which to generate the crawl plan"
    },
    "task_name": {
      "type": "string",
      "description": "Name/identifier for this crawl task"
    },
    "collected_information": {
      "type": "array",
      "description": "Aggregated outputs from other agents",
      "items": {
        "type": "object",
        "required": ["agent_name", "output", "description"],
        "properties": {
          "agent_name": {
            "type": "string",
            "enum": ["discovery_agent", "selector_agent", "accessibility_agent", "data_prep_agent"]
          },
          "output": {
            "type": "object",
            "description": "Full validated output from the agent"
          },
          "description": {
            "type": "string",
            "description": "Human-readable summary of what this agent provides"
          }
        }
      }
    },
    "output_directory": {
      "type": "string",
      "description": "Directory path where plan files should be saved"
    }
  }
}
```

### 2.2 Output Contract Schema

**File:** `src/contracts/schemas/plan_generator_agent/output.schema.json`

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "plan_generator_agent_output",
  "title": "PlanGeneratorAgent Output Contract",
  "type": "object",
  "required": ["status", "plan_file_path", "crawler_config"],
  "properties": {
    "status": {
      "type": "string",
      "enum": ["success", "partial_success", "failed"],
      "description": "Overall status of plan generation"
    },
    "plan_file_path": {
      "type": "string",
      "description": "Path to the generated plan.md file"
    },
    "crawler_config": {
      "$ref": "#/$defs/crawlerConfig"
    },
    "validation_result": {
      "type": "object",
      "properties": {
        "passed": { "type": "boolean" },
        "feedback": { "type": "string" }
      }
    },
    "agent_response_content": {
      "type": "string",
      "description": "Human-readable summary of the generation process"
    }
  },
  "$defs": {
    "crawlerConfig": {
      "type": "object",
      "required": ["start_url", "listing", "detail", "pagination", "request"],
      "properties": {
        "start_url": { "type": "string", "format": "uri" },
        "listing": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["property", "selectors"],
            "properties": {
              "property": { "type": "string" },
              "selectors": { "type": "array", "items": { "type": "string" } }
            }
          }
        },
        "detail": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["property", "selectors"],
            "properties": {
              "property": { "type": "string" },
              "selectors": { "type": "array", "items": { "type": "string" } }
            }
          }
        },
        "pagination": {
          "type": "object",
          "properties": {
            "enabled": { "type": "boolean" },
            "type": { "type": "string" },
            "selector": { "type": "string" },
            "max_pages": { "type": "integer" }
          }
        },
        "request": {
          "type": "object",
          "properties": {
            "requires_browser": { "type": "boolean" },
            "wait_between_requests": { "type": "integer" },
            "max_concurrent_requests": { "type": "integer" }
          }
        }
      }
    }
  }
}
```

### 2.3 New Tools Design

#### 2.3.1 plan_draft_provider_tool

**Purpose:** Provides example plan structure to guide LLM generation

**File:** `src/tools/plan_draft_provider.py`

```python
class PlanDraftProviderTool(BaseTool):
    name = "get_plan_draft"
    description = """Returns an example crawl plan structure to guide plan generation.
    Use this to understand the expected format and sections of a crawl plan."""

    def execute(self, **kwargs) -> dict[str, Any]:
        # Returns markdown template structure with section explanations
```

**Schema:** `src/contracts/schemas/tools/plan_draft_provider.schema.json`
- No input parameters required
- Returns example plan markdown structure

#### 2.3.2 prepare_crawler_configuration

**Purpose:** Generates dynamic crawler JSON configuration from collected selectors

**File:** `src/tools/crawler_config_generator.py`

```python
class PrepareCrawlerConfigurationTool(BaseTool):
    name = "prepare_crawler_configuration"
    description = """Generate crawler configuration JSON from collected selector data.
    Takes listing and detail selectors and produces a structured config."""

    def execute(
        self,
        start_url: str,
        listing_selectors: list[dict],
        detail_selectors: list[dict],
        pagination_config: dict | None = None,
        request_config: dict | None = None,
    ) -> dict[str, Any]:
        # Builds dynamic config from provided data
```

**Schema:** `src/contracts/schemas/tools/prepare_crawler_configuration.schema.json`

```json
{
  "type": "object",
  "required": ["start_url", "listing_selectors", "detail_selectors"],
  "properties": {
    "start_url": { "type": "string", "format": "uri" },
    "listing_selectors": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["property", "selectors"],
        "properties": {
          "property": { "type": "string" },
          "selectors": { "type": "array", "items": { "type": "string" } }
        }
      }
    },
    "detail_selectors": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["property", "selectors"],
        "properties": {
          "property": { "type": "string" },
          "selectors": { "type": "array", "items": { "type": "string" } }
        }
      }
    },
    "pagination_config": { "type": "object" },
    "request_config": { "type": "object" }
  }
}
```

#### 2.3.3 supervisor_tool

**Purpose:** LLM-based quality validation of generated output

**File:** `src/tools/supervisor.py`

```python
class SupervisorTool(BaseTool):
    name = "supervisor_validate"
    description = """Validates generated output quality using LLM analysis.
    Reviews task completion, correctness, and completeness."""

    def __init__(self, llm: LLMClient):
        self._llm = llm

    def execute(
        self,
        given_task: str,
        input_data: dict,
        output_candidate: str,
        context_summary: str | None = None,
    ) -> dict[str, Any]:
        # Uses LLM to validate output quality
        # Returns: { "valid": bool, "feedback": str, "issues": list }
```

**Schema:** `src/contracts/schemas/tools/supervisor.schema.json`

```json
{
  "type": "object",
  "required": ["given_task", "input_data", "output_candidate"],
  "properties": {
    "given_task": {
      "type": "string",
      "description": "Description of the task that was performed"
    },
    "input_data": {
      "type": "object",
      "description": "The input data provided to the agent"
    },
    "output_candidate": {
      "type": "string",
      "description": "The generated output to validate"
    },
    "context_summary": {
      "type": "string",
      "description": "Optional summary of available context"
    }
  }
}
```

---

## 3. Implementation Phases

### Phase 1: Foundation - Contract Schemas (Priority: Critical)

**Duration:** 1-2 hours
**Dependencies:** None

#### Tasks:
1. Create `src/contracts/schemas/plan_generator_agent/` directory
2. Create `input.schema.json` (as specified in 2.1)
3. Create `output.schema.json` (as specified in 2.2)
4. Update `config/agents.yaml` with plan_generator config:
   ```yaml
   plan_generator:
     output_contract_schema_path: "src/contracts/schemas/plan_generator_agent/output.schema.json"
     input_contract_schema_path: "src/contracts/schemas/plan_generator_agent/input.schema.json"
   ```

#### Validation:
- Run schema validator on new schemas
- Test schema loading via `AgentsConfig.get_schema_paths("plan_generator")`

---

### Phase 2: Supporting Tools (Priority: High)

**Duration:** 2-3 hours
**Dependencies:** Phase 1

#### Task 2.1: plan_draft_provider_tool
1. Create `src/tools/plan_draft_provider.py`
2. Create `src/contracts/schemas/tools/plan_draft_provider.schema.json`
3. Create test: `tests/tools/test_plan_draft_provider.py`

#### Task 2.2: prepare_crawler_configuration
1. Create `src/tools/crawler_config_generator.py`
2. Create `src/contracts/schemas/tools/prepare_crawler_configuration.schema.json`
3. Create test: `tests/tools/test_crawler_config_generator.py`

#### Validation:
- Unit tests pass for each tool
- Schema validation for tool inputs/outputs

---

### Phase 3: Supervisor Tool (Priority: High)

**Duration:** 2-3 hours
**Dependencies:** Phase 1

#### Tasks:
1. Create `src/tools/supervisor.py` with `SupervisorTool` class
2. Create `src/contracts/schemas/tools/supervisor.schema.json`
3. Create `src/prompts/templates/tools/supervisor_system.md.j2`:
   ```markdown
   You are a quality supervisor reviewing generated outputs.

   Your task is to verify that the output:
   1. Addresses the given task completely
   2. Is consistent with the input data
   3. Contains no logical errors or contradictions
   4. Follows expected format and structure

   Provide specific feedback on any issues found.
   ```
4. Create `src/prompts/templates/tools/supervisor_user.md.j2`:
   ```markdown
   ## Task Description
   {{ given_task }}

   ## Input Data Provided
   ```json
   {{ input_data | tojson(indent=2) }}
   ```

   ## Generated Output to Validate
   {{ output_candidate }}

   {% if context_summary %}
   ## Additional Context
   {{ context_summary }}
   {% endif %}

   Please analyze the output and provide validation feedback.
   ```
5. Create test: `tests/tools/test_supervisor.py`

#### Validation:
- Unit tests with mocked LLM responses
- Integration test with real validation scenario

---

### Phase 4: PlanGeneratorAgent (Priority: Critical)

**Duration:** 3-4 hours
**Dependencies:** Phases 1, 2, 3

#### Task 4.1: Agent Implementation
1. Create `src/agents/plan_generator_agent.py`:
   ```python
   class PlanGeneratorAgent(BaseAgent):
       name = "plan_generator_agent"
       description = "Generates comprehensive crawl plans from collected agent outputs"
       system_prompt = get_prompt_provider().get_agent_prompt("plan_generator")

       def __init__(
           self,
           llm: LLMClient | LLMClientFactory,
           output_dir: Path,
           memory_service: MemoryService | None = None,
       ):
           tools = [
               PlanDraftProviderTool(),
               PrepareCrawlerConfigurationTool(),
               SupervisorTool(llm),
               FileCreateTool(output_dir),
               MemoryWriteTool(memory_service),
           ]
           super().__init__(llm, tools, memory_service=memory_service)
   ```

#### Task 4.2: Prompt Templates
1. Create `src/prompts/templates/agents/plan_generator.md.j2` (system prompt):
   ```markdown
   You are the Plan Generator Agent, responsible for creating comprehensive
   crawl plans based on data collected by other specialized agents.

   ## Your Responsibilities
   1. Analyze collected information from discovery, selector, and accessibility agents
   2. Generate a well-structured crawl plan document (plan.md)
   3. Create a dynamic crawler configuration JSON
   4. Validate your output quality using the supervisor tool

   ## Available Tools
   - get_plan_draft: Get example plan structure
   - prepare_crawler_configuration: Generate crawler config JSON
   - supervisor_validate: Validate your generated output
   - file_create: Save the plan to disk

   ## Workflow
   1. First, use get_plan_draft to understand expected format
   2. Analyze all collected_information entries
   3. Generate plan markdown with all sections
   4. Use prepare_crawler_configuration for the config JSON
   5. Use supervisor_validate to verify quality
   6. Save plan to file and return path
   ```

2. Create `src/prompts/templates/agents/plan_generator_user.md.j2` (user prompt):
   ```markdown
   # Generate Crawl Plan for {{ target_url }}

   **Task:** {{ task_name }}

   ## Collected Information from Other Agents

   {% for info in collected_information %}
   ### From {{ info.agent_name }}

   **Purpose:** {{ info.description }}

   **Output:**
   ```json
   {{ info.output | tojson(indent=2) }}
   ```

   {% endfor %}

   ## Instructions

   1. Analyze all collected information above
   2. Generate a comprehensive crawl plan following the draft structure
   3. Include the crawler configuration JSON
   4. Validate your output with the supervisor tool
   5. Save the plan to: {{ output_directory }}/plan.md
   6. Return the file path and summary
   ```

#### Task 4.3: Tests
1. Create `tests/agents/test_plan_generator_agent.py`:
   - Test initialization with tools
   - Test run() with mocked collected_information
   - Test contract validation
   - Test file creation

#### Validation:
- All unit tests pass
- Agent can be initialized and run
- Output conforms to contract schema

---

### Phase 5: MainAgent Integration (Priority: High)

**Duration:** 2-3 hours
**Dependencies:** Phase 4

#### Tasks:
1. Modify `src/agents/main_agent.py`:
   - Add PlanGeneratorAgent import
   - Create PlanGeneratorAgent instance
   - Add AgentTool wrapper for plan_generator
   - Modify workflow to aggregate sub-agent outputs
   - Remove GeneratePlanTool usage

2. Update workflow in `create_crawl_plan()`:
   ```python
   # After running all sub-agents, aggregate outputs:
   collected_information = [
       {
           "agent_name": "discovery_agent",
           "output": discovery_result.data,
           "description": "Site structure, pagination, content areas discovered"
       },
       {
           "agent_name": "selector_agent",
           "output": selector_result.data,
           "description": "Verified CSS selectors for listings and articles"
       },
       # ... etc
   ]

   # Call plan generator agent via tool
   plan_result = run_plan_generator_agent(
       target_url=url,
       task_name=task_name,
       collected_information=collected_information,
       output_directory=str(self.output_dir)
   )
   ```

3. Update `src/prompts/templates/agents/crawl_plan_task.md.j2` to reflect new workflow

#### Validation:
- Integration test: Full workflow with mocked sub-agents
- End-to-end test: Complete plan generation

---

### Phase 6: Cleanup (Priority: Medium)

**Duration:** 1-2 hours
**Dependencies:** Phase 5 complete and validated

#### Tasks:
1. Remove `GeneratePlanTool` class from `src/tools/plan_generator.py`
2. Keep `GenerateTestPlanTool` (may need similar refactor later)
3. Remove unused memory key reads from main workflow
4. Update any remaining imports/references
5. Update documentation

#### Validation:
- All tests still pass
- No unused imports/dead code
- Linting passes

---

## 4. File Inventory

### New Files (19 total)

| File | Purpose | Phase |
|------|---------|-------|
| `src/contracts/schemas/plan_generator_agent/input.schema.json` | Input contract | 1 |
| `src/contracts/schemas/plan_generator_agent/output.schema.json` | Output contract | 1 |
| `src/tools/plan_draft_provider.py` | Draft example tool | 2 |
| `src/contracts/schemas/tools/plan_draft_provider.schema.json` | Tool schema | 2 |
| `src/tools/crawler_config_generator.py` | Config generator | 2 |
| `src/contracts/schemas/tools/prepare_crawler_configuration.schema.json` | Tool schema | 2 |
| `src/tools/supervisor.py` | LLM validation tool | 3 |
| `src/contracts/schemas/tools/supervisor.schema.json` | Tool schema | 3 |
| `src/prompts/templates/tools/supervisor_system.md.j2` | Supervisor system prompt | 3 |
| `src/prompts/templates/tools/supervisor_user.md.j2` | Supervisor user prompt | 3 |
| `src/agents/plan_generator_agent.py` | Main agent | 4 |
| `src/prompts/templates/agents/plan_generator.md.j2` | Agent system prompt | 4 |
| `src/prompts/templates/agents/plan_generator_user.md.j2` | Agent user prompt | 4 |
| `tests/tools/test_plan_draft_provider.py` | Tool tests | 2 |
| `tests/tools/test_crawler_config_generator.py` | Tool tests | 2 |
| `tests/tools/test_supervisor.py` | Tool tests | 3 |
| `tests/agents/test_plan_generator_agent.py` | Agent tests | 4 |
| `tests/integration/test_plan_generator_workflow.py` | Integration tests | 5 |

### Modified Files (4 total)

| File | Changes | Phase |
|------|---------|-------|
| `config/agents.yaml` | Add plan_generator config | 1 |
| `src/agents/main_agent.py` | Integration with new agent | 5 |
| `src/prompts/templates/agents/crawl_plan_task.md.j2` | Update workflow | 5 |
| `src/tools/plan_generator.py` | Remove GeneratePlanTool | 6 |

### Deleted Code

| Item | Location | Phase |
|------|----------|-------|
| `GeneratePlanTool` class | `src/tools/plan_generator.py` lines 21-653 | 6 |

---

## 5. Testing Strategy

### Unit Tests
- Each new tool has dedicated test file
- Mock LLM responses for deterministic testing
- Test contract validation for all schemas

### Integration Tests
- Test PlanGeneratorAgent with mocked sub-agent outputs
- Test MainAgent workflow end-to-end
- Test file creation and content validation

### Contract Tests
- Validate input schema with sample data
- Validate output schema with generated data
- Test schema loading from config

### Manual Testing
- Run full workflow against test URL
- Verify generated plan.md quality
- Verify crawler config correctness

---

## 6. Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| LLM context limits with large collected_information | Plan truncation | Summarize large outputs before passing |
| Supervisor validation loops | Infinite retries | Max retry limit (3) already in BaseAgent |
| Empty collected_information | Failed plan | Handle gracefully with partial plan |
| Schema migration issues | Runtime errors | Extensive schema testing |

---

## 7. Success Criteria

1. **Functional**
   - PlanGeneratorAgent generates valid plan.md
   - Crawler config JSON matches expected structure
   - Supervisor validation catches quality issues

2. **Quality**
   - All tests pass (unit, integration, contract)
   - Code follows existing patterns
   - No regressions in existing functionality

3. **Architecture**
   - Clean separation of concerns
   - Proper contract validation
   - Reusable supervisor tool

---

## Appendix A: Example Generated Plan Structure

```markdown
# Crawl Plan for example.com

Target: **https://example.com/articles**

## 1. Scope & Objectives
...

## 2. Start URLs
...

## 3. Listing Pages
### 3.1 Container selector
### 3.2 Article links
...

## 4. Pagination
...

## 5. Article Detail Pages
...

## 6. Data Model
...

## 7. Crawler Configuration
```json
{
  "start_url": "https://example.com/articles",
  "listing": [...],
  "detail": [...],
  ...
}
```

## 8. Accessibility & Requirements
...

## 9. Sample Articles
...

## 10. Notes
...
```

---

## Appendix B: Task Master Tasks

The following tasks should be created in Task Master for tracking:

```
Task 21: Create PlanGeneratorAgent Input/Output Contract Schemas
Task 22: Implement plan_draft_provider_tool
Task 23: Implement prepare_crawler_configuration tool
Task 24: Implement supervisor_tool with LLM validation
Task 25: Create PlanGeneratorAgent implementation
Task 26: Create prompt templates for PlanGeneratorAgent
Task 27: Integrate PlanGeneratorAgent into MainAgent
Task 28: Cleanup - Remove GeneratePlanTool
Task 29: Add comprehensive tests for new components
Task 30: End-to-end testing and validation
```
