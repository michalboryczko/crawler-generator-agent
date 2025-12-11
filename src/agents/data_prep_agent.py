"""Contract Data Preparation Agent for creating test datasets."""
import logging
from typing import Any

from .base import BaseAgent
from ..core.llm import LLMClient
from ..core.browser import BrowserSession
from ..tools.memory import (
    MemoryStore,
    MemoryReadTool,
    MemoryWriteTool,
    MemorySearchTool,
)
from ..tools.random_choice import RandomChoiceTool
from ..tools.extraction import (
    BatchFetchURLsTool,
    BatchExtractArticlesTool,
    BatchExtractListingsTool,
)

logger = logging.getLogger(__name__)

DATA_PREP_AGENT_PROMPT = """You are a Contract Data Preparation Agent that creates test datasets for web crawlers.

Your goal: Create test entries for BOTH listing pages and article pages.

## Required Test Data
- **5+ listing pages** with extracted article URLs
- **20+ article pages** with extracted content

## Test Entry Formats

### Listing Entry (type="listing"):
{
    "type": "listing",
    "url": "https://example.com/articles?page=2",
    "given": "<HTML content>",
    "expected": {
        "article_urls": ["url1", "url2", ...],
        "article_count": 10,
        "has_pagination": true,
        "next_page_url": "next page URL"
    }
}

### Article Entry (type="article"):
{
    "type": "article",
    "url": "https://example.com/article/123",
    "given": "<HTML content>",
    "expected": {
        "title": "Article Title",
        "date": "2024-01-15",
        "authors": ["Author Name"],
        "content": "First 500 chars..."
    }
}

## Available Tools

### batch_fetch_urls
Fetches URLs using browser and stores HTML in memory.
- urls: list of URLs to fetch
- key_prefix: prefix for storage keys (e.g., "listing-html" or "article-html")
- wait_seconds: wait time per page (default: 3)

### batch_extract_listings
Extracts article URLs from listing page HTML.
- html_key_prefix: prefix to find listing HTML (e.g., "listing-html")
- output_key_prefix: prefix for output (default: "test-data-listing")
- Also stores all found article URLs at "collected_article_urls"

### batch_extract_articles
Extracts article data from article page HTML.
- html_key_prefix: prefix to find article HTML (e.g., "article-html")
- output_key_prefix: prefix for output (default: "test-data-article")

### random_choice
Pick random items from a list.
- items: list to choose from
- count: number to pick

### memory_read/write/search
Access shared memory.

## Workflow - FOLLOW EXACTLY

### Phase 1: Generate Listing Page URLs
1. Read 'target_url' from memory
2. Read 'pagination_type' and 'pagination_max_pages' from memory
3. Generate 5-10 listing page URLs:
   - If pagination_type is "numbered" or "url_parameter":
     Use URL pattern like: {target_url}?page=N
   - Pick random page numbers (e.g., 1, 5, 10, 50, 100)
4. Use random_choice to select 5-7 listing URLs

### Phase 2: Fetch Listing Pages
1. Call batch_fetch_urls with:
   - urls: the selected listing URLs
   - key_prefix: "listing-html"
   - wait_seconds: 3
2. Browser will navigate to each listing page

### Phase 3: Extract Listing Data
1. Read 'article_selector' from memory (for hint)
2. Call batch_extract_listings with:
   - html_key_prefix: "listing-html"
   - output_key_prefix: "test-data-listing"
   - article_selector: the selector from memory
3. This creates test-data-listing-1, test-data-listing-2, etc.
4. Also stores all article URLs at "collected_article_urls"

### Phase 4: Select Article URLs
1. Read 'collected_article_urls' from memory
2. Use random_choice to pick 20-25 article URLs
   - This ensures random selection across all listing pages

### Phase 5: Fetch Article Pages
1. Call batch_fetch_urls with:
   - urls: the 20-25 selected article URLs
   - key_prefix: "article-html"
   - wait_seconds: 3

### Phase 6: Extract Article Data
1. Call batch_extract_articles with:
   - html_key_prefix: "article-html"
   - output_key_prefix: "test-data-article"
2. This creates test-data-article-1 through test-data-article-20+

### Phase 7: Summary
1. Store description at 'test-data-description' using memory_write
2. Report counts: X listing entries, Y article entries

## Important Rules
- ALWAYS fetch 5+ listing pages first
- ALWAYS wait for listing extraction before selecting articles
- Select articles ONLY from collected_article_urls (not from extracted_articles)
- This ensures articles come from different listing pages
- Total test entries: 25+ (5 listings + 20 articles minimum)
"""


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
            # Batch fetch (uses browser)
            BatchFetchURLsTool(browser_session, self.memory_store),
            # Batch extraction (separate LLM contexts)
            BatchExtractListingsTool(llm, self.memory_store),
            BatchExtractArticlesTool(llm, self.memory_store),
            # Random selection
            RandomChoiceTool(),
            # Memory tools
            MemoryReadTool(self.memory_store),
            MemoryWriteTool(self.memory_store),
            MemorySearchTool(self.memory_store),
        ]

        super().__init__(llm, tools)
