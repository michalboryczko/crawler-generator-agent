"""HTML cleaning utilities to reduce content size for LLM processing."""
import re
from typing import Any


def clean_html_for_llm(html: str) -> str:
    """Clean HTML content to reduce size before sending to LLM.

    Removes:
    - <script> tags and content
    - <style> tags and content
    - <noscript> tags and content
    - <svg> tags and content
    - Base64 encoded images
    - HTML comments
    - Excessive whitespace

    Keeps:
    - Body content structure
    - Text content
    - Links (href attributes)
    - Basic semantic tags

    Args:
        html: Raw HTML string

    Returns:
        Cleaned HTML string with reduced size
    """
    if not html:
        return ""

    # Remove script tags and content
    html = re.sub(r"<script\b[^>]*>[\s\S]*?</script>", "", html, flags=re.IGNORECASE)

    # Remove style tags and content
    html = re.sub(r"<style\b[^>]*>[\s\S]*?</style>", "", html, flags=re.IGNORECASE)

    # Remove noscript tags and content
    html = re.sub(r"<noscript\b[^>]*>[\s\S]*?</noscript>", "", html, flags=re.IGNORECASE)

    # Remove svg tags and content
    html = re.sub(r"<svg\b[^>]*>[\s\S]*?</svg>", "", html, flags=re.IGNORECASE)

    # Remove HTML comments
    html = re.sub(r"<!--[\s\S]*?-->", "", html)

    # Remove base64 encoded images (data:image/...)
    html = re.sub(r'src=["\']data:image/[^"\']+["\']', 'src="[base64-removed]"', html)
    html = re.sub(r'href=["\']data:[^"\']+["\']', 'href="[data-removed]"', html)

    # Remove inline styles
    html = re.sub(r'\s+style=["\'][^"\']*["\']', "", html)

    # Remove data attributes (often contain large JSON)
    html = re.sub(r'\s+data-[a-z-]+=["\'][^"\']*["\']', "", html, flags=re.IGNORECASE)

    # Remove onclick and other event handlers
    html = re.sub(r'\s+on\w+=["\'][^"\']*["\']', "", html, flags=re.IGNORECASE)

    # Remove excessive whitespace
    html = re.sub(r"\n\s*\n", "\n", html)
    html = re.sub(r"  +", " ", html)

    # Extract body content if present
    body_match = re.search(r"<body\b[^>]*>([\s\S]*)</body>", html, flags=re.IGNORECASE)
    if body_match:
        html = body_match.group(1)

    return html.strip()


def extract_text_content(html: str) -> str:
    """Extract plain text content from HTML.

    Args:
        html: HTML string

    Returns:
        Plain text with tags removed
    """
    # First clean the HTML
    html = clean_html_for_llm(html)

    # Remove all remaining tags
    text = re.sub(r"<[^>]+>", " ", html)

    # Clean up whitespace
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def get_html_summary(html: str) -> dict[str, Any]:
    """Get summary statistics about HTML content.

    Args:
        html: HTML string

    Returns:
        Dict with statistics about the HTML
    """
    original_size = len(html)
    cleaned = clean_html_for_llm(html)
    cleaned_size = len(cleaned)

    return {
        "original_size": original_size,
        "cleaned_size": cleaned_size,
        "reduction_percent": round((1 - cleaned_size / original_size) * 100, 1) if original_size > 0 else 0,
        "has_scripts": bool(re.search(r"<script", html, re.IGNORECASE)),
        "has_styles": bool(re.search(r"<style", html, re.IGNORECASE)),
        "link_count": len(re.findall(r"<a\s", html, re.IGNORECASE)),
    }
