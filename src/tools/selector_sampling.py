"""Selector sampling tools for generating page URLs to analyze.

This module uses the new observability decorators for automatic logging.
The @traced_tool decorator handles all tool instrumentation.

Prompts are now managed through the centralized PromptProvider.
"""

import logging
import random
import re
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from ..core.json_parser import parse_json_response
from ..core.llm import LLMClient
from ..observability.decorators import traced_tool
from ..prompts import get_prompt_provider
from .base import BaseTool
from .validation import validated_tool

logger = logging.getLogger(__name__)


class ListingPagesGeneratorTool(BaseTool):
    """Generate listing page URLs for selector analysis.

    Uses LLM to analyze pagination links and determine URL pattern,
    then applies sampling rules:
    - Sample ~2% of total pages
    - Minimum 5 pages
    - Maximum 20 pages (if total >= 1000)
    - URLs spread across pagination range
    """

    name = "generate_listing_pages"
    description = """Generate listing page URLs for selector analysis.
    Analyzes pagination links to detect URL pattern (page=N, offset=N, etc),
    then calculates optimal sample size (2% of total, min 5, max 20) and returns
    URLs spread across the pagination range."""

    def __init__(self, llm: LLMClient):
        self.llm = llm

    @traced_tool(name="generate_listing_pages")
    @validated_tool
    def execute(self, **kwargs: Any) -> dict[str, Any]:
        """Generate listing page URLs to analyze. Instrumented by @traced_tool."""
        target_url = kwargs["target_url"]
        max_pages = kwargs["max_pages"]
        pagination_links = kwargs.get("pagination_links")
        # Detect pagination pattern from links
        if pagination_links and len(pagination_links) >= 2:
            pattern_info = self._detect_pagination_pattern(target_url, pagination_links)
        else:
            # Fallback to simple ?page={n} pattern
            pattern_info = {
                "pattern_type": "page_number",
                "param_name": "page",
                "base_url": target_url,
                "url_template": f"{target_url}?page={{n}}",
            }

        # Calculate sample size: 2% of total, min 5, max 20
        sample_size = max(5, min(20, int(max_pages * 0.02)))

        # If there are fewer pages than sample_size, use all
        if max_pages <= sample_size:
            page_numbers = list(range(1, max_pages + 1))
        else:
            # Generate page numbers spread across the range
            page_numbers = self._generate_spread_pages(max_pages, sample_size)

        # Generate URLs using detected pattern
        urls = self._generate_urls(target_url, page_numbers, pattern_info)

        logger.info(
            f"Generated {len(urls)} listing URLs from {max_pages} total pages "
            f"(sample: {sample_size}, pattern: {pattern_info.get('pattern_type', 'unknown')})"
        )

        return {
            "success": True,
            "urls": urls,
            "page_numbers": page_numbers,
            "sample_size": sample_size,
            "total_pages": max_pages,
            "sample_percentage": round(sample_size / max_pages * 100, 1),
            "pagination_pattern": pattern_info,
        }

    def _detect_pagination_pattern(self, target_url: str, pagination_links: list[str]) -> dict:
        """Use LLM to analyze pagination links and detect the URL pattern."""
        # Use PromptProvider template for pagination pattern detection
        provider = get_prompt_provider()
        prompt = provider.render_prompt(
            "pagination_pattern", target_url=target_url, pagination_links=pagination_links
        )

        messages = [
            {
                "role": "system",
                "content": "You are a URL pattern analyzer. Analyze pagination URLs to understand the pattern. Respond with valid JSON only.",
            },
            {"role": "user", "content": prompt},
        ]

        try:
            response = self.llm.chat(messages)
            content = response.get("content", "")
            result = parse_json_response(content)

            if result:
                return result

        except Exception as e:
            logger.warning(f"LLM pattern detection failed: {e}")

        # Fallback: try to detect pattern ourselves
        return self._fallback_pattern_detection(target_url, pagination_links)

    def _fallback_pattern_detection(self, target_url: str, pagination_links: list[str]) -> dict:
        """Fallback pattern detection without LLM."""
        # Common pagination parameters to check
        common_params = ["page", "p", "pg", "offset", "start", "skip", "from"]

        for link in pagination_links:
            parsed = urlparse(link)
            params = parse_qs(parsed.query)

            for param in common_params:
                if param in params:
                    value = params[param][0]
                    try:
                        int(value)
                        # Found a numeric pagination param
                        base_parsed = urlparse(target_url)
                        base_params = parse_qs(base_parsed.query)
                        base_params.pop(param, None)
                        base_query = urlencode(base_params, doseq=True)
                        base_url = urlunparse(base_parsed._replace(query=base_query))

                        return {
                            "pattern_type": "offset"
                            if param in ["offset", "start", "skip", "from"]
                            else "page_number",
                            "param_name": param,
                            "base_url": base_url if base_url else target_url,
                            "url_template": f"{target_url}{'&' if '?' in target_url else '?'}{param}={{n}}",
                            "offset_multiplier": None,
                            "starts_at": 1,
                        }
                    except ValueError:
                        continue

        # Default fallback
        return {
            "pattern_type": "page_number",
            "param_name": "page",
            "base_url": target_url,
            "url_template": f"{target_url}{'&' if '?' in target_url else '?'}page={{n}}",
            "offset_multiplier": None,
            "starts_at": 1,
        }

    def _generate_urls(
        self, target_url: str, page_numbers: list[int], pattern_info: dict
    ) -> list[str]:
        """Generate URLs using the detected pattern."""
        urls = []
        url_template = pattern_info.get("url_template", f"{target_url}?page={{n}}")
        offset_multiplier = pattern_info.get("offset_multiplier")
        starts_at = pattern_info.get("starts_at", 1)

        for page_num in page_numbers:
            if page_num == 1 and starts_at == 1:
                # First page often uses the base URL without params
                urls.append(target_url)
            else:
                # Calculate the actual value to use
                if offset_multiplier:
                    value = (page_num - 1) * offset_multiplier
                elif starts_at == 0:
                    value = page_num - 1
                else:
                    value = page_num

                # Handle template that might have expressions like {n*20}
                if "{n*" in url_template:
                    # Extract multiplier from template
                    match = re.search(r"\{n\*(\d+)\}", url_template)
                    if match:
                        mult = int(match.group(1))
                        value = (page_num - 1) * mult
                        url = re.sub(r"\{n\*\d+\}", str(value), url_template)
                    else:
                        url = url_template.replace("{n}", str(value))
                else:
                    url = url_template.replace("{n}", str(value))

                urls.append(url)

        return urls

    def _generate_spread_pages(self, max_pages: int, sample_size: int) -> list[int]:
        """Generate page numbers spread evenly across the range.

        Always includes page 1 and max_page, with others distributed evenly.
        """
        if sample_size >= max_pages:
            return list(range(1, max_pages + 1))

        pages = set()

        # Always include first and last
        pages.add(1)
        pages.add(max_pages)

        # Calculate step size for even distribution
        remaining = sample_size - 2  # Minus first and last
        if remaining > 0:
            step = max_pages / (remaining + 1)
            for i in range(1, remaining + 1):
                page = int(step * i)
                # Avoid duplicates with first/last
                if page not in pages:
                    pages.add(page)

        # If we still need more pages (due to duplicates), add random ones
        while len(pages) < sample_size:
            candidate = random.randint(2, max_pages - 1)
            if candidate not in pages:
                pages.add(candidate)

        return sorted(list(pages))


