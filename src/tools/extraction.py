"""Extraction tools that process data with separate agent contexts."""
import logging
import json
from typing import Any

from .base import BaseTool
from .memory import MemoryStore
from ..core.browser import BrowserSession
from ..core.html_cleaner import clean_html_for_llm

logger = logging.getLogger(__name__)


class FetchAndStoreHTMLTool(BaseTool):
    """Fetch a URL and store HTML in memory without returning to LLM."""

    name = "fetch_and_store_html"
    description = """Fetch a URL using the browser and store the HTML in memory.
    The HTML is NOT returned to you - only a confirmation.
    Use this for batch fetching where you don't need to see the content."""

    def __init__(self, browser_session: BrowserSession, memory_store: MemoryStore):
        self.browser_session = browser_session
        self.memory_store = memory_store

    def execute(self, url: str, memory_key: str, wait_seconds: int = 3) -> dict[str, Any]:
        """Fetch URL and store in memory."""
        try:
            import time

            self.browser_session.navigate(url)
            time.sleep(wait_seconds)

            html = self.browser_session.get_html()
            cleaned_html = clean_html_for_llm(html)

            self.memory_store.write(memory_key, {
                "url": url,
                "html": cleaned_html,
                "html_length": len(cleaned_html)
            })

            logger.info(f"Fetched and stored {url} -> {memory_key} ({len(cleaned_html)} bytes)")

            return {
                "success": True,
                "result": f"Stored HTML ({len(cleaned_html)} bytes) at key: {memory_key}",
                "url": url,
                "memory_key": memory_key
            }
        except Exception as e:
            logger.error(f"Failed to fetch {url}: {e}")
            return {"success": False, "error": str(e)}

    def get_parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to fetch"},
                "memory_key": {"type": "string", "description": "Memory key to store the HTML"},
                "wait_seconds": {"type": "integer", "description": "Seconds to wait (default: 3)"}
            },
            "required": ["url", "memory_key"]
        }


class BatchFetchURLsTool(BaseTool):
    """Fetch multiple URLs in sequence and store in memory."""

    name = "batch_fetch_urls"
    description = """Fetch multiple URLs and store their HTML in memory.
    Each URL is stored with key pattern: {key_prefix}-{index}.
    Returns only a summary, not the HTML content."""

    def __init__(self, browser_session: BrowserSession, memory_store: MemoryStore):
        self.browser_session = browser_session
        self.memory_store = memory_store

    def execute(
        self,
        urls: list[str],
        key_prefix: str = "fetched",
        wait_seconds: int = 3
    ) -> dict[str, Any]:
        """Fetch multiple URLs."""
        import time

        logger.info(f"BatchFetchURLsTool: Starting fetch of {len(urls)} URLs with prefix '{key_prefix}'")

        results = []
        for i, url in enumerate(urls):
            try:
                logger.info(f"BatchFetchURLsTool: Navigating to ({i+1}/{len(urls)}): {url}")
                self.browser_session.navigate(url)
                time.sleep(wait_seconds)

                html = self.browser_session.get_html()
                cleaned_html = clean_html_for_llm(html)

                memory_key = f"{key_prefix}-{i+1}"
                self.memory_store.write(memory_key, {
                    "url": url,
                    "html": cleaned_html,
                    "html_length": len(cleaned_html)
                })

                results.append({
                    "url": url,
                    "memory_key": memory_key,
                    "success": True,
                    "html_length": len(cleaned_html)
                })
                logger.info(f"Fetched {i+1}/{len(urls)}: {url}")

            except Exception as e:
                results.append({"url": url, "success": False, "error": str(e)})
                logger.error(f"Failed {i+1}/{len(urls)}: {url} - {e}")

        successful = sum(1 for r in results if r.get("success"))

        return {
            "success": successful > 0,
            "result": f"Fetched {successful}/{len(urls)} URLs",
            "fetched_count": successful,
            "failed_count": len(urls) - successful,
            "memory_keys": [r["memory_key"] for r in results if r.get("success")]
        }

    def get_parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "urls": {"type": "array", "items": {"type": "string"}, "description": "URLs to fetch"},
                "key_prefix": {"type": "string", "description": "Prefix for memory keys"},
                "wait_seconds": {"type": "integer", "description": "Wait seconds per page"}
            },
            "required": ["urls"]
        }


