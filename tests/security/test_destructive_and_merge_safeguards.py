"""Integrity safeguards for destructive operations and duplicate merge."""

from __future__ import annotations

from uuid import UUID

import pytest

from pycrmkit import CRM
from pycrmkit.contacts import ContactId, ContactStatus, ContactUpdate
from pycrmkit.dedup import (
    ConflictSeverity,
    DedupConflict,
    DedupDecision,
    DedupProvenance,
    DedupSignal,
    MergeService,
)
from pycrmkit.exceptions import ConflictError, InvalidStateError, ValidationError
from pycrmkit.storage.memory import MemoryStore, MemoryUnitOfWork


def _contact_id(value: int) -> ContactId:
    return ContactId(UUID(int=value))


def test_public_facades_do_not_expose_generic_hard_delete_or_purge() -> None:
    crm = CRM.memory(webhook_auto_delivery=False)
    for namespace in (
        crm.contacts,
        crm.organizations,
        crm.relationships,
        crm.activities,
        crm.tasks,
        crm.external_identities,
        crm.webhooks,
    ):
        assert not hasattr(namespace, "delete")
        assert not hasattr(namespace, "purge")
        assert not hasattr(namespace, "hard_delete")


def test_archived_contact_cannot_be_mutated_through_public_facade() -> None:
    crm = CRM.memory(webhook_auto_delivery=False)
    contact = crm.contacts.create(display_name="Archive Safeguard")

    archived = crm.contacts.archive(contact.id)
    assert archived.status is ContactStatus.ARCHIVED

    with pytest.raises(InvalidStateError) as error:
        crm.contacts.update(
            contact.id,
            ContactUpdate(display_name="Should not change"),
        )
    assert error.value.code == "contact.archived"


def test_merge_requires_provenance_by_default() -> None:
    service = MergeService(lambda: MemoryUnitOfWork(MemoryStore()))

    with pytest.raises(ValidationError) as error:
        service.merge_contacts(
            primary_id=_contact_id(1),
            duplicate_id=_contact_id(2),
        )
    assert error.value.code == "merge.provenance.required"


def test_merge_rejects_forged_duplicate_decision_with_blocking_conflict() -> None:
    duplicate_id = _contact_id(2)
    provenance = DedupProvenance(
        candidate_entity_id=str(duplicate_id),
        score=100,
        decision=DedupDecision.DUPLICATE,
        matches=(),
        conflicts=(
            DedupConflict(
                signal=DedupSignal.CUSTOM_IDENTIFIER,
                severity=ConflictSeverity.BLOCKING,
                key="customer_number",
                incoming_values=("A-001",),
                candidate_values=("B-999",),
            ),
        ),
    )

    service = MergeService(lambda: MemoryUnitOfWork(MemoryStore()))
    with pytest.raises(ConflictError) as error:
        service.merge_contacts(
            primary_id=_contact_id(1),
            duplicate_id=duplicate_id,
            provenance=provenance,
        )

    assert error.value.code == "merge.provenance.blocking_conflict"
    assert error.value.context == {"signals": ("custom_identifier",)}
