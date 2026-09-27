"""Run Audit repository contracts against the SQLAlchemy adapter."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from pycrmkit.audit import AuditEntry, AuditEntryId, AuditRepository
from pycrmkit.storage.sqlalchemy.repositories import SQLAlchemyAuditRepository

from ...contracts.audit_repository import assert_audit_repository_contract


def test_sqlalchemy_audit_repository_contract(session: Session) -> None:
    repository: AuditRepository = SQLAlchemyAuditRepository(session)
    assert_audit_repository_contract(repository)


def test_nested_frozen_audit_changes_round_trip_through_json_storage(
    session: Session,
) -> None:
    repository = SQLAlchemyAuditRepository(session)
    entry = AuditEntry(
        id=AuditEntryId(UUID("00000000-0000-4000-8000-00000000a901")),
        actor_id="audit-json-regression",
        action="contact.merged",
        entity_type="contact",
        entity_id="contact-1",
        occurred_at=datetime(2026, 9, 27, 16, 0, tzinfo=UTC),
        changes={
            "statistics": {
                "activities_reassigned": 1,
                "tags_added": 2,
            },
            "provenance": {
                "decision": "duplicate",
                "matched_signals": ["email", "phone"],
            },
        },
        correlation_id="audit-json-regression",
    )

    repository.append(entry)
    session.commit()
    session.expire_all()

    reloaded = repository.get(entry.id)

    assert reloaded == entry
    assert reloaded.to_dict()["changes"] == {
        "statistics": {
            "activities_reassigned": 1,
            "tags_added": 2,
        },
        "provenance": {
            "decision": "duplicate",
            "matched_signals": ["email", "phone"],
        },
    }