class ArticlePagesGeneratorTool(BaseTool):
    """Generate article page URLs for selector verification.

    Uses LLM to group URLs by pattern, then samples from each group:
    - Single pattern: sample 20% (min 3)
    - Multiple patterns: sample 20% per group (min 3 each)
    """

    name = "generate_article_pages"
    description = """Generate article page URLs for selector verification.
    Groups URLs by pattern and samples appropriately from each group."""

    def __init__(self, llm: LLMClient):
        self.llm = llm

    @traced_tool(name="generate_article_pages")
    @validated_tool
    def execute(self, **kwargs: Any) -> dict[str, Any]:
        """Generate article URLs to analyze. Instrumented by @traced_tool."""
        article_urls = kwargs["article_urls"]
        min_per_group = kwargs.get("min_per_group", 3)
        sample_percentage = kwargs.get("sample_percentage", 0.20)
        if not article_urls:
            return {"success": False, "error": "No article URLs provided"}

        # Group URLs by pattern using LLM
        groups = self._group_urls_by_pattern(article_urls)

        # Sample from each group
        selected_urls = []
        group_samples = {}

        for pattern, urls in groups.items():
            # Calculate sample size: 20% of group, minimum 3
            sample_count = max(min_per_group, int(len(urls) * sample_percentage))
            # Don't sample more than available
            sample_count = min(sample_count, len(urls))

            # Random sample
            sampled = random.sample(urls, sample_count)
            selected_urls.extend(sampled)
            group_samples[pattern] = {
                "total_in_group": len(urls),
                "sampled_count": sample_count,
                "sampled_urls": sampled,
            }

        logger.info(
            f"Generated {len(selected_urls)} article URLs from {len(article_urls)} total "
            f"across {len(groups)} pattern groups"
        )

        return {
            "success": True,
            "selected_urls": selected_urls,
            "total_urls": len(article_urls),
            "selected_count": len(selected_urls),
            "pattern_groups": group_samples,
            "num_patterns": len(groups),
        }

    def _group_urls_by_pattern(self, urls: list[str]) -> dict[str, list[str]]:
        """Use LLM to group URLs by their structural pattern."""
        # For small sets, use simple path-based grouping
        if len(urls) <= 20:
            return self._simple_path_grouping(urls)

        # For larger sets, use LLM to identify patterns
        sample_urls = urls[:50] if len(urls) > 50 else urls

        # Use PromptProvider template for article URL pattern grouping
        provider = get_prompt_provider()
        prompt = provider.render_prompt("article_url_pattern", sample_urls=sample_urls)

        messages = [
            {
                "role": "system",
                "content": "You are a URL pattern analyzer. Respond with valid JSON only.",
            },
            {"role": "user", "content": prompt},
        ]

        try:
            response = self.llm.chat(messages)
            content = response.get("content", "")

            # Parse JSON using shared parser
            data = parse_json_response(content, allow_array=False)
            if data is None:
                logger.warning("Failed to parse URL pattern analysis response")
                return {}
            patterns = data.get("patterns", [])

            # Group all URLs by matched patterns
            groups = {}
            for pattern_info in patterns:
                pattern_name = pattern_info.get("pattern_name", "unknown")
                pattern_regex = pattern_info.get("pattern_regex", "")

                if pattern_regex:
                    try:
                        regex = re.compile(pattern_regex)
                        matched = [url for url in urls if regex.search(url)]
                        if matched:
                            groups[pattern_name] = matched
                    except re.error:
                        pass

            # Put any unmatched URLs in "other" group
            all_matched = set()
            for matched_urls in groups.values():
                all_matched.update(matched_urls)

            unmatched = [url for url in urls if url not in all_matched]
            if unmatched:
                if not groups:
                    groups["default"] = urls
                else:
                    groups["other"] = unmatched

            # If no groups found, use simple grouping
            if not groups:
                return self._simple_path_grouping(urls)

            return groups

        except Exception as e:
            logger.warning(f"LLM pattern grouping failed, using simple grouping: {e}")
            return self._simple_path_grouping(urls)

    def _simple_path_grouping(self, urls: list[str]) -> dict[str, list[str]]:
        """Simple grouping based on path depth and structure."""
        groups: dict[str, list[str]] = {}

        for url in urls:
            parsed = urlparse(url)
            path_parts = [p for p in parsed.path.split("/") if p]

            # Create pattern key from path structure
            # e.g., /publikacje/article-slug -> "publikacje/*"
            if len(path_parts) >= 2:
                pattern_key = f"{path_parts[0]}/*"
            elif len(path_parts) == 1:
                pattern_key = f"{path_parts[0]}"
            else:
                pattern_key = "root"

            if pattern_key not in groups:
                groups[pattern_key] = []
            groups[pattern_key].append(url)

        return groups
