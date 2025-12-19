"""Jinja2-based prompt templates for dynamic prompts."""

from typing import Any

from jinja2 import BaseLoader, Environment, TemplateSyntaxError, meta


class PromptTemplate:
    """Jinja2-based template for dynamic prompts.

    Allows rendering prompts with context variables using Jinja2 syntax.

    Example:
        template = PromptTemplate(
            'Analyze URL: {{ url }}\\nLinks: {% for l in links %}{{ l }}\\n{% endfor %}',
            name='url_analysis'
        )
        result = template.render(url='http://example.com', links=['a', 'b'])
    """

    def __init__(self, template_string: str, name: str = "unnamed") -> None:
        """Initialize template.

        Args:
            template_string: Jinja2 template string
            name: Template name for error messages

        Raises:
            ValueError: If template syntax is invalid
        """
        self.name = name
        self.template_string = template_string
        self._env = Environment(loader=BaseLoader(), autoescape=False)
        try:
            self._template = self._env.from_string(template_string)
        except TemplateSyntaxError as e:
            raise ValueError(f"Invalid template syntax in {name}: {e}") from e

    def render(self, **context: Any) -> str:
        """Render the template with given context.

        Args:
            **context: Variable values to substitute

        Returns:
            Rendered prompt string
        """
        return self._template.render(**context)

    def get_required_variables(self) -> set[str]:
        """Extract variable names required by this template.

        Returns:
            Set of variable names found in the template
        """
        ast = self._env.parse(self.template_string)
        return meta.find_undeclared_variables(ast)

    def validate_context(self, context: dict[str, Any]) -> list[str]:
        """Check if context has all required variables.

        Args:
            context: Context dictionary to validate

        Returns:
            List of missing variable names (empty if all present)
        """
        required = self.get_required_variables()
        return [var for var in required if var not in context]

    def __repr__(self) -> str:
        return f"PromptTemplate(name={self.name!r})"
