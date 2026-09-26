"""Transactional qualification for SQLAlchemyUnitOfWork."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from pycrmkit.audit import AuditEntry, AuditEntryId
from pycrmkit.contacts import Contact, ContactId
from pycrmkit.core.events import EventId, EventType
from pycrmkit.events import DomainEvent, InProcessEventBus
from pycrmkit.exceptions import InvalidStateError, NotFoundError
from pycrmkit.organizations import Organization, OrganizationId
from pycrmkit.storage.sqlalchemy import Base, SQLAlchemyUnitOfWork

NOW = datetime(2026, 9, 26, 12, 30, tzinfo=UTC)


@pytest.fixture
def session_factory(tmp_path: Path) -> Iterator[sessionmaker[Session]]:
    engine = create_engine(
        f"sqlite+pysqlite:///{tmp_path / 'uow.sqlite'}",
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    yield factory
    engine.dispose()


def _contact(number: int = 501) -> Contact:
    return Contact(
        id=ContactId(UUID(int=number)),
        created_at=NOW,
        updated_at=NOW,
        first_name=f"Contact {number}",
    )


def _organization(number: int = 601) -> Organization:
    return Organization(
        id=OrganizationId(UUID(int=number)),
        created_at=NOW,
        updated_at=NOW,
        legal_name=f"Organization {number}",
    )


def _event(number: int = 920) -> DomainEvent:
    contact = _contact()
    return DomainEvent(
        id=EventId(UUID(int=number)),
        type=EventType("contact.created"),
        schema_version=1,
        aggregate_type="contact",
        aggregate_id=str(contact.id),
        occurred_at=NOW,
        actor_id="sqlalchemy-uow-test",
        correlation_id="corr-sqlalchemy-uow",
    )


def _audit(number: int = 930) -> AuditEntry:
    contact = _contact()
    return AuditEntry(
        id=AuditEntryId(UUID(int=number)),
        actor_id="sqlalchemy-uow-test",
        action="contact.created",
        entity_type="contact",
        entity_id=str(contact.id),
        occurred_at=NOW,
        correlation_id="corr-sqlalchemy-uow",
    )


def test_uow_requires_context_before_repository_access(
    session_factory: sessionmaker[Session],
) -> None:
    uow = SQLAlchemyUnitOfWork(session_factory)

    with pytest.raises(InvalidStateError) as repository_error:
        _ = uow.contacts
    with pytest.raises(InvalidStateError) as commit_error:
        uow.commit()

    assert repository_error.value.code == "sqlalchemy.uow.not_active"
    assert commit_error.value.code == "sqlalchemy.uow.not_active"


def test_all_repositories_share_one_session(
    session_factory: sessionmaker[Session],
) -> None:
    with SQLAlchemyUnitOfWork(session_factory) as uow:
        repositories = (
            uow.activities,
            uow.communications,
            uow.contacts,
            uow.leads,
            uow.opportunities,
            uow.pipelines,
            uow.organizations,
            uow.relationships,
            uow.tasks,
            uow.timeline,
            uow.tags,
            uow.custom_fields,
            uow.audit,
            uow.webhooks,
            uow.webhook_deliveries,
        )
        sessions = {id(repository.session) for repository in repositories}

    assert len(sessions) == 1


def test_commit_persists_multiple_repositories_atomically(
    session_factory: sessionmaker[Session],
) -> None:
    contact = _contact()
    organization = _organization()
    audit = _audit()

    with SQLAlchemyUnitOfWork(session_factory) as uow:
        uow.contacts.save(contact)
        uow.organizations.save(organization)
        uow.audit.append(audit)
        uow.commit()

    with SQLAlchemyUnitOfWork(session_factory) as uow:
        assert uow.contacts.get(contact.id) == contact
        assert uow.organizations.get(organization.id) == organization
        assert uow.audit.get(audit.id) == audit


def test_exit_without_commit_rolls_back_all_repositories(
    session_factory: sessionmaker[Session],
) -> None:
    contact = _contact()
    organization = _organization()

    with SQLAlchemyUnitOfWork(session_factory) as uow:
        uow.contacts.save(contact)
        uow.organizations.save(organization)

    with SQLAlchemyUnitOfWork(session_factory) as uow:
        with pytest.raises(NotFoundError):
            uow.contacts.get(contact.id)
        with pytest.raises(NotFoundError):
            uow.organizations.get(organization.id)


def test_explicit_rollback_discards_state_and_uow_can_continue(
    session_factory: sessionmaker[Session],
) -> None:
    contact = _contact()
    organization = _organization()

    with SQLAlchemyUnitOfWork(session_factory) as uow:
        uow.contacts.save(contact)
        uow.rollback()
        assert uow.contacts.find(contact.id) is None

        uow.organizations.save(organization)
        uow.commit()

    with SQLAlchemyUnitOfWork(session_factory) as uow:
        assert uow.contacts.find(contact.id) is None
        assert uow.organizations.get(organization.id) == organization


def test_exception_rolls_back_staged_state(
    session_factory: sessionmaker[Session],
) -> None:
    contact = _contact()

    with pytest.raises(RuntimeError, match="boom"):
        with SQLAlchemyUnitOfWork(session_factory) as uow:
            uow.contacts.save(contact)
            raise RuntimeError("boom")

    with SQLAlchemyUnitOfWork(session_factory) as uow:
        assert uow.contacts.find(contact.id) is None


def test_bulk_write_foundation_commits_or_rolls_back_as_one_transaction(
    session_factory: sessionmaker[Session],
) -> None:
    committed = tuple(_contact(number) for number in range(1001, 1006))
    discarded = tuple(_contact(number) for number in range(1101, 1106))

    with SQLAlchemyUnitOfWork(session_factory) as uow:
        for contact in committed:
            uow.contacts.save(contact)
        uow.commit()

    with SQLAlchemyUnitOfWork(session_factory) as uow:
        for contact in discarded:
            uow.contacts.save(contact)

    with SQLAlchemyUnitOfWork(session_factory) as uow:
        assert all(uow.contacts.get(contact.id) == contact for contact in committed)
        assert all(uow.contacts.find(contact.id) is None for contact in discarded)


def test_domain_events_dispatch_only_after_successful_commit(
    session_factory: sessionmaker[Session],
) -> None:
    bus = InProcessEventBus()
    published: list[DomainEvent] = []
    event = _event()
    bus.subscribe("contact.created", published.append)

    with SQLAlchemyUnitOfWork(session_factory, event_publisher=bus) as uow:
        uow.add_event(event)
        assert uow.pending_events == (event,)
        assert published == []
        uow.commit()
        assert published == [event]
        assert uow.pending_events == ()


def test_rollback_and_uncommitted_exit_discard_pending_events(
    session_factory: sessionmaker[Session],
) -> None:
    bus = InProcessEventBus()
    published: list[DomainEvent] = []
    bus.subscribe("contact.created", published.append)

    with SQLAlchemyUnitOfWork(session_factory, event_publisher=bus) as uow:
        uow.add_event(_event(921))
        uow.rollback()

    with SQLAlchemyUnitOfWork(session_factory, event_publisher=bus) as uow:
        uow.add_event(_event(922))

    assert published == []


def test_post_commit_subscriber_can_open_follow_up_uow(
    session_factory: sessionmaker[Session],
) -> None:
    bus = InProcessEventBus()
    contact = _contact()
    observed: list[Contact] = []

    def inspect_committed_state(event: DomainEvent) -> None:
        del event
        with SQLAlchemyUnitOfWork(session_factory) as follow_up:
            observed.append(follow_up.contacts.get(contact.id))

    bus.subscribe("contact.created", inspect_committed_state)

    with SQLAlchemyUnitOfWork(session_factory, event_publisher=bus) as uow:
        uow.contacts.save(contact)
        uow.add_event(_event())
        uow.commit()

    assert observed == [contact]


def test_handler_failure_does_not_undo_committed_database_state(
    session_factory: sessionmaker[Session],
) -> None:
    bus = InProcessEventBus()
    contact = _contact()

    def fail(event: DomainEvent) -> None:
        del event
        raise RuntimeError("subscriber failed")

    bus.subscribe("contact.created", fail)

    with pytest.raises(RuntimeError, match="subscriber failed"):
        with SQLAlchemyUnitOfWork(session_factory, event_publisher=bus) as uow:
            uow.contacts.save(contact)
            uow.add_event(_event())
            uow.commit()

    with SQLAlchemyUnitOfWork(session_factory) as uow:
        assert uow.contacts.get(contact.id) == contact


def test_second_commit_on_same_uow_is_rejected(
    session_factory: sessionmaker[Session],
) -> None:
    with SQLAlchemyUnitOfWork(session_factory) as uow:
        uow.commit()
        with pytest.raises(InvalidStateError) as error:
            uow.commit()

    assert error.value.code == "sqlalchemy.uow.already_committed"
