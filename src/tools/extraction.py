"""Extraction tools that process data with separate agent contexts.

This module uses the new observability decorators for automatic logging.
The @traced_tool decorator handles all tool instrumentation.

Prompts are now managed through the centralized PromptProvider.
"""

import json
import time
from typing import TYPE_CHECKING, Any

from ..core.browser import BrowserSession
from ..core.html_cleaner import clean_html_for_llm
from ..core.json_parser import parse_json_response
from ..observability.decorators import traced_tool
from ..prompts import get_prompt_provider
from .base import BaseTool
from .validation import validated_tool

if TYPE_CHECKING:
    from ..services.memory_service import MemoryService

# Type alias for extraction field values: simple string, list of strings, or list of dicts
FieldValue = str | list[str] | list[dict[str, str]]


class FetchAndStoreHTMLTool(BaseTool):
    """Fetch a URL and store HTML in memory without returning to LLM."""

    name = "fetch_and_store_html"
    description = """Fetch a URL using the browser and store the HTML in memory.
    The HTML is NOT returned to you - only a confirmation.
    Use this for batch fetching where you don't need to see the content."""

    def __init__(self, browser_session: BrowserSession, memory_service: "MemoryService"):
        self.browser_session = browser_session
        self._service = memory_service

    @traced_tool(name="fetch_and_store_html")
    @validated_tool
    def execute(self, **kwargs: Any) -> dict[str, Any]:
        """Fetch URL and store in memory. Instrumented by @traced_tool."""
        url = kwargs["url"]
        memory_key = kwargs["memory_key"]
        wait_seconds = kwargs.get("wait_seconds", 3)
        self.browser_session.navigate(url)
        time.sleep(wait_seconds)

        html = self.browser_session.get_html()
        cleaned_html = clean_html_for_llm(html)

        self._service.write(
            memory_key, {"url": url, "html": cleaned_html, "html_length": len(cleaned_html)}
        )

        return {
            "success": True,
            "result": f"Stored HTML ({len(cleaned_html)} bytes) at key: {memory_key}",
            "url": url,
            "memory_key": memory_key,
        }


class BatchFetchURLsTool(BaseTool):
    """Fetch multiple URLs in sequence and store in memory."""

    name = "batch_fetch_urls"
    description = """Fetch multiple URLs and store their HTML in memory.
    Each URL is stored with key pattern: {key_prefix}-{index}.
    Returns only a summary, not the HTML content."""

    def __init__(self, browser_session: BrowserSession, memory_service: "MemoryService"):
        self.browser_session = browser_session
        self._service = memory_service

    @traced_tool(name="batch_fetch_urls")
    @validated_tool
    def execute(self, **kwargs: Any) -> dict[str, Any]:
        """Fetch multiple URLs. Instrumented by @traced_tool."""
        urls = kwargs["urls"]
        key_prefix = kwargs.get("key_prefix", "fetched")
        wait_seconds = kwargs.get("wait_seconds", 3)
        results = []
        for i, url in enumerate(urls):
            try:
                self.browser_session.navigate(url)
                time.sleep(wait_seconds)

                html = self.browser_session.get_html()
                cleaned_html = clean_html_for_llm(html)

                memory_key = f"{key_prefix}-{i + 1}"
                self._service.write(
                    memory_key, {"url": url, "html": cleaned_html, "html_length": len(cleaned_html)}
                )

                results.append(
                    {
                        "url": url,
                        "memory_key": memory_key,
                        "success": True,
                        "html_length": len(cleaned_html),
                    }
                )

            except Exception as e:
                results.append({"url": url, "success": False, "error": str(e)})

        successful = sum(1 for r in results if r.get("success"))

        return {
            "success": successful > 0,
            "result": f"Fetched {successful}/{len(urls)} URLs",
            "fetched_count": successful,
            "failed_count": len(urls) - successful,
            "memory_keys": [r["memory_key"] for r in results if r.get("success")],
        }


