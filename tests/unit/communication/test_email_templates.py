"""Tests for provider-neutral and Jinja2 email templates."""

from __future__ import annotations

import pytest

from pycrmkit.communication import EmailTemplate, TemplateRenderer
from pycrmkit.exceptions import IntegrationError, ValidationError
from pycrmkit.providers.email.jinja2 import Jinja2TemplateRenderer


def test_jinja2_renderer_renders_subject_text_and_escaped_html() -> None:
    renderer = Jinja2TemplateRenderer()
    template = EmailTemplate(
        name="proposal_followup",
        subject_template="Hello {{ name }}",
        text_template="Hello {{ name }}",
        html_template="<strong>{{ name }}</strong>",
    )

    content = renderer.render(template, {"name": "<Thomas>"})

    assert isinstance(renderer, TemplateRenderer)
    assert content.subject == "Hello <Thomas>"
    assert content.text_body == "Hello <Thomas>"
    assert content.html_body == "<strong>&lt;Thomas&gt;</strong>"


def test_jinja2_renderer_is_strict_about_missing_context() -> None:
    renderer = Jinja2TemplateRenderer()
    template = EmailTemplate(
        name="strict",
        text_template="Hello {{ missing_name }}",
    )

    with pytest.raises(IntegrationError) as error:
        renderer.render(template, {})

    assert error.value.code == "communication.email.template.render_failed"
    assert error.value.context["template"] == "strict"


def test_email_template_requires_a_body_template() -> None:
    with pytest.raises(ValidationError) as error:
        EmailTemplate(name="invalid", subject_template="Subject only")

    assert error.value.code == "communication.email.template.body.required"
