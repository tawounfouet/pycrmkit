"""0.6.0rc1 persistence qualification across the stable 0.1-0.5 surface."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session, sessionmaker

from pycrmkit import CRM
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
from pycrmkit.contacts import ContactEmail
from pycrmkit.core.references import EntityReference
from pycrmkit.core.time import FixedClock
from pycrmkit.core.unit_of_work import UnitOfWork
from pycrmkit.custom_fields import CustomFieldType
from pycrmkit.events import DomainEvent, InProcessEventBus
from pycrmkit.opportunities import OpportunityStatus
from pycrmkit.pipelines import Stage, StageTransition
from pycrmkit.relationships import RelationshipEndpoint, RelationshipType
from pycrmkit.storage.sqlalchemy import SQLAlchemyUnitOfWork
from pycrmkit.tasks import TaskStatus
from pycrmkit.webhooks import (
    WebhookDeliveryState,
    WebhookRequest,
    WebhookResponse,
    WebhookRetryPolicy,
)

pytestmark = pytest.mark.postgresql

NOW = datetime(2026, 9, 26, 15, 30, tzinfo=UTC)
WEBHOOK_SECRET = "0123456789abcdef0123456789abcdef"


class AcceptingProvider:
    def __init__(self) -> None:
        self.messages: list[EmailMessage] = []

    def send(self, message: EmailMessage) -> EmailProviderResult:
        self.messages.append(message)
        return EmailProviderResult(
            provider="rc-provider",
            status=EmailDeliveryStatus.ACCEPTED,
            provider_message_id=f"msg-{len(self.messages)}",
        )


class SequenceTransport:
    def __init__(self) -> None:
        self.requests: list[WebhookRequest] = []
        self.responses = [WebhookResponse(503), WebhookResponse(204)]

    def send(self, request: WebhookRequest) -> WebhookResponse:
        self.requests.append(request)
        return self.responses.pop(0)


def _crm(
    factory: sessionmaker[Session],
    *,
    clock: FixedClock,
    provider: AcceptingProvider | None = None,
    transport: SequenceTransport | None = None,
    webhook_auto_delivery: bool = True,
) -> CRM:
    bus = InProcessEventBus()

    def uow_factory() -> UnitOfWork:
        return SQLAlchemyUnitOfWork(factory, event_publisher=bus)

    return CRM(
        uow_factory=uow_factory,
        event_bus=bus,
        clock=clock,
        email_provider=provider,
        email_sender=CommunicationAddress(
            CommunicationChannel.EMAIL,
            "sales@example.com",
        ),
        webhook_transport=transport,
        webhook_retry_policy=WebhookRetryPolicy(max_attempts=2),
        webhook_auto_delivery=webhook_auto_delivery,
    )


def _define_pipeline(crm: CRM) -> None:
    crm.pipelines.define(
        id="sales",
        name="Sales",
        stages=(
            Stage("new", "New", 0, Decimal("0.10")),
            Stage("qualified", "Qualified", 10, Decimal("0.30")),
            Stage("proposal", "Proposal", 20, Decimal("0.60")),
            Stage("won", "Won", 30, terminal=True, outcome="won"),
        ),
        transitions=(
            StageTransition("new", "qualified"),
            StageTransition("qualified", "proposal"),
            StageTransition("proposal", "won"),
        ),
    )


def test_stable_0_1_to_0_5_surface_round_trips_through_postgresql(
    persistence_session_factory: sessionmaker[Session],
) -> None:
    clock = FixedClock(NOW)
    provider = AcceptingProvider()
    transport = SequenceTransport()
    crm = _crm(
        persistence_session_factory,
        clock=clock,
        provider=provider,
        transport=transport,
    ).with_context(
        actor_id="persistence-rc",
        correlation_id="corr-persistence-rc",
    )

    # 0.1 — CRM Core
    contact = crm.contacts.create(
        first_name="Ada",
        last_name="Lovelace",
        emails=(ContactEmail("ada@example.test", is_primary=True),),
    )
    organization = crm.organizations.create(
        legal_name="Analytical Engines Ltd",
    )
    relationship = crm.relationships.create(
        source=RelationshipEndpoint.contact(contact.id),
        target=RelationshipEndpoint.organization(organization.id),
        relationship_type=RelationshipType("employment"),
        role="founder",
        is_primary=True,
    )
    contact_ref = EntityReference("contact", contact.id)
    vip = crm.tags.create("VIP")
    crm.tags.assign(vip.id, contact_ref)
    tier = crm.custom_fields.define(
        key="customer_tier",
        label="Customer Tier",
        field_type=CustomFieldType.STRING,
        applies_to=("contact",),
    )
    tier_value = crm.custom_fields.set_value(
        tier.id,
        contact_ref,
        "gold",
    )

    # 0.2 — Activity, Task and Timeline
    activity = crm.activities.log(
        type="meeting",
        subject="Persistence RC discovery",
        participants=(
            ActivityParticipant(
                contact_ref,
                role="customer",
                is_primary=True,
            ),
        ),
        references=(EntityReference("organization", organization.id),),
    )
    task = crm.tasks.create(
        title="Prepare proposal",
        priority="high",
        due_at=NOW + timedelta(hours=2),
        references=(contact_ref,),
    )
    clock.advance(timedelta(minutes=5))
    task = crm.tasks.start(task.id)
    clock.advance(timedelta(minutes=5))
    task = crm.tasks.complete(task.id)
    assert task.status is TaskStatus.COMPLETED

    # 0.3 — Sales
    _define_pipeline(crm)
    lead = crm.leads.create(
        contact_id=contact.id,
        organization_id=organization.id,
        source="website",
    )
    lead = crm.leads.qualify(lead.id)
    opportunity = crm.leads.convert(
        lead.id,
        name="Persistence rollout",
        estimated_value=Decimal("25000.00"),
        currency="EUR",
        pipeline_id="sales",
        idempotency_key="persistence-rc-convert",
    )
    for stage in ("qualified", "proposal", "won"):
        opportunity = crm.opportunities.move(
            opportunity.id,
            to=stage,
        )
    assert opportunity.status is OpportunityStatus.WON

    # 0.4 — Communication
    record = crm.email.send(
        to=(
            CommunicationRecipient(
                CommunicationAddress(
                    CommunicationChannel.EMAIL,
                    "ada@example.test",
                ),
                reference=contact_ref,
            ),
        ),
        content=CommunicationContent(
            subject="Persistence RC",
            text_body="Qualified on PostgreSQL.",
        ),
        idempotency_key="persistence-rc-email",
    )
    assert record.delivery_status is EmailDeliveryEventType.SENT
    clock.advance(timedelta(minutes=1))
    crm.email.record_delivery_event(
        provider="rc-provider",
        provider_message_id=record.external_id or "",
        event_type=EmailDeliveryEventType.DELIVERED,
        occurred_at=clock.now(),
        external_event_id="evt-persistence-rc-delivered",
    )

    # 0.5 — Eventing & Webhooks
    observed: list[DomainEvent] = []
    crm.events.subscribe("contact.created", observed.append)
    subscription = crm.webhooks.register(
        url="https://hooks.example.com/persistence-rc",
        events=("contact.created",),
        signing_secret=WEBHOOK_SECRET,
    )
    webhook_contact = crm.contacts.create(
        display_name="Webhook PostgreSQL Contact",
    )
    assert webhook_contact.display_name == "Webhook PostgreSQL Contact"
    assert len(observed) == 1

    deliveries = crm.webhooks.deliveries(event_id=observed[0].id)
    assert deliveries.total == 1
    pending = deliveries.items[0]
    assert pending.subscription_id == subscription.id
    assert pending.state is WebhookDeliveryState.RETRY_SCHEDULED
    clock.advance(timedelta(seconds=10))
    retried = crm.webhooks.retry_due()
    assert retried[0].state is WebhookDeliveryState.SUCCEEDED
    assert len(transport.requests) == 2

    # New CRM/runtime + new Sessions must observe durable state.
    reloaded = _crm(
        persistence_session_factory,
        clock=clock,
        webhook_auto_delivery=False,
    )
    assert reloaded.contacts.get(contact.id) == contact
    assert reloaded.organizations.get(organization.id) == organization
    assert reloaded.relationships.get(relationship.id) == relationship
    assert reloaded.tags.list_for_entity(contact_ref).items == (vip,)
    assert reloaded.custom_fields.get_value(tier.id, contact_ref) == tier_value
    assert reloaded.activities.get(activity.id) == activity
    assert reloaded.tasks.get(task.id) == task
    assert reloaded.opportunities.get(opportunity.id) == opportunity
    assert reloaded.email.get(record.id).delivery_status is EmailDeliveryEventType.DELIVERED
    assert reloaded.webhooks.deliveries(
        state=WebhookDeliveryState.SUCCEEDED
    ).total == 1

    timeline = reloaded.timeline.for_contact(contact.id)
    event_types = {str(item.event_type) for item in timeline.items}
    assert {
        "contact.created",
        "activity.created",
        "task.created",
        "task.started",
        "task.completed",
        "email.queued",
        "email.sent",
        "email.delivered",
    } <= event_types

    audit = reloaded.audit.by_correlation("corr-persistence-rc")
    assert audit.total >= 15


def test_failed_postgresql_uow_rolls_back_all_participants(
    persistence_session_factory: sessionmaker[Session],
) -> None:
    clock = FixedClock(NOW)
    crm = _crm(
        persistence_session_factory,
        clock=clock,
        webhook_auto_delivery=False,
    )

    with pytest.raises(RuntimeError, match="force rollback"):
        with crm._runtime.uow_factory() as uow:
            contact = crm.contacts._runtime.id_factory.new_contact_id()
            del contact
            transient = crm.contacts.create(display_name="Outside transaction")
            del transient
            raise RuntimeError("force rollback")