class RunExtractionAgentTool(BaseTool):
    """Run a fresh extraction agent on stored HTML."""

    name = "run_extraction_agent"
    description = """Run an extraction agent with fresh LLM context on a stored HTML.
    The agent reads HTML from memory, extracts data, and stores result.
    Each call creates a completely separate LLM conversation."""

    def __init__(self, llm_client, memory_service: "MemoryService"):
        self.llm = llm_client
        self._service = memory_service

    @traced_tool(name="run_extraction_agent")
    @validated_tool
    def execute(self, **kwargs: Any) -> dict[str, Any]:
        """Run extraction agent on stored HTML. Instrumented by @traced_tool."""
        html_memory_key = kwargs["html_memory_key"]
        output_memory_key = kwargs["output_memory_key"]
        stored = self._service.read(html_memory_key)
        if not stored:
            return {"success": False, "error": f"No HTML at: {html_memory_key}"}

        html = stored.get("html", "")
        url = stored.get("url", "")

        # Truncate for LLM
        if len(html) > 150000:
            html = html[:150000] + "\n... [TRUNCATED]"

        # Get discovered selectors for dynamic field extraction
        detail_selectors = self._service.read("detail_selectors") or {}

        # Build dynamic extraction prompt based on discovered fields
        extraction_prompt = self._build_extraction_prompt(detail_selectors)

        messages = [
            {"role": "system", "content": extraction_prompt},
            {"role": "user", "content": f"URL: {url}\n\nHTML:\n{html}"},
        ]

        response = self.llm.chat(messages)
        extracted_text = response.get("content", "{}")

        # Parse JSON using shared parser
        extracted = parse_json_response(extracted_text, allow_array=False)
        if extracted is None:
            extracted = {"error": "No JSON found", "raw": extracted_text[:200]}

        # Create test entry
        test_entry = {
            "type": "article",
            "url": url,
            "given": stored.get("html", ""),
            "expected": extracted,
        }

        self._service.write(output_memory_key, test_entry)

        return {
            "success": True,
            "result": f"Extracted to: {output_memory_key}",
            "fields": list(extracted.keys()) if isinstance(extracted, dict) else [],
        }

    def _build_extraction_prompt(self, detail_selectors: dict) -> str:
        """Build dynamic extraction prompt based on discovered selectors."""
        # Default fields if no selectors discovered
        default_fields: dict[str, FieldValue] = {
            "title": "article title",
            "date": "publication date or null",
            "authors": ["author1", "author2"],
            "content": "first 500 characters of main content",
        }

        fields: dict[str, FieldValue]
        if not detail_selectors:
            fields = default_fields
        else:
            # Build fields from discovered selectors
            fields = {}
            for field_name, selector_chain in detail_selectors.items():
                if not selector_chain:
                    continue

                if field_name in ["authors", "tags"]:
                    fields[field_name] = ["value1", "value2"]
                elif field_name in ["files", "attachments", "images", "related_articles"]:
                    fields[field_name] = [{"url": "...", "title": "..."}]
                elif field_name == "content":
                    fields[field_name] = "first 500 characters of main content"
                elif field_name == "breadcrumbs":
                    fields[field_name] = ["Home", "Section", "Article"]
                else:
                    fields[field_name] = f"{field_name} value or null"

            if "title" not in fields:
                fields["title"] = "article title"
            if "content" not in fields:
                fields["content"] = "first 500 characters of main content"

        json_example = json.dumps(fields, indent=4)

        # Build selector hints string
        selector_hints = ""
        if detail_selectors:
            hints = []
            for field_name, selector_chain in detail_selectors.items():
                if isinstance(selector_chain, list) and len(selector_chain) > 0:
                    primary = selector_chain[0]
                    selector = (
                        primary.get("selector", "") if isinstance(primary, dict) else str(primary)
                    )
                    if selector:
                        hints.append(f"- {field_name}: use selector '{selector}'")
            if hints:
                selector_hints = "\n".join(hints)

        # Use PromptProvider template
        provider = get_prompt_provider()
        return provider.render_prompt(
            "article_extraction", json_example=json_example, selector_hints=selector_hints
        )


class BatchExtractArticlesTool(BaseTool):
    """Run extraction agent on multiple stored article HTML pages."""

    name = "batch_extract_articles"
    description = """Run extraction on article HTML pages matching a key prefix.
    Each page is processed by a fresh extraction agent (separate LLM context).
    Results are stored as article test entries with type='article'."""

    def __init__(self, llm_client, memory_service: "MemoryService"):
        self.llm = llm_client
        self._service = memory_service

    @traced_tool(name="batch_extract_articles")
    @validated_tool
    def execute(self, **kwargs: Any) -> dict[str, Any]:
        """Extract from all article HTML with matching prefix. Instrumented by @traced_tool."""
        html_key_prefix = kwargs["html_key_prefix"]
        output_key_prefix = kwargs.get("output_key_prefix", "test-data-article")
        html_keys = self._service.search(f"{html_key_prefix}-*")

        if not html_keys:
            return {"success": False, "error": f"No HTML found with prefix: {html_key_prefix}"}

        extractor = RunExtractionAgentTool(self.llm, self._service)
        results = []

        for i, html_key in enumerate(html_keys):
            output_key = f"{output_key_prefix}-{i + 1}"
            result = extractor.execute(
                html_memory_key=html_key,
                output_memory_key=output_key,
            )
            results.append(
                {
                    "html_key": html_key,
                    "output_key": output_key,
                    "success": result.get("success", False),
                }
            )

        successful = sum(1 for r in results if r["success"])

        return {
            "success": successful > 0,
            "result": f"Extracted {successful}/{len(html_keys)} articles",
            "extracted_count": successful,
            "output_keys": [r["output_key"] for r in results if r["success"]],
        }


