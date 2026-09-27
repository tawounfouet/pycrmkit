"""PyCRMKit V1 cross-layer production qualification scenario.

RC-02 deliberately qualifies the framework-agnostic system path. PostgreSQL,
migrations and framework integrations remain dedicated RC-03/RC-04 gates.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pycrmkit
from examples.data_operations.scenario import run_scenario as run_data_operations
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
from pycrmkit.events import DomainEvent
from pycrmkit.pipelines import Stage, StageTransition
from pycrmkit.relationships import RelationshipEndpoint, RelationshipType
from pycrmkit.webhooks import (
    WebhookDeliveryState,
    WebhookRequest,
    WebhookResponse,
    verify_webhook_signature,
)

NOW = datetime(2026, 9, 27, 14, 0, tzinfo=UTC)
WEBHOOK_SECRET = "0123456789abcdef0123456789abcdef"


@dataclass(slots=True)
class AcceptingEmailProvider:
    messages: list[EmailMessage] = field(default_factory=list)

    def send(self, message: EmailMessage) -> EmailProviderResult:
        self.messages.append(message)
        return EmailProviderResult(
            provider="qualification",
            status=EmailDeliveryStatus.ACCEPTED,
            provider_message_id="msg-v1-production",
            provider_metadata={"request_id": "req-v1-production"},
        )


@dataclass(slots=True)
class CapturingWebhookTransport:
    requests: list[WebhookRequest] = field(default_factory=list)

    def send(self, request: WebhookRequest) -> WebhookResponse:
        self.requests.append(request)
        return WebhookResponse(204)


def _define_pipeline(crm: CRM) -> None:
    crm.pipelines.define(
        id="production-sales",
        name="Production Sales",
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


def run_headless_customer_journey() -> dict[str, object]:
    clock = FixedClock(NOW)
    email_provider = AcceptingEmailProvider()
    webhook_transport = CapturingWebhookTransport()
    crm = CRM.memory(
        clock=clock,
        email_provider=email_provider,
        email_sender=CommunicationAddress(
            CommunicationChannel.EMAIL,
            "sales@example.test",
        ),
        webhook_transport=webhook_transport,
    ).with_context(
        actor_id="production-qualification",
        correlation_id="v1-production-qualification",
    )

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
    organization_ref = EntityReference("organization", organization.id)

    activity = crm.activities.log(
        type="meeting",
        subject="Discovery meeting",
        participants=(ActivityParticipant(contact_ref, is_primary=True),),
        references=(organization_ref,),
    )
    clock.advance(timedelta(minutes=5))
    task = crm.tasks.create(
        title="Prepare proposal",
        priority="high",
        references=(contact_ref, organization_ref),
    )
    clock.advance(timedelta(minutes=5))
    crm.tasks.start(task.id)
    clock.advance(timedelta(minutes=5))
    completed_task = crm.tasks.complete(task.id)

    _define_pipeline(crm)
    subscription = crm.webhooks.register(
        url="https://hooks.example.test/crm",
        events=("opportunity.won",),
        signing_secret=WEBHOOK_SECRET,
    )
    won_events: list[DomainEvent] = []
    crm.events.subscribe("opportunity.won", won_events.append)

    lead = crm.leads.create(
        contact_id=contact.id,
        organization_id=organization.id,
        source="production-qualification",
    )
    qualified = crm.leads.qualify(lead.id)
    opportunity = crm.leads.convert(
        qualified.id,
        name="Analytical Engine rollout",
        estimated_value=Decimal("25000.00"),
        currency="EUR",
        pipeline_id="production-sales",
        owner_id="production-qualification",
        idempotency_key="v1-production-lead-conversion",
    )
    replay = crm.leads.convert(
        qualified.id,
        name="Analytical Engine rollout",
        estimated_value=Decimal("25000.0"),
        currency="eur",
        pipeline_id="PRODUCTION-SALES",
        owner_id="production-qualification",
        idempotency_key="v1-production-lead-conversion",
    )
    assert replay.id == opportunity.id

    for stage in ("qualified", "proposal", "won"):
        clock.advance(timedelta(minutes=5))
        opportunity = crm.opportunities.move(opportunity.id, to=stage)

    assert len(won_events) == 1
    won_event = won_events[0]
    deliveries = crm.webhooks.deliveries(event_id=won_event.id)
    assert deliveries.total == 1
    delivery = deliveries.items[0]
    assert delivery.subscription_id == subscription.id
    assert delivery.state is WebhookDeliveryState.SUCCEEDED
    assert delivery.attempt_count == 1
    assert len(webhook_transport.requests) == 1

    webhook_request = webhook_transport.requests[0]
    assert webhook_request.headers["X-PyCRMKit-Event-Type"] == "opportunity.won"
    assert verify_webhook_signature(
        WEBHOOK_SECRET,
        int(webhook_request.headers["X-PyCRMKit-Timestamp"]),
        webhook_request.body,
        webhook_request.headers["X-PyCRMKit-Signature"],
    )

    clock.advance(timedelta(minutes=5))
    email_record = crm.email.send(
        to=(
            CommunicationRecipient(
                CommunicationAddress(
                    CommunicationChannel.EMAIL,
                    "ada@example.test",
                ),
                display_name="Ada Lovelace",
                reference=contact_ref,
            ),
        ),
        content=CommunicationContent(
            subject="Proposal",
            text_body="Your proposal is ready.",
        ),
        references=(organization_ref,),
        idempotency_key="v1-production-email",
    )
    assert email_record.delivery_status is EmailDeliveryEventType.SENT
    assert email_record.external_id == "msg-v1-production"
    assert len(email_provider.messages) == 1

    clock.advance(timedelta(minutes=1))
    crm.email.record_delivery_event(
        provider="qualification",
        provider_message_id="msg-v1-production",
        event_type=EmailDeliveryEventType.DELIVERED,
        occurred_at=clock.now(),
        external_event_id="evt-v1-production-delivered",
    )

    contact_timeline = crm.timeline.for_contact(contact.id)
    timeline_types = {str(entry.event_type) for entry in contact_timeline.items}
    assert {
        "activity.created",
        "task.created",
        "task.started",
        "task.completed",
        "email.queued",
        "email.sent",
        "email.delivered",
    } <= timeline_types

    audit = crm.audit.by_correlation("v1-production-qualification")
    audit_actions = {entry.action for entry in audit.items}
    assert {
        "contact.created",
        "organization.created",
        "relationship.created",
        "activity.created",
        "task.created",
        "task.started",
        "task.completed",
        "lead.created",
        "lead.qualified",
        "lead.converted",
        "opportunity.created",
        "opportunity.stage_changed",
        "opportunity.won",
        "webhook.subscription.registered",
        "email.queued",
        "email.sent",
        "email.delivered",
    } <= audit_actions

    assert crm.contacts.get(contact.id) == contact
    assert crm.organizations.get(organization.id) == organization
    assert crm.relationships.get(relationship.id) == relationship
    assert crm.activities.get(activity.id) == activity
    assert crm.tasks.get(task.id) == completed_task
    assert crm.email.for_contact(contact.id).items == (crm.email.get(email_record.id),)

    return {
        "contact": str(contact.id),
        "organization": str(organization.id),
        "relationship": str(relationship.id),
        "activity": str(activity.id),
        "task": str(task.id),
        "lead": str(qualified.id),
        "opportunity": str(opportunity.id),
        "opportunity_status": opportunity.status.value,
        "opportunity_stage": opportunity.stage_id,
        "timeline_event_types": sorted(timeline_types),
        "webhook_state": delivery.state.value,
        "webhook_attempts": delivery.attempt_count,
        "email_status": crm.email.get(email_record.id).delivery_status.value,
        "audit_entries": audit.total,
    }


def run_scenario() -> dict[str, object]:
    headless = run_headless_customer_journey()
    data_operations = run_data_operations()

    assert pycrmkit.__version__ == "1.0.0"
    assert data_operations["version"] == pycrmkit.__version__

    return {
        "version": pycrmkit.__version__,
        "qualification": "1.0.0-rc02-cross-layer-e2e",
        "headless_customer_journey": headless,
        "data_operations": {
            "import": data_operations["import"],
            "review": data_operations["review"],
            "merge": data_operations["merge"],
            "export": data_operations["export"],
        },
    }


def main() -> None:
    print(json.dumps(run_scenario(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
