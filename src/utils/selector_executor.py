"""Utility for deterministic CSS selector execution on HTML.

This module provides a SelectorExecutor class that applies CSS selectors
to HTML content using BeautifulSoup, extracting text deterministically
before passing to an LLM for formatting.
"""

from __future__ import annotations

from typing import Any

from bs4 import BeautifulSoup


class SelectorExecutor:
    """Utility for deterministic CSS selector execution on HTML.

    This class extracts text from HTML elements using CSS selectors,
    eliminating LLM interpretation variance and ensuring complete
    content extraction.
    """

    @staticmethod
    def execute_selector(html: str, selector: str) -> str | None:
        """Apply single CSS selector and return extracted text.

        Args:
            html: Raw HTML content
            selector: CSS selector string

        Returns:
            Extracted text with whitespace normalized, or None if not found
        """
        if not html or not selector:
            return None

        try:
            soup = BeautifulSoup(html, "html.parser")
            element = soup.select_one(selector)
            if element:
                return element.get_text(separator=" ", strip=True)
            return None
        except Exception:
            return None

    @staticmethod
    def execute_selector_chain(
        html: str,
        selector_chain: list[dict[str, Any]],
    ) -> str | None:
        """Try selectors in priority order, return first match.

        Selector chains are ordered by success rate (highest first).
        This method tries each selector until one matches.

        Args:
            html: Raw HTML content
            selector_chain: List of {"selector": "...", "success_rate": 0.95}
                          ordered by priority (first = highest priority)

        Returns:
            Extracted text from first matching selector, or None
        """
        if not html or not selector_chain:
            return None

        for item in selector_chain:
            if not isinstance(item, dict):
                continue
            selector = item.get("selector", "")
            if not selector:
                continue
            result = SelectorExecutor.execute_selector(html, selector)
            if result:
                return result
        return None

    @staticmethod
    def execute_all_selectors(
        html: str,
        detail_selectors: dict[str, list[dict[str, Any]]],
    ) -> dict[str, str]:
        """Execute all field selectors on HTML.

        Args:
            html: Raw HTML content
            detail_selectors: Dict mapping field names to selector chains
                            e.g., {"title": [{"selector": "h1", "success_rate": 1.0}]}

        Returns:
            Dict mapping field names to extracted text (empty string if not found)
        """
        if not detail_selectors:
            return {}

        results: dict[str, str] = {}
        for field_name, selector_chain in detail_selectors.items():
            if not selector_chain:
                results[field_name] = ""
                continue
            extracted = SelectorExecutor.execute_selector_chain(html, selector_chain)
            results[field_name] = extracted or ""
        return results

    @staticmethod
    def extract_all_elements(
        html: str,
        selector: str,
    ) -> list[str]:
        """Extract text from ALL matching elements (for lists).

        Useful for extracting multiple items like authors, tags, or links.

        Args:
            html: Raw HTML content
            selector: CSS selector string

        Returns:
            List of extracted text from each matching element
        """
        if not html or not selector:
            return []

        try:
            soup = BeautifulSoup(html, "html.parser")
            elements = soup.select(selector)
            return [
                el.get_text(separator=" ", strip=True) for el in elements if el.get_text(strip=True)
            ]
        except Exception:
            return []

    @staticmethod
    def extract_attribute(
        html: str,
        selector: str,
        attribute: str,
    ) -> str | None:
        """Extract an attribute value from the first matching element.

        Useful for extracting href, src, or data attributes.

        Args:
            html: Raw HTML content
            selector: CSS selector string
            attribute: Attribute name to extract (e.g., 'href', 'src')

        Returns:
            Attribute value or None if not found
        """
        if not html or not selector or not attribute:
            return None

        try:
            soup = BeautifulSoup(html, "html.parser")
            element = soup.select_one(selector)
            if element:
                return element.get(attribute)
            return None
        except Exception:
            return None

    @staticmethod
    def extract_all_attributes(
        html: str,
        selector: str,
        attribute: str,
    ) -> list[str]:
        """Extract an attribute from ALL matching elements.

        Useful for extracting all hrefs from article links.

        Args:
            html: Raw HTML content
            selector: CSS selector string
            attribute: Attribute name to extract

        Returns:
            List of attribute values from matching elements
        """
        if not html or not selector or not attribute:
            return []

        try:
            soup = BeautifulSoup(html, "html.parser")
            elements = soup.select(selector)
            return [el.get(attribute) for el in elements if el.get(attribute)]
        except Exception:
            return []