class RunListingExtractionAgentTool(BaseTool):
    """Run extraction agent on listing page HTML."""

    name = "run_listing_extraction_agent"
    description = """Run extraction agent on listing page HTML to extract article URLs.
    Creates a test entry with type='listing' containing article URLs found."""

    def __init__(self, llm_client, memory_service: "MemoryService"):
        self.llm = llm_client
        self._service = memory_service

    @traced_tool(name="run_listing_extraction_agent")
    @validated_tool
    def execute(self, **kwargs: Any) -> dict[str, Any]:
        """Extract article URLs from listing page HTML. Instrumented by @traced_tool."""
        html_memory_key = kwargs["html_memory_key"]
        output_memory_key = kwargs["output_memory_key"]
        article_selector = kwargs.get("article_selector")
        stored = self._service.read(html_memory_key)
        if not stored:
            return {"success": False, "error": f"No HTML at: {html_memory_key}"}

        html = stored.get("html", "")
        url = stored.get("url", "")

        # Try to extract just the main content area using listing_container_selector
        main_content_html = html
        listing_container_selector = self._service.read("listing_container_selector")

        if listing_container_selector:
            focused_html = self._extract_main_content(html, listing_container_selector)
            if focused_html and len(focused_html) < len(html):
                main_content_html = focused_html

        # Use LLM for extraction
        article_urls = self._extract_urls_with_llm(main_content_html, url, article_selector)

        extracted = {
            "article_urls": article_urls,
            "article_count": len(article_urls),
            "has_pagination": True,
            "next_page_url": None,
        }

        # Create listing test entry
        test_entry = {
            "type": "listing",
            "url": url,
            "given": stored.get("html", ""),
            "expected": extracted,
        }

        self._service.write(output_memory_key, test_entry)

        return {
            "success": True,
            "result": f"Extracted {len(article_urls)} article URLs to: {output_memory_key}",
            "article_urls": article_urls,
            "article_count": len(article_urls),
        }

    def _extract_main_content(self, html: str, container_selector: str) -> str | None:
        """Extract just the main content container HTML using the selector."""
        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html, "html.parser")
            container = soup.select_one(container_selector)
            if container:
                return str(container)
            return None
        except Exception:
            return None

    def _extract_urls_with_llm(
        self, html: str, url: str, article_selector: str | None
    ) -> list[str]:
        """Extract URLs using LLM."""
        if len(html) > 150000:
            html = html[:150000] + "\n... [TRUNCATED]"

        # Use PromptProvider template for listing URL extraction
        provider = get_prompt_provider()
        extraction_prompt = provider.render_prompt(
            "listing_url_extraction",
            page_url=url,
            base_url=url,
            selector_hint=article_selector or "",
        )

        messages = [
            {"role": "system", "content": extraction_prompt},
            {"role": "user", "content": f"Listing URL: {url}\n\nHTML:\n{html}"},
        ]

        response = self.llm.chat(messages)
        extracted_text = response.get("content", "{}")

        # Parse JSON using shared parser
        extracted = parse_json_response(extracted_text, allow_array=False)
        if extracted and isinstance(extracted, dict):
            return extracted.get("article_urls", [])

        return []


class BatchExtractListingsTool(BaseTool):
    """Run extraction on multiple listing pages."""

    name = "batch_extract_listings"
    description = """Run extraction on listing HTML pages matching a key prefix.
    Each page is processed by a fresh extraction agent.
    Results are stored as listing test entries with type='listing'.
    Also collects all article URLs found across all listings."""

    def __init__(self, llm_client, memory_service: "MemoryService"):
        self.llm = llm_client
        self._service = memory_service

    @traced_tool(name="batch_extract_listings")
    @validated_tool
    def execute(self, **kwargs: Any) -> dict[str, Any]:
        """Extract from all listing HTML with matching prefix. Instrumented by @traced_tool."""
        html_key_prefix = kwargs["html_key_prefix"]
        output_key_prefix = kwargs.get("output_key_prefix", "test-data-listing")
        article_selector = kwargs.get("article_selector")
        html_keys = self._service.search(f"{html_key_prefix}-*")

        if not html_keys:
            return {"success": False, "error": f"No HTML found with prefix: {html_key_prefix}"}

        extractor = RunListingExtractionAgentTool(self.llm, self._service)
        results = []
        all_article_urls = []

        for i, html_key in enumerate(html_keys):
            output_key = f"{output_key_prefix}-{i + 1}"
            result = extractor.execute(
                html_memory_key=html_key,
                output_memory_key=output_key,
                article_selector=article_selector,
            )
            extracted_urls = result.get("article_urls", [])
            results.append(
                {
                    "html_key": html_key,
                    "output_key": output_key,
                    "success": result.get("success", False),
                    "article_count": len(extracted_urls),
                }
            )
            if result.get("success") and extracted_urls:
                all_article_urls.extend(extracted_urls)

        successful = sum(1 for r in results if r["success"])

        # Deduplicate URLs while preserving order
        seen = set()
        unique_article_urls = []
        for url in all_article_urls:
            if url and url not in seen:
                seen.add(url)
                unique_article_urls.append(url)

        total_articles = len(unique_article_urls)

        # Store collected article URLs for later use
        self._service.write("extracted_listing_article_urls", unique_article_urls)
        self._service.write("collected_article_urls", unique_article_urls)

        return {
            "success": successful > 0,
            "result": f"Extracted {successful}/{len(html_keys)} listings, found {total_articles} unique article URLs",
            "extracted_count": successful,
            "total_article_urls": total_articles,
            "output_keys": [r["output_key"] for r in results if r["success"]],
            "article_urls_sample": unique_article_urls[:10] if unique_article_urls else [],
        }
