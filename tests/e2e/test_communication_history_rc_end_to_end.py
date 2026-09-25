"""Release-candidate E2E for Communication delivery history."""
from __future__ import annotations
from datetime import UTC, datetime, timedelta
from pycrmkit import CRM
from pycrmkit.communication import (
    CommunicationAddress, CommunicationChannel, CommunicationContent,
    CommunicationRecipient, EmailDeliveryEventType, EmailDeliveryStatus,
    EmailMessage, EmailProviderResult, EmailTemplate,
)
from pycrmkit.core.references import EntityReference
from pycrmkit.core.time import FixedClock
from pycrmkit.events import DomainEvent
from pycrmkit.providers.email.jinja2 import Jinja2TemplateRenderer
from pycrmkit.timeline import TimelineEntryKind

NOW=datetime(2026,9,25,18,0,tzinfo=UTC)

class AcceptingProvider:
    def __init__(self) -> None:
        self.messages: list[EmailMessage]=[]
    def send(self, message: EmailMessage) -> EmailProviderResult:
        self.messages.append(message)
        return EmailProviderResult(
            provider="fake", status=EmailDeliveryStatus.ACCEPTED,
            provider_message_id="provider-700", provider_metadata={"request_id":"req-700"},
        )

class FailingProvider:
    def send(self, message: EmailMessage) -> EmailProviderResult:
        del message
        return EmailProviderResult(
            provider="fake", status=EmailDeliveryStatus.FAILED,
            failure_code="fake.rejected",
        )

def _crm(provider: object) -> tuple[CRM, FixedClock]:
    clock=FixedClock(NOW)
    crm=CRM.memory(
        clock=clock, email_provider=provider,  # type: ignore[arg-type]
        email_sender=CommunicationAddress(CommunicationChannel.EMAIL,"sales@example.com"),
        template_renderer=Jinja2TemplateRenderer(),
    )
    return crm, clock

def test_rc_templated_send_callbacks_history_events_and_timeline() -> None:
    provider=AcceptingProvider(); crm,clock=_crm(provider)
    contact=crm.contacts.create(first_name="Ada",last_name="Lovelace")
    ref=EntityReference("contact",contact.id)
    recipient=CommunicationRecipient(
        CommunicationAddress(CommunicationChannel.EMAIL,"ada@example.com"),
        display_name="Ada Lovelace", reference=ref,
    )
    published: list[DomainEvent]=[]
    for name in ("email.queued","email.sent","email.delivered","email.opened","email.clicked"):
        crm.events.subscribe(name,published.append)

    record=crm.email.send(
        to=(recipient,),
        template=EmailTemplate(
            name="proposal", subject_template="Hello {{ name }}",
            text_template="Proposal for {{ name }}",
        ),
        template_context={"name":"Ada"},
        idempotency_key="proposal-700",
    )
    assert record.delivery_status is EmailDeliveryEventType.SENT
    assert record.external_id=="provider-700"
    assert provider.messages[0].content.subject=="Hello Ada"

    for offset,event_type,event_id in (
        (1,EmailDeliveryEventType.DELIVERED,"evt-delivered"),
        (2,EmailDeliveryEventType.OPENED,"evt-opened"),
        (3,EmailDeliveryEventType.CLICKED,"evt-clicked"),
    ):
        clock.advance(timedelta(minutes=1))
        crm.email.record_delivery_event(
            provider="fake",provider_message_id="provider-700",event_type=event_type,
            occurred_at=NOW+timedelta(minutes=offset),external_event_id=event_id,
        )

    # Provider callback replay is idempotent and emits no duplicate domain event.
    before=len(published)
    replay=crm.email.record_delivery_event(
        provider="fake",provider_message_id="provider-700",
        event_type=EmailDeliveryEventType.CLICKED,
        occurred_at=NOW+timedelta(minutes=3),external_event_id="evt-clicked",
    )
    assert replay.event_type is EmailDeliveryEventType.CLICKED
    assert len(published)==before

    current=crm.email.get(record.id)
    assert current.delivery_status is EmailDeliveryEventType.CLICKED
    history=crm.email.delivery_history(record.id)
    assert [item.event_type for item in history.items]==[
        EmailDeliveryEventType.CLICKED, EmailDeliveryEventType.OPENED,
        EmailDeliveryEventType.DELIVERED, EmailDeliveryEventType.QUEUED,
        EmailDeliveryEventType.SENT,
    ]
    assert crm.email.for_contact(contact.id).items==(current,)
    timeline=crm.timeline.for_contact(contact.id,kind=TimelineEntryKind.COMMUNICATION)
    assert [str(item.event_type) for item in timeline.items[:3]]==[
        "email.clicked","email.opened","email.delivered"
    ]
    assert {str(event.type) for event in published} >= {
        "email.queued","email.sent","email.delivered","email.opened","email.clicked"
    }
    assert all("ada@example.com" not in repr(event.payload) for event in published)

def test_rc_provider_failure_is_persisted_and_emitted() -> None:
    crm,_=_crm(FailingProvider())
    contact=crm.contacts.create(display_name="Failure Contact")
    ref=EntityReference("contact",contact.id)
    captured: list[DomainEvent]=[]
    crm.events.subscribe("email.failed",captured.append)
    record=crm.email.send(
        to=(CommunicationRecipient(
            CommunicationAddress(CommunicationChannel.EMAIL,"failure@example.com"),
            reference=ref,
        ),),
        content=CommunicationContent(subject="Failure",text_body="Body"),
    )
    assert record.delivery_status is EmailDeliveryEventType.FAILED
    assert record.external_id is None
    assert len(captured)==1
    assert crm.email.delivery_history(record.id).items[0].failure_code=="fake.rejected"
