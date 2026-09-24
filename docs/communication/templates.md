# Email Templates

PyCRMKit `0.4.0b1` adds a provider-neutral template contract plus an optional Jinja2 renderer.

## Core contract

`EmailTemplate` stores a named subject template and text/HTML body templates. At least one body template is required.

`TemplateRenderer` is a protocol:

```python
class TemplateRenderer(Protocol):
    def render(
        self,
        template: EmailTemplate,
        context: Mapping[str, object],
    ) -> CommunicationContent:
        ...
```

The Communication domain therefore remains independent from any concrete template engine.

## Jinja2 renderer

Install the email extra:

```bash
pip install "pycrmkit[email]"
```

Then:

```python
from pycrmkit.communication import EmailTemplate
from pycrmkit.providers.email.jinja2 import Jinja2TemplateRenderer

template = EmailTemplate(
    name="proposal_followup",
    subject_template="Hello {{ name }}",
    text_template="Your proposal is ready, {{ name }}.",
    html_template="<strong>Your proposal is ready, {{ name }}.</strong>",
)

content = Jinja2TemplateRenderer().render(
    template,
    {"name": "Thomas"},
)
```

Undefined Jinja variables fail explicitly. HTML rendering uses autoescaping by default, while subject and plain-text rendering do not.
