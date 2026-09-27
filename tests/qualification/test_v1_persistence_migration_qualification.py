"""RC-03 V1 persistence and migration qualification on live PostgreSQL."""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import UUID

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from pycrmkit import CRM
from pycrmkit.activities import ActivityParticipant
from pycrmkit.contacts import Contact, ContactEmail, ContactId, ContactStatus
from pycrmkit.core.pagination import OffsetPageRequest
from pycrmkit.core.references import EntityReference
from pycrmkit.core.time import FixedClock
from pycrmkit.core.unit_of_work import UnitOfWork
from pycrmkit.custom_fields import CustomFieldType
from pycrmkit.dedup import (
    DedupDecision,
    DedupProvenance,
    DedupSignal,
    MergeService,
    SignalMatch,
)
from pycrmkit.events import InProcessEventBus
from pycrmkit.exceptions import ConflictError
from pycrmkit.relationships import RelationshipEndpoint, RelationshipType
from pycrmkit.storage.sqlalchemy import Base, SQLAlchemyUnitOfWork

pytestmark = pytest.mark.postgresql

DATABASE_ENV = "PYCRMKIT_TEST_POSTGRES_URL"
NOW = datetime(2026, 9, 27, 15, 0, tzinfo=UTC)
MERGED_AT = datetime(2026, 9, 27, 15, 30, tzinfo=UTC)


@pytest.fixture
def production_engine() -> Iterator[Engine]:
    database_url = os.environ.get(DATABASE_ENV)
    if not database_url:
        pytest.skip(f"{DATABASE_ENV} is required for PostgreSQL qualification")

    engine = create_engine(database_url, pool_pre_ping=True)
    _reset_schema(engine)
    command.upgrade(_alembic_config(database_url), "head")
    try:
        yield engine
    finally:
        _reset_schema(engine)
        engine.dispose()


