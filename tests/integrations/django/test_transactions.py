"""Transaction semantics for the Django CRM bridge."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest
from django.db import transaction

from pycrmkit.contacts import Contact, ContactId
from pycrmkit.core.events import EventId, EventType
from pycrmkit.events import DomainEvent, InProcessEventBus
from pycrmkit.exceptions import InvalidStateError
from pycrmkit.integrations.django.repositories import (
    DjangoContactRepository,
    DjangoOrganizationRepository,
)
from pycrmkit.integrations.django.transactions import DjangoTransactionBridge
from pycrmkit.organizations import Organization, OrganizationId

NOW = datetime(2026, 9, 26, 20, 0, tzinfo=UTC)


def _contact(number: int = 8201) -> Contact:
    return Contact(
        id=ContactId(UUID(int=number)),
        created_at=NOW,
        updated_at=NOW,
        first_name=f"Django {number}",
    )


def _organization(number: int = 8301) -> Organization:
    return Organization(
        id=OrganizationId(UUID(int=number)),
        created_at=NOW,
        updated_at=NOW,
        legal_name=f"Django Organization {number}",
    )


def _event(number: int = 8401) -> DomainEvent:
    contact = _contact()
    return DomainEvent(
        id=EventId(UUID(int=number)),
        type=EventType("contact.created"),
        schema_version=1,
        aggregate_type="contact",
        aggregate_id=str(contact.id),
        occurred_at=NOW,
        actor_id="django-transaction-test",
        correlation_id="corr-django-transaction",
    )


def test_bridge_requires_context_before_repository_access() -> None:
    bridge = DjangoTransactionBridge()

    with pytest.raises(InvalidStateError) as repository_error:
        _ = bridge.contacts
    with pytest.raises(InvalidStateError) as commit_error:
        bridge.commit()

    assert repository_error.value.code == "django.transaction.not_active"
    assert commit_error.value.code == "django.transaction.not_active"


def test_commit_persists_multiple_repositories_atomically() -> None:
    contact = _contact()
    organization = _organization()

    with DjangoTransactionBridge() as bridge:
        bridge.contacts.save(contact)
        bridge.organizations.save(organization)
        bridge.commit()

    assert DjangoContactRepository().get(contact.id) == contact
    assert DjangoOrganizationRepository().get(organization.id) == organization


def test_exit_without_commit_rolls_back_all_writes() -> None:
    contact = _contact()
    organization = _organization()

    with DjangoTransactionBridge() as bridge:
        bridge.contacts.save(contact)
        bridge.organizations.save(organization)

    assert DjangoContactRepository().find(contact.id) is None
    assert DjangoOrganizationRepository().find(organization.id) is None


def test_exception_rolls_back_transaction() -> None:
    contact = _contact()

    with pytest.raises(RuntimeError, match="boom"):
        with DjangoTransactionBridge() as bridge:
            bridge.contacts.save(contact)
            raise RuntimeError("boom")

    assert DjangoContactRepository().find(contact.id) is None


def test_explicit_rollback_discards_work_and_opens_fresh_transaction() -> None:
    discarded = _contact(8202)
    committed = _organization(8302)

    with DjangoTransactionBridge() as bridge:
        bridge.contacts.save(discarded)
        bridge.rollback()
        assert bridge.contacts.find(discarded.id) is None

        bridge.organizations.save(committed)
        bridge.commit()

    assert DjangoContactRepository().find(discarded.id) is None
    assert DjangoOrganizationRepository().get(committed.id) == committed


def test_top_level_events_publish_only_after_database_commit() -> None:
    bus = InProcessEventBus()
    published: list[DomainEvent] = []
    event = _event()
    contact = _contact()
    bus.subscribe("contact.created", published.append)

    with DjangoTransactionBridge(event_publisher=bus) as bridge:
        bridge.contacts.save(contact)
        bridge.add_event(event)
        assert bridge.pending_events == (event,)
        assert published == []
        bridge.commit()
        assert published == [event]

    assert DjangoContactRepository().get(contact.id) == contact


def test_ambient_transaction_defers_events_until_outer_commit() -> None:
    bus = InProcessEventBus()
    published: list[DomainEvent] = []
    event = _event(8402)
    bus.subscribe("contact.created", published.append)

    with transaction.atomic():
        with DjangoTransactionBridge(event_publisher=bus) as bridge:
            bridge.contacts.save(_contact(8203))
            bridge.add_event(event)
            bridge.commit()

        assert published == []

    assert published == [event]


def test_outer_rollback_discards_bridge_commit_and_pending_event() -> None:
    bus = InProcessEventBus()
    published: list[DomainEvent] = []
    event = _event(8403)
    contact = _contact(8204)
    bus.subscribe("contact.created", published.append)

    with pytest.raises(RuntimeError, match="outer rollback"):
        with transaction.atomic():
            with DjangoTransactionBridge(event_publisher=bus) as bridge:
                bridge.contacts.save(contact)
                bridge.add_event(event)
                bridge.commit()
            raise RuntimeError("outer rollback")

    assert DjangoContactRepository().find(contact.id) is None
    assert published == []


def test_post_commit_subscriber_failure_does_not_undo_committed_state() -> None:
    bus = InProcessEventBus()
    contact = _contact(8205)

    def fail(event: DomainEvent) -> None:
        del event
        raise RuntimeError("subscriber failed")

    bus.subscribe("contact.created", fail)

    with pytest.raises(RuntimeError, match="subscriber failed"):
        with DjangoTransactionBridge(event_publisher=bus) as bridge:
            bridge.contacts.save(contact)
            bridge.add_event(_event(8404))
            bridge.commit()

    assert DjangoContactRepository().get(contact.id) == contact


def test_repository_access_after_commit_is_rejected() -> None:
    with DjangoTransactionBridge() as bridge:
        bridge.commit()
        with pytest.raises(InvalidStateError) as error:
            _ = bridge.contacts

    assert error.value.code == "django.transaction.already_committed"
