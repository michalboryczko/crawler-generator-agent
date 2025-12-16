"""Selector extraction tools with isolated LLM contexts per page.

This module uses the new observability decorators for automatic logging.
The @traced_tool decorator handles all tool instrumentation.

Prompts are now managed through the centralized PromptProvider.
"""
import json
import logging
import time
from collections import Counter
from typing import Any
from urllib.parse import urljoin

from ..core.browser import BrowserSession
from ..core.html_cleaner import clean_html_for_llm
from ..core.json_parser import parse_json_response
from ..core.llm import LLMClient
from ..observability.decorators import traced_tool
from ..prompts import get_prompt_provider
from .base import BaseTool

logger = logging.getLogger(__name__)


def _get_listing_extraction_prompt() -> str:
    """Get the listing extraction prompt from PromptProvider."""
    provider = get_prompt_provider()
    return provider.get_extraction_prompt("listing")


def _get_article_extraction_prompt() -> str:
    """Get the article extraction prompt from PromptProvider."""
    provider = get_prompt_provider()
    return provider.get_extraction_prompt("article")


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

    @traced_tool(name="extract_listing_page")
    def execute(
        self,
        url: str,
        wait_seconds: int = 5,
        listing_container_selector: str | None = None
    ) -> dict[str, Any]:
        """Extract selectors and URLs from a listing page. Instrumented by @traced_tool."""
        logger.info(f"Extracting listing page: {url}")

        # Navigate to page
        self.browser.navigate(url)
        time.sleep(wait_seconds)

        # Get cleaned HTML
        html = self.browser.get_html()
        cleaned_html = clean_html_for_llm(html)

        # Truncate if too large (100KB limit - will use better model in future)
        if len(cleaned_html) > 150000:
            original_len = len(cleaned_html)
            cleaned_html = cleaned_html[:150000] + "\n... [TRUNCATED]"
            logger.warning(f"HTML truncated from {original_len} to 150000 chars")

        # Fresh LLM call with isolated context
        messages = [
            {"role": "system", "content": _get_listing_extraction_prompt()},
            {"role": "user", "content": f"Analyze this listing page HTML:\n\n{cleaned_html}"}
        ]

        response = self.llm.chat(messages)
        content = response.get("content", "")

        # Parse JSON response
        result = parse_json_response(content)

        if result:
            article_urls = result.get("article_urls", [])

            # Convert relative URLs to absolute
            article_urls = [urljoin(url, u) for u in article_urls if u and not u.startswith("...")]

            # Warn if too few URLs extracted
            if len(article_urls) < 5:
                logger.warning(
                    f"Only {len(article_urls)} URLs extracted from {url}. "
                    f"Expected 10-30. LLM may be missing main content."
                )

            logger.info(
                f"Extracted from {url}: "
                f"{len(article_urls)} article URLs, "
                f"selectors: {list(result.get('selectors', {}).keys())}"
            )

            return {
                "success": True,
                "url": url,
                "selectors": result.get("selectors", {}),
                "article_urls": article_urls,
                "notes": result.get("notes", "")
            }
        else:
            return {
                "success": False,
                "url": url,
                "error": "Failed to parse LLM response"
            }

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
                },
                "listing_container_selector": {
                    "type": "string",
                    "description": "Optional CSS selector to focus on main content container"
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

    @traced_tool(name="extract_article_page")
    def execute(
        self,
        url: str,
        wait_seconds: int = 5
    ) -> dict[str, Any]:
        """Extract detail selectors from an article page. Instrumented by @traced_tool."""
        logger.info(f"Extracting article page: {url}")

        # Navigate to page
        self.browser.navigate(url)
        time.sleep(wait_seconds)

        # Get cleaned HTML
        html = self.browser.get_html()
        cleaned_html = clean_html_for_llm(html)

        # Truncate if too large
        if len(cleaned_html) > 50000:
            original_len = len(cleaned_html)
            cleaned_html = cleaned_html[:50000] + "\n... [TRUNCATED]"
            logger.warning(f"HTML truncated from {original_len} to 50000 chars")

        # Fresh LLM call with isolated context
        messages = [
            {"role": "system", "content": _get_article_extraction_prompt()},
            {"role": "user", "content": f"Analyze this article page HTML:\n\n{cleaned_html}"}
        ]

        response = self.llm.chat(messages)
        content = response.get("content", "")

        # Parse JSON response
        result = parse_json_response(content)

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

    @traced_tool(name="aggregate_selectors")
    def execute(
        self,
        listing_extractions: list[dict],
        article_extractions: list[dict]
    ) -> dict[str, Any]:
        """Aggregate selectors into ordered chains. Instrumented by @traced_tool."""
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

    def _aggregate_listing_selectors(self, extractions: list[dict]) -> dict:
        """Aggregate listing selectors into chains ordered by success rate."""
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
        # Use PromptProvider template for selector aggregation
        provider = get_prompt_provider()
        selector_variations_json = json.dumps(
            {k: dict(Counter(v)) for k, v in selector_variations.items()},
            indent=2
        )
        prompt = provider.render_prompt(
            "selector_aggregation",
            total_pages=total_pages,
            selector_variations_json=selector_variations_json
        )

        messages = [
            {"role": "system", "content": "You are a CSS selector analyst. Create ordered selector chains with ALL working selectors. Respond with JSON only."},
            {"role": "user", "content": prompt}
        ]

        try:
            response = self.llm.chat(messages)
            content = response.get("content", "")
            result = parse_json_response(content)

            if result and "selectors" in result:
                # Merge LLM analysis with our frequency data
                return self._merge_with_frequency_data(result, selector_variations, total_pages)

        except Exception as e:
            logger.warning(f"LLM aggregation failed, using frequency-based fallback: {e}")

        # Fallback: build chains from frequency data
        return self._fallback_chain_aggregation(selector_variations, total_pages)

    def _merge_with_frequency_data(self, llm_result: dict, variations: dict, total_pages: int) -> dict:
        """Merge LLM ordering with frequency/success rate data."""
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
