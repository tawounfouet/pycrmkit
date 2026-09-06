"""CRM facade wiring and context tests."""

from __future__ import annotations

from datetime import UTC, datetime

from pycrmkit import CRM, CRMConfig
from pycrmkit.contacts import ContactUpdate
from pycrmkit.core.time import FixedClock
from pycrmkit.events import DomainEvent

NOW = datetime(2026, 9, 6, 20, 0, tzinfo=UTC)


def test_memory_facade_isolated_instances() -> None:
    first = CRM.memory()
    second = CRM.memory()
    contact = first.contacts.create(first_name="Ada")

    assert first.contacts.get(contact.id) == contact
    assert second.contacts.search().total == 0


def test_context_is_shared_with_same_backend_but_overrides_actor_and_correlation() -> None:
    crm = CRM.memory(clock=FixedClock(NOW))
    scoped = crm.with_context(actor_id="user-42", correlation_id="corr-42")

    contact = scoped.contacts.create(first_name="Grace")

    assert crm.contacts.get(contact.id) == contact
    audit = crm.audit.by_correlation("corr-42")
    assert audit.total == 1
    assert audit.items[0].actor_id == "user-42"
    assert audit.items[0].action == "contact.created"


def test_contact_mutations_emit_events_and_audit_without_copying_pii_values() -> None:
    crm = CRM.memory(clock=FixedClock(NOW))
    published: list[DomainEvent] = []
    crm.events.subscribe("contact.created", published.append)
    crm.events.subscribe("contact.updated", published.append)

    contact = crm.contacts.create(first_name="Ada", emails=())
    crm.contacts.update(contact.id, ContactUpdate(last_name="Lovelace"))

    assert [str(event.type) for event in published] == ["contact.created", "contact.updated"]
    history = crm.audit.for_entity("contact", contact.id)
    assert history.total == 2
    assert all("Ada" not in repr(entry.changes) for entry in history.items)
    assert all("Lovelace" not in repr(entry.changes) for entry in history.items)


def test_events_and_audit_can_be_disabled_independently() -> None:
    published: list[DomainEvent] = []
    no_events = CRM.memory(config=CRMConfig(events_enabled=False, audit_enabled=True))
    no_events.events.subscribe("contact.created", published.append)
    contact = no_events.contacts.create(first_name="No Event")
    assert published == []
    assert no_events.audit.for_entity("contact", contact.id).total == 1

    no_audit = CRM.memory(config=CRMConfig(events_enabled=True, audit_enabled=False))
    captured: list[DomainEvent] = []
    no_audit.events.subscribe("contact.created", captured.append)
    contact2 = no_audit.contacts.create(first_name="No Audit")
    assert len(captured) == 1
    assert no_audit.audit.for_entity("contact", contact2.id).total == 0


def test_config_defaults_seed_initial_context() -> None:
    crm = CRM.memory(
        config=CRMConfig(
            default_actor_id="system",
            default_correlation_id="bootstrap",
        )
    )
    assert crm.context.actor_id == "system"
    assert crm.context.correlation_id == "bootstrap"
