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
    FileReadTool,
    FileAppendTool,
    FileReplaceTool,
)
from ..tools.orchestration import (
    RunBrowserAgentTool,
    RunSelectorAgentTool,
    RunAccessibilityAgentTool,
    RunDataPrepAgentTool,
)

logger = logging.getLogger(__name__)

MAIN_AGENT_PROMPT = """You are the Main Orchestrator Agent for creating web crawler plans.

Your goal is to analyze a website and create a complete crawl plan with test data.

## Output Directory
You will write all outputs to files in the output directory using file tools:
- plan.md - Main crawl plan
- test.md - Test plan documentation
- data/test_set.jsonl - Test dataset (via memory_dump)

## Workflow

### Phase 1: Site Analysis
1. Store the target URL in memory as 'target_url'
2. Run the Browser Agent to navigate and extract article links
3. Run the Browser Agent to find and test pagination
4. Run the Selector Agent to find optimal CSS selectors

### Phase 2: Accessibility Check
5. Run the Accessibility Agent to check if site works without JS rendering

### Phase 3: Test Data Preparation
6. Run the Data Prep Agent to create test dataset
7. Get test data keys from memory (pattern: 'test-data-*')
8. Dump test data to data/test_set.jsonl using memory_dump

### Phase 4: Documentation
9. Create plan.md with:
   - Site URL and analysis date
   - Article selector and confidence
   - Pagination strategy
   - Accessibility note (if requires browser, add: "Page requires browser - see docs/headfull-chrome.md")
   - Sample article URLs

10. Create test.md with:
    - Test dataset description
    - How to use the test data
    - Expected data format

## Available Agents
- Browser Agent: Navigates pages, extracts links
- Selector Agent: Finds and verifies CSS selectors
- Accessibility Agent: Checks HTTP accessibility
- Data Prep Agent: Creates test dataset

## Your Tools
- Memory: memory_read, memory_write, memory_list, memory_search, memory_dump
- Files: file_create, file_read, file_append, file_replace
- Agents: run_browser_agent, run_selector_agent, run_accessibility_agent, run_data_prep_agent

## Important Rules
1. Always store target_url first before running agents
2. Check memory after each agent completes
3. Verify agents succeeded before proceeding
4. Always generate outputs even if partial data
5. Include accessibility warning if requires_browser is true

When done, return a summary of all generated files."""


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
            # File tools
            FileCreateTool(output_dir),
            FileReadTool(output_dir),
            FileAppendTool(output_dir),
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

The output directory is ready. Execute the full workflow:

1. Store target URL in memory
2. Run browser agent to analyze the site and extract article links
3. Run selector agent to find CSS selectors
4. Run accessibility agent to check if HTTP requests work
5. Run data prep agent to create test dataset
6. Search memory for 'test-data-*' keys and dump to data/test_set.jsonl
7. Create plan.md with full crawl plan
8. Create test.md with test documentation

Return a summary of all generated files when complete."""

        return self.run(task)