class RunExtractionAgentTool(BaseTool):
    """Run a fresh extraction agent on stored HTML."""

    name = "run_extraction_agent"
    description = """Run an extraction agent with fresh LLM context on a stored HTML.
    The agent reads HTML from memory, extracts data, and stores result.
    Each call creates a completely separate LLM conversation."""

    def __init__(self, llm_client, memory_store: MemoryStore):
        self.llm = llm_client
        self.memory_store = memory_store

    def execute(
        self,
        html_memory_key: str,
        output_memory_key: str
    ) -> dict[str, Any]:
        """Run extraction agent on stored HTML.

        Args:
            html_memory_key: Key containing {url, html}
            output_memory_key: Key to store test entry
        """
        try:
            stored = self.memory_store.read(html_memory_key)
            if not stored:
                return {"success": False, "error": f"No HTML at: {html_memory_key}"}

            html = stored.get("html", "")
            url = stored.get("url", "")

            # Truncate for LLM
            if len(html) > 40000:
                html = html[:40000] + "\n... [TRUNCATED]"

            # Fresh LLM context for extraction
            extraction_prompt = """You are an HTML extraction agent. Extract article data from this HTML.

Return ONLY a JSON object with these fields:
{
    "title": "article title",
    "date": "publication date or null",
    "authors": ["author1", "author2"] or [],
    "content": "first 500 characters of main content"
}

Do not include any explanation, just the JSON."""

            messages = [
                {"role": "system", "content": extraction_prompt},
                {"role": "user", "content": f"URL: {url}\n\nHTML:\n{html}"}
            ]

            logger.info(f"Running extraction agent for: {url}")
            response = self.llm.chat(messages)
            extracted_text = response.get("content", "{}")

            # Parse JSON
            try:
                import re
                json_match = re.search(r'\{[\s\S]*\}', extracted_text)
                if json_match:
                    extracted = json.loads(json_match.group())
                else:
                    extracted = {"error": "No JSON found", "raw": extracted_text[:200]}
            except json.JSONDecodeError as e:
                extracted = {"error": str(e), "raw": extracted_text[:200]}

            # Create test entry
            test_entry = {
                "type": "article",
                "url": url,
                "given": stored.get("html", ""),
                "expected": extracted
            }

            self.memory_store.write(output_memory_key, test_entry)
            logger.info(f"Extraction complete: {html_memory_key} -> {output_memory_key}")

            return {
                "success": True,
                "result": f"Extracted to: {output_memory_key}",
                "fields": list(extracted.keys()) if isinstance(extracted, dict) else []
            }
        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            return {"success": False, "error": str(e)}

    def get_parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "html_memory_key": {"type": "string", "description": "Key containing stored HTML"},
                "output_memory_key": {"type": "string", "description": "Key to store result"}
            },
            "required": ["html_memory_key", "output_memory_key"]
        }


class BatchExtractArticlesTool(BaseTool):
    """Run extraction agent on multiple stored article HTML pages."""

    name = "batch_extract_articles"
    description = """Run extraction on article HTML pages matching a key prefix.
    Each page is processed by a fresh extraction agent (separate LLM context).
    Results are stored as article test entries with type='article'."""

    def __init__(self, llm_client, memory_store: MemoryStore):
        self.llm = llm_client
        self.memory_store = memory_store

    def execute(
        self,
        html_key_prefix: str,
        output_key_prefix: str = "test-data-article"
    ) -> dict[str, Any]:
        """Extract from all article HTML with matching prefix."""
        html_keys = self.memory_store.search(f"{html_key_prefix}-*")

        if not html_keys:
            return {"success": False, "error": f"No HTML found with prefix: {html_key_prefix}"}

        extractor = RunExtractionAgentTool(self.llm, self.memory_store)
        results = []

        for i, html_key in enumerate(html_keys):
            output_key = f"{output_key_prefix}-{i+1}"
            result = extractor.execute(html_key, output_key)
            results.append({
                "html_key": html_key,
                "output_key": output_key,
                "success": result.get("success", False)
            })

        successful = sum(1 for r in results if r["success"])

        return {
            "success": successful > 0,
            "result": f"Extracted {successful}/{len(html_keys)} articles",
            "extracted_count": successful,
            "output_keys": [r["output_key"] for r in results if r["success"]]
        }

    def get_parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "html_key_prefix": {"type": "string", "description": "Prefix to find article HTML keys"},
                "output_key_prefix": {"type": "string", "description": "Prefix for output keys (default: test-data-article)"}
            },
            "required": ["html_key_prefix"]
        }


