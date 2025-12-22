"""Crawler Configuration Generator Tool.

Generates dynamic crawler configuration JSON from collected selectors
and discovery data. Used by PlanGeneratorAgent to create structured
crawler configurations.

The @traced_tool decorator handles all tool instrumentation.
"""

import logging
from typing import Any

from ..observability.decorators import traced_tool
from .base import BaseTool
from .validation import validated_tool

logger = logging.getLogger(__name__)


class PrepareCrawlerConfigurationTool(BaseTool):
    """Generate dynamic crawler configuration JSON from collected data.

    This tool takes collected selectors and discovery data and generates
    a complete crawler configuration that can be used directly by the
    crawler system. The configuration uses a dynamic array format for
    listing and detail selectors to allow flexible property discovery.
    """

    name = "prepare_crawler_configuration"
    description = (
        "Generate dynamic crawler configuration JSON from collected selectors "
        "and discovery data. Produces a complete config ready for crawler use."
    )

    @traced_tool(name="prepare_crawler_configuration")
    @validated_tool
    def execute(self, **kwargs: Any) -> dict[str, Any]:
        """Generate crawler configuration from collected data.

        Args:
            target_url: Starting URL for the crawler
            listing_selectors: Dict of listing page selectors (from Selector Agent)
            detail_selectors: Dict of detail page selectors (from Selector Agent)
            pagination_config: Pagination configuration (from Discovery Agent)
            requires_browser: Whether JavaScript rendering is needed
            request_config: Optional custom request configuration

        Returns:
            dict with success status and generated config
        """
        target_url = kwargs["target_url"]
        listing_selectors = kwargs.get("listing_selectors", {})
        detail_selectors = kwargs.get("detail_selectors", {})
        pagination_config = kwargs.get("pagination_config", {})
        requires_browser = kwargs.get("requires_browser", True)
        request_config = kwargs.get("request_config", {})

        config = self._build_config(
            target_url=target_url,
            listing_selectors=listing_selectors,
            detail_selectors=detail_selectors,
            pagination_config=pagination_config,
            requires_browser=requires_browser,
            request_config=request_config,
        )

        return {
            "success": True,
            "config": config,
            "notes": (
                "Configuration uses dynamic selector arrays for listing and detail. "
                "Each property has multiple selectors tried in order."
            ),
        }

    def _build_config(
        self,
        target_url: str,
        listing_selectors: dict,
        detail_selectors: dict,
        pagination_config: dict,
        requires_browser: bool,
        request_config: dict,
    ) -> dict[str, Any]:
        """Build the complete crawler configuration."""
        return {
            "start_url": target_url,
            "listing": self._build_listing_config(listing_selectors),
            "detail": self._build_detail_config(detail_selectors),
            "pagination": self._build_pagination_config(pagination_config),
            "request": self._build_request_config(requires_browser, request_config),
            "deduplication": {"key": "url"},
        }

    def _build_listing_config(self, listing_selectors: dict) -> list[dict[str, Any]]:
        """Build dynamic listing configuration from selector data.

        Converts selector agent output format to dynamic array format:
        [
            {"property": "container_selector", "selectors": ["div.articles"]},
            {"property": "article_link_selector", "selectors": ["a.link"]}
        ]
        """
        listing_config = []

        # Extract listing_container
        container_data = listing_selectors.get("listing_container", [])
        container_selectors = self._extract_selector_list(container_data)
        if container_selectors:
            listing_config.append({
                "property": "container_selector",
                "selectors": container_selectors,
            })

        # Extract article_link
        link_data = listing_selectors.get("article_link", [])
        link_selectors = self._extract_selector_list(link_data)
        if link_selectors:
            listing_config.append({
                "property": "article_link_selector",
                "selectors": link_selectors,
            })

        # Include any additional listing properties discovered
        for prop, data in listing_selectors.items():
            if prop not in ("listing_container", "article_link"):
                selectors = self._extract_selector_list(data)
                if selectors:
                    listing_config.append({
                        "property": prop,
                        "selectors": selectors,
                    })

        return listing_config

    def _build_detail_config(self, detail_selectors: dict) -> list[dict[str, Any]]:
        """Build dynamic detail configuration from selector data.

        Converts selector agent output format to dynamic array format:
        [
            {"property": "title", "selectors": ["h1.title", ".article-title"]},
            {"property": "content", "selectors": [".article-content", ".body"]}
        ]
        """
        detail_config = []

        # Standard detail fields in preferred order
        standard_fields = [
            "title",
            "date",
            "authors",
            "content",
            "lead",
            "category",
            "tags",
            "images",
            "files",
        ]

        # Process standard fields first (in order)
        for field in standard_fields:
            if field in detail_selectors:
                selectors = self._extract_selector_list(detail_selectors[field])
                if selectors:
                    detail_config.append({
                        "property": field,
                        "selectors": selectors,
                    })

        # Then any additional discovered fields
        for field, data in detail_selectors.items():
            if field not in standard_fields:
                selectors = self._extract_selector_list(data)
                if selectors:
                    detail_config.append({
                        "property": field,
                        "selectors": selectors,
                    })

        return detail_config

    def _extract_selector_list(self, data: Any) -> list[str]:
        """Extract list of selector strings from various input formats.

        Handles:
        - List of dicts with "selector" key (selector chain format)
        - List of strings
        - Single dict with "primary" and "fallbacks"
        - Single string
        """
        if not data:
            return []

        # Handle list format (most common from Selector Agent)
        if isinstance(data, list):
            selectors = []
            for item in data:
                if isinstance(item, dict):
                    # Selector chain format: {"selector": "...", "success_rate": 0.9}
                    sel = item.get("selector", "")
                    if sel:
                        selectors.append(sel)
                elif isinstance(item, str) and item:
                    selectors.append(item)
            return selectors

        # Handle old dict format with primary/fallbacks
        if isinstance(data, dict):
            selectors = []
            primary = data.get("primary", data.get("selector", ""))
            if primary:
                selectors.append(primary)
            fallbacks = data.get("fallbacks", [])
            for fb in fallbacks:
                if fb:
                    selectors.append(fb)
            return selectors

        # Handle simple string
        if isinstance(data, str) and data:
            return [data]

        return []

    def _build_pagination_config(self, pagination_config: dict) -> dict[str, Any]:
        """Build pagination configuration."""
        if not pagination_config:
            return {
                "enabled": False,
                "selector": None,
                "type": "none",
                "strategy": "follow_next",
                "max_pages": 1,
            }

        pagination_type = pagination_config.get("type", "none")
        pagination_selector = pagination_config.get("selector")
        max_pages = pagination_config.get("max_pages", 100)

        # Determine strategy based on type
        strategy_map = {
            "numbered": "loop_pages",
            "next_link": "follow_next",
            "load_more": "click_load_more",
            "infinite_scroll": "scroll",
            "none": "follow_next",
        }
        strategy = strategy_map.get(pagination_type, "follow_next")

        return {
            "enabled": pagination_selector is not None and pagination_type != "none",
            "selector": pagination_selector,
            "type": pagination_type,
            "strategy": strategy,
            "max_pages": max_pages,
        }

    def _build_request_config(
        self, requires_browser: bool, custom_config: dict
    ) -> dict[str, Any]:
        """Build request configuration with defaults."""
        defaults = {
            "requires_browser": requires_browser,
            "wait_between_requests": 2,
            "max_concurrent_requests": 4,
            "timeout_seconds": 15,
        }

        # Override with custom config
        defaults.update(custom_config)
        return defaults
