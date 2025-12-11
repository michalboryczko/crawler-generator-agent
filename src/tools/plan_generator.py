"""Plan generation tool with comprehensive templates."""
import logging
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

from .base import BaseTool
from .memory import MemoryStore

logger = logging.getLogger(__name__)


class GeneratePlanTool(BaseTool):
    """Generate comprehensive plan.md from memory data."""

    name = "generate_plan_md"
    description = """Generate a comprehensive crawl plan from data stored in memory.
    Reads all collected data and produces detailed markdown documentation."""

    def __init__(self, memory_store: MemoryStore):
        self.memory_store = memory_store

    def execute(self) -> dict[str, Any]:
        try:
            # Read all data from memory
            target_url = self.memory_store.read("target_url") or "Unknown"
            article_selector = self.memory_store.read("article_selector") or "Not found"
            article_confidence = self.memory_store.read("article_selector_confidence") or 0
            pagination_selector = self.memory_store.read("pagination_selector") or "None"
            pagination_type = self.memory_store.read("pagination_type") or "none"
            pagination_max_pages = self.memory_store.read("pagination_max_pages")
            extracted_articles = self.memory_store.read("extracted_articles") or []
            accessibility = self.memory_store.read("accessibility_result") or {}
            detail_selectors = self.memory_store.read("detail_selectors") or {}
            listing_selectors = self.memory_store.read("listing_selectors") or {}

            # Parse URL for site info
            parsed = urlparse(target_url)
            site_name = parsed.netloc.replace("www.", "")
            base_url = f"{parsed.scheme}://{parsed.netloc}"

            # Determine browser requirement
            requires_browser = accessibility.get("requires_browser", True)
            listing_accessible = accessibility.get("listing_accessible", False)
            articles_accessible = accessibility.get("articles_accessible", False)

            # Build the comprehensive plan
            plan = self._build_header(site_name, target_url)
            plan += self._build_scope_section(target_url, pagination_max_pages)
            plan += self._build_start_urls_section(target_url, pagination_type, pagination_max_pages)
            plan += self._build_listing_section(article_selector, listing_selectors, article_confidence)
            plan += self._build_pagination_section(pagination_type, pagination_selector, pagination_max_pages)
            plan += self._build_detail_section(detail_selectors)
            plan += self._build_data_model_section(target_url, detail_selectors)
            plan += self._build_config_section(
                target_url, article_selector, pagination_selector,
                pagination_type, pagination_max_pages, requires_browser, detail_selectors
            )
            plan += self._build_accessibility_section(requires_browser, listing_accessible, articles_accessible)
            plan += self._build_sample_articles_section(extracted_articles)
            plan += self._build_notes_section(requires_browser)

            return {"success": True, "result": plan}
        except Exception as e:
            logger.error(f"Failed to generate plan: {e}")
            return {"success": False, "error": str(e)}

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

    def _build_scope_section(self, target_url: str, max_pages: int | None) -> str:
        parsed = urlparse(target_url)
        path = parsed.path.rstrip('/')

        section = """## 1. Scope & Objectives

**Goal:** Collect all articles/publications from this section, including:
- URL
- Title
- Publication date
- Author(s)
- Category/section
- Main content/body

**Coverage:**
"""
        if max_pages:
            section += f"- Listing pages: `{target_url}?page=N` (1 … ~{max_pages})\n"
        else:
            section += f"- Listing pages: `{target_url}` (pagination to be determined)\n"

        section += f"- Article detail pages: `{parsed.scheme}://{parsed.netloc}{path}/<slug>`\n\n---\n\n"
        return section

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

    def _build_listing_section(self, article_selector: str, listing_selectors: dict, confidence: float) -> str:
        section = f"""## 3. Listing Pages

### 3.1. Article blocks & links

**Purpose:** Discover article detail URLs and basic metadata from listing pages.

**Article link selector (verified):**
```css
{article_selector}
```
- **Confidence**: {confidence}

**Usage:**
- For each listing page, select all matching `<a>` elements.
- Extract:
  - `url`: resolve relative `href` against base URL
  - `title`: `textContent` of the `<a>`

"""
        if listing_selectors:
            section += "**Additional listing-level metadata:**\n\n"
            for field, selector in listing_selectors.items():
                if selector:
                    section += f"- **{field}:**\n  ```css\n  {selector}\n  ```\n\n"

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

