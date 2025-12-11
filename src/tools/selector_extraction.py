"""Selector extraction tools with isolated LLM contexts per page."""
import json
import logging
import time
from typing import Any

from .base import BaseTool
from ..core.llm import LLMClient
from ..core.browser import BrowserSession
from ..core.html_cleaner import clean_html_for_llm

logger = logging.getLogger(__name__)

LISTING_EXTRACTION_PROMPT = """You are analyzing a listing page to extract CSS selectors and article URLs.

Given the HTML of a listing page, identify:
1. CSS selector for article blocks/containers
2. CSS selector for article title/link (the <a> element linking to article)
3. CSS selector for article date (if visible on listing)
4. CSS selector for article category/type (if visible on listing)
5. CSS selector for pagination elements
6. All article URLs found on this page

Respond with JSON only:
{
  "selectors": {
    "article_container": "CSS selector for article block",
    "article_link": "CSS selector for article title/link",
    "article_date": "CSS selector or null if not found",
    "article_category": "CSS selector or null if not found",
    "pagination": "CSS selector for pagination"
  },
  "article_urls": ["url1", "url2", "..."],
  "notes": "any observations about the page structure"
}"""

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
9. Related links or files (if present)

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
    "files": {"selector": "CSS selector or null", "found": true/false}
  },
  "extracted_values": {
    "title": "actual title text found",
    "date": "actual date found",
    "authors": ["author names found"]
  },
  "notes": "observations about page structure"
}"""


class ListingPageExtractorTool(BaseTool):
    """Extract selectors and article URLs from a single listing page.

    Uses isolated LLM context - each call is independent with no history.
    """

    name = "extract_listing_page"
    description = """Navigate to a listing page and extract CSS selectors for article
    elements plus all article URLs. Uses fresh LLM context for each page."""

    def __init__(self, llm: LLMClient, browser: BrowserSession):
        self.llm = llm
        self.browser = browser

    def execute(
        self,
        url: str,
        wait_seconds: int = 5
    ) -> dict[str, Any]:
        """Extract selectors and URLs from a listing page.

        Args:
            url: URL of the listing page to analyze
            wait_seconds: Time to wait for page load (default: 5)

        Returns:
            dict with selectors, article_urls, and metadata
        """
        try:
            logger.info(f"Extracting listing page: {url}")

            # Navigate to page
            self.browser.navigate(url)
            time.sleep(wait_seconds)

            # Get cleaned HTML
            html = self.browser.get_html()
            cleaned_html = clean_html_for_llm(html)

            # Truncate if too large (keep first 40KB for LLM)
            if len(cleaned_html) > 40000:
                cleaned_html = cleaned_html[:40000] + "\n... [TRUNCATED]"

            # Fresh LLM call with isolated context
            messages = [
                {"role": "system", "content": LISTING_EXTRACTION_PROMPT},
                {"role": "user", "content": f"Analyze this listing page HTML:\n\n{cleaned_html}"}
            ]

            response = self.llm.chat(messages)
            content = response.get("content", "")

            # Parse JSON response
            result = self._parse_json_response(content)

            if result:
                logger.info(
                    f"Extracted from {url}: "
                    f"{len(result.get('article_urls', []))} article URLs, "
                    f"selectors: {list(result.get('selectors', {}).keys())}"
                )
                return {
                    "success": True,
                    "url": url,
                    "selectors": result.get("selectors", {}),
                    "article_urls": result.get("article_urls", []),
                    "notes": result.get("notes", "")
                }
            else:
                return {
                    "success": False,
                    "url": url,
                    "error": "Failed to parse LLM response"
                }

        except Exception as e:
            logger.error(f"Failed to extract listing page {url}: {e}")
            return {
                "success": False,
                "url": url,
                "error": str(e)
            }

    def _parse_json_response(self, content: str) -> dict | None:
        """Parse JSON from LLM response, handling markdown code blocks."""
        try:
            # Try direct parse first
            return json.loads(content.strip())
        except json.JSONDecodeError:
            pass

        # Try extracting from code blocks
        try:
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0]
                return json.loads(json_str.strip())
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0]
                return json.loads(json_str.strip())
        except (json.JSONDecodeError, IndexError):
            pass

        # Try finding JSON object in response
        try:
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(content[start:end])
        except json.JSONDecodeError:
            pass

        return None

    def get_parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL of the listing page to analyze"
                },
                "wait_seconds": {
                    "type": "integer",
                    "description": "Time to wait for page load (default: 5)"
                }
            },
            "required": ["url"]
        }


class ArticlePageExtractorTool(BaseTool):
    """Extract detail selectors from a single article page.

    Uses isolated LLM context - each call is independent with no history.
    """

    name = "extract_article_page"
    description = """Navigate to an article page and extract CSS selectors for all
    content fields (title, date, author, content, etc). Uses fresh LLM context."""

    def __init__(self, llm: LLMClient, browser: BrowserSession):
        self.llm = llm
        self.browser = browser

    def execute(
        self,
        url: str,
        wait_seconds: int = 5
    ) -> dict[str, Any]:
        """Extract detail selectors from an article page.

        Args:
            url: URL of the article page to analyze
            wait_seconds: Time to wait for page load (default: 5)

        Returns:
            dict with selectors, extracted_values, and metadata
        """
        try:
            logger.info(f"Extracting article page: {url}")

            # Navigate to page
            self.browser.navigate(url)
            time.sleep(wait_seconds)

            # Get cleaned HTML
            html = self.browser.get_html()
            cleaned_html = clean_html_for_llm(html)

            # Truncate if too large
            if len(cleaned_html) > 50000:
                cleaned_html = cleaned_html[:50000] + "\n... [TRUNCATED]"

            # Fresh LLM call with isolated context
            messages = [
                {"role": "system", "content": ARTICLE_EXTRACTION_PROMPT},
                {"role": "user", "content": f"Analyze this article page HTML:\n\n{cleaned_html}"}
            ]

            response = self.llm.chat(messages)
            content = response.get("content", "")

            # Parse JSON response
            result = self._parse_json_response(content)

            if result:
                selectors = result.get("selectors", {})
                found_count = sum(1 for s in selectors.values() if s.get("found", False))
                logger.info(
                    f"Extracted from {url}: "
                    f"{found_count}/{len(selectors)} selectors found"
                )
                return {
                    "success": True,
                    "url": url,
                    "selectors": selectors,
                    "extracted_values": result.get("extracted_values", {}),
                    "notes": result.get("notes", "")
                }
            else:
                return {
                    "success": False,
                    "url": url,
                    "error": "Failed to parse LLM response"
                }

        except Exception as e:
            logger.error(f"Failed to extract article page {url}: {e}")
            return {
                "success": False,
                "url": url,
                "error": str(e)
            }

    def _parse_json_response(self, content: str) -> dict | None:
        """Parse JSON from LLM response, handling markdown code blocks."""
        try:
            return json.loads(content.strip())
        except json.JSONDecodeError:
            pass

        try:
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0]
                return json.loads(json_str.strip())
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0]
                return json.loads(json_str.strip())
        except (json.JSONDecodeError, IndexError):
            pass

        try:
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(content[start:end])
        except json.JSONDecodeError:
            pass

        return None

    def get_parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL of the article page to analyze"
                },
                "wait_seconds": {
                    "type": "integer",
                    "description": "Time to wait for page load (default: 5)"
                }
            },
            "required": ["url"]
        }


class SelectorAggregatorTool(BaseTool):
    """Aggregate selectors from multiple page extractions into selector chains.

    Instead of picking ONE best selector, preserves ALL working selectors as a
    chain (ordered by success rate). The crawler plan will try selectors in order
    until one matches.
    """

    name = "aggregate_selectors"
    description = """Compare selectors extracted from multiple pages and create
    selector chains (ordered lists of all working selectors). Returns selector
    chains that the crawler can try in order until one matches."""

    def __init__(self, llm: LLMClient):
        self.llm = llm

    def execute(
        self,
        listing_extractions: list[dict],
        article_extractions: list[dict]
    ) -> dict[str, Any]:
        """Aggregate selectors into ordered chains.

        Args:
            listing_extractions: Results from ListingPageExtractorTool for each page
            article_extractions: Results from ArticlePageExtractorTool for each page

        Returns:
            dict with listing_selectors and detail_selectors as selector chains
        """
        try:
            # Aggregate listing selectors into chains
            listing_result = self._aggregate_listing_selectors(listing_extractions)

            # Aggregate article selectors into chains
            article_result = self._aggregate_article_selectors(article_extractions)

            return {
                "success": True,
                "listing_selectors": listing_result["selectors"],
                "detail_selectors": article_result["selectors"],
                "analysis": {
                    "listing_pages_analyzed": len(listing_extractions),
                    "article_pages_analyzed": len(article_extractions),
                    "listing_notes": listing_result.get("notes", ""),
                    "article_notes": article_result.get("notes", "")
                }
            }

        except Exception as e:
            logger.error(f"Failed to aggregate selectors: {e}")
            return {"success": False, "error": str(e)}

    def _aggregate_listing_selectors(self, extractions: list[dict]) -> dict:
        """Aggregate listing selectors into chains ordered by success rate."""
        from collections import Counter

        # Collect all selector variations with counts
        selector_variations = {}
        total_pages = len([e for e in extractions if e.get("success")])

        for extraction in extractions:
            if not extraction.get("success"):
                continue
            selectors = extraction.get("selectors", {})
            for key, value in selectors.items():
                if key not in selector_variations:
                    selector_variations[key] = []
                if value:
                    selector_variations[key].append(value)

        # Build selector chains ordered by frequency (most common first)
        selectors = {}
        for key, values in selector_variations.items():
            if values:
                counter = Counter(values)
                # Create ordered chain with all unique selectors
                chain = []
                for selector, count in counter.most_common():
                    success_rate = count / total_pages if total_pages > 0 else 0
                    chain.append({
                        "selector": selector,
                        "success_rate": round(success_rate, 2),
                        "found_on_pages": count
                    })
                selectors[key] = chain
            else:
                selectors[key] = []

        return {
            "selectors": selectors,
            "notes": f"Created selector chains from {total_pages} listing pages"
        }

    def _aggregate_article_selectors(self, extractions: list[dict]) -> dict:
        """Aggregate article selectors into chains ordered by success rate."""
        from collections import Counter

        # Collect all selector variations with counts
        selector_variations = {}
        total_pages = len([e for e in extractions if e.get("success")])

        for extraction in extractions:
            if not extraction.get("success"):
                continue
            selectors = extraction.get("selectors", {})
            for key, value in selectors.items():
                if key not in selector_variations:
                    selector_variations[key] = []
                # Handle both dict format {selector: ..., found: ...} and string format
                if isinstance(value, dict) and value.get("selector"):
                    selector_variations[key].append(value["selector"])
                elif isinstance(value, str) and value:
                    selector_variations[key].append(value)

        # Use LLM to analyze and order the selector chains
        prompt = f"""Analyze these CSS selectors extracted from {total_pages} article pages.
