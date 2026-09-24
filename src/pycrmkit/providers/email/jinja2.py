"""Optional Jinja2 implementation of the email TemplateRenderer contract."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

try:
    from jinja2 import Environment, StrictUndefined, TemplateError
except ModuleNotFoundError as exc:  # pragma: no cover - exercised without the extra
    raise ImportError(
        "Jinja2 email templates require the optional dependency: "
        'pip install "pycrmkit[email]"'
    ) from exc

from pycrmkit.communication.email.templates import EmailTemplate, TemplateRenderer
from pycrmkit.communication.value_objects import CommunicationContent
from pycrmkit.exceptions import IntegrationError


@dataclass(slots=True)
class Jinja2TemplateRenderer(TemplateRenderer):
    """Strict Jinja2 renderer with HTML autoescaping enabled by default."""

    autoescape_html: bool = True

    def render(
        self,
        template: EmailTemplate,
        context: Mapping[str, object],
    ) -> CommunicationContent:
        plain_environment = Environment(
            undefined=StrictUndefined,
            autoescape=False,
        )
        html_environment = Environment(
            undefined=StrictUndefined,
            autoescape=self.autoescape_html,
        )
        values = dict(context)
        try:
            subject = self._render_optional(
                plain_environment,
                template.subject_template,
                values,
            )
            text_body = self._render_optional(
                plain_environment,
                template.text_template,
                values,
            )
            html_body = self._render_optional(
                html_environment,
                template.html_template,
                values,
            )
        except TemplateError as exc:
            raise IntegrationError(
                "email template rendering failed",
                code="communication.email.template.render_failed",
                context={"template": template.name, "error_type": type(exc).__name__},
            ) from exc
        return CommunicationContent(
            subject=subject,
            text_body=text_body,
            html_body=html_body,
        )

    @staticmethod
    def _render_optional(
        environment: Environment,
        source: str | None,
        context: Mapping[str, object],
    ) -> str | None:
        if source is None:
            return None
        return environment.from_string(source).render(**context)


__all__ = ["Jinja2TemplateRenderer"]