Selectors below are inferred from site structure; validate on sample pages.

"""

        # Default selectors if none provided
        default_selectors = {
            "title": {
                "primary": "h1.article-title, .article-view h1",
                "description": "Main article title"
            },
            "date": {
                "primary": ".article-date, .publication-date, time[datetime]",
                "description": "Publication date"
            },
            "authors": {
                "primary": ".article-author a, .author-name, [rel='author']",
                "description": "Author name(s)"
            },
            "category": {
                "primary": ".article-category, .article-type a, .category",
                "description": "Article category/section"
            },
            "content": {
                "primary": ".article-content, .article-body, .entry-content, main article",
                "description": "Main article content"
            },
            "language": {
                "primary": "html[lang]",
                "description": "Page language from html attribute"
            }
        }

        selectors_to_use = detail_selectors if detail_selectors else default_selectors

        for i, (field, info) in enumerate(selectors_to_use.items(), 1):
            if isinstance(info, dict):
                selector = info.get("primary", info.get("selector", ""))
                desc = info.get("description", "")
            else:
                selector = info
                desc = ""

            section += f"""### 5.{i}. {field.title()}

**Selector:**
```css
{selector}
```
{f"*{desc}*" if desc else ""}

"""

        section += "---\n\n"
        return section

    def _build_data_model_section(self, target_url: str, detail_selectors: dict) -> str:
        parsed = urlparse(target_url)
        example_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}/example-article"

        return f"""## 6. Data Model

Recommended fields per article:

```json
{{
  "url": "{example_url}",
  "title": "Article Title",
  "publication_date": "2024-01-15",
  "authors": ["Author Name"],
  "category": "Category",
  "language": "en",
  "body_html": "<p>...</p>",
  "body_text": "...",
  "source_listing_page": "{target_url}?page=1"
}}
```

Notes:
- `publication_date` should come from the detail page, not the listing.
- `language` from `html[lang]`.
- `source_listing_page` is optional but useful for debugging.

---

"""

    def _build_config_section(
        self, target_url: str, article_selector: str, pagination_selector: str,
        pagination_type: str, max_pages: int | None, requires_browser: bool,
        detail_selectors: dict
    ) -> str:
        # Build detail selectors string
        detail_config = ""
        if detail_selectors:
            for field, info in detail_selectors.items():
                selector = info.get("primary", info) if isinstance(info, dict) else info
                detail_config += f'        "{field}_selector": "{selector}",\n'
        else:
            detail_config = '''        "title_selector": "h1.article-title, .article-view h1",
        "date_selector": ".article-date, .publication-date",
        "author_selector": ".article-author a, .author-name",
        "category_selector": ".article-category, .article-type a",
        "body_selector": ".article-content, .article-body",
        "language_selector": "html[lang]",
'''

        return f"""## 7. Crawler Configuration

```python
config = {{
    "start_url": "{target_url}",
    "listing": {{
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
{detail_config.rstrip().rstrip(',')}
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

---

"""

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

    def __init__(self, memory_store: MemoryStore):
        self.memory_store = memory_store

    def execute(self) -> dict[str, Any]:
        try:
            target_url = self.memory_store.read("target_url") or "Unknown"
            test_description = self.memory_store.read("test-data-description") or ""

            # Find all test data keys
            listing_keys = self.memory_store.search("test-data-listing-*")
            article_keys = self.memory_store.search("test-data-article-*")

            listing_count = len(listing_keys)
            article_count = len(article_keys)
            total_count = listing_count + article_count

            # Determine site name
            parsed = urlparse(target_url)
            site_name = parsed.netloc.replace("www.", "")

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

```json
{{
    "type": "article",
    "url": "article URL",
    "given": "HTML content of the article page",
    "expected": {{
        "title": "extracted title",
        "date": "publication date",
        "authors": ["author1", "author2"],
        "category": "category name",
        "content": "article content (truncated)"
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
                data = self.memory_store.read(key)
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
                data = self.memory_store.read(key)
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

            return {"success": True, "result": test_plan}
        except Exception as e:
            logger.error(f"Failed to generate test plan: {e}")
            return {"success": False, "error": str(e)}

    def get_parameters_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}
