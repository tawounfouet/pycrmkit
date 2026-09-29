from __future__ import annotations

from datetime import UTC, datetime

from django.test import override_settings
from rest_framework.test import APIClient

from pycrmkit import CRM
from pycrmkit.core.time import FixedClock
from pycrmkit.segments import (
    Predicate,
    QueryOperator,
    expression_to_dict,
)


def _crm() -> CRM:
    return CRM.memory(
        clock=FixedClock(datetime(2026, 9, 29, 9, 0, tzinfo=UTC)),
        webhook_auto_delivery=False,
    )


def test_drf_saved_query_segment_snapshot_and_bulk_membership_flow() -> None:
    crm = _crm()
    client = APIClient()

    with override_settings(PYCRMKIT_CRM_FACTORY=lambda: crm):
        ada = client.post(
            "/crm/contacts/",
            {"display_name": "Ada", "source": "LinkedIn"},
            format="json",
        ).data
        grace = client.post(
            "/crm/contacts/",
            {"display_name": "Grace", "source": "Newsletter"},
            format="json",
        ).data

        expression = expression_to_dict(
            Predicate("source", QueryOperator.EQ, "linkedin")
        )
        saved = client.post(
            "/crm/saved-queries/",
            {
                "key": "linkedin",
                "name": "LinkedIn",
                "entity_kind": "contact",
                "expression": expression,
            },
            format="json",
        )
        assert saved.status_code == 201
        saved_id = saved.data["id"]

        executed = client.get(
            f"/crm/saved-queries/{saved_id}/execute/?limit=10&offset=0"
        )
        assert executed.status_code == 200
        assert executed.data["total"] == 1
        assert executed.data["items"][0]["id"] == ada["id"]

        dynamic = client.post(
            "/crm/segments/",
            {
                "key": "linkedin-segment",
                "name": "LinkedIn Segment",
                "entity_kind": "contact",
                "mode": "dynamic",
                "expression": expression,
            },
            format="json",
        )
        assert dynamic.status_code == 201
        dynamic_id = dynamic.data["id"]

        members = client.get(f"/crm/segments/{dynamic_id}/members/")
        assert members.status_code == 200
        assert members.data["items"][0]["id"] == ada["id"]

        snapshot = client.post(
            f"/crm/segments/{dynamic_id}/snapshot/",
            {
                "key": "linkedin-frozen",
                "name": "LinkedIn Frozen",
            },
            format="json",
        )
        assert snapshot.status_code == 201
        assert snapshot.data["mode"] == "snapshot"

        static = client.post(
            "/crm/segments/",
            {
                "key": "manual-list",
                "name": "Manual List",
                "entity_kind": "contact",
                "mode": "static",
            },
            format="json",
        )
        assert static.status_code == 201
        static_id = static.data["id"]

        added = client.post(
            f"/crm/segments/{static_id}/members/",
            {
                "members": [
                    {"kind": "contact", "id": ada["id"]},
                    {"kind": "contact", "id": grace["id"]},
                ],
                "source": "api",
            },
            format="json",
        )
        assert added.status_code == 200
        assert len(added.data) == 2

        removed = client.post(
            f"/crm/segments/{static_id}/members/remove/",
            {"members": [{"kind": "contact", "id": grace["id"]}]},
            format="json",
        )
        assert removed.status_code == 200
        assert removed.data == {"removed": 1}
