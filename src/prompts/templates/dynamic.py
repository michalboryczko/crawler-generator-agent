"""Dynamic prompt templates loaded from Jinja2 files.

These templates use Jinja2 syntax for variable substitution and are
rendered with context at runtime via PromptProvider.render_prompt().
"""

from pathlib import Path
from typing import TYPE_CHECKING

from ..template import PromptTemplate

if TYPE_CHECKING:
    from ..provider import PromptProvider

TOOLS_TEMPLATES_DIR = Path(__file__).parent / "tools"


def _load_template(filename: str) -> str:
    """Load template content from a .j2 file."""
    template_path = TOOLS_TEMPLATES_DIR / filename
    return template_path.read_text()


def register_dynamic_templates(provider: "PromptProvider") -> None:
    """Register all dynamic templates with the provider."""
    provider.register_template(
        "article_extraction",
        PromptTemplate(_load_template("article_extraction.md.j2"), name="article_extraction"),
    )

    provider.register_template(
        "listing_url_extraction",
        PromptTemplate(
            _load_template("listing_url_extraction.md.j2"), name="listing_url_extraction"
        ),
    )

    provider.register_template(
        "pagination_pattern",
        PromptTemplate(_load_template("pagination_pattern.md.j2"), name="pagination_pattern"),
    )

    provider.register_template(
        "article_url_pattern",
        PromptTemplate(_load_template("article_url_pattern.md.j2"), name="article_url_pattern"),
    )

    provider.register_template(
        "selector_aggregation",
        PromptTemplate(_load_template("selector_aggregation.md.j2"), name="selector_aggregation"),
    )