def _reset_schema(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.exec_driver_sql("DROP SCHEMA IF EXISTS public CASCADE")
        connection.exec_driver_sql("CREATE SCHEMA public")


def _alembic_config(database_url: str) -> Config:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def _current_revision(engine: Engine) -> str | None:
    if "alembic_version" not in inspect(engine).get_table_names():
        return None
    with engine.connect() as connection:
        return connection.scalar(text("SELECT version_num FROM alembic_version"))


def _schema_diffs(engine: Engine) -> list[object]:
    with engine.connect() as connection:
        context = MigrationContext.configure(
            connection,
            opts={"compare_type": True, "compare_server_default": True},
        )
        return list(compare_metadata(context, Base.metadata))


def _session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


def _crm(factory: sessionmaker[Session], clock: FixedClock | None = None) -> CRM:
    bus = InProcessEventBus()

    def uow_factory() -> UnitOfWork:
        return SQLAlchemyUnitOfWork(factory, event_publisher=bus)

    return CRM(
        uow_factory=uow_factory,
        event_bus=bus,
        clock=clock or FixedClock(NOW),
        webhook_auto_delivery=False,
    )


def _provenance(duplicate_id: ContactId) -> DedupProvenance:
    return DedupProvenance(
        candidate_entity_id=str(duplicate_id),
        score=100,
        decision=DedupDecision.DUPLICATE,
        matches=(SignalMatch(DedupSignal.EMAIL, "ada@example.test"),),
    )


def test_previous_stable_head_to_v1_candidate_is_noop_and_preserves_fixture(
    production_engine: Engine,
) -> None:
    database_url = os.environ[DATABASE_ENV]
    config = _alembic_config(database_url)
    factory = _session_factory(production_engine)

    assert _current_revision(production_engine) == "0003"
    assert _schema_diffs(production_engine) == []

    fixture = Contact(
        id=ContactId(UUID("00000000-0000-4000-8000-00000000a001")),
        created_at=NOW,
        updated_at=NOW,
        first_name="Stable",
        last_name="Fixture",
        emails=(ContactEmail("stable@example.test", is_primary=True),),
        metadata={"source": "0.9.0-stable"},
    )
    with SQLAlchemyUnitOfWork(factory) as uow:
        uow.contacts.save(fixture)
        uow.commit()

    # V1 RC introduces no persistence schema delta over the 0.9.0 stable head.
    command.upgrade(config, "head")

    assert _current_revision(production_engine) == "0003"
    assert _schema_diffs(production_engine) == []
    with SQLAlchemyUnitOfWork(factory) as uow:
        assert uow.contacts.get(fixture.id) == fixture


def test_v1_contact_merge_commits_all_postgresql_participants_atomically(
    production_engine: Engine,
) -> None:
    factory = _session_factory(production_engine)
    clock = FixedClock(NOW)
    crm = _crm(factory, clock).with_context(
        actor_id="rc03-operator",
        correlation_id="rc03-merge-commit",
    )

    primary = crm.contacts.create(
        first_name="Ada",
        last_name="Lovelace",
        emails=(ContactEmail("ada@example.test", is_primary=True),),
    )
    duplicate = crm.contacts.create(
        first_name="Ada",
        last_name="Lovelace",
        emails=(ContactEmail("ADA@example.test", is_primary=True),),
    )
    organization = crm.organizations.create(legal_name="Analytical Engines Ltd")

    primary_ref = EntityReference("contact", primary.id)
    duplicate_ref = EntityReference("contact", duplicate.id)

    activity = crm.activities.log(
        type="meeting",
        subject="Duplicate-owned activity",
        participants=(ActivityParticipant(duplicate_ref, is_primary=True),),
    )
    relationship = crm.relationships.create(
        source=RelationshipEndpoint.contact(duplicate.id),
        target=RelationshipEndpoint.organization(organization.id),
        relationship_type=RelationshipType("employment"),
        role="founder",
    )
    imported = crm.tags.create("Imported")
    crm.tags.assign(imported.id, duplicate_ref)

    segment = crm.custom_fields.define(
        key="segment",
        label="Segment",
        field_type=CustomFieldType.STRING,
        applies_to=("contact",),
    )
    crm.custom_fields.set_value(segment.id, duplicate_ref, "enterprise")
    identity = crm.external_identities.attach(
        duplicate,
        system="legacy_crm",
        external_id="legacy-ada-42",
        metadata={"source": "rc03"},
    )

    result = MergeService(
        crm._runtime.uow_factory,
        clock=FixedClock(MERGED_AT),
    ).merge_contacts(
        primary_id=primary.id,
        duplicate_id=duplicate.id,
        provenance=_provenance(duplicate.id),
        actor_id="rc03-operator",
        correlation_id="rc03-merge-commit",
    )

    assert result.primary.id == primary.id
    assert result.duplicate.status is ContactStatus.ARCHIVED
    assert result.statistics.activities_reassigned == 1
    assert result.statistics.relationships_reassigned == 1
    assert result.statistics.tags_added == 1
    assert result.statistics.custom_fields_moved == 1
    assert result.statistics.external_identities_moved == 1
    assert result.audit_entry.action == "contact.merged"

    # New runtime/new Sessions prove committed durability rather than identity-map reuse.
    reloaded = _crm(factory)
    assert reloaded.contacts.get(duplicate.id).status is ContactStatus.ARCHIVED

    with reloaded._runtime.uow_factory() as uow:
        persisted_activity = uow.activities.get(activity.id)
        persisted_relationship = uow.relationships.get(relationship.id)

        assert persisted_activity.participants[0].reference == primary_ref
        assert persisted_relationship.source == RelationshipEndpoint.contact(primary.id)
        assert uow.tags.list_for_entity(duplicate_ref, OffsetPageRequest()).total == 0
        assert {
            tag.id
            for tag in uow.tags.list_for_entity(
                primary_ref,
                OffsetPageRequest(),
            ).items
        } == {imported.id}
        assert uow.custom_fields.get_value(segment.id, primary_ref).value == "enterprise"
        assert uow.custom_fields.find_value(segment.id, duplicate_ref) is None

    moved_identity = reloaded.external_identities.resolve("legacy_crm", "legacy-ada-42")
    assert moved_identity.id == identity.id
    assert moved_identity.entity == primary_ref
    merge_audits = [
        entry
        for entry in reloaded.audit.by_correlation("rc03-merge-commit").items
        if entry.action == "contact.merged"
    ]
    assert len(merge_audits) == 1
    assert merge_audits[0].changes["duplicate_id"] == str(duplicate.id)
    assert merge_audits[0].changes["provenance"]["decision"] == "duplicate"


def test_v1_contact_merge_conflict_rolls_back_every_postgresql_participant(
    production_engine: Engine,
) -> None:
    factory = _session_factory(production_engine)
    crm = _crm(factory)

    primary = crm.contacts.create(
        first_name="Ada",
        last_name="Lovelace",
        emails=(ContactEmail("ada@example.test", is_primary=True),),
    )
    duplicate = crm.contacts.create(
        first_name="Ada",
        last_name="Lovelace",
        emails=(ContactEmail("ADA@example.test", is_primary=True),),
    )
    primary_ref = EntityReference("contact", primary.id)
    duplicate_ref = EntityReference("contact", duplicate.id)

    rollback_tag = crm.tags.create("Rollback")
    crm.tags.assign(rollback_tag.id, duplicate_ref)
    tier = crm.custom_fields.define(
        key="tier",
        label="Tier",
        field_type=CustomFieldType.STRING,
        applies_to=("contact",),
    )
    crm.custom_fields.set_value(tier.id, primary_ref, "gold")
    crm.custom_fields.set_value(tier.id, duplicate_ref, "silver")

    with pytest.raises(ConflictError) as error:
        MergeService(
            crm._runtime.uow_factory,
            clock=FixedClock(MERGED_AT),
        ).merge_contacts(
            primary_id=primary.id,
            duplicate_id=duplicate.id,
            provenance=_provenance(duplicate.id),
            actor_id="rc03-operator",
            correlation_id="rc03-merge-rollback",
        )

    assert error.value.code == "merge.custom_field.conflict"

    reloaded = _crm(factory)
    assert reloaded.contacts.get(primary.id).status is ContactStatus.ACTIVE
    assert reloaded.contacts.get(duplicate.id).status is ContactStatus.ACTIVE
    assert reloaded.tags.list_for_entity(primary_ref).total == 0
    assert reloaded.tags.list_for_entity(duplicate_ref).items == (rollback_tag,)
    assert reloaded.custom_fields.get_value(tier.id, primary_ref).value == "gold"
    assert reloaded.custom_fields.get_value(tier.id, duplicate_ref).value == "silver"
    assert reloaded.audit.by_correlation("rc03-merge-rollback").total == 0
