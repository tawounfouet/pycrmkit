"""LOT-32-002: stable promotion compatibility gate for the published Campaign RC.

The prior V1, V1.1 and Campaign candidate fixtures are immutable historical
contracts. This suite checks observable semantics against those references;
the workflow additionally compares frozen source paths to the tagged RC SHA.
"""
from __future__ import annotations

import json
from dataclasses import fields
from pathlib import Path

import pytest

from pycrmkit import CRM
from pycrmkit.campaigns import UNSET, CampaignStatus, CampaignUpdate
from pycrmkit.events import DomainEvent, EventSerializer, default_event_registry
from pycrmkit.exceptions import ConflictError, InvalidStateError, ValidationError

HERE = Path(__file__).resolve().parent
V1 = json.loads((HERE / "public_api_v1_candidate.json").read_text(encoding="utf-8"))
V11 = json.loads((HERE / "public_api_v1_1_candidate.json").read_text(encoding="utf-8"))
V12 = json.loads(
    (HERE / "public_api_v1_2_campaign_candidate.json").read_text(encoding="utf-8")
)
HTTP = HERE.parent / "contracts" / "campaign_http"


def test_stable_promotion_preserves_original_manifest_lineage() -> None:
    assert V1["version"] == "1.0.0"
    assert V11["extends"] == "tests/compatibility/public_api_v1_candidate.json"
    assert V12["extends"] == [
        "tests/compatibility/public_api_v1_candidate.json",
        "tests/compatibility/public_api_v1_1_candidate.json",
    ]
    assert (V12["baseline_release"], V12["target_release"], V12["promoted_release"]) == (
        "1.2.0b3", "1.2.0rc1", "1.2.0",
    )
    assert len(V12["facade_signatures"]) == 26
    assert len(V12["event_types"]) == 16
    assert V12["invariants"]["max_campaign_import_rows"] == 1000


def test_status_dto_unset_and_error_code_contract() -> None:
    assert [status.value for status in CampaignStatus] == V12["campaign_status_values"]
    assert [field.name for field in fields(CampaignUpdate)] == V12["invariants"]["unsets"]
    assert all(getattr(CampaignUpdate(), name) is UNSET for name in V12["invariants"]["unsets"])
    assert CampaignUpdate(description=None).description is None
    assert CampaignUpdate(name="New value").name == "New value"
    assert {"key", "status", "revision", "archived_at"}.issubset(
        V12["invariants"]["exclude_patch_fields"]
    )


def test_campaign_rc_event_envelopes_serialize_with_stable_v1_fields() -> None:
    crm = CRM.memory(webhook_auto_delivery=False)
    received: list[DomainEvent] = []
    for event_type in ("campaign.created", "campaign.updated", "campaign.archived"):
        crm.events.subscribe(event_type, received.append)

    created = crm.campaigns.create(
        key="stable-event-envelope", name="Stable contract", description="Initial"
    )
    changed = crm.campaigns.update(
        created.id,
        CampaignUpdate(description=None),
        expected_revision=created.revision,
    )
    crm.campaigns.archive(created.id, expected_revision=changed.revision)
    assert [str(event.type) for event in received] == [
        "campaign.created",
        "campaign.updated",
        "campaign.archived",
    ]

    serializer = EventSerializer(default_event_registry())
    for event in received:
        assert event.schema_version == 1
        assert event.aggregate_type == "campaign"
        assert event.aggregate_id == str(created.id)
        wire = serializer.to_dict(event)
        assert list(wire) == V1["event_envelope_fields"]
        assert DomainEvent.from_dict(wire) == event

    assert dict(received[0].payload) == {
        "key": created.key, "status": "draft", "revision": 1,
    }
    assert dict(received[1].payload) == {"revision": changed.revision}
    assert dict(received[2].payload) == {"status": "archived", "revision": 3}


def test_patch_omitted_null_value_revision_and_archive_are_distinct() -> None:
    crm = CRM.memory(webhook_auto_delivery=False)
    created = crm.campaigns.create(
        key="stable-patch-semantics",
        name="Original",
        description="Keep until explicitly cleared",
    )
    omitted = crm.campaigns.update(
        created.id, CampaignUpdate(), expected_revision=1
    )
    assert omitted.revision == 1
    assert omitted.description == "Keep until explicitly cleared"

    cleared = crm.campaigns.update(
        created.id, CampaignUpdate(description=None), expected_revision=1
    )
    assert cleared.revision == 2
    assert cleared.description is None

    with_value = crm.campaigns.update(
        created.id, CampaignUpdate(name="Replacement"), expected_revision=2
    )
    assert with_value.revision == 3
    assert with_value.name == "Replacement"

    with pytest.raises(ConflictError) as stale:
        crm.campaigns.update(
            created.id, CampaignUpdate(name="Unwanted"), expected_revision=2
        )
    assert stale.value.code == "campaign.revision.conflict"
    assert crm.campaigns.get(created.id).name == "Replacement"

    archived = crm.campaigns.archive(created.id, expected_revision=3)
    assert archived.revision == 4
    assert archived.status is CampaignStatus.ARCHIVED
    with pytest.raises(InvalidStateError) as denied:
        crm.campaigns.update(
            created.id, CampaignUpdate(name="After archive"), expected_revision=4
        )
    assert denied.value.code == "campaign.archived"


def test_campaign_validation_error_is_machine_readable() -> None:
    crm = CRM.memory(webhook_auto_delivery=False)
    with pytest.raises(ValidationError) as error:
        crm.campaigns.create(key="!!!", name="Invalid")
    assert error.value.code == "campaign.key.invalid"
    assert error.value.code in V12["domain_error_codes"]


def test_rc_http_goldens_are_historical_not_regenerated_by_stable_gate() -> None:
    openapi = json.loads(
        (HTTP / "openapi_golden_v1_2.json").read_text(encoding="utf-8")
    )
    response = json.loads(
        (HTTP / "response_golden_v1_2.json").read_text(encoding="utf-8")
    )
    assert openapi["source_release"] == "1.2.0b3"
    assert openapi["target_release"] == "1.2.0rc1"
    assert response["baseline"] == "v1.2.0b3"
    assert {
        "/crm/campaigns",
        "/crm/campaigns/{campaign_id}/audience/count",
        "/crm/campaigns/{campaign_id}/communication-links",
    }.issubset(openapi["operations"])
    assert response["error_statuses"] == {
        "unauthenticated": 401,
        "forbidden": 403,
        "missing": 404,
        "stale_revision": 409,
        "invalid_patch": 422,
    }
    assert response["error_codes"]["stale_revision"] == "campaign.revision.conflict"
    assert response["error_codes"]["invalid_patch"] == "request.validation_error"
    assert set(response["campaign"]) == set(response["after_clear"])
    assert response["listing"]["total"] == 1
