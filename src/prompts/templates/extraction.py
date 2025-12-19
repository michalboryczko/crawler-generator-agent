"""Extraction prompts for listing and article pages.

These prompts are used by selector extraction tools to analyze page structure.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..registry import PromptRegistry

LISTING_EXTRACTION_PROMPT = """You are analyzing a listing page. Your PRIMARY task is to EXTRACT ALL ARTICLE URLs from the main listing.

## YOUR MAIN TASK: Extract URLs
Look at the HTML and find ALL links to articles/publications in the MAIN CONTENT area.
- Find every <a href="..."> that links to an individual article/publication/report
- Extract the FULL URL from each href attribute
- You should find 10-30 URLs on a typical listing page
- If you find fewer than 5 URLs, you are probably looking at the wrong section!

## SKIP these sections (they contain misleading links):
- <header>, <nav>, top navigation bars
- Sidebars, "featured", "popular", "recent", "trending" sections
- <footer>, bottom links
- Social media links, share buttons

## FOCUS on the MAIN LISTING:
- The main content area (often <main>, <section class="...content...">, <div class="...results...">)
- The repeating list of article cards/items (often <ul>, <div> with multiple similar child elements)
- This is the section that changes when you paginate

## Also identify these CSS selectors:
1. listing_container: The main content area containing the article list
2. article_list: The list element holding article items (ul, div, etc.)
3. article_link: The <a> element for article links (the selector you use to find URLs)
4. article_date: Date display (if visible), or null
5. article_category: Category/type (if visible), or null
6. pagination: Pagination controls

Respond with JSON:
{
  "article_urls": [
    "https://example.com/article1",
    "https://example.com/article2",
    "... (INCLUDE ALL URLs - this is the most important field!)"
  ],
  "selectors": {
    "listing_container": "CSS selector for main content container",
    "article_list": "CSS selector for the list element",
    "article_link": "CSS selector for article links",
    "article_date": "CSS selector or null",
    "article_category": "CSS selector or null",
    "pagination": "CSS selector for pagination"
  },
  "notes": "observations about page structure"
}

CRITICAL: The article_urls array MUST contain actual URLs extracted from the HTML, not placeholders!
A typical listing page has 10-30 articles. If your array is empty or has only 3-5 URLs, re-check the HTML."""


ARTICLE_EXTRACTION_PROMPT = """You are analyzing an article detail page to extract CSS selectors for content fields.

Given the HTML of an article page, identify CSS selectors for:
1. Article title (usually h1)
2. Publication date
3. Author(s)
4. Lead/summary/excerpt
5. Main content body
6. Category/type
7. Tags (if present)
8. Breadcrumbs (if present)
9. Downloadable files/attachments (PDF, DOC, etc.) - IMPORTANT: look for download links!
10. Images (if article has main images)

IMPORTANT - Look for downloadable files:
- PDF downloads (often in sidebar or "Download" sections)
- Document attachments (.pdf, .doc, .xlsx, .zip, etc.)
- "Download", "Full Report", "Read PDF" links
- Links with href containing .pdf, .doc, or file extensions

Respond with JSON only:
{
  "selectors": {
    "title": {"selector": "CSS selector", "found": true/false},
    "date": {"selector": "CSS selector or null", "found": true/false},
    "authors": {"selector": "CSS selector or null", "found": true/false},
    "lead": {"selector": "CSS selector or null", "found": true/false},
    "content": {"selector": "CSS selector", "found": true/false},
    "category": {"selector": "CSS selector or null", "found": true/false},
    "tags": {"selector": "CSS selector or null", "found": true/false},
    "breadcrumbs": {"selector": "CSS selector or null", "found": true/false},
    "files": {"selector": "CSS selector for download links/PDF links", "found": true/false},
    "images": {"selector": "CSS selector or null", "found": true/false}
  },
  "extracted_values": {
    "title": "actual title text found",
    "date": "actual date found",
    "authors": ["author names found"],
    "files": [{"url": "file URL if found", "title": "file name"}]
  },
  "notes": "observations about page structure, especially any download/file sections found"
}"""


def register_extraction_prompts(registry: "PromptRegistry") -> None:
    """Register extraction prompts with the registry."""
    registry.register_prompt(
        name="extraction.listing",
        content=LISTING_EXTRACTION_PROMPT,
        version="1.0.0",
        category="extraction",
        description="Extract article URLs and selectors from listing pages",
    )
    registry.register_prompt(
        name="extraction.article",
        content=ARTICLE_EXTRACTION_PROMPT,
        version="1.0.0",
        category="extraction",
        description="Extract content selectors from article pages",
    )