class RunListingExtractionAgentTool(BaseTool):
    """Run extraction agent on listing page HTML."""

    name = "run_listing_extraction_agent"
    description = """Run extraction agent on listing page HTML to extract article URLs.
    Creates a test entry with type='listing' containing article URLs found."""

    def __init__(self, llm_client, memory_store: MemoryStore):
        self.llm = llm_client
        self.memory_store = memory_store

    def execute(
        self,
        html_memory_key: str,
        output_memory_key: str,
        article_selector: str | None = None
    ) -> dict[str, Any]:
        """Extract article URLs from listing page HTML."""
        try:
            stored = self.memory_store.read(html_memory_key)
            if not stored:
                return {"success": False, "error": f"No HTML at: {html_memory_key}"}

            html = stored.get("html", "")
            url = stored.get("url", "")

            # Truncate for LLM
            if len(html) > 50000:
                html = html[:50000] + "\n... [TRUNCATED]"

            # Build extraction prompt
            selector_hint = ""
            if article_selector:
                selector_hint = f"\nHint: Article links use selector: {article_selector}"

            extraction_prompt = f"""You are an HTML extraction agent for listing pages.
Extract article link information from this listing page HTML.{selector_hint}

Return ONLY a JSON object with these fields:
{{
    "article_urls": ["url1", "url2", ...],
    "article_count": 10,
    "has_pagination": true,
    "next_page_url": "next page URL or null"
}}

Guidelines:
- article_urls: List of article detail page URLs found on this page
- Resolve relative URLs to absolute using base: {url}
- has_pagination: true if there are pagination links
- next_page_url: URL to the next page if available

Do not include any explanation, just the JSON."""

            messages = [
                {"role": "system", "content": extraction_prompt},
                {"role": "user", "content": f"Listing URL: {url}\n\nHTML:\n{html}"}
            ]

            logger.info(f"Running listing extraction agent for: {url}")
            response = self.llm.chat(messages)
            extracted_text = response.get("content", "{}")

            # Parse JSON
            try:
                import re
                json_match = re.search(r'\{[\s\S]*\}', extracted_text)
                if json_match:
                    extracted = json.loads(json_match.group())
                else:
                    extracted = {"error": "No JSON found", "article_urls": [], "article_count": 0}
            except json.JSONDecodeError as e:
                extracted = {"error": str(e), "article_urls": [], "article_count": 0}

            # Create listing test entry
            test_entry = {
                "type": "listing",
                "url": url,
                "given": stored.get("html", ""),
                "expected": extracted
            }

            self.memory_store.write(output_memory_key, test_entry)
            logger.info(f"Listing extraction complete: {html_memory_key} -> {output_memory_key}")

            return {
                "success": True,
                "result": f"Extracted {extracted.get('article_count', 0)} article URLs to: {output_memory_key}",
                "article_urls": extracted.get("article_urls", []),
                "article_count": extracted.get("article_count", 0)
            }
        except Exception as e:
            logger.error(f"Listing extraction failed: {e}")
            return {"success": False, "error": str(e)}

    def get_parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "html_memory_key": {"type": "string", "description": "Key containing stored listing HTML"},
                "output_memory_key": {"type": "string", "description": "Key to store listing test entry"},
                "article_selector": {"type": "string", "description": "Optional CSS selector hint for articles"}
            },
            "required": ["html_memory_key", "output_memory_key"]
        }


class BatchExtractListingsTool(BaseTool):
    """Run extraction on multiple listing pages."""

    name = "batch_extract_listings"
    description = """Run extraction on listing HTML pages matching a key prefix.
    Each page is processed by a fresh extraction agent.
    Results are stored as listing test entries with type='listing'.
    Also collects all article URLs found across all listings."""

    def __init__(self, llm_client, memory_store: MemoryStore):
        self.llm = llm_client
        self.memory_store = memory_store

    def execute(
        self,
        html_key_prefix: str,
        output_key_prefix: str = "test-data-listing",
        article_selector: str | None = None
    ) -> dict[str, Any]:
        """Extract from all listing HTML with matching prefix."""
        html_keys = self.memory_store.search(f"{html_key_prefix}-*")

        if not html_keys:
            return {"success": False, "error": f"No HTML found with prefix: {html_key_prefix}"}

        extractor = RunListingExtractionAgentTool(self.llm, self.memory_store)
        results = []
        all_article_urls = []

        for i, html_key in enumerate(html_keys):
            output_key = f"{output_key_prefix}-{i+1}"
            result = extractor.execute(html_key, output_key, article_selector)
            results.append({
                "html_key": html_key,
                "output_key": output_key,
                "success": result.get("success", False),
                "article_count": result.get("article_count", 0)
            })
            # Collect article URLs
            if result.get("success"):
                all_article_urls.extend(result.get("article_urls", []))

        successful = sum(1 for r in results if r["success"])
        total_articles = len(all_article_urls)

        # Store collected article URLs for later use
        self.memory_store.write("collected_article_urls", all_article_urls)

        return {
            "success": successful > 0,
            "result": f"Extracted {successful}/{len(html_keys)} listings, found {total_articles} article URLs",
            "extracted_count": successful,
            "total_article_urls": total_articles,
            "output_keys": [r["output_key"] for r in results if r["success"]]
        }

    def get_parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "html_key_prefix": {"type": "string", "description": "Prefix to find listing HTML keys"},
                "output_key_prefix": {"type": "string", "description": "Prefix for output keys (default: test-data-listing)"},
                "article_selector": {"type": "string", "description": "Optional CSS selector hint for articles"}
            },
            "required": ["html_key_prefix"]
        }


# Keep old name as alias for backward compatibility
BatchExtractTool = BatchExtractArticlesTool