For each field, create an ORDERED CHAIN of all working selectors (not just one!).
Order them by reliability - most reliable first, fallbacks after.

The crawler will try each selector in order until one matches.

Selector variations found (with counts):
{json.dumps({k: dict(Counter(v)) for k, v in selector_variations.items()}, indent=2)}

Respond with JSON only:
{{
  "selectors": {{
    "title": [
      {{"selector": "most reliable selector", "priority": 1, "notes": "why this is primary"}},
      {{"selector": "fallback selector", "priority": 2, "notes": "when to use this"}}
    ],
    "date": [...],
    "authors": [...],
    "lead": [...],
    "content": [...],
    "category": [...],
    "tags": [...],
    "breadcrumbs": [...],
    "files": [...]
  }},
  "notes": "overall analysis"
}}

IMPORTANT: Include ALL selectors that worked on any page, not just the most common one.
The crawler needs fallbacks for pages with different structures."""

        messages = [
            {"role": "system", "content": "You are a CSS selector analyst. Create ordered selector chains with ALL working selectors. Respond with JSON only."},
            {"role": "user", "content": prompt}
        ]

        try:
            response = self.llm.chat(messages)
            content = response.get("content", "")
            result = self._parse_json_response(content)

            if result and "selectors" in result:
                # Merge LLM analysis with our frequency data
                return self._merge_with_frequency_data(result, selector_variations, total_pages)

        except Exception as e:
            logger.warning(f"LLM aggregation failed, using frequency-based fallback: {e}")

        # Fallback: build chains from frequency data
        return self._fallback_chain_aggregation(selector_variations, total_pages)

    def _merge_with_frequency_data(self, llm_result: dict, variations: dict, total_pages: int) -> dict:
        """Merge LLM ordering with frequency/success rate data."""
        from collections import Counter

        selectors = llm_result.get("selectors", {})

        for key, chain in selectors.items():
            if not isinstance(chain, list):
                continue

            # Add success rate to each selector in chain
            freq_data = Counter(variations.get(key, []))
            for item in chain:
                if isinstance(item, dict) and "selector" in item:
                    selector = item["selector"]
                    count = freq_data.get(selector, 0)
                    item["success_rate"] = round(count / total_pages, 2) if total_pages > 0 else 0
                    item["found_on_pages"] = count

            # Ensure all found selectors are in the chain
            existing_selectors = {item.get("selector") for item in chain if isinstance(item, dict)}
            for selector, count in freq_data.items():
                if selector and selector not in existing_selectors:
                    chain.append({
                        "selector": selector,
                        "priority": len(chain) + 1,
                        "success_rate": round(count / total_pages, 2) if total_pages > 0 else 0,
                        "found_on_pages": count,
                        "notes": "additional selector found"
                    })

        return {
            "selectors": selectors,
            "notes": llm_result.get("notes", f"Selector chains from {total_pages} article pages")
        }

    def _fallback_chain_aggregation(self, variations: dict, total_pages: int) -> dict:
        """Fallback: build selector chains from frequency data only."""
        from collections import Counter

        selectors = {}
        for key, values in variations.items():
            if values:
                counter = Counter(values)
                chain = []
                priority = 1
                for selector, count in counter.most_common():
                    chain.append({
                        "selector": selector,
                        "priority": priority,
                        "success_rate": round(count / total_pages, 2) if total_pages > 0 else 0,
                        "found_on_pages": count,
                        "notes": "primary" if priority == 1 else "fallback"
                    })
                    priority += 1
                selectors[key] = chain
            else:
                selectors[key] = []

        return {
            "selectors": selectors,
            "notes": f"Fallback chain aggregation from {total_pages} pages"
        }

    def _parse_json_response(self, content: str) -> dict | None:
        """Parse JSON from LLM response."""
        try:
            return json.loads(content.strip())
        except json.JSONDecodeError:
            pass

        try:
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0]
                return json.loads(json_str.strip())
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0]
                return json.loads(json_str.strip())
        except (json.JSONDecodeError, IndexError):
            pass

        try:
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(content[start:end])
        except json.JSONDecodeError:
            pass

        return None

    def get_parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "listing_extractions": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "Results from ListingPageExtractorTool for each page"
                },
                "article_extractions": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "Results from ArticlePageExtractorTool for each page"
                }
            },
            "required": ["listing_extractions", "article_extractions"]
        }
