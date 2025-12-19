"""Dynamic prompt templates using Jinja2.

These templates use Jinja2 syntax for variable substitution and are
rendered with context at runtime via PromptProvider.render_prompt().
"""

from typing import TYPE_CHECKING

from ..template import PromptTemplate

if TYPE_CHECKING:
    from ..provider import PromptProvider

# Article extraction prompt - uses discovered selectors to build extraction instructions
ARTICLE_EXTRACTION_TEMPLATE = """You are an HTML extraction agent. Extract article data from this HTML.

Return ONLY a JSON object with these fields:
{{ json_example }}
{% if selector_hints %}

CSS SELECTOR HINTS:
{{ selector_hints }}
{% endif %}

REQUIREMENTS:
1. Extract actual values from the HTML, not placeholders
2. For arrays (authors, tags, files), return empty array [] if not found
3. For single values, return null if not found
4. content should be first 500 characters of main article body
5. files/attachments should include URL and title if present

Do not include any explanation, just the JSON."""


# Listing URL extraction prompt - extracts article URLs from listing pages
LISTING_URL_EXTRACTION_TEMPLATE = """You are extracting article URLs from a LISTING PAGE.

## YOUR TASK
Find ALL <a href="..."> links to individual articles in the HTML below.{% if selector_hint %}

USE THIS CSS SELECTOR to find article links: {{ selector_hint }}{% endif %}

## CRITICAL: Different pages have DIFFERENT articles!
This page URL is: {{ page_url }}
- If the URL has ?start=100, articles start from position 100
- If the URL has ?start=1000, articles start from position 1000
- Each listing page has DIFFERENT article URLs - they should NOT be the same!

## DO NOT EXTRACT from these (they're the same on EVERY page):
- Header section with "latest" or "featured" items
- Top navigation with recent articles
- Sidebar recommendations
- Footer links
- Any section labeled "popular", "trending", "recent"

## EXTRACT from the MAIN CONTENT AREA:
- The large repeated list of articles (10-20+ items)
- This is the section that CHANGES when you paginate

## Return JSON:
{
    "article_urls": ["https://example.com/article1", "https://example.com/article2", ...]
}

Expected: 10-30 URLs per page. If you find less than 5, you're probably looking at the header/sidebar!
Convert relative URLs to absolute using base: {{ base_url }}"""


# Pagination pattern detection prompt
PAGINATION_PATTERN_TEMPLATE = """Analyze these pagination URLs and identify the pagination pattern.

Base/Target URL: {{ target_url }}

Sample pagination links:
{% for link in pagination_links[:10] %}
{{ link }}
{% endfor %}

Identify:
1. What parameter controls pagination (page, offset, skip, start, p, etc.)
2. Is it page-based (page=1,2,3) or offset-based (offset=0,20,40) or something else?
3. What is the base URL without pagination params?
4. How to construct a URL for page N?

Respond with JSON only:
{
    "pattern_type": "page_number" or "offset" or "path_segment" or "other",
    "param_name": "the parameter name like 'page' or 'offset'",
    "base_url": "URL without pagination params",
    "url_template": "template with {n} placeholder, e.g. 'https://example.com?page={n}' or 'https://example.com?offset={n*20}'",
    "offset_multiplier": null or number (e.g., 20 if offset=0,20,40 for pages 1,2,3),
    "starts_at": 0 or 1 (whether first page is 0 or 1),
    "notes": "any observations"
}"""


# Article URL pattern grouping prompt
ARTICLE_URL_PATTERN_TEMPLATE = """Analyze these article URLs and identify distinct URL patterns.
Group them by their structural pattern (path structure, not content).

URLs to analyze:
{% for url in sample_urls %}
{{ url }}
{% endfor %}

Respond with JSON only:
{
  "patterns": [
    {
      "pattern_name": "descriptive name like 'slug-based' or 'year/month/slug'",
      "pattern_regex": "regex to match this pattern",
      "example_urls": ["url1", "url2"]
    }
  ]
}"""


# Selector chain aggregation prompt
SELECTOR_AGGREGATION_TEMPLATE = """Analyze these CSS selectors extracted from {{ total_pages }} article pages.
For each field, create an ORDERED CHAIN of all working selectors (not just one!).
Order them by reliability - most reliable first, fallbacks after.

The crawler will try each selector in order until one matches.

Selector variations found (with counts):
{{ selector_variations_json }}

Respond with JSON only:
{
  "selectors": {
    "title": [
      {"selector": "most reliable selector", "priority": 1, "notes": "why this is primary"},
      {"selector": "fallback selector", "priority": 2, "notes": "when to use this"}
    ],
    "date": [...],
    "authors": [...],
    "lead": [...],
    "content": [...],
    "category": [...],
    "tags": [...],
    "breadcrumbs": [...],
    "files": [...]
  },
  "notes": "overall analysis"
}

IMPORTANT: Include ALL selectors that worked on any page, not just the most common one.
The crawler needs fallbacks for pages with different structures."""


def register_dynamic_templates(provider: "PromptProvider") -> None:
    """Register all dynamic templates with the provider."""
    provider.register_template(
        "article_extraction", PromptTemplate(ARTICLE_EXTRACTION_TEMPLATE, name="article_extraction")
    )

    provider.register_template(
        "listing_url_extraction",
        PromptTemplate(LISTING_URL_EXTRACTION_TEMPLATE, name="listing_url_extraction"),
    )

    provider.register_template(
        "pagination_pattern", PromptTemplate(PAGINATION_PATTERN_TEMPLATE, name="pagination_pattern")
    )

    provider.register_template(
        "article_url_pattern",
        PromptTemplate(ARTICLE_URL_PATTERN_TEMPLATE, name="article_url_pattern"),
    )

    provider.register_template(
        "selector_aggregation",
        PromptTemplate(SELECTOR_AGGREGATION_TEMPLATE, name="selector_aggregation"),
    )
