"""Contract tests for Campaign FastAPI DTOs before HTTP exposure."""

from __future__ import annotations

from uuid import UUID

import pytest
from pydantic import ValidationError as PydanticValidationError

from pycrmkit.campaigns import UNSET
from pycrmkit.integrations.fastapi.campaign_schemas import (
    CampaignCreateRequest,
    CampaignMembersRequest,
    CampaignRevisionRequest,
    CampaignUpdateRequest,
)


def test_campaign_patch_preserves_omitted_values() -> None:
    patch = CampaignUpdateRequest(expected_revision=3)
    changes = patch.to_domain()
    assert patch.expected_revision == 3
    assert changes.name is UNSET
    assert changes.description is UNSET
    assert changes.starts_at is UNSET
    assert changes.ends_at is UNSET
    assert changes.owner_id is UNSET
    assert changes.metadata is UNSET


def test_campaign_patch_preserves_explicit_null_and_other_absences() -> None:
    patch = CampaignUpdateRequest.model_validate(
        {"expected_revision": 3, "description": None, "owner_id": None}
    )
    changes = patch.to_domain()
    assert changes.description is None
    assert changes.owner_id is None
    assert changes.name is UNSET
    assert changes.metadata is UNSET


def test_campaign_patch_never_exposes_status_or_key_mutations() -> None:
    with pytest.raises(PydanticValidationError):
        CampaignUpdateRequest.model_validate(
            {"expected_revision": 1, "status": "active"}
        )
    with pytest.raises(PydanticValidationError):
        CampaignUpdateRequest.model_validate(
            {"expected_revision": 1, "key": "new-campaign-key"}
        )


@pytest.mark.parametrize(
    "payload",
    [
        {"expected_revision": 0},
        {"expected_revision": -1},
        {"expected_revision": 1, "name": None},
        {"expected_revision": 1, "metadata": None},
    ],
)
def test_campaign_patch_rejects_invalid_input(payload: dict[str, object]) -> None:
    with pytest.raises(PydanticValidationError):
        CampaignUpdateRequest.model_validate(payload)


def test_campaign_status_transition_requires_revision() -> None:
    with pytest.raises(PydanticValidationError):
        CampaignRevisionRequest.model_validate({})
    assert CampaignRevisionRequest(expected_revision=2).expected_revision == 2


def test_campaign_create_rejects_naive_datetimes_and_extra_fields() -> None:
    with pytest.raises(PydanticValidationError):
        CampaignCreateRequest.model_validate(
            {
                "key": "renewal-q4",
                "name": "Renewal Q4",
                "starts_at": "2026-10-28T15:00:00",
            }
        )
    with pytest.raises(PydanticValidationError):
        CampaignCreateRequest.model_validate(
            {"key": "renewal-q4", "name": "Renewal Q4", "revision": 99}
        )


def test_campaign_member_schema_distinguishes_valid_and_duplicate_references() -> None:
    identity = "00000000-0000-4000-8000-000000000001"
    request = CampaignMembersRequest.model_validate(
        {"members": [{"kind": "contact", "id": identity}]}
    )
    assert request.references()[0].id.value == UUID(identity)

    with pytest.raises(PydanticValidationError):
        CampaignMembersRequest.model_validate(
            {
                "members": [
                    {"kind": "contact", "id": identity},
                    {"kind": "CONTACT", "id": identity},
                ]
            }
        )


def test_campaign_member_limit_rejects_more_than_1000() -> None:
    with pytest.raises(PydanticValidationError):
        CampaignMembersRequest.model_validate(
            {
                "members": [
                    {"kind": "contact", "id": str(UUID(int=index + 1))}
                    for index in range(1001)
                ]
            }
        )


def test_campaign_metadata_size_and_depth_are_bounded() -> None:
    with pytest.raises(PydanticValidationError):
        CampaignCreateRequest.model_validate(
            {
                "key": "renewal-q4",
                "name": "Renewal Q4",
                "metadata": {"data": "x" * 17000},
            }
        )

    nested: dict[str, object] = {}
    node = nested
    for _ in range(9):
        next_node: dict[str, object] = {}
        node["nested"] = next_node
        node = next_node
    with pytest.raises(PydanticValidationError):
        CampaignCreateRequest.model_validate(
            {"key": "renewal-q4", "name": "Renewal Q4", "metadata": nested}
        )
