"""Main Agent for orchestrating the crawl plan creation workflow."""
import logging
from typing import Any

from .base import BaseAgent
from .browser_agent import BrowserAgent
from .selector_agent import SelectorAgent
from ..core.llm import LLMClient
from ..core.browser import BrowserSession
from ..tools.memory import (
    MemoryStore,
    MemoryReadTool,
    MemoryWriteTool,
    MemoryListTool,
)
from ..tools.orchestration import (
    RunBrowserAgentTool,
    RunSelectorAgentTool,
    GenerateCrawlPlanTool,
)

logger = logging.getLogger(__name__)

MAIN_AGENT_PROMPT = """You are the Main Orchestrator Agent for creating web crawler plans.

Your goal is to analyze a website and create a complete crawl plan by coordinating specialized agents.

Workflow:
1. Store the target URL in memory
2. Run the Browser Agent to navigate and extract article links
3. Run the Selector Agent to find optimal CSS selectors
4. Generate the final crawl plan

Available agents:
- Browser Agent: Navigates pages, extracts links, stores in memory
- Selector Agent: Finds and verifies CSS selectors

Your tools:
- memory_write/read/list: Manage shared memory
- run_browser_agent: Execute browser agent with a task
- run_selector_agent: Execute selector agent with a task
- generate_crawl_plan: Create final markdown plan

Important:
1. Always store target_url first before running agents
2. Check memory after each agent completes
3. Verify agents succeeded before proceeding
4. Generate plan only after both agents complete

Error handling:
- If browser agent fails, retry with simplified task
- If selector agent can't find selectors, note in plan
- Always generate a plan, even if partial

When done, return the complete crawl plan."""


class MainAgent(BaseAgent):
    """Main orchestrator agent that coordinates browser and selector agents."""

    name = "main_agent"
    system_prompt = MAIN_AGENT_PROMPT

    def __init__(
        self,
        llm: LLMClient,
        browser_session: BrowserSession,
        memory_store: MemoryStore | None = None
    ):
        self.memory_store = memory_store or MemoryStore()
        self.browser_session = browser_session

        # Create sub-agents
        self.browser_agent = BrowserAgent(llm, browser_session, self.memory_store)
        self.selector_agent = SelectorAgent(llm, browser_session, self.memory_store)

        tools = [
            # Memory tools
            MemoryReadTool(self.memory_store),
            MemoryWriteTool(self.memory_store),
            MemoryListTool(self.memory_store),
            # Agent orchestration tools
            RunBrowserAgentTool(self.browser_agent),
            RunSelectorAgentTool(self.selector_agent),
            # Plan generation
            GenerateCrawlPlanTool(self.memory_store),
        ]

        super().__init__(llm, tools)

    def create_crawl_plan(self, url: str) -> dict[str, Any]:
        """High-level method to create a complete crawl plan for a URL."""
        task = f"""Create a complete crawl plan for: {url}

Steps:
1. Store the target URL in memory as 'target_url'
2. Run the browser agent to navigate to the URL and extract all article links
3. Run the selector agent to find the best CSS selectors
4. Generate the final crawl plan

Return the complete markdown crawl plan when done."""

        return self.run(task)
