"""Contract Data Preparation Agent for creating test datasets."""
import logging
from typing import Any

from .base import BaseAgent
from ..core.llm import LLMClient
from ..core.browser import BrowserSession
from ..tools.browser import (
    NavigateTool,
    GetHTMLTool,
    WaitTool,
)
from ..tools.memory import (
    MemoryStore,
    MemoryReadTool,
    MemoryWriteTool,
    MemorySearchTool,
)
from ..tools.random_choice import RandomChoiceTool

logger = logging.getLogger(__name__)

DATA_PREP_AGENT_PROMPT = """You are a Contract Data Preparation Agent that creates test datasets for web crawlers.

Your goal is to prepare a comprehensive test dataset that can be used to verify crawler implementations.

## Workflow

### Step 1: Understand the site structure
Read from memory:
- 'target_url': Base URL
- 'article_selector': CSS selector for article links
- 'pagination_type': How pagination works
- 'pagination_selector': Selector for pagination

### Step 2: Fetch listing pages
1. Generate at least 10 candidate listing page URLs based on pagination pattern
2. Use random_choice to pick 5 different listing pages
3. For each listing page:
   - Navigate to the page
   - Wait 5 seconds for content to load
   - Get the HTML content
   - Extract article URLs from the page
   - Store the listing page data in memory

### Step 3: Collect article URLs
1. Gather all article URLs from all listing pages
2. Use random_choice to pick 20 different article URLs

### Step 4: Fetch article pages
For each of the 20 selected articles:
1. Navigate to the article page
2. Wait 5 seconds for content to load
3. Get the HTML content
4. Extract expected data (title, date, author, content) using your understanding of the page
5. Store the article data in memory

### Step 5: Store test data
Store each test entry in memory with structured keys:
- 'test-data-listing-{n}': Listing page test entry
- 'test-data-article-{n}': Article page test entry

Each entry should be an object with:
```json
{
    "type": "listing" or "article",
    "url": "page URL",
    "given": "HTML content",
    "expected": {
        // For listings: {"article_urls": [...]}
        // For articles: {"title": "...", "date": "...", "author": "...", "content": "..."}
    }
}
```

### Step 6: Write description
Store a brief description of the test data at key 'test-data-description' explaining:
- How many listing pages
- How many article pages
- What data is extracted
- How to use the test set

## Important Notes
- Always wait 5 seconds after navigation for JS to render
- Use random selection to avoid bias
- Extract clean text content, not raw HTML for expected values
- Handle errors gracefully - skip pages that fail"""


class DataPrepAgent(BaseAgent):
    """Agent for preparing contract test datasets."""

    name = "data_prep_agent"
    system_prompt = DATA_PREP_AGENT_PROMPT

    def __init__(
        self,
        llm: LLMClient,
        browser_session: BrowserSession,
        memory_store: MemoryStore | None = None
    ):
        self.browser_session = browser_session
        self.memory_store = memory_store or MemoryStore()

        tools = [
            # Browser tools
            NavigateTool(browser_session),
            GetHTMLTool(browser_session),
            WaitTool(browser_session),
            # Random selection
            RandomChoiceTool(),
            # Memory tools
            MemoryReadTool(self.memory_store),
            MemoryWriteTool(self.memory_store),
            MemorySearchTool(self.memory_store),
        ]

        super().__init__(llm, tools)
