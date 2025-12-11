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
- extract_listing_page: Navigate to ONE listing page and extract selectors + article URLs
- extract_article_page: Navigate to ONE article page and extract detail selectors

### Aggregation Tool
- aggregate_selectors: Create SELECTOR CHAINS from all extractions (ordered lists of all
  working selectors, not just one). Crawler will try each in order until match.

### Memory Tools
- memory_read: Read from memory
- memory_write: Write to memory
- memory_search: Search memory

## Workflow - Follow these steps IN ORDER

### Step 1: Read configuration
Call memory_read for:
- 'target_url'
- 'pagination_max_pages'
- 'pagination_links' (if available - helps detect URL pattern like offset vs page)

### Step 2: Generate listing page URLs
Call generate_listing_pages with:
- target_url
- max_pages
- pagination_links (if available from memory)

### Step 3: Extract from EACH listing page
For EACH URL returned by generate_listing_pages:
- Call extract_listing_page with that URL
- This tool handles navigation, waiting, and extraction automatically
- Collect all results (selectors + article URLs from each page)

### Step 4: Generate article page URLs
After ALL listing pages are done, call generate_article_pages with all collected article URLs

### Step 5: Extract from EACH article page
For EACH URL returned by generate_article_pages:
- Call extract_article_page with that URL
- Collect all results

### Step 6: Aggregate selectors
Call aggregate_selectors with all listing_extractions and article_extractions
This returns SELECTOR CHAINS - ordered lists where crawler tries each until one matches

### Step 7: Store results
Store in memory:
- 'listing_selectors': Selector chains for listing pages (each field has ordered list)
- 'detail_selectors': Selector chains for article pages (each field has ordered list)
- 'article_selector': Primary article link selector (first from chain)
- 'collected_article_urls': All article URLs found
- 'selector_analysis': Summary of analysis
- 'pagination_pattern': Detected pagination URL pattern

## Selector Chain Format
Results are stored as chains, e.g.:
{
  "title": [
    {"selector": "h1.article-title", "priority": 1, "success_rate": 0.95},
    {"selector": "h1", "priority": 2, "success_rate": 0.80}
  ]
}
The crawler will try selectors in order until one matches.

## CRITICAL RULES
- Call ONE tool at a time
- You MUST call extract_listing_page for EACH URL from generate_listing_pages
- You MUST call extract_article_page for EACH URL from generate_article_pages
- Do NOT skip pages - process every URL returned by the generators
- Only call aggregate_selectors AFTER all extractions are complete"""


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
