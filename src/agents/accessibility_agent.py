"""Accessibility Validation Agent to check if site works without JavaScript.

This agent inherits from BaseAgent which uses the @traced_agent decorator
for automatic observability instrumentation.
"""
from .base import BaseAgent
from ..core.llm import LLMClient
from ..tools.http import HTTPRequestTool
from ..tools.memory import (
    MemoryStore,
    MemoryReadTool,
    MemoryWriteTool,
)

ACCESSIBILITY_AGENT_PROMPT = """You are an Accessibility Validation Agent that checks if a website's content can be accessed via simple HTTP requests without JavaScript rendering.

Your goal is to determine if a web crawler can use simple HTTP requests (like curl or requests library) or needs a full browser with JavaScript rendering.

Workflow:
1. Read from memory the target URL and article selector
2. Read from memory some sample article URLs
3. Use http_request tool to fetch the listing page
4. Analyze if the HTML contains the expected article links
5. Fetch a sample article page via HTTP
6. Check if the article content is present in the raw HTML

Memory keys to read:
- 'target_url': Main listing page URL
- 'extracted_articles': Sample article URLs
- 'article_selector': CSS selector for articles

Memory keys to write:
- 'accessibility_result': Object with:
  - 'requires_browser': boolean - true if JS rendering needed
  - 'listing_accessible': boolean - can access listing via HTTP
  - 'articles_accessible': boolean - can access articles via HTTP
  - 'notes': string - explanation of findings

Decision criteria:
1. If listing page HTML contains article links matching the selector → listing_accessible = true
2. If article pages contain main content without JS → articles_accessible = true
3. If either is false → requires_browser = true

Common signs that JS is required:
- HTML contains only skeleton/loading elements
- Content is loaded via JavaScript framework (React, Vue, Angular)
- Page has minimal HTML with lots of script tags
- Expected content not found in raw HTML

When done, summarize your findings."""


class AccessibilityAgent(BaseAgent):
    """Agent to validate if site content is accessible via HTTP."""

    name = "accessibility_agent"
    system_prompt = ACCESSIBILITY_AGENT_PROMPT

    def __init__(
        self,
        llm: LLMClient,
        memory_store: MemoryStore | None = None
    ):
        self.memory_store = memory_store or MemoryStore()

        tools = [
            HTTPRequestTool(),
            MemoryReadTool(self.memory_store),
            MemoryWriteTool(self.memory_store),
        ]

        super().__init__(llm, tools)
