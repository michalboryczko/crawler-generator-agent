"""Main Agent for orchestrating the crawl plan creation workflow."""
import logging
from pathlib import Path
from typing import Any

from .base import BaseAgent
from .browser_agent import BrowserAgent
from .selector_agent import SelectorAgent
from .accessibility_agent import AccessibilityAgent
from .data_prep_agent import DataPrepAgent
from ..core.llm import LLMClient
from ..core.browser import BrowserSession
from ..tools.memory import (
    MemoryStore,
    MemoryReadTool,
    MemoryWriteTool,
    MemoryListTool,
    MemorySearchTool,
    MemoryDumpTool,
)
from ..tools.file import (
    FileCreateTool,
    FileReplaceTool,
)
from ..tools.plan_generator import (
    GeneratePlanTool,
    GenerateTestPlanTool,
)
from ..tools.orchestration import (
    RunBrowserAgentTool,
    RunSelectorAgentTool,
    RunAccessibilityAgentTool,
    RunDataPrepAgentTool,
)

logger = logging.getLogger(__name__)

MAIN_AGENT_PROMPT = """You are the Main Orchestrator Agent for creating web crawler plans.

Your goal is to analyze a website and create a complete crawl plan with comprehensive test data.

## Output Files
- plan.md - Comprehensive crawl configuration (from generate_plan_md)
- test.md - Test dataset documentation (from generate_test_md)
- data/test_set.jsonl - Test entries for both listing and article pages

## Workflow - EXECUTE IN ORDER

### Phase 1: Site Analysis
1. Store target URL: memory_write("target_url", url)
2. Run browser agent: "Navigate to {url}, extract article links, find pagination, determine max pages"
   - Stores: extracted_articles, pagination_type, pagination_selector, pagination_max_pages

### Phase 2: Selector Discovery
3. Run selector agent: "Find CSS selectors for articles and detail page fields"
   - Stores: article_selector, article_selector_confidence, detail_selectors, listing_selectors

### Phase 3: Accessibility Check
4. Run accessibility agent: "Check if site works without JavaScript"
   - Stores: accessibility_result (includes requires_browser, listing_accessible, articles_accessible)

### Phase 4: Test Data Preparation - CRITICAL
5. Run data prep agent: "Create test dataset with 5+ listing pages and 20+ article pages"
   - Agent fetches listing pages from different pagination positions
   - Agent extracts article URLs from listings
   - Agent fetches article pages randomly selected across listings
   - Stores: test-data-listing-1..N and test-data-article-1..N

   Listing entry: {"type": "listing", "url": "...", "given": "<HTML>", "expected": {"article_urls": [...], ...}}
   Article entry: {"type": "article", "url": "...", "given": "<HTML>", "expected": {"title": "...", ...}}

### Phase 5: Generate Output Files
6. Call generate_plan_md -> returns comprehensive plan markdown
7. Call file_create with path="plan.md" and the plan content
8. Call generate_test_md -> returns test documentation (includes both listing and article counts)
9. Call file_create with path="test.md" and the test content

### Phase 6: Export Test Data
10. Call memory_search with pattern="test-data-listing-*" to get listing keys
11. Call memory_search with pattern="test-data-article-*" to get article keys
12. Combine both key lists
13. Call memory_dump with ALL keys and filename="data/test_set.jsonl"

## Available Tools
- Agents: run_browser_agent, run_selector_agent, run_accessibility_agent, run_data_prep_agent
- Generators: generate_plan_md, generate_test_md
- Memory: memory_read, memory_write, memory_list, memory_search, memory_dump
- Files: file_create, file_replace

## Rules
1. Run agents sequentially - each depends on previous results
2. ALWAYS check agent success before proceeding
3. Data prep agent should create 25+ test entries (5 listings + 20 articles)
4. Export BOTH listing and article test entries to JSONL

## CRITICAL - DO NOT SKIP ANY PHASE
You MUST call ALL four agents in order:
1. run_browser_agent - REQUIRED
2. run_selector_agent - REQUIRED
3. run_accessibility_agent - REQUIRED
4. run_data_prep_agent - REQUIRED (this fetches additional pages for test data)

Do NOT skip the data prep agent. It is essential for creating the test dataset.
The data prep agent will navigate the browser to multiple pages - you will see page changes."""


class MainAgent(BaseAgent):
    """Main orchestrator agent that coordinates all sub-agents."""

    name = "main_agent"
    system_prompt = MAIN_AGENT_PROMPT

    def __init__(
        self,
        llm: LLMClient,
        browser_session: BrowserSession,
        output_dir: Path,
        memory_store: MemoryStore | None = None
    ):
        self.memory_store = memory_store or MemoryStore()
        self.browser_session = browser_session
        self.output_dir = output_dir

        # Create sub-agents
        self.browser_agent = BrowserAgent(llm, browser_session, self.memory_store)
        self.selector_agent = SelectorAgent(llm, browser_session, self.memory_store)
        self.accessibility_agent = AccessibilityAgent(llm, self.memory_store)
        self.data_prep_agent = DataPrepAgent(llm, browser_session, self.memory_store)

        tools = [
            # Memory tools
            MemoryReadTool(self.memory_store),
            MemoryWriteTool(self.memory_store),
            MemoryListTool(self.memory_store),
            MemorySearchTool(self.memory_store),
            MemoryDumpTool(self.memory_store, output_dir),
            # Plan generators (structured output from memory)
            GeneratePlanTool(self.memory_store),
            GenerateTestPlanTool(self.memory_store),
            # File tools
            FileCreateTool(output_dir),
            FileReplaceTool(output_dir),
            # Agent orchestration tools
            RunBrowserAgentTool(self.browser_agent),
            RunSelectorAgentTool(self.selector_agent),
            RunAccessibilityAgentTool(self.accessibility_agent),
            RunDataPrepAgentTool(self.data_prep_agent),
        ]

        super().__init__(llm, tools)

    def create_crawl_plan(self, url: str) -> dict[str, Any]:
        """High-level method to create a complete crawl plan for a URL."""
        task = f"""Create a complete crawl plan for: {url}

Execute the full workflow:
1. Store '{url}' in memory as 'target_url'
2. Run browser agent to extract article links, pagination info, and max pages
3. Run selector agent to find CSS selectors for listings and detail pages
4. Run accessibility agent to check HTTP accessibility
5. Run data prep agent to create test dataset with 5+ listing pages and 20+ article pages
6. Use generate_plan_md to create comprehensive plan, then file_create for plan.md
7. Use generate_test_md to create test documentation, then file_create for test.md
8. Search for BOTH 'test-data-listing-*' AND 'test-data-article-*' keys
9. Dump ALL test entries to data/test_set.jsonl

Return summary with counts when complete."""

        return self.run(task)
