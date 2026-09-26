"""Installed-package smoke test for PyCRMKit 0.7.0rc1 FastAPI PostgreSQL E2E."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pycrmkit
from pycrmkit.activities import ActivityParticipant
from pycrmkit.communication import (
    CommunicationAddress,
    CommunicationChannel,
    CommunicationContent,
    CommunicationRecipient,
    EmailDeliveryEventType,
    EmailDeliveryStatus,
    EmailMessage,
    EmailProviderResult,
)
from pycrmkit.core import Money
from pycrmkit.core.references import EntityReference
from pycrmkit.core.time import FixedClock
from pycrmkit.events import DomainEvent, EventSerializer, default_event_registry
from pycrmkit.leads import LeadStatus
from pycrmkit.opportunities import OpportunityStatus
from pycrmkit.pipelines import InvalidStageTransition, Stage, StageTransition
from pycrmkit.providers.email import SMTPConfig
from pycrmkit.webhooks import (
    WebhookDeliveryState,
    WebhookRequest,
    WebhookResponse,
)

SALES_EVENTS = (
    "lead.created",
    "lead.qualified",
    "lead.converted",
    "lead.disqualified",
    "opportunity.created",
    "opportunity.stage_changed",
    "opportunity.won",
    "opportunity.lost",
)


def main() -> None:
    version = pycrmkit.__version__
    if version != "0.7.0rc1":
        raise SystemExit(f"Expected PyCRMKit 0.7.0rc1, got {version!r}")

    address = CommunicationAddress(
        CommunicationChannel.EMAIL,
        "Smoke.User@Example.COM",
    )
    if address.normalized != "smoke.user@example.com":
        raise SystemExit("Communication address normalization smoke failed")

    smtp_config = SMTPConfig(host="smtp.example.com")
    if smtp_config.port != 587:
        raise SystemExit("SMTP config smoke failed")

    provider_result = EmailProviderResult(
        provider="installed-smoke",
        status=EmailDeliveryStatus.ACCEPTED,
        provider_message_id="smoke-message",
        provider_metadata={"transport": "fake"},
    )
    if provider_result.provider_message_id != "smoke-message":
        raise SystemExit("Email provider result smoke failed")

    amount = Money(Decimal("15000"), "eur")
    if amount.currency != "EUR" or amount.amount != Decimal("15000"):
        raise SystemExit("Money Decimal/currency smoke failed")

    clock = FixedClock(datetime(2026, 9, 24, 7, tzinfo=UTC))
    crm = pycrmkit.CRM.memory(clock=clock).with_context(
        actor_id="installed-smoke",
        correlation_id="communication-stable-smoke",
    )
    contact = crm.contacts.create(first_name="Smoke", last_name="Test")
    organization = crm.organizations.create(legal_name="Smoke Org")
    contact_ref = EntityReference("contact", contact.id)
    organization_ref = EntityReference("organization", organization.id)

    crm.activities.log(
        type="meeting",
        subject="Stable 0.2 compatibility smoke",
        participants=(ActivityParticipant(contact_ref, is_primary=True),),
        references=(organization_ref,),
    )
    task = crm.tasks.create(
        title="Stable task compatibility smoke",
        references=(contact_ref, organization_ref),
    )
    crm.tasks.complete(task.id)
    if crm.timeline.for_contact(contact.id).total != 3:
        raise SystemExit("Stable Activity/Task/Timeline compatibility smoke failed")

    crm.pipelines.define(
        id="sales",
        name="Sales",
        stages=(
            Stage("new", "New", 0, Decimal("0.10")),
            Stage("qualified", "Qualified", 10, Decimal("0.30")),
            Stage("proposal", "Proposal", 20, Decimal("0.60")),
            Stage("won", "Won", 30, terminal=True, outcome="won"),
            Stage("lost", "Lost", 40, terminal=True, outcome="lost"),
        ),
        transitions=(
            StageTransition("new", "qualified"),
            StageTransition("qualified", "proposal"),
            StageTransition("proposal", "won"),
            StageTransition("proposal", "lost"),
        ),
    )

    events = []
    for event_type in SALES_EVENTS:
        crm.events.subscribe(event_type, events.append)

    won_lead = crm.leads.create(
        contact_id=contact.id,
        organization_id=organization.id,
        source="website",
    )
    won_lead = crm.leads.qualify(won_lead.id)
    if won_lead.status is not LeadStatus.QUALIFIED:
        raise SystemExit("Lead qualification smoke failed")

    won_opportunity = crm.leads.convert(
        won_lead.id,
        name="Installed package won path",
        estimated_value=Decimal("25000.00"),
        currency="EUR",
        pipeline_id="sales",
        idempotency_key="installed-smoke-won",
    )
    retry = crm.leads.convert(
        won_lead.id,
        name="Installed package won path",
        estimated_value=Decimal("25000.0"),
        currency="eur",
        pipeline_id="SALES",
        idempotency_key="installed-smoke-won",
    )
    if retry.id != won_opportunity.id:
        raise SystemExit("Lead conversion idempotent replay smoke failed")

    try:
        crm.opportunities.move(won_opportunity.id, to="won")
    except InvalidStageTransition:
        pass
    else:
        raise SystemExit("Pipeline invalid-transition smoke failed")

    for stage in ("qualified", "proposal", "won"):
        won_opportunity = crm.opportunities.move(won_opportunity.id, to=stage)
    if won_opportunity.status is not OpportunityStatus.WON:
        raise SystemExit("Won terminal outcome smoke failed")

    rejected = crm.leads.create(contact_id=contact.id, source="referral")
    rejected = crm.leads.disqualify(rejected.id)
    if rejected.status is not LeadStatus.DISQUALIFIED:
        raise SystemExit("Lead disqualification smoke failed")

    lost_lead = crm.leads.create(contact_id=contact.id, source="event")
    lost_lead = crm.leads.qualify(lost_lead.id)
    lost_opportunity = crm.leads.convert(
        lost_lead.id,
        pipeline_id="sales",
        idempotency_key="installed-smoke-lost",
    )
    for stage in ("qualified", "proposal", "lost"):
        lost_opportunity = crm.opportunities.move(lost_opportunity.id, to=stage)
    if lost_opportunity.status is not OpportunityStatus.LOST:
        raise SystemExit("Lost terminal outcome smoke failed")

    event_types = {str(event.type) for event in events}
    missing = set(SALES_EVENTS) - event_types
    if missing:
        raise SystemExit(f"Missing Sales RC events: {sorted(missing)!r}")
    if crm.timeline.for_contact(contact.id).total != 3:
        raise SystemExit("Sales events must remain outside Timeline in 0.4.0")

    class SmokeEmailProvider:
        def send(self, message: EmailMessage) -> EmailProviderResult:
            if message.content.subject != "Stable communication smoke":
                raise SystemExit("Email provider received unexpected content")
            return EmailProviderResult(
                provider="smoke",
                status=EmailDeliveryStatus.ACCEPTED,
                provider_message_id="smoke-provider-message",
            )

    email_crm = pycrmkit.CRM.memory(
        clock=clock,
        email_provider=SmokeEmailProvider(),
        email_sender=CommunicationAddress(
            CommunicationChannel.EMAIL,
            "sender@example.com",
        ),
    )
    email_contact = email_crm.contacts.create(display_name="Communication Smoke")
    email_ref = EntityReference("contact", email_contact.id)
    record = email_crm.email.send(
        to=(
            CommunicationRecipient(
                CommunicationAddress(
                    CommunicationChannel.EMAIL,
                    "recipient@example.com",
                ),
                reference=email_ref,
            ),
        ),
        content=CommunicationContent(
            subject="Stable communication smoke",
            text_body="Smoke body",
        ),
        idempotency_key="stable-communication-smoke",
    )
    if record.delivery_status is not EmailDeliveryEventType.SENT:
        raise SystemExit("Communication send/history smoke failed")

    email_crm.email.record_delivery_event(
        provider="smoke",
        provider_message_id="smoke-provider-message",
        event_type=EmailDeliveryEventType.DELIVERED,
        occurred_at=clock.now(),
        external_event_id="smoke-delivered",
    )
    current = email_crm.email.get(record.id)
    if current.delivery_status is not EmailDeliveryEventType.DELIVERED:
        raise SystemExit("Communication callback state smoke failed")
    if email_crm.email.delivery_history(record.id).total != 3:
        raise SystemExit("Communication delivery-history smoke failed")
    communication_timeline = email_crm.timeline.for_contact(email_contact.id)
    timeline_events = [str(item.event_type) for item in communication_timeline.items]
    if set(timeline_events) != {
        "email.queued",
        "email.sent",
        "email.delivered",
    }:
        raise SystemExit("Communication Timeline projection smoke failed")

    captured_events: list[DomainEvent] = []
    registry_crm = pycrmkit.CRM.memory(clock=clock)
    registry_crm.events.subscribe("contact.created", captured_events.append)
    registry_crm.contacts.create(display_name="Event Registry Smoke")
    serializer = EventSerializer(default_event_registry())
    encoded = serializer.dumps(captured_events[0])
    restored = serializer.loads(encoded)
    if restored.to_dict() != captured_events[0].to_dict():
        raise SystemExit("Event registry/serialization installed smoke failed")

    root_events: list[DomainEvent] = []
    child_events: list[DomainEvent] = []
    trace_crm = pycrmkit.CRM.memory(clock=clock)
    trace_crm.events.subscribe("contact.created", root_events.append)
    trace_crm.events.subscribe("task.created", child_events.append)
    trace_crm.with_context(
        actor_id="trace-smoke",
        correlation_id="trace-root",
    ).contacts.create(display_name="Trace Smoke")
    trace_crm.with_event(root_events[0]).tasks.create(title="Trace child")
    if child_events[0].actor_id != "trace-smoke":
        raise SystemExit("Actor propagation smoke failed")
    if child_events[0].correlation_id != "trace-root":
        raise SystemExit("Correlation propagation smoke failed")
    if child_events[0].causation_id != root_events[0].id:
        raise SystemExit("Causation propagation smoke failed")

    class SmokeWebhookTransport:
        def __init__(self) -> None:
            self.requests: list[WebhookRequest] = []

        def send(self, request: WebhookRequest) -> WebhookResponse:
            self.requests.append(request)
            return WebhookResponse(204)

    webhook_transport = SmokeWebhookTransport()
    webhook_crm = pycrmkit.CRM.memory(
        clock=clock,
        webhook_transport=webhook_transport,
    )
    subscription = webhook_crm.webhooks.register(
        url="https://hooks.example.com/pycrmkit",
        events=("contact.created", "opportunity.won"),
        signing_secret="0123456789abcdef0123456789abcdef",
    )
    if webhook_crm.webhooks.list(event_type="contact.created").items != (
        subscription,
    ):
        raise SystemExit("Webhook subscription filtering smoke failed")

    webhook_events: list[DomainEvent] = []
    webhook_crm.events.subscribe("contact.created", webhook_events.append)
    webhook_crm.contacts.create(display_name="Automatic Webhook Smoke")

    deliveries = webhook_crm.webhooks.deliveries()
    if deliveries.total != 1:
        raise SystemExit("Automatic webhook delivery smoke failed")
    delivered = deliveries.items[0]
    if delivered.state is not WebhookDeliveryState.SUCCEEDED:
        raise SystemExit("Automatic webhook did not succeed")
    if webhook_crm.webhooks.attempts(delivered.id).total != 1:
        raise SystemExit("Webhook delivery log smoke failed")
    if len(webhook_transport.requests) != 1:
        raise SystemExit("Automatic webhook transport smoke failed")

    replay = webhook_crm.webhooks.deliver(webhook_events[0])
    if replay[0].id != delivered.id or len(webhook_transport.requests) != 1:
        raise SystemExit("Webhook idempotency smoke failed")

    disabled = webhook_crm.webhooks.disable(subscription.id)
    if disabled.enabled:
        raise SystemExit("Webhook disable smoke failed")

    print(f"PyCRMKit {version}: Eventing & Webhooks Stable + stable 0.1-0.4 smoke OK")


if __name__ == "__main__":
    main()
