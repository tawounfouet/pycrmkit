"""Provider-neutral email template contracts."""

from __future__ import annotations

import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from pycrmkit.communication.value_objects import CommunicationContent
from pycrmkit.core.value_objects import ValueObject
from pycrmkit.exceptions import ValidationError


@dataclass(frozen=True, slots=True)
class EmailTemplate(ValueObject):
    """Named email template whose fields are rendered by a TemplateRenderer."""

    name: str
    subject_template: str | None = None
    text_template: str | None = None
    html_template: str | None = None

    def __post_init__(self) -> None:
        name = " ".join(unicodedata.normalize("NFKC", self.name).strip().split())
        if not name:
            raise ValidationError(
                "email template name is required",
                code="communication.email.template.name.required",
            )
        if len(name) > 255:
            raise ValidationError(
                "email template name must be at most 255 characters",
                code="communication.email.template.name.too_long",
            )
        if self.text_template is None and self.html_template is None:
            raise ValidationError(
                "email template requires a text or HTML body template",
                code="communication.email.template.body.required",
            )
        for field_name, value, limit in (
            ("subject_template", self.subject_template, 10_000),
            ("text_template", self.text_template, 1_000_000),
            ("html_template", self.html_template, 1_000_000),
        ):
            if value is not None and len(value) > limit:
                raise ValidationError(
                    f"{field_name} must be at most {limit} characters",
                    code=f"communication.email.template.{field_name}.too_long",
                )
        object.__setattr__(self, "name", name)


@runtime_checkable
class TemplateRenderer(Protocol):
    """Render an EmailTemplate into provider-neutral CommunicationContent."""

    def render(
        self,
        template: EmailTemplate,
        context: Mapping[str, object],
    ) -> CommunicationContent:
        """Render subject/text/HTML fields using the supplied context."""
