# Extraction Refactor Implementation Plan

## Problem Statement
Content extraction only returns the first paragraph instead of all text from the matched container. Selectors are discovered by the selector agent but never executed in Python code - they're passed as text hints to the LLM which interprets "extract content" as "get first paragraph".

## Solution Architecture

### Current Flow (Broken)
```
HTML (150KB) + selector hints → LLM → extracts first paragraph only
```

### Target Flow (Fixed)
```
HTML → BeautifulSoup.select(selector) → element.get_text() → LLM → formats/cleans
```

## Implementation Tasks

### Task 1: Create Selector Execution Utility
**File:** `src/utils/selector_executor.py`

Create a utility class that applies CSS selectors to HTML using BeautifulSoup:
- `execute_selector(html: str, selector: str) -> Optional[str]` - Apply single selector, return text
- `execute_selector_chain(html: str, selector_chain: List[Dict]) -> Optional[str]` - Try selectors in order, return first match
- `execute_all_selectors(html: str, detail_selectors: Dict[str, List[Dict]]) -> Dict[str, str]` - Execute all field selectors, return field→text mapping
- Use `element.get_text(separator=' ', strip=True)` for text extraction
- Handle fallback selectors in chain (first in chain = highest priority)

### Task 2: Modify RunExtractionAgentTool.execute()
**File:** `src/tools/extraction.py` (lines 135-183)

Changes:
1. Import and use SelectorExecutor utility
2. After reading HTML and detail_selectors from memory:
   - Call `SelectorExecutor.execute_all_selectors(html, detail_selectors)`
   - Get pre-extracted text for each field
3. Pass pre-extracted text to LLM instead of raw HTML
4. LLM task changes from "find and extract" to "format, clean, and validate"

### Task 3: Update Extraction Prompt Template
**File:** `src/prompts/templates/article_extraction.md.j2`

Changes:
1. Remove selector hints section (selectors already applied)
2. Change task description from "extract from HTML" to "format and validate pre-extracted text"
3. Input format changes from HTML to structured pre-extracted fields
4. LLM validates content, fixes formatting issues, handles edge cases

New prompt structure:
```
You are a content formatter. The following text was extracted from a web page.
Your task is to clean, format, and structure the extracted content.

PRE-EXTRACTED FIELDS:
{{ pre_extracted_fields }}

FORMAT as JSON matching this structure:
{{ json_example }}
```

### Task 4: Update _build_extraction_prompt()
**File:** `src/tools/extraction.py` (lines 185-242)

Changes:
1. Accept `pre_extracted_fields: Dict[str, str]` instead of `detail_selectors`
2. Remove selector hints generation logic
3. Format pre-extracted text for LLM prompt
4. Keep JSON example generation for output structure guidance

### Task 5: Update Data Prep Agent Input Contract
**File:** `src/contracts/schemas/data_prep_agent/input.schema.json`

Add required properties for selector data:
```json
{
  "listing_selectors": {
    "type": "object",
    "description": "Complete listing selectors from Selector Agent including listing_container and article_link chains",
    "properties": {
      "listing_container": { "type": "array", "$ref": "#/definitions/selector_chain" },
      "article_link": { "type": "array", "$ref": "#/definitions/selector_chain" }
    },
    "required": ["listing_container", "article_link"]
  },
  "detail_selectors": {
    "type": "object",
    "description": "Complete detail selectors from Selector Agent for all article fields (title, content, date, authors, etc.)",
    "additionalProperties": { "type": "array", "$ref": "#/definitions/selector_chain" }
  }
}
```

### Task 6: Update BatchExtractArticlesTool Input Contract
**File:** `src/contracts/schemas/tools/batch_extract_articles.schema.json`

Create/update schema with:
```json
{
  "html_key_prefix": {
    "type": "string",
    "description": "Memory key prefix for HTML content. Tool searches for '{prefix}-*' keys"
  },
  "output_key_prefix": {
    "type": "string",
    "description": "Memory key prefix for extraction results. Results stored as '{prefix}-1', '{prefix}-2', etc."
  },
  "detail_selectors": {
    "type": "object",
    "description": "Complete detail selectors object from Selector Agent. Each field maps to a selector chain array.",
    "additionalProperties": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "selector": { "type": "string" },
          "success_rate": { "type": "number" }
        },
        "required": ["selector"]
      }
    }
  }
}
```

### Task 7: Update BatchExtractListingsTool Input Contract
**File:** `src/contracts/schemas/tools/batch_extract_listings.schema.json`

Create/update schema similar to articles tool but for listing extraction.

### Task 8: Update Tool Classes to Accept Selectors as Parameters
**Files:** `src/tools/extraction.py`

Modify tool execute() methods:
1. `BatchExtractArticlesTool.execute()` - Accept `detail_selectors` parameter instead of reading from memory
2. `BatchExtractListingsTool.execute()` - Accept `listing_selectors` parameter
3. `RunExtractionAgentTool.execute()` - Accept `detail_selectors` parameter
4. Pass selectors down the call chain

### Task 9: Update Main Agent Prompt
**File:** `src/prompts/agents/main.md.j2` or related agent prompt

Add instructions about selector passing:
- Emphasize that ALL selectors from Selector Agent must be passed to Data Prep Agent
- Document the selector chain format
- Explain that selectors are now applied in code, not by LLM interpretation

### Task 10: Update RunListingExtractionAgentTool
**File:** `src/tools/extraction.py` (lines 295-399)

Apply same changes as article extraction:
1. Use SelectorExecutor for listing extraction
2. Apply listing_container_selector in code
3. Pass pre-extracted container content to LLM

### Task 11: Add Tests for Selector Executor
**File:** `tests/test_selector_executor.py`

Test cases:
- Single selector execution
- Selector chain with fallbacks
- Missing element handling
- Complex nested structures
- Text extraction with separator

### Task 12: Add Integration Tests
**File:** `tests/test_extraction_integration.py`

Test full extraction flow:
- HTML input → selector execution → LLM formatting → structured output
- Verify full content extracted (not just first paragraph)
- Test selector chain fallback behavior

### Task 13: Update Existing Tests
**Files:** `tests/test_extraction.py`, `tests/test_data_prep_agent.py`

Update tests to work with new selector passing pattern and pre-extraction flow.

## File Change Summary

| File | Action | Description |
|------|--------|-------------|
| `src/utils/selector_executor.py` | CREATE | New utility for CSS selector execution |
| `src/tools/extraction.py` | MODIFY | Use selector executor, accept selectors as params |
| `src/prompts/templates/article_extraction.md.j2` | MODIFY | Change from HTML extraction to text formatting |
| `src/contracts/schemas/data_prep_agent/input.schema.json` | MODIFY | Add selector requirements |
| `src/contracts/schemas/tools/batch_extract_articles.schema.json` | CREATE | Tool input contract |
| `src/contracts/schemas/tools/batch_extract_listings.schema.json` | CREATE | Tool input contract |
| `src/prompts/agents/main.md.j2` | MODIFY | Add selector passing instructions |
| `tests/test_selector_executor.py` | CREATE | Unit tests for selector executor |
| `tests/test_extraction_integration.py` | CREATE | Integration tests |
| `tests/test_extraction.py` | MODIFY | Update for new flow |

## Benefits
1. **Deterministic selector application** - No LLM interpretation variance
2. **Smaller LLM input** - Pre-extracted text instead of 150KB HTML
3. **Complete content capture** - All text from container, not just first paragraph
4. **Faster processing** - Less LLM context = faster inference
5. **Lower cost** - Reduced token usage
6. **More reliable** - Python selector execution is predictable
