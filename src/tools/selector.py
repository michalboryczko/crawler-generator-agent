"""Selector finding and verification tools."""
import logging
from typing import Any
from urllib.parse import urljoin, urlparse

from .base import BaseTool
from ..core.browser import BrowserSession

logger = logging.getLogger(__name__)


class FindSelectorTool(BaseTool):
    """Analyze HTML to suggest CSS selectors for elements."""

    name = "find_selector"
    description = """Analyze HTML patterns to find CSS selectors that match article links or pagination.
    Provide the type ('articles' or 'pagination') and optional hints about expected patterns."""

    def __init__(self, session: BrowserSession):
        self.session = session

    def execute(
        self,
        selector_type: str,
        hint: str | None = None
    ) -> dict[str, Any]:
        """Find potential selectors based on type and hints."""
        try:
            if selector_type == "articles":
                return self._find_article_selectors(hint)
            elif selector_type == "pagination":
                return self._find_pagination_selectors(hint)
            return {
                "success": False,
                "error": f"Unknown selector type: {selector_type}"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _find_article_selectors(self, hint: str | None) -> dict[str, Any]:
        """Find selectors for article links."""
        # Common article container patterns
        candidates = [
            "article a",
            ".post a",
            ".article a",
            ".entry a",
            ".card a",
            ".item a",
            "h2 a",
            "h3 a",
            ".title a",
            ".headline a",
            "[class*='article'] a",
            "[class*='post'] a",
            "[class*='story'] a",
            ".list-item a",
            ".news-item a",
        ]

        results = []
        for selector in candidates:
            elements = self.session.query_selector_all(selector)
            if elements:
                # Filter to likely article links
                valid = [
                    el for el in elements
                    if el.get("href") and
                    not el["href"].startswith("#") and
                    not el["href"].startswith("javascript:")
                ]
                if valid:
                    results.append({
                        "selector": selector,
                        "count": len(valid),
                        "sample": valid[:3]
                    })

        return {
            "success": True,
            "result": sorted(results, key=lambda x: x["count"], reverse=True)[:5],
            "total_candidates": len(results)
        }

    def _find_pagination_selectors(self, hint: str | None) -> dict[str, Any]:
        """Find selectors for pagination elements."""
        candidates = [
            ".pagination a",
            ".pager a",
            ".pages a",
            "nav.pagination a",
            "[class*='pagination'] a",
            "[class*='pager'] a",
            ".next",
            ".prev",
            "a[rel='next']",
            "a[rel='prev']",
            ".page-numbers",
            ".nav-links a",
            "[aria-label*='page']",
            "[aria-label*='next']",
        ]

        results = []
        for selector in candidates:
            elements = self.session.query_selector_all(selector)
            if elements:
                results.append({
                    "selector": selector,
                    "count": len(elements),
                    "sample": elements[:3]
                })

        return {
            "success": True,
            "result": sorted(results, key=lambda x: x["count"], reverse=True)[:5],
            "total_candidates": len(results)
        }

    def get_parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "selector_type": {
                    "type": "string",
                    "enum": ["articles", "pagination"],
                    "description": "Type of selector to find"
                },
                "hint": {
                    "type": "string",
                    "description": "Optional hint about expected pattern"
                }
            },
            "required": ["selector_type"]
        }


class TestSelectorTool(BaseTool):
    """Test a specific CSS selector and return matches."""

    name = "test_selector"
    description = "Test a CSS selector and return all matching elements with their text and href."

    def __init__(self, session: BrowserSession):
        self.session = session

    def execute(self, selector: str) -> dict[str, Any]:
        try:
            elements = self.session.query_selector_all(selector)
            return {
                "success": True,
                "result": elements,
                "count": len(elements)
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": "CSS selector to test"
                }
            },
            "required": ["selector"]
        }


class VerifySelectorTool(BaseTool):
    """Verify selector results against expected article URLs."""

    name = "verify_selector"
    description = """Verify that a CSS selector finds the expected articles.
    Compare selector results against a list of known article URLs."""

    def __init__(self, session: BrowserSession):
        self.session = session

    def execute(
        self,
        selector: str,
        expected_urls: list[str],
        base_url: str | None = None
    ) -> dict[str, Any]:
        try:
            elements = self.session.query_selector_all(selector)
            found_urls = set()

            for el in elements:
                href = el.get("href", "")
                if href and not href.startswith(("#", "javascript:")):
                    if base_url and not href.startswith("http"):
                        href = urljoin(base_url, href)
                    found_urls.add(href)

            expected_set = set(expected_urls)

            matched = found_urls & expected_set
            missing = expected_set - found_urls
            extra = found_urls - expected_set

            match_rate = len(matched) / len(expected_set) if expected_set else 0

            return {
                "success": True,
                "result": {
                    "match_rate": round(match_rate, 2),
                    "matched_count": len(matched),
                    "missing_count": len(missing),
                    "extra_count": len(extra),
                    "matched": list(matched)[:5],
                    "missing": list(missing)[:5],
                    "extra": list(extra)[:5],
                    "verdict": "GOOD" if match_rate >= 0.8 else "NEEDS_WORK"
                }
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": "CSS selector to verify"
                },
                "expected_urls": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of expected article URLs"
                },
                "base_url": {
                    "type": "string",
                    "description": "Base URL for resolving relative links"
                }
            },
            "required": ["selector", "expected_urls"]
        }


class CompareSelectorsTool(BaseTool):
    """Compare multiple selectors to find the best one."""

    name = "compare_selectors"
    description = "Compare multiple CSS selectors and rank them by match quality."

    def __init__(self, session: BrowserSession):
        self.session = session

    def execute(
        self,
        selectors: list[str],
        expected_urls: list[str],
        base_url: str | None = None
    ) -> dict[str, Any]:
        try:
            results = []
            expected_set = set(expected_urls)

            for selector in selectors:
                elements = self.session.query_selector_all(selector)
                found_urls = set()

                for el in elements:
                    href = el.get("href", "")
                    if href and not href.startswith(("#", "javascript:")):
                        if base_url and not href.startswith("http"):
                            href = urljoin(base_url, href)
                        found_urls.add(href)

                matched = found_urls & expected_set
                match_rate = len(matched) / len(expected_set) if expected_set else 0

                results.append({
                    "selector": selector,
                    "match_rate": round(match_rate, 2),
                    "matched_count": len(matched),
                    "total_found": len(found_urls),
                    "precision": round(len(matched) / len(found_urls), 2) if found_urls else 0
                })

            # Sort by match rate, then precision
            results.sort(key=lambda x: (x["match_rate"], x["precision"]), reverse=True)

            return {
                "success": True,
                "result": results,
                "best_selector": results[0]["selector"] if results else None
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "selectors": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of CSS selectors to compare"
                },
                "expected_urls": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of expected article URLs"
                },
                "base_url": {
                    "type": "string",
                    "description": "Base URL for resolving relative links"
                }
            },
            "required": ["selectors", "expected_urls"]
        }
