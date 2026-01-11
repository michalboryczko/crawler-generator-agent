"""Template renderer for contract-aware prompts.

Provides Jinja2 template rendering for building agent prompts
with contract documentation.
"""

import json
from functools import lru_cache
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

TEMPLATES_DIR = Path(__file__).parent / "templates" / "shared"
AGENTS_TEMPLATES_DIR = Path(__file__).parent / "templates" / "agents"


def _tojson_filter(value: object, indent: int = 2) -> str:
    """Custom tojson filter with pretty formatting.

    Args:
        value: Object to serialize to JSON.
        indent: Number of spaces for indentation.

    Returns:
        Formatted JSON string.
    """
    return json.dumps(value, indent=indent, sort_keys=True)


@lru_cache(maxsize=1)
def get_template_env() -> Environment:
    """Get configured Jinja2 environment for contract templates.

    Returns:
        Jinja2 Environment with templates directory and custom filters.
    """
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["tojson"] = _tojson_filter
    return env


def render_template(template_name: str, **context) -> str:
    """Render a contract template with provided context.

    Args:
        template_name: Name of template file (e.g., "sub_agent_item.md.j2").
        **context: Template variables.

    Returns:
        Rendered template string.

    Raises:
        jinja2.TemplateNotFound: If template doesn't exist.
    """
    env = get_template_env()
    template = env.get_template(template_name)
    return template.render(**context)


@lru_cache(maxsize=1)
def get_agents_template_env() -> Environment:
    """Get configured Jinja2 environment for agent templates.

    Returns:
        Jinja2 Environment with agents templates directory.
    """
    env = Environment(
        loader=FileSystemLoader(str(AGENTS_TEMPLATES_DIR)),
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["tojson"] = _tojson_filter
    return env


def render_agent_template(template_name: str, **context) -> str:
    """Render an agent template with provided context.

    Args:
        template_name: Name of template file (e.g., "crawl_plan_task.md.j2").
        **context: Template variables.

    Returns:
        Rendered template string.

    Raises:
        jinja2.TemplateNotFound: If template doesn't exist.
    """
    env = get_agents_template_env()
    template = env.get_template(template_name)
    return template.render(**context)
