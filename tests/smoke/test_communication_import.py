"""Compatibility smoke for the stable PyCRMKit 0.4 Communication surface."""

from pycrmkit.communication import (
    CommunicationAddress,
    CommunicationChannel,
    CommunicationContent,
    CommunicationIntent,
    CommunicationRecord,
    DeliveryAttempt,
    EmailDeliveryEvent,
    EmailDeliveryEventType,
    EmailProvider,
    EmailTemplate,
    TemplateRenderer,
)
from pycrmkit.providers.email import SMTPConfig, SMTPEmailProvider, SMTPSecurity
from pycrmkit.timeline import TimelineEntryKind


def test_stable_communication_domain_imports() -> None:
    assert CommunicationAddress.__name__ == "CommunicationAddress"
    assert CommunicationChannel.EMAIL.value == "email"
    assert CommunicationContent.__name__ == "CommunicationContent"
    assert CommunicationIntent.__name__ == "CommunicationIntent"
    assert DeliveryAttempt.__name__ == "DeliveryAttempt"
    assert CommunicationRecord.__name__ == "CommunicationRecord"
    assert EmailDeliveryEvent.__name__ == "EmailDeliveryEvent"


def test_stable_communication_contract_names() -> None:
    assert {item.event_name for item in EmailDeliveryEventType} == {
        "email.queued",
        "email.sent",
        "email.delivered",
        "email.opened",
        "email.clicked",
        "email.bounced",
        "email.failed",
    }
    assert EmailProvider.__name__ == "EmailProvider"
    assert EmailTemplate.__name__ == "EmailTemplate"
    assert TemplateRenderer.__name__ == "TemplateRenderer"
    assert TimelineEntryKind.COMMUNICATION.value == "communication"


def test_stable_stdlib_smtp_surface() -> None:
    assert SMTPConfig.__name__ == "SMTPConfig"
    assert SMTPEmailProvider.__name__ == "SMTPEmailProvider"
    assert SMTPSecurity.STARTTLS.value == "starttls"
