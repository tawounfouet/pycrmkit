"""Provider-neutral email communication contracts."""

from pycrmkit.communication.email.messages import EmailMessage
from pycrmkit.communication.email.provider import (
    EmailDeliveryStatus,
    EmailProvider,
    EmailProviderResult,
)
from pycrmkit.communication.email.services import EmailDeliveryService
from pycrmkit.communication.email.templates import EmailTemplate, TemplateRenderer

__all__ = [
    "EmailDeliveryService",
    "EmailDeliveryStatus",
    "EmailMessage",
    "EmailProvider",
    "EmailProviderResult",
    "EmailTemplate",
    "TemplateRenderer",
]
