"""Extraction prompts loaded from Jinja2 template files.

These prompts are used by selector extraction tools to analyze page structure.
"""

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..registry import PromptRegistry

TOOLS_TEMPLATES_DIR = Path(__file__).parent / "tools"


def _load_template(filename: str) -> str:
    """Load template content from a .j2 file."""
    template_path = TOOLS_TEMPLATES_DIR / filename
    return template_path.read_text()


def register_extraction_prompts(registry: "PromptRegistry") -> None:
    """Register extraction prompts with the registry."""
    registry.register_prompt(
        name="extraction.listing",
        content=_load_template("extraction_listing.md.j2"),
        version="1.0.0",
        category="extraction",
        description="Extract article URLs and selectors from listing pages",
    )
    registry.register_prompt(
        name="extraction.article",
        content=_load_template("extraction_article.md.j2"),
        version="1.0.0",
        category="extraction",
        description="Extract content selectors from article pages",
    )
