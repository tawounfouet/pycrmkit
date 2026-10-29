"""LOT-31-006 - Campaign domain invariants and Memory UoW fault injection.

These are regression/qualification contracts for v1.2.0b3, not new behavior.
Memory commits and synchronous subscribers are intentionally distinguished.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from pycrmkit import CRM
from pycrmkit.campaigns import CampaignQuery, CampaignService, CampaignStatus, CampaignUpdate
from pycrmkit.communication import CommunicationRecordId
from pycrmkit.contacts import ContactId
from pycrmkit.core.references import EntityReference
from pycrmkit.exceptions import (
    ConflictError,
    DuplicateError,
    InvalidStateError,
    NotFoundError,
    ValidationError,
)
from pycrmkit.storage.memory._state import MemoryStore

NOW = datetime(2026, 10, 29, 1, tzinfo=UTC)


@pytest.fixture
def crm() -> CRM:
    return CRM.memory(webhook_auto_delivery=False)


def _events(crm: CRM, *names: str) -> list[str]:
    observed: list[str] = []
    for name in names:
        crm.events.subscribe(
            name,
            lambda event, observed=observed: observed.append(str(event.type)),
        )
    return observed


def test_invalid_lifecycle_transitions_keep_revision_and_no_events(crm: CRM) -> None:
    campaign = crm.campaigns.create(key="invalid-lifecycle", name="Draft")
    observed = _events(crm, "campaign.activated", "campaign.completed")
    with pytest.raises(InvalidStateError) as error:
        crm.campaigns.complete(campaign.id, expected_revision=1)
    assert error.value.code == "campaign.complete.invalid_state"
    assert crm.campaigns.get(campaign.id).revision == 1
    assert observed == []

    activated = crm.campaigns.activate(campaign.id, expected_revision=1)
    assert activated.status is CampaignStatus.ACTIVE
    assert activated.revision == 2
    assert crm.campaigns.activate(campaign.id, expected_revision=2).revision == 2
    assert observed == ["campaign.activated"]


def test_idempotent_state_transitions_do_not_emit_extra_events(crm: CRM) -> None:
    campaign = crm.campaigns.create(key="idempotent-lifecycle", name="Lifecycle")
    observed = _events(
        crm, "campaign.activated", "campaign.completed", "campaign.archived"
    )
    active = crm.campaigns.activate(campaign.id, expected_revision=1)
    repeated_active = crm.campaigns.activate(campaign.id, expected_revision=2)
    assert repeated_active.revision == active.revision == 2
    completed = crm.campaigns.complete(campaign.id, expected_revision=2)
    repeated_completed = crm.campaigns.complete(campaign.id, expected_revision=3)
    assert repeated_completed.revision == completed.revision == 3
    archived = crm.campaigns.archive(campaign.id, expected_revision=3)
    repeated_archived = crm.campaigns.archive(campaign.id, expected_revision=4)
    assert repeated_archived.revision == archived.revision == 4
    assert crm.campaigns.get(campaign.id).status is CampaignStatus.ARCHIVED
    assert observed == [
        "campaign.activated", "campaign.completed", "campaign.archived"
    ]


def test_completed_cannot_reactivate_and_preserves_state(crm: CRM) -> None:
    campaign = crm.campaigns.create(key="completed-immutable-flow", name="Flow")
    crm.campaigns.activate(campaign.id)
    completed = crm.campaigns.complete(campaign.id)
    observed = _events(crm, "campaign.activated")
    with pytest.raises(InvalidStateError) as error:
        crm.campaigns.activate(campaign.id, expected_revision=completed.revision)
    assert error.value.code == "campaign.activate.invalid_state"
    current = crm.campaigns.get(campaign.id)
    assert current.status is CampaignStatus.COMPLETED
    assert current.revision == completed.revision
    assert observed == []


def test_stale_revisions_cannot_write_or_emit_events(crm: CRM) -> None:
    campaign = crm.campaigns.create(key="stale-revision", name="Original")
    updated = crm.campaigns.update(
        campaign.id, CampaignUpdate(name="Changed"), expected_revision=1
    )
    assert updated.revision == 2
    observed = _events(
        crm, "campaign.updated", "campaign.activated", "campaign.archived"
    )
    for attempt in (
        lambda: crm.campaigns.update(
            campaign.id, CampaignUpdate(name="Stale"), expected_revision=1
        ),
        lambda: crm.campaigns.activate(campaign.id, expected_revision=1),
        lambda: crm.campaigns.archive(campaign.id, expected_revision=1),
    ):
        with pytest.raises(ConflictError) as error:
            attempt()
        assert error.value.code == "campaign.revision.conflict"
        assert error.value.context["expected"] == 1
        assert error.value.context["actual"] == 2
    current = crm.campaigns.get(campaign.id)
    assert current.name == "Changed"
    assert current.status is CampaignStatus.DRAFT
    assert current.revision == 2
    assert observed == []


def test_archived_state_rejects_all_campaign_mutations(crm: CRM) -> None:
    campaign = crm.campaigns.create(key="frozen-archive", name="Archive")
    archived = crm.campaigns.archive(campaign.id, expected_revision=1)
    missing = EntityReference(
        "contact", ContactId.parse("00000000-0000-4000-8000-000000000601")
    )
    missing_comm = CommunicationRecordId.parse(
        "00000000-0000-4000-8000-000000000602"
    )
    observed = _events(
        crm, "campaign.updated", "campaign.member_added",
        "campaign.attribution_added", "campaign.communication_linked",
    )
    attempts = (
        lambda: crm.campaigns.update(
            campaign.id, CampaignUpdate(name="bad"), expected_revision=2
        ),
        lambda: crm.campaigns.activate(campaign.id, expected_revision=2),
        lambda: crm.campaigns.complete(campaign.id, expected_revision=2),
        lambda: crm.campaigns.add_member(campaign.id, missing),
        lambda: crm.campaigns.add_attribution(
            campaign.id, missing, source="web", external_ref=None
        ),
        lambda: crm.campaigns.link_communication(campaign.id, missing_comm),
    )
    for attempt in attempts:
        with pytest.raises(InvalidStateError) as error:
            attempt()
        assert error.value.code == "campaign.archived"
    assert crm.campaigns.get(campaign.id).revision == archived.revision
    assert crm.campaigns.list(CampaignQuery(include_archived=True)).total == 1
    assert observed == []


def test_validation_errors_preserve_previous_campaign_and_emit_nothing(
    crm: CRM,
) -> None:
    campaign = crm.campaigns.create(
        key="invalid-fields", name="Stable",
        description="Keep me", metadata={"source": "original"},
    )
    observed = _events(crm, "campaign.updated")
    attempts = (
        (CampaignUpdate(name=" "), "campaign.name.required"),
        (
            CampaignUpdate(
                starts_at=NOW + timedelta(days=3),
                ends_at=NOW + timedelta(days=1),
            ),
            "campaign.schedule.invalid",
        ),
        (CampaignUpdate(description="x" * 2001), "campaign.description.too_long"),
    )
    for changes, code in attempts:
        with pytest.raises(ValidationError) as error:
            crm.campaigns.update(campaign.id, changes, expected_revision=1)
        assert error.value.code == code
    current = crm.campaigns.get(campaign.id)
    assert current.revision == 1
    assert current.description == "Keep me"
    assert current.name == "Stable"
    assert current.metadata == {"source": "original"}
    assert observed == []


def test_missing_references_are_rejected_without_partial_linkage(crm: CRM) -> None:
    campaign = crm.campaigns.create(key="missing-references", name="References")
    missing = EntityReference(
        "contact", ContactId.parse("00000000-0000-4000-8000-000000000611")
    )
    missing_comm = CommunicationRecordId.parse(
        "00000000-0000-4000-8000-000000000612"
    )
    observed = _events(
        crm, "campaign.member_added", "campaign.attribution_added",
        "campaign.communication_linked",
    )
    with pytest.raises(ValidationError) as member_error:
        crm.campaigns.add_member(campaign.id, missing)
    assert member_error.value.code == "campaign.member.not_found"
    with pytest.raises(ValidationError) as attr_error:
        crm.campaigns.add_attribution(campaign.id, missing, source="event")
    assert attr_error.value.code == "campaign.attribution.target.not_found"
    with pytest.raises(NotFoundError) as comm_error:
        crm.campaigns.link_communication(campaign.id, missing_comm)
    assert comm_error.value.code == "communication.record.not_found"
    assert crm.campaigns.members(campaign.id).total == 0
    assert crm.campaigns.attributions(campaign.id).total == 0
    assert crm.campaigns.communication_links(campaign.id).total == 0
    assert observed == []


def test_none_external_ref_is_normalized_and_uniqueness_guarded(crm: CRM) -> None:
    contact = crm.contacts.create(display_name="Ada")
    campaign = crm.campaigns.create(key="none-external-ref", name="Attribution")
    entity = EntityReference("contact", contact.id)
    observed = _events(crm, "campaign.attribution_added")
    created = crm.campaigns.add_attribution(
        campaign.id, entity, source="event", external_ref=None
    )
    assert created.external_ref is None
    with pytest.raises(DuplicateError) as error:
        crm.campaigns.add_attribution(
            campaign.id, entity, source="EVENT", external_ref=None
        )
    assert error.value.code == "campaign.attribution.duplicate"
    assert crm.campaigns.attributions(campaign.id).total == 1
    assert observed == ["campaign.attribution_added"]


def test_invalid_attribution_source_does_not_commit(crm: CRM) -> None:
    contact = crm.contacts.create(display_name="Ada")
    campaign = crm.campaigns.create(key="invalid-attribution", name="Attribution")
    entity = EntityReference("contact", contact.id)
    observed = _events(crm, "campaign.attribution_added")
    with pytest.raises(ValidationError) as error:
        crm.campaigns.add_attribution(
            campaign.id, entity, source="   ", metadata={"safe": "value"}
        )
    assert error.value.code == "campaign.attribution.source.required"
    assert crm.campaigns.attributions(campaign.id).total == 0
    assert observed == []


def test_invalid_runtime_metadata_input_is_atomic_not_a_domain_code(
    crm: CRM,
) -> None:
    campaign = crm.campaigns.create(key="invalid-metadata", name="Valid")
    observed = _events(crm, "campaign.updated")
    # This is a direct Python caller violating CampaignUpdate's declared type.
    # Current b3 raises TypeError; no new domain ValidationError is invented.
    with pytest.raises(TypeError):
        crm.campaigns.update(
            campaign.id,
            CampaignUpdate(metadata=None),  # type: ignore[arg-type]
            expected_revision=1,
        )
    assert crm.campaigns.get(campaign.id).revision == 1
    assert observed == []


def test_injected_precommit_failure_rolls_back_state_and_events(
    crm: CRM, monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed = _events(crm, "campaign.created")
    original = MemoryStore._commit

    def fail_commit(_store: MemoryStore, _state: object) -> None:
        assert observed == []
        raise RuntimeError("injected MemoryStore pre-commit failure")

    monkeypatch.setattr(MemoryStore, "_commit", fail_commit)
    with pytest.raises(RuntimeError, match="injected MemoryStore"):
        crm.campaigns.create(key="failed-commit", name="Never persisted")
    monkeypatch.setattr(MemoryStore, "_commit", original)
    assert crm.campaigns.list().total == 0
    assert observed == []
    # No leaked active Memory transaction: subsequent valid UoW succeeds.
    retry = crm.campaigns.create(key="successful-retry", name="Persisted")
    assert crm.campaigns.get(retry.id).name == "Persisted"
    assert observed == ["campaign.created"]


def test_rollback_discards_staged_campaign_state_and_domain_events(crm: CRM) -> None:
    observed = _events(crm, "campaign.created")
    with crm._runtime.uow_factory() as uow:
        campaign = CampaignService(
            uow.campaigns,
            clock=crm._runtime.clock,
            id_factory=crm._runtime.id_factory,
        ).create(key="staged-rollback", name="Pending")
        crm._runtime.record_change(
            uow, event_type="campaign.created",
            aggregate_type="campaign", aggregate_id=campaign.id,
            payload={"key": campaign.key, "revision": campaign.revision},
        )
        assert len(uow.pending_events) == 1
        assert observed == []
        uow.rollback()
        assert uow.pending_events == ()
    assert crm.campaigns.list().total == 0
    assert observed == []


def test_postcommit_subscriber_exception_does_not_undo_committed_state(
    crm: CRM,
) -> None:
    def broken(_event: object) -> None:
        raise RuntimeError("injected downstream subscriber failure")

    crm.events.subscribe("campaign.created", broken)
    with pytest.raises(RuntimeError, match="injected downstream subscriber"):
        crm.campaigns.create(key="committed-before-delivery", name="Committed")
    page = crm.campaigns.list()
    assert page.total == 1
    assert page.items[0].key == "committed-before-delivery"
