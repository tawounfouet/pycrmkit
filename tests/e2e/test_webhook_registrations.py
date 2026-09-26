"""End-to-end Memory facade scenario for webhook registrations."""

from datetime import UTC, datetime

from pycrmkit import CRM
from pycrmkit.core.time import FixedClock
from pycrmkit.events import EventRegistry

NOW = datetime(2026, 9, 26, 8, 0, tzinfo=UTC)


def test_webhook_registration_disable_filtering_and_audit() -> None:
    crm = CRM.memory(clock=FixedClock(NOW)).with_context(
        actor_id="admin-1",
        correlation_id="webhook-config-1",
    )

    contact = crm.webhooks.register(
        url="https://hooks.example.com/contact",
        events=("contact.created", "contact.updated"),
    )
    sales = crm.webhooks.register(
        url="https://hooks.example.com/sales",
        events=("opportunity.won",),
    )

    assert crm.webhooks.list().total == 2
    assert crm.webhooks.list(event_type="contact.created").items == (contact,)
    assert crm.webhooks.list(enabled=True).total == 2

    disabled = crm.webhooks.disable(contact.id)
    assert disabled.enabled is False
    assert crm.webhooks.list(enabled=True).items == (sales,)
    assert crm.webhooks.list(enabled=False).items == (disabled,)

    # Idempotent disable does not create duplicate audit history.
    crm.webhooks.disable(contact.id)
    audit = crm.audit.by_correlation("webhook-config-1")
    assert [entry.action for entry in audit.items] == [
        "webhook.subscription.registered",
        "webhook.subscription.registered",
        "webhook.subscription.disabled",
    ]
    assert all("hooks.example.com" not in repr(entry.changes) for entry in audit.items)


def test_custom_event_registry_can_govern_webhook_registration() -> None:
    registry = EventRegistry()
    registry.register("customer.enriched", 1)
    crm = CRM.memory(event_registry=registry)

    subscription = crm.webhooks.register(
        url="https://hooks.example.com/custom",
        events=("customer.enriched",),
    )

    assert tuple(map(str, subscription.event_types)) == ("customer.enriched",)
