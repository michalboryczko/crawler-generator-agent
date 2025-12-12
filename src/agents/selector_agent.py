"""Selector Agent for finding and verifying CSS selectors."""
import logging

from .base import BaseAgent
from ..core.llm import LLMClient
from ..core.browser import BrowserSession
from ..tools.memory import (
    MemoryStore,
    MemoryReadTool,
    MemoryWriteTool,
    MemorySearchTool,
)
from ..tools.selector_sampling import (
    ListingPagesGeneratorTool,
    ArticlePagesGeneratorTool,
)
from ..tools.selector_extraction import (
    ListingPageExtractorTool,
    ArticlePageExtractorTool,
    SelectorAggregatorTool,
)

logger = logging.getLogger(__name__)

SELECTOR_AGENT_PROMPT = """You are a Selector Agent. Find CSS selectors by visiting multiple listing and article pages.

## CRITICAL: ONE TOOL CALL AT A TIME
You MUST call only ONE tool per response. Never batch multiple tool calls.

## Available Tools

### Sampling Tools
- generate_listing_pages: Generate listing page URLs (2% of pages, min 5, max 20).
  Pass pagination_links array if available to detect URL pattern (offset, page param, etc.)
- generate_article_pages: Group article URLs by pattern and sample (20% per group, min 3)

### Extraction Tools
- extract_listing_page: Navigate to ONE listing page and extract selectors + article URLs.
  Returns {"selectors": {...}, "article_urls": [...]}
- extract_article_page: Navigate to ONE article page and extract detail selectors

### Aggregation Tool
- aggregate_selectors: Create SELECTOR CHAINS from all extractions

### Memory Tools
- memory_read: Read from memory
- memory_write: Write to memory
- memory_search: Search memory

## Workflow - Follow these steps IN ORDER

### Step 1: Read configuration
Call memory_read for 'target_url' and 'pagination_max_pages'

### Step 2: Generate listing page URLs
Call generate_listing_pages with target_url and max_pages

### Step 3: Extract from EACH listing page
For EACH URL from Step 2:
- Call extract_listing_page with that URL
- SAVE the article_urls from each extraction (critical for Step 4!)
- After first page, pass listing_container_selector to focus subsequent pages

### Step 4: Generate article page URLs
Call generate_article_pages with ALL article URLs collected from Step 3
IMPORTANT: You need article URLs to proceed. If Step 3 extractions returned no URLs, report the error.

### Step 5: Extract from EACH article page
For EACH URL from Step 4, call extract_article_page

### Step 6: Aggregate selectors
Call aggregate_selectors with all listing_extractions and article_extractions

### Step 7: Store results (MULTIPLE memory_write calls)
After aggregation, make SEPARATE memory_write calls for EACH of these:

1. memory_write key='listing_selectors' value=<the listing_selectors from aggregation>
2. memory_write key='detail_selectors' value=<the detail_selectors from aggregation>
3. memory_write key='listing_container_selector' value=<extract from listing_selectors["listing_container"][0]["selector"]>
4. memory_write key='article_selector' value=<extract from listing_selectors["article_link"][0]["selector"]>
5. memory_write key='collected_article_urls' value=<ALL article URLs found in Step 3>
6. memory_write key='selector_analysis' value=<summary string>

CRITICAL: Steps 3 and 4 are essential. If you have 0 article URLs after Step 3, you MUST store
listing_container_selector and article_selector from the FIRST listing page extraction before
proceeding, even if article URLs are empty.

## Extracting Primary Selectors from Chains
After aggregation, listing_selectors looks like:
{
  "listing_container": [{"selector": "main.content", "success_rate": 1.0}, ...],
  "article_link": [{"selector": "a.article-link", "success_rate": 0.95}, ...]
}

To get the PRIMARY selector, take the FIRST item's "selector" field:
- listing_container_selector = listing_selectors["listing_container"][0]["selector"]
- article_selector = listing_selectors["article_link"][0]["selector"]

## CRITICAL RULES
- Call ONE tool at a time
- Process EVERY URL from generators - no skipping
- COLLECT article_urls from EVERY listing page extraction
- Store BOTH selector chains AND individual primary selectors in memory"""


class SelectorAgent(BaseAgent):
    """Agent for finding and verifying CSS selectors."""

    name = "selector_agent"
    system_prompt = SELECTOR_AGENT_PROMPT

    def __init__(
        self,
        llm: LLMClient,
        browser_session: BrowserSession,
        memory_store: MemoryStore | None = None
    ):
        self.browser_session = browser_session
        self.memory_store = memory_store or MemoryStore()

        tools = [
            # Sampling tools (URL generation with LLM for pattern detection)
            ListingPagesGeneratorTool(llm),
            ArticlePagesGeneratorTool(llm),
            # Extraction tools (isolated context per page)
            ListingPageExtractorTool(llm, browser_session),
            ArticlePageExtractorTool(llm, browser_session),
            # Aggregation tool (creates selector chains, not single selectors)
            SelectorAggregatorTool(llm),
            # Memory tools
            MemoryReadTool(self.memory_store),
            MemoryWriteTool(self.memory_store),
            MemorySearchTool(self.memory_store),
        ]

        super().__init__(llm, tools)
