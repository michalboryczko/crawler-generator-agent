"""Plan generation tool with comprehensive templates.

This module uses the new observability decorators for automatic logging.
The @traced_tool decorator handles all tool instrumentation.
"""
import logging
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from ..observability.decorators import traced_tool
from .base import BaseTool

if TYPE_CHECKING:
    from ..services.memory_service import MemoryService

logger = logging.getLogger(__name__)


class GeneratePlanTool(BaseTool):
    """Generate comprehensive plan.md from memory data."""

    name = "generate_plan_md"
    description = """Generate a comprehensive crawl plan from data stored in memory.
    Reads all collected data and produces detailed markdown documentation."""

    def __init__(self, memory_service: "MemoryService"):
        self._service = memory_service

    @traced_tool(name="generate_plan_md")
    def execute(self) -> dict[str, Any]:
        """Generate plan markdown. Instrumented by @traced_tool."""
        # Read all data from memory
        target_url = self._service.read("target_url") or "Unknown"
        article_selector = self._service.read("article_selector") or "Not found"
        article_confidence = self._service.read("article_selector_confidence") or 0
        listing_container_selector = self._service.read("listing_container_selector") or "Not found"
        pagination_selector = self._service.read("pagination_selector") or "None"
        pagination_type = self._service.read("pagination_type") or "none"
        pagination_max_pages = self._service.read("pagination_max_pages")
        extracted_articles = self._service.read("extracted_articles") or []
        accessibility = self._service.read("accessibility_result") or {}
        detail_selectors = self._service.read("detail_selectors") or {}
        listing_selectors = self._service.read("listing_selectors") or {}

        # Parse URL for site info
        parsed = urlparse(target_url)
        site_name = parsed.netloc.replace("www.", "")

        # Determine browser requirement
        requires_browser = accessibility.get("requires_browser", True)
        listing_accessible = accessibility.get("listing_accessible", False)
        articles_accessible = accessibility.get("articles_accessible", False)

        # Build the comprehensive plan
        plan = self._build_header(site_name, target_url)
        plan += self._build_scope_section(target_url, pagination_max_pages, detail_selectors)
        plan += self._build_start_urls_section(target_url, pagination_type, pagination_max_pages)
        plan += self._build_listing_section(article_selector, listing_container_selector, listing_selectors, article_confidence)
        plan += self._build_pagination_section(pagination_type, pagination_selector, pagination_max_pages)
        plan += self._build_detail_section(detail_selectors)
        plan += self._build_data_model_section(target_url, detail_selectors)
        plan += self._build_config_section(
            target_url, article_selector, listing_container_selector, pagination_selector,
            pagination_type, pagination_max_pages, requires_browser, detail_selectors
        )
        plan += self._build_accessibility_section(requires_browser, listing_accessible, articles_accessible)
        plan += self._build_sample_articles_section(extracted_articles)
        plan += self._build_notes_section(requires_browser)

        logger.info(f"Generated plan.md for {site_name}")

        return {"success": True, "result": plan}

    def _build_header(self, site_name: str, target_url: str) -> str:
        return f"""# Crawl Plan for {site_name}

Target: **{target_url}**

This plan is based on:
- Stored target URL
- Browser Agent output: extracted article records + pagination info
- Selector Agent output: verified listing & pagination selectors, inferred detail-page selectors
- Accessibility Agent output: HTTP vs browser requirement analysis

---

"""

    def _build_scope_section(self, target_url: str, max_pages: int | None, detail_selectors: dict) -> str:
        parsed = urlparse(target_url)
        path = parsed.path.rstrip('/')

        section = """## 1. Scope & Objectives

**Goal:** Collect all articles/publications from this section, including:
- URL
"""
        # Dynamically list fields based on discovered selectors
        discovered_fields = self._get_discovered_fields(detail_selectors)
        for field in discovered_fields:
            # Format field name nicely
            display_name = field.replace("_", " ").title()
            section += f"- {display_name}\n"

        section += "\n**Coverage:**\n"
        if max_pages:
            section += f"- Listing pages: `{target_url}?page=N` (1 … ~{max_pages})\n"
        else:
            section += f"- Listing pages: `{target_url}` (pagination to be determined)\n"

        section += f"- Article detail pages: `{parsed.scheme}://{parsed.netloc}{path}/<slug>`\n\n---\n\n"
        return section

    def _get_discovered_fields(self, detail_selectors: dict) -> list[str]:
        """Extract field names from detail selectors, handling both old and new chain format."""
        if not detail_selectors:
            # Default fields if nothing discovered
            return ["title", "publication_date", "authors", "category", "content"]

        fields = []
        for field, value in detail_selectors.items():
            # Check if the selector chain has any valid selectors
            if isinstance(value, list):
                # New chain format: [{"selector": "...", "priority": 1}, ...]
                if any(item.get("selector") for item in value if isinstance(item, dict)):
                    fields.append(field)
            elif isinstance(value, dict):
                # Old format: {"primary": "...", "fallbacks": [...]}
                if value.get("primary") or value.get("selector"):
                    fields.append(field)
            elif isinstance(value, str) and value:
                fields.append(field)

        return fields if fields else ["title", "publication_date", "authors", "category", "content"]

    def _build_start_urls_section(self, target_url: str, pagination_type: str, max_pages: int | None) -> str:
        section = f"""## 2. Start URLs

- Primary start URL:
  `{target_url}`

"""
        if pagination_type in ["numbered", "url_parameter"] and max_pages:
            section += f"""Optional explicit pages:
- Page 1: `{target_url}`
- Page 2: `{target_url}?page=2`
- Last page: `{target_url}?page={max_pages}`

"""
        section += "---\n\n"
        return section

    def _build_listing_section(self, article_selector: str, listing_container_selector: str, listing_selectors: dict, confidence: float) -> str:
        section = f"""## 3. Listing Pages

### 3.1. Main content container

**Purpose:** Focus extraction on the main listing area, excluding headers/sidebars/footers.

**Container selector:**
```css
{listing_container_selector}
```

**Usage:** Before extracting articles, narrow the DOM to this container to avoid
picking up "featured" or "recent" articles from headers/sidebars.

### 3.2. Article blocks & links

**Purpose:** Discover article detail URLs and basic metadata from listing pages.

**Article link selector (verified):**
```css
{article_selector}
```
- **Confidence**: {confidence}

**Usage:**
- Within the container, select all matching `<a>` elements.
- Extract:
  - `url`: resolve relative `href` against base URL
  - `title`: `textContent` of the `<a>`

"""
        if listing_selectors:
            section += "**Additional listing-level selectors (as chains):**\n\n"
            for field, selector_chain in listing_selectors.items():
                if selector_chain:
                    # Handle selector chains (list) or simple strings
                    if isinstance(selector_chain, list) and len(selector_chain) > 0:
                        primary = selector_chain[0]
                        selector = primary.get("selector", str(primary)) if isinstance(primary, dict) else str(primary)
                        section += f"- **{field}:**\n  ```css\n  {selector}\n  ```\n"
                        if len(selector_chain) > 1:
                            section += f"  (+ {len(selector_chain) - 1} fallback selectors)\n"
                        section += "\n"
                    else:
                        section += f"- **{field}:**\n  ```css\n  {selector_chain}\n  ```\n\n"

        section += "---\n\n"
        return section

    def _build_pagination_section(self, pagination_type: str, pagination_selector: str, max_pages: int | None) -> str:
        section = f"""## 4. Pagination

### 4.1. Pagination type

- **Type:** `{pagination_type}`
"""

        if pagination_type == "numbered":
            section += """- Example structure:
  ```html
  <div class="paginator">
    <ul class="pagination">
      <li class="first"><a href="...">&lt;&lt;</a></li>
      <li class="prev"><a rel="prev" href="...">&lt;</a></li>
      <li><a href="...">1</a></li>
      ...
      <li class="next"><a rel="next" href="...">&gt;</a></li>
      <li class="last"><a href="...">&gt;&gt;</a></li>
    </ul>
  </div>
  ```

"""

        section += f"""### 4.2. Pagination selector

**All pagination links:**
```css
{pagination_selector}
```

"""

        section += """### 4.3. Pagination strategy

Recommended approach:

"""
        if pagination_type == "numbered":
            section += f"""1. Start at the primary URL.
2. On each page:
   - Extract article links using the article selector.
   - Extract pagination links.
3. Either:
   - **Deterministic loop:** Iterate `page=1..{max_pages if max_pages else 'N'}`, or
   - **Link-following:** Follow the "next" link until it disappears or repeats.
4. De-duplicate article URLs globally.

"""
        elif pagination_type == "next_button":
            section += """1. Start at the primary URL.
2. On each page:
   - Extract article links.
   - Find and click the "Next" button.
3. Continue until the "Next" button is not found or disabled.
4. De-duplicate article URLs globally.

"""
        elif pagination_type == "infinite_scroll":
            section += """1. Start at the primary URL.
2. Scroll to bottom to trigger content loading.
3. Wait for new content to appear.
4. Repeat scrolling until no new content loads.
5. Extract all article links once loading is complete.

"""
        else:
            section += """Single page - extract all articles from the start URL.

"""

        section += "---\n\n"
        return section

    def _build_detail_section(self, detail_selectors: dict) -> str:
        section = """## 5. Article Detail Pages

Selectors below are discovered from analyzing multiple article pages.
Each field has a **selector chain** - an ordered list of selectors to try until one matches.

"""

        # Default selectors if none provided
        default_selectors = {
            "title": [{"selector": "h1.article-title, .article-view h1", "priority": 1, "success_rate": 1.0}],
            "date": [{"selector": ".article-date, .publication-date, time[datetime]", "priority": 1, "success_rate": 1.0}],
            "authors": [{"selector": ".article-author a, .author-name, [rel='author']", "priority": 1, "success_rate": 1.0}],
            "category": [{"selector": ".article-category, .article-type a, .category", "priority": 1, "success_rate": 1.0}],
            "content": [{"selector": ".article-content, .article-body, .entry-content", "priority": 1, "success_rate": 1.0}],
        }

        selectors_to_use = detail_selectors if detail_selectors else default_selectors

        for i, (field, info) in enumerate(selectors_to_use.items(), 1):
            section += f"""### 5.{i}. {field.replace("_", " ").title()}

"""
            # Handle selector chain format (new)
            if isinstance(info, list):
                if not info:
                    section += "*No selectors found for this field.*\n\n"
                    continue

                section += "**Selector chain** (try in order until match):\n\n"
                for j, item in enumerate(info, 1):
                    if isinstance(item, dict):
                        selector = item.get("selector", "")
                        success_rate = item.get("success_rate", 0)
                        notes = item.get("notes", "")
                        priority = item.get("priority", j)

                        section += f"{priority}. `{selector}`"
                        if success_rate:
                            section += f" *(success: {int(success_rate * 100)}%)*"
                        if notes:
                            section += f" - {notes}"
                        section += "\n"
                    else:
                        section += f"{j}. `{item}`\n"
                section += "\n"

            # Handle old dict format
            elif isinstance(info, dict):
                primary = info.get("primary", info.get("selector", ""))
                fallbacks = info.get("fallbacks", [])
                confidence = info.get("confidence", 0)
                desc = info.get("description", "")

                section += f"**Primary selector:**\n```css\n{primary}\n```\n"
                if confidence:
                    section += f"*Confidence: {int(confidence * 100)}%*\n"
                if desc:
                    section += f"*{desc}*\n"
                if fallbacks:
                    section += "\n**Fallbacks:**\n"
                    for fb in fallbacks:
                        section += f"- `{fb}`\n"
                section += "\n"

            # Handle simple string format
            elif isinstance(info, str):
                section += f"**Selector:**\n```css\n{info}\n```\n\n"

        section += "---\n\n"
        return section

    def _build_data_model_section(self, target_url: str, detail_selectors: dict) -> str:
        parsed = urlparse(target_url)
        example_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}/example-article"

        # Build dynamic JSON example based on discovered fields
        discovered_fields = self._get_discovered_fields(detail_selectors)

        json_fields = [f'  "url": "{example_url}"']

        # Map field names to example values
        field_examples = {
            "title": '"Article Title"',
            "date": '"2024-01-15"',
            "publication_date": '"2024-01-15"',
            "authors": '["Author Name"]',
            "author": '"Author Name"',
            "category": '"Category"',
            "content": '"<p>Article content...</p>"',
            "body": '"<p>Article content...</p>"',
            "lead": '"Article summary/lead paragraph"',
            "summary": '"Article summary"',
            "tags": '["tag1", "tag2"]',
            "language": '"en"',
            "breadcrumbs": '["Home", "Section", "Article"]',
            "files": '[{"name": "document.pdf", "url": "/files/doc.pdf"}]',
            "attachments": '[{"name": "file.pdf", "url": "/attachments/file.pdf"}]',
            "related_articles": '[{"title": "Related", "url": "/related"}]',
            "images": '[{"src": "/img/photo.jpg", "alt": "Photo"}]',
        }

        for field in discovered_fields:
            field_lower = field.lower()
            example = field_examples.get(field_lower, f'"{field} value"')
            json_fields.append(f'  "{field}": {example}')

        # Add metadata fields
        json_fields.append(f'  "source_listing_page": "{target_url}?page=1"')

        json_content = ",\n".join(json_fields)

        # Build notes based on discovered fields
        notes = []
        if "date" in discovered_fields or "publication_date" in discovered_fields:
            notes.append("- `date`/`publication_date` should come from the detail page, not the listing.")
        if "language" in discovered_fields:
            notes.append("- `language` extracted from `html[lang]` attribute.")
        if "files" in discovered_fields or "attachments" in discovered_fields:
            notes.append("- `files`/`attachments` contain downloadable documents found on the page.")
        if "breadcrumbs" in discovered_fields:
            notes.append("- `breadcrumbs` provide navigation path context.")
        notes.append("- `source_listing_page` is optional but useful for debugging.")

        notes_text = "\n".join(notes)

        return f"""## 6. Data Model

Recommended fields per article (based on discovered selectors):

```json
{{
{json_content}
}}
```

Notes:
{notes_text}

---

"""

    def _build_config_section(
        self, target_url: str, article_selector: str, listing_container_selector: str,
        pagination_selector: str, pagination_type: str, max_pages: int | None,
        requires_browser: bool, detail_selectors: dict
    ) -> str:
        # Build detail selectors with chain support
        detail_config = self._build_detail_config(detail_selectors)

        return f"""## 7. Crawler Configuration

```python
config = {{
    "start_url": "{target_url}",
    "listing": {{
        "container_selector": "{listing_container_selector}",  # Focus on main content
        "article_link_selector": "{article_selector}",
    }},
    "pagination": {{
        "enabled": {str(pagination_selector != "None").lower()},
        "selector": "{pagination_selector}",
        "type": "{pagination_type}",
        "strategy": "{"loop_pages" if pagination_type == "numbered" else "follow_next"}",
        "max_pages": {max_pages if max_pages else 100}
    }},
    "detail": {{
{detail_config}
    }},
    "request": {{
        "requires_browser": {str(requires_browser).lower()},
        "wait_between_requests": 2,
        "max_concurrent_requests": 4,
        "timeout_seconds": 15
    }},
    "deduplication": {{
        "key": "url"
    }}
}}
```

**Note:**
- Use `container_selector` first to narrow DOM to main content area (excludes header/sidebar articles)
- Detail selectors use chains - try each selector in order until one matches

---

"""

    def _build_detail_config(self, detail_selectors: dict) -> str:
        """Build detail config section with selector chains."""
        if not detail_selectors:
            return '''        "title": ["h1.article-title", ".article-view h1"],
        "date": [".article-date", ".publication-date", "time[datetime]"],
        "authors": [".article-author a", ".author-name"],
        "category": [".article-category", ".article-type a"],
        "content": [".article-content", ".article-body"]'''

        lines = []
        for field, info in detail_selectors.items():
            # Handle selector chain format (list)
            if isinstance(info, list):
                selectors = []
                for item in info:
                    if isinstance(item, dict):
                        sel = item.get("selector", "")
                        if sel:
                            selectors.append(f'"{sel}"')
                    elif isinstance(item, str) and item:
                        selectors.append(f'"{item}"')

                if selectors:
                    lines.append(f'        "{field}": [{", ".join(selectors)}]')

            # Handle old dict format
            elif isinstance(info, dict):
                primary = info.get("primary", info.get("selector", ""))
                fallbacks = info.get("fallbacks", [])
                selectors = [f'"{primary}"'] if primary else []
                selectors.extend(f'"{fb}"' for fb in fallbacks if fb)
                if selectors:
                    lines.append(f'        "{field}": [{", ".join(selectors)}]')

            # Handle simple string format
            elif isinstance(info, str) and info:
                lines.append(f'        "{field}": ["{info}"]')

        return ",\n".join(lines) if lines else '        # No selectors discovered'

    def _build_accessibility_section(self, requires_browser: bool, listing_ok: bool, articles_ok: bool) -> str:
        section = """## 8. Accessibility & Requirements

"""
        if requires_browser:
            section += f"""**Browser Required:** Yes

This site requires JavaScript rendering for full functionality.

- Listing pages accessible via HTTP: {"Yes" if listing_ok else "No"}
- Article pages accessible via HTTP: {"Yes" if articles_ok else "No"}

**Recommendation:** Use Playwright or Puppeteer with headless browser.
See `docs/headfull-chrome.md` for implementation details.

"""
        else:
            section += """**Browser Required:** No

This site can be crawled with simple HTTP requests (no JavaScript needed).

**Recommendation:** Use `requests` or `aiohttp` for efficient crawling.

"""
        section += "---\n\n"
        return section

    def _build_sample_articles_section(self, articles: list) -> str:
        section = """## 9. Sample Articles

"""
        if articles:
            for i, article in enumerate(articles[:10], 1):
                if isinstance(article, dict):
                    url = article.get("href", article.get("url", ""))
                    title = article.get("text", article.get("title", "Untitled"))
                    section += f"{i}. [{title}]({url})\n"
                else:
                    section += f"{i}. {article}\n"
        else:
            section += "No articles extracted yet.\n"

        section += "\n---\n\n"
        return section

    def _build_notes_section(self, requires_browser: bool) -> str:
        section = """## 10. Known Limitations / Notes

"""
        if requires_browser:
            section += """- **JavaScript Required:** Site content is dynamically loaded.
- **Rate Limiting:** Implement delays between requests to avoid blocks.
- **Anti-bot Protection:** May need to handle Cloudflare or similar.
"""
        else:
            section += """- **Static Content:** Site can be crawled via HTTP requests.
- **Rate Limiting:** Respect robots.txt and implement polite delays.
"""

        section += """- **Selector Validation:** Detail page selectors are inferred; validate on sample pages before production crawl.
- **Pagination Bounds:** Verify max pages dynamically if content is frequently updated.

This plan provides the foundation for implementing a complete site crawler.
"""
        return section

    def get_parameters_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}


