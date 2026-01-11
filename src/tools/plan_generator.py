"""Test plan generation tool.

This module provides GenerateTestPlanTool for generating test documentation.
Plan generation is now handled by PlanGeneratorAgent (see src/agents/plan_generator_agent.py).
"""

import logging
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from ..observability.decorators import traced_tool
from .base import BaseTool
from .validation import validated_tool

if TYPE_CHECKING:
    from ..services.memory_service import MemoryService

logger = logging.getLogger(__name__)


class GenerateTestPlanTool(BaseTool):
    """Generate structured test.md from memory data."""

    name = "generate_test_md"
    description = """Generate test documentation from test data stored in memory.
    Documents both listing and article test entries."""

    def __init__(self, memory_service: "MemoryService"):
        self._service = memory_service

    @traced_tool(name="generate_test_md")
    @validated_tool
    def execute(self, **kwargs: Any) -> dict[str, Any]:
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
                has_selectors = any(
                    item.get("selector") for item in value if isinstance(item, dict)
                )
            elif isinstance(value, dict):
                has_selectors = bool(value.get("primary") or value.get("selector"))
            elif isinstance(value, str):
                has_selectors = bool(value)

            if has_selectors:
                example = field_examples.get(field.lower(), f'"{field} value"')
                lines.append(f'        "{field}": {example}')

        return (
            ",\n".join(lines)
            if lines
            else '''        "title": "extracted title",
        "content": "article content"'''
        )