class GenerateTestPlanTool(BaseTool):
    """Generate structured test.md from memory data."""

    name = "generate_test_md"
    description = """Generate test documentation from test data stored in memory.
    Documents both listing and article test entries."""

    def __init__(self, memory_service: "MemoryService"):
        self._service = memory_service

    @traced_tool(name="generate_test_md")
    def execute(self) -> dict[str, Any]:
        """Generate test plan markdown. Instrumented by @traced_tool."""
        target_url = self._service.read("target_url") or "Unknown"
        test_description = self._service.read("test-data-description") or ""
        detail_selectors = self._service.read("detail_selectors") or {}

        # Find all test data keys
        listing_keys = self._service.search("test-data-listing-*")
        article_keys = self._service.search("test-data-article-*")

        listing_count = len(listing_keys)
        article_count = len(article_keys)
        total_count = listing_count + article_count

        # Determine site name
        parsed = urlparse(target_url)
        site_name = parsed.netloc.replace("www.", "")

        # Build dynamic expected fields based on discovered selectors
        expected_fields = self._build_expected_fields(detail_selectors)

        test_plan = f"""# Test Plan: {site_name}

## Test Dataset Overview

- **File**: `data/test_set.jsonl`
- **Total Entries**: {total_count}
  - Listing pages: {listing_count}
  - Article pages: {article_count}
- **Format**: JSONL (one JSON object per line)

---

## Entry Types

### Listing Page Entry

```json
{{
    "type": "listing",
    "url": "listing page URL",
    "given": "HTML content of the listing page",
    "expected": {{
        "article_urls": ["url1", "url2", ...],
        "article_count": 10,
        "has_pagination": true,
        "next_page_url": "next page URL or null"
    }}
}}
```

### Article Page Entry

Fields are based on selectors discovered during analysis:

```json
{{
    "type": "article",
    "url": "article URL",
    "given": "HTML content of the article page",
    "expected": {{
{expected_fields}
    }}
}}
```

---

## How to Use

### Load test data:
```python
import json

def load_test_data(path):
    with open(path) as f:
        return [json.loads(line) for line in f]

tests = load_test_data("data/test_set.jsonl")
listings = [t for t in tests if t["type"] == "listing"]
articles = [t for t in tests if t["type"] == "article"]
```

### Test listing extraction:
```python
from your_crawler import extract_article_links

for test in listings:
    result = extract_article_links(test["given"])
    assert len(result) == test["expected"]["article_count"]
    # Verify URLs match
```

### Test article extraction:
```python
from your_crawler import extract_article

for test in articles:
    result = extract_article(test["given"])
    assert result["title"] == test["expected"]["title"]
    assert result["date"] == test["expected"]["date"]
```

---

## Test URLs

### Listing Pages ({listing_count})
"""
        # Add listing URLs
        for i, key in enumerate(listing_keys[:10], 1):
            data = self._service.read(key)
            if data and isinstance(data, dict):
                url = data.get("url", "Unknown")
                test_plan += f"{i}. {url}\n"

        if listing_count > 10:
            test_plan += f"... and {listing_count - 10} more\n"
        elif listing_count == 0:
            test_plan += "No listing entries found.\n"

        test_plan += f"""
### Article Pages ({article_count})
"""
        # Add article URLs
        for i, key in enumerate(article_keys[:10], 1):
            data = self._service.read(key)
            if data and isinstance(data, dict):
                url = data.get("url", "Unknown")
                test_plan += f"{i}. {url}\n"

        if article_count > 10:
            test_plan += f"... and {article_count - 10} more\n"
        elif article_count == 0:
            test_plan += "No article entries found.\n"

        test_plan += f"""
---

## Notes

{test_description if test_description else "Test data generated automatically by crawler agent."}

- Listing pages are randomly sampled to avoid overfitting to specific structure
- Article pages are randomly selected from multiple listing pages
- HTML content is cleaned but preserves structure for selector testing
"""

        logger.info(f"Generated test.md for {site_name}")

        return {"success": True, "result": test_plan}

    def _build_expected_fields(self, detail_selectors: dict) -> str:
        """Build expected fields JSON based on discovered selectors."""
        # Default fields if nothing discovered
        if not detail_selectors:
            return '''        "title": "extracted title",
        "date": "publication date",
        "authors": ["author1", "author2"],
        "category": "category name",
        "content": "article content (truncated)"'''

        # Map field names to example values for test data
        field_examples = {
            "title": '"extracted title"',
            "date": '"2024-01-15"',
            "publication_date": '"2024-01-15"',
            "authors": '["author1", "author2"]',
            "author": '"Author Name"',
            "category": '"category name"',
            "content": '"article content (truncated)"',
            "body": '"article body text"',
            "lead": '"article lead/summary"',
            "summary": '"article summary"',
            "tags": '["tag1", "tag2"]',
            "language": '"en"',
            "breadcrumbs": '["Home", "Section"]',
            "files": '[{"name": "doc.pdf", "url": "/files/doc.pdf"}]',
            "attachments": '[{"name": "file.pdf", "url": "/file.pdf"}]',
            "related_articles": '[{"title": "Related", "url": "/related"}]',
            "images": '[{"src": "/img.jpg", "alt": "desc"}]',
        }

        lines = []
        for field, value in detail_selectors.items():
            # Check if selector chain has any valid selectors
            has_selectors = False
            if isinstance(value, list):
                has_selectors = any(item.get("selector") for item in value if isinstance(item, dict))
            elif isinstance(value, dict):
                has_selectors = bool(value.get("primary") or value.get("selector"))
            elif isinstance(value, str):
                has_selectors = bool(value)

            if has_selectors:
                example = field_examples.get(field.lower(), f'"{field} value"')
                lines.append(f'        "{field}": {example}')

        return ",\n".join(lines) if lines else '''        "title": "extracted title",
        "content": "article content"'''

    def get_parameters_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}
